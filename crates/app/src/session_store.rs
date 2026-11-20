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
    write_store_atomic(&path, &store)?;
    Ok(path.to_string_lossy().to_string())
}

/// 原子落盘：先写 `sessions.json.tmp`，再改名成正式文件。
///
/// 分出这一步是为了能脱离 Tauri 单测——目录、改名、残留这几件事，
/// 只有真往磁盘写一遍才验得出来。
fn write_store_atomic(path: &std::path::Path, store: &SessionStore) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("建目录失败：{e}"))?;
    }
    let tmp = path.with_extension("json.tmp");
    let text = store.to_json();
    fs::write(&tmp, text.as_bytes()).map_err(|e| format!("写临时文件失败：{e}"))?;
    fs::rename(&tmp, path).map_err(|e| format!("替换清单文件失败：{e}"))?;
    Ok(())
}

/// 清单文件到底在哪，前端拿去显示给用户，方便自己备份。
#[tauri::command]
pub fn sessions_path(app: tauri::AppHandle) -> Result<String, String> {
    Ok(store_path(&app)?.to_string_lossy().to_string())
}

/// 这一份字节到底还能不能当清单读：空文件（含只有空白）算「还没写过会话」，不算坏。
fn store_text_is_readable(bytes: &[u8]) -> bool {
    match std::str::from_utf8(bytes) {
        Ok(text) if text.trim().is_empty() => true,
        Ok(text) => SessionStore::from_json(text).is_ok(),
        // 半截写入 / 编码坏掉的文件读不成文本，一样算读不懂
        Err(_) => false,
    }
}

/// 清单读坏了就先另存一份，返回另存到哪儿；文件本来好好的（或还没有文件）返回 `None`。
///
/// 为什么非另存不可：前端解析不了时只能从空清单起步，而用户随后随手存一条会话，
/// `sessions_write` 就会把整份文件覆盖掉——原来那些记录再也读不回来，也说不清丢在哪。
/// 所以先把原文件按字节拷成 `sessions.json.broken-<毫秒时间戳>`，再让前端从空清单开始。
fn salvage_broken(path: &std::path::Path) -> Result<Option<PathBuf>, String> {
    let bytes = match fs::read(path) {
        Ok(b) => b,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(err) => return Err(format!("读会话清单失败：{err}")),
    };
    if store_text_is_readable(&bytes) {
        return Ok(None);
    }
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let dest = path.with_file_name(format!("{FILE_NAME}.broken-{stamp}"));
    fs::copy(path, &dest).map_err(|e| format!("另存坏掉的会话清单失败：{e}"))?;
    Ok(Some(dest))
}

/// 前端解析会话清单失败时调一次：把坏文件另存，返回另存的路径；本来就是好的返回 `null`。
#[tauri::command]
pub fn sessions_salvage(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let path = store_path(&app)?;
    Ok(salvage_broken(&path)?.map(|p| p.to_string_lossy().to_string()))
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

/// WinSCP 的 INI 可能在的地方：便携模式放用户目录，官方安装版导出时也常见在 Documents。
/// 没有文件选择对话框之前，按顺序找这几处，都找不到就把路径列给用户看。
fn winscp_candidates(app: &tauri::AppHandle) -> Vec<PathBuf> {
    let mut v = Vec::new();
    if let Ok(d) = app.path().data_dir() {
        v.push(d.join("WinSCP.ini"));
    }
    if let Ok(d) = app.path().local_data_dir() {
        v.push(d.join("WinSCP.ini"));
    }
    if let Ok(d) = app.path().document_dir() {
        v.push(d.join("WinSCP.ini"));
    }
    v
}

/// 从 `WinSCP.ini` 导入站点。`path` 为空时按 `winscp_candidates` 顺序找第一份存在的。
#[tauri::command]
pub fn sessions_import_winscp(
    app: tauri::AppHandle,
    path: Option<String>,
) -> Result<ImportReport, String> {
    let source = match path.as_deref().map(str::trim).filter(|p| !p.is_empty()) {
        Some(p) => std::path::PathBuf::from(p),
        None => {
            let candidates = winscp_candidates(&app);
            match candidates.iter().find(|p| p.is_file()) {
                Some(p) => p.clone(),
                None => {
                    let list = candidates
                        .iter()
                        .map(|p| p.to_string_lossy().to_string())
                        .collect::<Vec<_>>()
                        .join(" / ");
                    return Err(format!(
                        "没找到 WinSCP.ini（找过这些位置：{list}）；把配置导出一份放到其中一处再试"
                    ));
                }
            }
        }
    };
    if !source.is_file() {
        return Err(format!("读不到 WinSCP 配置：{}", source.to_string_lossy()));
    }

    let store_json = match fs::read_to_string(store_path(&app)?) {
        Ok(t) => t,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => String::new(),
        Err(err) => return Err(format!("读会话清单失败：{err}")),
    };
    let mut store = SessionStore::from_json(&store_json).map_err(|e| e.to_string())?;
    let (added, skipped) = import_winscp_file(&mut store, &source)?;
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

/// 把一份 `WinSCP.ini` 合并进清单（不落盘）。返回（新增条数，跳过总数）。
fn import_winscp_file(
    store: &mut SessionStore,
    source: &std::path::Path,
) -> Result<(usize, usize), String> {
    let text = fs::read_to_string(source)
        .map_err(|e| format!("读不到 {}：{e}", source.to_string_lossy()))?;
    let outcome = portio_core::parse_winscp_ini(&text);
    let mut incoming = SessionStore::new();
    for rec in outcome.records {
        let _ = incoming.upsert(rec);
    }
    let (added, dup) = store.merge(incoming);
    Ok((added, outcome.skipped + dup))
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
    fn atomic_write_lands_clean_file_and_creates_dir() {
        let dir = std::env::temp_dir().join(format!(
            "portio_store_{}_{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let path = dir.join("nested").join(FILE_NAME); // 目录故意还不存在

        let mut store = SessionStore::new();
        store.records.push(portio_core::SessionRecord {
            host: "web-01.prod".into(),
            port: 22,
            user: "deploy".into(),
            auth: "key".into(),
            keyfile: Some("~/.ssh/id_ed25519".into()),
            name: None,
            last_used: 1_763_000_000_000,
        });
        store.records.push(portio_core::SessionRecord {
            host: "db-01.prod".into(),
            port: 2222,
            user: "dba".into(),
            auth: "password".into(),
            keyfile: None,
            name: None,
            last_used: 0,
        });

        write_store_atomic(&path, &store).unwrap();

        assert!(path.exists(), "目录不在时要顺手建出来");
        let text = fs::read_to_string(&path).unwrap();
        let back = SessionStore::from_json(&text).unwrap();
        assert_eq!(back.records.len(), 2, "两条都要在");
        assert_eq!(
            back.records[0].last_used, 1_763_000_000_000,
            "最近用过的时间戳不能在半路丢掉"
        );
        assert_eq!(back.records[0].key(), "deploy@web-01.prod:22");
        assert!(
            !path.with_extension("json.tmp").exists(),
            "改完名之后不该留下临时文件"
        );

        // 再写一次：整份替换，不叠加、不留旧行
        let mut one = SessionStore::new();
        one.records.push(portio_core::SessionRecord {
            host: "only.example".into(),
            port: 22,
            user: "ops".into(),
            auth: "password".into(),
            keyfile: None,
            name: None,
            last_used: 5,
        });
        write_store_atomic(&path, &one).unwrap();
        let back2 = SessionStore::from_json(&fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(back2.records.len(), 1, "覆盖写只该剩最后那份");
        assert_eq!(back2.records[0].host, "only.example");
        assert!(!path.with_extension("json.tmp").exists());

        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn bad_json_is_rejected_before_touching_disk() {
        // sessions_write 先解析再落盘：坏数据根本走不到 write_store_atomic，
        // 所以磁盘上原来那份好文件必须原封不动。
        let dir = std::env::temp_dir().join(format!(
            "portio_store_bad_{}_{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join(FILE_NAME);
        let good = "{\"version\":1,\"records\":[{\"host\":\"keep.example\",\"port\":22,\"user\":\"ops\"}]}";
        fs::write(&path, good.as_bytes()).unwrap();

        assert!(
            SessionStore::from_json("{ 这不是 JSON }").is_err(),
            "坏 JSON 必须在校验那步就被拒"
        );
        assert_eq!(fs::read_to_string(&path).unwrap(), good, "旧文件不该被动过");
        fs::remove_dir_all(&dir).ok();
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
        assert!(
            web.keyfile.as_deref().unwrap().starts_with(&home),
            "~ 应展开到传入的 home"
        );
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
        let err = import_into_store(
            &mut store,
            std::path::Path::new("Z:\\nope\\config"),
            std::path::Path::new("C:\\"),
        )
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
        let db = store
            .records
            .iter()
            .find(|r| r.host == "10.9.9.10")
            .unwrap();
        assert_eq!(db.auth, "key");
        assert_eq!(db.name.as_deref(), Some("db-01"), "文件名当备注名");
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn winscp_ini_imports_ssh_and_skips_ftp() {
        let dir = std::env::temp_dir().join(format!(
            "portio_ini_{}_{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&dir).unwrap();
        let ini = dir.join("WinSCP.ini");
        fs::write(
            &ini,
            "[Sessions\\web-02]\nHostName=10.4.4.4\nUserName=deploy\nPortNumber=22\nFSProtocol=2\n\n\
             [Sessions\\ftp-legacy]\nHostName=ftp.example.com\nUserName=anon\nFSProtocol=3\n",
        )
        .unwrap();
        let mut store = SessionStore::new();
        assert_eq!(import_winscp_file(&mut store, &ini).unwrap(), (1, 1));
        assert_eq!(store.records[0].host, "10.4.4.4");
        assert_eq!(store.records[0].name.as_deref(), Some("web-02"));
        fs::remove_dir_all(&dir).ok();
    }

    fn temp_store_dir(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "portio_salvage_{}_{}_{}",
            tag,
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn one_record(host: &str) -> portio_core::SessionRecord {
        portio_core::SessionRecord {
            host: host.into(),
            port: 22,
            user: "ops".into(),
            auth: "password".into(),
            keyfile: None,
            name: None,
            last_used: 0,
        }
    }

    #[test]
    fn salvage_copies_broken_store_before_it_gets_overwritten() {
        let dir = temp_store_dir("keep");
        let path = dir.join(FILE_NAME);
        // 半截写入：一条记录只写进去一半，解析必失败
        let trash = "{\"version\":1,\"records\":[{\"host\":\"web-01.p";
        fs::write(&path, trash.as_bytes()).unwrap();

        let kept = salvage_broken(&path)
            .expect("坏文件不该报错")
            .expect("坏文件要另存一份");
        assert!(kept.is_file(), "另存的那份得真在磁盘上：{}", kept.display());
        assert_eq!(
            fs::read_to_string(&kept).unwrap(),
            trash,
            "另存的必须是原样字节"
        );
        assert_eq!(
            fs::read_to_string(&path).unwrap(),
            trash,
            "这会儿原文件先别动它"
        );
        assert!(
            kept.file_name()
                .unwrap()
                .to_string_lossy()
                .starts_with("sessions.json.broken-"),
            "另存的名字要一眼看出是什么：{}",
            kept.display()
        );

        // 前端从空清单起步后第一次存盘：原文件被整份盖掉，另存的那份得活下来
        let mut store = SessionStore::new();
        store.records.push(one_record("new.example"));
        write_store_atomic(&path, &store).unwrap();
        assert!(
            !fs::read_to_string(&path).unwrap().contains("web-01.p"),
            "原文件这时候已经被新清单覆盖了"
        );
        assert_eq!(
            fs::read_to_string(&kept).unwrap(),
            trash,
            "覆盖之后另存的那份还是原来那些字节——这才是它存在的理由"
        );
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn salvage_leaves_good_empty_and_missing_files_alone() {
        let dir = temp_store_dir("ok");
        let path = dir.join(FILE_NAME);
        assert!(
            salvage_broken(&path).unwrap().is_none(),
            "还没有这个文件就不用另存"
        );

        let good =
            "{\"version\":1,\"records\":[{\"host\":\"a.example\",\"port\":22,\"user\":\"ops\"}]}";
        fs::write(&path, good.as_bytes()).unwrap();
        assert!(salvage_broken(&path).unwrap().is_none(), "好文件不用另存");

        fs::write(&path, b"  \n\t ").unwrap();
        assert!(
            salvage_broken(&path).unwrap().is_none(),
            "空白文件等同还没写过会话"
        );

        fs::write(&path, b"").unwrap();
        assert!(salvage_broken(&path).unwrap().is_none(), "空文件同理");

        let leftovers: Vec<String> = fs::read_dir(&dir)
            .unwrap()
            .filter_map(|e| e.ok())
            .map(|e| e.file_name().to_string_lossy().into_owned())
            .filter(|n| n.contains("broken"))
            .collect();
        assert!(leftovers.is_empty(), "没坏就不该留下副本：{leftovers:?}");
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn salvage_catches_garbage_bytes_and_future_version() {
        let dir = temp_store_dir("bytes");
        let path = dir.join(FILE_NAME);

        // 读不成 UTF-8 的字节（断电写了一半的典型样子）也算读不懂
        fs::write(&path, b"\xff\xfe{\"version\":1").unwrap();
        assert!(
            salvage_broken(&path).unwrap().is_some(),
            "读不成文本的也算坏"
        );

        // 版本号比程序新的：程序拒绝解析，同样得先另存再从头开始
        fs::write(&path, b"{\"version\":9,\"records\":[]}").unwrap();
        assert!(
            salvage_broken(&path).unwrap().is_some(),
            "版本比程序新的也读不懂"
        );
        fs::remove_dir_all(&dir).ok();
    }
}
