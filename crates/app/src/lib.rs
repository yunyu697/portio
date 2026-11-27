use std::error::Error;
use tauri::utils::config::Color;
use tauri::{Manager, Window};

mod credentials;
mod diag;
mod session_store;
mod sessions;
mod updater;

/// 把一条错误的整条来源链拼成一行：顶层消息 → 根因。
///
/// WebView2 建窗失败时，顶层 `tauri::Error` 的消息常常只是笼统的一句，
/// 真正的 HRESULT（如 `0x800700AA` 占用）挂在 source 链上；只记顶层就把根因丢了。
fn error_chain(err: &impl Error) -> String {
    let mut parts = vec![err.to_string()];
    let mut src = err.source();
    while let Some(s) = src {
        parts.push(s.to_string());
        src = s.source();
    }
    parts.join(" → ")
}

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

/// 自动化跑门禁时设这个环境变量：窗口照常显示，但不许把用户的前台顶掉。
const QUIET_ENV: &str = "PORTIO_AUTOMATION";

/// 显示窗口但不激活。
///
/// 一轮门禁要拉八九次 exe，每次都把用户正在用的窗口顶下去——哪怕设了虚拟桌面也一样，
/// 新窗口总会出现在当前桌面上并拿焦点。前端调 `window_ready` 的那一刻改成：
/// 先给窗口挂 `WS_EX_NOACTIVATE`，再用 `SW_SHOWNOACTIVATE` 显示、压到 Z 序最底，
/// 全程 `SWP_NOACTIVATE`。窗口可见、WebView2 照常跑，前台仍在用户那边。
#[cfg(windows)]
fn show_quiet(window: &Window) -> Result<(), String> {
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        GetWindowLongPtrW, SetWindowLongPtrW, SetWindowPos, ShowWindow, GWL_EXSTYLE, HWND_BOTTOM,
        SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE, SW_SHOWNOACTIVATE, WS_EX_NOACTIVATE,
    };

    let hwnd = window.hwnd().map_err(map_err)?.0;
    unsafe {
        let ex = GetWindowLongPtrW(hwnd, GWL_EXSTYLE) | WS_EX_NOACTIVATE as isize;
        SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex);
        ShowWindow(hwnd, SW_SHOWNOACTIVATE);
        SetWindowPos(
            hwnd,
            HWND_BOTTOM,
            0,
            0,
            0,
            0,
            SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE,
        );
    }
    Ok(())
}

/// 前端画完第一帧后调一次，把窗口显示出来。
///
/// 窗口在配置里是 `visible: false`：先藏着建，等 webview 真正画出界面再 show。
/// 这样启动时不会先闪一块空白的窗口底色（深色底 + 用户其实是浅色主题时尤其明显）。
#[tauri::command]
fn window_ready(window: Window) -> Result<(), String> {
    if std::env::var_os(QUIET_ENV).is_some() {
        #[cfg(windows)]
        return show_quiet(&window);
        #[cfg(not(windows))]
        return window.show().map_err(map_err);
    }
    window.show().map_err(map_err)?;
    window.set_focus().map_err(map_err)?;
    Ok(())
}

pub fn run() {
    tauri::Builder::default()
        .manage(sessions::Registry::default())
        .manage(credentials::Credentials::default())
        .invoke_handler(tauri::generate_handler![
            window_control,
            window_state,
            window_ready,
            ui_theme_set,
            diag::diag_log,
            diag::diag_info,
            diag::diag_tail,
            diag::diag_reveal,
            credentials::cred_get,
            credentials::cred_set,
            credentials::cred_forget,
            credentials::cred_path,
            session_store::sessions_read,
            session_store::sessions_write,
            session_store::sessions_path,
            session_store::sessions_salvage,
            session_store::sessions_import_ssh_config,
            session_store::sessions_import_xshell,
            session_store::sessions_import_winscp,
            sessions::ssh_connect,
            sessions::hosts_list,
            sessions::hosts_forget,
            sessions::hosts_path,
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
            sessions::local_rename,
            updater::open_external
        ])
        .setup(|app| {
            // 崩溃采集先装钩子：后面任何地方 panic（含 setup 自己、tokio 任务）都能落一行日志。
            diag::install_panic_hook(app.handle().clone());
            diag::write_entry(
                app.handle(),
                "info",
                "app",
                &format!(
                    "Portio {} 启动 · {} {} · 日志 {}",
                    env!("CARGO_PKG_VERSION"),
                    std::env::consts::OS,
                    std::env::consts::ARCH,
                    diag::log_file(app.handle())
                        .map(|p| p.display().to_string())
                        .unwrap_or_else(|e| e)
                ),
            );
            // 窗口不再由 tauri.conf.json 静态建：底色要按用户上次的主题来定，
            // 否则浅色主题的用户每次启动都会先看到一块深色空窗口（就是"黑屏一下"）。
            let theme = read_ui_theme(app.handle());
            // Release 构建里下面那段 devtools 代码会被剥掉，win 就没人用了，
            // 所以显式放行这条"未使用"警告，免得 release 编译每次都刷一行。
            #[allow(unused_variables)]
            let win = match tauri::WebviewWindowBuilder::new(
                app,
                "main",
                tauri::WebviewUrl::App("index.html".into()),
            )
            .title("Portio")
            .inner_size(1180.0, 690.0)
            .min_inner_size(1024.0, 620.0)
            .decorations(false)
            .theme(Some(tauri::Theme::Dark))
            .background_color(theme_bg(&theme))
            .visible(false)
            .center()
            .build()
            {
                Ok(w) => w,
                Err(e) => {
                    // 建窗 / WebView2 失败要把整条错误链落进日志：探针早退归因是靠
                    // 日志尾巴认根因（占用 / panic）的；stderr 在探针里被丢进 DEVNULL，
                    // 这里不记，下一次早退就只剩一个退出码，看不出撞在哪。
                    diag::write_entry(
                        app.handle(),
                        "error",
                        "setup",
                        &format!("窗口 / WebView2 创建失败：{}", error_chain(&e)),
                    );
                    return Err(e.into());
                }
            };
            // 调试时想开 devtools 就设 PORTIO_DEVTOOLS=1，默认不自动弹，免得挡住窗口截图与演示。
            // 注意 open_devtools 只在 debug 构建里存在，所以用属性宏而不是 cfg! 宏：
            // cfg! 是运行期布尔，Release 编译时这行代码仍然要参与编译，会直接报 E0599。
            #[cfg(debug_assertions)]
            if std::env::var("PORTIO_DEVTOOLS").is_ok() {
                win.open_devtools();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Portio 启动失败");
}
