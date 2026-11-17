//! 会话注册表与 SSH 相关命令。
//!
//! 这里是 `app` 层唯一的"业务编排"位置：取配置路径、写 known_hosts、把协议层的事件
//! 翻译成前端事件。协议细节一律在 `portio-ssh` 里，不在这里重复。

use std::collections::HashMap;
use std::sync::Mutex;
use std::time::Duration;

use portio_ssh::{
    options, AuthMethod, HostKeyVerdict, KnownHosts, PtySize, ShellCommand, ShellEvent, SshSession,
};
use serde::Serialize;
use tauri::ipc::Channel;
use tauri::{AppHandle, Emitter, Manager, State};
use tokio::sync::mpsc::{unbounded_channel, UnboundedSender};

struct Entry {
    session: Option<SshSession>,
    tx: UnboundedSender<ShellCommand>,
}

#[derive(Default)]
pub struct Registry {
    next_id: Mutex<u32>,
    entries: Mutex<HashMap<u32, Entry>>,
}

#[derive(Serialize, Clone)]
struct ShellPayload {
    id: u32,
    kind: String,
    text: String,
}

fn known_hosts_path(app: &AppHandle) -> Result<std::path::PathBuf, String> {
    let dir = app
        .path()
        .app_config_dir()
        .map_err(|e| format!("取配置目录失败：{e}"))?;
    Ok(dir.join("known_hosts"))
}

/// 建连 + 认证 + 开 PTY。成功后返回会话 id，之后的输入/改尺寸都带这个 id。
#[tauri::command]
#[allow(clippy::too_many_arguments)]
pub async fn ssh_connect(
    app: AppHandle,
    reg: State<'_, Registry>,
    host: String,
    port: u16,
    user: String,
    password: Option<String>,
    keyfile: Option<String>,
    cols: u32,
    rows: u32,
    on_handshake: Channel<String>,
) -> Result<u32, String> {
    let auth = match (password, keyfile) {
        (Some(password), _) => AuthMethod::Password { password },
        (None, Some(keyfile)) => AuthMethod::PrivateKeyFile { path: keyfile },
        _ => return Err("缺少认证方式：要么给密码，要么给私钥路径".into()),
    };

    let opts = options(host, Some(port), user, auth);

    let kh_path = known_hosts_path(&app)?;
    let mut kh = KnownHosts::load(kh_path);
    let expected = kh.fingerprint_of(&opts.host.host, opts.host.port);

    let (session, fingerprint) =
        SshSession::connect(&opts, expected, Duration::from_secs(12))
            .await
            .map_err(|e| e.to_string())?;

    match kh
        .verify(&opts.host.host, opts.host.port, &fingerprint)
        .map_err(|e| e.to_string())?
    {
        HostKeyVerdict::Changed { previous } => {
            let _ = session.disconnect().await;
            // 用前缀让前端能区分"密钥变了"这种需要用户拍板的情况
            return Err(format!("HOSTKEY_CHANGED|{previous}|{fingerprint}"));
        }
        verdict => {
            let first = verdict == HostKeyVerdict::FirstSeen;
            let _ = on_handshake.send(format!("{fingerprint}|{first}"));
        }
    }

    let id = {
        let mut n = reg.next_id.lock().map_err(|_| "内部锁出错")?;
        *n += 1;
        *n
    };

    let (ev_tx, mut ev_rx) = unbounded_channel::<ShellEvent>();
    let (cmd_tx, cmd_rx) = unbounded_channel::<ShellCommand>();

    session
        .open_shell(PtySize { cols, rows }, ev_tx, cmd_rx)
        .await
        .map_err(|e| e.to_string())?;

    reg.entries
        .lock()
        .map_err(|_| "内部锁出错")?
        .insert(
            id,
            Entry {
                session: Some(session),
                tx: cmd_tx,
            },
        );

    let app_for_task = app.clone();
    tokio::spawn(async move {
        while let Some(ev) = ev_rx.recv().await {
            let (kind, text) = match ev {
                ShellEvent::Output(bytes) => ("output", String::from_utf8_lossy(&bytes).to_string()),
                ShellEvent::Exit(code) => ("exit", code.to_string()),
                ShellEvent::Closed => ("closed", String::new()),
                ShellEvent::Error(err) => ("error", err),
            };
            let _ = app_for_task.emit(
                "shell",
                ShellPayload {
                    id,
                    kind: kind.to_string(),
                    text,
                },
            );
        }
    });

    Ok(id)
}

#[tauri::command]
pub fn ssh_input(reg: State<'_, Registry>, id: u32, data: String) -> Result<(), String> {
    let map = reg.entries.lock().map_err(|_| "内部锁出错")?;
    let entry = map.get(&id).ok_or("会话不存在")?;
    entry
        .tx
        .send(ShellCommand::Data(data.into_bytes()))
        .map_err(|_| "会话已断开".to_string())
}

#[tauri::command]
pub fn ssh_resize(reg: State<'_, Registry>, id: u32, cols: u32, rows: u32) -> Result<(), String> {
    let map = reg.entries.lock().map_err(|_| "内部锁出错")?;
    let entry = map.get(&id).ok_or("会话不存在")?;
    entry
        .tx
        .send(ShellCommand::Resize { cols, rows })
        .map_err(|_| "会话已断开".to_string())
}

#[tauri::command]
pub async fn ssh_disconnect(reg: State<'_, Registry>, id: u32) -> Result<(), String> {
    let entry = reg
        .entries
        .lock()
        .map_err(|_| "内部锁出错")?
        .remove(&id)
        .ok_or("会话不存在")?;
    let _ = entry.tx.send(ShellCommand::Close);
    if let Some(session) = entry.session {
        let _ = session.disconnect().await;
    }
    Ok(())
}
