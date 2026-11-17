use portio_core::{HostId, SessionKind};

#[test]
fn target_omits_default_port() {
    let host = HostId::new("prod-web-01");
    assert_eq!(host.to_target("deploy"), "deploy@prod-web-01");
}

#[test]
fn target_keeps_custom_port() {
    let host = HostId {
        host: "10.20.8.11".into(),
        port: 2222,
    };
    assert_eq!(host.to_target("root"), "root@10.20.8.11:2222");
}

#[test]
fn session_kind_is_copy() {
    let kind = SessionKind::ShellAndFiles;
    let copied = kind;
    assert_eq!(kind, copied);
}
