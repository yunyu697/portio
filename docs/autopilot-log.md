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