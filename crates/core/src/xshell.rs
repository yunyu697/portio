//! Xshell 会话文件（`.xsh`）解析。
//!
//! `.xsh` 本质是一份 INI：一个文件 = 一台主机。这里只取"怎么连"需要的那几项，
//! 密码字段（Xshell 自己加密过，格式不公开）一律不碰，绝不落盘。

use crate::store::SessionRecord;

/// 从一份 `.xsh` 文本里取出一条会话记录。取不出必需项（主机 / 用户名）时返回 `None`。
///
/// * `fallback_name`：文件名去掉后缀，`[SESSION]` 里没写 `Name` 时拿它当备注名。
pub fn parse_xshell_session(text: &str, fallback_name: Option<&str>) -> Option<SessionRecord> {
    let mut host = String::new();
    let mut user = String::new();
    let mut port: Option<u16> = None;
    let mut name: Option<String> = None;
    let mut keyfile: Option<String> = None;
    let mut protocol_ok = true;
    let mut section = String::new();

    for raw in text.lines() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with(';') || line.starts_with('#') {
            continue;
        }
        if line.starts_with('[') && line.ends_with(']') {
            section = line[1..line.len() - 1].to_ascii_uppercase();
            continue;
        }
        let Some((k, v)) = line.split_once('=') else {
            continue;
        };
        let key = k.trim().to_ascii_uppercase();
        let val = unquote(v.trim());
        if val.is_empty() {
            continue;
        }
        match (section.as_str(), key.as_str()) {
            ("CONNECTION", "HOST") => host = val,
            ("CONNECTION", "PORT") => port = val.parse::<u16>().ok(),
            // 只认 SSH；Xshell 的 RDP / Serial 会话导进来没有意义
            ("CONNECTION", "PROTOCOL") => protocol_ok = val.eq_ignore_ascii_case("S"),
            ("CONNECTION:AUTHENTICATION", "USERNAME") => user = val,
            ("CONNECTION:AUTHENTICATION", "USERKEY") => keyfile = Some(val),
            ("SESSION", "NAME") => name = Some(val),
            _ => {}
        }
    }

    if !protocol_ok || host.trim().is_empty() || user.trim().is_empty() {
        return None;
    }
    let name = name.or_else(|| fallback_name.map(|n| n.trim().to_string()).filter(|n| !n.is_empty()));
    let (auth, keyfile) = match keyfile {
        Some(k) => ("key".to_string(), Some(k)),
        None => ("password".to_string(), None),
    };
    Some(SessionRecord {
        host,
        port: port.unwrap_or(22),
        user,
        auth,
        keyfile,
        name,
        last_used: 0,
    })
}

fn unquote(v: &str) -> String {
    let v = v.trim();
    if v.len() >= 2 && v.starts_with('"') && v.ends_with('"') {
        v[1..v.len() - 1].trim().to_string()
    } else {
        v.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const BASIC: &str = "[CONNECTION]\nProtocol=S\nHost=10.1.2.3\nPort=2222\n\n[CONNECTION:AUTHENTICATION]\nUserName=deploy\n\n[SESSION]\nName=生产机\n";

    #[test]
    fn maps_basic_fields() {
        let rec = parse_xshell_session(BASIC, None).expect("应当解析成功");
        assert_eq!(rec.host, "10.1.2.3");
        assert_eq!(rec.user, "deploy");
        assert_eq!(rec.port, 2222);
        assert_eq!(rec.name.as_deref(), Some("生产机"));
        assert_eq!(rec.auth, "password");
        assert!(rec.keyfile.is_none());
    }

    #[test]
    fn falls_back_to_file_name() {
        let rec = parse_xshell_session(BASIC, Some("web-01")).expect("应当解析成功");
        // [SESSION] 里有 Name 时以它为准
        assert_eq!(rec.name.as_deref(), Some("生产机"));
        let no_name = "[CONNECTION]\nHost=box\n[CONNECTION:AUTHENTICATION]\nUserName=a\n";
        let rec2 = parse_xshell_session(no_name, Some("web-01")).unwrap();
        assert_eq!(rec2.name.as_deref(), Some("web-01"));
    }

    #[test]
    fn user_key_means_key_auth() {
        let t = "[CONNECTION]\nHost=h\n[CONNECTION:AUTHENTICATION]\nUserName=u\nUserKey=\"C:\\keys\\id_ed25519\"\n";
        let rec = parse_xshell_session(t, None).unwrap();
        assert_eq!(rec.auth, "key");
        assert_eq!(rec.keyfile.as_deref(), Some("C:\\keys\\id_ed25519"));
    }

    #[test]
    fn skips_non_ssh_and_incomplete() {
        let rdp = "[CONNECTION]\nProtocol=RDP\nHost=h\n[CONNECTION:AUTHENTICATION]\nUserName=u\n";
        assert!(parse_xshell_session(rdp, None).is_none());
        let no_user = "[CONNECTION]\nProtocol=S\nHost=h\n";
        assert!(parse_xshell_session(no_user, None).is_none());
        let no_host = "[CONNECTION]\nProtocol=S\n[CONNECTION:AUTHENTICATION]\nUserName=u\n";
        assert!(parse_xshell_session(no_host, None).is_none());
    }

    #[test]
    fn comments_blank_and_case_insensitive_keys() {
        let t = "; 注释\n[connection]\nhOSt = h1 ; 不会被当成注释处理，整行是值\n\n[CONNECTION:AUTHENTICATION]\nusername=u\n";
        let rec = parse_xshell_session(t, None).unwrap();
        assert_eq!(rec.host, "h1 ; 不会被当成注释处理，整行是值");
        assert_eq!(rec.user, "u");
        assert_eq!(rec.port, 22);
    }
}
