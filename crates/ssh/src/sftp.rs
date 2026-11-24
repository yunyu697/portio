//! SFTP 文件传输：目录列举、上传、下载。
//!
//! 和大文件打交道时最忌讳"整个读进内存"——这里一律按 32KB 分块流式搬运，
//! 并每块回一次进度，界面才能在传输队列里画进度条。

use std::io::SeekFrom;
use std::path::{Path, PathBuf};

use russh_sftp::client::error::Error as SftpError;
use russh_sftp::client::SftpSession;
use russh_sftp::protocol::OpenFlags;
use tokio::io::{AsyncReadExt, AsyncSeekExt, AsyncWriteExt};

use crate::{SshError, SshSession};

/// SFTP 通道的建立入口挂在会话上——同一个 SSH 连接上可以同时跑终端和文件传输。
impl SshSession {
    pub async fn open_sftp(&self) -> Result<Sftp, SshError> {
        let channel = self
            .handle
            .channel_open_session()
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;
        // RFC 4254：必须先在会话通道上请求 sftp 子系统，服务端才会拉起 sftp-server。
        // 漏掉这一步直接发 FXP_INIT，对端不会回版本包，只会干等到请求超时，
        // 前端再把那条 Timeout 误判成"网络不可达"。
        channel
            .request_subsystem(true, "sftp")
            .await
            .map_err(|e| SshError::Protocol(format!("请求 SFTP 子系统失败：{e}")))?;
        let session = SftpSession::new(channel.into_stream())
            .await
            .map_err(|e| SshError::Protocol(format!("打开 SFTP 失败：{e}")))?;
        Ok(Sftp { inner: session })
    }
}

fn err(context: &str, e: SftpError) -> SshError {
    SshError::Protocol(format!("{context}：{e}"))
}

/// 远端目录项。字段和 WinSCP 的列表列一一对应：名字、大小、修改时间，外加权限位。
#[derive(Debug, Clone)]
pub struct RemoteEntry {
    pub name: String,
    pub path: String,
    pub is_dir: bool,
    pub size: u64,
    /// 修改时间（秒），0 表示服务器没给
    pub modified: i64,
    /// 服务器给的权限位（POSIX mode），`None` 表示这次 readdir 没带
    pub perm: Option<u32>,
}

/// 把 POSIX mode 排成 `ls -l` 那串：`drwxr-xr-x`。
/// 只认最常见的 rwx 三组，setuid / sticky 这些少见位统一显示成 `s` / `t`。
pub fn perm_string(perm: Option<u32>, is_dir: bool) -> String {
    let Some(mode) = perm else {
        return "—".to_string();
    };
    let mut out = String::with_capacity(10);
    out.push(if is_dir { 'd' } else { '-' });
    let bits = [
        (0o400, 'r'),
        (0o200, 'w'),
        (0o100, 'x'),
        (0o040, 'r'),
        (0o020, 'w'),
        (0o010, 'x'),
        (0o004, 'r'),
        (0o002, 'w'),
        (0o001, 'x'),
    ];
    for (bit, ch) in bits {
        out.push(if mode & bit != 0 { ch } else { '-' });
    }
    out
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
        let dir = self
            .inner
            .read_dir(path.to_string())
            .await
            .map_err(|e| err("列远端目录", e))?;
        for item in dir {
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
                perm: meta.permissions,
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

    /// 远端 → 本地。先写半截文件，传完再改名，避免中断留下半截文件冒充成品。
    /// 中断后重下一次会从半截文件末尾接着传（见 `resume`），不用从头再来。
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
        let tmp: PathBuf = crate::resume::part_path(local);
        let part_len = tokio::fs::metadata(&tmp)
            .await
            .map(|m| m.len())
            .unwrap_or(0);
        let start = crate::resume::resume_offset(part_len, total);
        if start == 0 && part_len > 0 {
            // 半截文件已经不能续（远端变小或早就传满），留着只会误导下一次，直接丢掉
            let _ = tokio::fs::remove_file(&tmp).await;
        }
        let mut out = if start > 0 {
            tokio::fs::OpenOptions::new()
                .append(true)
                .open(&tmp)
                .await
                .map_err(|e| SshError::Protocol(e.to_string()))?
        } else {
            tokio::fs::File::create(&tmp)
                .await
                .map_err(|e| SshError::Protocol(e.to_string()))?
        };
        if start > 0 {
            file.seek(SeekFrom::Start(start))
                .await
                .map_err(|e| SshError::Protocol(format!("远端定位到 {start} 失败：{e}")))?;
        }

        let mut buf = vec![0u8; 32 * 1024];
        let mut done = start;
        progress(done, total);
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

        // 远端先写半截文件，传完改名。中断后再传，从半截长度接着走。
        let tmp = crate::resume::remote_part_path(remote);
        let part_len = self
            .inner
            .metadata(tmp.clone())
            .await
            .ok()
            .and_then(|m| m.size)
            .unwrap_or(0);
        let start = crate::resume::resume_offset(part_len, total);
        if start == 0 && part_len > 0 {
            // 半截文件已经不能续（本地文件变小或早就传满），删掉重来
            let _ = self.inner.remove_file(tmp.clone()).await;
        }

        let mut file = if start > 0 {
            input
                .seek(SeekFrom::Start(start))
                .await
                .map_err(|e| SshError::Protocol(format!("本地定位到 {start} 失败：{e}")))?;
            // 半截文件已存在，只申请写权限（create 会截断，那就白续了）
            let mut f = self
                .inner
                .open_with_flags(tmp.clone(), OpenFlags::WRITE)
                .await
                .map_err(|e| err("打开远端半截文件", e))?;
            f.seek(SeekFrom::Start(start))
                .await
                .map_err(|e| SshError::Protocol(format!("远端定位到 {start} 失败：{e}")))?;
            f
        } else {
            self.inner
                .create(tmp.clone())
                .await
                .map_err(|e| err("创建远端文件", e))?
        };

        let mut buf = vec![0u8; 32 * 1024];
        let mut done = start;
        progress(done, total);
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
        if let Err(e) = self.inner.rename(tmp.clone(), remote.to_string()).await {
            // 有的服务器 rename 不覆盖同名文件，先删目标再改名
            let _ = self.inner.remove_file(remote.to_string()).await;
            self.inner
                .rename(tmp.clone(), remote.to_string())
                .await
                .map_err(|_| err("改名远端文件", e))?;
        }
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
    fn join_keeps_chinese_names() {
        // 远端路径拼接只认 `/`，名字里的中文、空格、# 一律原样带过去
        assert_eq!(join("/home/用户", "文档 汇总"), "/home/用户/文档 汇总");
        assert_eq!(join("/srv", "报表#2026"), "/srv/报表#2026");
        assert_eq!(parent_of("/home/用户/文档 汇总"), "/home/用户");
        assert_eq!(parent_of("/用户"), "/");
    }

    #[test]
    fn parent_stops_at_root() {
        assert_eq!(parent_of("/var/log"), "/var");
        assert_eq!(parent_of("/var"), "/");
        assert_eq!(parent_of("/"), "/");
    }

    #[test]
    fn perm_string_renders_rwx() {
        // 目录 0755、文件 0644，运维最常看到的两种
        assert_eq!(perm_string(Some(0o755), true), "drwxr-xr-x");
        assert_eq!(perm_string(Some(0o644), false), "-rw-r--r--");
        // 全空 / 全开
        assert_eq!(perm_string(Some(0o000), false), "----------");
        assert_eq!(perm_string(Some(0o777), true), "drwxrwxrwx");
        // 执行位与跨组：0750 只有组可读可执行
        assert_eq!(perm_string(Some(0o750), false), "-rwxr-x---");
        // 服务器没给权限位时不留空列
        assert_eq!(perm_string(None, false), "—");
        assert_eq!(perm_string(None, true), "—");
    }
}
