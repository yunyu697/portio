//! WinSCP 配置（`WinSCP.ini`）里的会话解析。
//!
//! WinSCP 默认把站点存在注册表，但"便携模式 / 导出配置"会写成一份 INI，
//! 站点放在 `[Sessions\<名字>]` 段里。这里只取 SSH 系列站点，密码同样不碰
//! （WinSCP 会存加密后的密码串，读了也没用）。

use crate::sshconfig::ImportOutcome;
use crate::store::SessionRecord;

/// 解析整份 `WinSCP.ini`，一个 `[Sessions\...]` 段对应一台主机。
pub fn parse_winscp_ini(text: &str) -> ImportOutcome {
    let mut out = ImportOutcome::default();

    let mut in_sessions = false;
    let mut name: Option<String> = None;
    let mut host = String::new();
    let mut user = String::new();
    let mut port: Option<u16> = None;
    let mut keyfile: Option<String> = None;
    let mut protocol_ok = true;

    let flush = |out: &mut ImportOutcome,
                     in_sessions: &bool,
                     name: &Option<String>,
                     host: &mut String,
                     user: &mut String,
                     port: &mut Option<u16>,
                     keyfile: &mut Option<String>,
                     protocol_ok: &bool| {
        if *in_sessions && *protocol_ok && !host.trim().is_empty() && !user.trim().is_empty() {
            let (auth, key) = match keyfile.take() {
                Some(k) => ("key".to_string(), Some(k)),
                None => ("password".to_string(), None),
            };
            out.records.push(SessionRecord {
                host: std::mem::take(host),
                port: port.take().unwrap_or(22),
                user: std::mem::take(user),
                auth,
                keyfile: key,
                name: name.clone(),
                last_used: 0,
            });
        } else if *in_sessions {
            out.skipped += 1;
        }
        *host = String::new();
        *user = String::new();
        *port = None;
        *keyfile = None;
    };

    for raw in text.lines() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with(';') || line.starts_with('#') {
            continue;
        }
        if line.starts_with('[') && line.ends_with(']') {
            flush(
                &mut out,
                &in_sessions,
                &name,
                &mut host,
                &mut user,
                &mut port,
                &mut keyfile,
                &protocol_ok,
            );
            let inner = &line[1..line.len() - 1];
            let lower = inner.to_ascii_lowercase();
            in_sessions = lower.starts_with("sessions\\") || lower.starts_with("sessions/");
            name = if in_sessions {
                let rest = inner.get("sessions".len() + 1..).unwrap_or("");
                // 允许 `[Sessions\分组\主机]`，整段去掉反斜杠后当备注名
                let n = rest.replace('\\', " / ");
                let n = n.trim_matches(|c: char| c.is_whitespace() || c == '/').to_string();
                Some(n).filter(|s| !s.is_empty())
            } else {
                None
            };
            protocol_ok = true;
            continue;
        }
        if !in_sessions {
            continue;
        }
        let Some((k, v)) = line.split_once('=') else {
            continue;
        };
        let key = k.trim().to_ascii_lowercase();
        let val = unquote(v.trim());
        if val.is_empty() {
            continue;
        }
        match key.as_str() {
            "hostname" => host = val,
            "username" => user = val,
            "portnumber" => port = val.parse::<u16>().ok(),
            // 0=SCP、1=SFTP(旧)、2=SFTP；3 以上是 FTP / WebDAV / S3，不是 SSH
            "fsprotocol" => protocol_ok = matches!(val.as_str(), "0" | "1" | "2"),
            "publickeyfile" | "keyfilepath" => keyfile = Some(val),
            _ => {}
        }
    }
    flush(
        &mut out,
        &in_sessions,
        &name,
        &mut host,
        &mut user,
        &mut port,
        &mut keyfile,
        &protocol_ok,
    );
    out
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

    #[test]
    fn two_sessions_one_ssh_one_ftp() {
        let ini = "\
[Configuration]
HostName=default.example

[Sessions\\web-01]
HostName=10.2.2.2
UserName=deploy
PortNumber=2222
FSProtocol=2

[Sessions\\ftp-legacy]
HostName=ftp.example.com
UserName=anonymous
FSProtocol=3
";
        let out = parse_winscp_ini(ini);
        assert_eq!(out.records.len(), 1, "FTP 站点不算");
        assert_eq!(out.skipped, 1);
        let rec = &out.records[0];
        assert_eq!(rec.host, "10.2.2.2");
        assert_eq!(rec.user, "deploy");
        assert_eq!(rec.port, 2222);
        assert_eq!(rec.name.as_deref(), Some("web-01"));
        assert_eq!(rec.auth, "password");
    }

    #[test]
    fn public_key_file_means_key_auth() {
        let ini = "[Sessions\\k]\nHostName=h\nUserName=u\nPublicKeyFile=\"C:\\k\\id_rsa.ppk\"\n";
        let out = parse_winscp_ini(ini);
        assert_eq!(out.records[0].auth, "key");
        assert_eq!(out.records[0].keyfile.as_deref(), Some("C:\\k\\id_rsa.ppk"));
    }

    #[test]
    fn grouped_session_keeps_group_in_name() {
        let ini = "[Sessions\\生产\\db-01]\nHostName=10.3.3.3\nUserName=dba\n";
        let out = parse_winscp_ini(ini);
        assert_eq!(out.records[0].name.as_deref(), Some("生产 / db-01"));
    }

    #[test]
    fn missing_user_is_skipped() {
        let ini = "[Sessions\\x]\nHostName=h\n";
        let out = parse_winscp_ini(ini);
        assert!(out.records.is_empty());
        assert_eq!(out.skipped, 1);
    }

    #[test]
    fn no_sessions_section_yields_nothing() {
        let out = parse_winscp_ini("[Configuration]\nHostName=a\nUserName=b\n");
        assert!(out.records.is_empty());
        assert_eq!(out.skipped, 0, "非会话段不计入跳过");
    }
}
