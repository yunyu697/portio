//! 会话清单的落盘：位置在应用数据目录，文件是普通 JSON，用户随时可以拷走。
//!
//! 规则都归 `portio-core::SessionStore`，这里只负责"读进来 / 原子写回去"。

use std::fs;
use std::path::PathBuf;

use portio_core::SessionStore;
use tauri::Manager;

const FILE_NAME: &str = "sessions.json";

fn store_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("拿不到应用数据目录：{e}"))?;
    Ok(dir.join(FILE_NAME))
}

/// 前端启动时读一次，拿到的就是整份清单的 JSON 文本。
/// 文件不存在等同"还没有会话"，不算错误。
#[tauri::command]
pub fn sessions_read(app: tauri::AppHandle) -> Result<String, String> {
    let path = store_path(&app)?;
    match fs::read_to_string(&path) {
        Ok(text) => Ok(text),
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => Ok(String::new()),
        Err(err) => Err(format!("读会话清单失败：{err}")),
    }
}

/// 整份覆盖写。先写临时文件再改名，半途断电也不会留下半个 JSON。
#[tauri::command]
pub fn sessions_write(app: tauri::AppHandle, json: String) -> Result<String, String> {
    // 写之前先过一遍解析：宁可拒绝，也不把坏数据落盘
    let store = SessionStore::from_json(&json).map_err(|e| e.to_string())?;
    let path = store_path(&app)?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("建目录失败：{e}"))?;
    }
    let tmp = path.with_extension("json.tmp");
    let text = store.to_json();
    fs::write(&tmp, text.as_bytes()).map_err(|e| format!("写临时文件失败：{e}"))?;
    fs::rename(&tmp, &path).map_err(|e| format!("替换清单文件失败：{e}"))?;
    Ok(path.to_string_lossy().to_string())
}

/// 清单文件到底在哪，前端拿去显示给用户，方便自己备份。
#[tauri::command]
pub fn sessions_path(app: tauri::AppHandle) -> Result<String, String> {
    Ok(store_path(&app)?.to_string_lossy().to_string())
}
