//! 协议层。
//!
//! 现在只有抽象与错误类型——S2 的 1.3 才接 `russh`。
//! 先把接口钉住，是为了让 `app` 层可以照着它写 UI，不被实现细节绑住。

use portio_core::HostId;

/// 连接参数。认证方式在 S2 才落地，这里先留位。
#[derive(Debug, Clone)]
pub struct ConnectOptions {
    pub host: HostId,
    pub user: String,
    pub auth: AuthMethod,
}

#[derive(Debug, Clone)]
pub enum AuthMethod {
    /// 读取本地私钥文件。口令式与 agent 式在 S2 补齐。
    PrivateKeyFile { path: String },
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
}

/// 一个已建立的连接能做的事。实现留到 S2。
pub trait Connection {
    fn open_shell(&mut self) -> Result<(), SshError>;
    fn resize(&mut self, cols: u32, rows: u32) -> Result<(), SshError>;
}
