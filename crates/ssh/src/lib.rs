//! 协议层：SSH / SFTP。
//!
//! 分层：`client` 只负责 russh 的连接与通道，`known_hosts` 负责首次信任校验，
//! 存储路径与 UI 都在 `app` 层，这一层可以被独立测试或给 CLI 复用。

pub mod client;
pub mod known_hosts;
pub mod sftp;

use portio_core::HostId;

pub use client::{options, PtySize, ShellCommand, ShellEvent, SshSession};
pub use known_hosts::{HostKeyVerdict, KnownHosts};
pub use sftp::{join, parent_of, RemoteEntry, Sftp};

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
    #[error("主机密钥校验失败：{0}")]
    HostKeyMismatch(String),
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
