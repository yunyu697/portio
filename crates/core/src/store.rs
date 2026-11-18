//! 会话清单：把"怎么连"记下来，换标签、重启、换机器都能复用。
//!
//! 红线：这里只管数据规则（去重、排序、上限、校验），不管文件落在哪儿、也不管 UI 怎么画。
//! 真正的读写交给外壳层，JSON 的解析规则也只有一套——前端和后端不会各写一份。

use crate::CoreError;
use serde::{Deserialize, Serialize};

/// 会话清单最多记这么多条，再多就把最久没用的挤出去。
pub const MAX_RECORDS: usize = 40;

fn default_port() -> u16 {
    22
}

fn default_auth() -> String {
    "password".to_string()
}

/// 一条"怎么连"的记录。**刻意没有 password 字段**：密码不进清单，也不落盘。
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SessionRecord {
    pub host: String,
    #[serde(default = "default_port")]
    pub port: u16,
    pub user: String,
    #[serde(default = "default_auth")]
    pub auth: String,
    #[serde(default)]
    pub keyfile: Option<String>,
    #[serde(default)]
    pub name: Option<String>,
    /// 最近一次用它的时间戳（毫秒），越大越靠前。
    #[serde(default)]
    pub last_used: u64,
}

impl SessionRecord {
    /// 清单里的去重键：同一台机器同一个账号只有一条。
    pub fn key(&self) -> String {
        format!("{}@{}:{}", self.user, self.host, self.port)
    }

    fn validate(&self) -> Result<(), CoreError> {
        let host = self.host.trim();
        let user = self.user.trim();
        if host.is_empty() || user.is_empty() {
            return Err(CoreError::BadSession("主机和用户名都不能为空".into()));
        }
        if self.port == 0 {
            return Err(CoreError::BadSession("端口不能是 0".into()));
        }
        match self.auth.as_str() {
            "password" => {}
            "key" => {
                let keyfile = self.keyfile.as_deref().unwrap_or("").trim();
                if keyfile.is_empty() {
                    return Err(CoreError::BadSession("密钥认证必须给出私钥路径".into()));
                }
            }
            other => {
                return Err(CoreError::BadSession(format!("不认识的认证方式：{other}")));
            }
        }
        Ok(())
    }
}

/// 整份清单。带 `records` 一层壳是为了以后加版本号/分组字段时旧文件还能读进来。
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct SessionStore {
    /// 文件格式版本。现在只有 1；读到更新的版本就拒绝，不猜。
    #[serde(default = "format_version")]
    pub version: u32,
    #[serde(default)]
    pub records: Vec<SessionRecord>,
}

fn format_version() -> u32 {
    1
}

impl SessionStore {
    pub fn new() -> Self {
        Self {
            version: 1,
            records: Vec::new(),
        }
    }

    /// 新增或覆盖一条：命中同键就替换并提到最前，否则插到最前；超过上限截断尾部。
    pub fn upsert(&mut self, mut rec: SessionRecord) -> Result<(), CoreError> {
        rec.host = rec.host.trim().to_string();
        rec.user = rec.user.trim().to_string();
        if rec.port == 0 {
            rec.port = 22;
        }
        rec.validate()?;
        let key = rec.key();
        self.records.retain(|r| r.key() != key);
        self.records.insert(0, rec);
        self.records.truncate(MAX_RECORDS);
        Ok(())
    }

    /// 删除一条，返回是否真删掉了。
    pub fn remove(&mut self, key: &str) -> bool {
        let before = self.records.len();
        self.records.retain(|r| r.key() != key);
        self.records.len() != before
    }

    pub fn find(&self, key: &str) -> Option<&SessionRecord> {
        self.records.iter().find(|r| r.key() == key)
    }

    /// 导入：逐条校验合并，坏记录跳过并计数。返回（成功条数，跳过条数）。
    pub fn merge(&mut self, other: SessionStore) -> (usize, usize) {
        let mut added = 0usize;
        let mut skipped = 0usize;
        // 倒序插入，保证导入文件里的第一条最后插、因而排在最前
        for rec in other.records.into_iter().rev() {
            if rec.validate().is_ok() {
                let _ = self.upsert(rec);
                added += 1;
            } else {
                skipped += 1;
            }
        }
        (added, skipped)
    }

    pub fn to_json(&self) -> String {
        // 手写序列化也不该失败；真失败了给一份空清单，不让调用方炸
        serde_json::to_string_pretty(self)
            .unwrap_or_else(|_| "{\"version\":1,\"records\":[]}".into())
    }

    /// 解析清单文件。能容错的地方容错：纯数组（手写的简易文件）也认。
    pub fn from_json(text: &str) -> Result<Self, CoreError> {
        let text = text.trim();
        if text.is_empty() {
            return Ok(Self::new());
        }
        if let Ok(store) = serde_json::from_str::<SessionStore>(text) {
            if store.version > 1 {
                return Err(CoreError::BadSession(format!(
                    "清单版本 {} 比当前程序支持的还新，先升级 Portio",
                    store.version
                )));
            }
            return Ok(store);
        }
        // 兼容"只给一个数组"的写法
        let records: Vec<SessionRecord> = serde_json::from_str(text)
            .map_err(|e| CoreError::BadSession(format!("不是合法的会话清单：{e}")))?;
        Ok(Self {
            version: 1,
            records,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rec(host: &str, user: &str, port: u16) -> SessionRecord {
        SessionRecord {
            host: host.into(),
            port,
            user: user.into(),
            auth: "password".into(),
            keyfile: None,
            name: None,
            last_used: 0,
        }
    }

    #[test]
    fn upsert_puts_newest_first_and_dedupes() {
        let mut s = SessionStore::new();
        s.upsert(rec("a.example", "root", 22)).unwrap();
        s.upsert(rec("b.example", "root", 22)).unwrap();
        s.upsert(rec("a.example", "root", 22)).unwrap();
        assert_eq!(s.records.len(), 2, "同键应该只留一条");
        assert_eq!(s.records[0].host, "a.example", "最近用过的排最前");
        assert_eq!(s.records[1].host, "b.example");
    }

    #[test]
    fn port_takes_part_in_key() {
        let mut s = SessionStore::new();
        s.upsert(rec("x", "root", 22)).unwrap();
        s.upsert(rec("x", "root", 2222)).unwrap();
        assert_eq!(s.records.len(), 2, "同机器不同端口算两条");
    }

    #[test]
    fn cap_keeps_newest_and_drops_oldest() {
        let mut s = SessionStore::new();
        for i in 0..(MAX_RECORDS + 5) {
            s.upsert(rec(&format!("h{i}"), "root", 22)).unwrap();
        }
        assert_eq!(s.records.len(), MAX_RECORDS);
        assert_eq!(s.records[0].host, format!("h{}", MAX_RECORDS + 4));
        assert!(
            !s.records.iter().any(|r| r.host == "h0"),
            "最老的应该被挤掉"
        );
    }

    #[test]
    fn validate_rejects_empty_fields_and_bad_auth() {
        let mut s = SessionStore::new();
        let mut empty_host = rec("  ", "root", 22);
        assert!(s.upsert(empty_host.clone()).is_err());
        empty_host.host = "ok".into();
        empty_host.user = " ".into();
        assert!(s.upsert(empty_host).is_err());

        let mut key_without_path = rec("ok", "root", 22);
        key_without_path.auth = "key".into();
        assert!(s.upsert(key_without_path).is_err());

        let mut key_with_path = rec("ok", "root", 22);
        key_with_path.auth = "key".into();
        key_with_path.keyfile = Some("/home/u/.ssh/id_ed25519".into());
        assert!(s.upsert(key_with_path).is_ok());

        let mut weird = rec("ok", "root", 22);
        weird.auth = "agent".into();
        assert!(s.upsert(weird).is_err());
        assert_eq!(s.records.len(), 1, "只有合法的那条进来了");
    }

    #[test]
    fn json_round_trip() {
        let mut s = SessionStore::new();
        s.upsert(rec("a", "root", 2222)).unwrap();
        s.upsert(rec("b", "deploy", 22)).unwrap();
        let text = s.to_json();
        let back = SessionStore::from_json(&text).unwrap();
        assert_eq!(back, s);
    }

    #[test]
    fn json_accepts_bare_array_and_empty_text() {
        let text = r#"[{"host":"a","user":"root","port":2222}]"#;
        let s = SessionStore::from_json(text).unwrap();
        assert_eq!(s.records.len(), 1);
        assert_eq!(s.records[0].port, 2222);

        let empty = SessionStore::from_json("   ").unwrap();
        assert!(empty.records.is_empty());
    }

    #[test]
    fn json_rejects_garbage_and_future_version() {
        assert!(SessionStore::from_json("{ not json").is_err());
        let future = r#"{"version":9,"records":[]}"#;
        assert!(SessionStore::from_json(future).is_err());
    }

    #[test]
    fn merge_counts_added_and_skipped() {
        let mut s = SessionStore::new();
        s.upsert(rec("a", "root", 22)).unwrap();
        let mut incoming = SessionStore::new();
        incoming.records = vec![
            rec("b", "root", 22),
            rec("c", "deploy", 22),
            SessionRecord {
                host: "".into(),
                ..rec("d", "root", 22)
            },
        ];
        let (added, skipped) = s.merge(incoming);
        assert_eq!((added, skipped), (2, 1));
        assert_eq!(s.records.len(), 3);
        assert!(s.find("deploy@c:22").is_some());
    }

    #[test]
    fn remove_only_removes_matching_key() {
        let mut s = SessionStore::new();
        s.upsert(rec("a", "root", 22)).unwrap();
        assert!(s.remove("root@a:22"));
        assert!(!s.remove("root@a:22"), "删过了再删应该报 false");
        assert!(s.records.is_empty());
    }
}
