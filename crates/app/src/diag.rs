//! 运行日志与崩溃采集：只写本机，不出网。
//!
//! 一条日志占一行：`2026-11-18T15:40:12Z [ERROR] [ui] 消息`。这样尾巴读取、轮转都简单，
//! 也不会因为某条异常自带换行把整个文件撑乱。满 1 MiB 轮转成 `portio.log.1`（只留一份）。

use serde::Serialize;
use std::cell::Cell;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::Manager;

const MAX_FILE_BYTES: u64 = 1 << 20; // 1 MiB
const MAX_MESSAGE_CHARS: usize = 4000;
const TAIL_LIMIT: usize = 200;

/// 写日志的串行闸：一条写完才轮到下一条，免得两条日志的字在文件里插成一团。
static WRITE_LOCK: Mutex<()> = Mutex::new(());

thread_local! {
    /// 「这个线程已经在写日志」：崩溃钩子里会写日志，写日志本身再 panic 就会递归。
    /// 这个是**按线程**算的——别的线程在写，不该把这一条丢掉。
    static INSIDE_WRITE: Cell<bool> = const { Cell::new(false) };
}

struct InsideGuard;

impl Drop for InsideGuard {
    fn drop(&mut self) {
        INSIDE_WRITE.with(|f| f.set(false));
    }
}

pub fn log_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    app.path()
        .app_log_dir()
        .map_err(|e| format!("拿不到日志目录：{e}"))
}

/// 日志文件路径：`<app_log_dir>/portio.log`
pub fn log_file(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    Ok(log_dir(app)?.join("portio.log"))
}

/// 轮转后的备份路径：`portio.log` → `portio.log.1`
pub fn backup_path(file: &Path) -> PathBuf {
    let name = file
        .file_name()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| "portio.log".to_string());
    file.with_file_name(format!("{name}.1"))
}

/// 秒级时间戳格式化成 UTC ISO8601，例如 `2026-11-18T15:40:12Z`。
/// 不引 chrono：只为打日志多带一个日期库不划算，按 Howard Hinnant 的历法换算足够。
pub fn iso8601_utc(secs: u64) -> String {
    let days = (secs / 86400) as i64;
    let rem = secs % 86400;
    let (h, mi, s) = (rem / 3600, (rem % 3600) / 60, rem % 60);
    let z = days + 719468;
    let era = (if z >= 0 { z } else { z - 146096 }) / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = if m <= 2 { y + 1 } else { y };
    format!("{year:04}-{m:02}-{d:02}T{h:02}:{mi:02}:{s:02}Z")
}

pub fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// 级别只收三档，别的一律按 ERROR 记（宁可多记，不可丢）。
pub fn normalize_level(level: &str) -> &'static str {
    match level.trim().to_ascii_lowercase().as_str() {
        "info" | "debug" => "INFO",
        "warn" | "warning" => "WARN",
        _ => "ERROR",
    }
}

/// 来源只留 `a-z0-9._-`，最长 16 字符，避免前端塞控制字符进日志。
pub fn normalize_source(source: &str) -> String {
    let cleaned: String = source
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'))
        .collect::<String>()
        .to_ascii_lowercase();
    if cleaned.is_empty() {
        "app".to_string()
    } else {
        cleaned.chars().take(16).collect()
    }
}

/// 一条日志必须落在同一行：换行折成 `⏎`，并按字符（不是字节）截到 4000。
pub fn clean_message(raw: &str) -> String {
    let flat = raw
        .replace("\r\n", " \u{23CE} ")
        .replace(['\r', '\n'], " \u{23CE} ");
    let mut out: String = flat.chars().take(MAX_MESSAGE_CHARS).collect();
    if flat.chars().count() > MAX_MESSAGE_CHARS {
        out.push_str("…(截断)");
    }
    out
}

pub fn format_line(stamp: &str, level: &str, source: &str, message: &str) -> String {
    format!(
        "{stamp} [{}] [{}] {}\n",
        normalize_level(level),
        normalize_source(source),
        clean_message(message)
    )
}

fn rotate_if_needed(file: &Path) -> Result<(), String> {
    let len = std::fs::metadata(file).map(|m| m.len()).unwrap_or(0);
    if len < MAX_FILE_BYTES {
        return Ok(());
    }
    let bak = backup_path(file);
    // 已有备份先删再改名，避免 Windows 上 rename 到已存在目标直接失败
    let _ = std::fs::remove_file(&bak);
    let _ = std::fs::rename(file, &bak);
    Ok(())
}

pub fn append_line(file: &Path, line: &str) -> Result<(), String> {
    if let Some(dir) = file.parent() {
        std::fs::create_dir_all(dir).map_err(|e| format!("建日志目录失败：{e}"))?;
    }
    rotate_if_needed(file)?;
    use std::io::Write;
    let mut f = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(file)
        .map_err(|e| format!("打开日志失败：{e}"))?;
    f.write_all(line.as_bytes())
        .map_err(|e| format!("写日志失败：{e}"))
}

/// 写一条日志。
///
/// 两道闸各管一件事：
///
/// - **同线程重入**直接放过：崩溃钩子里写日志、写日志本身又炸了，再往下钻会无限递归。
/// - **跨线程**排队：前端一次抛一串错误、几个 tokio 任务同时报错，谁都不许被丢，也不许把字插到别人行中间。
///
/// 任何失败都咽掉——记录日志这件事本身不该把应用带崩。
pub fn write_entry_to(file: &Path, level: &str, source: &str, message: &str) {
    if INSIDE_WRITE.with(|f| f.replace(true)) {
        return; // 这个线程已经在写（多半是写日志自己炸了、钩子又来一遍）
    }
    let _depth = InsideGuard;
    let _serial = WRITE_LOCK.lock().unwrap_or_else(|e| e.into_inner()); // 前一个写的人炸了也要继续写
    let _ = append_line(
        file,
        &format_line(&iso8601_utc(now_secs()), level, source, message),
    );
}

pub fn write_entry(app: &tauri::AppHandle, level: &str, source: &str, message: &str) {
    if let Ok(path) = log_file(app) {
        write_entry_to(&path, level, source, message);
    }
}

/// 装一个 panic 钩子：Rust 侧崩溃（含 tokio 任务里的 panic）都会先落一行日志，再走原来的钩子。
pub fn install_panic_hook(app: tauri::AppHandle) {
    let prev = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let where_ = info
            .location()
            .map(|l| format!("{}:{}:{}", l.file(), l.line(), l.column()))
            .unwrap_or_else(|| "unknown".to_string());
        let msg = format!("{info} @ {where_}");
        write_entry(&app, "error", "rust-panic", &msg);
        prev(info);
    }));
}

#[derive(Serialize)]
pub struct DiagInfo {
    pub path: String,
    pub bytes: u64,
}

#[tauri::command]
pub fn diag_log(app: tauri::AppHandle, level: String, source: String, message: String) {
    write_entry(&app, &level, &source, &message);
}

#[tauri::command]
pub fn diag_info(app: tauri::AppHandle) -> Result<DiagInfo, String> {
    let path = log_file(&app)?;
    let bytes = std::fs::metadata(&path).map(|m| m.len()).unwrap_or(0);
    Ok(DiagInfo {
        path: path.display().to_string(),
        bytes,
    })
}

/// 读日志尾巴（最多 200 行），「复制诊断信息」用它。
#[tauri::command]
pub fn diag_tail(app: tauri::AppHandle, lines: Option<usize>) -> Result<String, String> {
    let path = log_file(&app)?;
    let raw = match std::fs::read_to_string(&path) {
        Ok(t) => t,
        Err(_) => return Ok(String::new()),
    };
    let want = lines.unwrap_or(40).clamp(1, TAIL_LIMIT);
    let all: Vec<&str> = raw.lines().collect();
    let start = all.len().saturating_sub(want);
    Ok(all[start..].join("\n"))
}

/// 在文件管理器里定位日志文件（用户点按钮才触发，不自动弹窗）。
#[tauri::command]
pub fn diag_reveal(app: tauri::AppHandle) -> Result<(), String> {
    let path = log_file(&app)?;
    let dir = path
        .parent()
        .map(Path::to_path_buf)
        .ok_or_else(|| "日志目录不可用".to_string())?;
    std::fs::create_dir_all(&dir).map_err(|e| format!("建日志目录失败：{e}"))?;
    if !path.exists() {
        // 还没有日志时先落一个空文件，否则「定位到文件」在资源管理器里选不中东西
        let _ = std::fs::write(&path, "");
    }
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("explorer.exe")
            .arg(format!("/select,{}", path.display()))
            .spawn()
            .map_err(|e| format!("打开资源管理器失败：{e}"))?;
    }
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg("-R")
            .arg(&path)
            .spawn()
            .map_err(|e| format!("打开访达失败：{e}"))?;
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    {
        std::process::Command::new("xdg-open")
            .arg(&dir)
            .spawn()
            .map_err(|e| format!("打开文件管理器失败：{e}"))?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn iso8601_matches_known_dates() {
        assert_eq!(iso8601_utc(0), "1970-01-01T00:00:00Z");
        // 2026-11-18T00:00:00Z
        assert_eq!(iso8601_utc(1794960000), "2026-11-18T00:00:00Z");
        // 2024 闰年 2 月 29 日
        assert_eq!(iso8601_utc(1709164800), "2024-02-29T00:00:00Z");
        assert_eq!(
            iso8601_utc(1794960000 + 15 * 3600 + 40 * 60 + 12),
            "2026-11-18T15:40:12Z"
        );
    }

    #[test]
    fn level_is_limited_to_three_buckets() {
        assert_eq!(normalize_level("info"), "INFO");
        assert_eq!(normalize_level("DEBUG"), "INFO");
        assert_eq!(normalize_level("warn"), "WARN");
        assert_eq!(normalize_level("warning"), "WARN");
        assert_eq!(normalize_level("panic"), "ERROR");
        assert_eq!(normalize_level(""), "ERROR");
    }

    #[test]
    fn source_is_sanitized() {
        assert_eq!(normalize_source("UI"), "ui");
        assert_eq!(normalize_source("rust-panic"), "rust-panic");
        assert_eq!(normalize_source("bad source \u{7f}!"), "badsource");
        assert_eq!(normalize_source(""), "app");
        assert_eq!(
            normalize_source("averyveryverylongsource"),
            "averyveryverylon"
        );
    }

    #[test]
    fn message_stays_on_one_line() {
        let one = clean_message("第一行\nerror: 炸了\r\n  结尾");
        assert!(!one.contains('\n'), "日志条目不允许物理换行：{one}");
        assert!(!one.contains('\r'));
        assert!(one.contains("第一行"));
        assert!(one.contains("error: 炸了"));
        assert!(one.contains("结尾"));
    }

    #[test]
    fn long_message_is_truncated_by_chars() {
        let raw = "汉".repeat(MAX_MESSAGE_CHARS + 10);
        let out = clean_message(&raw);
        assert!(out.ends_with("…(截断)"));
        // 4000 个汉字 + 标记，按字节算早就爆了，这里必须按字符裁
        assert_eq!(
            out.chars().filter(|c| *c == '汉').count(),
            MAX_MESSAGE_CHARS
        );
    }

    #[test]
    fn line_format_is_stable() {
        let line = format_line("2026-11-18T15:40:12Z", "error", "ui", "boom\nstack");
        assert!(line.starts_with("2026-11-18T15:40:12Z [ERROR] [ui] boom"));
        assert_eq!(line.matches('\n').count(), 1, "一条日志只能有一个结尾换行");
        assert!(line.ends_with('\n'));
    }

    #[test]
    fn backup_name_appends_suffix() {
        assert_eq!(
            backup_path(Path::new("/tmp/portio.log")),
            PathBuf::from("/tmp/portio.log.1")
        );
    }

    #[test]
    fn append_and_rotate() {
        let dir = std::env::temp_dir().join(format!("portio-diag-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let file = dir.join("portio.log");
        append_line(&file, "a\n").unwrap();
        append_line(&file, "b\n").unwrap();
        let text = std::fs::read_to_string(&file).unwrap();
        assert_eq!(text, "a\nb\n");

        // 手工把文件撑过阈值，再写一条应当触发轮转：新文件只剩新行，旧内容进 .1
        let mut big = String::new();
        while (big.len() as u64) < MAX_FILE_BYTES {
            big.push_str("x\n");
        }
        std::fs::write(&file, &big).unwrap();
        append_line(&file, "after-rotate\n").unwrap();
        assert_eq!(std::fs::read_to_string(&file).unwrap(), "after-rotate\n");
        let bak = backup_path(&file);
        assert!(bak.exists(), "轮转后的备份应当存在");
        assert!(std::fs::metadata(&bak).unwrap().len() >= MAX_FILE_BYTES);
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// 别的线程在写日志时，这一条不许被丢掉。
    ///
    /// 以前用一个进程级的 `AtomicBool` 挡重入：只要有人在写就把后来的整条扔掉，
    /// 于是"前端一次抛一串错误"或"一个任务正在报错、另一个任务刚好崩了"的时候，
    /// 后面的行（包括崩溃那一条）是静默消失的。
    #[test]
    fn concurrent_writers_never_lose_a_line() {
        const THREADS: usize = 8;
        const PER_THREAD: usize = 120;

        let dir = std::env::temp_dir().join(format!("portio-diag-conc-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let file = dir.join("portio.log");

        let mut handles = Vec::new();
        for t in 0..THREADS {
            let file = file.clone();
            handles.push(std::thread::spawn(move || {
                for i in 0..PER_THREAD {
                    write_entry_to(&file, "error", "ui", &format!("t{t}-{i}"));
                }
            }));
        }
        for h in handles {
            h.join().unwrap();
        }

        let raw = std::fs::read_to_string(&file).unwrap();
        let lines: Vec<&str> = raw.lines().collect();
        assert_eq!(
            lines.len(),
            THREADS * PER_THREAD,
            "并发写日志丢了行：只落下来 {} / {}",
            lines.len(),
            THREADS * PER_THREAD
        );

        // 每一条都必须完整地落在自己那一行里（不许两条日志的字插在一起）
        let mut seen: Vec<String> = Vec::new();
        for line in &lines {
            assert!(
                line.contains(" [ERROR] [ui] "),
                "行格式坏了（时间戳 / 级别 / 来源没有各自归位）：{line}"
            );
            assert_eq!(
                line.matches("[ERROR]").count(),
                1,
                "一行里塞了不止一条日志：{line}"
            );
            let msg = line.rsplit(' ').next().unwrap();
            seen.push(msg.to_string());
        }
        seen.sort();
        seen.dedup();
        assert_eq!(seen.len(), THREADS * PER_THREAD, "出现了重复或残缺的日志内容");
        for t in 0..THREADS {
            for i in 0..PER_THREAD {
                let want = format!("t{t}-{i}");
                assert!(seen.contains(&want), "丢了这一条：{want}");
            }
        }

        let _ = std::fs::remove_dir_all(&dir);
    }

    /// 同一线程里重入（写日志自己 panic → 钩子再写一遍）必须直接放过，不能递归、也不能把闸卡死。
    #[test]
    fn reentry_on_the_same_thread_is_skipped_and_the_gate_resets() {
        let dir = std::env::temp_dir().join(format!("portio-diag-reent-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let file = dir.join("portio.log");

        // 手工把"这个线程正在写"点亮，模拟重入现场
        INSIDE_WRITE.with(|f| f.set(true));
        write_entry_to(&file, "error", "rust-panic", "递归进来的那条不该落盘");
        assert!(!file.exists(), "重入时不应该再写一条");

        // 闸放开之后必须立刻恢复，否则后面所有日志都会静默消失
        INSIDE_WRITE.with(|f| f.set(false));
        write_entry_to(&file, "info", "app", "闸放开之后的这一条");
        let raw = std::fs::read_to_string(&file).unwrap();
        assert!(raw.contains("闸放开之后的这一条"), "闸没复位：{raw}");

        let _ = std::fs::remove_dir_all(&dir);
    }
}
