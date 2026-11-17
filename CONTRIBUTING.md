# 参与与提交约定

## 提交信息

Conventional Commits，首行不超过 72 字符，正文说清"为什么"，不写"改了什么"（diff 已经说明）。

```
<type>(<scope>): <subject>

# 示例
feat(session): 会话树支持分组拖拽
fix(term): 修复 resize 后光标错行
chore(ci): 三平台构建改走 matrix
```

type 取值：`feat` `fix` `chore` `docs` `test` `ci` `refactor` `perf`。

## 分支

- `main`：永远可构建、可发布，只收 PR
- 工作分支：`<type>/<短描述>`，如 `feat/sftp-queue`
- 不 force push `main`，不 `--amend` 已推送的提交

## PR 自检

1. `cargo fmt --check` 与 `cargo clippy -- -D warnings` 通过
2. `cargo test --workspace` 通过
3. 改到前端时，附 1440×900 与 1280×720 两张截图
4. 涉及行为的改动，同步更新 CHANGELOG 的 Unreleased 段

## 分层红线

`core` 与 `ssh` 不得依赖 `tauri`、不得出现平台相关代码；`app` 不得直接调协议实现。
