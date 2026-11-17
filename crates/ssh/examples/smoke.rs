//! 冒烟检查：连一个真实 SSH 服务器，只做握手与主机密钥校验，不认证。
//!
//! 用法：cargo run -p portio-ssh --example smoke -- <host> [port]
//! 用途：验 russh 的 TCP + 密钥交换 + 指纹计算这条链路真的通，且不依赖密码。

use std::time::Duration;

use portio_ssh::{options, AuthMethod, SshSession};

#[tokio::main]
async fn main() {
    let mut args = std::env::args().skip(1);
    let host = args.next().unwrap_or_else(|| "github.com".into());
    let port: u16 = args.next().and_then(|p| p.parse().ok()).unwrap_or(22);

    // 故意给一个空密码：握手会成功，认证会被拒——我们要的就只是握手那一半。
    let opts = options(
        host.clone(),
        Some(port),
        "portio-smoke",
        AuthMethod::Password {
            password: String::new(),
        },
    );

    match SshSession::connect(&opts, None, Duration::from_secs(10)).await {
        Ok((_s, fp)) => println!("握手成功，主机指纹 {fp}（认证意外通过了？）"),
        Err(err) => {
            let text = err.to_string();
            if text.contains("认证失败") || text.contains("AuthFailed") {
                println!("握手成功，认证如预期被拒：{text}");
            } else {
                println!("握手失败：{text}");
                std::process::exit(1);
            }
        }
    }
}
