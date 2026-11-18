// 不管 debug 还是 release 构建都不要控制台窗口：用户看到的是一个纯桌面程序。
// Tauri 模板默认只在非 debug 构建里关控制台，而我们发的是 --debug 包，所以之前每次启动都会多弹一个黑窗。
#![windows_subsystem = "windows"]

fn main() {
    portio_app::run()
}
