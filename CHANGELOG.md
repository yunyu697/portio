# Changelog

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## 各版本的更新内容（GitHub Release 文案直接取自本节）

> 规则：**先写更新内容，再打包**。每个版本一个 `## [版本] - 日期` 小节，发布时整段复制到 GitHub Release 即可。
> 只写用户能感知的变化；内部重构放 `### Changed`，未验证的能力写进 `### Known limitations`。

## [1.0.2-Alpha3] - 2026-11-18

### Fixed
- 主题按钮"要点两次才变亮"：之前按 深色→浅色→跟随系统 三点轮转，系统本身是深色时第三档等于没变化。改成按当前实际显示的主题取反，一次点击就是一次可见变化；"跟随系统"仍在设置面板里可选。
- 跟随系统以前只在启动那一刻读一次，系统切深浅色时界面不跟。现在监听 `prefers-color-scheme` 变化即时同步。

### Changed
- 设置项（主题 / 终端字号 / 滚动缓冲）改为作用到**每个已开标签**的终端，不再只管当前这一个；改完字号后切回旧标签，字号也是新的。

## [1.0.2-Alpha2] - 2026-11-18

### Fixed
- 启动时不再弹出控制台黑窗：`main.rs` 改为无条件 `#![windows_subsystem = "windows"]`。Tauri 模板只在非 debug 构建里关控制台，而我们发的是 `--debug` 包，所以之前每次启动都会多一个黑窗。
- 主题按钮在亮暗主题下改用不同图标（深色月亮 / 浅色太阳），并按 24 格中心重画，与密度、设置、快捷键三枚图标对齐。

### Added
- `#theme-dark` / `#theme-light` 深链：截图核验主题图标时直接锁定主题，不必靠点按钮。

### Changed
- CHANGELOG 改为"每版一节、可直接作为 GitHub Release 文案"；排期文档新增第 10 节进度看板。

## [1.0.2-Alpha1] - 2026-11-18

### Added
- 远端文件重命名 `sftp_rename(id, from, to)`、本地文件重命名 `local_rename(from, to)`，两套右键菜单各加"重命名"（弹窗预填当前名字，没改或取消则不动）。

### Known limitations
- 真实 SFTP 会话下的改名未验证（缺测试主机与凭据）。

## [1.0.1-Alpha5 … Alpha10] - 2026-11-18

> 这十次进位都集中在"把界面和安装包做到能给外人看"上，合并成一节记录。

### Added
- `scripts/refresh-icon-cache.ps1`：停 Explorer → 删 `iconcache_*.db` 分片 → 重启 Explorer → `ie4uinit -show`。
- NSIS `NSIS_HOOK_POSTINSTALL` 安装钩子：装完自动刷一次图标缓存，脚本随包安装到 `%LOCALAPPDATA%\Portio\scripts\`，执行留痕写 `_iconhook.log`。
- 五处右键菜单：终端面板、远端文件行、本地文件行、会话行、标签页。
- 会话栏搜索框（主机 / 用户 / 备注）。

### Changed
- 应用图标改为无底板图形（去底板、描边、投影），并按 Windows 桌面实际显示校准内容占比（宽 97.9% / 高 88.2%），解决"图标比别人小一圈"。
- 会话列表按"最近使用 / 更早"分组。

### Fixed
- 安装钩子用 Windows PowerShell 5.1 跑 UTF-8 无 BOM 脚本导致的中文注释乱码 → ParserError，脚本改存 UTF-8 带 BOM。
- `.tbtn svg{display:block}` 特异性压过 `.i-sun{display:none}` 导致日月同显的问题（选择器提到 `.tbtn svg.i-sun`）。

## [1.0.1-Alpha4] - 2026-11-18

### Added
- 会话列表分组：最近使用 / 更早。

### Changed
- 应用图标重出为无底板版（Apple 图标规范的 80.5% 内容区比例）。

## [1.0.1-Alpha3] - 2026-11-18

### Fixed
- 圆角尺度统一：补齐 `tokens.css` 里缺失的 `--r-4 / --r-6 / --r-8 / --r-12`。变量未定义使整条 `border-radius` 声明失效，表现为"主窗口有圆角、其它元素全是直角"。
- 主题按钮的月牙 path 几何偏右上，与另三个图标不对齐。

### Added
- 会话栏搜索（`Ctrl+F` 聚焦，按主机 / 用户 / 备注过滤）。

## [1.0.1-Alpha2] - 2026-11-18

### Changed
- 标题栏四个文字按钮改成图标：主题、密度、设置、快捷键。
- 滚动条改为 6px 细条＋主题色，替换系统默认宽滚动条。
- 会话栏支持完全折叠，折叠态在左缘留一个动态显示的把手。


## [1.0.0-Alpha7] - 2026-11-18

### Added
- SSH 会话内核（russh 0.60.3，ring 后端）：密码 / 私钥认证、PTY 申请、窗口尺寸同步、断线清理
- known_hosts 首次信任（TOFU 一行一条），指纹变化立即断开并给出旧 / 新指纹对照
- SFTP：远端目录列举、32KB 分块上传下载（下载先写 `*.portio-part` 再改名）、建 / 删目录、重命名、逐块进度事件
- 终端：xterm.js 自托管 + FitAddon；选中即复制、右键粘贴、Ctrl+C 中断、F5 重绘、Ctrl+Alt+H 全屏
- 界面骨架：自绘标题栏（品牌 / 版本 / 标签页 / 主题 / 密度 / 窗口按钮）、会话栏、终端‖远端|本地三段式、传输队列抽屉、状态栏时钟
- 设置面板：主题（深 / 浅 / 跟随系统）、界面密度、终端字号 11–18、滚动缓冲 2000 / 8000 / 20000 行，全部持久化
- 快捷键一览浮层（`Ctrl + /`，三组 12 条，只列已实现的操作）
- 打包配置：NSIS 当前用户安装（简体中文 / English，不弹语言选择器）、macOS 最低 10.15

### Changed
- 错误提示统一为“标题 + 下一步”话术，覆盖认证被拒 / 连接被拒 / 超时 / 磁盘满 / 权限不足 / 路径不存在 / 指纹变化；翻译不了的一律保留原文

### Known limitations
- 未在真实服务器上验证：PTY 交互、resize、tmux / vim 全屏、真实 SFTP 上传下载（缺测试主机与凭据）
- 多标签与会话持久化在 S5 接入；`tauri bundle` 尚未实跑（本机缺 Node，Tauri CLI 未安装）

## [0.0.1-skeleton] - 2026-11-17

### Added
- Tauri v2 工程骨架与三 crate 工作区（`app` / `core` / `ssh`）
- 前端最小外壳：自绘标题栏、三栏栅格、状态栏，全部读 `ui/tokens.css`
- GitHub Actions：`check`（fmt / clippy / test）与 `build`（三平台）
- 品牌图标（深色 / 浅色两套，含 ico / icns）
