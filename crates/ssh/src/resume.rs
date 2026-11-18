//! 断点续传的纯逻辑：临时文件名怎么起、从哪个字节接着传。
//!
//! 这些判断不需要连服务器，所以单独抽出来做单元测试——传输主流程只负责按结论去 seek。

use std::path::{Path, PathBuf};

/// 半截文件的临时名：在原名后面接 `.portio-part`。
///
/// 不用 `with_extension`：`a.tar.gz` 会被改成 `a.tar.portio-part`，扩展名丢了，
/// 用户看到临时文件也认不出是哪个。
pub fn part_path(local: &Path) -> PathBuf {
    let name = local
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_else(|| "download".to_string());
    let dir = local.parent().unwrap_or(Path::new("."));
    dir.join(format!("{name}.portio-part"))
}

/// 本次从哪个偏移开始写；返回 0 表示从头重来。
///
/// 只有一种情况能续：临时文件比远端小。临时文件已经和远端一样大（甚至更大），
/// 说明上次其实传完了但没改名，或者远端文件变小了——两种情况都不能续，续下去就是回环脏数据。
pub fn resume_offset(part_len: u64, remote_size: u64) -> u64 {
    if part_len == 0 || remote_size == 0 || part_len >= remote_size {
        0
    } else {
        part_len
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn part_path_keeps_full_name() {
        assert_eq!(
            part_path(Path::new("/tmp/a.tar.gz")),
            PathBuf::from("/tmp/a.tar.gz.portio-part")
        );
        assert_eq!(
            part_path(Path::new("C:\\下载\\报表#2026")),
            PathBuf::from("C:\\下载\\报表#2026.portio-part")
        );
        // 没有父目录时落在当前目录
        assert_eq!(part_path(Path::new("x.bin")), PathBuf::from("x.bin.portio-part"));
    }

    #[test]
    fn resume_only_when_part_is_smaller() {
        assert_eq!(resume_offset(0, 100), 0, "没有半截文件就从头传");
        assert_eq!(resume_offset(40, 100), 40, "半截文件更小就接着传");
        assert_eq!(resume_offset(100, 100), 0, "正好传满不能再续，否则会卡在 0 字节");
        assert_eq!(resume_offset(120, 100), 0, "比远端还大说明远端变小了，重来");
        assert_eq!(resume_offset(40, 0), 0, "远端大小未知时不敢续");
    }

    /// 回环验证：把半截文件补完，得到的字节必须和源文件一致。
    #[test]
    fn appending_rest_rebuilds_whole_file() {
        let dir = std::env::temp_dir().join("portio_resume_单元");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let src: Vec<u8> = (0u32..300).map(|i| (i % 251) as u8).collect();
        let local = dir.join("备份.tar.gz");
        let part = part_path(&local);
        std::fs::write(&part, &src[..120]).unwrap();

        let start = resume_offset(std::fs::metadata(&part).unwrap().len(), src.len() as u64);
        assert_eq!(start, 120);

        use std::io::Write;
        let mut out = std::fs::OpenOptions::new().append(true).open(&part).unwrap();
        out.write_all(&src[120..]).unwrap();
        out.flush().unwrap();
        drop(out);

        std::fs::rename(&part, &local).unwrap();
        assert_eq!(std::fs::read(&local).unwrap(), src);

        std::fs::remove_dir_all(&dir).unwrap();
    }
}
