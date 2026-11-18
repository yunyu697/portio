//! 领域模型层。
//!
//! 红线：这里不认识 Tauri、不认识 Windows，只放数据与规则。
//! 任何"该怎么连"的实现都归 `portio-ssh`，任何"怎么显示"都归 `portio-app`。

mod session;
mod sshconfig;
mod store;
mod tabs;
mod xshell;

pub use session::{GroupId, HostId, Session, SessionGroup, SessionId, SessionKind};
pub use sshconfig::{parse_ssh_config, ImportOutcome};
pub use store::{SessionRecord, SessionStore, MAX_RECORDS};
pub use xshell::parse_xshell_session;
pub use tabs::{DEFAULT_MAX_TABS, Tab, TabId, TabSet};

/// 核心层的错误。刻意不用 `anyhow`：调用方要能分辨错误种类。
#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum CoreError {
    #[error("名称不能为空")]
    EmptyName,
    #[error("同名会话已存在：{0}")]
    DuplicateName(String),
    #[error("找不到会话：{0}")]
    NotFound(SessionId),
    #[error("标签数已达上限（{0}），先关掉一个再开")]
    TooManyTabs(usize),
    #[error("{0}")]
    BadSession(String),
}
