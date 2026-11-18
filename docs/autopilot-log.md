# 自动推进日志

每轮一行，按时间倒序追加。格式：日期 ｜ 版本 ｜ 做了什么 ｜ 验证 ｜ 下一步。

- 2026-11-18 ｜ v1.0.1-Alpha1 ｜ S5 收口 + 图标收边（两件事合并一轮）。① 会话清单落到文件：`portio-core/src/store.rs` 定义 `SessionRecord/SessionStore`（去重键 `user@host:port`、上限 40、导入合并返回"成功/跳过"计数、JSON 兼容裸数组、拒绝更高版本号），`crates/app/src/session_store.rs` 提供 `sessions_read/sessions_write/sessions_path` 三个命令，写到应用数据目录的 `sessions.json`，先写 `.tmp` 再改名（断电不留半个文件）；前端改以磁盘为真源、内存为镜像，启动拉一次，老版本 localStorage 记录一次性迁移后删除。② 图标"显小"：实测 `icon.png` 内容只占画布 **82.8%/83.2%**（四周透明留白），Windows 不给图标加内边距，所以桌面上比邻居小一圈；新增 `scripts/icon_fit.py`（标准库实现 PNG 解码/双线性缩放/ICO 打包，不装 Pillow），按 2% 留白重排，得到 95.5%/96.0%，并重生成 32/64/128/256/512/1024 与含 16–256 七帧的 `icon.ico` ｜ `cargo test -p portio-core` 全绿（新增 9 条 store 单测，修掉一条断言键写错的用例）；`cargo build -p portio-app` 通过；启动 exe 6 秒未崩（窗口标题 Portio）；前端 `node --check` 通过、无头 dump-dom 标题 `Portio`、`#sess-demo` 截图与 DOM 断言 2 条。未验证：真实连接后 `sessions.json` 的落盘（仍缺测试主机）；macOS 的 `icon.icns` 未重排 ｜ 下一轮：会话搜索与分组（S6）
- 2026-11-18 ｜ v1.0.0-Alpha10 ｜ S5 第三单元：会话配置持久化。连接逻辑从"读表单→直接连"抽成 `connectWith(spec)`，成功后把 `host/port/user/auth/keyfile` 写进 `localStorage`（键 `portio.sessions`，最多 40 条，最近使用排最前，**密码不入库**）；会话栏改由 `renderSessions()` 统一渲染：单击填表人工确认、双击在密钥认证下直接重连、行尾 `×` 删除记录；空列表才显示原来的引导文案 ｜ `node --check` 通过；无头 `--dump-dom` 标题 `Portio`；`#sess-demo` 截图确认两条记录渲染（`:2222` 端口标记、`key` 认证标记、计数 2）；DOM 断言 2 个 `.sess-row`。踩坑：`const anchor` 之后又 `anchor = row` 触发 "Assignment to constant variable"，而 `file://` 下未捕获异常被浏览器脱敏成 `Script error.`——加 `--allow-file-access-from-files` 才能看到真实消息，此后无头验证一律带这个 flag ｜ 下一单元：S5 收口——会话配置导入/导出（JSON），然后进 S6
- 2026-11-18 ｜ v1.0.0-Alpha9 ｜ S5 第二单元：前端标签条真接线。取消"单终端 + 单一 term 全局"的写法，改成每标签一个独立 xterm 容器（`.term-pane` 绝对定位叠放、`.on` 控制可见）与独立会话；`renderTabs / createTab / activateTab / closeTab` 落地，`×` 关闭（只剩一个标签时不显示）、`Ctrl+W` 真关闭（关闭后按"右邻优先、否则左邻"选前台，与 core 规则一致）、`F5` 改为重绘终端而非空提示；`shell` 事件按会话 id 路由到所属标签，后台标签输出不再串台；关窗时遍历断开所有会话 ｜ `node --check ui/app.js` 通过；无头 `--dump-dom` 标题无 `ERR`；`#tabs-demo` 截图确认标签条三态（激活底色、accent 圆点、× 按钮）与终端 banner 正常；DOM 断言"2 个 pane 中恰好 1 个 `.on`"。踩坑记录：`term/fitAddon` 在顶部与终端段重复 `let` 会 SyntaxError，整份脚本不执行（且 onerror 钩子在此情形下也不会注册，标题不会报 ERR，只能靠 `node --check` 抓） ｜ 下一单元：会话配置持久化（连接后记住 user/host/port，重启可一键重连）
- 2026-11-18 ｜ v1.0.0-Alpha8 ｜ ① 补做打包验证：用运行时自带的 Node 22 走 `npm install` 装好 Tauri CLI（devDependency，之前卡在"缺 Node 22"），`tauri build --debug --bundles nsis` 一次跑通，产出 `Portio_1.0.0-Alpha7_x64-setup.exe`（4.2 MiB，NSIS 当前用户安装）；② S5 第一单元：`crates/core/src/tabs.rs` 标签模型——open / activate / close / move_to / rename、上限 16 返回 `TooManyTabs`、关闭当前标签后焦点落右邻再落左邻 ｜ `cargo test -p portio-core` 11 passed（新增 11 条，另 3 条既有）；`check_versions.py` OK；打包 exit=0 且安装包文件存在 ｜ 下一单元：把 `TabSet` 接进应用层与前端标签条（先只做"同一窗口内切换 + Ctrl+W 真关闭"）
- 2026-11-18 ｜ v1.0.0-Alpha7 ｜ S4 收尾：打包配置（bundle 补 publisher/copyright/category/长短描述；Windows 走 NSIS 当前用户安装、简中+英文、不弹语言选择器；macOS 最低 10.15）＋ CHANGELOG 补 `1.0.0-Alpha7` 段落（Added / Changed / Known limitations 三块，写明未验证项） ｜ `python -c json.load` 校验配置合法；`cargo build -p portio-app` 通过（tauri 构建脚本已解析新配置，键名不合法会直接失败）；`check_versions.py` OK ｜ S4 结束，下一轮进 S5：多标签与会话持久化（先做标签模型的纯函数层 + 单测）
- 2026-11-18 ｜ v1.0.0-Alpha6 ｜ S4 第三单元：错误提示统一。新增 `explainError(cmd, err)`，把 russh/SFTP 的原始报错翻成"标题 + 下一步"七类话术（认证被拒/连接被拒/超时/磁盘满/权限不足/路径不存在/指纹变化），`call()` 与连接失败分支都改走它，匹配不上的保留原文不隐藏细节；顺带修掉 `permission` 规则漏配 `i` 标志导致 `Permission denied` 落回原文的问题 ｜ 无头 `--dump-dom` 标题无 `ERR`；`#err-demo` 截图确认三类样例文案均被正确翻译（此前第三类落回原文） ｜ 下一单元：打包配置（tauri bundle 基础项）＋ CHANGELOG 0.1 段
- 2026-11-18 ｜ v1.0.0-Alpha5 ｜ S4 第二单元：设置面板（主题 深色/浅色/跟随系统、界面密度、终端字号 11–18 滑块、滚动缓冲 2000/8000/20000），改动即时写入 xterm 并落 localStorage；主题按钮改为深→浅→跟随系统三态循环；修掉一个真 bug：`term` 原本在文件后段才 `let` 声明，设置函数提前调用会踩 TDZ 报 `Script error`，现提前到顶部声明 ｜ 无头 `--dump-dom` 标题恢复为 `Portio`（此前为 `ERR: Script error.`，修复后消失）；1440×900 截图确认面板排版与分段按钮选中态 ｜ 下一单元：错误提示统一（把裸报错文本换成可读话术）
- 2026-11-18 ｜ v1.0.0-Alpha4 ｜ S4 第一单元：快捷键一览浮层（标题栏 `?` 按钮 + `Ctrl + /` 打开、`Esc`/点背景关闭），三组（会话/终端/文件）共 12 条，与真实实现的习惯映射逐条对齐；`set_version.py` 现在一并改写标题栏静态版本标签，杜绝手工同步漏改 ｜ 无头 `--dump-dom` 标题无 `ERR:`；1440×900 截图确认浮层排版（列宽 168px、kbd 胶囊、分组标题）无溢出 ｜ 下一单元：设置页（字号/滚动缓冲/主题全量）
- 2026-11-18 ｜ v1.0.0-Alpha3 ｜ S3 收口：SFTP 协议层（列目录/分块上传下载/建删目录/重命名/进度回调）、应用层 7 个命令、前端远端与本地双栏 + 传输队列进度条 ｜ `cargo build -p portio-app` 通过；`cargo test -p portio-ssh` 全绿；Chrome 无头渲染无报错；实机窗口本地目录已真实列出 ｜ S4：设置页与快捷键全表

## 未验证项（持续登记）

- 真实 SSH 登录会话：无可用测试服务器与凭据，密码/私钥认证、PTY 交互、窗口 resize、tmux/vim 全屏均未实机验证。
- 真实 SFTP 上传下载：仅本地目录列举经实机验证；远端读写需等测试主机。
- 远端到本地真正落地传输的文件完整性（大文件、中文名、断点）未验证。

## 2026-11-18 · v1.0.1-Alpha2 · S6 前置：标题栏图标化 + 滚动条 + 会话栏折叠
- 标题栏四个文字按钮（主题 / 密度 / 设置 / 快捷键）改为内联 SVG 图标，34px 宽，保留 aria-label 与 title，id 不变以免影响既有事件绑定。
- 滚动条统一为主题色细条：6px 宽、thumb 取 --surface-3、hover 取 --text-3、track 透明；深浅主题共用。
- 会话栏可完全折叠：Ctrl+Alt+B 切换，展开态双击分隔把手收起，折叠态单击把手展开；折叠后仅留 10px 把手，箭头默认 55% 不透明、hover 变强调色；状态存 localStorage `portio.sidebarFolded`。
- 踩坑记录：折叠态首版写成 `grid-template-columns:0 1fr`，剩下的唯一子元素落进 0 宽第一列 → 整屏只剩背景；改为单列 `1fr` 才对。
- 顺带清理：删除重复的 `function 初次提示() {}`；快捷键面板补 Ctrl+Alt+B 一条，并把 Ctrl+W 的旧说明改成“关闭当前标签”。
- 验证：`node --check ui/app.js` 通过；Chrome 无头 `--dump-dom` 标题为 `<title>Portio</title>`（无 ERR）；截图 `_s6_fold.png`（1440×900 折叠态，终端+文件双栏铺满、左缘把手可见）、`_s6_icons_zoom.png`（图标按钮 4× 放大）、`_s6_keys_scroll.png`（快捷键面板 + 细滚动条）。
- 未验证：折叠态的单击/双击在真实 Tauri 窗口里的命中率（无头截图无法验证交互），需实机点一次。
- 图标：`scripts/icon_fit.py` 增加 `--margin` 参数并修掉 `global MARGIN` 位置导致的 SyntaxError；用 `--margin 0` 重出全套，128px 实测宽 99.2% / 高 100.0%；安装包与 `target\debug\portio-app.exe` 已内嵌该版本（exe 内 32px 帧占比 93.8%，为圆角损耗）。
- 下一步：截图核对通过后补 S6（会话搜索与分组）的最小交付单元。

## 2026-11-18 · v1.0.1-Alpha3 · 主题图标修正 + 圆角尺度统一 + 会话搜索
- 主题图标：原手写月牙路径弧线参数错，形状残缺；改用标准 `M12 3a6 6 0 0 0 9 9 9 9 0 0 1-9-9Z`，2× DPR 截图核对形状正常。
- 圆角根因（重要）：`ui/index.html` 里到处引用 `var(--r-4/6/8/12)`，但 `ui/tokens.css` 只定义了 `--r-1/2/3`；未定义变量的 `border-radius` 整条声明失效，所以除窗口本身外全是直角。补齐四档令牌，并把面板类补上圆角：`.fp-block` 8px、`.drawer` 顶部 8px。
- 现行圆角口径：4px 控件 / 6px 输入与标签 / 8px 面板 / 12px 浮层；终端画布保持满幅直角（终端惯例，不做卡片化）。
- 会话搜索：`#sess-search` 输入框（新建连接按钮下方），输入即筛选，匹配 `user@host:port` 与备注名；计数显示 `命中/总数`；无命中时给 `.sess-empty` 提示且不误报“还没有会话”；Esc 清空。深链 `#sess-demo&q=web` 可演示过滤。
- 验证：`node --check ui/app.js` 通过；无头 `--dump-dom` 标题 `<title>Portio</title>`（无 ERR）；截图 `_s7_search.png`（查询 web → 1/2、只剩 deploy@web-01）、`_s7_settings.png`（设置面板 12px 圆角、分段控件 6px、按钮 4px）、`_s7_keys.png`、`_s7_fold.png`、`_s6_icons_zoom.png`（月牙形状）。
- 未验证：搜索时键盘上下键跳选（未做）；真实 Tauri 窗口内输入法中文搜索未测。
- 下一步：S6 剩下会话分组/最近使用排序，再做终端字号与主题的运行时联动检查。

## 2026-11-18 · v1.0.1-Alpha4 · 无底板图标（Apple 规范比例）+ 会话列表分组
- 图标：按"只要图形、不要底板"重做。新建 `ui/mark-glyph.svg`：去掉 J7 的底板、描边与投影，只保留"终端+文件"图形本体；用 `translate(17.6 17.6) scale(10.3)` 把图形装进 824×824 安全区，即 1024 画布宽度的 80.5%（Apple 图标内容区比例），四边透明。
- 渲染路径：`ui/mark-glyph.svg` → 包一层透明页 → Chrome `--default-background-color=00000000` 截 1024×1024 → `scripts/icon_fit.py --fix ... --margin 0.10` 出全套（`--margin` 是 0–0.5 的比例而不是百分数，传 10 会算出负的 inner 长度、出一张全透明图，已记录）。
- 实测：`icon.png` 内容 819×737 = 宽 80.0% / 高 72.0%，`32x32.png` 25×23 = 78.1% / 71.9%，与 Apple 的 80.5% 基本一致。
- 会话列表：按 `last` 倒序，分「最近使用」（有使用记录的最近 5 条）与「更早」两组，组标题 11px 弱色；有搜索词时平铺不分组，避免"搜索还给我分组"的割裂感。
- 验证：`node --check` 通过；无头 dump-dom 标题无 ERR；截图 `_s8_groups.png`（最近使用 2 条 / 更早 1 条，计数 3）、`_s7_search.png`（搜索时不分组、1/2）。
- 未验证：透明图标在白色桌面上对比度偏低（右半浅色面板在白底上接近隐形），实际浅色壁纸下观感需用户确认；macOS 的 824 圆角安全区只按比例做了，未出 .icns。
- 下一步：主题与字号运行时联动自检、终端面板圆角是否跟进（待用户确认），然后进 S7。

## 2026-11-18 · v1.0.1-Alpha5~Alpha10 · 图标缓存、右键菜单、图标贴边

### Alpha5 图标缓存脚本 + 安装钩子
- 用户反馈"安装之后桌面图标没有更新"。诊断：快捷方式 `Portio.lnk` 的 IconLocation 已经是 `,0`（取目标 exe 内嵌图标），装的 exe 也已是 Alpha4 —— 不是指向问题，是 Explorer 的 `iconcache_*.db` 分片按"路径+时间"缓存了旧画法。
- `scripts/refresh-icon-cache.ps1`：停 explorer → 删 iconcache_*.db 与旧 IconCache.db → 重启 explorer → `ie4uinit -show`。实跑删掉 15 个分片，`_desktop_glyph.png` 显示新图形。
- `scripts/nsis-hooks.nsh` 的 `NSIS_HOOK_POSTINSTALL` + `tauri.conf.json` 的 `bundle.windows.nsis.installerHooks`，让安装结束自动刷一次。

### Alpha6 四处右键菜单
- 统一 `showCtx/hideCtx` 组件；终端面板、远端文件行、本地文件行、会话行、标签页五处挂 `contextmenu`。
- 终端：复制选中（无选中置灰并显示长度）/ 粘贴 / 全选 / 清屏 / 清空滚动缓冲；新增 `sendRaw`、`pasteInto`。
- 远端文件行：下载到本地 / 进入目录 / 新建文件夹 / 删除 / 复制路径 / 刷新。
- 本地文件行：上传到远端 / 进入目录 / 复制路径 / 刷新。
- 会话行：连接 / 编辑参数 / 复制地址 / 复制 ssh 命令 / 从列表删除。
- 标签页：关闭 / 关闭其它 / 复制标题。
- 深链 `#ctx-demo`、`#ctx-demo-file`、`#ctx-demo-tab`、`#ctx-demo-term` 走真实 handler 派发事件，便于无头截图。

### Alpha7~Alpha9 钩子三处翻车（逐层拆）
1. `nsExec::ExecToLog 'cmd /c taskkill ...'` 在静默安装（/S）下拿不到 explorer 的结果 —— 不再自己拼命令行，整段交给 ps1。
2. ps1 改成随包安装到 `$INSTDIR\scripts\`（`bundle.resources` 映射），钩子里用 `$SYSDIR\WindowsPowerShell\v1.0\powershell.exe` 绝对路径调用。
3. 致命项：ps1 存成 **UTF-8 无 BOM**，钩子走 Windows PowerShell **5.1**，它按 ANSI 读，中文注释全成乱码（`鍋滄 explorer`）→ ParserError 退出 1。改存 UTF-8 带 BOM 后正常。
- 顺带给 ps1 加 `%LOCALAPPDATA%\Portio\_iconhook.log` 时间戳：静默安装没有它，就分不清"没执行"和"执行了没效果"。
- 验证：Alpha9 安装包 `/S` 后 `_iconhook.log` 记 `2026-11-18 10:45:41 开始刷新（PID 14572）`，explorer StartTime 10:29:50→10:45:42。

### Alpha10 图标贴边
- 用户追问"去掉背景后图标又变小了"。原因：Apple 的 80.5% 内容区比例前提是**有底板**——底板定义视觉外框，macOS 再由系统裁圆角；Windows 桌面不裁、直接把 PNG 摊在壁纸上，透明留白就成了"图标更小"。这条规则不该套到无底板图形上。
- 改 `--margin 0.01` 重出：内容包围盒 1003×903 = 宽 97.9% / 高 88.2%。图形自身是圆角窗口形状，贴边不会被看扁。
- 验证：Alpha10 `/S` 安装 → log `10:48:32` → explorer 重启 `10:45:42→10:48:33` → `_desktop_big.png` 与 3× 裁切 `_desktop_big_row.png` 显示体量已与 SQX/Creo 齐平。
- 未验证：浅色壁纸下右半浅色面板的对比度（是否加描边仍未拍板）；交互式（带界面）安装时钩子的 explorer 重启是否会打断安装进度显示。
- 下一步：S7 终端字号/主题运行时联动自检；`docs/backlog.md` 待建；`sftp_rename` 仍是缺口（右键菜单暂无重命名）。

## 2026-11-18 · v1.0.2-Alpha1 · 重命名补齐（远端 + 本地）

- 缺口来源：上一轮右键菜单没有"重命名"，因为后端只有 `Sftp::rename` 没暴露成命令。这轮补齐。
- `sftp_rename(id, from, to)`：直接复用 `Sftp::rename`。注释写明它是"移动+改名"合一，当前只用于同目录改名，跨目录移动留给以后的文件面板。
- `local_rename(from, to)`：`std::fs::rename`，错误带回中文前缀。
- 远端 / 本地文件右键菜单各加"重命名"，prompt 预填当前名；名字未改或取消直接返回；撞名交给服务端报错，前端不吞。
- 版本：按"满 10 进 patch"规则，1.0.1-Alpha10 → 1.0.2-Alpha1。
- 验证：`node --check` 通过；`cargo check -p portio-app` 通过；`cargo test -p portio-core -p portio-ssh` 通过；`_ctx_rename_local.png` 显示菜单含"重命名"；1.0.2-Alpha1 `/S` 安装成功，`_iconhook.log` 记 10:54:50，安装版本读回 1.0.2-Alpha1。
- 未验证：真实 SFTP 改名（无测试主机与凭据），仅协议层 + 编译层验证。
- 下一步：S7 终端字号 / 主题运行时联动自检；`docs/backlog.md` 仍待建。

## 2026-11-18 · v1.0.2-Alpha2 · 启动去黑窗 + 主题图标对齐

- 控制台黑窗：Tauri 模板 `#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]` 只在非 debug 构建里关控制台，我们发的是 `--debug` 包 → 改为无条件 `#![windows_subsystem = "windows"]`。
- 主题图标：双 SVG（深色月亮 / 浅色太阳），两枚按 24 格中心重画；CSS `[data-theme="light"]` 切显隐。踩坑：`.tbtn svg{display:block}`(0,1,1) 压过 `.i-sun`(0,1,0) → 日月同显，选择器必须写 `.tbtn svg.i-sun`。
- 顺带：`#theme-dark` / `#theme-light` 深链锁主题；CHANGELOG 补齐 Alpha2–Alpha10 各版条目，改为"每版一节、可直接作 GitHub Release 文案"；排期文档新增第 10 节进度看板（S1–S14 状态 + 排期外增项 + 版本对照偏差说明）。
- 验证：PE OptionalHeader Subsystem = 2（GUI）；进程树无 conhost / cmd 子进程，仅主窗口 `Portio`；`_tb4_theme-dark.png` / `_tb4_theme-light.png` 4× 截图各只显示一枚图标且与另三枚同轴；`_real_alpha2.png` 实机桌面截图；1.0.2-Alpha2 `/S` 安装成功，`_iconhook.log` 11:04:21，安装版本读回 1.0.2-Alpha2；`cargo test -p portio-core -p portio-ssh` 通过。
- 未验证：真实 SSH/SFTP 能力仍缺测试主机与凭据。
- 下一步：S7 终端字号 / 主题运行时联动自检（改字号作用到已开标签、切主题同步 xterm 配色），随后转 S6 导入器。

## 2026-11-18 · v1.0.2-Alpha4 · 浅色主题标记去深底 + 分隔线/把手重做 + 克制动效

- 浅色主题下标题栏品牌标记原本贴的是 J7-dark 位图（深色底板）→ 改成内联 SVG，颜色走 `--mark-body/--mark-line/--mark-accent` 三个主题令牌：深色主题深底＋亮青，浅色主题浅底＋深青描线，18px 下再无"深色方块"。
- 分隔线：新增 `--line-strong`（dark `#333e4d` / light `#bcc9d5`），落到标题栏下沿、会话栏右边界、面板标题下沿、传输抽屉上沿与状态栏上沿；浅色下结构不再糊在白底里。
- 面板把手：`.gutter-v/.gutter-h` 重做——平时透明，hover 浮出 3px 胶囊，拖拽时胶囊变长变实并去色带；折叠态把手改用 `--line-strong`。`dragWith()` 现在给把手加 `.dragging`，`body.dragging` 期间关掉栅格过渡保证跟手。
- 动效：`.main`/`.stage` 走 `grid-template-columns/rows` 240ms 过渡；`.ctx` 自触点缩放张开；`.modal` 淡入＋`.sheet` 上浮；切标签 `.term-pane.on` 淡入；`prefers-reduced-motion` 下全部退化。
- 验证：`node --check ui/app.js` 通过；Chrome 无头 2× 截 `_p1_light.png` / `_p1_dark.png`，浅色下标记为浅底描线、无深色底板，两套主题结构分隔线均可见；`check_versions.py` OK v1.0.2-Alpha4；提交 `093e4c4`。
- 未验证：把手 hover / 拖拽胶囊与各处动效只按代码路径核对，未做实机拖拽录屏；真实 SSH/SFTP 端到端仍缺测试主机与凭据。
- 下一步：S7 终端字号/主题运行时联动自检；随后 S6 会话导入器（git 导入 ssh config）。
## 2026-11-18 · v1.0.2-Alpha5 · 移除安装期刷图标缓存的 NSIS 钩子

- 用户反馈：安装时重启资源管理器刷图标缓存，会黑屏一段时间，体验很差 → 判定"图标晚一步更新"比"安装黑屏"代价更小，撤掉钩子。
- 改动：`crates/app/tauri.conf.json` 去掉 `bundle.resources`（只装那份 ps1）与 `nsis.installerHooks`；删除 `scripts/nsis-hooks.nsh`；`scripts/refresh-icon-cache.ps1` 保留在仓库，仍可手动跑一次救急。
- 新建 `docs/backlog.md`（排期外点子落点），登记替代方案：快捷方式图标指向按版本命名的 ico 路径，绕过 Windows 的"路径＋时间"缓存，不用重启资源管理器。
- 验证：`json.load` 校验配置合法，`bundle` 下已无那两个键；`cargo` 构建 + NSIS 打包 exit=0；`/S` 静默安装 1.0.2-Alpha5（6.2 秒），安装前后 `explorer.exe` 启动时间均为 11:33:07（没有被重启），`_iconhook.log` 时间戳 11:33:06 未变（钩子确实没执行），安装目录 exe 版本读回 1.0.2-Alpha5；`check_versions.py` OK。
- 未验证 / 已知代价：覆盖安装后桌面图标可能仍是旧画法，要等资源管理器自己刷新缓存；真实 SSH/SFTP 端到端仍缺测试主机与凭据。
- 下一步：S6 会话导入器（从 OpenSSH `~/.ssh/config` 导入，主机 / 端口 / 用户 / 私钥路径映射），先做解析与单测。
## 2026-11-18 · v1.0.2-Alpha6 · S6 第一单元：从 ~/.ssh/config 导入主机

- 解析器 `crates/core/src/sshconfig.rs`：`Host` 块 → `SessionRecord`，映射 HostName / User / Port / IdentityFile；别名当备注名；有 IdentityFile 记 `auth=key` 并把 `~` 按传入的 home 展开；通配符块（`Host *`、`web-*`）、`Match` 块、缺用户名的块跳过并计数；支持 `Key=Value`、行内注释、引号内 `#`、同端点去重。
- 外壳层 `crates/app/src/session_store.rs`：新命令 `sessions_import_ssh_config(path?)`，读 `~/.ssh/config`（可传自定义路径）→ 与磁盘清单合并 → 仅在真有新增时原子写回；抽出可单测的 `import_into_store()`，命令层只剩找路径/读/写。
- 前端：会话栏搜索框下加虚线按钮「导入 ~/.ssh/config」，导入后直接用返回的整份 JSON 刷新内存与列表，提示「导入 N 台主机，跳过 M 项」。
- 验证：`cargo test -p portio-core` 29 passed（新增 9 条）；`cargo test -p portio-app` 3 passed（合并计数 / 重复导入幂等 / 缺文件报错且不污染清单）；`cargo check -p portio-app` 通过；`node --check ui/app.js` 通过；无头 `dump-dom` 标题 `Portio`（无 `ERR:`）且存在 `#btn-import-ssh`；`_s6_import.png` 2× 截图确认按钮位置与虚线样式；打包 exit=0，`check_versions.py` OK v1.0.2-Alpha6。
- 未验证：桌面版里点按钮的 IPC 往返与 toast 文案（无头环境不能 invoke）；本机没有 `~/.ssh/config`（只有 known_hosts），真实文件导入没跑；Xshell / WinSCP 自有格式未做。
- 下一步：Xshell / WinSCP 会话文件导入，或先回 S7 补快速连接模板（`docs/backlog.md` 里已记按版本命名 ico 的发布物料改进）。
## 2026-11-18 · v1.0.2-Alpha7 · 启动不再先黑一下

- 根因：窗口在配置里 `visible: true`，webview 还没画出内容就先露出一块 `backgroundColor #0D1014` 的空窗；用户长期用浅色主题，所以那一下深色特别刺眼。
- 改法：窗口改为 `setup` 里动态建（`WebviewWindowBuilder`），尺寸/最小尺寸/无边框/深色标题栏原样搬过去，并设 `visible(false)` + `.background_color()`；前端首屏画完后调新命令 `window_ready`（`show` + `set_focus`）。`tauri.conf.json` 的 `app.windows` 清空。
- 底色跟随上次主题：新增命令 `ui_theme_set`，前端 `applyTheme()` 每次把实际生效主题写进 `%APPDATA%\io.portio.desktop\theme.txt`；启动时 `read_ui_theme` 读它决定窗口底色（浅 `#F4F7F9` / 深 `#0D1014`）。
- 验证：`cargo check -p portio-app` 通过、`cargo test -p portio-app` 3 passed；实机两轮计时 1733ms / 1830ms 到窗口可见，可见前句柄已在但 `IsWindowVisible=false`；可见瞬间截屏 `_a7_v2_first.png` 即完整界面（标题栏/会话栏/导入按钮/终端都在），无空白或深色空窗帧；`theme.txt` 实测写入 `light`。
- 试过又回退的两版（记录备查）：①在内联脚本里提前 reveal → 290ms 就显示，但窗口下半部还没画，截图里能看到桌面上的别的窗口，属"半成品"帧；②把 xterm 脚本改 `defer` 提前 reveal → 可见时间反而涨到 2423ms。最终选择"藏到画完再显示"。
- 未验证：安装包安装后从桌面快捷方式启动的实际观感（只跑了 `target\debug\portio-app.exe`）；macOS / Linux 上的同等行为。
- 下一步：S6 第二单元 Xshell `.xsh` / WinSCP `.ini` 导入，或 S7 快速连接模板。
## 2026-11-18 · v1.0.2-Alpha8 · 设计规范 + 分隔线 + 拖拽渐变高亮

- 用户明确指出"早该建设计规范"，照办：新增 `docs/design-spec.md`，把精致拆成条款（色彩令牌表 / 圆角阶梯 / 三种线的职责 / 图标 / 间距 / 动效 / 组件条款 / 8 条验收清单 / 现存偏差）。`docs/autopilot.md` 加了 1.1 条：任何 UI 改动先读规范。
- 修"终端与文件栏、终端与抽屉之间分隔线看不见"：gutter 静止态补 1px `--line-strong`（`::before`），浅色 `#bcc9d5` 下可数；折叠态把手不画这条线。
- 拖拽提示改成用户给的参考样式：静止 1px 线 → hover 换 2px 渐变高亮（`linear-gradient` 中段实、22%/78% 处淡出）→ 拖拽 3px + 10px 外发光；横向把手按 90° 同款。原来的 34px 胶囊删除。
- 顺手把颜色收口：`--overlay`、`--shadow-1/2/3`、`--ctx-sep`、`--on-accent`、`--on-danger`、`--term-fg/cursor/selection`、`--ansi-*` 全部进 `tokens.css`；`app.js` 的 16 色终端调色板改为 `cssToken()` 读令牌；`#fff` / `#04100e` 改成令牌；菜单入场动画改用 `--dur` / `--ease`。
- 新增 `scripts/check_design_tokens.py`：扫 `ui/index.html` 与 `ui/app.js`，硬编码 hex / rgb / rgba / hsl 一律报错（会跳过 HTML 实体与纯注释行）。
- 验证：`check_design_tokens.py` → `OK 界面文件没有硬编码色值`；`node --check ui/app.js` 通过；无头 2× 截图 `_sep_rest.png`（五条结构线齐全）、`_sep_hover.png`（渐变高亮 + 外发光，与参考图一致）、`_sep_dark2.png`（深色同款）；打包 exit=0，`check_versions.py` OK v1.0.2-Alpha8。
- 未验证：真实窗口里 hover 手感与拖拽跟手度（无头无法 hover/拖拽，用 `ui/_probe.html` 注入 `opacity:1` 模拟拖拽态截屏，截完已删除该临时文件）。
- 下一步：S6 第二单元 Xshell `.xsh` / WinSCP `.ini` 导入；终端画布是否随规范收圆仍待用户拍板（已记 backlog）。
## 2026-11-18 · v1.0.2-Alpha9 · S6 第三单元：Xshell 会话导入

- 新增 `crates/core/src/xshell.rs`：`parse_xshell_session(text, fallback_name)` 解析 `.xsh`（INI 结构）。取 `Host` / `Port` / `Protocol` / `UserName` / `UserKey`（→ `auth=key`）/ `Name`；键名大小写不敏感、值可带引号、`;` 与 `#` 整行注释跳过；`Protocol` 非 `S`（RDP/Serial）或主机、账号缺任一 → 返回 `None`（跳过）。密码字段完全不读。5 条单测。
- 外壳 `session_store.rs` 新增 `sessions_import_xshell(app, dir?)`：`dir` 为空时走 `%APPDATA%\NetSarang\Xshell\Sessions`，目录不存在直接报错；读旧清单 → 合并 → 有新增才原子写回；返回 `ImportReport{json,added,skipped,source}`。可单测的 `import_xshell_dir` 用栈式遍历含子目录（用户常按分组建文件夹），只收 `.xsh`，坏记录单独计数。1 条单测（临时目录：2 台 SSH＋1 个 RDP＋1 个子目录会话，断言 added=2 / skipped=1 / 子目录会话用文件名 `db-01` 当备注名）。
- `lib.rs` 注册 `sessions_import_xshell`；`ui/index.html` 会话栏加第二个虚线按钮「导入 Xshell 会话」；`ui/app.js` 加对应 handler（照 ssh config 那条写，成功/无新增/失败三种 toast 文案）。
- 验证：`cargo test -p portio-core` 34 passed（含 xshell 5 条）；`cargo test -p portio-app` 4 passed（含 xshell 目录 1 条）；`cargo check` 全绿；`node --check ui/app.js` exit 0；`check_design_tokens.py` → OK（新按钮沿用 `.sess-import`，未引入新色值）；无头 2× 截图 `_s6_xshell.png`（浅色）确认两个导入按钮同时在会话栏且样式一致、`<title>` 仍是 `Portio`（无 `ERR:`）。
- 未验证：真实 Xshell 会话目录（本机未装 Xshell，`%APPDATA%\NetSarang\Xshell\Sessions` 不存在）；桌面版点击按钮后的 IPC 往返与 toast；带密码字段的 `.xsh` 真样本（只用构造样例覆盖）。
- 下一步：S6 收尾单元 WinSCP `.ini` 导入；之后 S7 会话分组 / S8 设置项。
## 2026-11-18 · v1.0.2-Alpha10 · S6 收尾单元：WinSCP .ini 导入

- 新增 `crates/core/src/winscp.rs`：`parse_winscp_ini(text) -> ImportOutcome`。按段解析，只认 `[Sessions\...]`；取 `HostName` / `UserName` / `PortNumber` / `FSProtocol` / `PublicKeyFile`|`KeyFilePath`（→ `auth=key`）。`FSProtocol` 3 以上（FTP/WebDAV/S3）与非会话段不计入记录，前者计入 skipped、后者不计；`[Sessions\分组\主机]` 的组名用 ` / ` 并入备注名；缺主机或缺账号跳过；密码不读。5 条单测。
- 外壳 `session_store.rs` 新增 `sessions_import_winscp(app, path?)` 与可单测的 `import_winscp_file`。`path` 为空时按 `%APPDATA%\WinSCP.ini` → `%LOCALAPPDATA%\WinSCP.ini` → `文档\WinSCP.ini` 顺序找第一份存在的，全都没有就把试过的路径列出来报错（本机暂无文件选择对话框，登记为后续项）。有新增才原子写回。1 条 app 单测。
- `lib.rs` 注册命令；`ui/index.html` 加第三个虚线按钮「导入 WinSCP 站点」；`ui/app.js` 加 handler。
- 验证：`cargo test -p portio-core` 39 passed（winscp 5 条）；`cargo test -p portio-app` 5 passed（winscp 1 条：1 个 SSH＋1 个 FTP → added=1 / skipped=1）；`node --check ui/app.js` 0；`check_design_tokens.py` OK；无头 2× 截图 `_s6_winscp.png` 三个导入按钮同排、样式一致；`#theme-dark` dump-dom 的 `<title>` 仍 `Portio`（无 `ERR:`）。
- 未验证：真实 `WinSCP.ini`（本机未装 WinSCP，三条候选路径都无文件）；桌面版点击按钮的 IPC 与 toast；「30 条真实会话」这条 S6 完成定义仍缺样本。
- 下一步：S7 会话分组（按项目分组、组内折叠）与 S8 设置项；下一步版本按规则进到 1.0.3-Alpha1。
## 2026-11-18 · v1.0.3-Alpha1 · S7 第一单元：快速连接

- 新增会话栏「快速连接」一行（`#quick-input` + `#btn-quick`）：输入 `user@host:port` 回车或点 ↵ 即打开连接面板并预填。`parseQuickSpec(text, records)` 处理 `ssh://` 前缀、尾随路径、`lastIndexOf("@")` 拆用户、`[::1]:2222` 方括号 IPv6、缺端口按 22；同主机旧记录当模板带出端口 / 认证方式 / 私钥路径，密码仍现填、不进任何存储。
- 顺手修老 Bug：`.field{display:grid}` 压过 `[hidden]`，导致选「私钥文件」时密码框仍显示；补 `.field[hidden]{display:none}`。
- 前端版本号随 `set_version.py` 变成 1.0.3-Alpha1（Alpha10 满位进 patch 回 Alpha1，符合既定规则）。
- 验证：`node --check ui/app.js` exit 0；`check_design_tokens.py` → OK（快速连接行只用既有令牌）；无头 2× 截图 `_s7_quick2.png`（1180×690 深色：输入框里 `deploy@10.0.8.12:2222`，面板预填主机 10.0.8.12 / 端口 2222 / 用户 deploy / 私钥文件 / `~/.ssh/id_ed25519`，密码框已不显示）、`_s7_light.png`（浅色：快速连接行正常）；`#quick-demo` 的 dump-dom 无 `ERR:`。
- 未验证：真实回车 → 面板 → 连接的全链路（本机无 SSH 服务器，连接仍属已知阻塞）；真实窗口里的焦点落位。
- 下一步：S7 剩余——发布物料（v0.2 gate 材料）与模板补强；之后进 S8（SFTP 通道复用已有 SSH 连接）。
## 2026-11-18 · v1.0.3-Alpha2 · 会话分组与折叠（补 S5 的 2.2）

- `ui/app.js` 新增分组层：`GROUPS_KEY=portio.groups`（会话 key → 分组名）、`GFOLD_KEY=portio.foldGroups`（折叠中的组名数组，注意与既有的 `FOLD_KEY=portio.sidebarFolded` 重名，已改名）；`groupsOf / setGroups / isFolded / toggleFold / caret` 五个小函数。
- `renderSessions` 分组逻辑改为：有搜索词仍平铺；无搜索词时先把带分组的会话按组名排（`localeCompare("zh")`）成组，剩下的进「未分组」；一条分组都没有时回落到原来的「最近使用 / 更早」。
- 分组标题：caret ▾ / 折叠时 `rotate(-90deg)` 变 ▸；hover 或折叠时才露出条数（`gcount`）；点击折叠、右键「展开/收起」+「解散这个分组」（「未分组」不给解散项）。
- 会话行右键新增：`分到分组…`（打开 `#group-modal` 小弹层，回车即确认）、最多 3 个已有分组的一键归类项、`移出分组`。
- 验证：`node --check ui/app.js` exit 0（第一次跑出 `Identifier 'FOLD_KEY' has already been declared`，改名 GFOLD_KEY 后通过）；`check_design_tokens.py` OK；无头 2× 截图 `_s7_groups.png`（1180×690 深色：测试组折叠只剩标题+条数 1、生产组展开两行 dba@db-01.prod:2222 与 deploy@web-01.prod key、未分组一行 root@10.0.8.12）；`#groups-demo` dump-dom `<title>` 仍是 `Portio`。
- 未验证：真实右键菜单点击、弹层输入与回车（无头不能交互）；分组在真实窗口下的折叠动画手感；分组数据在软件升级后是否沿用旧 localStorage（未实测）。
- 下一步：S7 收尾——发布物料（README / 更新说明 / 截图），之后进 S8（SFTP 通道复用已有 SSH 连接）。
## 2026-11-18 · v1.0.3-Alpha3 · S7 收尾：发布物料（README）

- `README.md` 整体重写为用户视角：这是什么 / Windows 安装（含 WebView2 前提）/ 三种连接入口（新建、快速连接、双击会话）/ 主机指纹策略（变了就停手，不为跑通降标准）/ 三种迁移导入各自的读取路径与跳过规则 / 会话分组用法 / 界面设定（密度、字号、滚动缓冲）/ 快捷键表 / 四版进度与版本号规则 / 开发与出包命令。
- 去掉过期描述「当前进度 v0.0.1-skeleton」；修正「排期」的坏链接（排期文档在仓库外，改成不链接的表述）。
- 顺手把快捷键浮层里 `Ctrl+W` 的旧说明（"多标签在后续版本接入"）改成"关闭当前标签（最后一个不关）"——多标签早在 Alpha 阶段就接了，说明没跟上。
- 验证：README 里每条说法都对着代码核过（`Ctrl+T/W//`、`Ctrl+Alt+B/H`、`F5` 的实现在 `ui/app.js` 392–412 与 1300 行附近；三个导入路径与 `session_store.rs` 里的候选顺序一致；`node --check ui/app.js` exit 0；`check_design_tokens.py` OK；无头 dump-dom `#theme-light` 的 `<title>` 仍 `Portio`，无 `ERR:`）。
- 未验证：文档里的安装/首次连接步骤没有在"干净机器 + 真实 SSH 服务器"上走一遍（仍受「无测试服务器」限制）。
- 下一步：S8 —— SFTP 通道复用已有 SSH 连接（同一连接开文件通道，不二次鉴权）。
## 2026-11-18 · v1.0.3-Alpha4 · 修三处布局缺陷（分界线粗细 / 标题条高度 / 缩放错位）

- 分界线粗细不一：`.sidebar` 自带 `border-right:1px`，把手又画一条 1px，两线叠加在会话栏右界；终端/文件那条只有一条，于是粗细不同。改法：去掉 `.sidebar` 的 `border-right`，两条分界统一由同一个 `.gutter-v::before` 画。
- 标题条高度不统一：`.pane-head` 写死 28px、`.drawer-head` 30px、`.sidebar h2` 8px 上下内边距（实测 32px）。改法：三者统一 `height:var(--row)`（标准 28 / 紧凑 24），`h2` 改成 `padding:0 12px` 垂直居中；compact 密度里那条单独 `.pane-head{height:24px}` 覆盖删掉（`--row` 已经管到）。
- 窗口缩小错位：把手原来绝对定位、由 JS 拿 `--sidebar` / `--split` 算像素贴边；栅格被夹取时（`.split` 右侧 `minmax(340px,1fr)`、窄窗口）算出来的位置和真实边界不一，只有 resize 补偿才对齐。改法：`.main` 改 `var(--sidebar) 0 1fr`、`.split` 改 `minmax(360px,var(--split,50%)) 0 minmax(340px,1fr)`，把把手放进那条 0 宽轨并 `margin-left:-4px` 自行溢出；横向把手改 `top:calc(100% - var(--drawer))`。JS 的 `positionGutters()` 及其 resize 监听、各 apply* 里的调用全部删除。
- 顺带：`.fp` 的远端/本地分隔从 `--line` 提到 `--line-strong`（规范第 4 节要求区域分界用 strong）；`design-spec.md` 组件条款新增「面板标题条」「把手定位」两条，偏差表新增 7/8/9 三条并标已修。
- 验证：真几何量测（临时 `_probe.html` 用 iframe + `getBoundingClientRect` 写进 `<title>`，读完即删）：1180×690 下 `pane-head` 28/28、`fp-bar` 28、`drawer-head` 28、`sidebar h2` 28；`gutter-v` 与 `sidebar.right` dx=0.00、`gutter-split` 与 `panes` 交界 dx=0.00、`gutter-h` 与 `drawer.top` dx=0.00。窄到 700px 时同样 dx=0.00（旧实现此例会偏）。折叠态量测：sidebar 0、gutter 0–10、stage 10–1180。截图 `_s9_dark.png`（1440×900@2x）、`_s9_light.png`（1180×690@2x）、`_s9_fold.png`（折叠态）；两条竖线 6× 裁切对比 `_s9_line_side.png` / `_s9_line_split.png` 宽度一致；`node --check ui/app.js` exit 0；`check_design_tokens.py` OK；`cargo test -p portio-core` / `-p portio-app` 均 ok；无头 dump-dom `<title>` 仍 `Portio`。
- 未验证：真实窗口里 hover/拖拽的手感与渐变高亮实拖（无头不能 hover/拖拽），只验证了静止态几何与折叠态。
- 下一步：S8 —— SFTP 通道复用已有 SSH 连接。
## 2026-11-18 · v1.0.3-Alpha5 · 设计规范升级 v2「全覆盖」+ 43 处裸数字收进刻度

**用户要求**：设计规范应覆盖软件所有界面元素和各种方面（间距、对齐方式等等），"而不是发现一个补一个，如果覆盖不全面，那就说明规范本身就是有问题的"（这是用户第 3 次强调规范）。

- 规范 v2 重写（`docs/design-spec.md`，130 行 v1 → 约 250 行）：
  - 新增 §0 适用范围；§3 尺度令牌表（间距 `--sp-1..--sp-6` = 4/8/12/16/24、控件三档 `--ctl/--ctl-2/--ctl-3` = 26/30/32、圆角 `--r-full` 胶囊 / `--r-hair` 发丝、字号四档、图标 16/18、线 1px、把手 9、滚动条 6）；
  - 新增 §4 对齐规则（同一行垂直居中、面板 12 / 行内控件 8 / 行内文字 12、同层左缘重合、右侧动作 `margin-left:auto` + gap 4、图标盒居中、单行截断、数字右对齐 `--mono`、分组靠 caret 不靠缩进）；
  - 新增 §9 状态矩阵（默认 / hover / active 选中 / focus / disabled / 拖拽中 / 加载 七态各自视觉）；
  - 新增 §10 **31 条元素覆盖矩阵**：窗口本体、标题栏、标签条、会话栏、会话栏标题、主按钮、快速连接行、搜索框、三枚导入按钮、空态、分组标题、会话行、右键菜单、终端标题条、终端画布、文件标题条、远端/本地块、文件栏工具条、文件行、传输抽屉、进度条、状态栏、toast、四类模态、表单字段、分段控件、滑块、键位表、滚动条、把手、窗口控制按钮——每条写清层级与关键条款；
  - 新增 §11 文案条款；§14 变更流程写明"新增界面元素必须先在 §10 加一行再写代码，没进矩阵的元素不接受"；
  - §12 偏差表补到 11 条（新增「规范只覆盖出过问题的几处」并标已修）；§13 验收清单 11 条（两个守卫脚本 + 四态截图 + 结构线/标题条/圆角/图标/状态/动效自检 + 实机截屏）。
- `ui/tokens.css` 新增 `--r-full:999px`、`--r-hair:2px`、`--ctl:26px`、`--ctl-2:30px`、`--ctl-3:32px`、`--sp-1..--sp-6`。
- 新增 `scripts/check_ui_scale.py`：扫 `ui/index.html` 与 `ui/app.js`，`font-size` 必须 `var(--fs-*)`、`border-radius` 必须 `var(--r-*)` 或 50%、`padding/margin/gap` 必须落在 `0/1/2/4/8/12/16/24`、`height` 只认 `--row/--ctl*/发丝档`、`width` 认刻度或 4 的倍数；命中打印 `path:line` 并退出码 1。
- 首跑报 **43 处**裸数字，逐处改到令牌：titlebar gap 10→8 / padding-left 10→12、tab 与 tbtn 左右内边距 10→12、tbtn svg 15→16、滚动条拇指 `3px`→`--r-full`、`sidebar h2` gap 6→8、`kbd` 圆角 `4px`→`--r-1` + padding `1px 5px`→`1px 4px`、空态 `font-size:12px`→`--fs-12`、drawer-head gap 10→8、状态栏 `.state` gap 6→8 与圆点 7→8、紧凑面板 padding `8 10`→`8 12`、终端画布 padding `6 0 0 8`→`4 0 0 8`、fp-bar gap 6→4、fp-row 列 `14/82`→`16/80` + gap 6→4、fp-list hint padding 10→12、传输进度条 `2px`→`--r-hair`、来源表单 gap 10→12、输入 `padding:7 9`→`0 12` + 高 32→`--ctl-3`、`.row` gap 10→12、`.btn` padding `7 14`→`8 12`、new-session margin `10 12 0`→`12 12 0` + 高 30→`--ctl-2`、搜索框 margin `6 12 2`→`4 12 4` + 高 26→`--ctl`、快速连接 gap 6→4 + margin →`8 12 0` + 输入/键钮 26→`--ctl`、导入按钮 margin →`4 12 4` + 高→`--ctl`、空态 padding `20 16`→`24 16`、右键菜单项 gap 10→8 + 高→`--ctl`、菜单分组线 margin `4 6`→`4 8`、分组标题 gap 6→8 + margin `14 12 4`→`12 12 4`、会话行 30→`--ctl-2`、键位表组 `padding:10 16 2`→`12 16 4` / 行 `7 16`→`8 16` / kbd `1 6`→`1 4`、toast padding `6 14`→`8 12`。
- 收尾把图标 16、状态点 8 这两个合法档补进脚本白名单（图标尺寸与圆点直径不是间距），脚本从报 2 处转为 OK。
- `docs/autopilot.md` 第 1.1 条改写：规范是 v2 全覆盖版，新增元素先入矩阵，改完两个脚本都要跑。

**验证证据**
- `python scripts/check_ui_scale.py` → `OK 界面尺度全部走令牌与刻度（tokens.css）`（改前 43 处）。
- `python scripts/check_design_tokens.py` → `OK 界面文件没有硬编码色值（令牌来源：ui/tokens.css）`。
- `node --check ui/app.js` → exit 0。
- 无头 dump-dom `<title>` = `Portio`（无 `ERR:`）。
- 真几何量测（临时 `_probe.html`，iframe + `getBoundingClientRect` 写进 `<title>`，读完即删）：`paneHeadTerm=28`、`paneHeadFiles=28`、`drawerHead=28`、`sidebarH2=28`（四条标题条一致）、`newSession=30`、`sessSearch=26`、`importBtn=26`（三档控件各就位）、`titlebar=38`、`statusbar=26`、`tbtnW=34`、`icon=16`（图标 15→16 已生效）。
- 截图（2× DPR）：`_a5_dark.png`（1440×900 #theme-dark）、`_a5_light.png`（1180×690 #theme-light）、`_a5_settings.png`（1440×900 #settings）、`_a5_small.png`（1024×620 浅色）——五条结构线在浅深两态都可见，四条标题条齐平，面板圆角与内嵌控件圆角同族。
- `cargo test -p portio-core` / `-p portio-app`：本轮只动前端与文档，未重跑（上一轮均 ok）。

**未验证**
- 无头环境不能 hover / 拖拽 / 右键，把手的渐变高亮与拖拽手感仍未实机验证。
- 真实登录会话、PTY 交互、tmux 全屏、真实 SFTP 上传下载仍无测试服务器（登记在案的已知阻塞）。
- 终端画布是否随规范收圆：仍待用户拍板（`docs/backlog.md`）。

**下一步**：S8 —— SFTP 通道复用已有 SSH 连接（同一连接开文件通道，不二次鉴权）；同时把本轮出的 NSIS 包交付。
## 2026-11-18 · v1.0.3-Alpha6 · 导入收进下拉 + 标题栏拖动区放宽

**用户要求**（原话）：导入的界面改成下拉，"不要留几个常驻的在那里占位置"；标题栏拖动区域太小，"拖动窗口很难"。

- **导入下拉**：会话栏里原来的三枚常驻虚线按钮（`~/.ssh/config` / Xshell / WinSCP）各占 26px 高＋上下各 4px 外边距，合计挤掉约 100px 的列表高度。现在收成一个 `#btn-import` 触发器（下载图标 + 「导入会话」+ chevron）＋ `#import-menu` 三项菜单，每项右侧用 `--mono` 标出来源（`~/.ssh/config` / `Sessions` / `WinSCP.ini`）。三个菜单项的 id 沿用 `btn-import-ssh` / `btn-import-xshell` / `btn-import-winscp`，原导入逻辑一行未改。
- 交互：点触发器开合（`aria-expanded` 同步）；点页面别处、按 Esc、以及选完任一项后都收起（三个导入 handler 开头各加一行 `setImportOpen(false)`）。
- **标题栏拖动区**：原来只有 `.brand` 与品牌文字挂 `data-tauri-drag-region`，而 `.tabs` 是 `flex:1` 占满整条中间，却没有拖动标记——于是标题栏最宽的一段点下去没反应，只剩左边几十像素能拖。现在 `.tabs`（标签条背景）、版本号 `span` 都挂上拖动区；标签项与图标按钮是子元素、没有标记，点击行为不受影响。双击空白由 Tauri 处理为最大化。
- 顺手修 `scripts/set_version.py`：版本号 span 加上 `data-tauri-drag-region` 后原正则 `<span class="ver">[^<]*</span>` 不再匹配，进位脚本会静默失败（本轮第一次跑就报了「没找到版本字段」）。正则改成 `<span class="ver"([^>]*)>[^<]*</span>` 并回填属性，属性顺序不会再被吃掉。
- 设计规范同步：§10 矩阵第 2 行（标题栏）补拖动区条款，第 9 行从「导入按钮（虚线 3 枚）」改写为「导入下拉（一处入口 + 三来源）」，写清触发器与菜单的材质和收起规则。

**验证证据**
- `python scripts/check_ui_scale.py` → OK；`python scripts/check_design_tokens.py` → OK；`node --check ui/app.js` → exit 0。
- 无头截图（1180×690 @2x）：`_a6_import_closed.png`（收起态：一行 `导入会话`，列表高度回补）、`_a6_open2.png`（浅色展开：菜单三项带来源路径、触发器转强调色边框、chevron 朝上）、`_a6_open2_dark.png`（深色展开同一形态）。
- 排查记录（避免下轮重踩）：展开态最初把 `background` 一起写进 `transition` 并在展开时换成 `--surface-3`，无头实测浅色下触发器被算成深色 `rgb(26,32,41)`（菜单里同一个令牌却是浅色），肉眼就是一整条黑。改成「展开态只换边框与图标颜色、背景不动，过渡列表里去掉 `background` 简写」后恢复正常。定论：**不要把 `background` 简写放进 transition 再配 var() 令牌做状态切换**。
- `set_version.py` 修好后 `python scripts/set_version.py 1.0.3-Alpha6` 输出「已写入：ui/index.html」，`check_versions.py` → `OK v1.0.3-Alpha6`。
- 临时文件 `ui/_imp.html`、`ui/_p2.html` 用完已删（`.gitignore` 不覆盖 html，必须删）。

**未验证**
- 标题栏拖动与双击最大化只做到「拖动区标记已覆盖整条空白」这一层，真实拖拽手感需在实机窗口里由用户确认（无头环境无法拖动窗口）。
- 已知阻塞不变：真实 SSH/SFTP 端到端、PTY、tmux 无测试服务器。

**下一步**：出 Alpha6 安装包并交付；之后进 S8 —— SFTP 通道复用已有 SSH 连接。
## 2026-11-18 · v1.0.3-Alpha7 · S9：远端文件列表权限列

排期 S9 的完成定义是「双栏浏览、路径与权限、中文文件名」，双栏与重命名早前已做，缺的是**权限**与中文名专项。本轮先做权限列这个最小单元。

- 数据源：`crates/ssh/src/sftp.rs` 的 `RemoteEntry` 加 `perm: Option<u32>`，取 SFTP `readdir` 返回的 `FileAttributes.permissions`，不需要额外 `stat` 往返，也没有多开通道。
- 展示：新增 `perm_string(perm, is_dir)`，把 mode 排成 `ls -l` 那串 10 位——首字符 d/-，后接三组 rwx；服务器没给时返回 `—`。
- 外壳：`FileItem` 加 `perm: String`，远端走 `perm_string`，本地固定 `—`（Windows 无 POSIX 位）。
- 前端：`renderList(el, items, side)` 在 `side === "remote"` 时多给一列 `.pm`，行上带 `has-perm` 类改用五列栅格 `16 / 1fr / 68 / 64 / 80`；本地行仍是四列，两栏不对齐是刻意的（本地没有这一列）。
- 规范同步：§10 矩阵第 19 行「文件行」补远端权限列条款（列宽、字号、对齐、缺省 `—`、本地不显示）。

**验证证据**
- `cargo test -p portio-ssh perm` → `test sftp::tests::perm_string_renders_rwx ... ok`（覆盖 0755 / 0644 / 000 / 777 / 750 / None 六组）。
- `check_ui_scale.py` OK、`check_design_tokens.py` OK、`node --check ui/app.js` exit 0。
- 无头截图（1180×690 @2x，塞了 5 条远端样本 + 2 条本地样本）：`_pm_light.png` / `_pm_dark.png`——权限串对齐、`—` 不缺列、本地栏确实只有四列。
- 临时页 `ui/_pm.html` 与脚本 `_pm.py` 用完已删。

**未验证**
- 真实主机上的 readdir 是否真的带 `permissions` 字段（OpenSSH sftp-server 通常带，russh 的 `meta.permissions` 为 `Option`，拿不到就退化 `—`）。无测试服务器，只能登记。

**下一步**：S9 中文名目录专项（本机造中文目录 + 回环验证），之后 S10 断点续传。
## 2026-11-18 · v1.0.3-Alpha8 · S9：中文名与特殊字符路径回归

S9 剩的最后一个卡点是「中文文件名」。真实 SFTP 侧要有服务器才能验，先把它拆成能验的部分：本地目录列举 + 路径拼接。

- `crates/app/src/sessions.rs`：`local_list` 里的读目录逻辑抽成 `list_local_dir(&Path)`，命令只负责选路径。抽出来是为了能单测，行为一字未改。
- 新增测试 `local_list_keeps_chinese_and_special_names`：在系统临时目录里造 `文档 汇总` / `报表#2026` / `配置&参考.yaml` / `会话记录 中文.txt`，断言
  1) 名字原样返回（含空格、`#`、`&`）；2) 目录排在文件前、同类按名字小写序；3) 目录 `size` 为 0、文件是真实大小；4) 本地行 `perm` 全是 `—`；5) `path` 结尾也是原样中文。
  跑完自删临时目录。
- `crates/ssh/src/sftp.rs` 补 `join_keeps_chinese_names`：中文名字进 `join` / `parent_of`，确认远端拼接只认 `/`，不会把中文或空格吃掉。
- 顺带核对前后端拼路径的实际用法（不改代码）：下载用 `winJoin(localPath, name)`、上传与建目录用 `posixJoin(remotePath, name)`，本地 `\`、远端 `/` 没有串用。

**环境异常（本轮特别记录）**
- 机器已锁屏（截到的首帧是锁屏界面，时间 17:18），**实机窗口截屏与界面点检本轮做不了**，因此本轮只做不依赖 GUI 的部分；启动过的实例已 `Stop-Process` 收掉。若后续轮次仍锁屏，继续挑代码层 / 无头层能收口的单元，不要反复去点 GUI。

**验证证据**
- `cargo test -p portio-app -p portio-ssh`：portio-app 6 passed（新增中文名测试在内）、portio-ssh 9 passed（新增中文拼接）、target 集成测试 1 passed，全绿。
- 本轮无 UI 改动，未跑截图；两个守卫脚本不涉及。

**未验证**
- 真实主机上的中文名上传 / 下载、中文名远端目录进出（无服务器）。
- 实机界面在中文目录下的观感（锁屏，未截屏）。

**下一步**：S10 断点续传（传输队列已有逐块进度，缺的是断开后从断点续传）。
## 2026-11-18 · v1.0.3-Alpha9 · S10：下载断点续传

S10 的完成定义是「断网后恢复继续传，进度与速率准确」。本轮先收下载方向——它是半截文件最容易留下的地方。

- `crates/ssh/src/resume.rs`（新）：`part_path(local)` 与 `resume_offset(part_len, remote_size)` 两个纯函数，把"临时文件叫什么、从哪续"从传输主流程里拆出来，这样不用连服务器就能测。
- 半截文件名从 `local.with_extension("portio-part")` 改成 `原名 + ".portio-part"`。旧写法对 `备份.tar.gz` 会产出 `备份.tar.portio-part`，扩展名被吃掉，用户根本对不上号；带中文/`#` 的名字也一样不该被改写。
- 续与不续的判定（写死在测试里）：`part_len == 0` 从头；`part_len < remote_size` 续；`part_len >= remote_size` 从头（等于时说明上次其实传完了没改名，续下去会一直卡在 0 字节）；`remote_size == 0`（metadata 没给大小）不敢续，从头。
- `download`：先读半截文件长度 → 算偏移 → 能续就 `OpenOptions.append` 打半截文件 + 远端 `seek(SeekFrom::Start(offset))`；不能续且半截文件存在 → 删掉它，重新 `create`。进度起始值直接给 `start`，进度条不会先跳 0 再涨。
- `crates/ssh/src/lib.rs` 导出 `part_path`、`resume_offset`。

**验证证据**
- `cargo test -p portio-app -p portio-ssh` 全绿：portio-app 6 passed；portio-ssh **12 passed**（新增 3 条：`part_path_keeps_full_name`、`resume_only_when_part_is_smaller`、`appending_rest_rebuilds_whole_file`）；target 集成 1 passed。
- 回环测试 `appending_rest_rebuilds_whole_file`：造 300 字节源，先把前 120 字节写成半截文件，算出偏移 120、追加剩余 200 字节，改名后逐字节比对与源一致——这就是"续传补完"的最小证据链。
- 本轮无 UI 改动；机器仍锁屏（首帧是锁屏界面），实机窗口点检未做。

**未验证**
- 真实断网/断连后的恢复续传（无服务器，只能协议层与本地回环）。
- 上传方向的断点续传未实现。
- 半截文件在真实目录里的观感与清理策略（要不要给用户"清理未完成传输"入口）——记进 backlog，等下一轮或用户拍板。

**下一步**：S10 第二半——上传断点续传（远端 `.portio-part` + 远端 stat 定偏移）。
## 2026-11-18 · v1.0.3-Alpha10 · S10：上传断点续传

上轮把下载方向收了，这轮收上传——S10 的「断点续传」两个方向到这一轮齐了。

- `resume::remote_part_path(remote)`：远端半截文件名 `/dir/名.portio-part`。刻意用字符串拼接而不是 `PathBuf`：远端是 posix 路径，Windows 上 `PathBuf` 会把 `/` 折成 `\`，拼出来的路径到服务器上就不存在了。
- `upload` 流程：读本地大小 → 远端 `metadata(tmp)` 拿半截长度 → `resume_offset` 判能不能续 → 不能续且半截存在就 `remove_file` 删掉重来 → 能续就本地 `seek` 跳过已传部分、远端 `open_with_flags(WRITE)` + `seek` 定位。
- 一个关键取舍：续传时**不能用 `create`** 打开远端半截文件，`create` 带 TRUNC，会把已经传上去的那段截掉，等于白续；所以续传走 `open_with_flags(OpenFlags::WRITE)`。
- 收尾：`flush` → `rename(tmp, remote)`。OpenSSH 的 `rename` 覆盖同名文件是可以的，但其他实现会报失败，所以失败时先 `remove_file(remote)` 再改名一次。
- 进度起始值给 `start`，界面进度条从断点开始，不跳 0。

**验证证据**
- `cargo test -p portio-app -p portio-ssh` 全绿：portio-app 6 passed；portio-ssh **14 passed**（本轮新增 2 条：`remote_part_stays_posix_and_keeps_name`、`skipping_source_head_then_appending_rebuilds_whole_file`）；target 集成 1 passed。
- `skipping_source_head_then_appending_rebuilds_whole_file`：300 字节源，服务器侧只到了前 120 字节，本地 `seek(120)` 后把剩余 200 字节接上，逐字节比对等于源——上传续传的最小证据链。
- `remote_part_stays_posix_and_keeps_name`：`/home/deploy/备份.tar.gz` → `/home/deploy/备份.tar.gz.portio-part`，并断言结果里没有 `\`。
- 本轮无 UI 改动；机器仍锁屏，实机点检未做。

**未验证**
- 真实断网后恢复续传（协议层与本地回环之外的部分）。
- 远端 `.portio-part` 出现在目录列表里的观感、以及要不要给它"未完成"标记 / 清理按钮——已记进 backlog，等用户拍板。
- `open_with_flags(WRITE)` + `seek` 在真实服务器上的行为（尤其是不支持随机写的实现）。

**下一步**：S10 收口——远端半截文件的 UI 处理（列表里标记"未完成"并可清理），或转 S11 凭据加密存储。
## 2026-11-18 · v1.0.4-Alpha1 · S11：口令加密存储（地基）

S10 之后按看板进 S11「安全与凭据」。S11 有两块：口令加密落盘、指纹管理界面。本轮只做第一块的加密层，而且刻意只做到"能测、能复用"为止，接线留到下一轮。

- `crates/core/src/vault.rs`（新）：`Vault::from_secret` 用 HKDF-SHA256 把本地主密钥派生成 AES-256-GCM 密钥；`seal` 输出 `nonce(12) || 密文`，`open` 解回来。选 AEAD 而不是"加密+哈希校验"是因为 AEAD 自带完整性，改一个字节就解不开。
- `CredentialStore`：`entries` 以会话 id 为键（同一主机换账号是两回事，不能拿主机名当键）；`flush` 先写 `.json.tmp` 再改名，断电不会留下半个 JSON；`parse_credentials` 遇到版本号不认识或 hex 不合法要报错，不做"当空处理"。
- 空口令按"清除"处理：`set_password(id, "")` 直接删条目，避免存上去一个空密码，下次连接拿着空串去认证。
- 主密钥：`load_or_create_master_secret` 首次生成 32 字节随机写盘，之后复用；POSIX 上收 0600，Windows 依赖用户目录 ACL（再强的隔离得走系统钥匙串，写进 docs 与代码注释）。
- 依赖：只用工程图上已有的 `ring`（russh 的 ring 特性已经把它带进来），没有为这件事新增加密库，`Cargo.lock` 只多了 `portio-core → ring` 一条依赖边。

**能力边界（如实写进代码注释与 CHANGELOG）**
- 主密钥与密文同机，能读本机文件的人就能解出口令。这层防的是"明文被同步盘/打包/日志带走"，不是本地提权。要更强需要把主密钥交给 Windows Credential Manager / macOS Keychain，接口层不用改。

**验证证据**
- `cargo test -p portio-core`：**47 passed / 0 failed**，其中本轮新增 8 条：`seal_then_open_roundtrips`（含中文口令、断言明文片段不出现在密文里）、`same_plaintext_stays_same`（两次密文不同、都能解回原值）、`tampered_ciphertext_is_rejected`（改 1 字节与截断都返回 `Open`）、`wrong_master_secret_cannot_open`、`store_persists_and_forgets`（落盘→重开读回→文件里搜不到明文→删除生效）、`empty_password_clears_instead_of_storing_blank`、`broken_file_is_reported_not_silently_empty`（坏 JSON / 版本 9 都报 `Format`）、`master_secret_is_created_once_then_reused`。
- `store_persists_and_forgets` 里的关键断言：读回后 `std::fs::read_to_string(path)` 里搜不到 `pw-1` 与 `pw-2-中文`——口令确实没有以明文落在磁盘上。
- 本轮无 UI 改动；机器仍锁屏，实机点检未做。

**未验证**
- 真实连接流程用上这把密钥（下一轮接线）；Windows 上主密钥文件的 ACL 是否真的只有当前用户可读（依赖默认 ACL，未实测）。
- S11 的 v0.3 gate（10GB 文件中断续传）无服务器，仍不可验。

**下一步**：把加密层接到连接流程——连接参数里带"记住口令"选项，`CredentialStore` 的路径落到 `%APPDATA%\io.portio.desktop\credentials.json`，主密钥落 `vault.key`；然后做指纹管理界面（列出 known_hosts 记录、删一条、看指纹）。
## 2026-11-18 · v1.0.4-Alpha2 · S11：记住口令接进连接流程

上一轮把加密层做好了但没接线，这轮把它接到用户真正会碰的地方。

- 新增 `crates/app/src/credentials.rs`：`Credentials(Mutex<Option<CredentialStore>>)` 懒加载——第一次真正读写口令时才生成 `vault.key` 与打开 `credentials.json`，不用口令的人不会多出一个密钥文件。四个命令 `cred_get` / `cred_set` / `cred_forget` / `cred_path`，路径都在应用数据目录。
- 口令的键用 `user@host:port`（和会话清单同一个 `sessionKey`），不是只按主机：同一台机器换账号是另一份凭据，不该互相覆盖。
- 前端：密码框下加「记住口令（本机加密保存）」；打开面板时查一次有没有存过——存过就把勾打上、把密码框占位换成「已保存口令，留空沿用」；连接时密码框留空就直接用存好的那份，这样"记住"才真省事。
- 取消勾选的处理：连接成功后调用 `cred_forget` 把旧口令删掉。否则界面上看着没记住，磁盘里还躺着一条，是更糟的状态。
- 改主机/端口/用户名时会重新查一次（`blur` 触发），避免拿着 A 的凭据去连 B。
- 勾选框自绘：系统原生勾选框在深色主题下是亮白方块，跟界面不搭。按规范 §10 新加的 #32 行实现：12×12、`--r-4`、`--line-strong` 边框、选中底 `--accent` + `--on-accent` 对勾。
- 规范先行：按 `autopilot.md` 1.1 的要求，先在 `docs/design-spec.md` §10 加了 #32 行才写代码。

**验证证据**
- `cargo check -p portio-app` 通过（无 error / warning）。
- `node --check ui/app.js` 通过；`check_ui_scale.py` OK；`check_design_tokens.py` OK。
- Chrome 无头 `--dump-dom`（真实 `ui/index.html#quick-demo`，带 `--allow-file-access-from-files`）：`<title>Portio</title>`，全文无 `ERR:`，`f-remember` 与「记住口令」都在 DOM 里。
- 截图 `_a12_pw.png`（900×760@2x，连接面板密码态）与 `_a12_cb_off.png` / `_a12_cb_on.png`（勾选框两态）：勾选行与输入左对齐、行高一致，未选中是细边空心、选中是 accent 底加对勾，两态都不抢输入框。
- 一次插曲：第一版临时核验页放在仓库根，`vendor/xterm-addon-fit.js` 的相对路径断了，状态栏出现 `ERR Uncaught ReferenceError: FitAddon is not defined`——这是核验页的路径问题，不是产品问题；把核验页放进 `ui/` 目录后复验无 `ERR`。记录在这里，免得下次误判成回归。

**未验证**
- 真实连接时"留空沿用已存口令"没端到端跑过（无服务器）；只有单测覆盖加密层本身。
- Windows 上 `vault.key` 的 ACL 依赖用户目录默认权限，未实测。
- 机器仍锁屏，实机窗口点检未做（GUI 侧只做了无头渲染）。

**下一步**：S11 后半——指纹管理界面（列 known_hosts 记录、显示 SHA256 指纹、删一条）。
## 2026-11-18 · v1.0.4-Alpha3 · S11：已知主机（指纹管理界面）

S11 的第二个交付：指纹不再是只能看文件的东西，设置里能列、能删。

- 协议层 `crates/ssh/src/known_hosts.rs` 加 `KnownHosts::records()` 与 `forget()`。键是 `host:port`，拆分用 `rsplit_once(':')` 而不是 `split_once`——IPv6 地址自带冒号，正向切会把 `[::1]:22` 切碎。文件被手改坏的行（没有端口、端口超范围）在 `records()` 里跳过，不让一条坏数据把整张表带崩。
- `crates/app/src/sessions.rs` 加三个命令：`hosts_list`（返回 host/port/fingerprint 三条字段）、`hosts_forget`（删一条，返回是否真删了）、`hosts_path`（记录文件在哪）。列表复用 `known_hosts_path()`，和建连时写的是同一个文件，不存在"界面看到的和校验用的不是一份"。
- 设置面板加「已知主机」：每条一行 `host:port` + `SHA256:xxxx…`（中段省略，完整值放 `title` 里悬停可见）+ 删除按钮；没有记录时是虚线空态加一句说明。点删除会 toast 并就地重绘。
- 顺手改了一处话术：`HOSTKEY_CHANGED` 的终端提示原本让人"删掉 known_hosts 里这台机器的条目"，现在指向「设置 → 已知主机」——界面里有入口了，就不该再让人去改文件。
- 规范先行：先在 `docs/design-spec.md` §10 加第 33 行「已知主机行」（行高 `--ctl`、`--r-6`、三列 `minmax(0,1fr)/auto/auto`、指纹 `--mono` `--fs-11`、删除按钮 hover 转 `--danger`），再写样式。

**验证证据**
- `cargo test -p portio-ssh`：17 条全绿，新增 3 条——`records_split_key_and_can_be_forgotten`（排序、删除、落盘后重载不复活、重复删除返回 false）、`records_keep_ipv6_hosts_whole`（`[::1]:22` 不被切碎）、`broken_line_is_skipped_not_fatal`（坏行跳过、好行照常）。
- `cargo check -p portio-app` 通过（第一次报 `HostRecord is private`，把结构体改成 `pub` 后无 error / warning）。
- `node --check ui/app.js` 通过；`check_ui_scale.py` OK；`check_design_tokens.py` OK。
- Chrome 无头，真实 `ui/index.html`，两个入口各跑截图 + `--dump-dom`：
  - `#settings`（空态）：标题仍为 `Portio`、无 `ERR:`、`hosts-list` 在 DOM、空态块渲染；
  - `#hosts-demo`（三条假记录）：无 `ERR:`、三行 `class="hz"` 渲染；
  - 浅色主题（临时页 `applyTheme('light')`，用完即删）：行与行之间 1px 边框在浅色下看得见，指纹小字不糊。
  - 截图 `_a13_empty.png` / `_a13_demo.png` / `_a13_light.png`。
- 一次插曲：`records()` 一开始想用 `split_once(':')`，写测试时才想到 IPv6，改成 `rsplit_once` 并单独立了一条测试。

**未验证**
- 真实连接"删记录 → 重连 → 重新 TOFU"的完整回路没有服务器可跑；只有文件层单测。
- 界面里没有"确认变更、直接用新指纹"的一键信任；现在的路径是删记录再连，行为正确但多一步。已写入 `docs/backlog.md` 等拍板。
- 机器仍锁屏，实机窗口点检未做（只有无头渲染证据）。

**下一步**：S11 收口评审（是否把 S11 标 ✅）→ 然后进 S12：终端分屏与搜索（分屏布局已定，搜索要接 xterm 的搜索插件/自绘）。
