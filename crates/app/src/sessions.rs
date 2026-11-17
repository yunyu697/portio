//! 会话注册表与 SSH 相关命令。
//!
//! 这里是 `app` 层唯一的"业务编排"位置：取配置路径、写 known_hosts、把协议层的事件
//! 翻译成前端事件。协议细节一律在 `portio-ssh` 里，不在这里重复。

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use portio_ssh::{
    options, AuthMethod, HostKeyVerdict, KnownHosts, PtySize, RemoteEntry, ShellCommand, ShellEvent,
    Sftp, SshSession,
};
use serde::Serialize;
use tauri::ipc::Channel;
use tauri::{AppHandle, Emitter, Manager, State};
use tokio::sync::mpsc::{unbounded_channel, UnboundedSender};
use tokio::sync::Mutex as AsyncMutex;

struct Entry {
    session: Option<SshSession>,
    tx: UnboundedSender<ShellCommand>,
    /// 同一个连接上的 SFTP 通道，第一次用到文件功能时才建立。
    sftp: Arc<AsyncMutex<Option<Sftp>>>,
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

    let (session, fingerprint) = SshSession::connect(&opts, expected, Duration::from_secs(12))
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

    // SFTP 在连接时一并建好：后续文件操作就不必再碰 session（它会随终端任务被 move 走）
    let sftp = session.open_sftp().await.map_err(|e| e.to_string())?;

    reg.entries.lock().map_err(|_| "内部锁出错")?.insert(
        id,
        Entry {
            session: Some(session),
            tx: cmd_tx,
            sftp: Arc::new(AsyncMutex::new(Some(sftp))),
        },
    );

    let app_for_task = app.clone();
    tokio::spawn(async move {
        while let Some(ev) = ev_rx.recv().await {
            let (kind, text) = match ev {
                ShellEvent::Output(bytes) => {
                    ("output", String::from_utf8_lossy(&bytes).to_string())
                }
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

// ---------- 文件双栏 ----------

/// 给前端的一行文件数据。远端与本地共用一套字段，界面才能复用同一种行模板。
#[derive(Serialize, Clone)]
pub struct FileItem {
    name: String,
    path: String,
    size: u64,
    modified: i64,
    is_dir: bool,
}

impl FileItem {
    fn from_remote(e: RemoteEntry) -> Self {
        Self {
            name: e.name,
            path: e.path,
            size: e.size,
            modified: e.modified,
            is_dir: e.is_dir,
        }
    }
}

#[derive(Serialize, Clone)]
struct TransferPayload {
    id: u32,
    name: String,
    done: u64,
    total: u64,
    dir: String,
}

fn sftp_of(reg: &Registry, id: u32) -> Result<Arc<AsyncMutex<Option<Sftp>>>, String> {
    let map = reg.entries.lock().map_err(|_| "内部锁出错")?;
    let entry = map.get(&id).ok_or("会话不存在")?;
    Ok(entry.sftp.clone())
}

/// 远端落地目录：登录后的 home，界面用它做初始路径。
#[tauri::command]
pub async fn sftp_home(reg: State<'_, Registry>, id: u32) -> Result<String, String> {
    let handle = sftp_of(&reg, id)?;
    let guard = handle.lock().await;
    let sftp = guard.as_ref().ok_or("SFTP 未就绪")?;
    sftp.home().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn sftp_list(
    reg: State<'_, Registry>,
    id: u32,
    path: String,
) -> Result<Vec<FileItem>, String> {
    let handle = sftp_of(&reg, id)?;
    let guard = handle.lock().await;
    let sftp = guard.as_ref().ok_or("SFTP 未就绪")?;
    let items = sftp.list(&path).await.map_err(|e| e.to_string())?;
    Ok(items.into_iter().map(FileItem::from_remote).collect())
}

/// 本地目录列举。路径为空时给用户主目录，避免一进来是空白。
#[tauri::command]
pub fn local_list(path: Option<String>) -> Result<(String, Vec<FileItem>), String> {
    let dir = match path {
        Some(p) if !p.trim().is_empty() => PathBuf::from(p),
        _ => dirs_home(),
    };
    let mut items = Vec::new();
    let rd = std::fs::read_dir(&dir).map_err(|e| format!("读本地目录失败：{e}"))?;
    for entry in rd.flatten() {
        let meta = match entry.metadata() {
            Ok(m) => m,
            Err(_) => continue,
        };
        let name = entry.file_name().to_string_lossy().to_string();
        let is_dir = meta.is_dir();
        let modified = meta
            .modified()
            .ok()
            .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0);
        items.push(FileItem {
            path: entry.path().to_string_lossy().to_string(),
            name,
            size: if is_dir { 0 } else { meta.len() },
            modified,
            is_dir,
        });
    }
    items.sort_by(|a, b| {
        b.is_dir
            .cmp(&a.is_dir)
            .then_with(|| a.name.to_lowercase().cmp(&b.name.to_lowercase()))
    });
    Ok((dir.to_string_lossy().to_string(), items))
}

fn dirs_home() -> PathBuf {
    std::env::var("USERPROFILE")
        .or_else(|_| std::env::var("HOME"))
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."))
}

#[tauri::command]
pub async fn sftp_download(
    app: AppHandle,
    reg: State<'_, Registry>,
    id: u32,
    remote: String,
    local: String,
) -> Result<u64, String> {
    let handle = sftp_of(&reg, id)?;
    let guard = handle.lock().await;
    let sftp = guard.as_ref().ok_or("SFTP 未就绪")?;
    let name = remote.rsplit('/').next().unwrap_or("file").to_string();

    let mut last_emit = 0u64;
    let mut cb = |done: u64, total: u64| {
        if done - last_emit >= 64 * 1024 || done == total {
            last_emit = done;
            let _ = app.emit(
                "transfer",
                TransferPayload {
                    id,
                    name: name.clone(),
                    done,
                    total,
                    dir: "down".into(),
                },
            );
        }
    };
    sftp.download(&remote, &PathBuf::from(&local), &mut cb)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn sftp_upload(
    app: AppHandle,
    reg: State<'_, Registry>,
    id: u32,
    local: String,
    remote: String,
) -> Result<u64, String> {
    let handle = sftp_of(&reg, id)?;
    let guard = handle.lock().await;
    let sftp = guard.as_ref().ok_or("SFTP 未就绪")?;
    let name = local.rsplit(['\\', '/']).next().unwrap_or("file").to_string();

    let mut last_emit = 0u64;
    let mut cb = |done: u64, total: u64| {
        if done - last_emit >= 64 * 1024 || done == total {
            last_emit = done;
            let _ = app.emit(
                "transfer",
                TransferPayload {
                    id,
                    name: name.clone(),
                    done,
                    total,
                    dir: "up".into(),
                },
            );
        }
    };
    sftp.upload(&PathBuf::from(&local), &remote, &mut cb)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn sftp_mkdir(reg: State<'_, Registry>, id: u32, path: String) -> Result<(), String> {
    let handle = sftp_of(&reg, id)?;
    let guard = handle.lock().await;
    let sftp = guard.as_ref().ok_or("SFTP 未就绪")?;
    sftp.mkdir(&path).await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn sftp_remove(
    reg: State<'_, Registry>,
    id: u32,
    path: String,
    is_dir: bool,
) -> Result<(), String> {
    let handle = sftp_of(&reg, id)?;
    let guard = handle.lock().await;
    let sftp = guard.as_ref().ok_or("SFTP 未就绪")?;
    sftp.remove(&path, is_dir).await.map_err(|e| e.to_string())
}
