# 版本号规则

Portio 的版本号定死在这张纸上，发布前照抄，不即兴发挥。

## 格式

```
vMAJOR.MINOR.PATCH           正式版       v1.0.0
vMAJOR.MINOR.PATCH-AlphaN    内测版       v1.0.0-Alpha1
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
| `AlphaN` | 内测 | 功能还能加、还能删 |
| `RCN` | 候选 | **功能冻结**，只修 Bug |
| 无后缀 | 正式 | 只发修 Bug的 patch |

顺序恒为 `Alpha < RC < 正式`。

**预发布计数 `N` 也是 1–10**：做到 `Alpha10` 后还想发第 11 个内测版，就进位到下一个 patch、重新从 `Alpha1` 开始（例：`1.2.3-Alpha10` → `1.2.4-Alpha1`）。这一条是我按同一精神补的，你若想改成"Alpha 允许超过 10"说一声。

## 里程碑与对外版本对照

内部的 v0.1–v0.4 是**阶段代号**，不是版本号；对外只发下面这些。

| 内部里程碑 | Gate 日期 | 对外版本 | 说明 |
|---|---|---|---|
| v0.1 能连能敲 | 2027-01-17 | 不发 | 自己用，只见 tag `internal-v0.1` |
| v0.2 会话管理与迁移 | 2027-02-28 | `v1.0.0-Alpha1` | 首个公开版 |
| v0.3 文件双栏 | 2027-04-25 | `v1.0.0-Alpha2` | 功能补齐 |
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

## 大小写：一律 Alpha / RC

两个阶段固定写作 **`Alpha`** 与 **`RC`**——首字母大写，其余照原样。这样同一个包里按字符串比较，
`Alpha`(A=65) 一定排在 `RC`(R=82) 前面，SemVer 的字面排序天然正确，不需要再为 crates.io / npm 做任何适配。

命令里输小写 `alpha` 也能认，脚本会自动规整成 `Alpha` 再输出，但**打 tag、写 CHANGELOG 时必须是 `AlphaN`**。
