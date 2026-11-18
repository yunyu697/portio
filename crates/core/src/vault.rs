//! 口令加密存储。
//!
//! 目标很具体：**让口令不以明文落在磁盘上**。会话文件、备份、误传的日志里都不该出现
//! 可以直接拿去登录的字符串。这里用 AES-256-GCM 加密口令，密钥由一段本地主密钥
//! 经 HKDF 派生，主密钥单独存一个文件。
//!
//! 诚实说明能力边界（写进 docs，也写在代码里）：
//! - 主密钥与密文在同一台机器上，能拿到这台机器文件系统的人就能解出口令。
//!   这防的是"明文被复制走"（同步盘、误打包、截图、日志），不是本地提权攻击。
//! - 后续若要更强，把主密钥换到系统钥匙串（Windows Credential Manager / macOS Keychain），
//!   接口层不用改，只换 `Vault::from_secret` 的密钥来源。

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use ring::aead;
use ring::aead::NONCE_LEN;
use ring::hkdf;
use ring::rand::{SecureRandom, SystemRandom};

/// 主密钥派生出加密密钥时用的上下文串。换加密参数就得换这个串，老密文自然解不开。
const HKDF_INFO: &[u8] = b"portio-credential-vault-v1";
const NONCE_LEN_USIZE: usize = NONCE_LEN;
const CREDENTIALS_VERSION: u8 = 1;

#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum VaultError {
    #[error("密钥派生失败")]
    KeyDerive,
    #[error("随机数生成失败")]
    Random,
    #[error("口令加密失败")]
    Seal,
    #[error("口令解密失败（密文被改动，或换了主密钥）")]
    Open,
    #[error("凭据文件读写失败：{0}")]
    Io(String),
    #[error("凭据文件格式不对：{0}")]
    Format(String),
}

/// 一把已经派生好的加密密钥。构造一次可以反复用。
pub struct Vault {
    key: aead::LessSafeKey,
}

impl Vault {
    /// 由本地主密钥（任意长度字节）派生出 AES-256-GCM 密钥。
    pub fn from_secret(secret: &[u8]) -> Result<Self, VaultError> {
        let salt = hkdf::Salt::new(hkdf::HKDF_SHA256, &[]);
        let prk = salt.extract(secret);
        let okm = prk
            .expand(&[HKDF_INFO], &aead::AES_256_GCM)
            .map_err(|_| VaultError::KeyDerive)?;
        let mut key_bytes = [0u8; 32];
        okm.fill(&mut key_bytes)
            .map_err(|_| VaultError::KeyDerive)?;
        let key = aead::UnboundKey::new(&aead::AES_256_GCM, &key_bytes)
            .map_err(|_| VaultError::KeyDerive)?;
        Ok(Self {
            key: aead::LessSafeKey::new(key),
        })
    }

    /// 加密：输出 `nonce(12) || 密文`。每次都用新 nonce，同样的口令两次结果也不同。
    pub fn seal(&self, plaintext: &str) -> Result<Vec<u8>, VaultError> {
        let rng = SystemRandom::new();
        let mut nonce_bytes = [0u8; NONCE_LEN_USIZE];
        rng.fill(&mut nonce_bytes).map_err(|_| VaultError::Random)?;
        let nonce = aead::Nonce::assume_unique_for_key(nonce_bytes);

        let mut buf = plaintext.as_bytes().to_vec();
        self.key
            .seal_in_place_append_tag(nonce, aead::Aad::empty(), &mut buf)
            .map_err(|_| VaultError::Seal)?;

        let mut out = Vec::with_capacity(NONCE_LEN_USIZE + buf.len());
        out.extend_from_slice(&nonce_bytes);
        out.extend_from_slice(&buf);
        Ok(out)
    }

    /// 解密 `seal` 的输出。密文被改一个字节、或者换了主密钥，都会返回 `Open`。
    pub fn open(&self, blob: &[u8]) -> Result<String, VaultError> {
        if blob.len() <= NONCE_LEN_USIZE {
            return Err(VaultError::Open);
        }
        let (nonce_bytes, cipher) = blob.split_at(NONCE_LEN_USIZE);
        let nonce =
            aead::Nonce::try_assume_unique_for_key(nonce_bytes).map_err(|_| VaultError::Open)?;
        let mut buf = cipher.to_vec();
        let plain = self
            .key
            .open_in_place(nonce, aead::Aad::empty(), &mut buf)
            .map_err(|_| VaultError::Open)?;
        String::from_utf8(plain.to_vec()).map_err(|_| VaultError::Open)
    }
}

/// 会话口令的落盘容器：`{ "version": 1, "entries": { "sess-id": "hex(密文)" } }`。
///
/// 用会话 id 当键而不是主机名：同一个主机换账号登录是两回事。
pub struct CredentialStore {
    path: PathBuf,
    vault: Vault,
    entries: BTreeMap<String, Vec<u8>>,
}

impl std::fmt::Debug for CredentialStore {
    /// 只打印路径与条数，绝不打印密钥或密文。
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("CredentialStore")
            .field("path", &self.path)
            .field("entries", &self.entries.len())
            .finish()
    }
}

impl CredentialStore {
    /// 打开（或新建）凭据文件。文件不存在就当空的，读得到但格式坏了要报错——
    /// 静默当成空会把用户口令"弄丢"而又不告诉他。
    pub fn load(path: impl Into<PathBuf>, secret: &[u8]) -> Result<Self, VaultError> {
        let path = path.into();
        let vault = Vault::from_secret(secret)?;
        let mut entries = BTreeMap::new();
        if path.exists() {
            let text = std::fs::read_to_string(&path).map_err(|e| VaultError::Io(e.to_string()))?;
            entries = parse_credentials(&text)?;
        }
        Ok(Self {
            path,
            vault,
            entries,
        })
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// 记住一个会话的口令。空字符串视为"清除"，不该存一个空口令上去。
    pub fn set_password(&mut self, session_id: &str, password: &str) -> Result<(), VaultError> {
        if password.is_empty() {
            self.entries.remove(session_id);
        } else {
            let blob = self.vault.seal(password)?;
            self.entries.insert(session_id.to_string(), blob);
        }
        self.flush()
    }

    pub fn password(&self, session_id: &str) -> Result<Option<String>, VaultError> {
        match self.entries.get(session_id) {
            Some(blob) => self.vault.open(blob).map(Some),
            None => Ok(None),
        }
    }

    pub fn forget(&mut self, session_id: &str) -> Result<(), VaultError> {
        self.entries.remove(session_id);
        self.flush()
    }

    /// 落盘。先写临时文件再改名，避免写一半断电留下半个 JSON。
    fn flush(&self) -> Result<(), VaultError> {
        if let Some(dir) = self.path.parent() {
            std::fs::create_dir_all(dir).map_err(|e| VaultError::Io(e.to_string()))?;
        }
        let text = render_credentials(&self.entries);
        let tmp = self.path.with_extension("json.tmp");
        std::fs::write(&tmp, text).map_err(|e| VaultError::Io(e.to_string()))?;
        std::fs::rename(&tmp, &self.path).map_err(|e| VaultError::Io(e.to_string()))
    }
}

fn parse_credentials(text: &str) -> Result<BTreeMap<String, Vec<u8>>, VaultError> {
    let doc: serde_json::Value =
        serde_json::from_str(text).map_err(|e| VaultError::Format(e.to_string()))?;
    let ver = doc
        .get("version")
        .and_then(|v| v.as_u64())
        .ok_or_else(|| VaultError::Format("缺少 version".into()))?;
    if ver != CREDENTIALS_VERSION as u64 {
        return Err(VaultError::Format(format!("不认识的版本号：{ver}")));
    }
    let obj = doc
        .get("entries")
        .and_then(|v| v.as_object())
        .ok_or_else(|| VaultError::Format("缺少 entries".into()))?;
    let mut out = BTreeMap::new();
    for (k, v) in obj {
        let hex = v
            .as_str()
            .ok_or_else(|| VaultError::Format(format!("{k} 的值不是字符串")))?;
        let bytes =
            from_hex(hex).ok_or_else(|| VaultError::Format(format!("{k} 的密文不是合法 hex")))?;
        out.insert(k.clone(), bytes);
    }
    Ok(out)
}

fn render_credentials(entries: &BTreeMap<String, Vec<u8>>) -> String {
    let mut obj = serde_json::Map::new();
    for (k, v) in entries {
        obj.insert(k.clone(), serde_json::Value::String(to_hex(v)));
    }
    let doc = serde_json::json!({ "version": CREDENTIALS_VERSION, "entries": obj });
    serde_json::to_string_pretty(&doc).unwrap_or_else(|_| "{}".to_string())
}

fn to_hex(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push(char::from_digit((b >> 4) as u32, 16).unwrap_or('0'));
        s.push(char::from_digit((b & 0x0f) as u32, 16).unwrap_or('0'));
    }
    s
}

fn from_hex(text: &str) -> Option<Vec<u8>> {
    if !text.len().is_multiple_of(2) {
        return None;
    }
    let mut out = Vec::with_capacity(text.len() / 2);
    let bytes = text.as_bytes();
    for pair in bytes.chunks(2) {
        let hi = (pair[0] as char).to_digit(16)?;
        let lo = (pair[1] as char).to_digit(16)?;
        out.push(((hi << 4) | lo) as u8);
    }
    Some(out)
}

/// 生成一段新的主密钥（32 字节随机）。首次启动时调用一次，写进钥匙文件。
pub fn new_master_secret() -> Result<Vec<u8>, VaultError> {
    let rng = SystemRandom::new();
    let mut secret = vec![0u8; 32];
    rng.fill(&mut secret).map_err(|_| VaultError::Random)?;
    Ok(secret)
}

/// 读主密钥文件；不存在就生成并写入（权限尽力收紧）。
pub fn load_or_create_master_secret(path: &Path) -> Result<Vec<u8>, VaultError> {
    if path.exists() {
        let bytes = std::fs::read(path).map_err(|e| VaultError::Io(e.to_string()))?;
        if bytes.len() < 16 {
            return Err(VaultError::Format(
                "主密钥文件内容太短，可能被截断了".into(),
            ));
        }
        return Ok(bytes);
    }
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).map_err(|e| VaultError::Io(e.to_string()))?;
    }
    let secret = new_master_secret()?;
    std::fs::write(path, &secret).map_err(|e| VaultError::Io(e.to_string()))?;
    tighten_permissions(path)?;
    Ok(secret)
}

#[cfg(unix)]
fn tighten_permissions(path: &Path) -> Result<(), VaultError> {
    use std::os::unix::fs::PermissionsExt;
    let mut perm = std::fs::metadata(path)
        .map_err(|e| VaultError::Io(e.to_string()))?
        .permissions();
    perm.set_mode(0o600);
    std::fs::set_permissions(path, perm).map_err(|e| VaultError::Io(e.to_string()))
}

#[cfg(not(unix))]
fn tighten_permissions(_path: &Path) -> Result<(), VaultError> {
    // Windows 上依赖用户目录本身的 ACL，不再叠一层。要更强的隔离得走系统钥匙串。
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_dir(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("portio_vault_{tag}"));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn seal_then_open_roundtrips() {
        let vault = Vault::from_secret(b"master-secret").unwrap();
        let blob = vault.seal("口令 P@ssw0rd 中文").unwrap();
        assert_eq!(vault.open(&blob).unwrap(), "口令 P@ssw0rd 中文");
        // 明文绝不能以子串形式出现在密文里
        assert!(!blob
            .windows(4)
            .any(|w| w == "口令 P".as_bytes().get(..4).unwrap()));
    }

    #[test]
    fn same_plaintext_stays_same() {
        // nonce 每次不同：同样的口令两次加密的结果必须不一样
        let vault = Vault::from_secret(b"master-secret").unwrap();
        let a = vault.seal("hunter2").unwrap();
        let b = vault.seal("hunter2").unwrap();
        assert_ne!(a, b);
        assert_eq!(vault.open(&a).unwrap(), "hunter2");
        assert_eq!(vault.open(&b).unwrap(), "hunter2");
    }

    #[test]
    fn tampered_ciphertext_is_rejected() {
        let vault = Vault::from_secret(b"master-secret").unwrap();
        let mut blob = vault.seal("hunter2").unwrap();
        let last = blob.len() - 1;
        blob[last] ^= 0x01;
        assert_eq!(vault.open(&blob).unwrap_err(), VaultError::Open);
        // 截断的密文同样解不开
        let short = &vault.seal("hunter2").unwrap()[..NONCE_LEN_USIZE];
        assert_eq!(vault.open(short).unwrap_err(), VaultError::Open);
    }

    #[test]
    fn wrong_master_secret_cannot_open() {
        let a = Vault::from_secret(b"secret-a").unwrap();
        let b = Vault::from_secret(b"secret-b").unwrap();
        let blob = a.seal("hunter2").unwrap();
        assert_eq!(b.open(&blob).unwrap_err(), VaultError::Open);
    }

    #[test]
    fn store_persists_and_forgets() {
        let dir = temp_dir("store");
        let path = dir.join("credentials.json");
        let mut store = CredentialStore::load(&path, b"master").unwrap();
        assert!(store.is_empty());

        store.set_password("sess-1", "pw-1").unwrap();
        store.set_password("sess-2", "pw-2-中文").unwrap();
        assert_eq!(store.len(), 2);

        // 重开同一把密钥能读回来
        let reopened = CredentialStore::load(&path, b"master").unwrap();
        assert_eq!(
            reopened.password("sess-1").unwrap().as_deref(),
            Some("pw-1")
        );
        assert_eq!(
            reopened.password("sess-2").unwrap().as_deref(),
            Some("pw-2-中文")
        );
        assert!(reopened.password("sess-3").unwrap().is_none());

        // 口令不出现在文件明文里
        let raw = std::fs::read_to_string(&path).unwrap();
        assert!(!raw.contains("pw-1"));
        assert!(!raw.contains("pw-2-中文"));

        store.forget("sess-1").unwrap();
        let after = CredentialStore::load(&path, b"master").unwrap();
        assert!(after.password("sess-1").unwrap().is_none());
        assert_eq!(after.len(), 1);

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn empty_password_clears_instead_of_storing_blank() {
        let dir = temp_dir("blank");
        let path = dir.join("credentials.json");
        let mut store = CredentialStore::load(&path, b"master").unwrap();
        store.set_password("sess-1", "pw").unwrap();
        store.set_password("sess-1", "").unwrap();
        assert!(store.password("sess-1").unwrap().is_none());
        assert!(store.is_empty());
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn broken_file_is_reported_not_silently_empty() {
        let dir = temp_dir("broken");
        let path = dir.join("credentials.json");
        std::fs::write(&path, "{ not json").unwrap();
        let err = CredentialStore::load(&path, b"master").unwrap_err();
        assert!(matches!(err, VaultError::Format(_)), "实际：{err:?}");

        // 版本号不认识也要报错，不要拿错口径去解
        std::fs::write(&path, r#"{"version":9,"entries":{}}"#).unwrap();
        let err = CredentialStore::load(&path, b"master").unwrap_err();
        assert!(matches!(err, VaultError::Format(_)), "实际：{err:?}");
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn master_secret_is_created_once_then_reused() {
        let dir = temp_dir("secret");
        let path = dir.join("vault.key");
        let first = load_or_create_master_secret(&path).unwrap();
        assert_eq!(first.len(), 32);
        let second = load_or_create_master_secret(&path).unwrap();
        assert_eq!(first, second);
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
