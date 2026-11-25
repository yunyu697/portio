//! 外链跳转：只允许 https 链接，交给系统默认浏览器打开。
//!
//! 轻量更新通道不做原位下载安装：检查到新版只把用户带到 Release 页面，
//! 下载与安装由用户手动完成。这里只负责安全地打开一个外部链接。

/// 校验链接：必须是 https、带主机名；拒绝 `file://`、`javascript:`、空主机。
fn validate_url(url: &str) -> Result<(), String> {
    let lower = url.trim().to_ascii_lowercase();
    let rest = lower
        .strip_prefix("https://")
        .ok_or_else(|| "只允许打开 https 链接".to_string())?;
    let host = rest.split('/').next().unwrap_or("");
    if host.is_empty() || host.contains(' ') {
        return Err("链接缺少主机名".to_string());
    }
    Ok(())
}

#[cfg(target_os = "windows")]
fn open_command(url: &str) -> std::process::Command {
    let mut cmd = std::process::Command::new("cmd");
    // `start` 的第一个带引号参数会被当成窗口标题，所以先塞一个空标题占位。
    cmd.args(["/C", "start", "", url]);
    cmd
}

#[cfg(target_os = "macos")]
fn open_command(url: &str) -> std::process::Command {
    let mut cmd = std::process::Command::new("open");
    cmd.arg(url);
    cmd
}

#[cfg(all(unix, not(target_os = "macos")))]
fn open_command(url: &str) -> std::process::Command {
    let mut cmd = std::process::Command::new("xdg-open");
    cmd.arg(url);
    cmd
}

/// 在系统默认浏览器里打开一个外部 https 链接。
#[tauri::command]
pub fn open_external(url: String) -> Result<(), String> {
    validate_url(&url)?;
    open_command(&url)
        .spawn()
        .map_err(|e| format!("打开浏览器失败：{e}"))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_https_with_host_allowed() {
        assert!(validate_url("https://github.com/yunyu697/portio/releases").is_ok());
        assert!(validate_url("https://github.com").is_ok());
        assert!(validate_url("http://github.com/x").is_err());
        assert!(validate_url("file:///C:/x").is_err());
        assert!(validate_url("javascript:alert(1)").is_err());
        assert!(validate_url("https://").is_err());
        assert!(validate_url("").is_err());
    }
}
