use tauri::Manager;

/// 目前只做一件事：起窗口。
/// 之后每个 IPC 命令都从这里登记，注意不要在这里写业务规则——那是 `core` 的活。
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            if let Some(win) = app.get_webview_window("main") {
                #[cfg(debug_assertions)]
                win.open_devtools();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Portio 启动失败");
}
