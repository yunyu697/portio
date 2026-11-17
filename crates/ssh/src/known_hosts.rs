//! known_hosts：首次连接信任（TOFU）+ 变更告警。
//!
//! 文件格式与 OpenSSH 的 known_hosts 不通用（那套要处理哈希化主机名与多算法），
//! 我们自己用一行一条 `host:port SHA256:xxxx`，够小、够看得懂。将来要兼容
//! `~/.ssh/known_hosts` 时在这里加一个导入器即可，不影响调用方。

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use crate::SshError;

/// 校验结果。UI 依据它决定：直接连、静默加入、还是弹"主机密钥变了"。
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum HostKeyVerdict {
    /// 首次见到这个主机，指纹已记录。
    FirstSeen,
    /// 指纹与记录一致。
    Match,
    /// 同一个主机指纹变了——中间人攻击或服务器重装，都必须让用户确认。
    Changed { previous: String },
}

#[derive(Debug)]
pub struct KnownHosts {
    path: PathBuf,
    entries: BTreeMap<String, String>,
}

fn key_of(host: &str, port: u16) -> String {
    format!("{host}:{port}")
}

impl KnownHosts {
    pub fn load(path: impl Into<PathBuf>) -> Self {
        let path = path.into();
        let mut entries = BTreeMap::new();
        if let Ok(text) = fs::read_to_string(&path) {
            for line in text.lines() {
                let line = line.trim();
                if line.is_empty() || line.starts_with('#') {
                    continue;
                }
                if let Some((k, v)) = line.split_once(char::is_whitespace) {
                    entries.insert(k.trim().to_string(), v.trim().to_string());
                }
            }
        }
        Self { path, entries }
    }

    /// 已记录的指纹，供建连前查一遍。
    pub fn fingerprint_of(&self, host: &str, port: u16) -> Option<String> {
        self.entries.get(&key_of(host, port)).cloned()
    }

    /// 校验并（首次时）写入。写盘失败不该阻断连接，所以这里只返回 Err 于校验本身。
    pub fn verify(
        &mut self,
        host: &str,
        port: u16,
        fingerprint: &str,
    ) -> Result<HostKeyVerdict, SshError> {
        let key = key_of(host, port);
        match self.entries.get(&key) {
            Some(old) if old == fingerprint => Ok(HostKeyVerdict::Match),
            Some(old) => Ok(HostKeyVerdict::Changed {
                previous: old.clone(),
            }),
            None => {
                self.entries.insert(key, fingerprint.to_string());
                self.persist();
                Ok(HostKeyVerdict::FirstSeen)
            }
        }
    }

    /// 用户明确接受变更后，用新指纹覆盖旧记录。
    pub fn trust(&mut self, host: &str, port: u16, fingerprint: &str) {
        self.entries
            .insert(key_of(host, port), fingerprint.to_string());
        self.persist();
    }

    fn persist(&self) {
        if let Some(dir) = self.path.parent() {
            let _ = fs::create_dir_all(dir);
        }
        let text: String = self
            .entries
            .iter()
            .map(|(k, v)| format!("{k} {v}\n"))
            .collect();
        let _ = fs::write(&self.path, text);
    }

    pub fn path(&self) -> &Path {
        &self.path
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp_path(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!("portio-kh-{name}-{}", std::process::id()))
    }

    #[test]
    fn first_seen_then_match() {
        let p = tmp_path("first");
        let _ = fs::remove_file(&p);
        let mut kh = KnownHosts::load(&p);
        assert_eq!(
            kh.verify("10.0.0.1", 22, "SHA256:AAA").unwrap(),
            HostKeyVerdict::FirstSeen
        );
        assert_eq!(
            kh.verify("10.0.0.1", 22, "SHA256:AAA").unwrap(),
            HostKeyVerdict::Match
        );
        let _ = fs::remove_file(&p);
    }

    #[test]
    fn changed_key_is_reported_not_swallowed() {
        let p = tmp_path("changed");
        let _ = fs::remove_file(&p);
        let mut kh = KnownHosts::load(&p);
        kh.verify("example.com", 2222, "SHA256:OLD").unwrap();
        match kh.verify("example.com", 2222, "SHA256:NEW").unwrap() {
            HostKeyVerdict::Changed { previous } => assert_eq!(previous, "SHA256:OLD"),
            other => panic!("应为 Changed，实际 {other:?}"),
        }
        let _ = fs::remove_file(&p);
    }

    #[test]
    fn different_port_is_a_different_host() {
        let p = tmp_path("port");
        let _ = fs::remove_file(&p);
        let mut kh = KnownHosts::load(&p);
        kh.verify("h", 22, "SHA256:A").unwrap();
        assert_eq!(
            kh.verify("h", 2222, "SHA256:B").unwrap(),
            HostKeyVerdict::FirstSeen
        );
        let _ = fs::remove_file(&p);
    }

    #[test]
    fn trust_overwrites_previous() {
        let p = tmp_path("trust");
        let _ = fs::remove_file(&p);
        let mut kh = KnownHosts::load(&p);
        kh.verify("h", 22, "SHA256:OLD").unwrap();
        kh.trust("h", 22, "SHA256:NEW");
        assert_eq!(
            kh.verify("h", 22, "SHA256:NEW").unwrap(),
            HostKeyVerdict::Match
        );
        let _ = fs::remove_file(&p);
    }

    #[test]
    fn persists_across_reload() {
        let p = tmp_path("reload");
        let _ = fs::remove_file(&p);
        {
            let mut kh = KnownHosts::load(&p);
            kh.verify("h", 22, "SHA256:X").unwrap();
        }
        let mut kh2 = KnownHosts::load(&p);
        assert_eq!(
            kh2.verify("h", 22, "SHA256:X").unwrap(),
            HostKeyVerdict::Match
        );
        let _ = fs::remove_file(&p);
    }
}
