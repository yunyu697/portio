//! 口令的加密落盘：把 `portio-core` 的加密层接到应用数据目录。
//!
//! 两个文件：
//! - `vault.key`：本机主密钥，首次用到时生成，之后只读。
//! - `credentials.json`：`{ "version": 1, "entries": { "user@host:port": hex(密文) } }`。
//!
//! 会话清单（`sessions.json`）里**不存口令**，这里存的是独立一份，用户随时能删。
//! 主密钥与密文同目录：防的是明文被同步盘 / 打包 / 日志带走，不是本地提权。

use std::path::PathBuf;
use std::sync::Mutex;

use portio_core::{load_or_create_master_secret, CredentialStore};
use tauri::Manager;

const CRED_FILE: &str = "credentials.json";
const KEY_FILE: &str = "vault.key";

/// 懒加载：第一次真正读写口令时才生成主密钥，没用到凭据的人不会多出一个密钥文件。
#[derive(Default)]
pub struct Credentials(Mutex<Option<CredentialStore>>);

fn data_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    app.path()
        .app_data_dir()
        .map_err(|e| format!("拿不到应用数据目录：{e}"))
}

fn with_store<T>(
    app: &tauri::AppHandle,
    creds: &tauri::State<'_, Credentials>,
    f: impl FnOnce(&mut CredentialStore) -> Result<T, String>,
) -> Result<T, String> {
    let mut guard = creds.0.lock().map_err(|_| "凭据存储的锁坏了".to_string())?;
    if guard.is_none() {
        let dir = data_dir(app)?;
        std::fs::create_dir_all(&dir).map_err(|e| format!("建目录失败：{e}"))?;
        let secret =
            load_or_create_master_secret(&dir.join(KEY_FILE)).map_err(|e| e.to_string())?;
        let store =
            CredentialStore::load(dir.join(CRED_FILE), &secret).map_err(|e| e.to_string())?;
        *guard = Some(store);
    }
    f(guard.as_mut().expect("刚填过"))
}

/// 取一条口令。没存过返回空，不算错误。
#[tauri::command]
pub fn cred_get(
    app: tauri::AppHandle,
    creds: tauri::State<'_, Credentials>,
    key: String,
) -> Result<Option<String>, String> {
    with_store(&app, &creds, |store| {
        store.password(&key).map_err(|e| e.to_string())
    })
}

/// 存一条口令。空字符串等于"删除"。
#[tauri::command]
pub fn cred_set(
    app: tauri::AppHandle,
    creds: tauri::State<'_, Credentials>,
    key: String,
    password: String,
) -> Result<(), String> {
    with_store(&app, &creds, |store| {
        store
            .set_password(&key, &password)
            .map_err(|e| e.to_string())
    })
}

/// 忘掉一条口令（前端"清除已保存口令"用）。
#[tauri::command]
pub fn cred_forget(
    app: tauri::AppHandle,
    creds: tauri::State<'_, Credentials>,
    key: String,
) -> Result<(), String> {
    with_store(&app, &creds, |store| {
        store.forget(&key).map_err(|e| e.to_string())
    })
}

/// 凭据文件在哪，给用户看（方便自己备份或彻底删除）。
#[tauri::command]
pub fn cred_path(app: tauri::AppHandle) -> Result<String, String> {
    Ok(data_dir(&app)?
        .join(CRED_FILE)
        .to_string_lossy()
        .to_string())
}
