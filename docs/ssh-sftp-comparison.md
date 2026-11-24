# 主流开源 SSH/SFTP 客户端实现对照与 Portio 复用边界

> 目的：在继续堆功能前，先看成熟开源客户端是怎么分层、怎么选轮子的，
> 明确「哪些已经在复用、哪些不该自研、缺口该按什么顺序补」，避免重复造轮子。
> 对照对象：PuTTY、OpenSSH、FileZilla、Tabby；WinSCP 作为功能对位参考（其源码许可与形态不作为实现来源）。
> 口径：本文只做架构与选型对照，不排期；真排进 Sprint 时挪进 `backlog.md`。

## 0. 结论先行

1. **Portio 当前分层方向是对的**：协议层委托 russh / russh-sftp，终端仿真委托 xterm.js，外壳与 IPC 委托 Tauri。自研代码只应落在业务编排——会话模型、传输队列、配置导入导出、错误翻译、UI 状态。
2. **协议与终端层没有重复造轮子**：KEX/加密/分包/通道、VT/ANSI/Unicode 渲染都是库在做；Portio 写的是薄封装。
3. **缺口集中在两块**：
   - 企业级连接能力：跳板主机链、端口转发、agent、键盘交互认证（主流客户端标配，Portio 尚未支持）。
   - 文件管理深度：目录树批量传输、属性/时间戳保留、校验核对、目录比较同步、在线编辑（FileZilla/WinSCP 的成熟能力，Portio 还在单文件层面）。
4. **薄封装有两个已踩过/易踩的坑**：SFTP 子系统请求顺序（RC3 已修）；错误归类不能把所有 `Timeout` 都翻成「网络不可达」，要区分 TCP / 握手 / 认证 / 子系统 / 通道各阶段。

## 1. 参照对象一览

| 工具 | 语言 / 形态 | 协议栈 | 终端 | 主要可借鉴层 |
|---|---|---|---|---|
| PuTTY | C，MIT，原生桌面 | 自研 SSH-2 全栈（BPP → 传输 → 用户认证 → 连接层 → 通道） | 自研终端仿真 | 协议分层切分、通道类型划分、Pageant agent 模型、会话配置组织 |
| OpenSSH | C，BSD，参考实现 | 系统级 SSH 参考实现 | 无 GUI 终端（命令行） | `ssh_config` 语义、known_hosts TOFU/严格检查、转发语义（-L/-R/-D）、ProxyJump/ProxyCommand、退出码与 stderr 分离、keepalive |
| FileZilla | C++，GPL，双栏桌面 | FTP/FTPS/SFTP 多协议统一客户端 | 自带文件视图 | 传输队列引擎（优先级/暂停/取消/重排）、多会话隔离（浏览会话 ≠ 传输会话）、断点续传与重试退避、目录比较、在线编辑（下载临时文件→保存回传）、速度限制、过滤器 |
| Tabby | TypeScript，MIT，Electron | Node `ssh2`（SSH2 客户端库） | xterm.js（WebGL/Canvas 双渲染、Unicode11、连字、fit、搜索、状态序列化） | 会话 Profile 模型（主机/端口/认证/转发/代理/算法/X11）、SSHSession 生命周期编排、跳板与 agent 转发、登录脚本、加密凭据容器、标签记忆 |
| WinSCP | 源码可用的闭源形态 | SFTP/SCP/FTP | 双栏文件管理 | 功能对位参考：会话树、过滤器、比较/同步、保留时间戳与权限、符号链接、编辑器集成、队列与续传 |

> 选型注记：Portio 是 Rust + Tauri，不可能直接搬 C++/TS 代码；借鉴的是**分层边界、协议语义、功能清单与可靠性策略**，具体实现走 Rust 生态对应库。

## 2. 能力对照矩阵

图例：✅ 原生支持　🟡 部分/受限　❌ 未支持　— 不适用

| 功能域 | PuTTY | OpenSSH | FileZilla | Tabby | Portio 现状 |
|---|---|---|---|---|---|
| 密码认证 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 公钥认证 | ✅（PPK） | ✅ | ✅ | ✅ | ✅（私钥文件；口令解锁与 agent 未做） |
| 键盘交互 keyboard-interactive | ✅ | ✅ | ✅ | ✅ | ❌ |
| GSSAPI /  Kerberos | ✅ | ✅ | 🟡 | ❌ | ❌ |
| 主机密钥 TOFU / known_hosts | ✅ | ✅ | ✅ | ✅ | ✅（TOFU；变更后只能删记录重连，无「确认更换」显式入口） |
| 跳板主机 ProxyJump / 代理链 | 🟡（Plink 隧道） | ✅ | ✅ | ✅ | ❌（ssh_config 解析刻意跳过 ProxyJump） |
| 本地端口转发 -L | ✅ | ✅ | — | ✅ | ❌ |
| 远程端口转发 -R | ✅ | ✅ | — | ✅ | ❌ |
| 动态转发 -D（SOCKS） | ✅ | ✅ | — | 🟡 | ❌ |
| agent 转发 / Pageant / 系统 agent | ✅（Pageant） | ✅（ssh-agent） | ✅ | ✅（含 Pageant、Windows OpenSSH Agent） | ❌ |
| X11 转发 | ✅ | ✅ | — | ✅ | ❌ |
| 交互式 PTY + resize | ✅ | ✅ | — | ✅ | ✅（xterm-256color、window-change） |
| 退出码 / stderr 分离 | ✅ | ✅ | — | ✅ | 🟡（退出码有；stderr 走扩展通道并入输出，未分离） |
| 目录列举 / 元数据 | ✅（PSFTP） | ✅ | ✅ | ✅ | ✅（名字/大小/时间/权限位） |
| 单文件上传下载 | ✅ | ✅ | ✅ | ✅ | ✅（32KB 分块流式） |
| 断点续传 | ✅ | ✅（scp/sftp 语义） | ✅ | 🟡（Zmodem） | ✅（`.part` 半截文件 + 偏移续传，上下行均有钩子） |
| 目录树批量传输 | ✅（PSFTP 递归） | ✅（scp -r / sftp -r） | ✅ | 🟡 | ❌（当前单文件操作） |
| 传输队列（优先级/暂停/取消/重排） | 🟡（命令行） | — | ✅ | 🟡 | 🟡（有队列与进度；暂停/优先级/重排未做） |
| 失败重试与退避 | 🟡 | ✅（连接重试） | ✅（可配次数与退避） | 🟡 | ❌ |
| 并发上限 / 速度限制 | ❌ | — | ✅（全局与站点级限速、时段限速） | 🟡 | ❌（当前单流串行） |
| 校验和核对（传后比对） | ❌ | — | 🟡（大小/时间比较） | ❌ | ❌ |
| 保留时间戳 / 权限 | ✅（PSFTP `-p`） | ✅（scp -p） | ✅ | ❌ | ❌（只搬内容） |
| 符号链接（读/建/跟随） | ✅ | ✅ | ✅ | 🟡 | ❌ |
| chmod / chown | ✅ | ✅ | ✅ | 🟡 | ❌ |
| 目录比较 / 同步 | 🟡 | — | ✅ | ❌ | ❌ |
| 在线编辑（下载临时→保存回传） | 🟡（外部编辑器） | — | ✅ | ❌ | ❌ |
| 会话持久化 / 标签记忆 | ✅（保存会话） | — | ✅（Site Manager 分目录） | ✅（remember tabs） | ✅（会话落盘 + 加密凭据库） |
| 导入 PuTTY/OpenSSH/WinSCP 会话 | ✅（自身格式互通） | — | ✅ | 🟡 | ✅（PuTTY、Xshell、OpenSSH ssh_config 解析器） |
| 断线重连 / 多路复用 | 🟡 | ✅（ControlMaster） | ✅（自动重连） | 🟡 | ❌ |

## 3. 按功能域拆解

### 3.1 传输与连接层

**主流做法**
- PuTTY/OpenSSH 严格按协议栈分层：分包（BPP）→ 传输（KEX、服务端认证、加密）→ 用户认证 → 连接层（通道与转发）→ 通道处理器。上层只拿通道句柄，不碰加密细节。
- 连接阶段错误可区分：TCP 不通、KEX 失败、主机密钥变更、认证被拒、子系统不存在、通道超时——各阶段错误语义不同。
- OpenSSH/FileZilla 都有 keepalive 与断线检测；FileZilla 传输会话与浏览会话隔离，大文件传输时目录仍可自由浏览。

**可复用库（Rust）**
- `russh`：tokio 上的低层 SSH2 客户端/服务端，传输、认证、通道、`direct-tcpip`/`forward-tcpip` 转发都在库内；生态配套 `russh-sftp`。Portio 已用。
- `ssh2-rs`：libssh2 的 Rust 绑定，C 依赖、需 OpenSSL/原生加密后端；功能成熟但构建链重，Portio 现选 russh（ring 后端）是合理的。
- `remotefs-ssh`：在 russh / ssh2 之上做的统一文件协议抽象，附带 ssh_config 解析；未来若要加 SCP 或多协议，可评估。

**Portio 现状**
- `crates/ssh/src/client.rs`：`connect()` 包 TCP + 握手 + 认证，12s 超时；`open_shell()` 开会话通道、申请 PTY、起 shell；通道双向搬运走 tokio mpsc。
- 错误映射在 `lib.rs` 的 `SshError`；已知坑：SFTP 阶段的 `Timeout` 曾被前端统一翻成「网络不可达或服务端限流」。

**建议边界**
- 不要自研分包/加密/KEX；连接编排与阶段化错误翻译是自研层的活。
- 错误分类要按阶段细化：`ConnectTimeout`（TCP/握手）、`AuthFailed`、`HostKeyMismatch`、`Protocol`（通道/子系统），前端翻译按阶段匹配，不要用一条 `timeout` 正则兜全部。
- 浏览会话与传输会话是否隔离，等目录树批量传输排期时再定；当前单连接单通道不必提前拆。

### 3.2 认证与主机密钥

**主流做法**
- 认证方式矩阵：密码、公钥、键盘交互、agent、GSSAPI；多数客户端把「首选方式 + 兜底」交给配置。
- 主机密钥：首次 TOFU 落盘；再次连接比对指纹；变更时显式告警，给「确认这是新机器 / 放弃」两个出口，不默认放行。
- 私钥格式：OpenSSH 私钥、PPK、RSA/ECDSA/Ed25519；带口令的私钥需要交互解锁；agent 是免口令与多机复用的标准方案。

**Portio 现状**
- 密码 / 公钥文件两种；公钥走 `load_secret_key` + `best_supported_rsa_hash`。
- `known_hosts.rs` 做 TOFU 与指纹比对；变更只能去设置删记录再重连。
- 口令式私钥解锁、ssh-agent、键盘交互认证均未做（`lib.rs` 已留注记）。

**建议边界**
- 私钥格式解析、agent 协议走库（russh-keys / 对应 agent 支持），不要自己写 PPK/OpenSSH 私钥解析。
- 主机密钥变更的「一键信任」入口属于安全默认值，需用户拍板后再做（backlog 已登记）。

### 3.3 PTY 与终端会话

**主流做法**
- Tabby：终端前端抽象成接口，xterm.js 给 WebGL / Canvas 两套渲染；接 Unicode11（双宽/emoji）、连字、fit（随容器缩放）、搜索 addon；会话状态可序列化。
- OpenSSH/PuTTY：PTY 申请带终端类型、行列宽高；resize 走 `window-change`；退出码、EOF、通道关闭是独立事件；stderr 与 stdout 分通道。

**Portio 现状**
- xterm.js + `addon-fit` 本地 vendor；PTY `xterm-256color`；`Resize` 走 `window_change`；事件有 `Output / Exit / Closed / Error`。
- 搜索是前端自绘（跨折行命中已处理）；未接官方 `@xterm/addon-search`；未接 Unicode11 / 连字 addon；stderr 扩展通道并入了输出流。

**建议边界**
- 终端仿真、字符宽/折行/渲染一律不碰；缺的终端能力优先找 xterm 官方 addon，而不是自己在 app.js 里补。
- 后续可评估：`@xterm/addon-search`（全量命中高亮）、`unicode11`、`ligatures`；stdout/stderr 分离在协议层把扩展通道单独成事件。

### 3.4 SFTP 文件操作

**主流做法**
- FileZilla/WinSCP：双栏本地/远端；目录树递归传输；属性含权限、属主、时间戳、链接类型；操作覆盖 chmod、chown、符号链接、远端改名/复制；在线编辑走「下载到临时目录 → 保存时回传」。
- OpenSSH sftp：协议语义参考；`stat/lstat/readlink` 区分符号链接；`setstat` 改属性。

**Portio 现状**（`crates/ssh/src/sftp.rs`）
- 已有：`home / list / download / upload / mkdir / remove / rename`；32KB 流式；`.part` 半截文件 + 偏移续传；上传改名不覆盖时先删目标再改名的兜底。
- 未做：目录树递归、符号链接、chmod/chown、属主、时间戳/权限保留、传后校验、远端复制、过滤器/隐藏项。

**建议边界**
- SFTP 报文格式（FXP_*、OpenFlags、属性编码）由 russh-sftp 负责；Portio 只做业务操作编排。
- 缺口按「单文件可用 → 目录批量 → 比较同步」三步走；属性保留与校验在批量传输阶段一起设计，单文件阶段不必返工式补。

### 3.5 传输队列、续传与可靠性

**主流做法**
- FileZilla：队列项可排队、调优先级、暂停/继续/取消、重排；失败项自动重试（可配次数与退避）；限速分站点级与全局级；多会话并发，浏览不被传输阻塞；断点续传基于字节范围，>4GB 文件同样适用。
- OpenSSH：连接层有重试与 keepalive；续传语义在 scp/sftp 命令层。
- Tabby：会话级传输（Zmodem / SFTP 标签），队列能力较轻。

**Portio 现状**
- 传输抽屉有队列与实时进度（字节进度回调）；上下行都有半截文件续传钩子。
- 未做：暂停/继续、优先级、并发上限、失败重试退避、限速、传后校验、断线后续传会话恢复。

**建议边界**
- 队列状态机（待传/进行/暂停/失败/完成）是自研业务层；重试退避策略可参考 FileZilla 的可配次数 + 指数退避。
- 续传判定（远端变小/传满/半截失效）已有 `resume.rs` 规则，沿用并补测试覆盖。

### 3.6 会话配置与导入

**主流做法**
- Tabby Profile：主机/端口/用户/认证方式/转发规则/代理/算法偏好/X11 等成套存一个对象；导入与手工编辑同构。
- OpenSSH `ssh_config`：`Host` 块、`Include`、`ProxyJump`、`LocalForward` 等有标准语义；FileZilla Site Manager 分目录组织会话。
- PuTTY/WinSCP：会话文件互相可导入。

**Portio 现状**
- `core/session_store.rs` 会话落盘；`core/vault.rs` 加密凭据库；`core/sshconfig.rs` 解析 OpenSSH 配置（刻意跳过 ProxyJump / LocalForward）；`core/winscp.rs`、`core/xshell.rs` 导入器。

**建议边界**
- 配置文件格式解析（ssh_config、PuTTY 注册表/导出、Xshell 会话）参考现成解析器语义；若复用 `ssh2-config` 类 crate 可减少自写解析的边角 case。
- 跳板/转发参数等真正进入 Profile 模型时，再回头把 ssh_config 里被跳过的键接上。

### 3.7 凭据本地存储

**主流做法**
- Tabby：加密容器存 SSH 机密与配置；OpenSSH 私钥口令可由 agent 托管；FileZilla 主密码保护站点管理器。
- 共同点：落盘的是加密后的机密；明文口令不进普通配置文件。

**Portio 现状**
- `core/vault.rs` 凭据加密；`credentials.rs` 存取；`vault.key` 32B。

**建议边界**
- 加密算法与密钥派生走成熟 crate；自研层只负责「哪项机密进保险库、哪项只存引用」。

## 4. 轮子复用清单

### 4.1 已经在复用（继续保持，不要自研替代）

| 层 | 库 / 组件 | 覆盖的轮子 |
|---|---|---|
| SSH 传输/认证/通道 | russh 0.60.3（ring 后端） | KEX、加密/完整性、主机密钥校验、通道收发、转发原语 |
| SFTP 协议 | russh-sftp 2.4 | FXP 报文、目录/文件操作、属性编码 |
| 终端仿真 | xterm.js（vendor） | VT/ANSI 解析、屏幕缓冲、Unicode/双宽、渲染 |
| 终端尺寸适配 | addon-fit | 容器尺寸 → PTY 行列同步 |
| 桌面外壳 / IPC | Tauri 2 | 窗口、WebView、前后端通信、打包 |
| 异步运行时 | tokio | 任务调度、mpsc 通道、超时、文件 IO |
| 持久化序列化 | serde / serde_json | 会话、配置、凭据结构落盘 |
| 错误类型 | thiserror | 协议错误枚举封装 |

### 4.2 可评估引入（按缺口触发，不提前上）

| 需求触发点 | 候选 | 说明 |
|---|---|---|
| 远程命令执行会话（分离 stdout/stderr/退出码） | `async-ssh2-russh`（russh 薄封装） | 补 russh 高层 API 不便于区分流的短板；当前 PTY 场景可先不引 |
| 未来加 SCP / 多文件协议抽象 | `remotefs-ssh` | 统一文件协议抽象 + ssh_config 解析；评估其 russh 后端成熟度 |
| 终端搜索全量高亮 | `@xterm/addon-search` | 官方 addon，替代自绘搜索的补充能力 |
| 双宽/emoji 完整性 | `@xterm/addon-unicode11` | 官方 addon |
| 连字渲染 | `@xterm/addon-ligatures` | 官方 addon，依赖字体 |
| 本地 agent / 系统 agent 对接 | russh-keys agent 支持 / 对应 agent crate | 跳板与免口令场景的前置 |

### 4.3 明确不要自研

- VT/ANSI 解析器、终端屏幕缓冲、字符宽度与折行算法。
- SSH 分包、加密、KEX、主机密钥格式与指纹算法。
- SFTP 报文编码、属性/标志位定义。
- OpenSSH / PPK 私钥格式解析、known_hosts 线格式。
- 已知主机与 agent 的协议线格式。

## 5. 缺口优先级建议（对照主流客户端）

> 仅给方向与复用提示；排期以 backlog 与 Sprint 为准。

### P0 — 先把现有链路在真机上跑通

- **真机端到端复测**（任务 #75 挂起中）：缺目标服务器凭据；登录后 PTY / SFTP / 续传链路要在真服务器跑一遍。若目标 Dropbear 未装 `sftp-server`，文件面板仍会报错——属服务端前提，不是客户端缺陷。
- 阻塞解除前，不建议叠加新连接能力。

### P1 — 主流客户端标配、Portio 缺得最多的一块

1. **跳板主机链 / ProxyJump / 代理**：参考 OpenSSH `ProxyJump` 语义与 Tabby Profile 的代理字段；底层用 russh 的通道转发原语。先单跳，再链式。
2. **端口转发**：本地 -L / 远程 -R / 动态 -D；russh 已具备 `direct-tcpip` / `forward-tcpip` 原语，封装成 Profile 项即可。
3. **ssh-agent 对接**：本地 agent 与 Windows 系统 agent / Pageant；覆盖带口令私钥与多机复用。
4. **键盘交互认证**：服务端 `keyboard-interactive` 挑战应答；russh 认证段补一条路径。
5. **目录树批量上传下载**：递归列举 + 队列化传输；这是引入「浏览/传输会话隔离、并发上限」的触发点。
6. **队列重试与退避**：失败项可配重试次数与指数退避；单流并发上限先做成可配。
7. **在线编辑**：下载到本地临时目录 → 保存回传（FileZilla 模式）；改动检测与冲突提示后补。

### P2 — 文件管理深度与体验完善

1. 目录比较 / 同步（FileZilla 目录比较模式）。
2. 符号链接：`lstat/readlink` 区分，支持创建链接。
3. chmod / chown / 保留时间戳与权限（批量传输时一起落地）。
4. 传后校验：大小比对优先；校验和核对作为可选增强。
5. 速度限制（站点级 / 全局级）。
6. 断线重连与会话恢复；keepalive 死链检测。
7. X11 转发、Zmodem 直传：低频可选，按用户反馈再定。

## 6. 薄封装风险点（实现时对照协议自查）

1. **子系统请求顺序**：会话通道打开后，必须先 `request_subsystem("sftp")` 再 `SftpSession::new`；顺序反了服务端不起 sftp-server，干等到超时。RC3 已修，改动类测试不要回退这一步。
2. **阶段化错误归类**：`Timeout` 要能区分 TCP 连接、KEX 握手、认证、SFTP 子系统、通道 IO；前端翻译按阶段走，禁止一条超时正则兜全部。
3. **stderr 与扩展数据**：`ExtendedData` 当前并入输出；做命令会话或错误诊断时要能分流。
4. **退出码 / EOF / 通道关闭**：三个事件语义不同（命令退出 ≠ 通道关闭），搬运循环别混。
5. **空闲超时与死链**：russh `inactivity_timeout` 已有 30s；长线传输与空闲挂起要区分，避免大文件传输被误判空闲断开。
6. **服务端前提**：精简版 Dropbear 可能只起 shell、不带 sftp-server；报错文案要能区分「协议不支持子系统」与「网络不通」。

## 7. 参考来源

- Tabby（GitHub）：https://github.com/Eugeny/tabby
- Tabby SSH 实现拆解（DeepWiki）：https://deepwiki.com/Eugeny/tabby/4.1-ssh-implementation
- Tabby 终端架构（DeepWiki）：https://deepwiki.org/Eugeny/tabby/3-terminal-functionality
- FileZilla Client 功能与队列（Wiki）：https://wiki.filezilla-project.org/wiki/index.php?oldid=4918&title=FileZilla_FTP_Client
- FileZilla Pro 传输引擎与队列：https://filezillapro.com/docs/v3/features-v3/filezilla-pro-features/
- PuTTY SSH 协议分层（DeepWiki）：https://deepwiki.com/github/putty/4.1-ssh-protocol-layers
- russh crate：https://crates.io/crates/russh
- remotefs-ssh crate：https://crates.io/crates/remotefs-ssh
- async-ssh2-russh crate：https://crates.io/crates/async-ssh2-russh/0.3.0
