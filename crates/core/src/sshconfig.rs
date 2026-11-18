//! OpenSSH 客户端配置（`~/.ssh/config`）→ 会话记录。
//!
//! 运维机器上早就有这份配置，让人一条条手抄进 GUI 是最没道理的活。
//! 这里只做"读文本 → 出记录"的纯函数：不碰文件系统、不认识 Tauri，
//! 路径展开由调用方给 home 目录，没给就原样保留（`~` 留给外壳层去展开）。
//!
//! 刻意不做的事：不解析 `ProxyJump` / `LocalForward`（这些是连接参数，不是"怎么连到哪"），
//! 不展开通配符 `Host *` / `Host web-*`（它们不是一台具体的机器），遇到一律跳过并计数。

use crate::store::SessionRecord;
use std::collections::HashSet;

/// 一次导入的结果：能用的记录 + 明确跳过的块数。
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ImportOutcome {
    pub records: Vec<SessionRecord>,
    /// 因为通配符、缺用户名、重复等原因跳过的 Host 块数。
    pub skipped: usize,
}

/// 解析配置文本。
///
/// * `default_user`：块里没写 `User` 时用的兜底账号（`None` 表示这种块跳过）。
/// * `home`：用于把 `IdentityFile ~/.ssh/id_ed25519` 展开成绝对路径（`None` 时保留 `~`）。
pub fn parse_ssh_config(
    text: &str,
    default_user: Option<&str>,
    home: Option<&str>,
) -> ImportOutcome {
    let mut out = ImportOutcome::default();
    let mut seen: HashSet<String> = HashSet::new();

    // 当前块。出现 Host 行就收口上一块。
    let mut cur: Option<Block> = None;

    for raw in text.lines() {
        let line = match strip_comment(raw) {
            Some(l) => l,
            None => continue,
        };
        let (key, value) = match split_kv(&line) {
            Some(kv) => kv,
            None => continue,
        };
        match key.as_str() {
            "host" => {
                if let Some(block) = cur.take() {
                    if let Some(rec) = finish(block, default_user, home, &mut seen) {
                        out.records.push(rec);
                    } else {
                        out.skipped += 1;
                    }
                }
                cur = Some(Block::new(&value));
            }
            // Match 块（`Match host *.example`）整块不属于任何一台机器，遇到就收掉当前块并停收。
            "match" => {
                if let Some(block) = cur.take() {
                    if let Some(rec) = finish(block, default_user, home, &mut seen) {
                        out.records.push(rec);
                    } else {
                        out.skipped += 1;
                    }
                }
            }
            _ => {
                if let Some(block) = cur.as_mut() {
                    block.set(&key, &value);
                }
            }
        }
    }
    if let Some(block) = cur.take() {
        if let Some(rec) = finish(block, default_user, home, &mut seen) {
            out.records.push(rec);
        } else {
            out.skipped += 1;
        }
    }
    out
}

struct Block {
    /// `Host` 行里的别名，可能多个（`Host a b`）。
    aliases: Vec<String>,
    hostname: Option<String>,
    user: Option<String>,
    port: Option<u16>,
    identity: Option<String>,
}

impl Block {
    fn new(alias_text: &str) -> Self {
        Self {
            aliases: alias_text
                .split_whitespace()
                .map(|s| s.to_string())
                .collect(),
            hostname: None,
            user: None,
            port: None,
            identity: None,
        }
    }

    fn set(&mut self, key: &str, value: &str) {
        match key {
            "hostname" => self.hostname = Some(value.to_string()),
            "user" => self.user = Some(value.to_string()),
            "port" => self.port = value.parse::<u16>().ok().filter(|p| *p > 0),
            "identityfile" => self.identity = Some(value.to_string()),
            _ => {}
        }
    }
}

/// 把一块收成一条记录；通配符、缺用户名、重复的一律返回 `None`。
fn finish(
    block: Block,
    default_user: Option<&str>,
    home: Option<&str>,
    seen: &mut HashSet<String>,
) -> Option<SessionRecord> {
    // 通配符块不是一台具体的机器
    let has_wildcard = |s: &str| s.contains('*') || s.contains('?') || s.starts_with('!');
    if block.aliases.is_empty() || block.aliases.iter().any(|a| has_wildcard(a)) {
        return None;
    }
    let alias = block.aliases[0].clone();
    let host = block.hostname.unwrap_or_else(|| alias.clone());
    if host.trim().is_empty() || has_wildcard(&host) {
        return None;
    }
    let user = match block.user.or_else(|| default_user.map(|s| s.to_string())) {
        Some(u) if !u.trim().is_empty() => u,
        _ => return None,
    };
    let keyfile = block.identity.map(|p| expand_home(&p, home));
    let auth = if keyfile.is_some() { "key" } else { "password" }.to_string();

    let rec = SessionRecord {
        host,
        port: block.port.unwrap_or(22),
        user,
        auth,
        keyfile,
        // 别名就是人给这台机器起的名字，直接拿来当备注
        name: Some(alias),
        last_used: 0,
    };
    if !seen.insert(rec.key()) {
        return None;
    }
    Some(rec)
}

/// `~` / `~/x` 展开；认不出前缀就原样返回，不做猜测。
fn expand_home(path: &str, home: Option<&str>) -> String {
    let p = path.trim();
    let Some(home) = home else {
        return p.to_string();
    };
    if p == "~" {
        return home.to_string();
    }
    if let Some(rest) = p.strip_prefix("~/") {
        return format!("{home}/{rest}");
    }
    p.to_string()
}

/// 去掉行内注释。`#` 在引号里不算注释——`IdentityFile "~/my # key"` 这种写法要留着。
fn strip_comment(line: &str) -> Option<String> {
    let mut out = String::with_capacity(line.len());
    let mut in_quote = false;
    for ch in line.chars() {
        match ch {
            '"' => {
                in_quote = !in_quote;
                out.push(ch);
            }
            '#' if !in_quote => break,
            _ => out.push(ch),
        }
    }
    let trimmed = out.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_string())
    }
}

/// 拆 `Key value` / `Key=value`；键转小写（OpenSSH 的键不区分大小写）。
fn split_kv(line: &str) -> Option<(String, String)> {
    let line = line.trim();
    if let Some(eq) = line.find('=') {
        let k = line[..eq].trim();
        let v = line[eq + 1..].trim().trim_matches('"');
        if k.is_empty() {
            return None;
        }
        return Some((k.to_lowercase(), v.to_string()));
    }
    let mut it = line.splitn(2, char::is_whitespace);
    let k = it.next()?.trim();
    let v = it.next().unwrap_or("").trim().trim_matches('"');
    if k.is_empty() {
        return None;
    }
    Some((k.to_lowercase(), v.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    const HOME: &str = "/home/deploy";

    #[test]
    fn basic_block_maps_fields() {
        let cfg = "\
Host web-01
    HostName 10.0.0.11
    User deploy
    Port 2222
    IdentityFile ~/.ssh/id_ed25519
";
        let out = parse_ssh_config(cfg, None, Some(HOME));
        assert_eq!(out.records.len(), 1);
        let r = &out.records[0];
        assert_eq!(r.host, "10.0.0.11");
        assert_eq!(r.user, "deploy");
        assert_eq!(r.port, 2222);
        assert_eq!(r.auth, "key");
        assert_eq!(r.keyfile.as_deref(), Some("/home/deploy/.ssh/id_ed25519"));
        assert_eq!(r.name.as_deref(), Some("web-01"), "别名当备注");
    }

    #[test]
    fn defaults_when_fields_missing() {
        let cfg = "\
Host db
    HostName db.example.com
";
        // 没写 User：给了兜底账号就用它，端口回到 22
        let out = parse_ssh_config(cfg, Some("ops"), Some(HOME));
        assert_eq!(out.records[0].user, "ops");
        assert_eq!(out.records[0].port, 22);
        assert_eq!(out.records[0].auth, "password");
        assert_eq!(out.records[0].host, "db.example.com");
    }

    #[test]
    fn host_without_hostname_uses_alias() {
        let cfg = "Host jump\n  User root\n";
        let out = parse_ssh_config(cfg, None, Some(HOME));
        assert_eq!(out.records[0].host, "jump");
        assert_eq!(out.records[0].name.as_deref(), Some("jump"));
    }

    #[test]
    fn wildcard_and_match_blocks_are_skipped() {
        let cfg = "\
Host *
    User nobody
    Port 2200

Host web-*
    User nobody

Match host *.example
    User nobody

Host real
    HostName 10.0.0.9
    User deploy
";
        let out = parse_ssh_config(cfg, None, Some(HOME));
        assert_eq!(out.records.len(), 1, "只有 real 这一块是具体机器");
        assert_eq!(out.records[0].host, "10.0.0.9");
        // `Host *` 与 `Host web-*` 各算一块跳过；`Match` 不是 Host 块，本身不计数
        assert_eq!(out.skipped, 2);
    }

    #[test]
    fn equals_form_and_comments_and_quotes() {
        let cfg = "\
# 我的测试机
Host=lab   # 行内注释
    HostName=lab.example
    User = deploy
    Port=2022
    IdentityFile \"~/keys/lab key\"
";
        let out = parse_ssh_config(cfg, None, Some(HOME));
        let r = &out.records[0];
        assert_eq!(r.host, "lab.example");
        assert_eq!(r.port, 2022);
        assert_eq!(r.keyfile.as_deref(), Some("/home/deploy/keys/lab key"));
        assert_eq!(r.name.as_deref(), Some("lab"));
    }

    #[test]
    fn duplicate_endpoints_collapse() {
        let cfg = "\
Host a
    HostName 10.0.0.7
    User deploy

Host b
    HostName 10.0.0.7
    User deploy
";
        let out = parse_ssh_config(cfg, None, Some(HOME));
        assert_eq!(out.records.len(), 1, "同一台同一账号只留一条");
        assert_eq!(out.skipped, 1);
    }

    #[test]
    fn bad_port_falls_back_to_22() {
        let cfg = "Host x\n  HostName x.y\n  User u\n  Port not-a-number\n";
        let out = parse_ssh_config(cfg, None, None);
        assert_eq!(out.records[0].port, 22);
    }

    #[test]
    fn unknown_keys_are_ignored() {
        let cfg = "\
Host srv
    HostName srv.example
    User deploy
    ProxyJump bastion
    LocalForward 8080 localhost:80
    ServerAliveInterval 30
";
        let out = parse_ssh_config(cfg, None, Some(HOME));
        assert_eq!(out.records.len(), 1);
        assert_eq!(out.records[0].host, "srv.example");
    }

    #[test]
    fn tilde_left_alone_without_home() {
        let cfg = "Host k\n  HostName k.example\n  User u\n  IdentityFile ~/.ssh/id_rsa\n";
        let out = parse_ssh_config(cfg, None, None);
        assert_eq!(out.records[0].keyfile.as_deref(), Some("~/.ssh/id_rsa"));
    }
}
