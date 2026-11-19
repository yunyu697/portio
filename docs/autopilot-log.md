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
## 2026-11-18 · v1.0.4-Alpha4 · S12：终端查找（Ctrl+F）

S12 的第一件：终端能找了。第二个交付（分屏）还没动。

- 查找条浮在画布右上（`.find`，绝对定位在 `.term-host` 里），不挤压字符网格，也不改 xterm 的 fit 计算。
- 扫 buffer 而不是可视区：`buffer.active.getLine(row).translateToString(true)` 逐行取文本、忽略大小写找 `indexOf`，命中记 `{row, col}`。这样 8000 行滚动缓冲里的旧输出一样找得到。
- 高亮用 `term.select(col, row, len)`，跳转用 `term.scrollToLine(row - rows/2)` 把命中挪到视野中间。实测这两个都是公共 API（先写了个 `ui/_p1.html` 探针确认 `select` 存在且 `getSelection()` 返回预期文本，再动手）。
- 没引 `@xterm/addon-search`：npm 源能通（`npm view` 试过），但 addon 会带版本对齐和体积成本，而这次的三行 API 就够用。要"全量命中都染色"才需要它，已记 backlog。
- 键盘：`term.attachCustomKeyEventHandler` 把 `Ctrl+F` 返回 false 拦在 xterm 之前——不拦的话 `^F` 会被当普通输入发给远端。全局 `keydown` 里再开查找条。
- 交互细节：`Esc` 收起时先摘 `.open` 跑完 240ms 淡出再 `hidden`，不"啪"一下消失；收起时 `clearSelection()` 并 `term.focus()` 把光标交还终端；`activateTab` 里顺手收起查找条（命中行号属于上一个标签的 buffer，留着会指错地方）。
- 序号环回抽成纯函数 `findStep(n, at, delta)`，这样不用起浏览器也能验：从 -1 出发向后落到第一条、向前落到最后一条，其余按 `(at + delta + n) % n` 回绕。
- 规范先行：`docs/design-spec.md` §10 先加第 34 行（位置、`--ctl` 高、`--surface-3` 底、计数 `--mono --fs-11`、无命中转 `--danger`、焦点用 `:focus-within` 转 `--accent`、240ms 上移淡入），再写样式。

**验证证据**
- `cargo test -p portio-core -p portio-app -p portio-ssh`：47 + 6 + 3 + 17 + 1 全绿（本轮无 Rust 改动，跑一遍确认没被前端改动带崩）。
- `node --check ui/app.js` 通过；`check_ui_scale.py` OK；`check_design_tokens.py` OK。
- API 探针 `ui/_p1.html`（临时页，已删）：`select=function`、`scrollToLine=function`、`select(0,1,3)` 后 `getSelection()` 返回 `"foo"`。
- 交互核验（临时页注入断言，跑完即删）：`Ctrl+F` 后 `findBar.hidden=false`；查询 `Portio` → 计数 `1/1`；点「下一个」→ 选中区 `"Portio"`；点「上一个」→ 仍 `1/1`；`Esc` → `.open` 摘掉、选中区清空。
- `findStep` 纯函数 8 条用例（前进、回绕、单命中、空集、反向）全过。
- 视觉：`_a14_find.png`（浅色 1180×690@2x，命中高亮可见）、`_a14_hit_dark.png` / `_a14_none_dark.png`（深色命中与无命中两态，无命中计数转红）、`_a14_find_light.png`、`_a14_find_narrow.png`（1024×620 窄窗，查找条不越界、不压标题条）。
- 无头 `--dump-dom`：四态标题均为 `Portio`，全文无 `ERR:`。

**未验证**
- 真实会话里的手感（大缓冲、连续跳转、tmux 里滚动区）没有服务器可跑；只有本地 banner 与注入文本的证据。
- 跨折行的命中（一个词被终端折成两行）扫不到，行为已写进 CHANGELOG 的 Known limitations。
- 机器仍锁屏，实机窗口点检未做。

**下一步**：S12 第二件——终端分屏（Ctrl+Shift+D 竖切 / Ctrl+Shift+E 横切，各自一套 xterm 实例与 fit，标签粒度不变）。
## 2026-11-18 · v1.0.4-Alpha5 · 会话栏动作行重排 + 按钮文字居中（用户反馈）

用户这轮点了两处，都是"看着不对但说不出哪里"的细节，正好都是规范没覆盖到的空白——所以顺手把规范也补了。

**先量再改。** 用 `Range.getBoundingClientRect()` 把文字盒和按钮盒各量一次：`新建连接` 水平偏差 `dx=0.0`、
垂直 `dy=+4.0`。水平本来就居中，问题是**垂直偏下 4px**：`height:30` + `padding:8px 0` + `line-height:normal`
的行盒（14.4）比内容区（12）高，溢出部分把字顶了下去。改成 `display:inline-flex` +
`align-items:center` + `justify-content:center` + `padding:0 12` + `min-height:--ctl-2` 后，
复测 `dx=-0.0` / `dy=-0.2`。

**动作行。** 把 `.sess-actions` 引入会话栏：`display:flex` + `flex-wrap` + `gap:--sp-2`，主按钮
`flex:2 1 112`、导入下拉 `flex:1 1 112`，两者 `--ctl-2` 同高。量了三种宽度：
- 264（默认）：同排，117.3 / 114.7，tops 都是 78.0；
- 420（拖宽）：同排，221.3 / 166.7（2:1 生效）；
- 200（拖窄）：换行，tops 78.0 / 116.0，各 176（满内宽）。
导入菜单从"以触发器为定位父级"改成"以整条动作行为父级"：之前触发器只有 114 宽，菜单跟着只有 114，
三项菜单里带 `~/.ssh/config` 的那条会被截；现在菜单宽度 = 动作行宽（240 @ 264），换行后也仍铺满。
另给 `.item .path` 加了 `min-width:0` + 省略号，超窄菜单里路径先让位。

**连带修的一处。** `renderSessions` 里"搜不到"的空态是 `btn-new.after(hint)`，动作行合并后这个节点会
插进 flex 行里把按钮挤歪；改成 `sess-actions.after(hint)`。

**验证证据**
- 量测（临时页注入断言，跑完即删）：`new dx=-0.0 dy=-0.2`、`import dx=-0.3 dy=0.0`；
  `sameRow=true`；`menu=240.0@12.0` 与 `actingW=240.0@12.0` 一致；`wrapped=true w=176/176`；`wide sameRow=true 221.3/166.7`。
- 守卫：`check_ui_scale.py` OK、`check_design_tokens.py` OK（中途 `check_ui_scale` 报过一次
  "高度写了裸 px [4.0]"——是我 CSS 注释里写了"4px"，脚本连注释一起扫，改成文字描述后通过）。
- `node --check ui/app.js` 通过。
- 视觉四张：`_a5_actions.png`（浅色同排）、`_a5_actions_dark.png`（深色同排）、
  `_a5_actions_open.png`（菜单展开，铺满动作行）、`_a5_actions_narrow2.png`（200 宽换行 + 菜单）；
  另补 `_a5_modal.png` / `_a5_modal_dark.png` 确认连接面板底部按钮没被 `.btn` 改动带塌。
- 四态 `--dump-dom` 标题均 `Portio`，无 `ERR:`。

**未验证**
- 实机窗口内的 hover / 拖动改宽（会话栏拖到 200 只用手改 CSS 模拟过，没拖过真把手）；
  机器仍锁屏，实机点检未做。
- 窄到 200 时会话栏里的空态文案折成三行（"按 Ctrl+T 新建，或点上面的按钮"被断开），可读但不算漂亮，
  真需要再收（先记着，不在这轮扩）。

**下一步**：S12 第二件——终端分屏。

## 2026-11-18 · v1.0.4-Alpha6 · 终端分屏（一格 → 两格 → 四格）

这轮是 S12 的第二件：一个标签里能并排放好几格终端。上一轮留下的代码是半改状态（CSS 与 `eachTerm`/`fitQuietly` 已动、
`createTab` 主体还是单终端模型，且 `fitQuietly` 引用了一个不存在的 `activeTab()`），这轮把它接完。

**模型。** 标签从「一套终端」变成「N 格终端」：`tab = { stage, grid, cells[], cell, gridTemplate, spec }`，
每格 `{ el, term, fit, sid }` 各有一套 xterm 与自己的会话 id。全局 `term / fitAddon / sessionId` 不再代表标签，
而是「当前标签的当前格」——由 `syncActiveCell()` 统一指过去，所以查找条、SFTP、字号主题这些只认当前格的功能不用各自改。

**格数与布局。** 只走 1 → 2 → 4 三档：1 格 1×1、2 格按方向 1×2 / 2×1、4 格 2×2。中途试过"竖分加列、横分加行"的
递增规则，结果两格再横分得到 2×2 网格只放三格，右下空出一个洞（截图里就是一块死黑），所以改成"两格再分一次补满四格"。
四格关一格会成三格，这时给第一格 `grid-row: span 2` 占满左列，仍然没有空洞。

**格间线。** 用 `.panes-grid{gap:1px; background:--line-strong}` + 每格 `--term-bg` 画，格子自己不画 border——
和"同一处只有一条线"的规范一致，也与终端/文件之间那条线同粗。

**当前格描边。** 先写过 `::after` + `inset box-shadow`，无头截图里只看得见左边和上边；换成 `outline` +
`outline-offset:-1px` 后四边齐全（`outline` 不受 `overflow:hidden` 裁剪）。单格时这道描边不存在（`.multi` 才挂）。

**踩到的坑：新格子里写的字会丢。** 第一版在 `makeCell()` 里 `t.open(el)` 后立刻 `write` 横幅，结果新建的三格全空白——
格子刚 append 进网格时尺寸还是 0，这时写进去的内容不上屏。改成 `requestAnimationFrame` 里先 `fitQuietly()` 再写，
四格就都有内容了（截图 `_a6_split2x2.png` 可见）。

**已连接标签的分屏。** 每格一条通道，不能两格抢同一个 PTY。`tab.spec` 记下"怎么连的"，新格用 `credPeek()` 取同一台
主机的加密口令再 `ssh_connect`；取不到就当场说明「本机没存这台主机的口令，先连一次并勾上记住口令」，
不弹第二个密码框（那会变成半截实现）。

**标题条读数。** 右侧 `80×24` 原来写死，分屏后每格列数不同会骗人，改成当前格实时尺寸（`_a6_single.png` 是 50×23，
1024 带四格时是 20×9）。

**验证证据**
- `cargo test -p portio-core -p portio-app -p portio-ssh`：`6 / 47 / 3 / 17 / 1` 全绿，0 failed。
- 守卫：`check_ui_scale.py` OK、`check_design_tokens.py` OK；`node --check ui/app.js` 通过。
- 状态机自检（`#split-test`，无头跑，断言写进 `<title>`）：1 格 1×1 → 竖分 1×2 → 再分 2×2 → 满四格后分屏键不新建 →
  关一格成三格且挂 `tri` → 再关成左右两格 → 再关回单屏且摘掉 `multi`。结果 `SELFTEST-OK`。
  （这条自检留在了页面里，作为以后每轮的分屏回归门禁，规范 §13 第 13 条引用它。）
- 无头渲染四态 `--dump-dom`：根页 `#split-demo` `#tabs-demo` 标题均为 `Portio`，无 `ERR:`。
- 视觉：`_a6_single.png`（单格 1180×690@2x，无描边、读数 50×23）、`_a6_split2x2.png`（2×2 四格，格间 1px 线、
  当前格四边描边、四格都有横幅）、`_sp4_narrow.png`（1024×620 四格仍不重叠不裁切）、`_sp4_teal.png`（放大核对描边）。

**未验证**
- 真实服务器下的分屏：两条通道各自 `ssh_resize`、输入互不串、关格时 `ssh_disconnect` 只断自己那条——
  只有代码层与无头证据，端到端**未验证**（无可用 SSH 测试服务器，与已知阻塞同因）。
- 实机键盘触发 `Ctrl+Shift+D / E / W` 没在真窗口里按过（机器仍锁屏），只验了 `splitTab`/`closeCell` 的调用路径。
- 格与格之间不能拖宽（等分），四格时每格 20 列级别，窄得只能看命令回显。

**下一步**：S12 第三件——每格的颜色/字号独立设置（或按排期取下一个未完成单元：工作区标签组 / 会话标签页重命名）。
`docs/backlog.md` 追加：分屏格可拖动改宽窄。

## 2026-11-18 · v1.0.4-Alpha7 · 三处界面修正（用户当轮截图驱动）

**本轮性质**：用户给出实机截图（v1.0.4-Alpha5 窄窗）并直接要求三项改动，属排期外增项（S4 / S14 方向），
按 autopilot 1.1 条先改 §10 覆盖矩阵再动代码。

**做了什么**
1. **导入下拉窄窗不溢出**：`.item` 由「文字 + 路径」直接并排改成分段 `<span class="lbl">` + `<span class="path">`；
   `.item` 加 `min-width:0` + `overflow:hidden`，`.lbl` 拿 `flex:1 1 auto` + 省略号，`.path` 让位（`max-width:48%`）。
   根因是 grid/flex 子项 `min-width:auto` + `nowrap` 会按内容撑宽，绝对定位菜单（`left/right:0`）定死了宽度，
   内容便画出边框外并压到终端上。
2. **文件面板可整块折叠**：`.split.files-folded` 三列改 `minmax(0,1fr) 0 10px`，`.pane.files{display:none}`，
   `#gutter-split` 搬进第 3 列 `justify-self:stretch`、`::before` 隐去、`::after` 换成 `‹` 字形
   （与会话栏折叠 `›` 同一套观感）；文件标题条右侧加 `#files-fold` 图标钮（`.pane-tbtn` 26 见方、16 号 SVG）；
   `applyFilesFold()` + `FFOLD_KEY` 落盘 + 启动恢复；三个入口（标题条钮 / 折叠后单击右缘把手 / `Ctrl+Alt+F`）；
   `#gutter-split` 的 pointerdown 在折叠态下不调比例，避免拖到 0 宽度。
3. **传输抽屉收起只占一行**：`PREF.drawer.min` 34 → 28（= `--row`），`applyDrawer()` 里判 `h <= min+2` 加
   `.drawer.collapsed`（正文 `display:none`）、标题右侧文案切「展开」，末尾 `rAF(fitQuietly)`；
   `.drawer.collapsed{border-radius:0}`（一行高时圆角会切文字）；`finishTransfer` 里原来只是
   `classList.remove("collapsed")`（高度不跟着变，会出现「没收起却只露一行」），改成收起态时 `applyDrawer(drawerLast)`。
4. `.split` 补 `grid-template-columns` 240ms 过渡，`body.dragging` 时与 `.main` / `.stage` 一起关掉。

**验证证据**
- `node --check ui/app.js` 通过；`check_ui_scale.py`、`check_design_tokens.py` 均 `OK`。
- 无头量测（1024×620，侧栏压到 180，核验页放在 `ui/` 内、关掉过渡只量终态）标题
  `PROBE-OK`：`menuRight 168 / sideRight 180`（`menuOverflow −12`）、菜单与条目 `scrollWidth−clientWidth = 0`；
  折叠后 `filesDisplay none`、`termW 564 = splitW 574 − handleW 10`、折回后回到 360；
  抽屉收起 `h 28`（`--row` 28）、正文 `none`、文案「展开」，再点回 172 且正文恢复。
- 截图：`_u3_narrow_menu.png`（1024×620@2x，导入菜单整条落在侧栏内、三项省略号）、
  `_u3_fold.png`（1180×690@2x，文件面板收起后终端 101×30、抽屉只剩一行）、`_u3_edge.png`（右缘 `‹` 把手 4× 放大）。
- 提交正文写明验证方式。

**未验证项**
- 三处收放的实机点检（机器仍锁屏）：鼠标 hover 把手亮箭头、实机按 `Ctrl+Alt+F`、收起后拖回比例的手感。
- 无头里 rAF/过渡不推进（轨迹停在起点值），核验页一律关过渡只量终态，因此**过渡动画本身**没被观测到。

**下一步**：S12 第三件（每格独立字号/配色），或按排期取「工作区标签组 / 标签重命名」。

---

## 2026-11-18 · v1.0.4-Alpha8 · S12「复制粘贴习惯对齐」

**本轮做了什么**
1. 按键 → 剪贴板动作抽成纯函数 `clipboardAction(mods, hasSelection)`（`"copy"` / `"paste"` / `null` = 不拦照发）：
   - 复制：`Ctrl+Shift+C`、`Ctrl+Insert`、**有选中时的 `Ctrl+C`**（Windows Terminal 习惯：有选中就复制，没选中照发 `^C`，
     不会出现"想复制却把命令打断了"）；
   - 粘贴：`Ctrl+V`、`Ctrl+Shift+V`、`Shift+Insert`（Xshell / PuTTY 习惯全覆盖）；
   - `Alt` 参与的组合一律 `null`，不抢 `Ctrl+Alt+H/B/F`；`Ctrl+Shift+D/E/W` 也不受影响。
2. 顺手修掉一个顺序隐患：`attachCustomKeyEventHandler` 原来挂在 `const cell` **之前**，handler 里要用 `cell`，
   属于潜在 TDZ；现在挪到 `t.open(el)` 与 `cell` 建好之后。
3. `copySelection(cell)` 统一复制路径：无选中 → toast「没有选中内容」；有选中 → 写剪贴板、`clearSelection()`、
   toast 字符数；失败 → 指出剪贴板权限。右键菜单的「复制选中」改成调它，不再自己写一遍。
4. 右键菜单「复制选中 / 粘贴」补键位 hint（选中 `Ctrl+Shift+C`、未选中「无选中」、粘贴 `Ctrl+V`）。
5. `pasteInto` 多行提醒：去掉尾随换行后超过 2 行 → toast「已粘贴 N 行：多行会一次性送下去，看清楚再回车」（只提示不阻断）。
6. 修掉**不实的文案**：快捷键一览里的「选中即复制」从来没实现过（全代码无 `onSelectionChange`），
   改成「拖选只是高亮，复制要点 `Ctrl+Shift+C` 或右键『复制选中』」；「Ctrl+C 中断」改成「有选中时复制、没选中时中断」。
7. `#ctx-demo` 的终端目标从 `.term-pane`（隐藏容器，派发后打不出菜单）改成 `.term-cell`，右键菜单截图从此可用。

**验证证据**
- `node --check ui/app.js` 通过；`check_ui_scale.py`、`check_design_tokens.py` 均 `OK`。
- 无头 `#clip-test` 标题 **`CLIP-SELFTEST-OK 10`**（10 条断言：三种复制键位、两种 `Ctrl+C` 分支、三种粘贴键位、
  分屏 / 关标签 / `Ctrl+Alt+F` 不被抢）；STDERR 0 行，无 `ERR`。
- 回归门禁：`#split-test` 仍为 `SELFTEST-OK`；普通页标题 `Portio`（无 JS 报错）。
- 截图 `_clip_ctx.png`（1180×690@2x）：终端右键菜单项顺序 = 复制选中(无选中) / 粘贴 Ctrl+V / 全选 Ctrl+A / 分隔 /
  清屏 Ctrl+L / 清空滚动缓冲 / 分隔 / 竖分一格 / 横分一格 / 关闭这一格，与规范 #13 钉的顺序一致。
- `cargo test -p portio-core -p portio-app -p portio-ssh` 全绿（本轮无 Rust 改动）；`check_versions.py` → `OK v1.0.4-Alpha8`。

**未验证项**
- 真实键盘事件进 xterm、真实系统剪贴板读写（复制/粘贴实际效果）未点检——机器持续锁屏，只能做纯函数级自检；
  实机键盘与剪贴板的这条链路仍是 `未验证`。
- `Ctrl+C` 有选中即复制这条在真实 SSH 会话里是否会误伤"想中断但刚好有选中"的用法，需要用人手感确认。
- 多行粘贴的提示只在真实粘贴时出现，无头下未观测。

**下一步**：S13 里能自己收口的「崩溃上报本地采集」（panic hook + 前端 onerror 落盘到 `logs\portio.log`，
设置面板给「打开日志目录 / 复制诊断」）——远端上报端点需用户给；或按排期取 S14「文档站点」最小版（README 落地页）。

---

## 2026-11-18 · v1.0.4-Alpha9 · S13「崩溃上报本地采集」

**本轮做了什么**
1. 新 `crates/app/src/diag.rs`：本机运行日志。一条占一行（`2026-11-18T15:49:16Z [INFO] [app] …`），
   换行在写入前折成 `⏎`，单条按**字符**截到 4000（不是字节，中文不会半截），满 1 MiB 轮转成 `portio.log.1`
   （只留一份备份）。级别只收 INFO / WARN / ERROR，其它一律按 ERROR 记。时间戳自己按 Howard Hinnant 历法算
   UTC ISO8601，不为了打日志引 chrono。
2. Rust panic 钩子：`install_panic_hook` 先落一行 `[ERROR] [rust-panic] … @ 文件:行:列`，再走原来的钩子
   （保留默认报错行为，不静默吞）。`setup` 第一件事就是装钩子，后面任何地方（含 tokio 任务）panic 都能留痕。
3. 四个命令：`diag_log`（前端上报）、`diag_info`（路径 + 字节数）、`diag_tail`（最多 200 行）、
   `diag_reveal`（Windows `explorer /select,`、macOS `open -R`、Linux `xdg-open`）。写日志失败一律咽掉——
   记录日志本身不该把应用带崩，并用一个 `AtomicBool` 闸门防钩子里递归写。
4. 前端：`window error` 与 `unhandledrejection` → `diag_log`（无 Tauri 桥时直接跳过，不因记日志再抛一次）。
5. 设置面板新增「运行日志」区块：等宽路径一行省略（全路径进 `title`）、实时体积、「打开日志位置」
   「复制诊断信息」（版本 + 系统 + 屏幕/窗口尺寸 + 最近 20 行）。打开设置时读一次。
6. **顺手修一笔旧账**：设置面内容变长后，1024×620 下「完成」按钮被挤出视口。改 `.sheet` 为
   `display:flex;flex-direction:column;max-height:calc(100vh - 32px)` + `.sheet .body{overflow:auto;min-height:0}`，
   头部与底部钉住、只滚正文。

**验证证据**
- `cargo test -p portio-app` → **14 passed**（新增 8 条 diag 用例：ISO8601 三个已知日期、级别归桶、
  来源清洗、单行化、按字符截断、行格式、备份名、**真实落盘 + 撑爆阈值触发轮转**）；三个 crate 合计
  `6 / 47 / 3 / 17 / 1` 一类的既有用例全绿（`portio-app` 14、`portio-core` 47、`portio-ssh` 17 等）。
- **实机启动验证**：`target\debug\portio-app.exe` 跑 6 秒后，
  `%LOCALAPPDATA%\io.portio.desktop\logs\portio.log` 出现 158 字节一行：
  `2026-11-18T15:49:16Z [INFO] [app] Portio 1.0.4-Alpha9 启动 · windows x86_64 · 日志 …\portio.log`
  —— 说明钩子安装、路径解析、落盘在真实进程里都对（不是只有单元测试过）。随后 `Stop-Process` 收掉。
- 无头：`#settings` 标题 `Portio`（无 JS 报错）、STDERR 0 行；`#clip-test` 仍 `CLIP-SELFTEST-OK 10`；
  `log-path` 兜底文案正确（`浏览器预览没有本机日志`）、两个按钮都在。
- 截图 `_log_wide.png`（1180×690@2x）与 `_log_narrow.png`（1024×620@2x）：新区块在位；窄窗下卡不越界、
  「完成」按钮可见可点、正文可滚。
- `node --check ui\app.js` 0；两个守卫脚本 `OK`；`check_versions.py` → `OK v1.0.4-Alpha9`。

**规范**
- §10 新增 #39「设置面板 · 运行日志区块」（路径单行省略 + 动作行可换行 + 日志格式约束）。
- 改写 #24「模态」：补「卡高 ≤ `100vh − 32`、头部与底部钉住、只有正文滚」——这条以前根本没写，
  才允许设置面板一路长到窗口外，属于规范缺口，不是单个页面写错。

**未验证项**
- 真实崩溃（Rust panic / 前端异常）没有真触发过：只验证了「落盘 + 轮转」逻辑与启动那条日志；
  panic 钩子路径实机 `未验证`。
- 「打开日志位置」「复制诊断信息」两个按钮在真实窗口里的行为（资源管理器定位、剪贴板内容）未点检——
  机器锁屏，无头环境没有 Tauri 桥。
- 远端上报未做（无端点，需用户给服务地址与出网许可）。

**下一步**：S13 剩余两项都要用户拍板（代码签名证书、自动更新分发端点），先跳过；转 S14「文档站点最小版」
——把 `README.md` 扩成一页可离线打开的说明站（安装 / 首次连接 / 已知主机与指纹 / 快捷键 / 故障排查指向运行日志），
静态 HTML 放 `docs/site/`，仍不带任何网络依赖。

## 2026-11-18 · v1.0.4-Alpha10 · 面板右键菜单 + 文件面板真折叠（用户当轮反馈驱动）

**这一轮修的三件事**
- 有些面板右键会弹浏览器那套菜单（会话栏空白、标签条、文件面板、传输抽屉、状态栏、标题栏）。
- 每个面板的右键菜单要跟这块面板自己的功能对得上，不能只做终端和文件行那两处。
- 文件面板"可以完全折叠"之前提过一次，我这边点了跟没点一样——收起来之后它自己的折叠钮也跟着没了，
  右缘还常驻一条竖线和一个 ‹，看着就像面板还在原地。

**做了什么**
- `ui/app.js` 末尾加「面板级右键菜单」段：`document` 捕获阶段统一 `preventDefault()` 兜住 webview 默认菜单，
  然后按面板各给各的菜单（会话栏空白 / 标签条空白 / 终端标题条 / 文件标题条 / 远端块空白 / 本地块空白 /
  传输抽屉 / 状态栏 / 标题栏空白），原有 6 处自定义菜单（会话行、分组标题、标签项、终端格、远端行、本地行）不动。
- 文件面板折叠钮从「文件标题条」搬到「终端标题条」并改成开关（`aria-pressed`）：面板收起来之后钮还在，
  按一下能收、再按一下能开；`title` 与 `aria-label` 随状态切「折叠 / 展开文件面板」。
- 折叠态右缘把手：静止什么都不画（`‹` 不透明度 0、无竖条带），hover 到 10px 命中区才淡入 `‹` + 左缘亮线，
  `title` 同步「点击展开文件面板」。这才是"完全折叠"。
- 顺手修掉远端工具条里一个多余的 `</td>`。
- 新增 `#fold-test` 回归门禁（与 `#split-test`、`#clip-test` 同一套做法）：关过渡后量三态终值，写进 `<title>`。

**验证证据**
- `#fold-test` → `FOLD-SELFTEST-OK [{"open","term":360,"files":340,"gutter":9},{"fold","term":480,"files":0,"gutter":10,"glyph":"‹"},{"back","term":360,"files":340}]`
  —— 折叠后文件面板宽度真归 0、终端吃满（490−10）、把手 10、回展开恢复 340。
- 逐面板派发真实 `contextmenu`（15 处）全部开出对应菜单，且 `defaultPrevented` 全为 true：
  会话栏空白［新建连接 / 导入会话 / 收起会话栏］、标签条空白［新建连接 / 关闭当前标签］、
  终端标题条［查找 / 清屏 / 折叠文件面板］、文件标题条［折叠文件面板 / 刷新两侧目录］、
  远端块［刷新远端目录 / 新建目录 / 回到上一级］、本地块［刷新本地目录 / 回到上一级］、
  远端行 7 项、本地行 5 项、传输抽屉［收起传输队列］、状态栏［复制诊断信息 / 打开运行日志］、
  标题栏空白［最小化 / 最大化 / 关闭 Portio］、会话行 8 项、分组标题 2 项、标签项 3 项、终端格 8 项。
  终端空白与标题栏品牌区只兜默认菜单、不开菜单（符合"面板要有对应菜单"的分界）。
- 折叠钮点两次：`folded true → false`，两次 `btnVisible` 都是 true，`aria-pressed` 跟着 true/false。
- 截图 `_u4_fold.png`（1180×690@2x 折叠态：文件面板整体消失、终端铺满、开关钮在终端标题条上）、
  `_u4_ctx.png`（会话栏空白菜单）。
- `node --check ui\app.js` 0；`check_design_tokens.py` OK；`check_ui_scale.py` OK；`check_versions.py` → `OK v1.0.4-Alpha10`；
  `cargo test -p portio-app` 全绿（本轮没动 Rust，只为版本号改写后的构建完整性跑一遍）。

**规范（v2.6）**
- 新增 #40「面板级右键菜单」：逐面板条目清单 + 「webview 默认菜单一个都不许出现」+ 「新增面板必须同步这里」。
- 验收清单加第 15 条右键菜单自检（三问：有没有对应菜单 / `defaultPrevented` 是否为真 / 会不会被窗口裁切）。
- 改写 #37 / #14 / #16：折叠入口写在终端标题条上（随面板消失的钮不算入口）、折叠态静止不画任何东西。
- 补记 v2.5（Alpha9 当时改了 #24 与 #39 却漏改版本号）——规范自己的版本纪律也得守。

**未验证项**
- 右键菜单与折叠只在无头 Chromium 里验过；WebView2 实机的点击复验没做成：本轮屏幕被占用，
  PIP 虚拟桌面里 `launch_app` 返回 `accepted_unverified` 且 10 秒内没出窗口。标 `未验证`。
- 状态栏「打开运行日志」在真机上会调 `explorer /select`，无头环境没有 Tauri 桥，未点检。

**下一步**：S14「文档站点最小版」——把 `README.md` 扩成一页可离线打开的说明站（安装 / 首次连接 /
已知主机与指纹 / 快捷键 / 故障排查指向运行日志），静态 HTML 放 `docs/site/`，零网络依赖。

**排查尾巴**：上一轮怀疑「安装版 exe 里搜不到 files-fold / gutter-split 说明 UI 没带进去」——本轮用刚打出的`target\debug\portio-app.exe`复验，新标记同样一个都搜不到（iles-fold 0 /折叠文件面板 0），说明 Tauri 把前端资源压进 exe 时是压缩过的，字节搜索本就搜不到。**上一轮的怀疑排除**：安装版确实带了折叠代码，用户感觉「没实现」的真正原因就是入口随面板一起消失 + 右缘常驻条带，本轮已按这个结论修掉。

## 2026-11-19 · v1.0.5-Alpha1 · S14「文档站点最小版」

**这一轮要什么**：S14 排期里第一件是 `4.3 文档站点`，v0.4 的总目标是「新用户不看文档能连上第一台机器」——
反过来说，真要看的时候，得有一份能看的说明，而不是让新用户去仓库里读 README。Alpha10 之后仓库里
`docs/site/` 根本不存在，所以先做最小版：一页、离线、把「装到用」讲完。

**做了什么**
- 新增 `docs/site/index.html`：单文件（CSS/JS 全内联）、**零外部请求**——字体走系统栈，首屏那张界面示意
  用 CSS 画（截图会过期，结构不会）。共 11 节：安装 / 第一次连上 / 主机指纹 / 会话与分组 /
  从别的工具搬过来 / 文件与传输 / 终端与快捷键 / 设置与外观 / 出问题先看这里 / 文件都放在哪 / 版本与进度。
- 版式沿用软件自己的三栏思路：左侧一列目录，滚动到哪节哪条亮起（首屏默认亮第一节，不会出现"一条都不亮"）；
  窗口窄到 900px 以下目录改成正文上方横排，界面示意同时收成两栏。
- 主题：深/浅两套，跟着标题栏那颗钮轮换并记进 localStorage；`?theme=dark|light` 可以强制指定（方便截图核对）。
- 内容以代码与本机实测为准：数据目录、日志目录、known_hosts 路径、三个导入来源的路径与跳过规则、
  七条报错话术与提示、快捷键（含分屏、查找、复制粘贴的真实键位）全部逐一对照过 `crates/app/src/*.rs`
  与 `ui/app.js`，没有写"大概"。
- 同时把两处不实描述改准：
  - `ui/index.html` 快捷键一览里 Ctrl+Alt+F 旧文案「也可点标题条箭头」——那是 Alpha10 之前长在文件面板
    自己标题条上的钮，钮已经搬到终端标题条，改成「折叠钮在终端标题条上，收起后点右缘细条也能回来」。
  - `README.md`：导入改成了下拉菜单（不再是"三个虚线按钮"）；键位表删掉"选中即复制"（Alpha8 就没有这行为了），
    补上分屏 / 查找 / 真复制三个键位；进度表版本号跟上；顶部加一行指向文档页。
- `CHANGELOG.md` 先写 `1.0.5-Alpha1` 段，再打包（按既有规则：先写更新内容，再打包）。
- `.gitignore` 补 `_*.js`（本轮为 `node --check` 临时导出过一次内联脚本）。

**验证证据**
- 结构自检（临时脚本，已删）：标签栈 0 未闭合、0 失配；0 处 `http`（整页没有任何外链）；11 个节锚点
  全部有对应目标、没有指向空锚点；内联脚本 `node --check` 通过。
- 无头 Chromium 渲染：1440×900（深/浅各一次，整页按 3900/6200 高截全）、1024×620（窄窗）、
  760×900（`≤900` 折叠成单列）；逐张看过首屏、表格、键位表、报错表、附录。截图 `_site_d1..d7.png`、
  `_site_l1.png`、`_site_narrow.png`、`_site_tall.png`。
- `check_design_tokens.py` OK、`check_ui_scale.py` OK（改 `ui/index.html` 必须两关都过）。
- `check_versions.py` → `OK v1.0.5-Alpha1`（Alpha 满 10 后按规则进位到 patch）。
- `cargo test -p portio-app` 通过（本轮没动 Rust，只为版本字段改写后跑一遍完整性）。
- 安装包：见本轮交付说明。

**过程中的坑（记下来免得下次再踩）**
- `--screenshot=` 必须给绝对路径，相对路径会落到 Chrome 自己的 CWD 里，`Test-Path` 只见 MISSING。
- 页面 JS 的 `prefers-color-scheme` 在无头里默认是 light：不显式带 `?theme=dark`，深色那一次截的其实是浅色
  （两张 PNG 字节数一模一样才露的马脚）。
- 带 `#锚点` 的 URL 在无头里配合 `scroll-behavior:smooth` 会截在没滚完的位置（整页纯背景）；要么加
  `--disable-smooth-scrolling`，要么干脆用超高视口一次截全。
- 无头里 `>` 重定向抓不到 HTML，仍旧是 Python `subprocess` + 显式 `utf-8`。

**未验证项**
- 这一页**没在 WebView2 实机窗口里打开过**（无头只能证明版式与结构，证明不了 WebView2 下的字体回退与
  深色滚动条细节）。标 `未验证`。
- 只在 Windows 语境写：macOS / Linux 打包还没开工，安装与卸载那节只讲 Windows。

**下一步**：S14 第二件「首发物料」——一页可粘贴的发布说明（从 CHANGELOG 抽 Alpha 段、按用户视角写清
这一版能干什么 / 已知限制 / 怎么装），存 `docs/release-notes.md`；之后才是三平台包与签名（签名证书要用户给）。

## 2026-11-19 · v1.0.5-Alpha2 · S14「首发物料：发布说明」

**这一轮要什么**：S14 排期里第二件是「首发物料」。文档页（Alpha1）解决"装完怎么看"，这一轮解决
"怎么把它讲出去"——发版时不用现编文案，一页里既有能贴到 Release 的整段正文，也有转发用的一句话。

**做了什么**
- 新增 `docs/release-notes.md`（143 行）：开头先写"这份文件怎么用"（哪段贴哪里、哪节不能删），
  然后是①一句话短版；②正文（整段可粘贴）；③版本号读法；④每版改动指回 CHANGELOG。
- 正文按用户能感知的六块讲：终端（多标签 / 分屏 / 查找 / 复制粘贴）、文件（双栏 / 队列 / 断点续传 /
  权限列）、会话（本地清单 / 分组 / 搜索 / 快速连接 / 三个导入来源）、安全（口令加密 / 记住口令 /
  指纹变更即拦）、排障（本机日志 / 复制诊断 / 七类报错话术）、界面（主题 / 密度 / 面板右键 / 三处可折叠）。
- 「怎么装」写清安装包名、体积、WebView2 依赖、SmartScreen 会亮一次、调试构建这句实话。
- 「第一次连一台机器」给三种入口，外加核对指纹的命令（`ssh-keygen -lf …pub`）。
- 「文件都放在哪」一张表六个路径（会话 / 加密口令 + 主密钥 / 指纹 / 主题 / 日志 / 程序本体），
  并写卸载后怎么彻底清。
- 单开一节「哪些是代码写完了但没在真服务器上跑过」，五项逐条列出：真实登录与 PTY、`vim`/`tmux`/`htop`
  重绘、真实上传下载与断网续传、分屏新通道、真实崩溃路径、WebView2 实机点检。
- 「已知限制」六条：只有 Windows、无签名无自动更新、无远端上报、远端半截文件没界面、分屏格不能拖动、
  查找只高亮一条、多行粘贴只提示不拦截。
- README 顶部加一行指向这份说明；CHANGELOG 先写 `1.0.5-Alpha2` 段（规则是先写更新内容再打包）。

**验证证据**
- 自检脚本（临时，已删）：文档内所有相对链接都落地（`site/index.html`、`versioning.md`、`../CHANGELOG.md`
  三条全在）；文档内出现的版本号只有 `1.0.5-Alpha2`（无旧版残留），与 `Cargo.toml` 一致；
  1 个 H1 + 14 个标题，八个必备小节齐全。
- 文案事实逐条对照：七个报错话术取自 `app.js` 的 `explainError`；六组键位取自 keydown 与
  `clipboardAction`；三个导入来源与跳过规则取自 Rust 侧解析器；两个目录取自 `sessions.rs` / `diag.rs`。
- 本轮实际构建：`Portio_1.0.5-Alpha2_x64-setup.exe`（4535935 字节 = 4.33 MiB），与文里"约 4.3 MiB"对得上。
- `check_versions.py` → `OK v1.0.5-Alpha2`；`check_design_tokens.py` OK、`check_ui_scale.py` OK；
  `cargo test -p portio-app` 14 passed（本轮没动 Rust，只为版本改写后跑一遍）。

**未验证项**
- 说明里描述的能力本身，仍有五项只在协议层单测与本机回环里验过（文档内已逐条标 `未验证`）。
- 这份文案没在真实发布页（GitHub Release / 论坛编辑器）里预览过排版——Markdown 在那边会不会把
  「一句话」的引用块渲染成缩进、表格列宽会不会挤，都要等真发一次才知道。标 `未验证`。

**下一步**：S14 第三件。首发物料还剩「截图与图标素材」与「多语言」两处可做，但排期里更靠前的是
**RC 回归清单**（`docs/rc-checklist.md`：把前 13 个 Sprint 的完成定义压成一张可勾的表，标出哪些能本机验、
哪些必须有服务器）。三平台包与签名要等用户给证书与机器。

## 2026-11-19 · v1.0.5-Alpha3 · S14「RC 回归清单」

**这一轮要什么**：S14 的 gate 原话是「三个平台安装包齐全，新用户不看文档能连上第一台机器」。要往这个方向收，
先得把"现在到底差什么"写成一张能勾的表——不然每轮都在凭印象推进。所以这一轮不写功能，写清单。

**做了什么**
- 新增 `docs/rc-checklist.md`（164 行），四块：
  - §1 本机自动化 11 项：每项一条命令、一个判据、一行最近结果；
  - §2 无头做不到、得真人点一遍的 12 项（hover / 拖拽 / 真右键 / 真键盘 / 真安装包）；
  - §3 逐 Sprint 拿排期原文的出口标准对着现状（S1–S14 各一行，过 / 未验 / 缺口 / 卡外部条件）；
  - §4 只有真服务器能过的 9 项（B1–B9）与只有人能给的 5 项（C1–C5）。
- §1 里把前端自检的跑法写成可复制的片段：自检逻辑本来就在 `ui/app.js` 里由 hash 触发，
  **直接打开产品页 `ui/index.html#split-test` / `#clip-test` / `#fold-test` 读 `<title>` 就行**，
  不必另做核验页——这是本轮才发现可以省掉的一步，以前每轮都临时写一张 `_*.html`；
  顺带记了四个必踩的坑（页面必须在 `ui/` 里、`--allow-file-access-from-files` 必带、无头默认浅色、
  pwsh 的 `>` 重定向抓不到 dump-dom）。
- §6 写清 gate 判定：**现在不能过**（三平台只有 Windows 且未签名、缺一次真人陌生环境试用），
  并给出不靠人给东西也能先发的范围（Windows 内测包 + 离线说明页 + 发布说明）。
  过 gate 的最短路径按依赖排了序，第一条是「给一台能连的测试机，或允许我在本机起只监听回环的 sshd」——
  后者要动系统能力，按守则不自作主张，等点头。
- §7 建了回归记录表，本轮填了第一行。

**验证证据**
- `cargo test --workspace` → 82 passed（app 14 / core 50 / ssh 18）。
- 无头四条判据实跑（Python `subprocess` 抓 `<title>`）：默认页 `Portio`（无 `ERR:`）、
  `#split-test` → `SELFTEST-OK`、`#clip-test` → `CLIP-SELFTEST-OK 10`、
  `#fold-test` → `FOLD-SELFTEST-OK`（open 360/340/9 → fold 480/0/10 → back 360/340）。
- PE 子系统实读：`Subsystem = 2`（GUI，启动不带控制台黑窗）。
- `node --check ui/app.js` exit 0；`check_design_tokens.py` OK；`check_ui_scale.py` OK；
  `check_versions.py` → `OK v1.0.5-Alpha3`。
- 文档自检：7 个二级标题、70 行表格、竖线数逐块一致（无错列）。
- 安装包 `Portio_1.0.5-Alpha3_x64-setup.exe` 4534194 字节（4.32 MiB）。

**顺手修的排期文档问题（仓库外）**
- 上一轮回填脚本按"第一行以 `| S14` 开头"定位，结果改中的是**第 64 行 Sprint 排布表**里的 S14 行，
  不是第 167 行的看板行——看板行反而没更新。这一轮按行号精确改回来：第 64 行恢复成
  「`2027-05-24 → 06-06` / 4.3 文档站点、首发物料、收口；v0.4 gate / 发布页面与三平台包齐全」，
  第 167 行补上 Alpha2 的发布说明。教训写在这里：**同一文档里有两处同名前缀的行，别用 startswith 定位**。

**未验证项**
- §2 的 12 项人工点检一项没做（机器被占用；PIP 里 WebView2 起不来）。
- §4 的 9 项真服务器项一项没做（无测试服务器与凭据）。
- 清单是文档，不会自己跑；每次仍要手动执行 §1 的 11 条。

**下一步**：S14 第四件。清单已经把"要服务器才能验"的部分钉死了，剩下的时间里能做的是
**把前端那三条自检从"每轮临时拼命令"变成仓库里一个固定入口**——加 `scripts/rc.py`（一条命令跑完
A1–A10 并打印 PASS/FAIL 汇总），这样回归记录表的每一行都有可复现的输出，不用我每次手打命令。
之后是首发物料里的截图素材与多语言。

## 2026-11-19 · v1.0.5-RC1 · 进入 RC 阶段 + 一条命令跑完自动化回归

**这一轮要什么**：用户拍板"下一轮开始改成 RC 版本"，同时上一轮记下的下一步是补 `scripts/rc.py`。
两件事正好是一件事：宣布 RC 就意味着"不再加功能、只修 Bug"，那第一件该做的事就是让"能不能发"
有一个可复现的判断口，而不是靠我每轮手打一堆命令。

**做了什么**
- 新增 `scripts/rc.py`（约 300 行），按 `docs/rc-checklist.md` §1 的 A1–A11 顺序跑：
  - A1 `cargo test --workspace`（解析 `test result:` 行累计 passed / failed）
  - A2 `node --check ui/app.js`
  - A3/A4 两个界面守卫脚本
  - A5 `check_versions.py`
  - A6–A9 Chrome 无头抓 `<title>`（默认页 / `#split-test` / `#clip-test` / `#fold-test`，出现 `ERR:` 即判失败）
  - A10 读 `portio-app.exe` 的 PE 子系统
  - A11 最新 NSIS 包的体积与文件名
  - 全跑约 57 秒（`cargo test` 占 50 秒）；`--fast` 跳过 A1；`--list` 只列项；任一 FAIL 退出码 1，可直接当 CI 门禁；
    三个工具自动探测（rustup 默认 cargo、豆包运行时自带 node、标准路径 Chrome），也可用环境变量覆盖；
    跳过项不算通过，汇总行会提醒写清跳过原因。
- 版本规则补上 RC（`docs/versioning.md` 新增「从 Alpha 转到 RC」小节）：`v1.0.5-RC1` 起每完成一个单元 RC 进一位，
  RC 满 10 进位到下一个 patch 回 RC1，转正去掉后缀，阶段只许前进（`version.py` 会拦住退回）。
- `docs/autopilot.md` 里两处"Alpha 进位"改成"预发布位进位（Alpha / RC）"，并写明 RC 只修 Bug。
- README 开发段把"照清单过一遍"换成两条命令（`rc.py` / `rc.py --fast`）。
- `rc-checklist.md` §1 顶部写明固定入口；§7 回归记录加 RC1 一行。

**验证证据**
- `python scripts/rc.py` 全跑：**11 通过 / 0 失败 / 0 跳过，56.8s**
  （A1 82 passed；A2 exit 0；A3/A4 OK；A5 `OK v1.0.5-RC1`；A6 `title = Portio`；A7 `SELFTEST-OK`；
  A8 `CLIP-SELFTEST-OK 10`；A9 `FOLD-SELFTEST-OK`（fold: files=0 / gutter=10 / back 复原）；
  A10 `Subsystem=2`；A11 当时读到的是上一版包）。
- 打包后又跑一次 `--fast`：A11 已指到 `Portio_1.0.5-RC1_x64-setup.exe` 4532960 字节（4.32 MiB），
  A5 仍是 `OK v1.0.5-RC1`。
- `python -m unittest scripts.test_version` → 12 tests OK（含 `Alpha3 → RC1`、`RC1 → final`）。
- `python scripts/version.py next 1.0.5-Alpha3 stage RC` → `1.0.5-RC1`；`set_version.py` 四处同步。
- 提交 `e33d85c`（12 files +390/−15）。

**未验证项**
- `rc-checklist.md` §2 的 12 项人工点检、§4 的 9 项真服务器项：本版一项没做（机器被占用、无测试服务器）。
- 安装包仍未签名（S13 的 C1 未到位）。
- `rc.py` 只覆盖本机能验的部分；A6–A9 依赖本机装 Chrome，换机器要设 `PORTIO_CHROME`。

**下一步**：RC 阶段只修 Bug，所以接下来的单元都从清单里挑。第一顺位是
**§2 那 12 项人工点检**——它是清单里唯一"代码全齐、就是没人点过"的部分，
其中 M5（九个面板右键）、M6（文件面板与队列折叠）、M11（窄窗）是前面几轮用户亲自报过的点，
最该由我先验一遍。机器被占用时退而求其次做首发物料的截图素材与多语言。

## 2026-11-19 · v1.0.5-RC2 · 「九处面板右键菜单」自检（M5 从人工项里挪出来）

**这一轮要什么**：RC 阶段只修 Bug，那第一顺位是清单 §2 那 12 项人工点检。可机器这会儿被占用，
实机点不了。于是把其中**唯一能变成代码的那一项**——M5"每个面板的右键菜单是不是它自己那份"——先自动化：
判它不需要真鼠标，只要派发事件、读菜单条目就行。剩下那些"手感顺不顺"才必须人点。

**做了什么**
- `ui/app.js` 末尾新增 `#ctx-test`：九处面板逐处派发一次真实 `contextmenu`（会话栏 / 标签条 /
  文件面板标题条 / 文件面板远端 / 文件面板本地 / 终端标题条 / 传输抽屉 / 状态栏 / 标题栏），每处判两件事：
  ①浏览器默认菜单有没有被拦下来（`defaultPrevented` 为真）；②开出来的是不是自己那份菜单——
  条目文字逐条比对，动态文案（折叠↔展开、收起↔展开队列、最大化↔还原）两种写法都放行。
  结果写进 `<title>`：`CTX-SELFTEST-OK 9`，失败时 `CTX-SELFTEST-FAIL [{哪一处、拦没拦住、实际条目}]`。
- `scripts/rc.py` 增 **A12**，回归从 11 项变 12 项。
- `docs/rc-checklist.md`：§1 加 A12 一行；§2 的 M5 改成"只剩实机手感"——"开的是不是自己那份"已由 A12 兜住。

**验证证据**
- 无头 `ui/index.html#ctx-test` 读 `<title>` → `CTX-SELFTEST-OK 9`。
- **反向验证（这轮最重要的证据）**：自检最怕空转——全绿也可能什么都没测到。所以临时把"标签条"那组
  期望条目改错一个字再跑，结果 `CTX-SELFTEST-FAIL [{"name":"标签条","prevented":true,"open":true,
  "labels":["新建连接","关闭当前标签"]}]`：既判了失败，又点名是哪一处、实际条目是什么、默认菜单拦住了没。
  验证完立刻还原 `app.js`（101303 字节，与改坏前一致）。
- `python scripts/rc.py` 全跑：**12 通过 / 0 失败 / 0 跳过，64.7s**
  （A1 82 passed；A5 `OK v1.0.5-RC2`；A6–A9 四条旧判据照旧；A10 `Subsystem=2`；
  A11 `Portio_1.0.5-RC2_x64-setup.exe` 4536738 字节 / 4.33 MiB；A12 `CTX-SELFTEST-OK 9`）。
- `node --check ui/app.js` exit 0；两个界面守卫 OK。

**未验证项**
- 只测"是不是自己那份 + 有没有拦住浏览器默认菜单"，**菜单里的动作真按下去对不对没测**——
  那要真环境（连上服务器、有文件、有标签）。清单 §2 的 M5 仍留一行"实机手感"。
- §2 其余 11 项人工点检、§4 的 9 项真服务器项：仍未做。
- 安装包仍未签名。

**下一步**：M6 与 M11 是用户亲自报过的两处（文件面板真折叠、传输队列收起只占一行、窄窗下拉不溢出）。
这三件里"折叠"与"窄窗"都能用无头量尺寸验（`#fold-test` 已覆盖折叠，窄窗还没有判据），
下一轮做 `#narrow-test`：把窗口宽度压到 1024 / 900 两档，量导入下拉右界、模态按钮位置，
把 M11 也收进 `rc.py`。M6 的"队列收起只占一行"同轮可量高度。

## 2026-11-19 · v1.0.5-RC3 · 窄窗几何门禁（M6 与 M11 也交给命令跑）

**这一轮要什么**：上一轮把 M5（右键菜单）自动化了，接着往下走，清单 §2 里剩下的 11 项里，
有两项是我自己截图报过去的：M11「窗口调窄后导入下拉的条目跑到菜单外」、M6「文件面板要能真折叠、
传输队列收起只留一行」。这两件都不用真鼠标——**量尺寸就能判**，所以这一轮把它们做成判据。

**做了什么**
- `ui/app.js` 末尾新增 `#narrow-test`：`--window-size` 换宽度跑同一页，量真实几何，判六条：
  ①导入下拉整条留在最窄（180）侧栏里；②条目文字被裁住——条目 overflow 可见且内容比盒子宽就算失败
  （这正是我截图里"字跑到菜单边框外、再被侧栏切掉"的成因）；③传输队列收起正好一行高（等于标题条），
  正文 0；④文件面板折叠后宽度归 0、终端吃满整列、把手 10px；⑤设置卡与「完成」按钮在窗内；
  ⑥整页无横向滚动条、右键菜单贴右缘会内收。
- `scripts/rc.py` 增 **A13**，在 1024 / 900 两档各跑一次；`docs/rc-checklist.md` §1 加 A13 行，
  §2 的 M6、M11 改成"尺寸已自动化，只剩手感"。

**验证证据**
- 三档无头几何全 OK：内容宽 1254 / 998 / 874；菜单与侧栏右缘固定留 12px、条目在菜单内 5px；
  抽屉 28px = 标题条 28px、正文 0；折叠后 `files 0 / term 684 / gutter 10`；`actionsOverflow 0`。
- **反向验证**：把 `.item` 与 `.lbl` 的 `overflow:hidden` 与 `min-width:0` 临时去掉（复原我截图里那个样子），
  900 宽立刻 `NARROW-SELFTEST-FAIL`，点名「导入条目文字越出菜单右侧 32px」「动作行横向溢出 32px」
  ——说明判据抓的正是那个毛病，不是空转。验证后已还原 `index.html`（51204 字节）。
- `python scripts/rc.py` 全跑：**13 通过 / 0 失败 / 0 跳过，75.1s**
  （A1 82 passed；A5 `OK v1.0.5-RC3`；A11 `Portio_1.0.5-RC3_x64-setup.exe` 4537521 字节 / 4.33 MiB；
  A12 `CTX-SELFTEST-OK 9`；A13 `1024 OK / 900 OK`）。

**未验证项**
- 判据只看几何、不看"挤不挤"：900 宽下条目路径会省略到只剩几个字，这得我自己看一眼。
- WebView2 真机字体度量与无头 Chrome 可能差一两像素，判据留了 1–5px 余量，真机上还没核。
- 清单 §2 其余 10 项人工点检、§4 的 9 项真服务器项：仍未跑。安装包仍未签名。

**下一步**：剩下的人工项里能代码化的已经不多。下一轮做 M7「深浅两套主题切完无组件错位」——
这个也能量：给每个面板在 `light` / `dark` 下取矩形，比两次的宽高与左边界，再看分隔线颜色的对比度是否
达到 3:1；顺带把 S12 的出口标准收进清单 §3。

## 2026-11-19 · v1.0.5-RC4 · 主题门禁（深浅两套几何必须一个像素不差）

**先更正上一轮日志的一处笔误**：上一轮写"下一步做 M7 主题切换"，M7 其实是复制粘贴；
主题切换与密度是 **M10**。这一轮做的是 M10 的深浅那半。

**这一轮要什么**：切主题这件事我最怕的不是丑，是"切完某个面板宽了一点、某个条高了一点"——
这种错位肉眼扫一遍常常漏。主题只管颜色，几何本来就不该动，所以这件事完全可以交给命令：
两套主题各量一遍同一组分区，逐项比。

**做了什么**
- `ui/app.js` 末尾新增 `#theme-test`：深 / 浅两套各量 11 个分区（标题栏 / 会话栏 / 标签条 /
  终端与终端标题条 / 文件面板 / 远端块 / 本地块 / 传输队列 / 状态栏 / 主题按钮），
  比左上角与宽高，差超过 1px 就点名；同时判主题按钮的太阳↔月亮有没有按主题互换；
  再按 WCAG 把六组令牌的对比度算出来（分隔线 ≥1.25、强线 ≥1.5、正文 ≥10、次要 ≥4.5、弱化 ≥2.9），
  免得哪天为了"看着柔和"把分隔线调成看不见。量完把主题还原成我原来那档。
- `scripts/rc.py` 增 **A14**（共 14 项）；`docs/rc-checklist.md` §1 加行，§2 的 M10 改成
  "深浅几何与对比度已自动化，只剩眼睛与密度"，§3 的 S12 行改判为"能"。

**验证证据**
- 无头跑 `#theme-test` → `THEME-SELFTEST-OK`：`landmarks 11`、`worstShift 0`；
  深色 `line/surface 1.30`、`line/bg 1.39`、`strong 1.64`、`text 14.04`、`text2 5.94`、`text3 3.15`；
  浅色 `1.37 / 1.27 / 1.69 / 16.04 / 5.86 / 3.00`；浅色只显示太阳（sun 16 / moon 0），深色反之。
- **反向验证**：临时加两条只在浅色生效的规则——`.statusbar{height:30px}` 与把 `--line` 调成近白，
  立刻 `THEME-SELFTEST-FAIL` 并点名「statusbar 切主题后错位 4px」「浅色主题分隔线对面板底只有 1.08，低于 1.25」；
  随后 `git checkout -- ui/index.html` 还原（50450 字节，`反向验证` 字样计数 0）。
  顺带发现一件事：先前我用 `--sidebar:300px` 做反例没被抓到，因为 `applySidebar` 会把宽度写进行内样式，
  盖过 CSS 规则——所以反例得挑真会被 CSS 影响的属性，这条也记在下面。
- `python scripts/rc.py` 全跑：**14 通过 / 0 失败 / 0 跳过，93.1s**
  （A1 82 passed；A5 `OK v1.0.5-RC4`；A11 `Portio_1.0.5-RC4_x64-setup.exe` 4539634 字节 / 4.33 MiB；
  A14 全绿）。

**未验证项**
- 量的是盒子几何，**不管画笔**：边框色、阴影深浅、图标线条粗细这类"看着偏"的看不出来——
  这些只能我自己看一眼。
- 真机 WebView2 的字体度量与无头 Chrome 可能差一两像素，判据留了 1px 余量，真机上还没核。
- 密度三档（标准 / 紧凑）的切换仍只有人工点检（M10 后半）。
- 清单 §2 其余人工项、§4 的 9 项真服务器项：仍未跑。安装包仍未签名。

**下一步**：M10 里剩下的密度半件事就不勉强代码化了（密度只改行高，肉眼一眼能看）。
下一轮转去 §2 里另一件能量的事——M9「查找」：给 `#find-test` 打一套判据，查 `1/N` 计数是否跟
`term.search` 真结果一致、无命中是否转红、窄窗下查找条不越界（最后这条 A13 原理可复用）。

## 2026-11-19 · v1.0.5-RC5 · 查找门禁（把"搜索不太准"拆成能数的七件事）

**这一轮要什么**：查找是那种出错最安静的功能——计数多一条少一条、跳过去高亮的不是那一条、
没命中却不变红。用的人只会说"这搜索不太准"，我说不出哪儿不对，也没法写进回归清单。
所以这一轮把它拆开：凡是能数出来的，都交给命令。

**做了什么**
- `ui/app.js` 末尾新增 `#find-test`，七组判据：
  ① 计数与"自己重扫一遍 buffer"的条数一致、面板写 `1/N`；
  ② 每条命中的行列坐标按 buffer 取出来正好是查询词（这条专治"少扫一个字"的退化）；
  ③ 首跳落在第 1 条并真的选中它；
  ④ `findStep` 五条环回算式，再真按一遍"末条往后绕回第 1 条"；
  ⑤ 无命中 `0/0` 且转红、改回有命中的词要摘红；
  ⑥ 查找条不越出终端面板、不压标题条；
  ⑦ 关掉后 `open` 态撤掉、终端不留高亮、序号复位。
- 用例素材自己补一行：4 处大小写不同的查询词堆在同一行，外加两个不带尾字母的 "Porti"——
  "一行多处命中""多条环回""少扫一个字"这三件事才真的被走一遍，一共 5 处命中。
- `scripts/rc.py` 增 **A15**（共 15 项；`a_page` 加了 `window` 参数，A15 在 900×620 下跑，
  顺带把窄窗里的查找条几何一起量了）；`docs/rc-checklist.md` §1 加行，§2 的 M9 改成
  "计数 / 坐标 / 环回 / 无命中 / 几何已自动化，剩下跳过去那条看着对不对"。

**验证证据**
- 无头 `#find-test` 在 1024 / 900 / 默认三档都是 `FIND-SELFTEST-OK`：
  `hits 5`、`label 1/5`、`sel "Portio"`、`step [0,4,0,4,-1]`、`nohit "0/0"`、
  `geom {w:263, gapRight:8, gapHead:4}`。
- **反向验证**：临时把 `findScan` 的 needle 截短一个字、并删掉"无命中转红"那行，立刻
  `FIND-SELFTEST-FAIL`，四条一起点名：「条数不一致：自扫 5 条，查找认为 7 条」
  「计数文字是 1/7，应为 1/5」「命中坐标取到的不是查询词：`[{row:4,col:17,got:"Porti、"}…]`」
  「无命中时计数没转红（缺 .bad）」；随后从备份还原（`restored: True True`）。
  中间还吃了一次教训：一开始的素材只有 5 处 "Portio"，把 needle 截短成 "porti" 之后条数**恰好还是 5**，
  反例完全抓不到——所以专门加了两个裸 "Porti" 当诱饵，才让这个退化暴露。
- `python scripts/rc.py` 全跑：**15 通过 / 0 失败 / 0 跳过，75.6s**（A2 语法通过、A5 `OK v1.0.5-RC5`）；
  打包后 `A11 Portio_1.0.5-RC5_x64-setup.exe` 4545481 字节 / 4.33 MiB。

**未验证项**
- 判的是"算得对、画得对"，**不判"跳得准不准"**：命中行是否真滚到视野中间、长 buffer 下滚动跟不跟手，
  这两件无头量不出来（`scrollToLine` 的落点只按 `hit.row - rows/2` 估，本来也是估）。
- 用例素材是我自己写进 buffer 的 5 处，真实远端输出里的宽字符（中文 / emoji）、ANSI 颜色、自动折行
  还没覆盖；这类命中列号的偏差正是下一步真人真机才看得出来的。
- 真机 WebView2 的字符宽与无头 Chrome 可能有差，`col` 判据在真机上没核过。
- 清单 §2 其余人工项、§4 的 9 项真服务器项：仍未跑。安装包仍未签名。

**下一步**：`Ctrl+F` 那条链路里还剩"截图级别"的两件事——命中行居中与长 buffer 滚动。
下一轮把 `#find-test` 扩成"宽字符 + ANSI 颜色 + 长 buffer"三组素材：往 buffer 里写 120 行，
每 10 行一处命中，再混中文与带色文本，然后把"跳到最后一条后命中行是否落在可视区中间"也量出来。
这条能量，也正好解开上面第一条未验证。

## 2026-11-19 · v1.0.5-RC6 · 中文行上高亮右偏（修掉它，并把能抓它的判据补上）

**这一轮为什么**：上一轮我把查找的账算清了，但账本里只有 banner 那 5 处、全是英文。
真连上机器以后，屏幕上一大半是中文——而中文是宽字符，占两格却只算一个字。
`findScan` 拿 `translateToString()` 的**字符下标**直接当 `select()` 要的**格号**用，
一行里前面只要有中文，后面的命中列号就小了几格：跳过去，高亮的是右边错位的一段字。
这不是"手感"，是错。

**做了什么**
- 修 `findScan`：真命中时才逐格走一遍 buffer，把每个字符记到它所在的格号上，命中返回真格号。
  只在有命中的行建这张映射，没有命中的行不开销——搜索框边打边扫不能因为这行代码变卡。
- `#find-test` 的第②条判据从"按列号切片取字"改成"真的跳过去、看 `getSelection()` 取回什么"。
  原来那条切片是按字符切的，正是它让这个偏移一直没被发现——**判据本身选错了尺度**。
- 追加第⑧段（长 buffer / 宽字符 / ANSI）：写 120 行，每 10 行一处命中，交替插中文前缀与 ANSI 颜色包裹，
  再埋两个少个尾字母的 `Portio_lon` 当诱饵。判：计数 12 条 / `1/12`、逐格重扫与查找给出同一格号、
  逐条跳过去选区就是查询词、中间那条落在视野中间、末条贴底时仍可见且 `viewportY = baseY`、
  滚过之后旧行还在（`after 12`）。
- `scripts/rc.py` 的 A15 标签改写；清单 §1 的 A15 行、§2 的 M9 行一起更新。

**验证证据**
- 无头 `#find-test`（900×620 与默认窗宽）→ `FIND-SELFTEST-OK`：
  `hits 5`、`long {wrote 12, flushed 12, hits 12, label 1/12, center {row 65, viewportY 58, wantY 58}, last {at 11, row 125, viewportY 113 = baseY}, after 12}`。
- **反例一**（把修复放回去：`col: cellOf[at]` → `col: at`）：FAIL 三条同时点名——
  「按命中跳过去，选出来的不是查询词：`[{i:4,row:4,got:"加 Por"}]`」
  「列号对不上（把字符下标当成了格号？）：`[{row:25,findCol:6,cellCol:11}…]`」
  「长 buffer 里跳过去选到的不是查询词：`[{i:1,row:25,got:"字符 Portio"}…]`」。
- **反例二**（把居中落点改成直接滚到命中行）：FAIL「中间那条没滚到视野中间：viewportY 65，应 58」。
  两个反例跑完都从备份还原（`restored: True True`）。
- `python scripts/rc.py` 全跑：**15 通过 / 0 失败 / 0 跳过，89.9s**；打包后
  `A11 Portio_1.0.5-RC6_x64-setup.exe` 4541039 字节 / 4.33 MiB；两守卫都 OK。

**未验证项**
- 宽字符只在无头 Chrome 里验过。理论上现在按格算与字体无关，但**真机 WebView2 没实测**。
- 120 行只够"产生滚动"，不是"很长"：几百上千行时扫描耗时、滚动跟手程度都没量；
  emoji（宽度 2 且是组合字符）没进素材，那一类可能还有别的偏。
- 命中行居中只判"落点算式对不对"，判不了"看着舒不舒服"。
- 清单 §4 的 9 项真服务器项、§2 其余人工项仍未跑；安装包仍未签名。

**下一步**：这一轮把"算得对"补到了中文与颜色上。剩下的差距集中在**真机**：查找在真实
WebView2 里的字符度量、以及几千行 buffer 下边打边扫是否卡顿。前者没有 SSH 服务器也能做——
下一轮开一个"真机冒烟"单元：把已装的旧版本卸掉、装 RC6、启动窗口截屏，确认终端里写一段中文
再 `Ctrl+F` 高亮落在字上（这条能解开上面第一条未验证），同时把 `#find-test` 的 120 行拉到 800 行
量一次扫描耗时。

## 2026-11-19 · v1.0.5-RC7 · 查找门禁压到 800 行（80 处命中），补上 emoji 与组合字符

**这一轮为什么**：上一轮的 120 行只是"够产生滚动"，不是"真长"。真实场景是翻几百行前的日志尾巴，
而滚动缓冲默认 8000 行。素材不够长，判据就只是在短纸上验字。

**做了什么**
- `#find-test` 的长 buffer 段从 120 行扩到 **800 行**，命中从 12 处增到 80 处。素材里同时出现四类字符：
  中文宽字符前缀、**emoji 前缀**（`😀` 是代理对，两个 code unit 占两格）、**组合字符行**（`e\u0301`
  一个格子两个 code unit）、ANSI 颜色包裹；再埋两个 `Portio_lon` 半截词当诱饵。
- "中间那条"从固定第 5 条改成 `floor(80/2)` 那条——素材变长以后，中间得是真正的中间。
- 新增"扫描规模"判据（第 8f 段）：每次按键都要重扫整段 buffer，探针记下行数与扫过的字符数
  （实测 `rows 807 / chars 16607`），并要求扫描复现的命中条数与面板计数一致。这条专门拦"只扫可视区"
  这种偷工——只扫可视区会漏掉滚动缓冲里的命中，而滚动缓冲正是"查找"最该管的地方。
- `scripts/rc.py`：`chrome_title()` 与 `a_page()` 加 `budget` 参数，A15 预算给到 20s。

**验证证据**
- 无头 `#find-test`（900×620 与默认窗宽）→ `FIND-SELFTEST-OK`：
  `long {wrote 80, flushed 80, hits 80, label 1/80, center {at 40, row 415, viewportY 408 = wantY 408, baseY 793}, last {at 79, row 805, viewportY 793 = baseY}, after 80, scan {rows 807, chars 16607, hits 80}}`。
- **反例一**（把 `findScan` 的行循环改成只扫可视区）：FAIL 五条同时点名——
  「长 buffer 计数是 2，应为 80」「计数文字是 1/2」「逐格扫得 80 条，查找认为 2 条」
  「列号对不上：`[{row:795,findCol:0,cellCol:0},{row:805,findCol:11,cellCol:7}]`」「扫描复现的命中是 2 条，应为 80」。
- **反例二**（把格号修复放回去）：FAIL 点名 emoji 行「`findCol 6 / cellCol 7`」、中文行「`6 / 11`」，
  选区取到 `" Portio_lon"`。两个反例跑完都从备份还原（`restored: True True`）。
- `python scripts/rc.py` 全跑：**15 通过 / 0 失败 / 0 跳过，68.6s**；打包后
  `A11 Portio_1.0.5-RC7_x64-setup.exe` 4545366 字节 / 4.33 MiB；两守卫与 `test_version` 都 OK。

**一个踩出来的事实（值得记住）**：`--virtual-time-budget` 下 `performance.now()` 在**定时器回调里是冻结的**——
我实测同一个回调里前后两次读数完全相同（`[89.4, 89.4]`），而页面加载时的同步代码能正常量到 18ms。
所以"边打边扫要多少毫秒"这类指标，在本轮这套无头核验里**量不出来**；探针改成只报扫描规模，
毫秒耗时如实记为未验证。这不是产品的问题，是量具的问题——别为了凑一个数字去改量具。

**未验证项**
- "边打边扫"的毫秒耗时：无头量不到（见上），只能在真机 WebView2 里用真实输入打一遍才知道。
- 800 行还不是上限（默认 `scrollback` 8000）：满缓冲时的扫描规模、滚动条拖到中间的跟手度都没量。
- 命中词**本身**含 emoji 的情形没覆盖（现在 emoji 只在前缀位置）。
- 真机 WebView2 仍未实测；中文/emoji 在真实字体度量下是否与格号一致，理论上一致但没看过。
- 清单 §4 的 9 项真服务器项、§2 其余人工项仍未跑；安装包仍未签名。

**下一步**：查找这块的"算得对"已经压到 800 行；剩下的都是**只能上真机**的账：真实输入下的耗时、
满缓冲的跟手度、WebView2 里的字符度量。这三条都无法靠无头 Chrome 回答。所以下一轮转去做
不依赖真机的下一件事——清单 §2 里还没自动化的那一项：**M10 的"密度三档"**（紧凑 / 标准 /
宽松切完不许有组件错位），把它做成 `#density-test` 并挂进 A16；这条能量、能自动核，
而且与主题切换那套几何判据可以复用同一套写法。

## 2026-11-19 · v1.0.5-RC8 · 密度两档量成数字（新增 #density-test / A16）

**这一轮为什么**：设置里能切"标准"与"紧凑"，差别只在行高（28 → 24）。这几轮我一直在修"看着歪"的东西，
但密度这一档从来没量过——"看着没歪"和"每一处都严丝合缝"是两件事。这一天把它量成数字。

**做了什么**
- `#density-test`：九处行高元素（会话栏标题 / 终端标题条 / 文件标题条 / 两路文件栏 / 两条文件行 /
  传输标题条 / 传输行）在两档里各自量高度与位置，判五件事：每档 `--row` 是 28 / 24 且两档只差 4px；
  每处高度严丝合缝等于本档 `--row`（容差 0.6px）；两档高度差正好 4px；切档只许改高度、左右位置与
  宽度一动不动（容差 1px）；切完窗口不横向溢出、导入那排不溢出会话栏。另验分段控件两档都选中对应项、
  能切回原档位。无头下文件列表只有提示、队列是空的，所以临时塞两条行进来量，量完拿掉。
- `scripts/rc.py`：plan 增 A16，A15 的分支从兜底 `else` 改成显式 `elif`。
- **改准一处不实描述**：清单 §2 的 M10 原写"设置里密度三档"，实际只有标准 / 紧凑两档。已改成"两档"，
  "宽松档"这个想法按守则记进 `docs/backlog.md`（功能扩张，RC 冻结期不做）。

**验证证据**
- 无头 `#density-test`（900×620 与默认窗宽）→ `DENSITY-SELFTEST-OK`：标准 `28px` / 紧凑 `24px` / `delta 4`；
  九处高度 28 与 24 全部对上，两档左右位置与宽度完全一致（`sessHead 0/264`、`termHead 264/360`、
  `filesHead 624/340`…）；`compactOverflow 0`、`actionsOverflow 0`；`back {standard, 28}`。
- **反例一**（文件行写死 30px）：FAIL 六条——「remoteRow 标准档高 30px，应等于 --row 28px」
  「remoteRow 两档高度差 0px，应正好 4px」以及 localRow 同样三条。
- **反例二**（只在紧凑档把本地文件栏右移 6px）：FAIL 四条——「localBar 切档后左右动了 624 → 630」
  「localBar 切档后宽度变了 340 → 334」以及 localRow 同样两条。两例跑完都从备份还原（`restored: True`）。
- `python scripts/rc.py` 全跑：**16 通过 / 0 失败 / 0 跳过，134.6s**；打包后
  `A11 Portio_1.0.5-RC8_x64-setup.exe` 4547762 字节 / 4.34 MiB；两守卫 OK。

**踩到的一处小坑**：第一次写 A16 那行时，`Edit` 的 `old_string` 只取了 A15 行的开头片段，结果把 A15 与
A16 两行内容粘成了一行、还少了结尾竖线。已用脚本按"`| python scripts/rc.py`（内部在 900×620 下打开"
这个锚点拆回两行，并补上结尾竖线（四行现在都是 6 列）。**教训**：往 Markdown 表格里插整行，`Edit`
的 `old_string` 必须整行（含结尾竖线），别只取开头几个字。

**未验证项**
- 这里量的是几何（高度、位置、宽度），量不到"24 高下 12 号字读起来挤不挤"——那仍要靠眼睛，实机未看。
- 只在无头 Chrome 里验过，真机 WebView2 未实测。
- 文件行与传输行是自检里临时塞的，真实数据行数变多后的滚动没量。
- 清单 §4 的 9 项真服务器项、§2 其余人工项仍未跑；安装包仍未签名。

**下一步**：§2 的人工项里，能与"几何量化"挂钩的都已经搬进无头套件了（M5 → A12、M6/M11 的尺寸 → A13、
M9 → A15、M10 的深浅与密度 → A14/A16）。剩下的人工项都是**看着顺不顺眼**这一类，靠无头回答不了。
所以下一轮转到另一类不依赖真机的账：**S14 首发物料里还没开工的那部分**——按排期，S14 还剩"截图素材
与多语言"。先做**多语言的地基**不现实（那是功能扩张），能做的是把发布物料里的**截图素材**用现有构建
在无头里按统一规格批量出图（固定 1180×690@2x、深浅两套、四个关键场景），这样发布页与 README 就有
一致的图可用。这条纯做物料、不碰产品代码，符合 RC 冻结的边界。

---

## 2026-11-19 · v1.0.5-RC8 · 把仓库推上 GitHub，CI 与三平台发版跑通

这一轮不碰产品代码——你拍板了"推 GitHub、建 CI、发三平台包、RC 起才发包、Alpha 只打 tag"，
所以这一轮交付的是**发布管道本身**。

**做了什么**

1. 推前先在本机把 CI 会跑的三关跑了一遍，抓到两处会让 CI 变红的东西：`cargo fmt --all --check` 有格式漂移；
   clippy 在 Rust 1.99 上报三条新 lint（`manual_is_multiple_of` / `while_let_on_iterator` / `manual_clamp`），
   另有一条 `x == false`。全修掉，顺带把 rustfmt 重排的九个文件另外提交（`0920664`、`9121e3e`）。
2. 新建 `.github/workflows/release.yml`（`79661c3`）：打 `v<版本>` tag 就触发；gate 先校验 tag 与
   仓库里的版本号一致，再按版本分流——含 `-Alpha` 不给发包（build 作业整体跳过，等于只打 tag），
   含 `-RC` 发预发布，纯版本号发正式版。
3. 建公开仓库 `github.com/yunyu697/portio`，推 main；只在仓库级配了 `credential.https://github.com.helper`
   指向 gh 的 keyring token，没动全局 git 配置、没改 git 身份。
4. 首次推送后 CI 红了：ubuntu 上编译 `portio-app` 需要 webkit2gtk 的 pkg-config 文件，`check` 作业没装依赖。
   给 check 补上同款 apt 步骤，并把 Linux runner 钉到 22.04（24.04 上没有 `libappindicator3-dev`，
   换成 `libayatana-appindicator3-dev`）（`becadf6`）。
5. 首次发版也红了，是**真 Bug**：`lib.rs` 里写的是 `if cfg!(debug_assertions) && ... { win.open_devtools(); }`，
   `cfg!` 是运行期布尔，Release 编译时这行仍要参与编译，直接 E0599。改成 `#[cfg(debug_assertions)]`
   属性宏（`cbcabfe`）。
6. 第二次发版四个作业里有三个跑完了，但整条 run 一直 `pending`：矩阵里的 `macos-13` 作业
   `runner_name` 为空、永远排队——那个镜像已退役。改成 `macos-latest` + `--target universal-apple-darwin`，
   一个 dmg 覆盖 Apple Silicon 与 Intel（`d09d5ed`）。
7. 中途遇到本机直连 github.com:443 不通（`Test-NetConnection` False），给这个仓库单独配了
   `http.https://github.com.proxy=http://127.0.0.1:7897`，推送立刻恢复。

**验证证据**

- CI 在 `d09d5ed` 上全绿，3m50s：`version rule` + `fmt / clippy / test` + 三平台 `build`（windows-latest /
  macos-latest / ubuntu-22.04，`npm run build -- --no-bundle`）。
- 发版 run `44428862667` 三项全 success，Release 已建：`Portio 1.0.5-RC8`，`prerelease: true`，四个包都在——
  `Portio_1.0.5-RC8_x64-setup.exe`（3349931 B）、`Portio_1.0.5-RC8_universal.dmg`（9451398 B）、
  `Portio_1.0.5-RC8_amd64.deb`（4939320 B）、`Portio_1.0.5-RC8_amd64.AppImage`（83139064 B）。
- gate 的分流逻辑在推 tag 之前用 Git bash 空跑过：`v1.0.5-RC8` → `version=1.0.5-RC8`、`publish=true`；
  `v1.0.5-Alpha9` → `publish=false`。

**下一步**：管道到位之后，剩下的账回到产品上——RC 阶段只修 Bug，下一轮做 S14 里还没开工的
**首发截图素材**（1180×690@2x、深浅两套、四个关键场景），纯物料、不碰产品代码。

**未验证项**

- Windows 安装包没有签名，SmartScreen 会拦（清单 §5 C1）；macOS dmg 未签名，Gatekeeper 要求右键打开。
- CI 的 mac/linux 包**只证明能构建**，没在真机上装过、跑过（清单 §4 / 应用内的真实 SSH 项同理）。
- 从 CI 出来的 exe（3.19 MiB）与本地 debug 包（4.34 MiB）体积不同，属正常；本次没有安装它验证启动。
- "Alpha 只打 tag 不发包"目前只有本地空跑与 gate 代码保证，还没有真的推过一个 Alpha tag 去跑——怕在仓库里
  留一条红色记录。下次做 Alpha 单元时会真推一次，作为正式验证。
- 仓库暂无 LICENSE（清单 §5 C6）：public 仓库没许可证默认"保留所有权利"，与"先免费开源"口径冲突，等你定。

## 2026-11-19 · v1.0.5-RC9 · 首发截图定成一套规格（八张，深浅各四）

这一轮不动产品逻辑，做的是一件迟早都要做的事：把"对外讲 Portio 用的图"从一堆随手截屏，
变成一条能重跑的流水线。以后 README、发布页、商店描述要换图，一条命令重出八张，不用再靠手气。

**做了什么**

1. 新增 `scripts/shots.py`。四个场景 × 深浅两套：主界面（`#sess-demo`）、终端 2×2 分屏（`#split-demo`）、
   导入下拉展开（新增 `#import-demo`）、设置面板与已知主机（`#hosts-demo`）。逻辑窗口 1180×690，
   强制 2 倍像素密度，产物正好 2360×1380。
2. 每张出图**先查再出**：先用 `--dump-dom` 读 `<title>`，出现 `ERR:` 就不出这张图；出完再读 PNG 头，
   尺寸不是 2360×1380 判失败。两个门都过不了就 FAIL，不会悄悄交一张歪图。
3. `ui/app.js` 顶部加了一段参数解析：钩子可以写成 `#split-demo?theme=light`，把 `?` 之后摘出来
   （`theme` 写进 `localStorage`，主 hash 用 `replaceState` 还原）。原因是下面各处 demo 判断用的都是
   `location.hash === "#split-demo"` 这类精确比较，带着 `?` 会全部失效。
4. 会话播种那块顺手覆盖了 `#import-demo` 与 `#split-demo`：分屏与导入两张图里侧栏有会话，不至于空着。
   导入菜单走的是按钮自己的 click，不是另画一份菜单。

**踩到的坑（值得记一笔）**

- 第一版八张图的文件大小一模一样（99702 B），一眼不对。查下去发现是我那段 `replaceState` 少了半个括号，
  `app.js` 整份语法错误、一行都没执行——连既有的 `#split-test` 都退回 `Portio` 默认标题。
  补上括号后 `#split-test` 立刻回到 `SELFTEST-OK`，八张体积也各不相同了。
- 教训：**"截图看着像界面"不等于脚本跑了**。样式是 CSS 的功劳，钩子、终端初始化全靠 JS。
  以后看截图先看有没有该出现的内容（会话条数、终端 banner），别只看排版。

**验证证据**

- `python scripts\shots.py`：8 张全 OK，尺寸全部 2360×1380；体积 115 KB–218 KB 各不相同。
  逐张看过 `portio-dark-split.png`（2×2 四格、侧栏 3 条会话、标题条 `1.0.5-RC9`）、
  `portio-light-settings.png`（浅色设置面板、已知主机三条 `SHA256:` 指纹、指纹截断加省略号）、
  `portio-dark-import.png`（导入菜单三项带来源路径 `~/.ssh/config` / `Sessions` / `WinSCP.ini`）。
- `cargo check --workspace` 通过（15.21s，三个 crate 都编译到 `v1.0.5-RC9`）。
- `python scripts\check_design_tokens.py` / `check_ui_scale.py` 都 OK（这轮没加任何新样式）。
- `python scripts\set_version.py 1.0.5-RC9` + `check_versions.py` OK：Cargo.toml / package.json /
  tauri.conf.json / ui/index.html 五处一致。

**下一步**：S14 还剩多语言素材（中文说明 + 英文说明两份，配同一批图）。这一轮先不推 tag——
图是物料，二进制没变，推一个 RC 包出去让人下载同一份程序没有意义；tag 留给下一次真正改产品的那一轮。

**未验证项**

- 无头浏览器没有 Tauri 后端：文件双栏是"连上主机后显示远端目录"、传输队列为空、本地目录停在
  "正在读取本地目录…"。这三处是如实画面，没有补假数据；带真实文件列表的素材要等可连的测试机。
- 这八张图只在 1180×690 这一档量过。窄窗（1024）与超宽都没有出图，发布页如果要响应式配图得另跑一档。
- 截图里没有出现真实 SSH 会话的终端输出（banner 是应用自己写的欢迎语），不能当"连上服务器的样子"用。


## 2026-11-19 · v1.0.5-RC10 · 对外介绍收成一页，中英两份

上一轮把图定下来了，这一轮补文字。目的很实在：以后要发 Release、发帖、写 README，
不用每次重新组织语言，也不用担心英文版和中文版说的不是一回事。

**做了什么**

1. 新增 `docs/press-kit.md`：中文与英文各一份「一句话 / 两句话」简介；一张「能力 vs 现状」对照表，
   中英并列一项一行；八张截图与文件名、场景、说明的对应；最后是一栏「不要这么说」的红线
   （不许把"CI 能构建"说成"支持 macOS"、不许说"安全审计过"、不许把演示图说成真连上的样子）。
2. **先把事实核过再写**。写的过程中我改了三条原本想当然的说法：
   - 字号实际是 **11–18**（滑条上写着 `min="11" max="18"`），不是我记忆里的更宽范围；
   - 口令**不是系统钥匙串**：`credentials.rs` 的注释写得很清楚——密文写 `credentials.json`、
     主密钥 `vault.key` 同目录，挡的是明文被同步盘 / 打包 / 日志带走，**不是本地提权**；
   - 口令与 `sessions.json` 分开存（会话清单里不存口令），这条也在文案里写明了。
3. README 顶部加一行指向这份物料页，免得它埋在 docs 里没人知道。

**验证证据**

- 事实核对（逐条看代码，不看记忆）：`crates/core/src/vault.rs` 的 HKDF 与主密钥说明、
  `crates/app/src/credentials.rs` 顶部注释（`vault.key` + `credentials.json`、不防本地提权）、
  `ui/index.html` 的字号滑条 `11–18`、会话导入的三个来源（`sessions_import_winscp` /
  `xshell` / ssh config）。
- `python scripts\set_version.py 1.0.5-RC10` + `check_versions.py` OK，五处一致。
- `cargo check --workspace` 通过（只改了文档与版本号，二进制逻辑没动）。
- CHANGELOG 标题核对：`^## \[1\.0\.5` 十二个小节都在，新加的 RC10 在最上面。

**下一步**：S14 的物料部分到此为止（图 + 中英文案）。再往下就是 gate 本身——清单 §5 的 C1–C3
（签名证书、自动更新端点、崩溃上报服务）等你给，等你给之前，下一轮我打算回头补"对外一致性"：
README、`docs/site/index.html`、`docs/release-notes.md` 三处的版本号与下载表都还停在 Alpha2 / RC8，
把它们对齐到当前版本，避免同一件事三个说法。

**未验证项**

- 英文版只是文案，界面本身仍是中文；界面多语言不在 RC 阶段范围，已写进 Known limitations。
- 物料页里引用的三个平台包仍是 RC8 那批，没有重新构建；mac / linux 依旧只到"CI 能构建"。
- 这份物料页没在真实发布场景里用过（没发过 Release 正文、没发过帖），文案长度是否合适还没有反馈。


## 2026-11-19 · v1.0.6-RC1 · 把三处过期的版本说法对齐

上一轮说的下一件事就是它：README、文档站、发布说明三处各自写着不同的版本，用户对照着看会以为装错了。
这一轮只改文字，不动程序。

**做了什么**

1. `docs/site/index.html` 四处：标题旁的版本号、页脚版本号都是 `1.0.5-Alpha1`；安装段示例文件名也是
   `Portio_1.0.5-Alpha1_x64-setup.exe`；版本规则那段还写着"Alpha 进一位"。统一改成 `1.0.6-RC1`、
   真实产物名 `Portio_1.0.5-RC8_x64-setup.exe`，规则补上 RC 那句。
2. `docs/release-notes.md` 三处 + 新增一行现状：一句话与安装步骤里的 `Alpha2` 换成当前版本；
   原文写着"这是内测版，用的是调试构建"——**这句已经不成立了**，RC8 起是 `tauri build` 的发布构建，
   照实改成"候选版（RC）、发布构建、功能冻结只修 Bug"；顶部加一行"版本在 1.0.6-RC1、最新包是 1.0.5-RC8"。
3. `README.md` 版本号那段补上 RC 规则与当前版本，避免只讲 Alpha 显得产品还停在很早期。

**验证证据**

- 文档站改完用 Chrome 无头实跑一遍：`--dump-dom` 拿到 `<title>Portio 使用说明</title>`，
  DOM 里**没有 `ERR:`**，旧版本标记（`1.0.5-RC10` / `Alpha1`）残留 0 处，新版本出现 4 处。
- 仓库内全文再扫一遍 `Alpha2|Alpha1|内测版|调试构建`：剩下的命中只有"规则说明"那两句（`回 Alpha1`），没有过期事实。
- `python scripts\set_version.py 1.0.6-RC1`（1.0.5 的 RC 位满了，按规则进 patch 回 RC1）+ `check_versions.py` OK。
- `cargo check --workspace` 通过（本轮只改文档与版本号）。

**下一步**：对外一致性还剩一处没覆盖——`docs/press-kit.md` 里的下载表指向 RC8、版本写 RC10，
可以等下次发包时一起动，不必单独为它进一位。真正还空着的是清单 §5 的 C1–C3（签名证书、自动更新端点、
崩溃上报服务），这三项都要你给资源才能开工；不给的话下一轮我打算清理"未推过 Alpha tag 验证"这条——
用一次本地空跑或真推一个历史版本 tag 来验证 gate 分流真的会把 Alpha 拦在"只打 tag 不发包"。

**未验证项**

- `1.0.6-RC1` 只是仓库里的开发版本号，没有对应安装包；三处文案仍指向 `1.0.5-RC8` 那批产物。
- 文档站是纯静态页，本轮只验证了在本机 Chrome 里能正常渲染，没有在别的浏览器 / 手机上过。
- 英文侧文案（`press-kit.md`）本轮没跟着改，版本数字改到下次发包时统一处理。


## 2026-11-19 · v1.0.6-RC2 · 把「tag → 发包」这条判定做成可测的

上一轮说下一轮要验证「Alpha 只打 tag」这条 gate。真推一个 Alpha tag 顺手，但推之前先看了一眼那段
判定逻辑，发现它根本没被测试过——而且兜底分支有个真问题。

**做了什么**

1. 判定逻辑从 `release.yml` 的内联 bash 搬到 `scripts/release_gate.py`：读 `ui/index.html` 的版本、
   和 tag 比对、按 `-Alpha` / `-RC` / 无后缀分流，`--github-output` 写回 `$GITHUB_OUTPUT`。
   workflow 里那 18 行 `case` 现在只剩一行调用。
2. **修掉一个会静默发错包的分支**：旧 bash 的 `case` 用 `*` 兜底，不认识的后缀一律当正式版——
   也就是说 `v1.0.6-Beta1` 会被当成正式版挂进 Latest。现在未登记的后缀直接判失败。
3. 新增 `scripts/test_release_gate.py` 17 个用例：Alpha / RC / 正式版三条分流、tag 与仓库版本不一致、
   `-Beta1` 未知后缀、PATCH 越界 `1.0.11`、tag 缺 `v` 前缀、真实仓库版本可解析、CLI 真写输出文件。
4. `docs/rc-checklist.md` C5 补一句判定逻辑与单测在哪儿。

**验证证据**

- `python -m unittest scripts.test_release_gate -v` → **17 通过**，0.078s。
- `python -m unittest discover -s scripts -p "test_*.py"` → **29 通过**（版本规则 12 + 判定 17），
  这条命令就是 CI `version` 作业跑的那条。
- CLI 真跑：`--tag v1.0.6-RC1` → `publish=True prerelease=True`；`--tag v1.0.5-RC8` → 报
  "与仓库里的版本 1.0.6-RC1 不一致"、退出码 1；`--tag v1.0.6-Alpha1` → 退出码 0、publish 为假。
- 两个 workflow 文件用 PyYAML 解析通过（release ok / ci ok）。
- `set_version.py 1.0.6-RC2` + `check_versions.py` OK；`cargo check --workspace` 15.78s 通过。

**下一步**：分流现在有单测兜底，但"推一个 Alpha tag 真的只产生 tag、不产生 Release"这件事还没在 GitHub
上实测过。再下一步打算真推一个 `v1.0.6-RC2` 的 Alpha 形态 tag？——不行，tag 必须等于仓库版本，
所以要做这件事得先选一个历史版本号打 tag；这件事会动远端，先登记，等下次单独一轮做。
在那之前的下一轮：`docs/press-kit.md` 的版本数字与下载表跟到当前版本（上次留的尾巴）。

**未验证项**

- 真 Alpha tag 的分流行为（单测覆盖了判定，没覆盖 GitHub 上的实际结果）。
- workflow 的改动只做了本地 YAML 解析，真正的 gate 作业要等下一次 tag 推送才会跑到。
- macOS / Linux 的包仍然只在 CI 里构建过，没在真机装过。


## 2026-11-19 · v1.0.6-RC3 · 对外文字一次性对齐到同一个版本

上一轮登记过的尾巴：`docs/press-kit.md` 还指着 RC8、版本写 RC10；而上一轮把 README / 发布说明 / 文档站
跟到 RC1 之后，按规则又进了一位，这三处立刻落后一版。对外文字散成四种说法，用户对照着看会以为装错了版本。
本轮只做这一件事：全部对齐到当前版本，一处不剩。

**做了什么**

1. `docs/press-kit.md`「现在可以下载什么」段：标题版本、Linux 两个真实产物名（`.deb` / `.AppImage` 具体文件名）、
   Release 页入口；「未签名」「未在真机装过」一处没删——这是这页立得住的原因。
2. README、`docs/release-notes.md`、`docs/site/index.html`、`docs/press-kit.md` 的版本串统一；
   「只改物料没重新打包」那句从「RC9 / RC10」扩成「RC9、RC10、RC1、RC2、RC3」，因为后面这几版确实都没动二进制。
3. `docs/release-notes.md`「版本号怎么读」原来写「第 1 个候选版」，进位后是错的——改成按轮次读：
   1.0.6 这轮的第 N 个候选版。这是本轮发现的一处**实质错误**，不是措辞问题。
4. 物料页开头那句「凡是标了『未签名』『内测』『仅 Windows 出过安装包』的地方都不要删」里的「内测」已经过期
   （RC 起是发布构建、三平台都有 CI 包），换成「未签名 / 未在真机装过 / 未验证」。

**验证证据**

- 文档站 Chrome 无头 `--dump-dom` 实跑：`<title>Portio 使用说明</title>`、DOM 无 `ERR:`、
  `1.0.6-RC3` 出现 4 处、旧标记（RC2 / RC1 / 1.0.5-Alpha1 / Alpha2）残留 0 处。8 条断言全 PASS。
- 逐文件数版本串：README 3 处、发布说明 3 处、文档站 4 处、物料页 2 处都是新版本；
  残留的 RC1 / RC2 只出现在「哪几版只改物料没打包」那张清单里，是有意的历史说明。
- `set_version.py 1.0.6-RC3` + `check_versions.py` → `OK v1.0.6-RC3`；`cargo check --workspace` 15.43s 通过。
- 挖出并修掉一处实质错误（「第 1 个候选版」）；写脚本次数断言 `n == want` 时逮到物料页有重复的
  `1.0.6-RC2、1.0.6-RC2`，属于上一轮批量替换的连带损伤，一并修掉。

**下一步**：S14 物料与对外口径这一条可以算收了。下一轮打算把清单 §2 的人工项里还能自动化的部分继续往前推
（M9 的「跳过去那条看着对不对」目前只有几何断言，没有视觉对比），或者补历史版本 tag —— 后者会动远端，
需要你点头。

**未验证项**

- 文档站仍只在本机 Chrome 无头里验过，没有线上地址。
- 「三平台包在真机装一遍」仍然没做（没有 macOS / Linux 机器）。
- 可下载的包仍只有 `v1.0.5-RC8`，RC9 起二进制没变，这一点对外只能如实说明。


## 2026-11-19 · v1.0.6-RC4 · 分屏下的查找只认当前格（真 Bug）

上一轮把对外文字对齐收完了，这一轮回到产品本身：从 `docs/rc-checklist.md` 的 M9（查找，实机手感）
往下挖，挖到一个不会报错、但用户会觉得"搜索不准"的真 Bug。

**Bug 长什么样**

分屏之后 `Ctrl+F` 搜的是**上一格**的 buffer：查找条里记的是上一次扫出来的行号，而终端选区落在
"当前这一格"里。于是点一下别的格换焦点之后——
- 计数还是旧格的（例如 `1/3`），新格里可能一处都没有；
- 按 Enter 跳过去，在**新格**的错行上高亮，看起来"有计数、地方不对"；
- 旧格的高亮也不收，两格同时亮。

换标签这条路本来是对的（`activateTab` 里会收起查找条），换格这条路漏了。

**改法**

- `findHits` 多记一项 `term`：记下这次扫的是哪一格的 buffer；
- `setActiveCell`（鼠标点格、右键换格、分屏后自动切格都走它）在查找条开着且扫过的不是这一格时，
  先把上一格的选区收掉，再按同一个查询词重扫一遍这一格；
- 查询词空着就只清空记录，不做无谓扫描。

改的是"跟着谁走"，不是新增功能，符合 RC 阶段只修 Bug 的口径。

**验证证据**

1. 先写用例再修：新增 `#find-pane-test`（rc.py 里的 A17），四格各写自己的标记词（3 / 1 / 2 / 1 处），
   走一遍"在 A 格查到 `1/3` → 切到 C 格 → 在 C 格查自己的词 → 切回 B 格 → 关掉"。
   修之前跑一遍是 **FAIL，10 条断言全中**：
   `切格之后查找还记着上一格的 buffer（没有重扫）`、`C 格里一处 TOKENA 都没有，却报了 3 处`、
   `切格后计数应 0/0，实际 1/3`、`A 格还留着上一轮查询的高亮`、`跳转把选区留在了别的格：[1]` 等。
   修之后同一页 `FIND-PANE-SELFTEST-OK`：`a 1/3` → `switch 0/0 termIsC:true aSel:""` → `c 1/2` → `b 1/1`。
2. `python scripts\rc.py` 全跑 **17 项全 PASS、0 FAIL、0 SKIP，114.2s**（A1 `cargo test` 82 passed；
   A15 单格查找的老判据在改动后仍然全绿；A17 报告里 `jumps 0` 表示逐条跳转没有一条选错）。
3. `node --check ui\app.js` 0；`check_design_tokens.py` OK；`check_ui_scale.py` OK；`check_versions.py` → `OK v1.0.6-RC4`。
4. 文档站无头 7 条断言全 PASS（`1.0.6-RC4` 4 处、RC3 / RC2 / 1.0.5-Alpha1 残留 0）。

**踩的坑**

第一版用例的标记词写在行中间（`第 2 格 命中 1：PANEB_TOKEN`），分屏后每格只有二十来列，词被折到下一行，
"按整词搜"一条也搜不到，于是先假失败一次（`四格素材没写全：[0,0,0,0]`）。把标记词挪到行首、
外加把窗口钉成 1180×690 之后才拿到真实结果。这条记在这里：**分屏用例的素材必须活得过一次折行**。

**下一步**

RC4 起前端有改动，二进制变了，该出包了：本地打一份 NSIS 包 → 推 `v1.0.6-RC4` tag 走 CI 三平台 →
Release 里能看到真包。这一步会动远端（推 tag、建 Release），按守则属于日常动作，下一轮做。

**未验证项**

- 分屏 + 查找只在无头里跑过；真实窗口里"点一下那格、看高亮跳没跳过去"的一遍没做（机器常被占用）。
- 本轮没出包，可下载的仍是 `v1.0.5-RC8`；文档里已经写明"RC4 起前端改过，包要重新打"。
- 三平台包仍未在真机装过；真服务器相关的 B1–B9 依旧一项没做。


## 2026-11-19 · v1.0.6-RC4 · 把 RC4 发出去：三平台包上架（本轮不进位）

上一轮修完分屏下的查找 Bug，日志里就写了"下一轮该出包了"。这一轮只做这一件事：把 RC4 真的发出去，
让别人能下载到。

**做了什么**

1. `python scripts\check_versions.py` → `OK v1.0.6-RC4`，推 `v1.0.6-RC4` tag（tag 必须等于仓库版本，
   否则 `scripts/release_gate.py` 会判失败退出）。
2. 发版工作流 `44469913056` 跑完：`gate` 判定 `publish=true` / `prerelease=true`（RC 走预发布，不进 Latest），
   然后 `windows-x64` / `macos-universal` / `linux-x64` 三个 build 全 success。
3. Release 已建：**`Portio 1.0.6-RC4`**，`isPrerelease: true`、`isDraft: false`，四个资产都在——
   `Portio_1.0.6-RC4_x64-setup.exe` 3349729 B、`Portio_1.0.6-RC4_universal.dmg` 9456257 B、
   `Portio_1.0.6-RC4_amd64.deb` 4939024 B、`Portio_1.0.6-RC4_amd64.AppImage` 83134968 B。
4. 本地也打了一份对照包（`tauri build --debug --bundles nsis`，53.41s）：`Portio_1.0.6-RC4_x64-setup.exe`
   4548074 B —— 比 CI 那份大，因为 debug 不剥符号；两份都可装，正式下发用 CI 那份。
5. 文档对齐（四处说的都变成"最新一批包就是 RC4"）：README 版本段、`docs/release-notes.md` 当前状态与两处产物名、
   `docs/site/index.html` 安装段的示例文件名、`docs/press-kit.md` 下载表（连体积一起写实）。
   `docs/rc-checklist.md` 的「最近一次整跑」改成 RC4 / 17 项，§7 记录表补 RC4 那一行（含打包结果）。

**验证证据**

- `gh run view 44469913056` → 四个 job 全 `success`；`gh release view v1.0.6-RC4` → 四资产、`prerelease:true`、`draft:false`。
- 本地实机启动新构建的 `target\debug\portio-app.exe`：进程存活 6 秒无崩溃（`alive=True`）。
  **截屏没截到窗口**：桌面处于锁屏状态，抓屏抓到的是锁屏壁纸（`_rc4_real.png` 4508544 B），
  所以"窗口在真机上长什么样"这一眼仍未做。
- 文档站无头（上一轮那套 7 条断言）在本次改动后重跑仍全 PASS。

**为什么本轮不进位**

本轮没有改产品代码，只是把 RC4 这版发出去。tag 必须等于仓库里的版本号，所以版本停在 `v1.0.6-RC4`。
如果为了"每轮进一位"改成 RC5，仓库就会领先于刚发出去的包，对外反而说不清"你下的到底是哪版"。
下一个真正改了东西的单元再进位（那一步会是 RC5）。

**下一步**

1. 真窗口点检：把 RC4 的安装包装上，实机打开、分屏、点格换焦点试一遍查找（就是上一轮修的那个 Bug），
   顺手给桌面截一张（这台机器锁屏时截不到窗口，得等能解锁的时候）。
2. `docs/rc-checklist.md` 的 M1–M12 人工项与 B1–B9 真服务器项依旧没跑；无 SSH 服务器这条阻塞没解。
3. 清单 §5 的 C1–C3（三平台签名证书 / 自动更新端点 / 崩溃上报）与 C6（许可证选型）仍在等人给。
4. 历史版本 tag 要不要补打，等用户拍板。

**未验证项**

- macOS universal dmg 与 Linux deb / AppImage 仍只到"CI 构建通过"，**未在真机装过**。
- Windows 包能装能跑（历次验过），但 RC4 这一版没重新装一遍 —— 本轮只做了进程启动存活检查。
- 真实窗口视觉确认（锁屏挡住了），未做。
- 无 SSH 服务器与凭据 → 真实登录、PTY、tmux、SFTP 传输一律未验证（长期阻塞）。


## 2026-11-19 · v1.0.6-RC5 · 「新建连接」会把上一台机器的参数留下来（顺手把 M2 自动化）

前一轮把 RC4 的包发了出去，日志里留的第一条待办是"真窗口点检"。这一轮桌面依然锁着
（`LogonUI.exe` 在跑），所以换个能一次收口的：把清单 §2 的 M2（三类连接入口）自动化，
过程中拿出一个真 Bug。

**发现的 Bug**

`openConnect()` 原来只有"有预填"那半支在赋值，空白那半支只清了主机、口令两项：

```js
} else {
  el("f-user").value = localStorage.getItem("portio.user") ?? "";
  el("f-host").value = "";
  el("f-password").value = "";
}
```

于是这样一条路就出事了：右键一台**密钥登录、端口 2222** 的会话 → 编辑连接参数（面板填满、认证切成密钥、
私钥路径填上）→ 关掉 → 点「新建连接」。按不懂技术的使用者的理解，这里该是干净的空白表单；
实际看到的是端口 `2222`、认证停在 `key`、私钥框里还躺着上一台机器（甚至上一台**服务器**）的私钥路径。
不说会连错机器，至少会带着别人的私钥路径去试。RC 阶段正好只修 Bug，这就是该修的那一类。

**改法**

`openConnect()` 里把六项一律每次都写一遍（主机 / 端口 / 用户名 / 认证 / 私钥路径 / 口令），
两个字段框的显隐也按 `auth` 算一次，不再分两支各写一半。以后面板再加字段，也不会漏清。

**新增回归 A18 `#connect-entry-test`**

M2 原来写在"需要人点"的清单里，但它要验的全是逻辑（面板开没开、字段对不对），无头完全做得掉：

1. 先把面板弄脏（按密钥 + 2222 打开），关掉，再点「新建连接」→ 读六个字段；
2. 快速连接框写 `deploy@10.0.8.12:2222`，回车 → 主机 / 端口 / 用户 / 认证全比对；
3. 双击**口令认证**那台会话（密钥认证双击是直连、不进面板）→ 字段带对；
4. `ssh://ops@[fe80::1]:2200` → 主机 `fe80::1`、端口 `2200`（顺手钉住括号 IPv6 不被冒号切错）；
5. 空输入只提示、不开面板。

为此沿用前面几轮的写法：把自检块塞进 `ui/app.js`、按 hash 触发、结果写 `<title>`；
`scripts/rc.py` 里加 A18 并分派到 `#connect-entry-test`（1180×690、8s 虚拟时间）。
`docs/rc-checklist.md` §1 补 A18 行、段首改 A1–A18，§2 的 M2 从 `◻` 改成 `✅ 自动化`。

**验证证据**

- **反向验证（先证它能抓 Bug）**：把 `openConnect` 换回老写法再跑 A18 → 标题变
  `CONNECT-ENTRY-SELFTEST-FAIL`，`新建连接`那组**5 条断言**全炸并逐条点名：
  `端口回 22："2222" ≠ "22"`、`认证回口令："key" ≠ "password"`、
  `私钥路径清空："C:/Users/me/.ssh/id_ed25519" ≠ ""`、`私钥框收起：true ≠ false`、`口令框露出：false ≠ true`。
  换回修好的版本，同一页立刻 `CONNECT-ENTRY-SELFTEST-OK`。
- **整跑**：`python scripts/rc.py` → **18 通过 / 0 失败 / 0 跳过**，117.2s
  （A1 `cargo test --workspace` 82 passed 也在里面；A11 认到新包 `Portio_1.0.6-RC5_x64-setup.exe` 4.34 MiB）。
- 守卫：`check_versions.py` → `OK v1.0.6-RC5`、`check_design_tokens.py` / `check_ui_scale.py` 都 OK、`node --check` 通过。
- **发版**：推 `v1.0.6-RC5` tag → run `44477846989`：`gate` 判 `publish=true` / `prerelease=true`，
  `windows-x64` / `linux-x64` / `macos-universal` 三个 build 全 success。
  Release **`Portio 1.0.6-RC5`**（`prerelease: true`、`draft: false`）四资产：
  `Portio_1.0.6-RC5_x64-setup.exe` 3352875 B、`Portio_1.0.6-RC5_universal.dmg` 9460253 B、
  `Portio_1.0.6-RC5_amd64.deb` 4940892 B、`Portio_1.0.6-RC5_amd64.AppImage` 83134968 B。
- 本地另打一份对照包（`tauri build --debug --bundles nsis`，44.29s）：`Portio_1.0.6-RC5_x64-setup.exe`
  4555570 B（debug 不剥符号，比 CI 大），已放到 `new-chat\` 根，正式下发用 CI 那份。
- 文档同步：README 版本段、`docs/release-notes.md`（当前状态 + 两处产物名）、`docs/site/index.html`
  四处版本串与安装段示例名、`docs/press-kit.md` 下载表（连体积一起换到 RC5）。
  `docs/rc-checklist.md` 的「最近一次整跑」改 RC5 / 18 项，§7 补 RC5 行。

**下一步**

1. 真窗口点检（仍缺）：装上 `Portio_1.0.6-RC5_x64-setup.exe`，打开 → 分屏 → 点别的格换焦点 → `Ctrl+F`；
   再走一遍"编辑一台密钥会话 → 关掉 → 新建连接"，看表单是不是真的干净了。锁屏时截不到窗口，得等能解锁。
2. 清单里还剩下的自动化机会：M3（会话增删改与分组落盘，可以靠重开页面模拟）、M12（已知主机删除后重连走首次信任，
   这半截在 Rust 侧能测）。M7 复制粘贴与 M8 分屏仍是"真键盘手感"，留给人。
3. 等用户给的仍是那几项：三平台签名证书、自动更新端点、崩溃上报（C1–C3）与许可证选型（C6）。

**未验证项**

- A18 只在无头里跑过，真实窗口点着看的那一遍未做（截屏时桌面锁着）。
- macOS universal dmg 与 Linux deb / AppImage 只到"CI 构建通过"，**未在真机装过**。
- 无 SSH 服务器与凭据 → 真实登录、PTY、tmux、SFTP 传输一律未验证（长期阻塞）。


## 2026-11-19 · v1.0.6-RC6 · 重开之后「最近使用」空了：前后端把时间字段叫成了两个名字

上一轮把 M2 收进 A18，日志里留给这一轮的是 M3（会话增删改与分组）。M3 里"结果落盘、关掉重开还在"
这半句正好戳到一处一直被忽略的地方——顺手挖出一个从 Alpha 就在的 Bug。

**发现的 Bug**

`ui/app.js` 存清单时写的是 `last`：

```js
sessionStore.records = [{ ...rec, last: Date.now() }, ...next].slice(0, 40);
```

而磁盘那头的 `SessionRecord`（`crates/core/src/store.rs`）字段叫 `last_used`，还被 `#[serde(default)]`
兜着。于是每次 `sessions_write` 都**认不出** `last`、按默认值 0 落盘——存一次，全部记录"上次用过"归零。
后果是重开之后：没有一台算"最近用过"，「最近使用」这组直接消失，常用机器全挤进「更早」；排序也退化成
文件顺序（看着还像对的，只是不再"最近的在最上面"）。不报错、不丢数据，纯粹安静地把一层便利磨掉。

**改法**

- 界面统一改用 `last_used`（`saveSession` 写入、列表排序、最近使用筛选三处）；
  另留 `lastUsed(s)` 同时认 `last_used` 与老文件里的 `last`，老清单不至于读坏。
- `#sess-demo` 里那条"从没用过"的播种记录同步改名，否则截图里的分组会怪。
- 落盘那半步抽出 `write_store_atomic(path, store)`（先写 `.json.tmp` 再改名），并补两条单测：
  ① 目录不在时自建、写完不留临时文件、整份覆盖不叠加旧行、`last_used` 一路不丢；
  ② 坏 JSON 在校验那步就被拒、磁盘上原来那份好文件原封不动。

**新增回归 A19 `#sessions-test`**

清单 §2 的 M3 逻辑部分无头全做得掉，于是按使用者的手指顺序走一遍：

1. 加三条不同机器 → 三条、最近存的排最前；
2. 同一台再存一次 → 不新增一条、内容换成新的并排到最前、列表仍三行；
3. 清单里不许出现口令字段（口令走另一套加密文件）；
4. 连存 45 条 → 封顶 40、最老的被挤掉、最新的还在；
5. 分两组 → 组头与计数对；折叠 → 组头带 `folded`、组员行收起、折叠状态进 localStorage；
   展开回来；移出分组 → 落回「未分组」；解散最后一组 → 回到「最近使用」；
6. 删一条 → 清单与列表同时少一行；
7. 搜索 `web` → 只剩一条、计数 `1/2`；搜不到时列表空；清空复原；
8. **磁盘上的 `last_used` 读回来要认得出「最近使用」**，老写法 `last` 也认——这条就是本次 Bug 的钉子。

`scripts/rc.py` 加 A19（19 项），`docs/rc-checklist.md` §1 补 A19 行、段首改 A1–A19，
§2 的 M3 从 `✗ 拖拽` 改成 `✅ 自动化（A19）/ ✗ 拖拽`（拖拽分组仍记在 backlog）。

**验证证据**

- **反向验证**：把 `saveSession` 与排序换回 `last` 再跑 A19 → `SESSIONS-SELFTEST-FAIL`，
  点名的正是 `磁盘上的 last_used 认得出最近使用：false ≠ true`；换回修好的版本立刻 OK。
- **整跑**：`python scripts/rc.py` → **19 通过 / 0 失败 / 0 跳过**，109.2s
  （A1 `cargo test --workspace` **84 passed**，其中 app crate 16 passed 含新增两条落盘单测）。
- 守卫：`check_design_tokens.py` / `check_ui_scale.py` OK、`node --check ui/app.js` 通过、`check_versions.py` → `OK v1.0.6-RC6`。
- **发版**：推 `v1.0.6-RC6` tag → run `44482762020`：`gate` 判发包，`windows-x64` / `macos-universal` /
  `linux-x64` 三个 build success；Release **`Portio 1.0.6-RC6`**（`prerelease: true`）四资产
  （exe 3353673 B / dmg 9467814 B / deb 4947424 B / AppImage 83143160 B；linux 作业这次跑了约 30 分钟才收口）。
- 本地另打一份对照包（`tauri build --debug --bundles nsis`）：`Portio_1.0.6-RC6_x64-setup.exe` 4551034 B。

**下一步**

1. 真窗口点检（仍缺）：装上 RC6，打开 → 分屏 → 换格 → `Ctrl+F`；会话栏右键走一遍"分到分组 / 移出 / 解散 / 删"，
   关掉重开看分组与「最近使用」还在不在。桌面锁着时截不到窗口，得等能解锁。
2. 清单里最后一个有明显逻辑的自动化机会：M12（已知主机删除后重连走首次信任，Rust 侧能测）。
   之后 M7 / M8 属"真键盘手感"，只能留给人。
3. 等用户给的仍是：三平台签名证书、自动更新端点、崩溃上报（C1–C3）与许可证选型（C6）。

**未验证项**

- A19 只在无头里跑过；真机上点着做一遍（含双击连上、右键菜单）未做（截屏时桌面锁着）。
- 拖拽分到分组一直没做（`docs/backlog.md` 有记）。
- macOS dmg 与 Linux deb / AppImage 只到"CI 构建通过"，**未在真机装过**。
- 无 SSH 服务器与凭据 → 真实登录、PTY、tmux、SFTP 传输一律未验证（长期阻塞）。


## 2026-11-19 · v1.0.6-RC7 · 「主机密钥变了」这句提示，其实一直没送出去

上一轮日志留给这一轮的是 M12（设置 → 已知主机：列出、删除、删除后重连走首次信任）。
打开那段代码顺着走一遍，发现一件更难看的事：**界面一直在等一个从来没被发出来的信号。**

**发现的 Bug**

`ui/app.js` 里有两处靠 `raw.includes("HOSTKEY_CHANGED")` 分辨"密钥变了"和其它连接失败
（终端里那段红字、连接面板的 catch 分支），文案写得很清楚：

> 记录：SHA256:xxx
> 本次：SHA256:yyy
> 如果你确认服务器重装过，去「设置 → 已知主机」删掉这台机器的记录，再连一次就会重新信任。

可是这个前缀根本没被发出来过。`crates/app/src/sessions.rs` 只在 `kh.verify(...)` **之后**
看到 `HostKeyVerdict::Changed` 才拼 `HOSTKEY_CHANGED|…`；而指纹对不上时 `SshSession::connect`
在握手阶段就把连接拒了（`SshError::HostKeyMismatch`），那半段代码永远走不到。
人真正看到的只有 `主机密钥校验失败：记录的是 X，服务器给的是 Y`——知道出事了，却不知道下一步干什么。

**改法**

- `crates/ssh`：`SshError::HostKeyMismatch` 从 `String` 改成带 `expected` / `actual` 的结构变体；
  新增 `hostkey_changed_tag()` 统一产出 `HOSTKEY_CHANGED|记录|本次`。做成方法而不是让 app 层去拆
  错误字符串——以后改中文文案也不会把界面契约拆坏。
- `crates/app`：建连失败统一走新抽出的 `connect_error_text()`；`verify` 之后那支保留为兜底并注明
  "正常路径走不到这里"。
- 校验标准一点没松：删记录只是让这台主机重新走一次首次信任；重新信任之后再换第三把钥匙，照样报变更
  （这条写进了单测）。

**新增 A20 `#hosts-test`（已知主机面板）**

M12 的"能看见的那半句"按顺序走一遍：三条记录画三行、计数「3 条」；长指纹只露前 10 位加省略号、
全文挂 `title`；删掉 `h.example.com:2222` 之后同一台机器的 `:22` 还在（**端口是键的一部分**）、
计数变「2 条」、回执文案对；IPv6 主机 `[::1]` 整串显示也能删；删空之后没有行、计数写「无」、
空态那句解释在；再喂一批能正常长回来。

顺带把核验页的删除行为做实：`#hosts-demo` / `#hosts-test` 没有后端，删除就删内存里那几条，
不像以前只是点了没反应——否则"点完少一行、计数跟着变"这条路一次都没被真走过。

**Rust 侧四条单测**

1. `lib.rs`：变更错误能变成三段式标记，且只有变更错误带标记（超时 / 认证失败 / 通道断开都不许带）。
2. `sessions.rs`（app）：`connect_error_text` 对变更给前缀、对其它错误保留自己的中文措辞。
3. `known_hosts`：`forget_makes_the_next_connection_first_seen_again`——有记录时 `fingerprint_of` 带旧指纹；
   删掉之后必须变回 `None`（否则"点完删除仍连不上且不知为何"）；随后同一台换钥匙来连算 `FirstSeen`；
   再换第三把钥匙来，仍然报 `Changed`。
4. `known_hosts`：`forget_only_touches_the_port_it_names`——忘掉某台机器的 2222，它的 22 必须还在。

**验证证据**

- **反向验证（两处，都改回老写法再跑）**
  1. `connect_error_text` 改回 `e.to_string()` → app crate 那条断言 FAIL：
     `三段式：主机密钥校验失败：记录的是 SHA256:OLD，服务器给的是 SHA256:NEW`。
  2. 核验删除改回"只按 host 删" → A20 FAIL 并点名
     `同机另一端口还在：false ≠ true`、`计数跟着变："1 条" ≠ "2 条"`、`删掉一条后剩两行：1 ≠ 2`。
  两处还原后立刻 OK（`HOSTS-SELFTEST-OK`）。
- **整跑**：`python scripts/rc.py` → **20 通过 / 0 失败 / 0 跳过**，83.8s
  （A1 `cargo test --workspace` **90 passed**，比上轮 84 条多出的正是这四 + 两处新增）。
- 守卫：`check_design_tokens.py` / `check_ui_scale.py` OK、`node --check ui/app.js` 通过、`check_versions.py` → `OK v1.0.6-RC7`。
- **发版**：推 `v1.0.6-RC7` tag → run `44494644638`：gate 判发包，三平台 build 全 success；Release
  **`Portio 1.0.6-RC7`**（`prerelease: true`）四资产：exe 3358391 B / dmg 9472094 B / deb 4947594 B / AppImage 83139064 B。
- 本地对照包 `tauri build --debug --bundles nsis` → `Portio_1.0.6-RC7_x64-setup.exe` 4555374 B。

**下一步**

1. M12 只剩"真机上点一遍"的手感；M7 / M8 也是纯手感。清单 §2 的人工项到这里已无自动化余地。
2. 下一个可推的单元：清单 §4 的 B1–B9 全部需要真服务器（阻塞），§5 的 C1–C3 需要用户给证书/端点。
   剩下能自己做的，是 §3 里几条与"打包 / 升级 / 日志"相关的收尾——下一轮去 §3 挑一条。
3. 等用户给的仍是：三平台签名证书、自动更新端点、崩溃上报（C1–C3）与许可证选型（C6）。

**未验证项**

- 真·主机密钥变更要有服务器换钥匙才能走通；这轮只有单测与错误映射，**没有实测**。
- "删记录 → 重连"整条要真机 + 真服务器；这里只到协议层与面板层。
- 桌面锁着（`LogonUI.exe` 在跑），真窗口点检仍没做。
- macOS dmg 与 Linux deb / AppImage 只到"CI 构建通过"，**未在真机装过**。
- 无 SSH 服务器与凭据 → 真实登录、PTY、tmux、SFTP 传输一律未验证（长期阻塞）。


## 2026-11-19 · v1.0.6-RC8 · 崩溃那一行日志，可能根本写不进去

上一轮日志留的下一步是"去清单 §3 挑一条打包 / 升级 / 日志类的收尾"。翻了 `crates/app/src/diag.rs`
（运行日志与崩溃采集，338 行），撞到一个不需要服务器就能证明的缺陷。

**发现的 Bug**

`write_entry` 用一个进程级的 `AtomicBool` 挡重入：

```rust
static IN_HOOK: AtomicBool = AtomicBool::new(false);
if IN_HOOK.swap(true, Ordering::SeqCst) { return; }   // 有人正在写 → 这一条直接扔掉
...
IN_HOOK.store(false, Ordering::SeqCst);
```

这个开关本来的意思只有一句："写日志自己炸了，崩溃钩子又要写一遍，别递归。"可它是**进程级**的，
于是"别的线程正在写"也被当成了重入。现实里同时写日志的地方不止一处：

- 界面那边 `window.onerror` 与 `unhandledrejection` 都走 `diag_log`，一次抛一串错误就是连续几条；
- 几个 tokio 任务同时报错；
- 最要命的一种：一个任务正在写日志时另一个任务 panic —— 崩溃那条**静默消失**，日志里连"丢过"都看不出来。

**改法（两道闸各管一件事）**

- **同线程重入**：换成 `thread_local` 的 `Cell<bool>`，配一个 `Drop` 自动复位。
  panic 展开时必定复位，不然这个线程从此所有日志都会静默消失（比丢一条更坏）。
- **跨线程**：排一把 `Mutex<()>`，一个写完再放下一个；前一个写的人炸了（poison）用
  `into_inner()` 接着写，不让一次异常把整个日志功能废掉。
- 顺带把落盘那半步抽成 `write_entry_to(file, level, source, message)`，让并发这条路能在单测里真跑
  （不用为了测一句日志去造一个 `AppHandle`）。

**两条单测**

1. `concurrent_writers_never_lose_a_line`：8 线程 × 120 条 → 磁盘上必须**正好 960 行**；
   每行只含一条日志（`[ERROR]` 出现次数 = 1，拦"两条的字插到同一行"）；120 个内容逐条都在、无重复。
2. `reentry_on_the_same_thread_is_skipped_and_the_gate_resets`：重入被放过（不落盘、不递归），
   且闸放开之后下一条必须真落盘——拦"闸卡死"。

**验证证据**

- **反向验证**：把互斥改回老写法（进程级 `AtomicBool` + `swap` 就 `return`）→
  `concurrent_writers_never_lose_a_line` FAIL，点名
  **「并发写日志丢了行：只落下来 120 / 960」**（8 个线程各写 120，最后只有 120 条落盘，其余 840 条全被丢）；
  还原后立刻 ok。
- **整跑**：`python scripts/rc.py` → **20 通过 / 0 失败 / 0 跳过**，111.4s
  （A1 `cargo test --workspace` **92 passed**，比 RC7 那轮 90 条多出的正是这两条）。
- 守卫：`check_design_tokens.py` / `check_ui_scale.py` 未涉及界面、仍随 A3/A4 全绿；`check_versions.py` → `OK v1.0.6-RC8`。
- **发版**：推 `v1.0.6-RC8` → run `44503329899` gate + 三平台 build 全 success；Release
  **`Portio 1.0.6-RC8`**（`prerelease: true`）四资产：exe 3356439 B / dmg 9463772 B / deb 4945556 B / AppImage 83139064 B。
- 本地对照包 `tauri build --debug --bundles nsis` → `Portio_1.0.6-RC8_x64-setup.exe` 4556946 B。

**下一步**

1. 日志这条线还剩一处同性质的地方：`diag_tail`（「复制诊断信息」）用 `read_to_string` 读整份日志，
   文件里只要有一个坏字节就整段返回空——**恰好是"日志坏了、我更需要把它交出去"的时候**。
   下一轮若还走日志线，就把它改成按字节读 + 容错解码，并补一条"半截/损坏文件里仍能拿到前面几行"的单测。
2. 或者换去 `diag_reveal`（Windows 走 `explorer.exe /select,<带空格的中文路径>`）——这条只在真机上能验，
   属于 M 类手感。

**未验证项**

- 并发"不丢行"只在回环临时文件上证明过（8 线程 / 960 行）；真实机器上磁盘慢、日志目录被占用、
  杀软扫描锁文件这类情形没模拟。
- 崩溃钩子这条路没有真的触发过一次 panic 去录日志（要真让应用崩一次才能验），只有单测覆盖重入与复位。
- 桌面锁着，真窗口仍未点检；mac / linux 包仍只到"CI 构建通过"。
- 无 SSH 服务器与凭据 → 真实登录、PTY、tmux、SFTP 传输一律未验证（长期阻塞）。


## 2026-11-19 · v1.0.6-RC9 · 「复制诊断信息」读不出东西的时候，正是我最需要它的时候

上一轮日志留的下一步就是这一条。`diag_tail`（「复制诊断信息」用的那个命令）长这样：

```rust
let raw = match std::fs::read_to_string(&path) {
    Ok(t) => t,
    Err(_) => return Ok(String::new()),   // 读不动 → 当作没有内容
};
```

整份文件一次性当 UTF-8 读进来。文件里只要有**一个**非法字节——半截写入、别的程序往这个文件里写过东西、
磁盘出错、日志被外部工具转码过——`read_to_string` 就 `Err`，函数返回空串。于是：

- 我看到的"复制诊断信息"是**空的**，看起来像"这台机器一条日志都没有"；
- 而坏字节**前面**那些完好的行，本来一个字都没丢，也被一起吞掉了；
- 日志坏掉恰恰是出事的一种，这个按钮本来就是给出事用的。

**改法**

按 `\n` 切字节、逐行 `String::from_utf8_lossy` 解码：坏字节就地变成一个 `�`，坏字节**前后**完好的行都留住；
`\r\n` 的行尾去掉。抽成两个可测的函数：

- `pub fn tail_of(bytes: &[u8], want: usize) -> String`（纯函数，按行切开取最后 N 行）
- `pub fn read_tail_file(file: &Path, want: usize) -> String`（读字节 → `tail_of`；文件不存在/读不动读成空）
- `diag_tail` 只剩"取路径 + 夹 lines 到 1..=200"。

**三条单测**

1. `a_damaged_log_still_yields_the_intact_lines`：先写五行正常日志，再塞一行含
   `\xff\xfe\x00\x80\x81` 的坏内容，最后接一条正常的尾巴 → 断言第 0 行、第 3 行、最后一条都在；
   坏行里出现 `�`；共 7 行；输出里没有 `\r`。
2. `tail_of_keeps_only_the_last_lines_and_handles_edges`：只取最后 2/1 行、N 大于行数、
   空文件、全是换行、单行无换行、CRLF。
3. `a_missing_log_reads_as_empty`：文件不存在 → 空串。

**验证证据**

- **反向验证**：把 `read_tail_file` 改回 `read_to_string` 那套 →
  `a_damaged_log_still_yields_the_intact_lines` FAIL，点名 **「坏字节前面完好的行没拿到：""」**；
  还原后 `diag::tests` 13 条全 ok。
- **整跑**：`python scripts/rc.py` → **20 通过 / 0 失败 / 0 跳过**，116.6s
  （A1 `cargo test --workspace` **95 passed**，比 RC8 的 92 多出的正是这三条）。
- **发版**：推 `v1.0.6-RC9` → run `44512390674` gate + 三平台 build 全 success；Release
  **`Portio 1.0.6-RC9`**（`prerelease: true`）四资产：exe 3358660 B / dmg 9470390 B / deb 4945780 B / AppImage 83147256 B。
- 本地对照包 `Portio_1.0.6-RC9_x64-setup.exe` 4555962 B。

**顺手修掉的一条 CI 红（run 44505662151）**

上一轮 RC8 的并发单测没跑 `cargo fmt`：一个 `assert_eq!` 一行太长，CI 的
`cargo fmt --all --check` 直接红；顺手跑 clippy 又发现一处 `format!("纯字面串")`。
本轮一并补上：`cargo fmt --all` → `cargo fmt --all --check` exit 0；
`cargo clippy --workspace --all-targets -- -D warnings` exit 0；`cargo test --workspace` 95 passed。
提交 `b8915cf chore(fmt)`。

> 记一笔事实：`v1.0.6-RC9` 这个 tag 落在格式化**之前**的提交 `a91c524` 上。发版 workflow 的 gate 只查
> "四处版本一致 + tag 该不该发包"，不跑 fmt/clippy——所以包本身没问题；fmt 那条闸在另一条 CI workflow 里，
> 它跑的是 main 上的新提交 `b8915cf`。以后每轮提交前都要自带 `cargo fmt --all`。

**下一步**

1. 日志这条线已经修完两处（RC8 并发丢行、RC9 损坏文件读空）。下一个候选是
   `diag_reveal` 的 Windows 分支：`explorer.exe /select,<路径>` 只有一个参数，路径里含空格/中文时
   能否正确选中文件，只在本机真机点一次才知道（属 M 类手感，锁屏时做不了）。
2. 或者转去清单 §3 里还没走到的打包项：Windows 只有 NSIS、没有 msi；
   Linux 只有 deb + AppImage、没有 rpm——这属于"要不要加发包目标"，得用户拍板，登记着。
3. 再往下的纯代码项：`sessions.rs` 里 `SshError` 写成全路径 `portio_ssh::SshError`（该提到文件顶部 use），
   这只是整洁度，不是 Bug。

**未验证项**

- 损坏文件只在临时目录里造出来验过；真实磁盘坏块、文件被别的进程同时写、被转码工具改过这类情形没模拟。
- 日志目录里只剩 `portio.log.1`（刚轮转完、新文件还没建）时「看日志」读不到内容——既有行为，本轮没动。
- 桌面锁着，真窗口仍未点检；mac / linux 包仍只到"CI 构建通过"。
- 无 SSH 服务器与凭据 → 真实登录、PTY、tmux、SFTP 传输一律未验证（长期阻塞）。


## 2026-11-19 · v1.0.6-RC10 · 那个「定位日志文件」按钮，在我这台机器上是哑的

上一轮日志的自检清单里写着：`diag_reveal` 的 Windows 分支值得实机点一次。真去读代码时发现，
它不只是"要验证"，更像是本来就不会成功：

```rust
Command::new("explorer.exe")
    .arg(format!("/select,{}", path.display()))
```

Rust 的 `Command::arg` 在 Windows 上会给含空格的参数加引号。`/select,<路径>` 是一个参数，
而我的日志路径是 `C:\Users\Tyler Zhang\AppData\Local\…\portio.log`——用户目录里有空格。
于是送出去的命令行变成：

```
"explorer.exe" "/select,C:\Users\Tyler Zhang\AppData\Local\…\portio.log"
```

引号把 `/select,` 一起包了进去。资源管理器解析到的开关名是 `/select,C:\Users\Tyler`，
剩下的 `Zhang\AppData\…` 被当成别的参数——它去选一个不存在的路径。这个按钮在"用户名带空格"
的机器上（我猜这是 Windows 上最常见的一类用户名）一直是没反应的，而用户无从知道是它坏了。

资源管理器要的形态是 `/select,"C:\完整\路径"`：引号只包路径。改法两步：
`select_arg` 拼 `/select,"<路径>"`；送出去时用 `CommandExt::raw_arg` 逐字写进命令行——
explorer 不按常规引号规则解析，交给系统再拼一遍会被改坏。命令构造抽成
`reveal_command(&path)`，生产路径和测试用同一处，这样测试才拦得住回归。

**验证证据**

- **反向验证**：把 `reveal_command` 改回 `.arg(format!("/select,{}", …))` →
  新加的 `select_arg_keeps_the_switch_outside_the_quotes` FAIL，并把真实命令行打到日志里：
  `"explorer.exe" "/select,C:\\Users\\Tyler Zhang\\AppData\\Local\\portio\\logs\\portio.log"`
  （引号正好落在 `/select` 前面，就是那个 Bug 的样子）；还原后 ok。
- **单测**：含空格的英文路径、含空格的中文路径（`D:\日志 目录\portio.log`）都断言"引号只包路径"；
  再用 `Command` 的真实命令行断言"旧写法把开关括进引号、新写法没有"——不需要真开窗口。
- **整跑**：`python scripts/rc.py` → **20 通过 / 0 失败 / 0 跳过**，86.2s
  （`cargo test --workspace` **96 passed**，比 RC9 多出的正是这一条）；`cargo fmt --all --check` 与
  `clippy -D warnings` 均 exit 0。
- **CI**：main run `44518756656` 五项全 success（fmt/clippy/test 也绿了——上一轮 `b8915cf` 的补救生效）。
- **发版**：推 `v1.0.6-RC10` → run `44518772700` gate + 三平台 build 全 success；Release
  **`Portio 1.0.6-RC10`**（`prerelease: true`、`draft: false`）四资产：
  exe 3358285 B / dmg 9470333 B / deb 4944570 B / AppImage 83134968 B。本地对照包 4558534 B。

**下一步**

1. 日志这条线还有一处真的没修：**轮转刚发生、`portio.log` 还是空的、内容都在 `portio.log.1` 里**时，
   「看日志」与「复制诊断信息」都读到空。修法是"当前文件为空则回落到 `.1`"，属于下一个候选单元。
2. 实机点检仍欠着：装上 RC10 → 设置 → 运行日志 →「定位」看资源管理器是不是真选中了那个文件。
   桌面锁着做不了，等哪一轮桌面是开的时候补。
3. 其余仍是等用户拍板的老项：许可证、打包目标（msi / rpm）、历史 tag 补打。

**未验证项**

- 资源管理器窗口里"是否真的选中了那个文件"**没有实机确认**：跑测试时 `LogonUI.exe` 在跑（桌面锁着），
  开了窗口也截不到、看不见。命令行构造对了是测试证明的，窗口行为要靠实机点一次。
- 只验证了 Windows 分支；mac `open -R` 与 linux `xdg-open` 这条路没动，也没在对应机器上跑过。
- 桌面锁着，真窗口仍未点检；mac / linux 包仍只到"CI 构建通过"。
- 无 SSH 服务器与凭据 → 真实登录、PTY、tmux、SFTP 传输一律未验证（长期阻塞）。


## 2026-11-19 · v1.0.7-RC1 · 日志刚轮转的那一下，「看日志」给我的是一屏空

`portio.log` 满 1 MiB 就轮转成 `portio.log.1`。轮转之后、下一条日志写进来之前，当前文件是空的
（严格说它那时都不存在，是下一条日志进来时才重建的）。在这个空窗里按设置里的「看日志」，
或者按「复制诊断信息」——拿到的是空串。而日志被搬走的这一刻，恰恰是我最想看它的时候。

上一轮修的是"「定位日志文件」按了没反应（路径含空格）"，两处其实是同一类毛病：
**我按的是出事时要用的按钮，它却在出事时给不了东西。** 日志这条线到最后，剩下这一块。

**改法**

`read_tail_file` 先读当前文件；读不出内容（不存在 / 0 字节 / 只有空行）就回落到
`backup_path(file)`（`portio.log.1`）。当前文件一旦有了新的一条，就只读它，旧内容不混进来——
否则日志会变成"上一代 + 这一代"拼在一起，时间顺序就假了。两份都没有仍是空（保持原来
"不弹错"的语义，看日志不是个会弹错的功能）。读文件那半步抽成 `tail_of_file`，
回落这一支才有可测的形状。

**验证证据**

- **反向验证**：把回落短掉（`if !current.is_empty()` 改成恒真返回）→ 新单测
  `an_emptied_or_missing_log_falls_back_to_the_backup` FAIL，点名
  「当前文件不存在时该读 .1：""」；还原后 ok。
- **单测**走四个状态：① 当前文件已被改走、只剩 `.1` → 读到旧的两行；② 当前文件存在但 0 字节 →
  仍读到旧的两行；③ 当前文件写进新的一条 → 只读新的（断言不含"旧的"）；④ 两份都删 → 空串。
- **整跑**：`python scripts/rc.py` → **20 通过 / 0 失败 / 0 跳过**，137.6s
  （`cargo test --workspace` **97 passed**，比上轮多出的正是这一条）；`fmt --check` 与
  `clippy -D warnings` 均 exit 0。
- **进位**：RC10 已是 RC 位上限，按"满 10 进 patch 回 RC1"→ **v1.0.7-RC1**，四处清单一致。
- **CI**：main run `44530131804` 五项全 success。
- **发版**：推 `v1.0.7-RC1` → run `44530154521` gate + 三平台 build 全 success；Release
  **`Portio 1.0.7-RC1`**（`prerelease: true`、`draft: false`）四资产：
  exe 3357107 B / dmg 9473551 B / deb 4942768 B / AppImage 83134968 B。本地对照包 4557214 B。

**下一步**

1. 日志这条线到这里算收口了：并发丢行、坏字节读空、定位按钮哑、轮转空窗，四块都补了，各带单测与反向验证。
   下一轮该换线了——候选：会话/凭据侧还剩的口子（`sessions.rs` 里 `connect_error_text` 写成全路径这种整洁度问题不算单元），
   或者把「看日志」预览行数、以及清单里还只到"自动化"没到"实机手感"的项往前推一格。
2. 实机点检仍欠着（桌面锁着）：装上这一版 → 设置 → 运行日志 → 按「看日志」看有没有按预期回落、
   按「定位」看资源管理器是不是真选中了文件。

**未验证项**

- 真实轮转（写满 1 MiB 触发 rotate）没有在真机窗口里点过一次，只证明了读那侧的逻辑。
- 「定位日志文件」仍然定位 `portio.log` 本身，不会跳到 `.1`（已知限制，已写进 CHANGELOG）。
- 只回落到一代 `.1`：连续两次轮转之间的空窗拿到的是早一代，不会更往前追。
- 桌面锁着，真窗口仍未点检；mac / linux 包仍只到"CI 构建通过"。
- 无 SSH 服务器与凭据 → 真实登录、PTY、tmux、SFTP 传输一律未验证（长期阻塞）。


## 2026-11-19 · v1.0.7-RC2 · 自定义开做：主色可换（六套预置）

你说了句「现在软件的自定义程度太低了」。这句我认——以前能调的只有三样：主题（深/浅/跟随系统）、
密度（标准/紧凑）、终端字号（11–18），主色、终端配色、字体、面板布局全钉死。

按定下的四个方向（D-10 记录在 `docs/decisions.md`）逐轮做，本轮先铺地基：**把主色从写死变成可换**。

**做了什么**

- `ui/tokens.css` 末段开一组强调色预置：`html[data-accent="<名字>"]`，六套——teal 青（默认）/ azure 蓝 /
  violet 紫 / amber 琥珀 / rose 玫瑰 / lime 青柠，深浅各一档（浅色下同一批色相压暗一档，白底上才看得清）。
  每套只换**跟主色一起走的四个令牌**：`--accent`、`--on-accent`、`--mark-accent`、`--term-cursor`。
- **ANSI 八色刻意不动**：红绿黄蓝是终端语义（`git diff`、`ls` 上色），跟着主色走会让人分不清
  "这是成功还是我选了蓝色"。这条写进规范 §2 规则，新元素进 §10 #41。
- 设置面板「主题」下面加了一排色片：`--ctl` 见方、`--r-6`、底色取 `--acc-*`，当前那颗用
  "底色隔一道 + 主色环"（`0 0 0 --r-hair --surface, 0 0 0 --sp-1 --accent`）——
  第一版直接画主色环，蓝色环套在蓝色块上等于没画，截图一看就知道错了。
- 落盘 `portio.accent`，认不出的值回默认青；换色后把终端主题重挂一遍，光标才跟着变。
- 新增演示钩子 `#accent-demo` / `#accent-demo-light`（与 `#theme-light` 同类，只给截图用）。

**验证证据**

- **新增自检 A21 `#accent-test`**（`ui/app.js` 末尾 + `scripts/rc.py` 分派链 A20 之后 + `rc-checklist` §1 一行）。
  验的不是"我点了按钮"，而是"主色真的走到该去的地方、且没走到不该去的地方"：① 没选过时落默认青；
  ② 换蓝后 `--accent` 与那张色片取到同一个值（不靠两处写死对上）；③ `--on-accent` 不许与 `--accent` 同色；
  ④ 主按钮底色等于 `--accent`（关掉 160ms 过渡再量，否则读到过渡中的颜色——第一版就是这么挂的）；
  ⑤ 切浅色后选的还是蓝、主色换成浅色那一档；⑥ 认不出的值回默认；⑦ 只有一颗色片是选中态；
  ⑧ **ANSI 绿不跟着主色变**、而终端光标跟着。
- **反向验证**：把 `root.dataset.accent = want` 改成恒等 `"teal"`（只记 localStorage、界面没换）→ A21 FAIL
  并点出 8 条，原文含「换色后 data-accent 是 azure：\"teal\" ≠ \"azure\"」「--accent 就是蓝那张色片的值：
  \"#2fb39a\" ≠ \"#4f9fdd\"」「ANSI 绿不跟着主色变：true ≠ false」；还原后 OK。
- **整跑**：`python scripts/rc.py` → **21 通过 / 0 失败 / 0 跳过**（67.4s，A21 1.5s）；
  `check_design_tokens.py`、`check_ui_scale.py`、`node --check ui/app.js`、`cargo fmt --all --check` 全 OK。
- **截图核验**（无头 1180×690@2x，深浅各一张）：色片、选中环、主按钮、字号滑杆拇指都跟着主色；
  深色下蓝色选中环有底色隔开，看得清。
- **CI**：main run `44535030414` 五项全 success。
- **发版**：`v1.0.7-RC2` → run `44535047553` gate + 三平台 build 全 success；Release `Portio 1.0.7-RC2`
  （`prerelease: true`）四资产：exe 3359627 B / dmg 9477429 B / deb 4946390 B / AppImage 83143160 B；
  本地对照包 4556762 B。

**下一步**

1. 自定义②**终端配色方案**：把终端配色从界面主题解耦，先给 Portio（现状）/ Dracula / Solarized Dark / Nord
  四套，进 `html[data-term="<名字>"]`，落盘 `portio.termTheme`，配 `#term-theme-test`。
2. 自定义③字号/字体/密度、自定义④布局与面板，顺序与要点都写进 `docs/backlog.md` 的「自定义」段。

**未验证项**

- 真窗口里没点过这套色片（桌面锁着，`LogonUI` 在跑），只做了无头截图。
- 六套色在真实终端滚动内容上的观感（大量 ANSI 上色时为不为难眼睛）只看了静态截图。
- mac / linux 包仍只到"CI 构建通过"；无 SSH 服务器与凭据 → 真实登录、PTY、SFTP 一律未验证（长期阻塞）。


## 2026-11-19 · v1.0.7-RC3 · 自定义第二单元：终端配色跟界面主题解耦

上一版把主色打通了，但终端那套色还跟界面主题绑在一起——界面切浅色，终端也得跟着变白。
这轮把终端配色单独拎出来：**换终端主题，界面纹丝不动；换界面深浅，终端纹丝不动。**

**做了什么**

- `ui/tokens.css` 末段开 `html[data-term="<名字>"]` 三套预设：Dracula / Solarized / Nord。
  每套**成套换九个令牌**：`--term-bg`、`--term-fg`、`--term-selection` 加 ANSI 八色。
  只换底不换字那种事没干——浅底配浅字等于让人瞎。
- 不设 `data-term` 就是「跟界面」：沿用界面深浅那两套 `--term-*` / `--ansi-*`，等于原来那套观感。
- 设置面板加「终端配色」一行四档（跟界面 / Dracula / Solarized / Nord），复用 `.seg` 形态；
  落盘 `portio.termTheme`，认不出的值回「跟界面」。
- 规则写进规范 §10 #42：**预设档里不许放 `--term-cursor`**。光标永远跟主色走（它归强调色管），
  否则用户会以为"我换了个终端配色，光标颜色怎么也变了"。
- 「跟界面」这一档是 `delete root.dataset.term`，不是写成 `data-term="auto"`——写 auto 属性一直在，
  浅色档就永远回不去（这个坑我自己踩了一版才看见，反向验证②就是它）。
- 新增演示钩子 `#term-demo` / `#term-demo-light` 与 `#term-palette` / `#term-palette-solarized` /
  `#term-palette-auto`（把 ANSI 八色真写进终端给截图比对，不参与任何逻辑）。

**验证证据**

- **新增自检 A22 `#term-theme-test`**（`ui/app.js` + `scripts/rc.py` 分派链 A21 之后 + `rc-checklist` §1 一行）。
  九条判据：① 默认「跟界面」且 `html` 上没有 `data-term`；② 选 Nord 后底/字/ANSI 绿成套换、底色与界面底色不同源；
  ③ 界面切浅色后终端那套一动不动（同时确认界面底色确实变浅了）；④ **真终端对象的 `options.theme` 当场就是 Nord**；
  ⑤ Dracula 与 Nord 两套真的不同；⑥ 回「跟界面」后属性消失、深色下终端底色回到原值；⑦ 认不出的值读成「跟界面」；
  ⑧ 换主色不动 Nord 的 ANSI 绿、光标仍跟主色；⑨ seg 里只有 Nord 一颗选中。
  期望值一律拿"改前 / 改后"互相比，不写死色值——写死就等于把配色又钉回代码里，而这里的规矩是配色只许住 `tokens.css`。
- **反向验证两条，都翻红并点名**：
  ① 去掉 `eachTerm((t) => { t.options.theme = terminalTheme(); })`（CSS 换了、真终端没换）→
  FAIL「真终端的背景就是 Nord 的底：\"#090c10\" ≠ \"#2e3440\"」「真终端的绿就是 Nord 的绿：\"#2fb39a\" ≠ \"#a3be8c\"」；
  ② 把 `delete root.dataset.term` 改成 `dataset.term = "auto"` →
  FAIL「没选过时 html 上没有 data-term：\"auto\" ≠ undefined」。还原后 OK。
  中间踩到一个真问题：第④条一开始查在「切浅色主题」之后，而 `applyTheme` 里也会顺手重挂一遍终端主题，
  结果把"applyTerm 自己忘了挂"这个 bug 盖住了（改坏①第一次跑居然 PASS）——已把这条判据挪到切主题之前。
- **整跑**：`python scripts/rc.py` → **22 通过 / 0 失败 / 0 跳过**（50.4s，A22 1.2s）；
  `node --check ui/app.js`、`check_design_tokens.py`、`check_ui_scale.py`、`cargo fmt --all --check` 全 OK。
  第一版自检里写了 9 处字面色值，被 `check_design_tokens.py` 当场拦下（配色的规矩是"只许住 tokens.css"），已全改成令牌互比。
- **截图核验**（无头 1180×690@2x，把 ANSI 八色真写进终端）：
  `_term_nord.png`（Nord 的板岩底 + 低饱和八色）、`_term_solarized.png`（Solarized 的深青底）、
  `_term_auto.png`（跟界面那套近黑底），三套肉眼可分；`_term_dark.png` / `_term_light.png` 是设置面板里的这一行。
- **CI**：main run `44540966932` success。
- **发版**：`v1.0.7-RC3` → run `44540983130` gate + 三平台 build 四项全 success；
  Release `Portio 1.0.7-RC3`（`prerelease: true`）四资产：exe 3363277 B / dmg 9483460 B /
  deb 4947522 B / AppImage 83143160 B；本地对照包 4568370 B。

**下一步**

1. 自定义③**字号 / 字体 / 密度**：界面字号与终端字号分开调（终端 9–24、界面 11–16 两档）；
   等宽字体可选（JetBrains Mono / Cascadia Mono / Consolas / 系统 mono，重建终端才彻底生效）；
   密度补第三档「宽松」（`html[data-density="comfortable"]{--row:32px}`，同时要改 `#density-test` 那条"两档只差 4px"的判据）。
2. 之后是自定义④布局与面板。

**未验证项**

- 真窗口里没点过这两行设置（桌面锁着，`LogonUI` 在跑），只做了无头截图。
- 无 SSH 服务器与凭据 → 真实会话里大量 ANSI 内容（`ls --color`、`git diff`、`htop`）下的观感未验证。
- 三套外来配色只做了深色版；Solarized Light 这类浅色变体没做（记在 backlog）。
- Release 里 AppImage 与 RC2 的字节数完全一样（83143160 B），像是构建缓存复用了上一轮产物；
  没影响这一版（Linux 包本来就没装过真机），但下次动 Linux 打包时要核一下是不是真重建了。

## 2026-11-19 · v1.0.7-RC4 · 自定义③ 字号 / 字体 / 密度

**做了什么**

前两轮都在改颜色，这一轮改"看得清不清"。原来的状态很别扭：终端字号一条滑杆管到 18 就封顶，
界面字号全写死在 `tokens.css` 的 `--fs-11…--fs-20` 里；等宽字体串一笔写死；密度只有两档。

- 界面字号两档（标准 / 大一号）：`html[data-ui-font="large"]` **整块重定义** `--fs-11` 到 `--fs-20`。
  只放大正文会让标题跟正文脱档，所以是整套刻度一起抬；默认档不写属性（认不出也回默认）。
- 终端字号放开到 9–24（原 11–18），只改 xterm 的 `options.fontSize`，不碰 `--fs-*`。
- 等宽字体四选（自动 / JetBrains / Cascadia / Consolas）：`html[data-mono=X]` 只改 `--mono` 一处，
  界面小号等宽与终端同时换；每个族名串末尾都留 `monospace` 兜底——回落到比例字体等于让终端每一列错位。
- 密度第三档「宽松」：24 / 28 / 32，相邻正好差 4px；标题栏那颗钮改成三档循环。
- xterm 不认 CSS 变量，所以换字体/字号必须**当场改真终端对象**再重量格子，否则"字变了但列宽还是旧字体算的"。
- 两条互不带动写死：调界面字号不动终端字号，调终端字号不动 `--fs-*`。

**验证证据**

- 新增自检 **A23 `#font-test`**（八组判据）：出厂态无 `data-ui-font` / `data-mono`、终端 13px 且族名含
  JetBrains Mono；「大一号」把 `--fs-13` 13px→14px、真元素字号跟着变大而**终端字号一动不动**；
  终端 18 时界面 `--fs-13` 一动不动；字号 30 / 8 越界回 13、下界 9 认；换 Consolas 后 `data-mono` 落上、
  真终端族名以 `Consolas` 打头且末尾有 `monospace`；Cascadia 与 Consolas 族名不同、认不出的名字不留痕回自动；
  密度三档 24/28/32 且 seg 跟着走；界面与终端共用同一个 `--mono`。
- 既有 **A16 `#density-test` 从两档扩到三档**：三档都逐条核 `--row` 与九处行高、相邻正好差 4px、切档不横向错位。
- `python scripts/rc.py` → **23 通过 / 0 失败 / 0 跳过，81.7s**（A23 1.8s）。
- `check_design_tokens.py` / `check_ui_scale.py` / `node --check ui/app.js` / `cargo fmt --all --check` 全 OK。
- 反向验证两条都翻红：① 去掉 `applyMono` 里的 `eachTerm(...)` → FAIL「真终端的族名没以 Consolas 打头」
  「Cascadia 与 Consolas 的族名不同：…撞了」；② 删掉宽松档 `--row:32px` → FAIL「宽松档 --row 应为 32px：28 ≠ 32」
  「标准 → 宽松 差 0px，应正好 4px」（② 那一跑 JS 没还原、与 ① 叠着跑，输出里同时带 ① 的失败项）。还原后 OK。
- 无头截图 `_font_tall.png`（1180×1120@2x）：界面字号「大一号」、密度「宽松」、终端字号 18、等宽字体 Consolas
  四处选中态都对，文字确实变大、行确实变松；`_font_dark.png` / `_font_light.png` 同轮深浅对照。
- 发版：`95dc066`，tag `v1.0.7-RC4`，Release run `44552237437` con**success**（gate + 三平台），
  主干 CI `44552220992` success；Release `Portio 1.0.7-RC4`（prerelease）四资产
  exe 3367657 / dmg 9493220 / deb 4955346 / AppImage 83134968 B。
- 本地 NSIS 包：`Portio_1.0.7-RC4_x64-setup.exe`（4572646 B）——见下面这条坑。

**这一轮撞上的真坑：C 盘被自己撑爆了**

打包第一次报 `failed to build app`，然后 PowerShell 工具与 computer_use 工具**双双**报
`write non-interactive command script failed: no space on device (system_error=28)`——
它们都要把命令写成临时脚本，盘满就连工具都起不来。实测 C 盘 464.6 GB / 剩 **0 MB**，D 盘 1862.9 GB / 剩 513 GB。

量出来才知道是我自己的：`target\debug\incremental` **61.99 GB**、`target\debug` 合计 84 GB。
删掉 `incremental`（可重建、被 gitignore 的增量缓存）后工具恢复，但八轮下来 `deps` 12.9 GB + `build` 6.8 GB
仍在，C 盘也就腾出几 GB，`tauri build` 依旧打不出包。
最后解法：`$env:CARGO_TARGET_DIR="D:\portio-target"` + `$env:TEMP/$env:TMP` 一并指到 D 盘，
打包成功（2m33s 全新编译，NSIS 产出 4.36 MiB）。**中途试过一次只改 `CARGO_TARGET_DIR`、
TEMP 还在 C 盘，进程以 `exit code -1073741571`（0xC00000FD 栈溢出）退出**——盘满时连 rustc/node
的内部临时文件都写不出来，报出来的却是栈溢出，这个错法很坑人。
`TEMP` 里占头部的（`sewrkmda` 1.06 GB、`XLLogReport` 528 MB、`trae-cn-user-x64` 447 MB、
`vscode-stable-system-x64` 273 MB、四个 `flutter_tools.*` 各 120–190 MB）**都是别人的、没动**。

**下一步**

1. 自定义④**布局与面板**：会话栏 / 文件面板的启动默认显隐与默认宽度、文件面板显示哪些列
   （权限列能否关）、启动默认单屏还是 2×2 分屏。
2. **C 盘空间需要用户拍板**：`target\deps` 12.9 GB / `build` 6.8 GB 还在，目前每轮靠
   `CARGO_TARGET_DIR` + `TEMP` 指到 D 盘绕过；要不要把整个 `target` 迁到 D 盘（或允许定期清 `target`），
   以及 `D:\portio-target` / `D:\portio-tmp` 是否保留。

**未验证项**

- 真窗口里没点过这四处设置（桌面锁着，`LogonUI` 在跑），只做了无头截图。
- JetBrains Mono / Cascadia Mono 是否真装在这台机器上没核；没装就按族名串顺序回落，观感可能与名字不符。
- 无 SSH 服务器 → 9 号 / 24 号在真实满屏输出（`htop`、`ls --color`）下的可读性未验证。
- macOS dmg / Linux deb、AppImage 仍只到"CI 构建通过"，未真机装过；Windows 包只做进程启动存活检查的历史口径不变。

## 2026-11-20 · v1.0.7-RC5 · 自定义④ 第一单元：启动时的面板显隐

**做了什么**

自定义做到最后一个方向（布局与面板），先挑最小的一件：**开局那一刻，两块面板是什么样子**。
原来的行为只有一种——记住上次：会话栏、文件面板的折叠状态各自落盘，重开还是那个样子。
问题在于有人要的从来不是"上次"，而是"每次都要同一个开局"：干活时想要一进来就是干净的全屏终端，
也有人恰恰相反，一开机就要看见左边会话、右边文件。

隐患在实现上：折叠态原来只有一句 `applyFold()`，既改界面又写盘。若照原样让「启动时」偏好也走它，
选了「总是展开」的同时就把 `portio.sidebarFolded` 改成了 0——等哪天想换回「记住上次」，
"我上次其实收起来了"这件事已经没了。所以先拆逻辑，再加设置。

- `setFoldUI` / `setFilesFoldUI`：只改界面（class、`--sidebar`、把手箭头、折叠钮 aria），
  **不碰记忆键**；`applyFold` / `applyFilesFold` = 前者 + 落盘，给用户手点用。
- 新增 `portio.bootSide` / `portio.bootFiles`，三档 `remember` / `open` / `folded`；
  `bootFold(mode, remembered)` 一句话把三档落成布尔值。
- 启动改成 `applyBootSide()` / `applyBootFiles()`：按偏好算一次就当次生效，
  记忆键原封不动；「总是展开」回到记忆里的宽度（不许写成 0）。
- 设置面板加两行 `.field`（会话栏 · 启动时 / 文件面板 · 启动时），`.hint` 只写一句：
  "只管下次打开，眼前这一下不动手；宽度和分栏比例照旧记你上次拖出来的"。
- 规范 §10 加 **#44**，把"偏好不是命令"写成条款：改「启动时」不许动眼前布局，启动时强行收放不许改写记忆键。
  标题升到 **v2.8**。

**验证证据**

- 新增自检 **A24 `#boot-test`**：出厂态两个 seg 都是「记住上次」且盘里没有 boot 键；
  三档语义四种组合逐个核；**改「启动时」眼前的会话栏与文件面板都还开着**（这条专治"把设置当命令"），
  且两个记忆键一个字节没变；模拟启动后「总是收起」让 `--sidebar` 归 0、文件面板进 `files-folded`
  且折叠钮 `aria-pressed=true`，「总是展开」两处都回来、宽度回到 264px；认不出的档位读成「记住上次」且不回写垃圾；
  seg 选中项跟着落盘值走。`BOOT-SELFTEST-OK {"width":{"remembered":"0px","after":"264px"}}`。
- `python scripts/rc.py` → **24 通过 / 0 失败 / 0 跳过，213.2s**（A24 2.2s；A1 在
  `CARGO_TARGET_DIR=D:\portio-target` 上全新编译 157.3s，97 passed）。
- 反向验证两条都翻红：① 在 `applyBootMode` 里顺手 `applyBootSide()` / `applyBootFiles()` →
  FAIL「选了「总是收起」后眼前的会话栏还开着：true ≠ false」「…文件面板还开着：true ≠ false」；
  ② 在 `setFoldUI` 里顺手写 `portio.sidebarFolded` → FAIL「启动覆盖不改会话栏记忆态：\"1\" ≠ \"0\"」。
  还原后 `BOOT-SELFTEST-OK`。
- 无头截图 `_boot_tall.png`（1180×1120@2x，#boot-demo：会话栏已让位、右侧文件面板还在，
  设置里「会话栏·启动时＝总是收起」「文件面板·启动时＝总是展开」两处选中），
  `_boot_tall_light.png` 浅色同形态；`_boot_dark.png` / `_boot_light.png` 是 1180×690 下的同一画面。
- check_design_tokens / check_ui_scale / node --check 均 OK。

**一个工具层面的坑（记下来免得下次再撞）**

Chrome 无头探针漏写 `--dump-dom` 时，**stdout 与 stderr 都是空的、退出码还是 0**——不是页面崩了，
是我这轮自己写的探针脚本少了一个参数。第一次跑到"title 空、outlen 0、errlen 0"，
差一点误判成 C 盘满导致 Chrome 起不来（当时 C 确实只剩 0 MB）。
判法：`--screenshot` 与 `--dump-dom` 二选一必须显式写，两者都没有就等于让 Chrome 白跑一趟。

**下一步**

1. 自定义④ 剩下两件：**文件面板显示哪些列**（权限列能否关）、**启动时默认单屏还是 2×2 分屏**；
   以及「默认宽度」要不要单独给一层（现在只有上次拖出来的值）。
2. C 盘空间仍要用户拍板：本轮 C 盘一度只剩 0 MB，靠 `CARGO_TARGET_DIR` + `TEMP` 指到 D 盘把所有验证跑完。

**未验证项**

- 真窗口里没真重启过（桌面锁着）："重开 Portio 后按偏好收放"只有自检里那条模拟启动兜着。
- 无 SSH 服务器：`总是收起` 在真实会话里省出来的那点宽度，实际多出几列、观感如何未验证。
- 「总是收起」在启动后手动展开，本次会话保持展开——这条行为是刻意设计，但没在真窗口里走过一遍。

**发版补记（同轮晚些时候写完）**

- Release run `44563959577`：gate + windows-x64 + linux-x64 全 success，**macOS 那一格第一次是 `cancelled`**
  （排队 15 分钟后被取消、一个 step 都没跑、日志为空），三平台因此先只上传了 exe / deb / AppImage。
  用 `gh run rerun 44563959577 --failed` 重跑，macOS 跑完转 success，dmg 补上，整轮才齐。
- Release `Portio 1.0.7-RC5`（`prerelease: true`、非草稿）四资产：
  exe **3367447** B / dmg **9498340** B / deb **4955524** B / AppImage **83147256** B。
- main CI `44563942066` success。
- 对外文案同步：README 版本段、`docs/release-notes.md` 当前状态、`docs/press-kit.md` 下载表（实际字节数）、
  `docs/site/index.html` 五处版本串、`docs/rc-checklist.md` §7 行的四资产字节数。
- 排期 `排期-v0.1.md` 的「续 20」段改 RC5，记录表追加一行。
## 2026-11-20 · v1.0.7-RC6 · 自定义④ 第二单元：文件面板的权限列开关

**做了什么**

上一轮定的是"开局时面板开着还是收着"，这一轮定"面板里面摆哪几列"。
远端文件行比本地多一列 `drwxr-xr-x`。它有用——一眼看得出可执行、可写——也是真占地方：
68px 在窄窗里常常是从文件名那儿抢来的，一个 `portio_1.0.7-RC6_x64-setup.exe` 就被截成半截。
所以给一个开关，默认照旧显示。

要点不在"藏起来"，而在**藏得干不干净**：
只把单元格 `display:none` 是最常见的假隐藏——权限确实看不见了，可 68px 的轨道还杵在那儿，
文件名一点没变宽，等于白藏。所以隐藏走的是**收走整条轨道**：`html[data-perm="hide"]` 下
`.fp-row.has-perm` 的 `grid-template-columns` 从 5 列减到 4 列，同时 `.pm` 置 `display:none`。

- `portio.permCols`（`show` / `hide`），认不出的值一律回 `show`——宁可多显示一列，也不许无声地藏掉信息；
  默认档不留根属性，给以后改默认留余地。
- `applyPerm()` 立刻生效（跟上一轮「启动时」相反：那条是"下次打开"才动，别混成一层），点了顺手 toast 一句。
- 设置面板在「文件面板 · 启动时」之后加一行「文件面板 · 权限列」，两档「显示 / 隐藏」，`.hint` 交代
  "那 68px 还给文件名，行高不动；本地行本来就没有这一列"。
- 规范 §10 加 **#45**，标题升 **v2.9**，把"看不见"与"不占地方"的区别写成条款，并钉住
  "行高 / 行宽 / 右对齐两列的右缘都不许动"。

**验证证据**

- 新增自检 **A25 `#perm-test`**：出厂态无 `data-perm`、seg 选「显示」、盘里无键、远端行 5 列；
  关掉后权限单元格 `display:none`、**远端行只剩 4 列**、名字列多出的宽度正好 72px（68 + 4 的 gap），
  而**大小列与时间列的右缘一动不动**（0.5px 内）、行宽与行高（= `--row` = 28）不变；本地行始终 4 列；
  认不出的值读成「显示」且不回写；再开回来列数回 5、名字列宽度回原值。
  `PERM-SELFTEST-OK {"perm":{"pmW":68,"nmGain":72,"rowH":28}}`。
- `python scripts/rc.py` → **25 通过 / 0 失败 / 0 跳过，178.1s**（A25 2.3s，A1 cargo test 97 passed）。
- 反向验证两条都翻红：① 删掉"隐藏时收走 68px 轨道"那条 CSS（只藏单元格）→
  FAIL「关掉后远端行只剩 4 列：5 ≠ 4」「关掉后名字列多出来的宽度：0 ≠ 72（差 -72）」
  「关掉后大小列的右缘不许挪：994 ≠ 1062（差 -68）」；② `readPerm` 去掉白名单校验 →
  FAIL「认不出的值读成显示：\"collapse\" ≠ \"show\"」。还原后 `PERM-SELFTEST-OK`。
- 截图 `_perm_dark.png` / `_perm_light.png`（1180×690@2x，设置关掉，直接看远端两行没有权限列、文件名整条铺开）、
  `_perm_set.png`（1180×1330@2x，设置面板里「文件面板 · 权限列」隐藏已选中）、
  `_perm_narrow.png` / `_perm_narrow_light.png`（1024×620@2x 窄窗不溢出）。
- check_design_tokens / check_ui_scale / node --check 均 OK。

**下一步**

1. 自定义④ 最后两件：**启动时默认单屏还是 2×2 分屏**；「默认宽度」要不要单独给一层。
2. C 盘空间仍要用户拍板（这轮同样靠 `CARGO_TARGET_DIR` + `TEMP` 指到 D 盘才跑完验证与打包）。

**未验证项**

- 真窗口里没点过（桌面锁着）：这一档在真窗口里点「隐藏」的手感、以及和深/浅两套主题下的对比度差异，只有无头页面兜着。
- 无 SSH 服务器：真实远端目录里权限串长短不一（`-rw-r--r--`、`lrwxrwxrwx`、`drwx------`）时的视觉对齐只在无头页面用一条假行量过。
- 1024 窄窗藏列只核了"不横向溢出"，没在真实文件多的目录里看省略号停在哪。

**发版补记（同轮晚些时候写完）**

- Release run `44576133068` **首跑四项全 success**（gate / windows-x64 / macos-universal / linux-x64），
  这回 macOS 没再被取消。
- Release `Portio 1.0.7-RC6`（`prerelease: true`、非草稿）四资产：
  exe **3372544** B / dmg **9502433** B / deb **4957370** B / AppImage **83147256** B。
- 本地 Windows 包同样打了一份：`D:\portio-target` 增量 + `TEMP/TMP=D:\portio-tmp`，
  `Portio_1.0.7-RC6_x64-setup.exe` **4582076** B，已复制到 `new-chat\` 根目录交付。
- 对外文案同步：README 版本段、`docs/release-notes.md` 当前状态、`docs/press-kit.md` 下载表（实际字节数）、
  `docs/site/index.html` 五处版本串、`docs/rc-checklist.md` §7 行的四资产字节数。
- 排期 `排期-v0.1.md` 的「续 20」段改 RC6，记录表追加一行。
## 2026-11-20 · v1.0.7-RC7 · 自定义④ 第三单元：终端开局格数

**做了什么**

前两版定的是面板开着还是收着、里面摆哪几列，这一版定**开局摆几格终端**。
有人一开机就要四个格（左边跑日志、右边盯 `top`），也有人永远只要一格。
设置里多一行「终端 · 开局格数」：`单屏` / `2×2 四格`，默认单屏。

要点不在"能摊开"，而在**只摊那一下**：

- 一次性标记 `bootPanesPending` 在 `createLocalTab` 里消费一次就置假——
  只认"打开应用时的第一个标签"；第二个标签、以及连主机开的标签，全都仍是一格。
  开局偏好是给开机那一刻备的，不是给每一次分屏下命令。
- 改设置**不许动眼前**：`applyBootPanes()` 只落盘 + `syncSegs()`，跟 #44 那两行同一套口径
  （设置描述的是下一次开局，不是立刻执行的动作）。
- `2×2` 直接**复用两次普通分屏**（`fillQuad` = `splitTab(v)` + `splitTab(h)`），
  不另造网格代码——焦点、`Ctrl+F` 只认当前格、关一格补洞这些既有规则一条都不必重写。
- 认不出的值回 `single`，且不回写垃圾；这一档不产生根属性、不改 CSS，纯布局动作。

**验证证据**

- 新增自检 **A26 `#panes-test`**：出厂态单屏、盘里无键；选 2×2 立刻落盘且 seg 跟上，
  **而眼前那个标签格数一点没变**；模拟一次开机 → 第一个标签真摊成 4 格、网格 2×2、带焦点描边类，
  第二个标签仍是 1 格、一次性标记已消费；单屏档同样只影响下一个开局标签；认不出的值读成单屏且不回写。
  `PANES-SELFTEST-OK {"cells":[1,4,1,1]}`。
- `python scripts/rc.py` → **26 通过 / 0 失败 / 0 跳过，202.2s**（A26 3.8s，A1 cargo test 144.6s / 97 passed）。
- 反向验证三条都翻红：① `createLocalTab` 里不再调 `fillQuad` → FAIL「2×2 开局应 4 格：1」
  「2×2 开局应是 2×2 网格：1×1」「四格应有焦点描边类」；② `readPanes` 去掉白名单（`v || "single"`）→
  FAIL「认不出的档位应读成单屏：tri」；③ `applyBootPanes` 里顺手把当前标签摊开 →
  FAIL「改开局格数不许动眼前这一下：1 → 4」。还原后 `PANES-SELFTEST-OK`。
  （① 这一条还顺带证明了 A26 真的在跑 `fillQuad` 那条路径，不是空转。）
- 截图 `_panes_dark.png` / `_panes_light.png`（1180×690@2x，开局四格：2×2 四格各带光标、
  焦点描边落在右下格、右侧文件面板仍在）、`_panes_set.png`（1180×1330@2x，设置面板里
  「终端 · 开局格数」选中 2×2 四格——用 PNG 逐像素核过：填充区 `#222a35` 落在右按钮 x 858–1014，
  左按钮是透明底，采样脚本藏在 `_px7b.py`，不进仓库）、`_panes_narrow.png`（1024×620@2x，
  四格不横向溢出，每格 23×9 列）。
- check_design_tokens / check_ui_scale / node --check 均 OK。
- 顺手补了演示页的一个真问题：`#panes-demo*` 是在启动那串 `applyX` **之后**才改偏好，
  seg 的选中态原先还停在「单屏」（截图里当场看出来），加一句 `syncSegs()` 才对齐。

**下一步**

1. 自定义④ 最后一件：**「默认宽度」要不要单独给一层**（现在是"只有上次拖出来的值"）。
2. C 盘空间仍要用户拍板（这轮同样靠 `CARGO_TARGET_DIR` + `TEMP` 指 D 盘才跑完验证）。

**未验证项**

- 真窗口里没点过（桌面锁着）：四格开局的实际手感（每格多少列、焦点给谁、`Ctrl+F` 是否落在当前格）只在无头页面量过。
- 无 SSH 服务器：四格里连主机时"每格一条 PTY、口令从加密凭据取"这条路没端到端验证过。
- 「第二个标签仍一格」是按一次性标记断言的；真实使用里连主机开新标签那条路径（`createTab` 而非
  `createLocalTab`）也未经实机验证，只是读代码确认它不碰这个标记。

**发版补记（同轮晚些时候写完）**

- Release run `44587528236` **首跑四项全 success**（gate / windows-x64 / macos-universal / linux-x64）。
- Release `Portio 1.0.7-RC7`（`prerelease: true`、非草稿）四资产：
  exe **3371429** B / dmg **9507487** B / deb **4958050** B / AppImage **83147256** B。
- main CI `44587514954` success。
- 本地 Windows 包同样打了一份（`CARGO_TARGET_DIR=D:\portio-target` + `TEMP/TMP=D:\portio-tmp`）：
  `Portio_1.0.7-RC7_x64-setup.exe` **4581282** B，已复制到 `new-chat\` 根目录交付。
- 对外文案同步：README 版本段、`docs/release-notes.md` 当前状态、`docs/press-kit.md` 下载表（实际字节数）、
  `docs/site/index.html` 版本串、`docs/rc-checklist.md` §7 行的四资产字节数。

## 2026-11-20 · v1.0.7-RC8 · 自定义④第四单元（也是这部分最后一件）：面板宽度分两层

**这一轮为什么做这个**
上一轮把「开局格数」收完，backlog 里「布局与面板」就只剩一件：默认宽度要不要单独给一层。
答案是要，而且理由比我原来想的更硬——现在三处尺寸（会话栏宽度、终端:文件分栏、传输队列高度）只有一层：
拖过就落盘，开机照盘里的再落一次。于是只要开机用「用默认」，上一次辛苦拖出来的宽度就被默认值悄悄顶掉，
再也找不回来。这不是缺个设置，是**设置和记忆搅在一层里**。

**做了什么**
- 三处尺寸全部拆成两半：`setSidebarUI` / `setSplitUI` / `setDrawerUI` 只改界面，
  `applySidebar` / `applySplit` / `applyDrawer` 才写记忆层。手拖、双击把手、点抽屉标题条这些动作走后者；
  开机按偏好落尺寸走前者，一个字都不写盘。
- 新增 `applyBootLayout()`：`remember` 读 `portio.sidebar` / `portio.split` / `portio.drawer`，
  `default` 只读默认宽度档，分栏固定 50/50、抽屉固定一行高（一个「干净开局」该有的样子）。
  折叠态它不碰：会话栏收起时 `--sidebar` 归零由 `setFoldUI` 决定。
- 新增两行设置：「面板宽度 · 打开时」`记住上次` / `用默认`（键 `portio.bootLayout`），
  「默认会话栏宽度」`窄`200 / `标准`264 / `宽`328（键 `portio.defWidth`）。两档都只作用于开机那一刻，
  改设置不动眼前；认不出的值分别回 `remember` 与 `264`，且都不回写垃圾。
- 顺手修掉一个老毛病：`setFoldUI` 展开时原来调的是 `applySidebar`（会落盘），跟它自己注释里
  「只改界面，不落盘」对不上；现在换成 `setSidebarUI(layoutWidth())`，宽度来源也统一走一个 `layoutWidth()`。
- `syncSegs` 补两项、两条监听器、演示钩子 `#layout-demo` / `#layout-demo-light` / `#layout-demo-set`、
  自检 A27 `#layout-test`；`scripts/rc.py` 加 A27（A26 从 `else` 改成显式 `elif`）；规范 §10 加 #47 / #48，升 v2.11。

**验证证据**
- `python scripts/rc.py` → **27 通过 / 0 失败 / 0 跳过，192.2s**；A1 `cargo test --workspace` 130.4s / **97 passed**；
  新增 A27 1.7s，标题 `LAYOUT-SELFTEST-OK {"layout":["360px","66.00%","200px"]}`。
- 反向验证三条，全翻红且指名道姓：
  ① 开机落尺寸顺手走 `applySidebar` → 「用默认不许改写宽度记忆：200」「记住上次应回到 360px：200px」；
  ② `readLayoutMode` 去掉白名单 → 「认不出的布局档应读成记住上次：auto」；
  ③ 分栏不退 50% → 「用默认分栏应回 50.00%：66.00%」。还原后重跑 OK。
- `check_design_tokens.py` / `check_ui_scale.py` / `node --check ui/app.js` 全 OK；`check_versions.py` → v1.0.7-RC8。
- 截图（1180×690@2x，`#layout-demo` 系列）：深色 / 浅色各一张，设置里「用默认」「宽」都选中（1180×1330@2x 那张）；
  1024×620 窄窗一张。像素核对：深色图里会话栏右缘落在 x≈655/2360 → **327.5 CSS px ≈ 328**（默认档生效），
  终端与文件面板右缘各占一半（50/50 生效）。

**未验证**
- 真窗口里「关掉再打开、按默认宽度的三档各开一次」没实机重启过（桌面锁着，抓屏只得锁屏壁纸）；三档只在无头页里逐个数过内联变量。
- 「用默认」下拖拽、再换回「记住上次」这条人工手感没点过（逻辑层由 A27 覆盖）。
- 真实窗口里拖到 180 / 420 两个端点、折叠态下拖把手的边界手感，仍未实机点。

**下一步**
- 自定义④ 四单元收完（启动时显隐 / 权限列 / 开局格数 / 面板宽度两层），这一段可以合上。
- 下一轮取 S13–S14 发布工程里能自己做的：文档站补这一版、press-kit 数字同步，或清单 §2 里还剩的人工项里挑一项能在无头环境验证的。
- 仍卡外部条件：无 SSH 服务器（B1–B9 全挂在这里）、签名证书 / 更新端点 / 崩溃上报（C1–C3）、许可证（C6）。

**发版补记（同轮晚些时候写完）**

- Release run `44596899518` 四项全 success（gate / windows-x64 / macos-universal / linux-x64，macOS 这次没被取消）。
- Release `Portio 1.0.7-RC8`（`prerelease: true`、非草稿）四资产：
  exe **3375150** B / dmg **9510808** B / deb **4959920** B / AppImage **83143160** B。
- main CI `44596888277` success；提交 `b1722d4` 已 push main，tag `v1.0.7-RC8` 已推。
- 本地 Windows 包（`CARGO_TARGET_DIR=D:\portio-target` + `TEMP/TMP=D:\portio-tmp`）：
  `Portio_1.0.7-RC8_x64-setup.exe` **4580142** B，已复制到 `new-chat\` 根目录交付。
- 对外文案同步：README 版本段、`docs/release-notes.md` 当前状态、`docs/press-kit.md` 下载表（实际字节数）、
  `docs/site/index.html` 版本串、`docs/rc-checklist.md` §7 RC8 行。

## 2026-11-20 · v1.0.7-RC8（物料轮，未进位）· 说明页补上「自定义」，并给这一页装一道闸

**这一轮为什么做这个**

自定义四个方向（强调色 / 终端配色 / 字号字体密度 / 布局与面板）收完之后，仓库里唯一还能自己往前推的
S13–S14 交付就是文档站点。而它恰好落后两版：离线说明页 §08 还在写「界面密度 两档」「终端字号 11–18」，
产品里已经是三档 24/28/32 与 9–24；强调色、终端配色、等宽字体、两处「启动时」、面板宽度、权限列、
开局格数七项一个字都没写。新用户点开这一页照着调，找不到那些开关——这不是排版问题，是说明页和产品
不是同一版东西。所以这一轮做两件事：把它补齐，并且让它以后没法再悄悄落后。

**做了什么**

- `docs/site/index.html` §08 从「设置与外观」重写成「自定义」：十六项按**两批**排——
  「改完立刻生效」九项（主题 / 强调色 / 界面字号 / 界面密度 / 终端配色 / 终端字号 / 等宽字体 /
  权限列 / 滚动缓冲），「只管下一次打开」五项（两处「启动时」/ 面板宽度 / 默认宽度三档 / 开局格数），
  再加「面板与维护」两项（已知主机 / 运行日志）。四十个档位逐个写到，含像素数（200 / 264 / 328）
  与字号区间（9–24）。开头一句先把两批的区别说清：后者不会为了你改一个设置就把眼前的窗口重排一遍。
- 加一条提示卡把这一版最容易误解的地方钉住：「记住上次」与「用默认」是两层，不是二选一——拖出来的宽度
  永远记着，选「用默认」只是开机时不拿它当准；换回「记住上次」，上次拖到 360 就还是 360。
- 新增 `scripts/check_site.py`：把设置面板按 `<label>` 切成十六项、把每项的可点档位（`data-v` 文字、
  色片的 `title`、滑块的 min/max）抽出来，再逐项去 `docs/site/index.html` 那一节的两列表里核。
  双向都判：产品有而页面没写 → FAIL 并点名「没写这一项」；页面写了一项产品里没有的 → FAIL 并点名
  「写了一项界面里没有的」；页面说「设置里十六项」而实际项数不符 → FAIL。版本串只能是当前那个，
  且至少出现在署名 / 安装 / 版本段三处。
- `scripts/test_check_site.py` 12 条单测（含一条「真仓库现在必须对齐」，它既是测试也是本版验收判据）。
- `scripts/rc.py` 加 A28（纯 Python，0.1s，不开浏览器）；A26 起那条兜底 `else` 改成显式 `elif`。
- `docs/rc-checklist.md`：§1 加 A28 行、范围改 A1–A28；顺手把三处过期证据对齐——A1 的「82 passed」
  改 97、A5 的版本串改当前、A22 的「待反向验证」改已验；§7 里 RC8 与 RC7 两行顺序调正，末行补本轮记录。
- 导航项「设置与外观」改名「自定义」；§06 权限列那句补上「嫌窄可以关掉，那 68 像素还给文件名」。

**验证证据**

- `python scripts/check_site.py` → `OK 说明页 16 项设置 / 40 个档位与代码对上，版本 v1.0.7-RC8`。
- 首跑（真仓库还没改页面时）把漂移一条条点出来，共 14 处：12 项「没写这一项」，加「界面密度 漏了档位
  宽松」、「终端字号 的档没写对，代码里是 9–24」——这就是那道闸当场的价值。
- `python -m unittest scripts/test_check_site.py` → **12 通过**。
- `python scripts/rc.py --fast` → **27 通过 / 0 失败 / 1 跳过（A1 被 --fast 跳过），28 项 61.4s**；
  A28 0.1s。
- 反向验证三条，全翻红且指名：
  ① 密度写回两档 → `FAIL 「界面密度」漏了档位「宽松」`；
  ② 版本串留 RC7 → `FAIL 说明页版本串过期：1.0.7-RC7 ≠ 1.0.7-RC8`（并报当前版本 0 次）；
  ③ 项名写成「查看配色」→ `FAIL 没写这一项：「终端配色」` ＋ `FAIL 写了一项界面里没有的：「查看配色」`。
  还原后重跑 OK。
- 无头渲染：`--dump-dom` 标题 `Portio 使用说明`、`ERR:` 0 处、页面里「自定义」在；截图两张
  （`_site_look_full_dark.png` / `_site_look_full_light.png`，1180×1700，只留 §08 那一节），
  深浅两套三张表都齐、提示卡与收尾段没溢出。

**为什么这一轮不进位、不打 tag**

这一轮只动物料与回归工具，产品二进制一个字节没变。RC 阶段的规矩是「进位 = 出一批新包」，
而纯物料轮单独推 RC tag 是早就否决过的；真推了会更糟：页面写着 RC9，下载页上的包还是 RC8。
所以版本停在 v1.0.7-RC8，下一个真正改产品的单元再进 RC9。

**未验证**

- 说明页只在无头里看过（桌面锁着，抓屏只得锁屏壁纸）：真浏览器里滚这一节的手感、窄窗 1024 下三张表
  会不会挤成两行，都没实机看。
- 「立刻生效 / 下次打开才生效」这个分法是从代码读出来的（哪些走 `applyX`、哪些只落 preference 键），
  没有在真窗口里逐项点一遍确认心理预期一致。
- 页脚写的「每一个档位都有脚本对着代码核」只覆盖**设置项与档位文字**；档位背后的行为仍靠 A21–A27 那七条
  无头自检兜，两者不重复但也不互相替代。

**下一步**

- 自定义这一段已经彻底收口（四方向 + 说明页 + 闸）。下一轮挑一个真正改产品的单元进 RC9：
  候选是 `docs/rc-checklist.md` 里 M 类还剩的实机能验项里可自动化的、或 backlog 里等拍板的取舍
  （「用默认」要不要连分栏 / 抽屉也给几档、默认宽度是否放开任意像素）。
- 仍卡外部：无 SSH 服务器（B1–B9）、签名证书 / 更新端点 / 崩溃上报（C1–C3）、许可证（C6）、
  真窗口点检（桌面长期锁屏）。

**同轮补记（提交之后）**

- 提交 `36348d0` 已 push main；main CI run `44607672769` **六项全 success**
  （fmt / clippy / test / version rule / build(ubuntu) / build(windows) / build(macos)）。
- 版本停在 `v1.0.7-RC8`，`check_versions.py` → `OK v1.0.7-RC8`；没有新 tag、没有新 Release，
  下载页上的包仍是 RC8 那一批——页面与包仍是同一版。

