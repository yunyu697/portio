# Portio

跨平台的 SSH 终端 + SFTP 文件管理，一个窗口里干完两件事。

> 名字取 **port + io**：port 是 SSH 端口，也是数据的进出口——命令往下走，文件往上走。

## 状态

| 版本 | 范围 | Gate |
|---|---|---|
| v0.1 能连能敲 | Tauri 外壳、SSH 连接池、终端仿真、会话树 | 2027-01-17 |
| v0.2 会话管理与迁移 | 会话 CRUD、分组、Xshell/WinSCP 导入 | 2027-02-28（首个公开版） |
| v0.3 文件双栏 | SFTP、传输队列、断点续传 | 2027-04-25 |
| v0.4 打磨发布 | 主题、签名、自动更新、文档 | 2027-06-06 |

当前进度：**v0.0.1-skeleton**，只有骨架，没有真实 SSH 与 SFTP。

## 本地跑起来

```bash
# 前置：Rust stable（MSVC 工具链）、Node 22 LTS、WebView2 Runtime
npm install          # 装 @tauri-apps/cli
npm run dev          # 开发模式起窗口
cargo test --workspace
```

若 `cargo` 提示找不到命令，把 `%USERPROFILE%\.cargo\bin` 加进 PATH 后重开终端。

## 结构

```
crates/
  app/     Tauri 外壳：窗口、菜单、与前端通信（唯一允许依赖 tauri 的 crate）
  core/    领域模型：会话、分组、传输队列。不依赖 Tauri，可单独测试
  ssh/     协议层：SSH / SFTP 抽象。实现从 S2 开始
ui/        前端（原生 HTML/CSS/JS，无构建步骤；设计令牌见 docs/design-tokens.md）
docs/      设计基线与决策记录
```

**分层规则**：`core` 与 `ssh` 不认识 Windows、不认识 Tauri；`app` 不认识协议细节。越界就是返工。

## 约定

Conventional Commits（`feat` / `fix` / `chore` / `docs` / `test` / `ci` / `refactor`）。分支用 `<type>/<短描述>`，例如 `feat/session-tree`。`main` 只收 PR。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可

MIT，见 [LICENSE](LICENSE)。
