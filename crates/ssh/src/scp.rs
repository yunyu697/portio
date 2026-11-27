//! SCP 回退通道。
//!
//! 背景：很多精简系统（OpenWrt 的 dropbear、路由器/嵌入式设备）没有 sftp-server，
//! SFTP 子系统根本起不来；但它们都带 `scp`。WinSCP 在这类主机上能连、能传文件，
//! 就是因为它退到了 SCP。这里补上同一条退路：目录列举走 `ls -la`，上传/下载走
//! 远端 `scp -t` / `scp -f` 的经典协议（RFC 之外的老协议，实现见下）。
//!
//! 设计取舍：SCP 没有真正的元数据接口，列目录靠解析 `ls -la`，所以文件名里带
//! 换行的极端情况会丢；能拿到权限位、大小、时间就先够用，SDK 里也不做假装精确。

use std::path::Path;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use russh::client::Msg;
use russh::{Channel, ChannelMsg};

use crate::sftp::RemoteEntry;
use crate::{SshError, SshSession};

const EXEC_TIMEOUT: Duration = Duration::from_secs(30);

/// 单引号包裹，供远端 shell 使用。
fn sq(s: &str) -> String {
    format!("'{}'", s.replace('\'', "'\\''"))
}

impl SshSession {
    /// 跑一条命令并收齐 stdout/stderr/退出码。SCP 的一切都建在这上面。
    pub async fn exec_collect(&self, command: &str) -> Result<(String, String, u32), SshError> {
        let mut channel = self
            .handle
            .channel_open_session()
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;
        channel
            .exec(true, command.as_bytes().to_vec())
            .await
            .map_err(|e| {
                SshError::Protocol(format!("远端拒绝执行命令（{command}）：{e}"))
            })?;

        let mut out = Vec::new();
        let mut err = Vec::new();
        let mut code = 0u32;
        let deadline = tokio::time::Instant::now() + EXEC_TIMEOUT;
        loop {
            let left = deadline.saturating_duration_since(tokio::time::Instant::now());
            if left.is_zero() {
                return Err(SshError::Protocol(format!("命令超时（{command}）")));
            }
            match tokio::time::timeout(left, channel.wait()).await {
                Ok(Some(ChannelMsg::Data { data })) => out.extend_from_slice(&data),
                Ok(Some(ChannelMsg::ExtendedData { data, .. })) => err.extend_from_slice(&data),
                Ok(Some(ChannelMsg::ExitStatus { exit_status })) => code = exit_status,
                Ok(Some(ChannelMsg::Eof)) | Ok(Some(ChannelMsg::Close)) | Ok(None) => break,
                Ok(Some(_)) => {}
                Err(_) => return Err(SshError::Protocol(format!("命令超时（{command}）"))),
            }
        }
        Ok((
            String::from_utf8_lossy(&out).to_string(),
            String::from_utf8_lossy(&err).to_string(),
            code,
        ))
    }

    /// 登录后的落脚目录。SCP 没有 canonicalize，只能问远端。
    pub async fn scp_home(&self) -> Result<String, SshError> {
        let (out, err, code) = self
            .exec_collect("pwd 2>/dev/null || echo \"$HOME\"")
            .await?;
        let path = out.lines().next().unwrap_or("").trim();
        if path.is_empty() {
            return Err(SshError::Protocol(format!(
                "取远端当前目录失败：{}",
                err.trim()
            )));
        }
        let _ = code;
        Ok(path.to_string())
    }

    /// 列目录：`ls -la` 解析。目录在前、同名按字典序，和 SFTP 那套排序一致。
    pub async fn scp_list(&self, path: &str) -> Result<Vec<RemoteEntry>, SshError> {
        let cmd = format!("ls -la {}", sq(path));
        let (out, err, code) = self.exec_collect(&cmd).await?;
        if code != 0 && out.trim().is_empty() {
            return Err(SshError::Protocol(format!(
                "列远端目录失败：{}",
                err.trim()
            )));
        }
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0);
        let mut items = Vec::new();
        for line in out.lines() {
            if let Some(e) = parse_ls_line(line, path, now) {
                items.push(e);
            }
        }
        items.sort_by(|a, b| {
            b.is_dir
                .cmp(&a.is_dir)
                .then_with(|| a.name.to_lowercase().cmp(&b.name.to_lowercase()))
        });
        Ok(items)
    }

    /// 远端 → 本地。走 `scp -f`：对端发 `C<mode> <size> <name>` 控制行，收到后回 ACK 再收数据。
    pub async fn scp_download(
        &self,
        remote: &str,
        local: &Path,
        progress: &mut (dyn FnMut(u64, u64) + Send),
    ) -> Result<u64, SshError> {
        let channel = self
            .handle
            .channel_open_session()
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;
        channel
            .exec(true, format!("scp -f {}", sq(remote)).into_bytes())
            .await
            .map_err(|e| SshError::Protocol(format!("远端拒绝 scp -f：{e}")))?;
        let mut s = Stream::new(channel);
        s.send(b"\x00").await?;

        if let Some(parent) = local.parent() {
            std::fs::create_dir_all(parent).map_err(|e| SshError::Protocol(e.to_string()))?;
        }
        let tmp = crate::resume::part_path(local);
        let mut file = tokio::fs::File::create(&tmp)
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;

        let mut done = 0u64;
        loop {
            match s.next_control().await? {
                Control::File { size, .. } => {
                    s.send(b"\x00").await?;
                    let mut remaining = size;
                    let mut total_check = 0u64;
                    while remaining > 0 {
                        let n = s.take_bytes(&mut file, remaining).await?;
                        if n == 0 {
                            return Err(SshError::Protocol("对端提前结束传输".into()));
                        }
                        remaining -= n;
                        total_check += n;
                        done += n;
                        progress(done, done);
                    }
                    s.send(b"\x00").await?;
                    let _ = total_check;
                }
                Control::End => break,
                Control::Time => s.send(b"\x00").await?,
                Control::Ack => {},
                Control::Error(msg) => return Err(SshError::Protocol(msg)),
            }
        }
        // 收尾：对端最后还会发一次确认，读不到也不致命
        let _ = s.next_control().await;
        tokio::io::AsyncWriteExt::flush(&mut file)
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;
        drop(file);
        tokio::fs::rename(&tmp, local)
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;
        Ok(done)
    }

    /// 本地 → 远端。走 `scp -t`：先等对端就绪，再发 C 头 + 数据 + 结束确认。
    pub async fn scp_upload(
        &self,
        local: &Path,
        remote: &str,
        progress: &mut (dyn FnMut(u64, u64) + Send),
    ) -> Result<u64, SshError> {
        let name = Path::new(remote)
            .file_name()
            .and_then(|n| n.to_str())
            .ok_or_else(|| SshError::Protocol(format!("远端路径不合法：{remote}")))?;
        let meta = std::fs::metadata(local).map_err(|e| SshError::Protocol(e.to_string()))?;
        let total = meta.len();

        let channel = self
            .handle
            .channel_open_session()
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;
        channel
            .exec(true, format!("scp -t {}", sq(remote)).into_bytes())
            .await
            .map_err(|e| SshError::Protocol(format!("远端拒绝 scp -t：{e}")))?;
        let mut s = Stream::new(channel);
        match s.next_control().await? {
            Control::Ack => {}
            Control::Error(msg) => return Err(SshError::Protocol(msg)),
            _ => return Err(SshError::Protocol("scp -t 未就绪".into())),
        }

        s.send(format!("C0644 {total} {name}\n").as_bytes()).await?;
        match s.next_control().await? {
            Control::Ack => {}
            Control::Error(msg) => return Err(SshError::Protocol(msg)),
            _ => return Err(SshError::Protocol("对端未接受文件头".into())),
        }

        let mut file = tokio::fs::File::open(local)
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;
        let mut buf = vec![0u8; 32 * 1024];
        let mut done = 0u64;
        progress(0, total);
        loop {
            let n = tokio::io::AsyncReadExt::read(&mut file, &mut buf)
                .await
                .map_err(|e| SshError::Protocol(e.to_string()))?;
            if n == 0 {
                break;
            }
            s.send(&buf[..n]).await?;
            done += n as u64;
            progress(done, total);
        }
        drop(file);
        s.send(b"\x00").await?;
        match s.next_control().await? {
            Control::Ack => {}
            Control::Error(msg) => return Err(SshError::Protocol(msg)),
            _ => {}
        }
        Ok(done)
    }

    pub async fn scp_mkdir(&self, path: &str) -> Result<(), SshError> {
        self.run_or_fail(format!("mkdir -p {}", sq(path)), "建目录").await
    }

    pub async fn scp_remove(&self, path: &str, is_dir: bool) -> Result<(), SshError> {
        let cmd = if is_dir {
            format!("rm -rf {}", sq(path))
        } else {
            format!("rm -f {}", sq(path))
        };
        self.run_or_fail(cmd, "删除").await
    }

    pub async fn scp_rename(&self, from: &str, to: &str) -> Result<(), SshError> {
        self.run_or_fail(format!("mv {}", sq(from)) + " " + sq(to).as_str(), "重命名")
            .await
    }

    async fn run_or_fail(&self, cmd: String, what: &str) -> Result<(), SshError> {
        let (_, err, code) = self.exec_collect(&cmd).await?;
        if code != 0 {
            return Err(SshError::Protocol(format!(
                "{what}失败（退出码 {code}）：{}",
                err.trim()
            )));
        }
        Ok(())
    }
}

/// `ls -la` 的一行 → 目录项。解析不了的行（如 total 行）返回 None。
fn parse_ls_line(line: &str, dir: &str, now: i64) -> Option<RemoteEntry> {
    let t: Vec<&str> = line.split_whitespace().collect();
    if t.len() < 8 {
        return None;
    }
    let perm = t[0];
    if !perm.starts_with('-') && !perm.starts_with('d') && !perm.starts_with('l') {
        return None;
    }
    let is_dir = perm.starts_with('d');
    let size: u64 = t[4].parse().ok()?;
    // 时间：月份 日 时刻/年份 之后全都是文件名（名字里可以有空格）
    let month = t[5];
    let day: i64 = t[6].parse().ok()?;
    let stamp = t[7];
    let name_start = line.find(t[7])? + t[7].len();
    let name = line[name_start..].trim_start();
    if name == "." || name == ".." || name.is_empty() {
        return None;
    }
    let name = match name.split_once(" -> ") {
        Some((n, _)) => n.trim_end().to_string(),
        None => name.to_string(),
    };
    let modified = match stamp.split_once(':') {
        // `21:45` → 今年；和 ls 一样的规则：比现在晚半年以上，就算去年
        Some((hh, mm)) => {
            let hh: i64 = hh.parse().ok()?;
            let mm: i64 = mm.parse().ok()?;
            let year = current_year(now);
            let mut ts = epoch(year, month, day, hh, mm);
            if ts > now + 15_778_476 {
                ts = epoch(year - 1, month, day, hh, mm);
            }
            ts
        }
        // `2025` → 当年 1 月 1 日
        None => {
            let year: i64 = stamp.parse().ok()?;
            epoch(year, month, day, 0, 0)
        }
    };
    let mode = mode_bits(perm);
    Some(RemoteEntry {
        name: name.clone(),
        path: crate::sftp::join(dir, &name),
        is_dir,
        size,
        modified,
        perm: Some(mode),
    })
}

fn current_year(now: i64) -> i64 {
    let (y, _, _) = civil_from_days((now / 86_400) as i32);
    y as i64
}

fn mode_bits(perm: &str) -> u32 {
    let chars: Vec<char> = perm.chars().skip(1).take(9).collect();
    let mut digit = [0u32; 3];
    for (i, c) in chars.iter().enumerate() {
        let bit = match c {
            'r' => 4,
            'w' => 2,
            'x' | 't' | 's' => 1,
            _ => 0,
        };
        digit[i / 3] |= bit;
    }
    (digit[0] << 6) | (digit[1] << 3) | digit[2]
}

fn month_index(m: &str) -> Option<i64> {
    const M: [&str; 12] = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ];
    M.iter().position(|x| *x == m).map(|i| i as i64)
}

fn epoch(year: i64, month: &str, day: i64, hh: i64, mm: i64) -> i64 {
    let Some(m) = month_index(month) else {
        return 0;
    };
    let days = days_from_civil(year as i32, (m + 1) as u32, day.max(1) as u32) as i64;
    days * 86_400 + hh * 3600 + mm * 60
}

/// Howard Hinnant 的 days_from_civil。
fn days_from_civil(y: i32, m: u32, d: u32) -> i32 {
    let y = if m <= 2 { y - 1 } else { y };
    let era = if y >= 0 { y } else { y - 399 } / 400;
    let yoe = (y - era * 400) as u32;
    let mp = if m > 2 { m - 3 } else { m + 9 };
    let doy = (153 * mp + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146_097 + doe as i32 - 719_468
}

fn civil_from_days(z: i32) -> (i32, u32, u32) {
    let z = z + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = (z - era * 146_097) as u32;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe as i32 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    (if m <= 2 { y + 1 } else { y }, m, d)
}

/// SCP 控制流里我们真正需要区分的几种消息。
enum Control {
    Ack,
    Time,
    File { size: u64 },
    End,
    Error(String),
}

/// 一条 exec 通道上的字节流：按行/按字节取，转发超时和错误。
struct Stream {
    channel: Channel<Msg>,
    buf: Vec<u8>,
    closed: bool,
}

impl Stream {
    fn new(channel: Channel<Msg>) -> Self {
        Self {
            channel,
            buf: Vec::new(),
            closed: false,
        }
    }

    async fn send(&self, bytes: &[u8]) -> Result<(), SshError> {
        self.channel
            .data(bytes)
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))
    }

    async fn fill(&mut self) -> Result<(), SshError> {
        loop {
            if self.closed {
                return Ok(());
            }
            match tokio::time::timeout(Duration::from_secs(30), self.channel.wait()).await {
                Ok(Some(ChannelMsg::Data { data })) => {
                    self.buf.extend_from_slice(&data);
                    return Ok(());
                }
                Ok(Some(ChannelMsg::ExtendedData { data, .. })) => {
                    return Err(SshError::Protocol(
                        String::from_utf8_lossy(&data).trim().to_string(),
                    ))
                }
                Ok(Some(ChannelMsg::ExitStatus { exit_status })) if exit_status != 0 => {
                    return Err(SshError::Protocol(format!("远端 scp 退出码 {exit_status}")));
                }
                Ok(Some(ChannelMsg::Eof)) | Ok(Some(ChannelMsg::Close)) | Ok(None) => {
                    self.closed = true;
                    return Ok(());
                }
                Ok(Some(_)) => continue,
                Err(_) => return Err(SshError::Protocol("SCP 通道等待超时".into())),
            }
        }
    }

    /// 取下一个控制字节/控制行，翻译成 Control。
    async fn next_control(&mut self) -> Result<Control, SshError> {
        while self.buf.is_empty() {
            if self.closed {
                return Ok(Control::End);
            }
            self.fill().await?;
        }
        let first = self.buf[0];
        match first {
            0u8 => {
                self.buf.remove(0);
                Ok(Control::Ack)
            }
            b'C' | b'D' => {
                let line = self.read_line().await?;
                let mut parts = line.split_whitespace();
                let mode = parts.next().unwrap_or("");
                let size: u64 = parts.next().and_then(|s| s.parse().ok()).unwrap_or(0);
                let _ = mode;
                Ok(Control::File { size })
            }
            b'T' => {
                let _ = self.read_line().await?;
                Ok(Control::Time)
            }
            b'E' => {
                let _ = self.read_line().await?;
                Ok(Control::End)
            }
            1u8 | 2u8 => {
                self.buf.remove(0);
                let line = self.read_line().await?;
                Ok(Control::Error(line.trim().to_string()))
            }
            other => Err(SshError::Protocol(format!(
                "SCP 协议出现意外字节 {other}"
            ))),
        }
    }

    async fn read_line(&mut self) -> Result<String, SshError> {
        loop {
            if let Some(pos) = self.buf.iter().position(|b| *b == b'\n') {
                let line: String = String::from_utf8_lossy(&self.buf[..pos]).to_string();
                self.buf.drain(..=pos);
                return Ok(line);
            }
            if self.closed {
                let rest = String::from_utf8_lossy(&self.buf).to_string();
                self.buf.clear();
                return Ok(rest);
            }
            self.fill().await?;
        }
    }

    /// 把剩余数据写进文件，最多 `max` 字节。
    async fn take_bytes(
        &mut self,
        file: &mut tokio::fs::File,
        max: u64,
    ) -> Result<u64, SshError> {
        while self.buf.is_empty() {
            if self.closed {
                return Ok(0);
            }
            self.fill().await?;
        }
        let n = (self.buf.len() as u64).min(max) as usize;
        let chunk: Vec<u8> = self.buf.drain(..n).collect();
        tokio::io::AsyncWriteExt::write_all(file, &chunk)
            .await
            .map_err(|e| SshError::Protocol(e.to_string()))?;
        Ok(n as u64)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ls_line_parses_regular_file_with_time() {
        let line = "-rw-r--r--    1 root     root          1234 Oct 17 21:45 config.txt";
        let e = parse_ls_line(line, "/etc", 1_700_000_000).expect("应能解析");
        assert_eq!(e.name, "config.txt");
        assert_eq!(e.size, 1234);
        assert!(!e.is_dir);
        assert_eq!(e.path, "/etc/config.txt");
        assert_eq!(e.perm.map(|p| p & 0o777), Some(0o644));
        assert!(e.modified > 1_600_000_000);
    }

    #[test]
    fn ls_line_parses_dir_with_year_and_space_in_name() {
        let line = "drwxr-xr-x    2 root     root          4096 Jan  1  2024 my folder name";
        let e = parse_ls_line(line, "/", 1_700_000_000).expect("应能解析");
        assert!(e.is_dir);
        assert_eq!(e.name, "my folder name");
        assert_eq!(e.path, "/my folder name");
        assert_eq!(e.perm.map(|p| p & 0o777), Some(0o755));
    }

    #[test]
    fn ls_line_skips_total_and_dot_entries() {
        assert!(parse_ls_line("total 12", "/", 0).is_none());
        let dot = "drwxr-xr-x    2 root     root          4096 Oct 17 21:45 .";
        assert!(parse_ls_line(dot, "/", 0).is_none());
    }

    #[test]
    fn symlink_name_loses_the_target() {
        let line = "lrwxrwxrwx    1 root     root            18 Oct 17 21:45 scp -> /usr/sbin/dropbear";
        let e = parse_ls_line(line, "/usr/bin", 1_700_000_000).expect("应能解析");
        assert_eq!(e.name, "scp");
        assert!(!e.is_dir);
    }

    #[test]
    fn epoch_matches_known_dates() {
        assert_eq!(epoch(1970, "Jan", 1, 0, 0), 0);
        // 2024-01-01 00:00 UTC
        assert_eq!(epoch(2024, "Jan", 1, 0, 0), 1_704_067_200);
    }

    #[test]
    fn shell_quoting_survives_single_quotes() {
        assert_eq!(sq("/tmp/a b"), "'/tmp/a b'");
        assert_eq!(sq("it's"), "'it'\\''s'");
    }
}
