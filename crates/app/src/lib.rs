use tauri::{Manager, Window};

mod session_store;
mod sessions;

fn map_err(err: tauri::Error) -> String {
    err.to_string()
}

/// 自绘标题栏的窗口按钮都走这一个入口，避免前端各调各的 API 导致状态不同步。
/// 返回值是操作后的窗口状态，前端据此把"最大化/还原"的字形换掉。
#[tauri::command]
fn window_control(window: Window, action: &str) -> Result<String, String> {
    match action {
        "minimize" => window.minimize().map_err(map_err)?,
        "maximize" => {
            if window.is_maximized().map_err(map_err)? {
                window.unmaximize().map_err(map_err)?
            } else {
                window.maximize().map_err(map_err)?
            }
        }
        "close" => window.close().map_err(map_err)?,
        "fullscreen" => {
            let now = window.is_fullscreen().map_err(map_err)?;
            window.set_fullscreen(!now).map_err(map_err)?
        }
        other => return Err(format!("未知的窗口动作：{other}")),
    }
    let st = if window.is_fullscreen().map_err(map_err)? {
        "fullscreen"
    } else if window.is_maximized().map_err(map_err)? {
        "maximized"
    } else {
        "normal"
    };
    Ok(st.to_string())
}

/// 窗口刚起来时前端问一次，用来把按钮字形摆到正确状态。
#[tauri::command]
fn window_state(window: Window) -> Result<String, String> {
    let st = if window.is_fullscreen().map_err(map_err)? {
        "fullscreen"
    } else if window.is_maximized().map_err(map_err)? {
        "maximized"
    } else {
        "normal"
    };
    Ok(st.to_string())
}

pub fn run() {
    tauri::Builder::default()
        .manage(sessions::Registry::default())
        .invoke_handler(tauri::generate_handler![
            window_control,
            window_state,
            session_store::sessions_read,
            session_store::sessions_write,
            session_store::sessions_path,
            sessions::ssh_connect,
            sessions::ssh_input,
            sessions::ssh_resize,
            sessions::ssh_disconnect,
            sessions::sftp_home,
            sessions::sftp_list,
            sessions::local_list,
            sessions::sftp_download,
            sessions::sftp_upload,
            sessions::sftp_mkdir,
            sessions::sftp_remove,
            sessions::sftp_rename,
            sessions::local_rename
        ])
        .setup(|app| {
            if let Some(win) = app.get_webview_window("main") {
                // 调试时想开 devtools 就设 PORTIO_DEVTOOLS=1，默认不自动弹，免得挡住窗口截图与演示
                if cfg!(debug_assertions) && std::env::var("PORTIO_DEVTOOLS").is_ok() {
                    win.open_devtools();
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Portio 启动失败");
}

