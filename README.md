# Portio

[![CI](https://github.com/yunyu697/portio/actions/workflows/ci.yml/badge.svg)](https://github.com/yunyu697/portio/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/yunyu697/portio?include_prereleases&label=release)](https://github.com/yunyu697/portio/releases)

跨平台的 SSH 终端 + SFTP 文件管理，一个窗口里干完两件事。

> 名字取 **port + io**：port 是 SSH 端口，也是数据的进出口——命令往下走，文件往上走。

> 完整使用说明在 [`docs/site/index.html`](docs/site/index.html)（一页、离线、不用联网就能打开）。
> 下面这份是速览；两处不一致时以那一页为准。
> 发版文案在 [`docs/release-notes.md`](docs/release-notes.md)，整段可贴到 Release。
> 对外介绍（中文 / English 两份）与截图在 [`docs/press-kit.md`](docs/press-kit.md)。

## 下载

三平台的包都挂在 [Releases](https://github.com/yunyu697/portio/releases) 上，按系统取一个：

| 系统 | 文件 | 说明 |
|---|---|---|
| Windows x64 | `Portio_<版本>_x64-setup.exe` | NSIS 安装包，装给当前用户，需要 WebView2 |
| macOS（Apple Silicon / Intel 通用） | `Portio_<版本>_universal.dmg` | 一个 dmg 两种芯片都能装 |
| Linux x64 | `Portio_<版本>_amd64.deb` / `_amd64.AppImage` | Debian/Ubuntu 用 deb，其它发行版用 AppImage |

**发版节奏**：`Alpha` 阶段只打 tag，不产出安装包；**从 RC 起才发包**（RC 挂在预发布里，正式版才进 Latest）。
所有包**目前都没有代码签名**：Windows 会弹 SmartScreen 提示，macOS 首次打开要按住 Control 点图标选「打开」。


## 这是什么

左边是会话清单，中间是终端，右边是远端 / 本地两栏文件。连上主机后终端能直接敲，
文件栏能看能传——不用在 `ssh` 和另外的 SFTP 客户端之间来回切。

- **终端**：xterm.js 渲染，russh 走协议；PTY 尺寸跟着窗口走
- **文件**：SFTP 双栏，目录与文件双击即进出，拖拽上传
- **会话**：写进本机清单，一次填好下次双击就连
- **迁移**：能把 `~/.ssh/config`、Xshell 的 `.xsh`、WinSCP 的 `WinSCP.ini` 里的主机一次带进来
- **外观**：深色 / 浅色 / 跟系统三态，密度与字号可调

## 安装（Windows）

拿到的文件名形如 `Portio_<版本>_x64-setup.exe`，双击装完即可，桌面和开始菜单都有快捷方式。
首次运行需要系统装有 **WebView2 Runtime**（Win11 自带；Win10 若缺，安装包会引导安装）。

## 怎么连一台机器

三种入口，随便挑一种顺手的：

1. **新建连接**——点会话栏顶上的绿色按钮，填主机 / 端口 / 用户名，密码或私钥二选一。
2. **快速连接**——会话栏那行 `user@host:port`，写完按回车（或点右侧 ↵）直接跳到连接面板，
   地址填好了，只剩密码。同一台机器以前连过的话，端口和认证方式会按上次的记录带出来。
3. **双击会话**——列表里双击密钥认证的主机会直接重连；密码类会停在密码框等你输入。

> 密码**不保存**，用完即弃。清单里只存"怎么连"：主机、端口、用户、认证方式、私钥路径。

### 主机指纹

首次连接会把服务器指纹记进 `known_hosts`；以后再连时若指纹变了，Portio 会**直接停手**
并打印新旧指纹，让你自己判断是不是服务器重装过。这条不会为了让连接"跑通"而放松。

## 从别的工具搬过来

会话栏那颗「导入会话」下拉里三项：

| 菜单项 | 读哪里 | 说明 |
|---|---|---|
| 导入 `~/.ssh/config` | `%USERPROFILE%\.ssh\config` | 通配符块与 `Match` 块会跳过并计数；`IdentityFile` 记为密钥认证 |
| 导入 Xshell 会话 | `%APPDATA%\NetSarang\Xshell\Sessions` | 递归收子目录，一个 `.xsh` 一台主机；RDP / Serial 跳过 |
| 导入 WinSCP 站点 | `%APPDATA%\WinSCP.ini` → `%LOCALAPPDATA%\WinSCP.ini` → `文档\WinSCP.ini` | 取第一份存在的；FTP / WebDAV / S3 跳过，只收 SSH 系列站点 |

导入是**合并**：同端点只留一条，重复的不覆盖你改过的备注名。三个来源的密码字段都不读
（Xshell 与 WinSCP 的密码是各自加密的，读了也用不上）。

## 会话分组

会话行右键 →「分到分组…」，填个组名（比如 `生产` / `测试`），列表就按组收拢。
分组标题点一下能折叠，折叠时只留标题和条数；组标题右键还能「解散这个分组」。
没有分组的会话落在「未分组」里；一条分组都没有时，列表仍按「最近使用 / 更早」排。

右键菜单在其它模块也有一份：终端里能复制/粘贴/清屏、标签上能重命名/关闭、
文件行能下载/上传/删除/重命名。要什么都在右键里找。

## 界面设定

右上角三个图标：主题（深色 / 浅色 / 跟系统）、快捷键一览、设置。

设置里能调**界面密度**（标准 / 紧凑）、**终端字号**（11–18）、**终端滚动缓冲**（2000 / 8000 / 20000 行）。
全都记在本地，下次打开还是你调的样子。

## 快捷键

| 键 | 作用 |
|---|---|
| `Ctrl` + `T` | 新建连接 |
| `Ctrl` + `W` | 关闭当前标签 |
| `Ctrl` + `/` | 打开快捷键一览（`Esc` 关闭） |
| `Ctrl` + `Alt` + `B` | 收起 / 展开左侧会话栏 |
| `Ctrl` + `Alt` + `F` | 收起 / 展开右侧文件面板 |
| `Ctrl` + `Shift` + `D` / `E` | 左右 / 上下分一格 |
| `Ctrl` + `F` | 终端里查找 |
| `F5` | 刷新终端显示与尺寸 |
| `Ctrl` + `Shift` + `C` / `Ctrl` + `Insert` | 复制选中（`Ctrl` + `C` 有选中才复制，否则照发 `^C`） |
| `Ctrl` + `V` / `Shift` + `Insert` | 粘贴 |

## 当前进度

按既定排期走的是四版节奏：

| 版本 | 范围 |
|---|---|
| v0.1 能连能敲 | 外壳、SSH、终端、会话树 |
| v0.2 会话管理与迁移（首个公开版） | 会话 CRUD、分组、Xshell / WinSCP 导入、快速连接、设置项 |
| v0.3 文件双栏 | SFTP、传输队列、断点续传 |
| v0.4 打磨发布 | 主题全量、签名、自动更新、文档站 |

版本号形如 `v1.0.6-RC1`：`Alpha` 阶段每完成一个交付单元进一位、满 10 进 patch 回 `Alpha1`；
进 RC 后功能冻结、只修 Bug，进位规则不变（满 10 进 patch 回 `RC1`）；不带后缀就是正式版。
当前在 **v1.0.6-RC1**，三平台最新安装包仍是 `v1.0.5-RC8`（RC9 / RC10 只改物料与文档，没有重新打包）。
逐版更新内容见 [CHANGELOG.md](CHANGELOG.md)，使用说明见 [`docs/site/index.html`](docs/site/index.html)。

## 开发

```bash
# 前置：Rust stable（MSVC 工具链）、Node 22 LTS、WebView2 Runtime、NSIS
npm install                     # @tauri-apps/cli
npm run dev                     # 开发模式起窗口
cargo test --workspace
node --check ui/app.js          # 前端语法门禁
python scripts/check_design_tokens.py   # 界面不许出现硬编码色值
```

改完代码想确认"这一版能不能发"，一条命令就够：

```bash
python scripts/rc.py            # 跑完 docs/rc-checklist.md §1 的 11 项，逐项 PASS / FAIL / SKIP
python scripts/rc.py --fast     # 只改了前端时跳过 cargo test
```

`rc-checklist.md` 里 §2 是得真人点一遍的，§4 写明哪些必须有服务器才验得了。

出本地安装包：

```bash
npx @tauri-apps/cli build --debug --bundles nsis
# 产物在 target/debug/bundle/nsis/Portio_<版本>_x64-setup.exe
```

**内存占位**：三 crate 分层 —— `core`（领域模型，不认识 Tauri）、`ssh`（协议抽象）、
`app`（Tauri 外壳，唯一允许依赖 tauri 的 crate）。界面是原生 HTML/CSS/JS，无构建步骤。

## 约定

Conventional Commits（`feat` / `fix` / `chore` / `docs` / `test` / `ci` / `refactor`），
提交正文写清验证方式。界面改动先读 [docs/design-spec.md](docs/design-spec.md)。
分支用 `<type>/<短描述>`，`main` 只收 PR。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 版本号

格式 `vMAJOR.MINOR.PATCH`，预发布 `-AlphaN` / `-RCN`；MINOR 与 PATCH 封顶 10，满 10 向高位进位。
规则与对照表见 [docs/versioning.md](docs/versioning.md)，用 `python scripts/set_version.py` 写、
`python scripts/check_versions.py` 校验，别手改四处版本字段。

## 许可

MIT，见 [LICENSE](LICENSE)。
