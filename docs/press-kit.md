# Portio 物料页（中文 / English）

给谁看的：写 README、发 Release、发帖、做介绍页时从这里取文案，**中文一份、英文一份，事实口径统一**。
截图在 [`docs/shots/`](shots/)，规格统一为 1180×690 逻辑尺寸、2 倍像素密度（PNG 2360×1380），深浅各一套。

> 写这一页时遵守一条：不吹没做到的事。凡是标了「未签名」「未在真机装过」「未验证」的地方都不要删——
> 删了短一截好看，但用户装不上时会记得是谁说的。

---

## 一句话（短）

**中文**：Portio · 一个窗口做完 SSH 和文件——左边会话、中间终端、右边远端与本机双栏。

**English**: Portio — SSH and file transfer in one window: sessions on the left, the terminal in the middle,
remote and local files side by side on the right.

## 两句话（长）

**中文**：在服务器上干活时最烦的是来回切窗口：一边 `ssh`，一边另开工具拖文件，路径还得手打。Portio 把这两件事
塞进同一个窗口——命令往下走，文件往上走。名字取 **port + io**：port 是 SSH 端口，也是数据的进出口。

**English**: The annoying part of server work isn't the commands — it's the window switching: one tab for `ssh`,
another tool for dragging files, then typing the path again. Portio puts both in a single window: commands go
down, files go up. The name is **port + io** — an SSH port, and the doorway data passes through.

## 这一版能做什么（事实对照）

| 能力 | 现状 | Status |
| --- | --- | --- |
| SSH 终端、多标签 | 已做，`Ctrl+T` 新开、`Ctrl+W` 关（最后一个不关） | SSH terminal, multiple tabs |
| 分屏（最多四格） | 已做，`Ctrl+Shift+D` 左右、`Ctrl+Shift+E` 上下，每格独立通道 | Split panes, up to 2×2, one channel per pane |
| 终端查找 | 已做，扫整条缓冲区（含滚出屏幕的旧行） | Search across the whole scrollback |
| 复制粘贴 | 按老习惯：`Ctrl+Shift+C` / `Ctrl+Insert` 复制，`Ctrl+V` 粘贴；`Ctrl+C` 有选中才复制，否则发中断 | Copy/paste follows muscle memory; `Ctrl+C` only copies when something is selected |
| 双栏文件 + 拖拽上传 | 已做，双击进出目录，`F5` 刷新两侧 | Dual-pane files, drag to upload, `F5` refreshes both sides |
| 断点续传 | 已做，半截文件写 `原名.portio-part`，传完改名 | Resumable transfers via a `.portio-part` partial file |
| 传输队列 | 已做，逐块进度，能收成一行 | Transfer queue with per-chunk progress, collapses to one row |
| 会话管理 | 已做，双击就连；分组、搜索、重命名；存本地 `sessions.json` | Saved sessions, groups, search, rename; stored locally |
| 导入旧配置 | 已做，从 `~/.ssh/config`、Xshell、WinSCP 导入 | Import from `~/.ssh/config`, Xshell, WinSCP |
| 主机指纹 | 已做，首次连接记录指纹，变了就拦下 | Host key pinning on first connect; changed keys are blocked |
| 主题与强调色 | 已做，深浅两套（还能「跟随系统」）；强调色六套预置：青 / 蓝 / 紫 / 琥珀 / 玫瑰 / 青柠 | Light/dark (+ follow system); six accent presets |
| 终端配色 | 已做四档：跟界面 / Dracula / Solarized / Nord（成套换底与八色，光标仍跟主色） | Four terminal colorways, decoupled from the UI theme |
| 字号 / 字体 / 密度 | 已做：界面字号两档、终端字号 9–24、等宽字体四选（自动 / JetBrains / Cascadia / Consolas）、密度 24 / 28 / 32 三档；两套字号互不带动 | UI font scale, terminal 9–24, four mono fonts, three density steps; the two scales move independently |
| 启动时与布局 | 已做：会话栏与文件面板各自的启动显隐三档；远端权限列可隐藏（68px 全还给文件名）；开局单屏或 2×2；面板宽度「记住上次 / 用默认」两层、默认宽度三档 | Boot-time panel visibility, optional permission column, start-with-one-pane-or-four, remembered vs default widths |
| 口令本地加密 | 已做：密文写 `credentials.json`，主密钥 `vault.key` 留在应用数据目录；挡的是明文被同步盘 / 打包 / 日志带走，**不是本地提权**；系统钥匙串还没接 | Passwords encrypted at rest with a machine-local master key (not a keychain); protects against plaintext leaking into sync folders or logs |
| 真实服务器端到端 | **未验证**（没有可连的测试机，只有协议层与本地回环测试） | End-to-end against a real server: **not verified** |
| 代码签名 | **未签名**（Windows SmartScreen 会拦，macOS 需右键打开） | **Unsigned**: SmartScreen warns, macOS needs right-click |

## 截图与说明（Ten shots：五个场景 × 深浅两套）

`docs/shots/` 下十张，命名 `portio-<dark|light>-<scene>.png`。图里的会话、已知主机与传输队列是演示数据；
文件双栏显示「连上主机后显示远端目录」是因为无头浏览器里没有后端——**这是如实的一张图，没有 P 图补内容**。
设置面板从「自定义」做进来之后长到十六项，一屏放不下，所以拆成顶部（自定义）与滚到底（已知主机）两张。

| 场景 | 文件 | 中文说明 | English caption |
| --- | --- | --- | --- |
| 主界面 | `portio-*-main.png` | 左会话、中终端、右远端与本机双栏，底部传输队列三条 | Sessions left, terminal center, files right, transfer queue below |
| 2×2 分屏 | `portio-*-split.png` | 四格各自独立，光标所在格有描边 | Four panes, each with its own channel |
| 导入下拉 | `portio-*-import.png` | 一个入口，三个来源：`~/.ssh/config`、Xshell、WinSCP | One menu, three sources: ssh config, Xshell, WinSCP |
| 设置 · 自定义 | `portio-*-settings.png` | 主题、强调色、字号、密度、终端配色、字体、启动时、布局 | Theme, accent, type scale, density, terminal colorway, mono font, boot layout |
| 设置 · 已知主机 | `portio-*-hosts.png` | 已知主机指纹表（可单条删除）与运行日志 | Pinned host keys (deletable) and the local log |

出图脚本：`python scripts/shots.py`（先查 `<title>` 有没有 `ERR:`，再校验 2360×1380，任一门不过即 FAIL）。

## 现在可以下载什么（截至 `v1.0.8-RC1`）

最新一批包是 `v1.0.8-RC1`（预发布，从 [Releases](https://github.com/yunyu697/portio/releases) 下）。
1.0.6 的 RC1–RC3 只动过物料、文档与脚本，没单独出包；RC4 修了分屏下的查找 Bug、
RC5 修了「新建连接」带着上一台机器端口与私钥路径的问题、RC6 修了重开之后「最近使用」分组消失的问题、
RC7 修了「主机密钥变了」那句处理提示没送达界面的问题、RC8 修了并发写日志会丢行的问题、
RC9 修了「复制诊断信息」碰到坏字节会把整段日志读成空的问题、RC10 修了「定位日志文件」
在用户目录含空格的机器上按了没反应的问题、1.0.7-RC1 修了日志刚轮转那一下「看日志」读到空的问题，
这些版本各有自己的包；1.0.7-RC2 起开始做自定义，RC3 加了终端配色四档，RC4 把字号 / 字体 / 密度拆开调，RC5 又能定两块面板的启动显隐，RC6 还能把远端权限列藏掉换名字宽度，RC7 又能定开局摆几格终端，RC8 再把面板宽度分成「记住上次 / 用默认」两层（默认宽度三档）；1.0.7-RC9 修了传输队列的两处状态 Bug（空态那句「空…」不再赖着不走、标题条计数从开始那一刻就跟着实际行数），并重出了首发十张图，RC9 是最新的一批。

| 平台 | 产物 | 状态 |
| --- | --- | --- |
| Windows x64 | `Portio_1.0.8-RC1_x64-setup.exe`（NSIS，待发布后回填字节数） | 能装、能跑；未签名 |
| macOS（Apple Silicon + Intel） | `Portio_1.0.8-RC1_universal.dmg`（待发布后回填字节数） | CI 构建通过，**未在真机装过**；未签名 |
| Linux x64 | `Portio_1.0.8-RC1_amd64.deb` / `Portio_1.0.8-RC1_amd64.AppImage`（待发布后回填字节数） | CI 构建通过，**未在真机装过** |

规则：**RC 及以后发包，Alpha 只打 tag**。tag 必须等于仓库里的版本号，对不上就不进打包流程。

## 不要这么说（红线）

- 不要说「支持 macOS / Linux」而不带「未在真机验证」——现在只到「CI 能构建」。
- 不要说「安全审计过」「开源可审计，欢迎审计」——仓库公开但**还没有 LICENSE**，许可证选型未定。
- 不要说「有自动更新」「有崩溃上报」——这两件都还没做，等端点与方案。
- 不要把演示截图说成「连上服务器后的样子」。

---

## English（for a README / store listing）

**Portio** — SSH and SFTP in one window. Sessions on the left, terminal in the middle, remote and local
files on the right. Commands go down, files go up; no second app, no retyping paths.

- **Terminal**: tabs, 2×2 split panes (each pane gets its own channel), search across the full scrollback,
  copy/paste that follows muscle memory.
- **Files**: dual pane, drag to upload, resumable transfers (`name.portio-part` until finished),
  a queue with per-chunk progress that collapses to a single row.
- **Sessions**: saved locally, groups, search, rename; import from `~/.ssh/config`, Xshell, WinSCP.
- **Security**: host keys pinned on first connect and blocked when they change; passwords encrypted at rest
  with a machine-local master key (protects against plaintext ending up in sync folders, backups or logs —
  not against a local attacker with your account; OS keychain integration is still on the list).
- **Honest bits**: builds are **unsigned** (SmartScreen and Gatekeeper will warn), macOS and Linux packages
  are CI-built but not yet installed on real hardware, and end-to-end SSH/SFTP against a live server is
  still unverified.

Built with Tauri 2 + Rust + xterm.js. Windows first, macOS in the same release, Linux next.
