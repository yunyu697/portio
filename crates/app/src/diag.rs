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

/// 从一段字节里取最后 `want` 行。
///
/// 不按 UTF-8 整体解码，而是按行切、逐行容错解码：日志里混进一个坏字节（半截写入、别的程序
/// 往这个文件里写过东西、磁盘出错），**前面的行照样能拿到**，坏字节就地变成 `�`。
/// 旧写法用 `read_to_string` 读整份，一个坏字节就让整段变成空串——日志坏掉的时候，
/// 恰恰是我最需要把它交出去的时候。
pub fn tail_of(bytes: &[u8], want: usize) -> String {
    let mut parts: Vec<&[u8]> = bytes.split(|b| *b == b'\n').collect();
    // 文件以换行结尾时最后那一段是空的，不算一行
    while parts.last().is_some_and(|p| p.is_empty()) {
        parts.pop();
    }
    let want = want.max(1);
    let skip = parts.len().saturating_sub(want);
    let mut out = String::new();
    for (i, part) in parts[skip..].iter().enumerate() {
        if i > 0 {
            out.push('\n');
        }
        let decoded = String::from_utf8_lossy(part);
        out.push_str(decoded.trim_end_matches('\r'));
    }
    out
}

/// 读文件的最后 `want` 行；文件不存在或读不动就当没有内容（不弹错）。
pub fn read_tail_file(file: &Path, want: usize) -> String {
    let current = tail_of_file(file, want);
    if !current.is_empty() {
        return current;
    }
    // 当前文件不存在、或者是个空文件（刚轮转完，新的一条还没写进来）——内容整份都在 `.1` 里。
    // 轮转发生的那一刻，恰恰是我最需要看日志的时候，这时候读空等于把东西藏起来。
    let bak = backup_path(file);
    if bak == file {
        return current;
    }
    tail_of_file(&bak, want)
}

fn tail_of_file(file: &Path, want: usize) -> String {
    match std::fs::read(file) {
        Ok(bytes) => tail_of(&bytes, want),
        Err(_) => String::new(),
    }
}

/// 读日志尾巴（最多 200 行），「复制诊断信息」用它。
#[tauri::command]
pub fn diag_tail(app: tauri::AppHandle, lines: Option<usize>) -> Result<String, String> {
    let path = log_file(&app)?;
    let want = lines.unwrap_or(40).clamp(1, TAIL_LIMIT);
    Ok(read_tail_file(&path, want))
}

/// Windows 上「在资源管理器里选中这个文件」要交给它的原始命令行是
/// `/select,"C:\Users\A B\AppData\...\portio.log"`——引号必须只包住路径本身。
///
/// 旧写法是 `.arg(format!("/select,{}", path))`，参数里一带空格，Rust 就把**整个参数**
/// （连 `/select,` 一起）括进引号，资源管理器拿到的开关名变成 `/select,C:\Users\Tyler`，
/// 于是去选一个不存在的路径。用户名含空格（`C:\Users\Tyler Zhang\…`）是最常见的一种，
/// 这类机器上这个按钮一直是哑的。路径里不可能出现 `"`（Windows 不允许），所以不必转义。
#[cfg(target_os = "windows")]
pub fn select_arg(path: &Path) -> String {
    format!("/select,\"{}\"", path.display())
}

/// 交给资源管理器的那条命令，生产路径与测试用的是同一处。
#[cfg(target_os = "windows")]
fn reveal_command(path: &Path) -> std::process::Command {
    use std::os::windows::process::CommandExt;
    let mut cmd = std::process::Command::new("explorer.exe");
    // 用 raw_arg 逐字送过去：explorer 不按常规的引号规则解析，交给它自己拼会被改坏
    cmd.raw_arg(select_arg(path));
    cmd
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
        reveal_command(&path)
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
        assert_eq!(
            seen.len(),
            THREADS * PER_THREAD,
            "出现了重复或残缺的日志内容"
        );
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

    /// 文件里混进坏字节时，前面完好的行必须照样拿得到。
    ///
    /// 旧写法 `read_to_string` 读整份文件，遇到一个非法 UTF-8 字节就整段返回空——
    /// 于是"日志坏了"这件事本身把证据也一起吞掉了。
    #[test]
    fn a_damaged_log_still_yields_the_intact_lines() {
        let dir = std::env::temp_dir().join(format!("portio-diag-damaged-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let file = dir.join("portio.log");

        let mut bytes: Vec<u8> = Vec::new();
        for i in 0..5 {
            bytes.extend_from_slice(
                format!("2026-11-19T10:00:0{i}Z [ERROR] [ui] 第{i}条\n").as_bytes(),
            );
        }
        // 半截写入 + 一坨非 UTF-8（0xFF / 孤立的续字节 / NUL）
        bytes.extend_from_slice(b"2026-11-19T10:00:06Z [ERROR] [ui] \xff\xfe\x00\x80\x81 tail\r\n");
        bytes.extend_from_slice("2026-11-19T10:00:07Z [INFO] [app] 最后一条".as_bytes());
        std::fs::write(&file, &bytes).unwrap();

        let text = read_tail_file(&file, 200);
        assert!(
            text.contains("[ERROR] [ui] 第3条"),
            "坏字节前面完好的行没拿到：{text:?}"
        );
        assert!(
            text.contains("[ERROR] [ui] 第0条"),
            "最前面那一条也该在（没超出 want 就别裁）：{text:?}"
        );
        assert!(
            text.contains("[INFO] [app] 最后一条"),
            "坏字节后面正常的行没拿到：{text:?}"
        );
        assert!(
            text.contains('\u{FFFD}'),
            "坏字节应该就地变成替换字符，而不是把整行吞掉：{text:?}"
        );
        assert!(
            !text.contains('\r'),
            "CRLF 里的 \\r 不该留在输出里：{text:?}"
        );
        assert_eq!(text.lines().count(), 7, "行数不对：{text:?}");

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn tail_of_keeps_only_the_last_lines_and_handles_edges() {
        let raw = b"a\nb\nc\nd\n";
        assert_eq!(tail_of(raw, 2), "c\nd");
        assert_eq!(tail_of(raw, 99), "a\nb\nc\nd");
        assert_eq!(tail_of(raw, 1), "d");
        assert_eq!(tail_of(b"", 5), "");
        assert_eq!(tail_of(b"\n\n\n", 3), "");
        assert_eq!(tail_of(b"only-one-line", 3), "only-one-line");
        assert_eq!(tail_of(b"a\r\nb\r\n", 1), "b");
    }

    #[test]
    fn a_missing_log_reads_as_empty() {
        let dir = std::env::temp_dir().join(format!("portio-diag-missing-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let file = dir.join("portio.log");
        assert_eq!(read_tail_file(&file, 40), "");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// 资源管理器要的开关是 `/select,"<路径>"`：引号只包路径，`/select,` 留在外面。
    ///
    /// 旧写法把 `/select,<路径>` 当一个普通参数交给 `Command::arg`，路径一带空格
    /// （`C:\Users\Tyler Zhang\…` 就是这种机器）Rust 就把整段括进引号，开关名被吃成
    /// `/select,C:\Users\Tyler`，于是这个按钮在含空格的用户名下一直是哑的。
    #[cfg(target_os = "windows")]
    #[test]
    fn select_arg_keeps_the_switch_outside_the_quotes() {
        let spaced = Path::new(r"C:\Users\Tyler Zhang\AppData\Local\portio\logs\portio.log");
        assert_eq!(
            select_arg(spaced),
            r#"/select,"C:\Users\Tyler Zhang\AppData\Local\portio\logs\portio.log""#
        );
        // 中文目录名同样只在引号里面
        assert_eq!(
            select_arg(Path::new(r"D:\日志 目录\portio.log")),
            "/select,\"D:\\日志 目录\\portio.log\""
        );

        // 旧的调用形态：整个参数被括起来，引号落在 /select 前面
        let old = format!(
            "{:?}",
            std::process::Command::new("explorer.exe").arg(format!("/select,{}", spaced.display()))
        );
        assert!(
            old.contains("\"/select,"),
            "旧写法应当把 /select, 一起括进引号（这才是那个 Bug）：{old}"
        );

        // 新形态：/select, 在引号外面（走生产代码那条构造）
        let new = format!("{:?}", reveal_command(spaced));
        assert!(
            new.contains("/select,\""),
            "新写法应当让 /select, 留在引号外：{new}"
        );
        assert!(
            !new.contains("\"/select,"),
            "新写法不该把 /select, 括进引号：{new}"
        );
    }

    /// 轮转把整份内容搬去 `.1` 的那一瞬间，当前文件不存在；再往后一点，当前文件是个空文件。
    /// 这两种时候「看日志」都得能看到 `.1` 里的东西——出事的时候正好就是这时候。
    #[test]
    fn an_emptied_or_missing_log_falls_back_to_the_backup() {
        let dir = std::env::temp_dir().join(format!("portio-diag-{}-fallback", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let file = dir.join("portio.log");
        let bak = backup_path(&file);

        // ① 刚轮转：当前文件已被改走，只剩 `.1`
        std::fs::write(&bak, "旧的一行\n旧的最后一行\n").unwrap();
        let got = read_tail_file(&file, 5);
        assert_eq!(
            got, "旧的一行\n旧的最后一行",
            "当前文件不存在时该读 .1：{got:?}"
        );

        // ② 快照里当前文件也可能是个 0 字节的空文件
        std::fs::write(&file, b"").unwrap();
        let got = read_tail_file(&file, 5);
        assert_eq!(
            got, "旧的一行\n旧的最后一行",
            "当前文件为空时该读 .1：{got:?}"
        );

        // ③ 当前文件一旦有了新内容，就只读它，不掺旧内容
        std::fs::write(&file, "新的一条\n").unwrap();
        assert_eq!(read_tail_file(&file, 5), "新的一条");
        assert!(
            !read_tail_file(&file, 5).contains("旧的"),
            "当前文件有内容时不该把 .1 混进来"
        );

        // ④ 两份都没有 → 空串（不弹错）
        let _ = std::fs::remove_file(&file);
        let _ = std::fs::remove_file(&bak);
        assert_eq!(read_tail_file(&file, 5), "");

        let _ = std::fs::remove_dir_all(&dir);
    }
}
