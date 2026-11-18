use tauri::{Manager, Window};
use tauri::utils::config::Color;

mod session_store;
mod sessions;

/// 上次退出时用户看的是什么主题。前端每次换主题都会写一份，这里启动时读它决定窗口底色。
/// 读不到就按深色（也是产品默认）。
fn read_ui_theme(app: &tauri::AppHandle) -> String {
    let path = app
        .path()
        .app_data_dir()
        .map(|d| d.join("theme.txt"))
        .map_err(|e| e.to_string());
    match path.ok().and_then(|p| std::fs::read_to_string(p).ok()) {
        Some(t) if t.trim() == "light" => "light".into(),
        _ => "dark".into(),
    }
}

/// 窗口底色跟着主题走：深色 #0D1014、浅色 #F4F7F9。
fn theme_bg(theme: &str) -> Color {
    if theme == "light" {
        Color(244, 247, 249, 255)
    } else {
        Color(13, 16, 20, 255)
    }
}

/// 前端每次切换主题都会调一次，落盘给下次启动用。
#[tauri::command]
fn ui_theme_set(app: tauri::AppHandle, theme: String) -> Result<(), String> {
    let dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&dir).map_err(|e| format!("建目录失败：{e}"))?;
    let theme = if theme == "light" { "light" } else { "dark" };
    std::fs::write(dir.join("theme.txt"), theme).map_err(|e| format!("写主题文件失败：{e}"))
}

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

/// 前端画完第一帧后调一次，把窗口显示出来。
///
/// 窗口在配置里是 `visible: false`：先藏着建，等 webview 真正画出界面再 show。
/// 这样启动时不会先闪一块空白的窗口底色（深色底 + 用户其实是浅色主题时尤其明显）。
#[tauri::command]
fn window_ready(window: Window) -> Result<(), String> {
    window.show().map_err(map_err)?;
    window.set_focus().map_err(map_err)?;
    Ok(())
}

pub fn run() {
    tauri::Builder::default()
        .manage(sessions::Registry::default())
        .invoke_handler(tauri::generate_handler![
            window_control,
            window_state,
            window_ready,
            ui_theme_set,
            session_store::sessions_read,
            session_store::sessions_write,
            session_store::sessions_path,
            session_store::sessions_import_ssh_config,
            session_store::sessions_import_xshell,
            session_store::sessions_import_winscp,
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
            // 窗口不再由 tauri.conf.json 静态建：底色要按用户上次的主题来定，
            // 否则浅色主题的用户每次启动都会先看到一块深色空窗口（就是"黑屏一下"）。
            let theme = read_ui_theme(app.handle());
            let win = tauri::WebviewWindowBuilder::new(app, "main", tauri::WebviewUrl::App("index.html".into()))
                .title("Portio")
                .inner_size(1180.0, 690.0)
                .min_inner_size(1024.0, 620.0)
                .decorations(false)
                .theme(Some(tauri::Theme::Dark))
                .background_color(theme_bg(&theme))
                .visible(false)
                .center()
                .build()?;
            // 调试时想开 devtools 就设 PORTIO_DEVTOOLS=1，默认不自动弹，免得挡住窗口截图与演示
            if cfg!(debug_assertions) && std::env::var("PORTIO_DEVTOOLS").is_ok() {
                win.open_devtools();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Portio 启动失败");
}

