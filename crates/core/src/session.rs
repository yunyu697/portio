use serde::{Deserialize, Serialize};

/// 会话标识。字符串而非自增整数，便于导入外部会话时保留来源 id。
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct SessionId(pub String);

impl std::fmt::Display for SessionId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct GroupId(pub String);

impl std::fmt::Display for GroupId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

/// 主机地址。IP 与域名都走这一个类型，端口默认 22。
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HostId {
    pub host: String,
    pub port: u16,
}

impl HostId {
    pub fn new(host: impl Into<String>) -> Self {
        Self {
            host: host.into(),
            port: 22,
        }
    }

    /// `user@host:port`，端口是 22 时省略。
    pub fn to_target(&self, user: &str) -> String {
        if self.port == 22 {
            format!("{}@{}", user, self.host)
        } else {
            format!("{}@{}:{}", user, self.host, self.port)
        }
    }
}

/// 一个会话的类型：只要终端，还是同时要文件面板。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SessionKind {
    Shell,
    ShellAndFiles,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Session {
    pub id: SessionId,
    pub name: String,
    pub host: HostId,
    pub user: String,
    pub group: Option<GroupId>,
    pub kind: SessionKind,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SessionGroup {
    pub id: GroupId,
    pub name: String,
    pub expanded: bool,
}
