//! russh 之上的薄封装：连接、认证、开 PTY、双向数据。
//!
//! 设计原则：这一层只做协议，不碰 UI、不碰配置存储路径——存储由调用方传进来，
//! 这样 `portio-ssh` 可以独立被 CLI 或测试驱动。

use std::sync::{Arc, Mutex};
use std::time::Duration;

use russh::client::{self, Handle};
use russh::keys::ssh_key::{HashAlg, PublicKey};
use russh::keys::{load_secret_key, PrivateKeyWithHashAlg};
use russh::{ChannelMsg, Disconnect};
use tokio::sync::mpsc::{UnboundedReceiver, UnboundedSender};

use portio_core::HostId;

use crate::{AuthMethod, ConnectOptions, SshError};

/// 终端尺寸。远端 vim / tmux 依赖这个值决定重排。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PtySize {
    pub cols: u32,
    pub rows: u32,
}

impl Default for PtySize {
    fn default() -> Self {
        Self { cols: 80, rows: 24 }
    }
}

/// 界面 → 协议层的指令。
#[derive(Debug, Clone)]
pub enum ShellCommand {
    Data(Vec<u8>),
    Resize { cols: u32, rows: u32 },
    Close,
}

/// 协议层 → 界面的事件。
#[derive(Debug, Clone)]
pub enum ShellEvent {
    Output(Vec<u8>),
    Exit(u32),
    Closed,
    Error(String),
}

struct Handler {
    /// 之前记录过的指纹。None 表示首次连接，走 TOFU。
    expected: Option<String>,
    /// 握手过程中看到的指纹，无论成功失败都记下来，好让上层落盘或报"密钥变了"。
    seen: Arc<Mutex<Option<String>>>,
}

impl client::Handler for Handler {
    type Error = russh::Error;

    async fn check_server_key(&mut self, key: &PublicKey) -> Result<bool, Self::Error> {
        let fp = key.fingerprint(HashAlg::Sha256).to_string();
        *self.seen.lock().expect("seen 锁中毒") = Some(fp.clone());
        Ok(match &self.expected {
            Some(expected) => expected == &fp,
            None => true,
        })
    }
}

pub struct SshSession {
    handle: Handle<Handler>,
}

fn fp_now(seen: &Arc<Mutex<Option<String>>>) -> String {
    seen.lock()
        .expect("seen 锁中毒")
        .clone()
        .unwrap_or_else(|| "未知".into())
}

impl SshSession {
    /// 建连 + 认证。返回会话和本次握手看到的主机指纹，指纹由调用方决定怎么存。
    pub async fn connect(
        opts: &ConnectOptions,
        expected_fingerprint: Option<String>,
        timeout: Duration,
    ) -> Result<(Self, String), SshError> {
        let seen = Arc::new(Mutex::new(None));
        let handler = Handler {
            expected: expected_fingerprint.clone(),
            seen: seen.clone(),
        };
        let config = Arc::new(client::Config {
            inactivity_timeout: Some(Duration::from_secs(30)),
            ..<_>::default()
        });

        let addr = (opts.host.host.clone(), opts.host.port);
        let connected = tokio::time::timeout(
            timeout,
            client::connect(config, addr, handler),
        )
        .await
        .map_err(|_| {
            SshError::ConnectTimeout(format!("{}:{}", opts.host.host, opts.host.port))
        })?;

        let mut session = match connected {
            Ok(h) => h,
            Err(err) => {
                // 主机密钥被拒时，russh 只会给一个笼统的错误，这里翻译成人话
                if let Some(expected) = &expected_fingerprint {
                    let actual = fp_now(&seen);
                    if &actual != expected {
                        return Err(SshError::HostKeyMismatch(format!(
                            "记录的是 {expected}，服务器给的是 {actual}"
                        )));
                    }
                }
                return Err(SshError::Protocol(err.to_string()));
            }
        };

        let fingerprint = fp_now(&seen);

        match &opts.auth {
            AuthMethod::Password { password } => {
                let res = session
                    .authenticate_password(&opts.user, password.as_str())
                    .await
                    .map_err(|e| SshError::AuthFailed(e.to_string()))?;
                if !res.success() {
                    return Err(SshError::AuthFailed("密码被拒绝".into()));
                }
            }
            AuthMethod::PrivateKeyFile { path } => {
                let key = load_secret_key(path, None)
                    .map_err(|e| SshError::AuthFailed(format!("读取私钥失败：{e}")))?;
                let hash = session
                    .best_supported_rsa_hash()
                    .await
                    .map_err(|e| SshError::AuthFailed(e.to_string()))?
                    .flatten();
                let res = session
                    .authenticate_publickey(
                        &opts.user,
                        PrivateKeyWithHashAlg::new(Arc::new(key), hash),
                    )
                    .await
                    .map_err(|e| SshError::AuthFailed(e.to_string()))?;
                if !res.success() {
                    return Err(SshError::AuthFailed("私钥被拒绝".into()));
                }
            }
        }

        Ok((Self { handle: session }, fingerprint))
    }

    /// 开一个 PTY 会话，之后由后台任务负责双向搬运。
    pub async fn open_shell(
        &self,
        pty: PtySize,
        out: UnboundedSender<ShellEvent>,
        mut input: UnboundedReceiver<ShellCommand>,
    ) -> Result<(), SshError> {
        let channel = self
            .handle
            .channel_open_session()
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;

        channel
            .request_pty(
                true,
                "xterm-256color",
                pty.cols,
                pty.rows,
                0,
                0,
                &[],
            )
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;
        channel
            .request_shell(true)
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;

        let (mut read_half, write_half) = channel.split();

        tokio::spawn(async move {
            loop {
                tokio::select! {
                    cmd = input.recv() => {
                        let Some(cmd) = cmd else { break };
                        let res = match cmd {
                            ShellCommand::Data(bytes) => write_half.data(&bytes[..]).await,
                            ShellCommand::Resize { cols, rows } => {
                                write_half.window_change(cols, rows, 0, 0).await
                            }
                            ShellCommand::Close => {
                                let _ = write_half.eof().await;
                                let _ = write_half.close().await;
                                break;
                            }
                        };
                        if let Err(err) = res {
                            let _ = out.send(ShellEvent::Error(err.to_string()));
                            break;
                        }
                    }
                    msg = read_half.wait() => {
                        let Some(msg) = msg else { break };
                        match msg {
                            ChannelMsg::Data { data } => {
                                let _ = out.send(ShellEvent::Output(data.to_vec()));
                            }
                            ChannelMsg::ExtendedData { data, .. } => {
                                let _ = out.send(ShellEvent::Output(data.to_vec()));
                            }
                            ChannelMsg::ExitStatus { exit_status } => {
                                let _ = out.send(ShellEvent::Exit(exit_status));
                            }
                            ChannelMsg::Eof | ChannelMsg::Close => {
                                let _ = out.send(ShellEvent::Closed);
                                break;
                            }
                            _ => {}
                        }
                    }
                    else => break,
                }
            }
        });

        Ok(())
    }

    pub async fn disconnect(self) -> Result<(), SshError> {
        self.handle
            .disconnect(Disconnect::ByApplication, "", "")
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))
    }
}

/// 给上层用的便捷构造。
pub fn options(host: impl Into<String>, port: Option<u16>, user: impl Into<String>, auth: AuthMethod) -> ConnectOptions {
    let mut h = HostId::new(host);
    if let Some(p) = port {
        h.port = p;
    }
    ConnectOptions {
        host: h,
        user: user.into(),
        auth,
    }
}
