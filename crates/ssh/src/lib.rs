//! 协议层：SSH / SFTP。
//!
//! 分层：`client` 只负责 russh 的连接与通道，`known_hosts` 负责首次信任校验，
//! 存储路径与 UI 都在 `app` 层，这一层可以被独立测试或给 CLI 复用。

pub mod client;
pub mod known_hosts;
pub mod resume;
pub mod sftp;

use portio_core::HostId;

pub use client::{options, PtySize, ShellCommand, ShellEvent, SshSession};
pub use known_hosts::{HostKeyVerdict, KnownHostRecord, KnownHosts};
pub use resume::{part_path, resume_offset};
pub use sftp::{join, parent_of, perm_string, RemoteEntry, Sftp};

/// 连接参数。
#[derive(Debug, Clone)]
pub struct ConnectOptions {
    pub host: HostId,
    pub user: String,
    pub auth: AuthMethod,
}

#[derive(Debug, Clone)]
pub enum AuthMethod {
    /// 读取本地私钥文件。口令式解锁与 ssh-agent 在 S2 之后补。
    PrivateKeyFile {
        path: String,
    },
    Password {
        password: String,
    },
}

impl AuthMethod {
    /// 日志里只写类型，绝不把口令打出来。
    pub fn label(&self) -> &'static str {
        match self {
            AuthMethod::PrivateKeyFile { .. } => "private-key",
            AuthMethod::Password { .. } => "password",
        }
    }
}

#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum SshError {
    #[error("连接超时：{0}")]
    ConnectTimeout(String),
    /// 指纹与记录不一致。两个指纹都留着：界面要把"记录的是哪个、这次是哪个"摆出来，
    /// 才谈得上让人决定要不要重新信任。
    #[error("主机密钥校验失败：记录的是 {expected}，服务器给的是 {actual}")]
    HostKeyMismatch { expected: String, actual: String },
    #[error("认证失败：{0}")]
    AuthFailed(String),
    #[error("通道已断开")]
    ChannelClosed,
    #[error("协议错误：{0}")]
    Protocol(String),
}

/// 一个已建立的连接能做的事。S2 起由 `SshSession` 实现具体能力。
pub trait Connection {
    fn open_shell(&mut self) -> Result<(), SshError>;
    fn resize(&mut self, cols: u32, rows: u32) -> Result<(), SshError>;
}

impl SshError {
    /// 主机密钥与记录不一致时，给上层一个能分辨的标记：`HOSTKEY_CHANGED|记录|本次`。
    ///
    /// 界面靠这个前缀把"密钥变了"和其它连接失败分开：前者要人拍板（去设置里确认或删记录），
    /// 后者只需要看错误文本。做成方法而不是让 app 层去拆错误字符串，改文案时就不会把契约拆坏。
    pub fn hostkey_changed_tag(&self) -> Option<String> {
        match self {
            SshError::HostKeyMismatch { expected, actual } => {
                Some(format!("HOSTKEY_CHANGED|{expected}|{actual}"))
            }
            _ => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hostkey_mismatch_becomes_a_tag_the_ui_can_parse() {
        let err = SshError::HostKeyMismatch {
            expected: "SHA256:OLD".into(),
            actual: "SHA256:NEW".into(),
        };
        assert_eq!(
            err.hostkey_changed_tag().as_deref(),
            Some("HOSTKEY_CHANGED|SHA256:OLD|SHA256:NEW")
        );
        // 三段、竖线分隔——前端 split("|") 取前两段，格式不能变
        assert_eq!(err.hostkey_changed_tag().unwrap().split("|").count(), 3);
    }

    #[test]
    fn other_errors_are_not_tagged() {
        for err in [
            SshError::ConnectTimeout("h:22".into()),
            SshError::AuthFailed("userauth failed".into()),
            SshError::ChannelClosed,
            SshError::Protocol("boom".into()),
        ] {
            assert_eq!(err.hostkey_changed_tag(), None, "{err:?} 不该当成密钥变更");
        }
    }
}
