//! SFTP 文件传输：目录列举、上传、下载。
//!
//! 和大文件打交道时最忌讳"整个读进内存"——这里一律按 32KB 分块流式搬运，
//! 并每块回一次进度，界面才能在传输队列里画进度条。

use std::path::{Path, PathBuf};

use russh_sftp::client::SftpSession;
use russh_sftp::client::error::Error as SftpError;
use tokio::io::{AsyncReadExt, AsyncWriteExt};

use crate::{SshError, SshSession};

/// SFTP 通道的建立入口挂在会话上——同一个 SSH 连接上可以同时跑终端和文件传输。
impl SshSession {
    pub async fn open_sftp(&self) -> Result<Sftp, SshError> {
        let channel = self
            .handle
            .channel_open_session()
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;
        let session = SftpSession::new(channel.into_stream())
            .await
            .map_err(|e| SshError::Protocol(format!("打开 SFTP 失败：{e}")))?;
        Ok(Sftp { inner: session })
    }
}

fn err(context: &str, e: SftpError) -> SshError {
    SshError::Protocol(format!("{context}：{e}"))
}

/// 远端目录项。字段和 WinSCP 的列表列一一对应：名字、大小、修改时间。
#[derive(Debug, Clone)]
pub struct RemoteEntry {
    pub name: String,
    pub path: String,
    pub is_dir: bool,
    pub size: u64,
    /// 修改时间（秒），0 表示服务器没给
    pub modified: i64,
}

pub struct Sftp {
    inner: SftpSession,
}


impl Sftp {
    /// 登录后的落脚点，通常是 /home/<user>。
    pub async fn home(&self) -> Result<String, SshError> {
        self.inner
            .canonicalize(".")
            .await
            .map_err(|e| err("取远端当前目录", e))
    }

    pub async fn list(&self, path: &str) -> Result<Vec<RemoteEntry>, SshError> {
        let mut out = Vec::new();
        let mut dir = self
            .inner
            .read_dir(path.to_string())
            .await
            .map_err(|e| err("列远端目录", e))?;
        while let Some(item) = dir.next() {
            let name = item.file_name();
            if name == "." || name == ".." {
                continue;
            }
            let meta = item.metadata();
            let full = join(path, &name);
            out.push(RemoteEntry {
                is_dir: meta.is_dir(),
                size: meta.size.unwrap_or(0),
                modified: meta.mtime.unwrap_or(0) as i64,
                path: full,
                name,
            });
        }
        // 目录在前、同类型按名字排——运维眼睛习惯了这一套
        out.sort_by(|a, b| {
            b.is_dir
                .cmp(&a.is_dir)
                .then_with(|| a.name.to_lowercase().cmp(&b.name.to_lowercase()))
        });
        Ok(out)
    }

    /// 远端 → 本地。先写同目录临时文件，传完再改名，避免中断留下半截文件。
    pub async fn download(
        &self,
        remote: &str,
        local: &Path,
        progress: &mut (dyn FnMut(u64, u64) + Send),
    ) -> Result<u64, SshError> {
        let mut file = self
            .inner
            .open(remote.to_string())
            .await
            .map_err(|e| err("打开远端文件", e))?;
        let total = self
            .inner
            .metadata(remote.to_string())
            .await
            .ok()
            .and_then(|m| m.size)
            .unwrap_or(0);

        if let Some(parent) = local.parent() {
            std::fs::create_dir_all(parent).map_err(|e| SshError::Protocol(e.to_string()))?;
        }
        let tmp: PathBuf = local.with_extension("portio-part");
        let mut out = tokio::fs::File::create(&tmp)
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;

        let mut buf = vec![0u8; 32 * 1024];
        let mut done = 0u64;
        loop {
            let n = file
                .read(&mut buf)
                .await
                .map_err(|e| SshError::Protocol(e.to_string()))?;
            if n == 0 {
                break;
            }
            out.write_all(&buf[..n])
                .await
                .map_err(|e| SshError::Protocol(e.to_string()))?;
            done += n as u64;
            progress(done, total);
        }
        out.flush()
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;
        drop(out);
        tokio::fs::rename(&tmp, local)
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;
        Ok(done)
    }

    /// 本地 → 远端。断点续传先不做，但 resumable 的钩子留在这里。
    pub async fn upload(
        &self,
        local: &Path,
        remote: &str,
        progress: &mut (dyn FnMut(u64, u64) + Send),
    ) -> Result<u64, SshError> {
        let mut input = tokio::fs::File::open(local)
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;
        let total = input.metadata().await.map(|m| m.len()).unwrap_or(0);
        let mut file = self
            .inner
            .create(remote.to_string())
            .await
            .map_err(|e| err("创建远端文件", e))?;

        let mut buf = vec![0u8; 32 * 1024];
        let mut done = 0u64;
        loop {
            let n = input
                .read(&mut buf)
                .await
                .map_err(|e| SshError::Protocol(e.to_string()))?;
            if n == 0 {
                break;
            }
            file.write_all(&buf[..n])
                .await
                .map_err(|e| SshError::Protocol(e.to_string()))?;
            done += n as u64;
            progress(done, total);
        }
        file.flush()
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;
        drop(file);
        Ok(done)
    }

    pub async fn mkdir(&self, path: &str) -> Result<(), SshError> {
        self.inner
            .create_dir(path.to_string())
            .await
            .map_err(|e| err("建远端目录", e))
    }

    pub async fn remove(&self, path: &str, is_dir: bool) -> Result<(), SshError> {
        if is_dir {
            self.inner
                .remove_dir(path.to_string())
                .await
                .map_err(|e| err("删远端目录", e))
        } else {
            self.inner
                .remove_file(path.to_string())
                .await
                .map_err(|e| err("删远端文件", e))
        }
    }

    pub async fn rename(&self, from: &str, to: &str) -> Result<(), SshError> {
        self.inner
            .rename(from.to_string(), to.to_string())
            .await
            .map_err(|e| err("重命名远端文件", e))
    }
}

/// POSIX 拼路径。远端不认 Windows 反斜杠，这里统一用 `/`。
pub fn join(dir: &str, name: &str) -> String {
    if dir.is_empty() || name.starts_with('/') {
        return name.to_string();
    }
    if dir.ends_with('/') {
        format!("{dir}{name}")
    } else {
        format!("{dir}/{name}")
    }
}

/// 上一级目录。到 `/` 就停在 `/`。
pub fn parent_of(path: &str) -> String {
    let trimmed = path.trim_end_matches('/');
    match trimmed.rfind('/') {
        Some(0) => "/".to_string(),
        Some(i) => trimmed[..i].to_string(),
        None => "/".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn join_handles_slashes() {
        assert_eq!(join("/var", "log"), "/var/log");
        assert_eq!(join("/var/", "log"), "/var/log");
        assert_eq!(join("", "log"), "log");
    }

    #[test]
    fn parent_stops_at_root() {
        assert_eq!(parent_of("/var/log"), "/var");
        assert_eq!(parent_of("/var"), "/");
        assert_eq!(parent_of("/"), "/");
    }
}
