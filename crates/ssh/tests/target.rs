use portio_core::HostId;
use portio_ssh::{AuthMethod, ConnectOptions};

#[test]
fn connect_options_carry_host_and_user() {
    let opts = ConnectOptions {
        host: HostId::new("10.20.8.11"),
        user: "deploy".into(),
        auth: AuthMethod::PrivateKeyFile {
            path: "~/.ssh/id_ed25519".into(),
        },
    };
    assert_eq!(opts.host.to_target(&opts.user), "deploy@10.20.8.11");
}
