# Changelog

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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
