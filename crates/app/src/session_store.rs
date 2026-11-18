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

/// 从 OpenSSH 客户端配置导入主机。
///
/// 解析规则全在 `portio_core::parse_ssh_config`，这里只负责"找文件 → 读文本 → 合并 → 落盘"。
/// 返回合并后的完整清单 JSON 与计数，前端直接拿去替换内存里的那份。
#[derive(serde::Serialize)]
pub struct ImportReport {
    pub json: String,
    /// 本次新导入 / 更新的条数。
    pub added: usize,
    /// 配置里被跳过的块数（通配符块、缺用户名、与已有记录重复）。
    pub skipped: usize,
    /// 实际读的是哪份文件，出错时给用户看。
    pub source: String,
}

#[tauri::command]
pub fn sessions_import_ssh_config(
    app: tauri::AppHandle,
    path: Option<String>,
) -> Result<ImportReport, String> {
    let home = app
        .path()
        .home_dir()
        .map_err(|e| format!("拿不到用户目录：{e}"))?;
    let source = match path.as_deref().map(str::trim).filter(|p| !p.is_empty()) {
        Some(p) => std::path::PathBuf::from(p),
        None => home.join(".ssh").join("config"),
    };
    // 清单本身也要能读：坏文件不该被导入悄悄覆盖成空表
    let store_json = match fs::read_to_string(store_path(&app)?) {
        Ok(t) => t,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => String::new(),
        Err(err) => return Err(format!("读会话清单失败：{err}")),
    };
    let mut store = SessionStore::from_json(&store_json).map_err(|e| e.to_string())?;
    let (added, skipped_extra) = import_into_store(&mut store, &source, &home)?;
    let json = store.to_json();
    // 只有真的变化了才写盘，免得每次点导入都改文件时间
    if added > 0 {
        let p = store_path(&app)?;
        if let Some(parent) = p.parent() {
            fs::create_dir_all(parent).map_err(|e| format!("建目录失败：{e}"))?;
        }
        let tmp = p.with_extension("json.tmp");
        fs::write(&tmp, json.as_bytes()).map_err(|e| format!("写临时文件失败：{e}"))?;
        fs::rename(&tmp, &p).map_err(|e| format!("替换清单文件失败：{e}"))?;
    }
    Ok(ImportReport {
        json,
        added,
        skipped: skipped_extra,
        source: source.to_string_lossy().to_string(),
    })
}

/// Xshell 的会话目录默认位置：`%APPDATA%\NetSarang\Xshell\Sessions`。
/// 那里一个 `.xsh` 对一台主机，用户装过 Xshell 就一定有。
fn xshell_default_dir(app: &tauri::AppHandle) -> Option<PathBuf> {
    app.path()
        .data_dir()
        .ok()
        .map(|d| d.join("NetSarang").join("Xshell").join("Sessions"))
}

/// 从 Xshell 会话目录导入主机。
///
/// 规则全在 `portio_core::parse_xshell_session`（一个文件一台机器）；这里只负责
/// "遍历目录 → 逐个解析 → 合并 → 落盘"。密码字段不读，识别的只有主机/端口/账号/私钥路径。
#[tauri::command]
pub fn sessions_import_xshell(
    app: tauri::AppHandle,
    dir: Option<String>,
) -> Result<ImportReport, String> {
    let source = match dir.as_deref().map(str::trim).filter(|p| !p.is_empty()) {
        Some(p) => std::path::PathBuf::from(p),
        None => xshell_default_dir(&app).ok_or_else(|| "拿不到 Xshell 会话目录".to_string())?,
    };
    if !source.is_dir() {
        return Err(format!(
            "找不到 Xshell 会话目录：{}（装过 Xshell 才会有这个目录）",
            source.to_string_lossy()
        ));
    }

    let store_json = match fs::read_to_string(store_path(&app)?) {
        Ok(t) => t,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => String::new(),
        Err(err) => return Err(format!("读会话清单失败：{err}")),
    };
    let mut store = SessionStore::from_json(&store_json).map_err(|e| e.to_string())?;
    let (added, skipped) = import_xshell_dir(&mut store, &source)?;
    let json = store.to_json();
    if added > 0 {
        let p = store_path(&app)?;
        if let Some(parent) = p.parent() {
            fs::create_dir_all(parent).map_err(|e| format!("建目录失败：{e}"))?;
        }
        let tmp = p.with_extension("json.tmp");
        fs::write(&tmp, json.as_bytes()).map_err(|e| format!("写临时文件失败：{e}"))?;
        fs::rename(&tmp, &p).map_err(|e| format!("替换清单文件失败：{e}"))?;
    }
    Ok(ImportReport {
        json,
        added,
        skipped,
        source: source.to_string_lossy().to_string(),
    })
}

/// 遍历一个 Xshell 会话目录（含子目录，用户常按分组建子文件夹），合并进清单。
/// 返回（新增条数，跳过总数：解析不出必需项的会话 + 与已有记录重复的）。
fn import_xshell_dir(
    store: &mut SessionStore,
    dir: &std::path::Path,
) -> Result<(usize, usize), String> {
    let mut incoming = SessionStore::new();
    let mut skipped = 0usize;
    let mut stack = vec![dir.to_path_buf()];
    while let Some(cur) = stack.pop() {
        let entries = fs::read_dir(&cur)
            .map_err(|e| format!("读目录 {} 失败：{e}", cur.to_string_lossy()))?;
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
                continue;
            }
            let is_xsh = path
                .extension()
                .and_then(|e| e.to_str())
                .is_some_and(|e| e.eq_ignore_ascii_case("xsh"));
            if !is_xsh {
                continue;
            }
            let stem = path.file_stem().and_then(|s| s.to_str());
            match fs::read_to_string(&path) {
                Ok(text) => match portio_core::parse_xshell_session(&text, stem) {
                    Some(rec) => {
                        // 单条坏记录不连累整批
                        if incoming.upsert(rec).is_err() {
                            skipped += 1;
                        }
                    }
                    None => skipped += 1,
                },
                Err(_) => skipped += 1,
            }
        }
    }
    let (added, dup) = store.merge(incoming);
    Ok((added, skipped + dup))
}

/// 把一份 ssh config 合并进已有清单（不落盘）。返回（新增条数，跳过总数）。
/// 抽成独立函数是为了能脱离 Tauri 直接测：解析、合并、跳过的规则都在这里，
/// 命令层只剩"找路径 / 读 / 写"三件事。
fn import_into_store(
    store: &mut SessionStore,
    source: &std::path::Path,
    home: &std::path::Path,
) -> Result<(usize, usize), String> {
    let text = fs::read_to_string(source).map_err(|e| {
        format!(
            "读不到 {}：{e}（确认文件存在，或手工指定另一份配置）",
            source.to_string_lossy()
        )
    })?;
    let outcome = portio_core::parse_ssh_config(&text, None, Some(&home.to_string_lossy()));
    let mut incoming = SessionStore::new();
    for rec in outcome.records {
        // 单条坏记录跳过，不连累整批
        let _ = incoming.upsert(rec);
    }
    let (added, dup) = store.merge(incoming);
    Ok((added, outcome.skipped + dup))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn temp_config(text: &str) -> (std::path::PathBuf, std::path::PathBuf) {
        let dir = std::env::temp_dir().join(format!(
            "portio_import_{}_{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&dir).unwrap();
        let cfg = dir.join("config");
        let mut f = fs::File::create(&cfg).unwrap();
        f.write_all(text.as_bytes()).unwrap();
        (dir.clone(), cfg)
    }

    #[test]
    fn import_merges_and_reports_counts() {
        let (dir, cfg) = temp_config(
            "\
Host web-01
  HostName 10.1.1.1
  User deploy
  IdentityFile ~/.ssh/id_ed25519

Host db-01
  HostName 10.1.1.2
  User deploy

Host *
  User nobody
",
        );
        let mut store = SessionStore::new();
        let (added, skipped) = import_into_store(&mut store, &cfg, &dir).unwrap();
        assert_eq!(added, 2);
        assert_eq!(skipped, 1, "通配符块跳过");
        assert_eq!(store.records.len(), 2);
        let web = store
            .records
            .iter()
            .find(|r| r.host == "10.1.1.1")
            .expect("web-01 应该在清单里");
        assert_eq!(web.auth, "key");
        assert_eq!(web.port, 22);
        let home = dir.to_string_lossy().to_string();
        assert!(web
            .keyfile
            .as_deref()
            .unwrap()
            .starts_with(&home), "~ 应展开到传入的 home");
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn reimport_is_idempotent() {
        let (dir, cfg) = temp_config("Host a\n  HostName 1.2.3.4\n  User u\n");
        let mut store = SessionStore::new();
        assert_eq!(import_into_store(&mut store, &cfg, &dir).unwrap(), (1, 0));
        // 第二次：同键覆盖、不算新增
        assert_eq!(import_into_store(&mut store, &cfg, &dir).unwrap(), (1, 0));
        assert_eq!(store.records.len(), 1, "重复导入不叠加记录");
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn missing_file_is_an_error_not_empty_import() {
        let mut store = SessionStore::new();
        let err = import_into_store(&mut store, std::path::Path::new("Z:\\nope\\config"), std::path::Path::new("C:\\"))
            .unwrap_err();
        assert!(err.contains("读不到"), "错误要指出是哪份文件：{err}");
        assert!(store.records.is_empty());
    }

    #[test]
    fn xshell_dir_imports_valid_and_skips_bad_ones() {
        let dir = std::env::temp_dir().join(format!(
            "portio_xsh_{}_{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(dir.join("生产")).unwrap();
        fs::write(
            dir.join("推一台.xsh"),
            "[CONNECTION]\nProtocol=S\nHost=10.9.9.9\nPort=2200\n[CONNECTION:AUTHENTICATION]\nUserName=ops\n",
        )
        .unwrap();
        // 分组子目录里的会话也要收进来，并用文件名当备注名
        fs::write(
            dir.join("生产").join("db-01.xsh"),
            "[CONNECTION]\nProtocol=S\nHost=10.9.9.10\n[CONNECTION:AUTHENTICATION]\nUserName=dba\nUserKey=\"C:\\k\\id\"\n",
        )
        .unwrap();
        // RDP 会话：没有 SSH 意义，应当跳过
        fs::write(
            dir.join("远程桌面.xsh"),
            "[CONNECTION]\nProtocol=RDP\nHost=10.9.9.11\n[CONNECTION:AUTHENTICATION]\nUserName=x\n",
        )
        .unwrap();
        let mut store = SessionStore::new();
        let (added, skipped) = import_xshell_dir(&mut store, &dir).unwrap();
        assert_eq!(added, 2, "两台 SSH 主机");
        assert_eq!(skipped, 1, "RDP 会话跳过");
        let db = store.records.iter().find(|r| r.host == "10.9.9.10").unwrap();
        assert_eq!(db.auth, "key");
        assert_eq!(db.name.as_deref(), Some("db-01"), "文件名当备注名");
        fs::remove_dir_all(&dir).ok();
    }
}