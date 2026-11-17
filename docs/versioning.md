# 版本号规则

Portio 的版本号定死在这张纸上，发布前照抄，不即兴发挥。

## 格式

```
vMAJOR.MINOR.PATCH           正式版       v1.0.0
vMAJOR.MINOR.PATCH-alphaN    内测版       v1.0.0-alpha1
vMAJOR.MINOR.PATCH-RCN       候选版       v1.0.0-RC1
```

- **MAJOR**：破坏性变更或大重构，只有"进位"能推高它。
- **MINOR**、**PATCH**：取值 **0–10**，**不允许出现 11**。
- **进位**：`PATCH` 满 10 再加一 → `MINOR + 1`、`PATCH = 0`；`MINOR` 满 10 再加一 → `MAJOR + 1`、`MINOR = 0`、`PATCH = 0`。

| 当前 | 动作 | 下一版 | 说明 |
|---|---|---|---|
| `1.0.5` | patch | `1.0.6` | 常规 |
| `1.0.10` | patch | `1.1.0` | PATCH 满 10，进位 |
| `1.10.10` | patch | `2.0.0` | MINOR 也满 10，连进两级 |
| `1.0.10` | minor | `1.1.0` | MINOR 直接加一 |
| `1.10.3` | minor | `2.0.0` | MINOR 满 10，进位 |
| `1.2.3` | major | `2.0.0` | 重新从零开始 |

## 阶段

| 阶段 | 含义 | 能改什么 |
|---|---|---|
| `alphaN` | 内测 | 功能还能加、还能删 |
| `RCN` | 候选 | **功能冻结**，只修 Bug |
| 无后缀 | 正式 | 只发修 Bug的 patch |

顺序恒为 `alpha < RC < 正式`。

**预发布计数 `N` 也是 1–10**：做到 `alpha10` 后还想发第 11 个内测版，就进位到下一个 patch、重新从 `alpha1` 开始（例：`1.2.3-alpha10` → `1.2.4-alpha1`）。这一条是我按同一精神补的，你若想改成"alpha 允许超过 10"说一声。

## 里程碑与对外版本对照

内部的 v0.1–v0.4 是**阶段代号**，不是版本号；对外只发下面这些。

| 内部里程碑 | Gate 日期 | 对外版本 | 说明 |
|---|---|---|---|
| v0.1 能连能敲 | 2027-01-17 | 不发 | 自己用，只见 tag `internal-v0.1` |
| v0.2 会话管理与迁移 | 2027-02-28 | `v1.0.0-alpha1` | 首个公开版 |
| v0.3 文件双栏 | 2027-04-25 | `v1.0.0-alpha2` | 功能补齐 |
| v0.4 打磨发布 | 2027-06-06 | `v1.0.0-RC1` → `v1.0.0` | 冻结后转正 |

## 发布动作（四步，缺一不可）

```bash
python scripts/version.py next 1.0.5 patch     # 先算出来，别心算
# 1) 同步改三处：Cargo.toml 的 [workspace.package]、package.json、crates/app/tauri.conf.json
python scripts/check_versions.py               # 2) 三处必须一致且合规
git tag -a v1.0.6 -m "v1.0.6"
# 3) CHANGELOG 加一条，日期写发布当天
```

`check` 与 `check_versions` 都已进 CI，任何人绕过，流水线直接红。

## 一个必须知道的坑

`v1.0.0-alpha1` 与 `v1.0.0-RC1` 混用大小写，会让 **SemVer 的字面排序出错**：ASCII 里 `R`(82) < `a`(97)，所以按字符串比较时 `RC1` 会排在 `alpha1` **前面**，看起来像先发了 RC 再发 alpha。我们自己的 `version.py` 按"阶段顺序 + 计数"比较，不受影响；但若将来上传 crates.io 或 npm，那里只看字符串——两种解法任选：把两段都写成大写（`ALPHA1` / `RC1`），或都写成小写（`alpha1` / `rc1`）。现在维持你定的写法，等真要上传时再统一。
