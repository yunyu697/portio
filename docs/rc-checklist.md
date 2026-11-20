# Portio RC 回归清单（v0.4 gate）

`v1.0.0-RC1` 之前从这里第一行过到最后一行，每条填上日期与证据。清单只认两样东西：**一条命令的输出**，
或者**我亲眼看过的一帧画面**。没跑过的一律写「未验」，不写「应该没问题」。

**状态口径**

| 记号 | 含义 |
|---|---|
| ✅ | 跑过、看过，结论就是过（同行写明证据与日期） |
| ◻ | 待验：本机能验，但这轮还没做 |
| ✗ | 已知缺口：代码里就没有，或明知不合格 |
| 🚫 | 卡外部条件：缺服务器 / 缺证书 / 缺平台机器，写清差什么 |

**最近一次整跑**：2026-11-21 · `v1.0.9-RC6` · `python scripts/rc.py`（全量，含 A1）→ **41 通过 / 0 失败 / 0 未验，344.3s，退出码 0**（这轮多了 A41：最后两条只在无头里跑的自检（`#net-fail-test` / `#connect-entry-test`）也进了真窗口——`2 条在真窗口 + 真后端里跑过（net-fail-test、connect-entry-test）；跑完 theme.txt / sessions.json / known_hosts 一个字节没动（这两条自检这回没写盘——收回这套是护栏，不是它们的证据）`；这轮顺带查清一件事：这两条本来就不写盘，所以判据重心放在「是不是真在我的真偏好里跑的」上；A1 97 passed、A32 fmt 干净 clippy 零警告、A34 包里那份逐字节一致）。
人工项与真服务器项仍未跑（见 §7）。

---

## 1. 本机自动化（一条命令一项，五分钟跑完）

**这一段现在有固定入口**：`python scripts/rc.py` 按顺序跑完 A1–A41，逐项打 `[PASS]` / `[FAIL]` / `[未验]`，
最后一行是汇总，可以直接贴进 §7。全跑五分钟上下（`cargo test` 与 `clippy` 各占一半），只改前端时用 `--fast` 跳过 A1；
只想核其中几项就直接写编号——`python scripts/rc.py A11`、`python scripts/rc.py A10 A11`、
`python scripts/rc.py A10,A11` 都认，只跑选中的那几项；编号写错会回一句「不认识的编号」并以退出码 2 结束，
不会静悄悄跑 0 项。

**「未验」不是「通过」**（2026-11-20 起）：以前只要没有 FAIL 就退出 0，于是这一版还没打包、
截图清单还没出、机器上没 Chrome、`--fast` 跳了 A1 这些**没跑**的项，都混在同一句「通过 / 跳过」里
看着像全绿。现在没核过的单列「未验」，退出码也分开：**0 = 每项都真跑过且过；1 = 有失败；
2 = 编号写错；3 = 没有失败但有未验项**。整跑若拿不到 0，回归记录里必须写清是哪几项没验、为什么。
表里保留每项的命令与判据，`rc.py` 出问题时按表手工复现。

| # | 项 | 怎么验 | 通过判据 | 最近结果 |
|---|---|---|---|---|
| A1 | Rust 单元与集成测试 | `cargo test --workspace` | 0 failed | ✅ 97 passed（RC8 整跑 130.4s） |
| A2 | 前端语法 | `node --check ui/app.js` | exit 0 | ✅ |
| A3 | 界面无硬编码色值 | `python scripts/check_design_tokens.py` | 打印 OK | ✅ |
| A4 | 界面尺度走令牌 | `python scripts/check_ui_scale.py` | 打印 OK | ✅ |
| A5 | 七处版本号一致且合规（清单三处 + 标题栏 `span.ver` + `Cargo.lock` 三个 crate） | `python scripts/check_versions.py` | `OK v<版本>（7 处一致…）`，任何一处漂移就退出码 1 并点名那一处 | ✅ `OK v1.0.8-RC4（7 处一致）`；反向验证：标题栏写回 RC3 → 点名「ui/index.html 标题栏」，把 `portio-ssh` 写回 RC3 → 点名「Cargo.lock portio-ssh」 |
| A6 | 启动无 JS 报错 | 无头打开 `ui/index.html`（不带 hash），读 `<title>` | 标题是 `Portio`，**出现 `ERR:` 即失败** | ✅ `Portio` |
| A7 | 分屏状态机 | 无头打开 `ui/index.html#split-test` | 标题 `SELFTEST-OK` | ✅ |
| A8 | 复制粘贴按键映射 | 无头打开 `ui/index.html#clip-test` | 标题 `CLIP-SELFTEST-OK 10` | ✅ 10/10 |
| A9 | 文件面板折叠 | 无头打开 `ui/index.html#fold-test` | 标题 `FOLD-SELFTEST-OK`，且折叠态 `files` 宽 = 0、把手 = 10、回展开 = 原宽 | ✅（open 360/340/9 → fold 480/0/10 → back 360/340） |
| A10 | 启动不带控制台黑窗 | 读 `portio-app.exe` 的 PE `OptionalHeader+68`；找 exe 时仓库 `target` 与 `CARGO_TARGET_DIR` 两处的 **release / debug** 都看、取 mtime 最新那份，并把「哪一档构建」写进结论（RC8 起 release 排在候选前面：用户装的是 release，先核那一份） | `Subsystem = 2`（GUI），并打印判定用的是哪个目录、哪一档构建 | ✅ Subsystem=2 ← D:\portio-target\release（release 构建） |
| A11 | 安装包是本版本的那个、体积像话 | `python scripts/rc.py`（内部按界面里的版本号找 `Portio_<当前版本>_x64-setup.exe`：仓库根 + **跟 A33 同一档**的 `bundle/nsis`——核的是 release 就只认 release 打出来的包，debug 包顶不上去；档不明才两档都看） | 找到同名文件且体积落在 2–30 MiB；**找不到就报「未验」并点名眼前的旧包**，不拿旧包充数（改前取 mtime 最新的那个，2026-11-20 全量回归拿着两个版本前的 RC3 包就判过了） | ✅ `Portio_1.0.8-RC8_x64-setup.exe` 3382127 字节（3.23 MiB）← `D:\portio-target\release\bundle\nsis`；单测 18 条 |
| A12 | 九处面板右键菜单 | 无头打开 `ui/index.html#ctx-test` | 标题 `CTX-SELFTEST-OK 9`：每处都拦住浏览器默认菜单，且开的是自己那份（条目文字逐条比对） | ✅ 9/9 |
| A13 | 窄窗几何 | `python scripts/rc.py`（内部用 `--window-size` 跑 1024 / 900 两档） | 两档标题都是 `NARROW-SELFTEST-OK`：导入下拉整条留在 180 宽的侧栏里、条目文字被裁住、抽屉收起正好一行高（正文 0）、文件面板折叠后终端吃满整列、设置卡与「完成」按钮全在窗里、整页无横向滚动、右键菜单贴右缘会内收 | ✅ 1024 / 900 |
| A14 | 深浅两套主题几何与对比度 | 无头打开 `ui/index.html#theme-test` | 标题 `THEME-SELFTEST-OK`：11 个分区在两套主题下左上角与宽高完全一致（`worstShift 0`）、主题按钮的太阳/月亮图标按主题互换、六组令牌对比度都在下限之上（分隔线 ≥1.25、强线 ≥1.5、正文 ≥10、次要 ≥4.5、弱化 ≥2.9） | ✅ worstShift 0 |
| A15 | 终端查找（计数 / 坐标 / 环回 / 无命中 / 几何 / 800 行长 buffer + 宽字符 + emoji + 组合字符 / 跨折行命中） | `python scripts/rc.py`（内部在 900×620 下打开 `#find-test`，虚拟时间预算 20s） | 标题 `FIND-SELFTEST-OK`：计数与"自己重扫一遍 buffer"的条数一致（`hits 5`、面板写 `1/5`）、逐条跳过去选区就是查询词本身、首跳落在第 1 条、末条往前一步绕到末条、`findStep` 五条环回算得对、无命中时 `0/0` 且转红、改回有命中的词摘红、查找条不越出终端面板（`gapRight 8 / gapHead 4`）、关掉后选区清空且序号复位；再写 800 行（每 10 行一处命中、交替中文前缀 / emoji 前缀 / ANSI 颜色、夹杂组合字符行、另埋两个 `Portio_lon` 诱饵）判：计数 80 条 / `1/80`、逐格重扫与查找给出同一格号、80 条逐条跳过去选区都是查询词、第 40 条落在视野中间（`viewportY` = 命中行 − 半屏）、第 79 条贴底仍可见且真滚到底（`viewportY = baseY`）、滚过之后旧行还在（`after 80`）、扫描规模 `rows 807 / chars 16607` 且复现 80 条（拦"只扫可视区"）；最后写一条骑在折点上的 `Portio_wrap`（45 列下起点第 41 格、跨 11 格）判：搜得到且只 1 处、起点格号对、长度超出本行剩余格数（真绕过折行）、跳过去 `getSelection()` 是整串、硬换行诱饵 `abc` / `def` 命中数为 0 | ✅ 800 行 80 处全对；跨折行起点 41 格 / 长 11 格 / 选中整串 |
| A16 | 密度三档（宽松 32 / 标准 28 / 紧凑 24） | `python scripts/rc.py`（内部打开 `#density-test`） | 标题 `DENSITY-SELFTEST-OK`：每档 `--row` 读出来是 24 / 28 / 32、相邻两档正好差 4px；九处行高元素（会话栏标题 / 终端标题条 / 文件标题条 / 两路文件栏 / 两条文件行 / 传输标题条 / 传输行）高度在三档里都严丝合缝等于各自 `--row`（±0.6）、相邻两档高度差正好 4px（±0.6）；切档只改高度、左右位置与宽度一动不动（±1，横向重排是这类 bug 最常见的样子）；切完窗口不横向溢出、导入那排不溢出会话栏；设置里的分段控件三档都选中对应项、切回原档位能回去 | ✅ 三档九处全对 |
| A17 | 分屏下的查找只认当前格 | `python scripts/rc.py`（内部打开 `#find-pane-test`） | 标题 `FIND-PANE-SELFTEST-OK`：四格各写自己的标记词（3 / 1 / 2 / 1 处）；A 格查到 `1/3` 并选中第 1 处 → 切到 C 格（等价于点一下那格）后计数立刻变 `0/0` 并转红、`findHits` 记的确实是 C 格的 buffer、A 格高亮被收掉 → 在 C 格查自己的词拿到 `1/2`、逐条跳过去 C 格选中的都是查询词、别格一个选区都没有 → 切回 B 格变 `1/1` 且选中查询词 → 关掉后四格都不留高亮、序号复位 | ✅ 修前 10 条断言全 FAIL，修后全 PASS |
| A18 | 三类连接入口 | `python scripts/rc.py`（内部打开 `#connect-entry-test`） | 标题 `CONNECT-ENTRY-SELFTEST-OK`：点「新建连接」面板从空白起（主机空、端口 22、认证回口令、私钥路径空、私钥框收起 / 口令框露出）；快速连接 `deploy@10.0.8.12:2222` 回车后主机 / 端口 / 用户 / 认证全对上；双击口令认证那台会话开面板且字段带对；`ssh://ops@[fe80::1]:2200` 解析成主机 `fe80::1` + 端口 `2200`；空输入只提示、不开面板 | ✅ 修前 5 条断言 FAIL、修后全 PASS |
| A19 | 会话增删改与分组 | `python scripts/rc.py`（内部打开 `#sessions-test`） | 标题 `SESSIONS-SELFTEST-OK`：加三条／改一台不新增且排到最前／清单里没有口令字段／封顶 40 条并挤掉最老的；分到分组后组头与计数对、折叠进 localStorage 且组员行收起、移出分组落回「未分组」、解散最后一组回到「最近使用」；删一条同时从清单与列表消失；搜索只留命中且计数写成「命中/总数」；**磁盘那份用 `last_used` 写的时间戳读回来要认得出「最近使用」**（旧写法是 `last`，落盘一次就把它抹成 0） | ✅ 反向验证 1 条断言 FAIL |
| A20 | 已知主机面板 | `python scripts/rc.py`（内部打开 `#hosts-test`） | 标题 `HOSTS-SELFTEST-OK`：三条记录画三行、计数写「3 条」；长指纹只露前 10 位加省略号、全文挂在 `title` 上；删掉 `h.example.com:2222` 之后同一台机器的 `:22` 还在（端口是键的一部分）、计数变「2 条」、回执文案对；IPv6 主机整串显示也能删；删空之后没有行、计数写「无」、空态那句解释在；再喂一批能正常长回来。「删除后重连走首次信任」那半句在 Rust 侧（`known_hosts` 两条单测） | ✅ 反向验证 1 条断言 FAIL |
| A21 | 强调色六套预置 | `python scripts/rc.py`（内部打开 `#accent-test`） | 标题 `ACCENT-SELFTEST-OK`：没选过时落默认青；换蓝后 `data-accent` 与 `--accent` 都对，且 `--accent` 就是那张色片的值（不靠两处写死对上）；`--on-accent` 与 `--accent` 不同色；主按钮底色等于 `--accent`（关掉过渡再量）；切浅色后选的还是蓝、主色换成浅色那一档；认不出的值回默认；设置里只有一颗色片是选中态且名字跟着变；**ANSI 绿不跟着主色变**、而终端光标跟着 | ✅ 反向验证 1 条断言 FAIL |
| A22 | 终端配色方案 | `python scripts/rc.py`（内部打开 `#term-theme-test`） | 标题 `TERM-THEME-SELFTEST-OK`：没选过时是「跟界面」且 `html` 上没有 `data-term`；选 Nord 后底/字/ANSI 绿成套换、底色与界面底色不同源；此时把界面切浅色，终端那套色一动不动（界面底色确实变浅了）；Dracula 与 Nord 两套真的不同；回「跟界面」后属性消失、深色下终端底色回到原值；认不出的值读成「跟界面」；**真终端对象的 `options.theme`** 也跟着换了；换主色不动 Nord 的 ANSI 绿、光标仍跟主色 | ✅ 反向验证 2 条均翻红 |
| A23 | 字号 / 字体 / 密度三件 | `python scripts/rc.py`（内部打开 `#font-test`） | 标题 `FONT-SELFTEST-OK`：出厂态无 `data-ui-font` / `data-mono`、终端 13px 且族名含 JetBrains Mono；界面字号「大一号」把 `--fs-13` 从 13px 抬到 14px、真元素算出来的字号跟着变大，而**终端字号一动不动**；终端字号 18 时界面 `--fs-13` 一动不动（两套互不带动）；字号 30 / 8 越界读回 13、下界 9 认；换 Consolas 后 `data-mono` 落上、**真终端族名以 Consolas 打头且末尾有 monospace 兜底**；Cascadia 与 Consolas 族名不同、认不出的名字不留痕回「自动」；密度三档 24 / 28 / 32、相邻正好差 4px、seg 跟着走；界面与终端共用同一个 `--mono` 令牌 | ✅ 反向验证两条都翻红：去掉 `eachTerm` 换字体那行 → FAIL「真终端的族名没以 Consolas 打头」；删掉宽松档 `--row:32px` → FAIL「宽松档 --row 应为 32px：28 ≠ 32」「标准 → 宽松 差 0px」 |
| A24 | 启动时的面板显隐 | `python scripts/rc.py`（内部打开 `#boot-test`） | 标题 `BOOT-SELFTEST-OK`：出厂态两个 seg 都是「记住上次」、盘里没有 boot 键；三档语义四种组合逐个核（记住上次用记忆态 / 总是展开恒展开 / 总是收起恒收起）；改「启动时」**眼前的会话栏与文件面板都还开着**，且 `portio.sidebarFolded` / `portio.filesFolded` 两个记忆键一个字节都没变；模拟启动：总是收起 → 会话栏真收起（`--sidebar` 归 0）、文件面板进 `files-folded` 且折叠钮 `aria-pressed=true`；总是展开 → 两处都回来、宽度回到记忆值（不是 0）；认不出的档位读成「记住上次」且不回写垃圾；seg 选中项跟着落盘值走 | ✅ 反向验证两条都翻红：① 在 `applyBootMode` 里顺手 `applyBootSide()` / `applyBootFiles()`（把设置当命令用）→ FAIL「选了「总是收起」后眼前的会话栏还开着：true ≠ false」「…文件面板还开着」；② 在 `setFoldUI` 里顺手写 `portio.sidebarFolded`（启动覆盖污染记忆）→ FAIL「启动覆盖不改会话栏记忆态："1" ≠ "0"」。还原后 `BOOT-SELFTEST-OK` |
| A25 | 文件面板权限列开关 | `python scripts/rc.py`（内部打开 `#perm-test`） | 标题 `PERM-SELFTEST-OK`：出厂态没有 `data-perm`、seg 选「显示」、盘里没有这个键，远端行是 5 列；关掉后 `data-perm="hide"`、权限单元格 `display:none`、**远端行只剩 4 列**（轨道真被收走）、名字列多出的宽度正好 68 + 4（gap）；而**大小列与时间列的右缘一点都不挪**（0.5px 内）、行宽与行高（= `--row`）不变；本地行始终 4 列不受影响；认不出的值读成「显示」且不回写垃圾；落盘与 seg 选中跟着走，再开回来列数回 5、名字列宽度回原值 | ✅ 反向验证两条都翻红：① 删掉 `html[data-perm="hide"] .fp-row.has-perm{…}` 那条（只藏单元格、留着 68px 轨道）→ FAIL「关掉后远端行只剩 4 列：5 ≠ 4」「关掉后名字列多出来的宽度：0 ≠ 72（差 -72）」「关掉后大小列的右缘不许挪：994 ≠ 1062（差 -68）」；② `readPerm` 去掉白名单校验（认不出的值原样返回）→ FAIL「认不出的值读成显示："collapse" ≠ "show"」。还原后 `PERM-SELFTEST-OK` |
| A26 | 终端开局格数 | `python scripts/rc.py`（内部打开 `#panes-test`） | 标题 `PANES-SELFTEST-OK`：出厂态读到单屏、seg 选「单屏」、盘里没有这个键；选「2×2 四格」立刻落盘、seg 跟着走，而**眼前那个标签的格数一点没变**（设置描述下一次开局，不是立即执行的动作）；模拟一次开机：第一个标签真摊成 4 格且网格是 2×2、带焦点描边类，**第二个标签仍是 1 格**，一次性标记只消费一次；单屏档同样只影响下一个开局标签；认不出的值读成「单屏」且不回写垃圾 | ✅ 反向验证三条都翻红：① `createLocalTab` 里不再调 `fillQuad` → FAIL「2×2 开局应 4 格：1」「2×2 开局应是 2×2 网格：1×1」「四格应有焦点描边类」；② `readPanes` 去掉白名单（`v || 单屏`）→ FAIL「认不出的档位应读成单屏：tri」；③ `applyBootPanes` 里顺手把当前标签摊开 → FAIL「改开局格数不许动眼前这一下：1 → 4」。还原后 `PANES-SELFTEST-OK {"cells":[1,4,1,1]}` |
| A27 | 面板宽度两层 | `python scripts/rc.py`（内部打开 `#layout-test`） | 标题 `LAYOUT-SELFTEST-OK`：出厂态读到「记住上次」、seg 选「记住上次」、宽度档选「标准」、盘里没有这两个键；手拖一次（360px）记忆层落盘、界面跟着走；切成「用默认 + 窄」按开机口径重落一次 → 侧栏 **200px**、分栏 **50.00%**、抽屉 **172px**，而**记忆层三个键一个字没被改写**（仍是 360 / 0.6600 / 200）；换回「记住上次」再落一次 → 三处原样回到 360px / 66.00% / 200px；认不出的值各回各的默认（`auto` → 记住上次、`300` → 标准）且不回写垃圾 | ✅ 反向验证三条都翻红：① 开机落尺寸顺手走 `applySidebar`（会落盘）→ FAIL「用默认不许改写宽度记忆：200」「记住上次应回到 360px：200px」；② `readLayoutMode` 去掉白名单（直接返回盘里的值）→ FAIL「认不出的布局档应读成记住上次：auto」；③ `applyBootLayout` 的分栏不退 50%（仍读记忆层）→ FAIL「用默认分栏应回 50.00%：66.00%」。还原后 `LAYOUT-SELFTEST-OK {"layout":["360px","66.00%","200px"]}` |
| A28 | 离线说明页与代码对表 | `python scripts\check_site.py`（也就是 `rc.py` 的 A28，纯 Python 不开浏览器） | 打印 `OK`：`docs/site/index.html` 那一节的每一项设置都在设置面板里真的存在、每一颗按钮的档位都被页面写到、滑块范围（终端字号 9–24）对得上；页面写了一项产品里没有的项同样 FAIL；版本串只能是当前那个，且至少出现在署名 / 安装 / 版本段三处 | ✅ 首跑 `OK 16 项设置 / 40 个档位` |
| A29 | 传输队列的空态、计数与几条文案 | `python scripts\rc.py`（内部打开 `#transfer-test`） | 标题 `TRANSFER-SELFTEST-OK`：空队列时那句「空。上传、下载、同步的进度都会在这里」在；第一行一出现它就消失（`empty:false`）；三条之后行数 3、标题条计数 `3`、正文里 3 条 `.tr`；45600000/106000000 的进度条是 `43%`、行尾写「43% · 101 MB」；完成那条满格且写「完成 · 6.0 KB」；还没开始那条写「排队」；每个传输行都有尺寸且右缘不越出抽屉 | ✅ 反向验证两条都翻红：① 把空态删除改回 `.hint` 旧写法 → FAIL「队列里有行了，空态提示还挂着」「三条都在跑了，空态提示还挂着」（`empty:true`）；② 让 `transferRow` 不调 `syncTransferCount` → FAIL「标题条计数应是 3：2」（`num:2`）。还原后 `TRANSFER-SELFTEST-OK {"rows":3,"num":"3","bar":"43%","empty":false}` |
| A30 | 后端出错时界面有没有话说 | `python scripts\rc.py`（内部打开 `#net-fail-test`） | 标题 `NET-FAIL-SELFTEST-OK`：四类回包（`No such file or directory` / `Permission denied` / `Connection refused` / `no space left on device`）都翻成「发生了什么 + 下一步怎么做」，认不出的保留原文并带命令名；列目录失败时块里留一句「列目录失败，原因见右下角提示」、路径条不被写成打错的路径、不抛；上传 / 下载失败各落成「失败」红条（进度条 `0%` 且用 `--danger`）、标题条计数为 2、toast 分别是「远端磁盘已满：…」与「连接超时：…」 | ✅ 反向验证两条都翻红：① 下载改回直连 `bridge.invoke` → FAIL「核后端出错这一路的过程抛了异常：Cannot read properties of null (reading 'invoke')」（行停在「排队」）；② 错误翻译改回大小写敏感 → FAIL「「No such file or directory」应翻成「路径不存在：…」」「「Permission denied」应翻成「权限不足：…」」。还原后 `NET-FAIL-SELFTEST-OK {"remote":"列目录失败，原因见右下角","failed":2}` |
| A31 | 发布截图是本版本那一套 | `python scripts/rc.py`（纯 Python 读清单对图，不开浏览器） | `docs/shots/manifest.json` 的 `version` 与界面里的版本串一致，清单里十张图逐张都在 `docs/shots/` 里、字节数跟清单记的一样；版本对不上 → **SKIP 并点名是哪一版**（不报 PASS，别拿旧界面当本版物料）；版本对上但少图 / 字节数变了 → **FAIL 并点名那张** | ✅ 10 张全是 1.0.8-RC2 的（1.58 MiB）；反向验证两条：① 给 `portio-dark-main.png` 尾部多写 1 字节 → `FAIL … portio-dark-main.png（清单 126790 字节 / 现在 126791 字节）`；② 清单版本改回 `1.0.7-RC9` → `SKIP … 这套图是 1.0.7-RC9 那一版的，当前是 1.0.8-RC2`。还原后 PASS |

| A32 | 格式与 lint 闸（跟 CI 那关同一个口径） | `python scripts/rc.py`（内部跑 `cargo fmt --all --check` 与 `cargo clippy --workspace --all-targets -- -D warnings`） | 两条都干净才 PASS；格式没过要报出 `文件:行`（同一文件的两个 hunk 折成一条）、clippy 没过要报出 `文件:行:列`，两道同时没过时一次说清 | ✅ 12.2s（增量，clippy 零警告）；反向验证两条都翻红：① 往 `crates/core/src/lib.rs` 塞一行 `pub fn _rc_probe( )->i32{1}` → `FAIL … fmt 有文件没格式化：crates\core\src\lib.rs:36`；② 塞 `let unused = 1` 那句 → `FAIL … clippy 有警告：crates\core\src\lib.rs:39`。还原后 PASS |

| A33 | 这份 exe 真的起得来 | `python scripts\rc.py`（拉起 `portio-app.exe`、枚举该进程的顶层窗口标题、盯住存活，用完 `taskkill /T` 收干净；非 Windows 报「未验」；结论末尾点名核的是 release 还是 debug 构建） | 进程撑过 10s+4s 还在、且有一条窗口标题带 `Portio` 才 PASS；起后当场退出 / 进程在但一个窗口都没有 / 标题不对 / 标题里出现 `ERR:` 都 FAIL（多窗口时有一个带 `ERR:` 就红，不许挑好看的那个报） | ✅ 14.6s：`窗口标题 'Portio'，撑过 14s 没退（release 构建）`，收尾后 `Get-Process portio-app` 无残留。反向：`launch_verdict` 里「进程在、没有窗口」一档在单测里钉住不许过 |

| A34 | 包里那份 exe 就是核的那份 | `python scripts\rc.py`（用 7-Zip 把 A11 认的那份安装包拆到临时目录——**只拆不装**，不写注册表、不进开始菜单、拆完删掉——再拿里面的 `portio-app.exe` 与构建产物逐字节对；非 Windows / 没装 7-Zip 报「未验」） | 包里拆得出 `portio-app.exe`、大小与构建产物一致、抹掉打包器那几位 `__TAURI_BUNDLE_TYPE_VAR_` 标记后逐字节一致才 PASS；拆不出 / 大小不同 / 别处差一个字节 / 包里那份还写着 `UNK`（打包器没改写它）都 FAIL | ✅ 0.2s：`包里那份 13709312 字节，跟构建产物逐字节一致（只差打包器写的标记：UNK → NSS）← Portio_1.0.8-RC9_x64-setup.exe（release 构建）`；单测 13 条（`scripts/test_rc_installer.py`），含「别处差 1 字节必须红」「包里那份还带 UNK 必须红」「没有构建产物可比只能报未验」 |

| A34 的由来（2026-11-20 RC9） | A11 只核「文件名对不对 + 体积像不像话」，查不出「装的是上一轮那份 exe」；A33 核的是**构建产物**，不是**包里那份**。实测拆开 RC8 的包：里面那份与 `release/portio-app.exe` 大小都是 13709312 字节，但 SHA-256 不同——差 3 个字节，位置在 `__TAURI_BUNDLE_TYPE_VAR_UNK` 与 `__TAURI_BUNDLE_TYPE_VAR_NSS` 这一串上（打包器把 `UNK` 改写成包型 `NSS`）。所以判据不是「差几字节就算了」，而是「精确抹掉这几位标记后再逐字节比」 |
| A35 | 回归脚本自己那批单测 | `python scripts\rc.py`（跑 `scripts/test_*.py` 全批，命令与 CI `ci.yml` 里那条 `python -m unittest discover -s scripts -p "test_*.py"` 一致） | 退出码 0、收尾是 `OK`、且真解析到 `Ran N tests` 且 N ≥ 1 才算 PASS；`Ran 0 tests`、解析不到条数、没有 `OK`、退出码非 0 全 FAIL——「一条都没跑到」正是「假装跑过」的样子；按平台跳过的条数要单独写明 | ✅ 1.3s：`163 条通过（按平台跳 1 条...）`；单测 9 条（`scripts/test_rc_scripts.py`），含「零条也算红」「解析不到也算红」「A35 真接进计划表」「本地这条命令与 CI 那条一致」；反向验证：塞一个必定失败的 `test_zzz_negative.py` → `0 通过 / 1 失败`、退出码 **1**，删掉即回 PASS |
| A35 的由来（2026-11-20 RC10） | 整跑 A1 是 `cargo test`、A32 是 fmt/clippy，`scripts/test_*.py` 这一批（154 条）只在 CI 里跑，**本地整跑一条都没跑过**。于是「改完 `rc.py` 忘了跑对应单测」时本地三十几项全绿、推上去 CI 才红，与 RC3 的「本地的绿要等于 CI 的绿」正相反 |
| A36 | 窗口起来了，界面也真画出来了 | `python scripts\rc.py`（只对这一个子进程开 WebView2 调试口，进真 webview 读一句 DOM，读完 `taskkill /T` 收干净；非 Windows 报「未验」） | 等页面从 `about:blank` 导航到 `tauri.localhost`、等 `readyState` 变 `complete`（最多 10s）之后，四条都得对上才 PASS：标题里没有 `ERR:`、标题栏那个版本串**就是本版**、`window.findScan` 是函数（`app.js` 跑完了）、至少一个终端对象且 DOM ≥ 20000 字节；导航不到 / 加载不完 / 标题炸 / `app.js` 没跑完 / 没有终端对象 / 只剩骨架 都 FAIL。**手上这份 exe 不是本版构建时报「未验」**——那只是没核到，不是坏了 | ✅ 2.8s：`界面已加载：标题 'Portio'、版本 1.0.9-RC1、DOM 94432 字节、1 个标签、xterm 1 个（release 构建）`；不带 `CARGO_TARGET_DIR` 时拿仓库里那份旧 debug → 报未验：`这份 exe 里的界面是 1.0.7-RC3，仓库是 1.0.8-RC10——不是本版构建…`、退出码 3；单测 18 条（`scripts/test_rc_webview.py`），含「没进到界面必须红」「`readyState` 不到 complete 必须红」「`app.js` 没跑完必须红」「没有终端对象必须红」「只剩骨架必须红」「等不到加载完会假红」 |
| A36 的由来（2026-11-20 · 1.0.9-RC1） | A33 核的是「进程没退 + 窗口标题带 Portio」，可那个标题是 `tauri.conf.json` 里写死的，窗口一开就挂着——界面里一根筋没加载，这条照样成立。实测把探针接到真 webview 才发现：仓库 `target\debug` 里那份 exe 是 1.0.7-RC3 时期构建的，界面里还写着 RC3 的版本号，而 A33 一路绿灯。另外反向验证时第一眼读到的 `readyState` 是 `interactive`（已经导航过去、还没解析完），拿这个下判会把「正在加载」误判成「加载坏了」——所以先等 `complete` 再读，且「手上这份不是本版」按未验算、不按红算。 |


| A37 | 那几条自检在真窗口里也跑得动 | `python scripts\rc.py`（同一个 WebView2 调试口：拉起 exe → 先读版本串确认是本版 → 存下 localStorage → 逐条 `Page.navigate` 到自检钩子 → 读**页面自己**的 `document.title` → 跑完把偏好写回去 → `taskkill /T` 收干净；非 Windows 报「未验」） | 七条（split / clip / fold / ctx / find / find-pane / transfer）每条都得对上**它自己的**前缀（`CLIP-SELFTEST-OK 10`、`CTX-SELFTEST-OK 9` 这种全文，不是笼统一个 `SELFTEST-OK`），而且只在 `location.hash` 对上、`readyState = complete` 之后才认；任一条 `ERR:` / 没跑出结果 / 标题空 → FAIL 并点名；跑前跑后的偏好必须同一份，写回后不一致 → FAIL（「我的偏好被自检挪了」）；这份 exe 不是本版构建 → 未验 | ✅ 3.7s：`7 条在真窗口里跑过（split-test、clip-test、fold-test、ctx-test、find-test、find-pane-test、transfer-test）；跑前存下、跑完写回的偏好一字没动（release 构建）`；单测 24 条（`scripts/test_rc_selftests.py`），含「读到上一条的标题必须红」「前缀对上但缺数字必须红」「一条都没跑必须红」「没写回必须红」；反向验证两次都翻红：① 把第一条挪成不存在的 `nope-test` → `FAIL … nope-test 没跑出结果（标题 Portio，期望以 SELFTEST-OK 开头）`、退出码 1；② 把「确认写回」那行改成恒 False → `FAIL … 跑完没把设置写回去——我的偏好被自检挪动了`、退出码 1 |
| A37 的由来（2026-11-20 · 1.0.9-RC2） | 那 21 条自检一直跑在 `file://` 上：没有真后端、`localStorage` 是临时 profile，真窗口是另一回事。实测挖出三个坑：① 只改 fragment 是同文档导航，页面不重载，启动那段自检压根不跑（标题一直是 `Portio`，等 25s 也没结果）；② `/json/list` 里的标题比页面慢一拍——翻到 `ctx-test` 读到的却是上一条 `fold-test` 的结果；③ 跑完一看 `portio.drawer` 从 28 变成 172，那是我的偏好被自检挪了。所以改成「带查询串才叫真重载、标题从页面自己嘴里读且只在 hash 对上后认前缀、跑前存偏好跑完写回」。会改设置的那几条（主题 / 字号 / 密度 / 强调色 / 终端配色 / 启动布局 / 权限列 / 开局格数 / 面板宽度 / 会话 / 已知主机 / 窄窗）**不进这一轮**——它们动的是我的真偏好，甚至真文件 |
| A38 | 会改设置的那批自检也在真窗口里跑 | `python scripts\rc.py`（同一个调试口，额外给它一份一次性偏好目录：拉起 exe → 等标题栏版本串出现（不是等 `readyState`）→ 逐条 `Page.navigate` 到九个自检钩子、读页面自己的 `document.title` → 收进程 → 删临时目录） | 九条（panes / layout / density / accent / term-theme / boot / perm / font / theme）各自前缀全对才过；还要三层证据俱在：一次性目录里真建出了 localStorage 库（隔离生效）、我真偏好库的文件数 / 总字节 / 最新时间跑前跑后一模一样（没被碰）、`theme.txt` 按原字节写回并核对；任一层不成立都 FAIL 并点名；不是本版构建 → 未验 | ✅ 9.9s：`9 条在一次性 profile 里跑过（panes-test、layout-test、density-test、accent-test、term-theme-test、boot-test、perm-test、font-test、theme-test）；我自己的偏好库一个字节没动，底色文件写回原样（release 构建）`；单测 34 条（`scripts/test_rc_fresh.py`），含「隔离没生效必须红」「偏好库被动必须红」「量不到也得红」「底色文件没写回必须红」「会话与已知主机不许进表」；反向验证：① 让写回只比对不落盘 → `FAIL … 窗口底色文件没写回原样`、退出码 1；② 假装一次性目录没建出库 → `FAIL … 一次性 profile 里没冒出 localStorage 库——隔离没生效`、退出码 1 |
| A38 的由来（2026-11-20 · 1.0.9-RC3） | A37 只搬了不动的七条，剩下九条要改的正是我自己的偏好。「跑完写回」对它们不可靠：中途崩、超时被杀就写不回去。实测发现 WebView2 认进程级的 `WEBVIEW2_USER_DATA_FOLDER`，于是换成「物理隔离」——空偏好目录、跑完删掉，比还原稳。同时撞出两个坑：① 给的那层目录下 WebView2 会再套一层 `EBWebView`，判「隔离生效」不能拼死路径；② 空偏好首启时 `about:blank` 那一帧也报 `complete`，等「加载完」会读到空白页、版本串是空的。另外发现启动本身会按新偏好的主题重写真目录里的 `theme.txt`，所以这份文件得存了再写回。 |
| A39 | 会写盘的两条自检也在真窗口 + 真后端里跑 | `python scripts\rc.py`（同一个调试口 + 一次性偏好目录：拉起 exe → 等版本串 → 跑前先把 `theme.txt` / `sessions.json` / `known_hosts` 按字节存下 → 逐条 `Page.navigate` 到 `#sessions-test` / `#hosts-test` 读页面自己的 `document.title` → 收进程等 2s（后端落盘是「先写 .tmp 再改名」）→ 按原字节写回（原本没有的那份收走）→ **再独立读一遍**逐份跟跑前对 → 删临时目录） | 两条各自前缀全对才过；还要两层俱在：① `sessions.json` 确实变了（它没冒出来也没变，说明这两条根本没走真后端，等于没核）② 三份文件都回到跑前那份字节（原来没有的那份现在也不许在）。任一层不成立 → FAIL 并点名；不是本版构建 → 未验 | ✅ 12.4s：`2 条在真窗口 + 真后端里跑过（sessions-test、hosts-test）；会话清单确实落了盘（sessions.json 变了），跑完按原字节收回、逐字节核对一致（release 构建）`；单测 39 条（`scripts/test_rc_appdata.py`），含「没落盘必须红」「没收回去必须红」「量不到也算没收干净」「测试自己造出来的那份要收走、我本来没有的不许凭空造一份」；反向验证两次都翻红：① 还原函数换成「什么都不做」→ `FAIL … 这几份后端文件没收回原样：theme.txt、sessions.json`；② 把前后指纹冻成同一份（假装没落盘）→ `FAIL … 跑完 sessions.json 没冒出来也没变——这说明这两条没在真后端上跑过…等于没核` |
| A39 的由来（2026-11-21 · 1.0.9-RC4） | A37/A38 之后只剩这两条还在无头里跑。先试了最省事的办法：给子进程改 `APPDATA` 让后端也落进一次性目录——**没用**，实测新目录里什么都没长出来，真 app-data 里的 `theme.txt` 照样被启动改写（Tauri 取的是 Known Folder API，不认进程环境变量）。于是改成存/收/核三步。写第一版时判据只信还原函数的返回值，反向验证直接把「什么都不做的还原函数」喂进去——照样报绿，而会话清单其实早被换成测试那 45 条了；所以补了「收完再独立读一遍」这一层。 |
| A40 | 窄窗那条自检也在真窗口里跑（按 1024 / 900 两档视口） | `python scripts\rc.py`（同一个调试口 + 一次性偏好目录：拉起 exe → 等版本串 → 在**同一根长连会话**里`Emulation.setDeviceMetricsOverride` 把布局视口改成 1024×620 → `Page.navigate` 到 `?nw=1024x620#narrow-test` → 读页面自己的 `document.title` → 再改成 900×620 重来一遍 → 收进程 → 删临时目录） | 两档各自前缀全对才过，另加两层：① 自检标题里那个 `w=` 必须等于我要求的那档（界面还停在 1180 宽就算红）；② 界面实际视口 `window.innerWidth` 也必须等于那一档；③ 两档几何不许一样，折叠态终端宽度要按档收窄。隔离照旧：一次性 profile 里真建出库、我真偏好库指纹不变、`theme.txt` 写回原样；不是本版构建 → 未验 | ✅ 9.7s：`2 档在真窗口里跑过（1024x620、900x620）；折叠态终端宽度按档收窄（1024 宽 834px、900 宽 710px），视口是真换过来的；我自己的偏好库一个字节没动，底色文件写回原样（release 构建）`；单测 44 条（`scripts/test_rc_narrow.py`）；反向验证：把 `set_viewport` 做成空转 → `FAIL … 1024x620：自检说自己在 1180 宽里量的，它不是 1024——这档没在窄窗里跑；900x620：… 不是 900` |
| A40 的由来（2026-11-21 · 1.0.9-RC5） | A37/A38/A39 之后只剩三条还在无头里跑，`#narrow-test` 是其中最像「真窗口才量得准」的一条。它一直卡在「真窗口只有一个宽度」：`tauri.conf` 固定 1180×690。绕法是调试口自带的换视口命令，不用动 Rust。撞出来的坑是**这条命令是会话级的**——开一条新连接发一次、连上就设、断开就回原样，而 `cdp_call` 每次都是新会话，照它的写法「这条会话设视口、那条会话读结果」，读到的会是退回 1180 的那份。所以两档得在同一根长连会话里跑完。第一版判据还把排序方向写反了（从窄往宽排），第一次跑就自己撞红（`视口从 900 收窄到 1024，终端宽度却从 710 变到 834`）——那一步正好说明几何判据是活的。 |
| A41 | 最后两条自检也在真窗口 + 真后端里跑（`#net-fail-test` / `#connect-entry-test`） | `python scripts\rc.py`（同一个调试口，**故意不给**一次性偏好目录——要的就是我的真偏好：拉起 exe → 等版本串 → 先读现场（Tauri 桥 / `localStorage` 里的 `portio.theme` / 界面底色对真 app-data 的 `theme.txt`），并让后端真回一次 `sessions_read` → 跑前把 `theme.txt` / `sessions.json` / `known_hosts` 按字节存下 → 逐条 `Page.navigate` 到 `?st=<钩子>#<钩子>` → 收进程 → 按跑前状态收回 → 再独立读一遍逐份对 | 三层缺一即红：① 两条自检各自的标题前缀对（`NET-FAIL-SELFTEST-OK` / `CONNECT-ENTRY-SELFTEST-OK`）；② 证明这轮真跑在我的真后端 / 真偏好上（没有 Tauri 桥、`localStorage` 是空的（一次性 profile 就是空的）、偏好里没有 `portio.theme`、界面底色与 `theme.txt` 对不上、`sessions_read` 没回话——任一条都判红）；③ 收回后三份文件与跑前逐字节一致，「量不到」也算没收干净 | ✅ 见 §7 |
| A41 的由来（2026-11-21 · 1.0.9-RC6） | A40 之后只剩这两条还在无头里跑。它们跟前几条不一样：它们**本来就不该写盘**——`#net-fail-test` 塞的是后端替身，`#connect-entry-test` 只点入口、不连主机；实测跑完 `sessions.json` 连冒都没冒出来、`theme.txt` 一个字节没动。所以这轮判据的重心不在「收得回来」，而在**「这轮到底是不是在我的真偏好里跑的」**：1.0.9-RC3 起凡要改设置的自检都换一次性 profile，环境变量写错一处，这两条会在一份空偏好里跑得漂漂亮亮，却跟我的会话清单一句话都没说上。反向验证两条：把子进程换成一次性空 profile → 界面底色是 `dark`、真 app-data 是 `light`，判据当场翻红（「两边对不上，这轮没读我的真偏好」）；故意在自检过程中往 `sessions.json` 写一笔、还原做成空转 → 判据点名「`sessions.json` 没收回原样」，同一笔写、还原照做就绿并如实写「跑完这几份被动过」。另把结论口径改了一次：这两条没写盘就写「一个字节没动」，并明说收回这套是护栏、不替它们担保。 |

### 怎么跑 A6–A9（无头）

自检逻辑写在 `ui/app.js` 里，由 URL hash 触发，结果写进 `<title>`——所以不需要另做核验页，
直接打开产品页本身：

```powershell
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$page   = "file:///C:/Users/Tyler%20Zhang/Doubao/chats/2026-11-17/new-chat/portio/ui/index.html"
$prof   = Join-Path $env:TEMP "portio-rc"

foreach ($frag in "", "#split-test", "#clip-test", "#fold-test") {
  & $chrome --headless=new --disable-gpu --allow-file-access-from-files `
            "--user-data-dir=$prof" --dump-dom "$page$frag" |
    Select-String -Pattern "<title>.*</title>" | ForEach-Object { $_.Matches.Value }
}
```

四个必踩的坑（走过一次就够了）：

1. 自检页必须放在 `ui/` 里，否则 `vendor/*`、`tokens.css` 相对路径断掉，假报 `FitAddon is not defined`。
2. 必须带 `--allow-file-access-from-files`，否则 `file://` 下加载 vendor 会被拦。
3. 无头默认 `prefers-color-scheme: light`，要拍深色得靠 `?theme=dark` 或页面自己的 `applyTheme("dark")`。
4. 用 PowerShell 的 `>` 重定向抓 `--dump-dom` 会得到 0 字节，要用 `subprocess`（Python）或 `Select-String` 直接吃管道。

---

## 2. 需要人工在本机点一遍的（无头做不到 hover / 拖拽 / 真右键 / 真键盘）

| # | 项 | 点哪里 | 看到什么才算过 | 状态 |
|---|---|---|---|---|
| M1 | 安装包能装能起 | 双击 `Portio_<版本>_x64-setup.exe` | 装完桌面快捷方式在、启动 3 秒内出完整界面（无空白首帧） | ◻ |
| M2 | 三类连接入口 | 新建连接 / 快速连接一行回车 / 双击会话 | 三条路径都能走到连接面板、字段带对（A18 已自动核；剩下的是真机上看着顺不顺手） | ✅ 自动化 |
| M3 | 会话增删改与分组 | 会话右键：重命名 / 分到分组 / 解散分组 | 增删改与分组逻辑、以及「最近用过」在落盘之后还认得出来（A19 已自动核；写盘那半步另有 Rust 单测；拖拽分组仍未做）；**拖拽分组未做** → ✗ | ✅ 自动化（A19）/ ✗ 拖拽 |
| M4 | 三个导入来源 | 「导入会话」下拉三项 | 有样本时逐条导入；本机无 Xshell / WinSCP 样本 → 🚫 | 🚫 |
| M5 | 面板右键菜单 | 九个面板各点一次右键 | 每个面板开自己的菜单、**一个浏览器默认菜单都不出现**；条目是否合用（A12 已覆盖"开的是自己那份"，剩下的是"看着顺不顺手"） | ◻ 实机手感 |
| M6 | 文件面板与传输队列折叠 | 终端标题条那颗钮 / 抽屉右侧按钮 | 折叠后文件面板宽度真归 0、右缘静止无痕迹；队列收起只占一行（A13 已量尺寸，剩下是"看着舒服不舒服"） | ◻ 实机手感 |
| M7 | 复制粘贴 | 终端里选中一段，按 `Ctrl+Shift+C`，再 `Ctrl+V` | 剪贴板内容对；`Ctrl+C` 没选中时仍然打断命令 | ◻ |
| M8 | 分屏 | `Ctrl+Shift+D` / `Ctrl+Shift+E` / `Ctrl+Shift+W` | 1→2→4 格，当前格描边，读数跟着当前格 | ◻ |
| M9 | 查找 | `Ctrl+F` 输入一个 banner 里的词 | 计数 `1/N`、命中行居中（A15 已自动核计数 / 坐标 / 环回 / 无命中转红 / 查找条几何 / 800 行长 buffer / 中文·emoji·组合字符行上的列号 / 居中落点与贴底 / 扫描规模，剩下是"跳过去那条看着对不对"与满缓冲时的跟手感、以及真实耗时） | ◻ 实机手感 |
| M10 | 主题与密度 | 标题栏月亮钮（三档循环）、设置里密度三档（紧凑 / 标准 / 宽松） | 深浅切换无组件错位（A14 已两套各量一遍几何、并算过令牌对比度，剩下是"眼睛看着舒服不舒服"）；密度两档九处行高都等于 `--row`、两档只差 4px、切档不横向错位（A16 已自动核，剩下是 24 高下 12 号字读起来挤不挤） | ◻ 实机手感 |
| M11 | 窄窗 | 窗口拉到 1024×620、再拉到 900 宽 | 导入下拉不越界、模态「完成」按钮不被挤出（A13 已按这两档量过几何，剩下是 900 宽下读起来挤不挤） | ◻ 实机手感 |
| M12 | 设置 → 已知主机 | 打开设置看列表 | 有记录时显示 `host:port` + 指纹，删除后重连走首次信任 | 列表/截断/按端口删/空态已自动核（A20）；「删除后重连走首次信任」由 Rust 侧单测钉住（`known_hosts: forget_makes_the_next_connection_first_seen_again`、`forget_only_touches_the_port_it_names`）；只剩「真机上点一遍」的手感 | ✅ 自动化（A20 + 2 条 Rust 单测） |

> M1–M12 一直没做过全：这台机器常被占用（锁屏 / PIP 虚拟桌面里 WebView2 起不来）。
> 谁先有空，一次点完最好；每条只要一帧截图或一句「哪一步不对」就够。

---

## 3. 逐 Sprint 出口标准（排期原文 → 现在的结论）

| Sprint | 出口标准（排期原文） | 本机能不能验 | 结论 | 差什么 |
|---|---|---|---|---|
| S1 | `cargo tauri dev` 起得来，CI 能出三平台空包 | 前半能，后半不能 | 前半 ✅（每轮 `tauri build --debug --bundles nsis` 走通）；后半 ✗ | 无 CI、无 GitHub 远端（用户未拍板） |
| S2 | 能连上 3 台真实主机，断网重连不崩 | 不能 | 🚫 | 无测试服务器与凭据 |
| S3 | `vim` 与 `tmux` 全屏正常，`htop` 不错行 | 不能 | 🚫 | 同上 |
| S4 | 连 / 敲 / 中文路径 / 全屏四问全过 | 部分 | 中文路径：本地侧 ✅（真实临时目录单测）；远端 🚫；连与敲 🚫；全屏按钮在，实机未点 ◻ | 服务器 + 一次实机点检 |
| S5 | 会话能增删改、分组拖拽正常 | 能 | 增删改 ✅（`sessions.json` 落盘）；分组 ✅（右键分到分组）；**拖拽 ✗** | 拖拽分组记在 backlog，未排期 |
| S6 | 导入 30 条真实会话，失败项有明细 | 不能 | 🚫 | 本机没有 Xshell / WinSCP 样本（三种解析器各有 5–9 条单测） |
| S7 | 陌生机器不看文档能连上 | 不能 | 🚫 | 文档已有（`docs/site/index.html`），缺一个真正陌生的人 + 一台机器 |
| S8 | 同一连接上开文件通道，不二次鉴权 | 不能 | 🚫 | 服务器 |
| S9 | 中文名目录进出、上传下载均正常 | 部分 | 本地侧 ✅；远端 🚫 | 服务器 |
| S10 | 断网后恢复继续传，进度与速率准确 | 不能 | 🚫 | 服务器 + 可控断网 |
| S11 | 10GB 文件中断续传成功 | 不能 | 🚫 | 服务器 + 大文件 |
| S12 | 深浅两套主题切完无组件错位 | 能 | 能：`#theme-test` 两套各量 11 个分区几何、`worstShift 0`，令牌对比度全部达标 ✅（A14）；实机切换手感 ◻ | 只剩一次真窗口切换 |
| S13 | 三平台安装包可签名安装 | 不能 | Windows：能出包 ✅（未签名，SmartScreen 会亮）；签名 ✗；mac / linux ✗ | 证书 + 两台平台机器 |
| S14 | 三个平台安装包齐全，新用户不看文档能连上第一台机器 | 不能 | 文档 ✅（离线页 + 发布说明）、Windows 包 ✅；其余 ✗ / 🚫 | 见 §5、§6 |

---

## 4. 只有真服务器能过的（这批一次都没跑过）

| # | 项 | 怎么算过 |
|---|---|---|
| B1 | 真实登录（密码 / 私钥 / 带口令的私钥） | 三种都能连上，错了给对应提示 |
| B2 | 首次信任（TOFU）与指纹变更拦截 | 首次记下；改 host key 后连接被拒，提示指向「设置 → 已知主机」 |
| B3 | PTY 尺寸与 resize | 拉窗口后 `stty size` 跟着变；`vim` / `htop` / `tmux` 全屏不错行 |
| B4 | SFTP 同连接复用 | 不二次鉴权就能列目录、上传、下载 |
| B5 | 中文名与特殊字符（远端） | `创建目录/文件`、进出、上传下载都正常 |
| B6 | 断网续传（下载 / 上传） | 拔网线 → 恢复后从 `.portio-part` 偏移接着传，进度与速率对 |
| B7 | 10GB 大文件 | 一次中断后续传完成，全程不回退别的工具 |
| B8 | 分屏新开通道 | 已连接标签分出来的格能独立收输入、独立 resize |
| B9 | 已知主机删除后重连 | 删除记录 → 重连走首次信任，标准没降 |

> 一句话：**B1–B9 是这份清单里唯一能真正证明"这东西能用"的部分**，代码写得再齐也替不了。

---

## 5. 只有用户能给的（我这边拿不到）

| # | 差什么 | 卡住哪些项 |
|---|---|---|
| C1 | Windows 代码签名证书（或先明确"内测不签名"） | S13 / S14 gate |
| C2 | 自动更新分发端点（放哪、走什么协议） | S13 的自动更新 |
| C3 | 崩溃远端上报服务（要不要出网、报到哪） | S13 的远端上报 |
| C4 | macOS / Linux 机器与打包环境 | 三平台包（CI 已用 GitHub 自家 runner 顶上，仍未在真机上跑过） |
| C5 | ~~是否建 GitHub 远端、从哪版走 PR、release 何时打~~ | ✅ 已定：`github.com/yunyu697/portio` 公开；打 `v<版本>` tag 即发版，**RC 及以后发包、Alpha 只打 tag**；main 直推。判定逻辑已从 workflow 里抽到 `scripts/release_gate.py`，17 个单测（`scripts/test_release_gate.py`）覆盖 Alpha / RC / 正式版、tag 与仓库版本不一致、后缀不认识（旧 bash 会把 `-Beta1` 当正式版发出去） |
| C6 | 开源许可证选型（MIT / Apache-2.0 / 其它） | 仓库已公开但暂无 LICENSE，默认"保留所有权利"，与"先免费开源"口径冲突 |

---

## 6. v0.4 gate 现在能不能过

**不能。** 本机能验的那部分（自动化 10 项 + 文档 + Windows 出包）是全绿的，但 gate 的原话是
「三个平台安装包齐全，新用户不看文档能连上第一台机器」，两半都没到：

- 三个平台 → 只有 Windows，且没签名（C1 / C4）；
- 新用户不看文档能连上 → 缺一次真人陌生环境试用（S7 / B1）。

**能先发什么**（不需要任何人给东西就能做的）：Windows 内测包 + 离线说明页 + 发布说明。
这也是 `docs/release-notes.md` 里已经写清楚的那一版；它的「已知限制」就是这份清单的 B / C 两类。

**要过 gate 的最短路径**（按依赖排序）：

1. 给一台能连的测试机（或允许我在本机起一个只监听回环的 sshd）→ 一次干掉 B1–B5、B8、B9；
2. 断网续传与 10GB（B6 / B7）在同一台机器上做，需要能控网络；
3. C1 / C4 到位 → 三平台签名包；
4. 最后才是 S7 的真人试用。

> 关于「本机起 sshd」：Windows 自带 OpenSSH Server 可选功能，但装它等于改系统能力，
> 按守则我不能自作主张装，等你点头。

---

## 7. 回归记录

| 日期 | 版本 | A 类（自动化） | M 类（人工） | B / C 类 | 备注 |
|---|---|---|---|---|---|
| 2026-11-19 | `v1.0.5-Alpha2` | A1–A10 全绿（82 tests / 4 条无头判据 / 2 个守卫 / 版本 OK / GUI 子系统） | 未跑 | 未跑 | 首次建立清单；顺带发现并修掉排期文档里 S14 行被写串的位置 |
| 2026-11-19 | `v1.0.5-RC1` | `scripts/rc.py` 一把跑完：**11 通过 / 0 失败 / 0 跳过**，56.8s（82 tests、4 条无头判据、2 个守卫、版本 `OK v1.0.5-RC1`、GUI 子系统、安装包体积） | 未跑 | 未跑 | 进入 RC 阶段；自动化从"手打命令"改成固定入口 |
| 2026-11-19 | `v1.0.5-RC2` | `scripts/rc.py` → **12 通过 / 0 失败 / 0 跳过**，64.7s（多出 A12 `#ctx-test` 九处面板右键菜单 9/9）；反向验证：故意改错一处期望条目即 FAIL 并点名位置 | 未跑 | 未跑 | M5 的"开的是不是自己那份"已自动化，只剩实机手感 |
| 2026-11-19 | `v1.0.5-RC3` | `scripts/rc.py` → **13 通过 / 0 失败 / 0 跳过**，75.1s（多出 A13 `#narrow-test` 两档窄窗 1024 / 900 全 OK，含 5 条窄窗几何判据）；反向验证：去掉条目裁切即 FAIL 并点名越界 32px | 未跑 | 未跑 | M6 的折叠尺寸、M11 的窄窗越界已自动化，只剩实机手感 |
| 2026-11-19 | `v1.0.5-RC4` | `scripts/rc.py` → **14 通过 / 0 失败 / 0 跳过**，93.1s（多出 A14 `#theme-test`：11 个分区两套主题 `worstShift 0`、六组令牌对比度达标）；反向验证：浅色下改 statusbar 高度与分隔线色即 FAIL 并点名 4px / 1.08 | 未跑 | 未跑 | M10 的深浅几何已自动化，只剩眼睛与密度三档 |
| 2026-11-19 | `v1.0.5-RC5` | `scripts/rc.py` → **15 通过 / 0 失败 / 0 跳过**，75.6s（多出 A15 `#find-test`：900 宽下计 5 处命中、`1/5`、坐标逐条对上、环回与无命中转红全对、查找条 `gapRight 8 / gapHead 4`）；反向验证：needle 截短 + 去掉转红即 FAIL 并点名四条 | 未跑 | 未跑 | M9 的计数/坐标/环回/几何已自动化，只剩"跳过去那条看着对不对" |
| 2026-11-19 | `v1.0.5-RC6` | `scripts/rc.py` → **15 通过 / 0 失败 / 0 跳过**，89.9s（A15 扩成 120 行长 buffer + 宽字符 + ANSI + 居中 + 贴底；顺手修掉"中文行上高亮右偏"这个真 Bug：`findScan` 原来把字符下标当格号）；反向验证两个反例分别放回去都 FAIL 并点名（`findCol 6 vs cellCol 11`、`viewportY 65 应 58`） | 未跑 | 未跑 | M9 只剩"看着对不对"与长 buffer 跟手感；宽字符只在无头里验过 |
| 2026-11-19 | `v1.0.5-RC7` | `scripts/rc.py` → **15 通过 / 0 失败 / 0 跳过**，68.6s（A15 素材拉到 800 行 / 80 处命中，加 emoji 与组合字符，新增"扫描规模"判据 `rows 807 / chars 16607`）；反向验证：① `findScan` 只扫可视区 → FAIL 五条（计数掉到 2、`1/2`、逐格 80 vs 查找 2）；② 格号修复放回去 → FAIL 点名 emoji 行 `findCol 6 / cellCol 7` | 未跑 | 未跑 | 耗时在无头虚拟时钟里量不到（`performance.now` 在定时器回调里冻结），只能报规模；满 8000 行的缓冲与真实输入耗时仍未验证 |
| 2026-11-19 | `v1.0.5-RC8` | `scripts/rc.py` → **16 通过 / 0 失败 / 0 跳过**，134.6s（新增 A16 `#density-test`：两档 `--row` 28 / 24、九处行高严丝合缝、两档只差 4px、切档左右与宽度一动不动、窗口无横向溢出、分段控件跟着走）；反向验证：① 文件行写死 30px → FAIL 六条；② 只在紧凑档把本地文件栏右移 6px → FAIL 四条（`624 → 630`、`340 → 334`） | 未跑 | 未跑 | M10 的密度几何已自动化，只剩"24 高下字挤不挤"这一眼；另发现清单原文写「密度三档」，实际只有标准 / 紧凑两档，已改准并记账 |
| 2026-11-19 | `v1.0.6-RC4` | `scripts/rc.py` → **17 通过 / 0 失败 / 0 跳过**，114.2s（多出 A17 `#find-pane-test`：分屏后换格即重扫，计数 / 命中 / 选区 / 高亮跟着当前格走）；反向验证：先写用例再修——同一页在修之前 **10 条断言全 FAIL**（切格后仍记着上一格 buffer、C 格报了 3 处、A 格高亮未清、选区留在别格），改完 `FIND-PANE-SELFTEST-OK`。另出三平台包 `Portio 1.0.6-RC4`，四资产齐、`prerelease: true` | 未跑 | 未跑 | M9 只剩「真窗口里点着看」这一眼；mac / linux 包未在真机装 |
| 2026-11-19 | `v1.0.6-RC5` | `scripts/rc.py` → **18 通过 / 0 失败 / 0 跳过**，117.2s（新增 A18 `#connect-entry-test`：新建连接 / 快速连接回车 / 双击口令会话三条入口字段全对、`ssh://ops@[fe80::1]:2200` 解析正确、空输入不开面板）；反向验证：把 `openConnect` 换回老写法，「新建连接」那组 **5 条断言 FAIL** 并逐条点名（端口 `2222`、认证 `key`、私钥路径仍在、两框显隐没换回来）。另出三平台包 `Portio 1.0.6-RC5`（exe 3352875 B / dmg 9460253 B / deb 4940892 B / AppImage 83134968 B，`prerelease: true`） | 未跑 | 未跑 | M2 已被 A18 覆盖，只剩真机手感；mac / linux 包未真机装 |
| 2026-11-19 | `v1.0.6-RC6` | `scripts/rc.py` → **19 通过 / 0 失败 / 0 跳过**，109.2s（新增 A19 `#sessions-test`：会话增删改 / 分组 / 折叠 / 搜索，外加「磁盘上的 last_used 读回来认不认最近使用」；`cargo test --workspace` 84 passed，其中 app crate 新增两条落盘单测）；反向验证：把 `saveSession` 与排序换回 `last`，A19 FAIL 并点名「磁盘上的 last_used 认得出最近使用：false ≠ true」。另出三平台包 `Portio 1.0.6-RC6`（exe 3353673 B / dmg 9467814 B / deb 4947424 B / AppImage 83143160 B，`prerelease: true`；linux 作业跑了约 30 分钟） | 未跑 | 未跑 | 会话删改与分组只剩真机手感；拖拽分组仍未做；mac / linux 包未真机装 |
| 2026-11-19 | `v1.0.6-RC7` | `scripts/rc.py` → **20 通过 / 0 失败 / 0 跳过**，83.8s（新增 A20 `#hosts-test`：已知主机列出 / 指纹截断 / 按端口删 / 删空后的空态；`cargo test --workspace` 90 passed，多出的是密钥变更标记、建连错误映射、删记录回到首次信任、忘掉某端口不影响同机其它端口四条）；反向验证两处：`connect_error_text` 改回 `e.to_string()` → app 断言 FAIL；核验删除改回只按 host 删 → A20 FAIL 并点名「同机另一端口还在：false ≠ true」。另出三平台包 `Portio 1.0.6-RC7`（exe 3358391 B / dmg 9472094 B / deb 4947594 B / AppImage 83139064 B，`prerelease: true`） | 未跑 | 未跑 | 密钥变更只有单测、没有真服务器换钥匙；真机窗口没点 |
| 2026-11-19 | `v1.0.6-RC8` | `scripts/rc.py` → **20 通过 / 0 失败 / 0 跳过**，111.4s（`cargo test --workspace` 92 passed，多出的是两条日志并发单测：8 线程 × 120 条必须一条不丢、同线程重入必须被放过且闸能复位）；反向验证：写日志的互斥改回进程级 `AtomicBool` → FAIL 并点名「并发写日志丢了行：只落下来 120 / 960」。另出三平台包 `Portio 1.0.6-RC8`（exe 3356439 B / dmg 9463772 B / deb 4945556 B / AppImage 83139064 B，`prerelease: true`） | 未跑 | 未跑 | 并发只在回环文件上验过；崩溃钩子没真触发过；真机窗口没点 |
| 2026-11-19 | `v1.0.6-RC9` | `scripts/rc.py` → **20 通过 / 0 失败 / 0 跳过**，116.6s（`cargo test --workspace` 95 passed，多出的是三条「读日志尾巴」单测：损坏文件里坏字节前后完好的行都要拿到、只取最后 N 行与边界、文件不存在读成空）；反向验证：改回 `read_to_string` → FAIL 并点名「坏字节前面完好的行没拿到：""」。另补跑 `cargo fmt --all` 与 `clippy -D warnings`（消掉 run 44505662151 那条 CI 红）；三平台包 `Portio 1.0.6-RC9`（exe 3358660 B / dmg 9470390 B / deb 4945780 B / AppImage 83147256 B，`prerelease: true`） | 未跑 | 未跑 | 只造过损坏内容，真实磁盘坏块没模拟；只剩 `.log.1` 时读不到内容未改；真机窗口没点 |
| 2026-11-19 | `v1.0.6-RC10` | `scripts/rc.py` → **20 通过 / 0 失败 / 0 跳过**，86.2s（`cargo test --workspace` 96 passed，多出的是「定位日志文件」那条：含空格/中文路径都只在引号内，且旧写法确实把 `/select,` 括进引号）；反向验证：改回 `.arg(format!("/select,{}", …))` → FAIL 并打出真实命令行 `"/select,C:\\Users\\Tyler Zhang\\…"`。三平台包 `Portio 1.0.6-RC10`（exe 3358285 B / dmg 9470333 B / deb 4944570 B / AppImage 83134968 B，`prerelease: true`）；main CI run 44518756656 五项全 success | 未跑 | 未跑 | 资源管理器窗口没实机确认（桌面锁着）；mac/linux 那条定位路径没动 |
| 2026-11-19 | `v1.0.7-RC1` | `scripts/rc.py` → **20 通过 / 0 失败 / 0 跳过**，137.6s（`cargo test --workspace` 97 passed，多出的是「轮转后读日志」那条：只剩 `.1` / 当前文件 0 字节都读到旧内容，当前文件有新内容则只读它）；反向验证：回落那支短路 → FAIL 点名「当前文件不存在时该读 .1：""」。三平台包 `Portio 1.0.7-RC1`（exe 3357107 B / dmg 9473551 B / deb 4942768 B / AppImage 83134968 B，`prerelease: true`）；main CI run 44530131804 五项全 success | 未跑 | 未跑 | 真实轮转没在窗口里点过；「定位日志文件」仍定位当前文件 |
| 2026-11-19 | `v1.0.7-RC2` | `scripts/rc.py` → **21 通过 / 0 失败 / 0 跳过**，67.4s（新增 A21 `#accent-test` 1.5s）；反向验证：把 `root.dataset.accent = want` 改成恒等 `"teal"`（只记 localStorage、界面没换）→ FAIL 并点出 8 条，含「换色后 data-accent 是 azure："teal" ≠ "azure"」「ANSI 绿不跟着主色变：true ≠ false」。check_design_tokens / check_ui_scale / node --check 均 OK。三平台包 `Portio 1.0.7-RC2`（exe 3359627 B / dmg 9477429 B / deb 4946390 B / AppImage 83143160 B，`prerelease: true`）；main CI run 44535030414 五项全 success | 未跑 | 未跑 | 真窗口里没点过（桌面锁着）；六套色在真实终端滚动内容上的观感只看静态截图 |
| 2026-11-19 | `v1.0.7-RC3` | `scripts/rc.py` → **22 通过 / 0 失败 / 0 跳过**，50.4s（新增 A22 `#term-theme-test` 1.2s）；反向验证两条：① 去掉 `eachTerm` 那一行（CSS 换了真终端没换）→ FAIL 点名「真终端的背景就是 Nord 的底："#090c10" ≠ "#2e3440"」；② 把 `delete root.dataset.term` 改成 `dataset.term = "auto"` → FAIL「没选过时 html 上没有 data-term："auto" ≠ undefined」。check_design_tokens / check_ui_scale / node --check 均 OK（第一版自检写了 9 处字面色值被 check_design_tokens 拦下，已改成令牌互比）。三平台包 `Portio 1.0.7-RC3`（exe 3363277 B / dmg 9483460 B / deb 4947522 B / AppImage 83143160 B，`prerelease: true`） | 未跑 | 未跑 | 真窗口里没点过（桌面锁着）；无 SSH 服务器，真实会话里大量 ANSI 内容下的观感未验证 |
| 2026-11-19 | `v1.0.7-RC4` | `scripts/rc.py` → **23 通过 / 0 失败 / 0 跳过**，81.7s（新增 A23 `#font-test` 1.8s）；反向验证两条：① 去掉 `applyMono` 里的 `eachTerm(t => t.options.fontFamily = termFont())`（CSS 换了、真终端没换）→ FAIL 点名「真终端的族名没以 Consolas 打头：\"JetBrains Mono\",…」「Cascadia 与 Consolas 的族名不同：…撞了」；② 删掉 `html[data-density="comfortable"]{--row:32px}` → FAIL「宽松档 --row 应为 32px：28 ≠ 32」「标准 → 宽松 差 0px，应正好 4px」（② 那一跑 JS 没还原、与 ① 叠着跑，所以输出里同时带着 ① 的失败项）。还原后 `FONT-SELFTEST-OK`。check_design_tokens / check_ui_scale / node --check / cargo fmt --all --check 均 OK。三平台包 `Portio 1.0.7-RC4`（exe 3367657 B / dmg 9493220 B / deb 4955346 B / AppImage 83134968 B，`prerelease: true`） | 未跑 | 未跑 | 真窗口里没点过（桌面锁着）；JetBrains / Cascadia 是否真装在这台机器上没核（族名串按回落走）；无 SSH 服务器，9 号 / 24 号在真实满屏输出下的可读性未验证；本地 NSIS 包改用 `CARGO_TARGET_DIR=D:\portio-target` 才打出来（C 盘见下） |
| 2026-11-20 | `v1.0.7-RC5` | `scripts/rc.py` → **24 通过 / 0 失败 / 0 跳过**，213.2s（新增 A24 `#boot-test` 2.2s；A1 在 `CARGO_TARGET_DIR=D:\portio-target` 上全新编译 157.3s，97 passed）；反向验证两条：① `applyBootMode` 里顺手立刻改眼前布局 → FAIL「选了「总是收起」后眼前的会话栏还开着」「…文件面板还开着」；② `setFoldUI` 里顺手写 `portio.sidebarFolded` → FAIL「启动覆盖不改会话栏记忆态："1" ≠ "0"」。还原后 `BOOT-SELFTEST-OK`。check_design_tokens / check_ui_scale / node --check 均 OK。三平台包 `Portio 1.0.7-RC5`（exe 3367447 B / dmg 9498340 B / deb 4955524 B / AppImage 83147256 B，`prerelease: true`；Release run 44563959577：gate + 三平台四项全 success，macOS 那格第一次被取消、`gh run rerun --failed` 重跑后过） | 未跑 | 未跑 | 真窗口里没真重启过一次（桌面锁着），「重开 Portio 后按偏好收放」是靠自检里模拟启动那条判据兜的；无 SSH 服务器，`总是收起` 在真实会话里省出来的宽度有什么观感未验证 |
| 2026-11-20 | `v1.0.7-RC6` | `scripts/rc.py` → **25 通过 / 0 失败 / 0 跳过**，178.1s（新增 A25 `#perm-test` 2.3s）；反向验证两条：① 删掉「隐藏时收走 68px 轨道」那条 CSS → FAIL「远端行只剩 4 列：5 ≠ 4」「名字列多出来的宽度：0 ≠ 72」「大小列的右缘不许挪：994 ≠ 1062」；② `readPerm` 去掉白名单 → FAIL「认不出的值读成显示：\"collapse\" ≠ \"show\"」。还原后 `PERM-SELFTEST-OK`。check_design_tokens / check_ui_scale / node --check 均 OK。三平台包 `Portio 1.0.7-RC6`（exe 3372544 B / dmg 9502433 B / deb 4957370 B / AppImage 83147256 B，`prerelease: true`；Release run 44576133068 首跑四项全 success） | 未跑 | 未跑 | 真窗口里没点过（桌面锁着）；无 SSH 服务器，真实远端目录里权限串长短不一（`-rw-r--r--` 与 `lrwxrwxrwx`）时的对齐只在无头页面里量过；1024 窄窗下藏列的效果只核了不溢出，没有实机手感 |
| 2026-11-20 | `v1.0.7-RC7` | `scripts/rc.py` → **26 通过 / 0 失败 / 0 跳过**，202.2s（新增 A26 `#panes-test` 3.8s；A1 在 `CARGO_TARGET_DIR=D:\portio-target` 上 144.6s，97 passed）；反向验证三条：① 开局不摊开 → FAIL「2×2 开局应 4 格：1」「2×2 开局应是 2×2 网格：1×1」「四格应有焦点描边类」；② `readPanes` 不过白名单 → FAIL「认不出的档位应读成单屏：tri」；③ `applyBootPanes` 当场摊开 → FAIL「改开局格数不许动眼前这一下：1 → 4」。还原后 `PANES-SELFTEST-OK {"cells":[1,4,1,1]}`。check_design_tokens / check_ui_scale / node --check 均 OK。三平台包 `Portio 1.0.7-RC7`（exe 3371429 B / dmg 9507487 B / deb 4958050 B / AppImage 83147256 B，`prerelease: true`；Release run 44587528236 首跑四项全 success；本地 NSIS 包 4581282 B） | 未跑 | 未跑 | 真窗口里没点过（桌面锁着）：四格开局的实际手感（每格列数、焦点、`Ctrl+F`）只有无头页面兜着；无 SSH 服务器，四格里连主机的通道行为（每格一条 PTY）未端到端验证 |
| 2026-11-20 | `v1.0.7-RC8` | `scripts/rc.py` → **27 通过 / 0 失败 / 0 跳过**，192.2s（新增 A27 `#layout-test` 1.7s；A1 在 `CARGO_TARGET_DIR=D:\portio-target` 上 130.4s，97 passed）；反向验证三条：① 开机落尺寸顺手落盘 → FAIL「用默认不许改写宽度记忆：200」「记住上次应回到 360px：200px」；② `readLayoutMode` 去掉白名单 → FAIL「认不出的布局档应读成记住上次：auto」；③ 分栏不退 50% → FAIL「用默认分栏应回 50.00%：66.00%」。还原后 `LAYOUT-SELFTEST-OK {"layout":["360px","66.00%","200px"]}`。check_design_tokens / check_ui_scale / node --check 均 OK。三平台包 `Portio 1.0.7-RC8`（exe 3375150 B / dmg 9510808 B / deb 4959920 B / AppImage 83143160 B，`prerelease: true`；Release run 44596899518 四项全 success；main CI 44596888277 success；本地 NSIS 包 4580142 B） |
| 2026-11-20 | `v1.0.7-RC8`（物料轮，未进位） | `rc.py --fast` → **27 通过 / 0 失败 / 1 跳过**（50.4s，A28 0.1s：`OK 16 项设置 / 40 个档位`）；`python -m unittest scripts/test_check_site.py` 10 通过；反向验证三条：密度写回两档 → FAIL「漏了档位「宽松」」、版本串留 RC7 → FAIL「版本串过期」、项名写错 → FAIL「没写这一项：「终端配色」」＋「写了一项界面里没有的」；还原后 OK | 未跑 | 未跑 | 说明页 §08 从「设置与外观」重写成「自定义」：16 项按「立刻生效 / 下次打开才生效」两批排、40 个档位逐个写到，顺带修掉页面落后两版的「密度两档」「终端字号 11–18」。不单独推 RC tag：纯物料轮，推了会让页面写着 RC9 而下载页仍是 RC8 |

| 2026-11-20 | `v1.0.8-RC1` | `scripts/rc.py` → **30 通过 / 0 失败 / 0 跳过**，56.5s（A11 改判：只认 `Portio_<当前版本>_x64-setup.exe`，找不到就 SKIP 并点名旧包；A10 改沿 `CARGO_TARGET_DIR` 取这一轮构建出来的 exe）；反向验证两条翻红点名；另 13 条单测（`scripts/test_rc_artifacts.py`） | 未跑 | 未跑 | 同一目录里躺着 RC3 旧包也不再判过了——A11 从「有没有留下过安装包」变成了「当前版本的包在不在、体积像不像话」 |
| 2026-11-20 | `v1.0.8-RC2` | `scripts/rc.py` → **30 通过 / 0 失败 / 0 跳过**，56.5s；`python -m unittest scripts.test_rc_selection` 13 通过（与另三份合跑 67 条全过）；反向验证两条：认不出的编号静悄悄丢掉 → `FAILED (failures=2)` 且 `rc.py A99` 变成「只跑 0 项 / 汇总 0 通过 / exit=0」；顺序退回按书写顺序 → `FAILED (failures=1)` | 未跑 | 未跑 | 回归脚本能只跑一项了（`A11` / `A10 A11` / `A10,A11` 都认），改一处核一处从一分钟降到几秒 |
| 2026-11-20 | `v1.0.8-RC2`（物料轮，未进位） | `scripts/rc.py` → **31 通过 / 0 失败 / 0 跳过**，214.1s（A1 151.5s / 97 passed；新增 A31 0.0s）；`python -m unittest scripts.test_shots` 8 通过；反向验证两条（多写 1 字节 → FAIL 点名、清单写旧版本 → SKIP 点名），还原后 PASS | 未跑 | 未跑 | 十张首发截图重出到 `1.0.8-RC2`（原来还是 `1.0.7-RC9` 的界面，press-kit 还指着它们）并配上 `docs/shots/manifest.json`；不单独推 RC tag：纯物料轮，产品代码一个字没动 |
| 2026-11-20 | `v1.0.8-RC4` | `scripts/rc.py` → **31 通过 / 0 失败 / 1 跳过**，246.6s（A1 与 A32 都是冷缓存：cargo test 现编、fmt/clippy 45.8s；唯一跳过的是 A11，整跑时 RC4 的包还没打，打完包单跑转 PASS）；反向验证：把 `findGroups` 的折行拼接条件临时改成 `false` → FAIL「跨折行的 Portio_wrap 搜不到（退回逐行扫了？）」，还原即 PASS | 未跑 | 未跑 | 折成两行的长命令现在搜得出来：先按 `isWrapped` 拼逻辑行再扫，命中回映射成（行, 格），跨折行按格累加长度交给 `select()`；只拼自动折行、不跨硬换行，末行补位空白不算内容（这个 xterm 的 `BufferLine` 没有 `getTrimmedLength`，自己数） |

| 2026-11-20 | `v1.0.8-RC5` | `scripts/rc.py` → **31 通过 / 0 失败 / 1 跳过**，337.3s（A1 冷：进位改了 `Cargo.lock` 里三个 crate 的版本，三个包都得重编，224.4s；A32 fmt/clippy 51.5s；跳过项仍是 A11——整跑时 RC5 的包还没打，打完包单跑 `A10 A11` 转 PASS）；反向验证两处：① 标题栏写回 `RC3` → A5 退出码 1 并点名「ui/index.html 标题栏」；② `Cargo.lock` 里 `portio-ssh` 写回 `RC3` → 点名「Cargo.lock portio-ssh」;另证旧行为：把 lock 里 `portio-core` 写回上一版，`cargo metadata --locked` 与 `cargo build --locked` 都退出码 **101**（`cannot update the lock file … because --locked was passed`），写回新号两者都 0 | 未跑 | 未跑 | 版本号写几处就核几处：`check_versions.py` 从三处扩到七处（清单三处 + 标题栏 `span.ver` + lock 三个 crate），`set_version.py` 直接写 lock（不再等下一次构建）；新增 `test_check_versions.py` 9 条、`test_set_version.py` 4 条锁文件用例 |
| 2026-11-20 | `v1.0.8-RC6` | `scripts/rc.py` → **32 通过 / 0 失败 / 0 未验**，224.6s，**退出码 0**（先打包再整跑：A11 认的是 `Portio_1.0.8-RC6_x64-setup.exe` 4586339 字节）；反向验证：`rc.py --fast A1` → 打 `[未验] A1`、汇总写「0 通过 / 0 失败 / 1 未验」、退出码 **3**（改前这种情况退出 0、只写「1 跳过」） | 未跑 | 未跑 | 整跑的绿不能再含一项没核过的东西：SKIP 改称「未验」单列，退出码分成 0 / 1 / 2 / 3，未验项逐条写明为什么没跑；新增 `test_rc_summary.py` 11 条 |
| 2026-11-20 | `v1.0.8-RC7` | `scripts/rc.py` → **33 通过 / 0 失败 / 0 未验**，225.8s，**退出码 0**（A33 14.4s：`窗口标题 'Portio'，撑过 14s 没退`；单跑 `A33` 15.1s，收尾后无残留进程）；`python -m unittest scripts.test_rc_launch` 12 条；反向证据：`launch_verdict` 五档在单测里各钉一条，「进程在、窗口没画出来」不许过 | 未跑 | 未跑 | 「子系统是 GUI」不等于「这份 exe 起得来」：真把它拉起来、等窗口、核标题、撑 4s、`taskkill /T` 收干净；mac / linux 报「未验」 |
| 2026-11-20 | `v1.0.8-RC8` | `scripts/rc.py` → **33 通过 / 0 失败 / 0 未验**，350.5s，**退出码 0**（A1 164.5s / A32 98.4s 都是 release 冷编之后的重编；A10 `← D:\portio-target\release（release 构建）`、A11 `3382127 字节 ← release\bundle\nsis`、A33 `撑过 14s 没退（release 构建）`）；`python -m unittest scripts.test_rc_artifacts scripts.test_rc_launch` → 30 条（29 过 + 1 按平台跳过） | 未跑 | 未跑 | 「我核的那份 exe，不是用户装的那份」：核的、认的、交的统一到 release 档——`app_exe_dirs()` release 优先、`find_app_exe()` 把档一起返回、`bundle_dirs(kind)` 替掉写死的 debug 目录；单测从 25 条到 30 条（档跟着实际那份走 / 档必须写进结论 / 未知档才回退两档 / `CARGO_TARGET_DIR` 也算进候选） |
| 2026-11-20 | `v1.0.8-RC9` | `scripts/rc.py` → **34 通过 / 0 失败 / 0 未验**，282.1s，**退出码 0**（先打包再整跑：A11 `3380547 字节 ← release\bundle\nsis`、A33 14.5s `撑过 14s 没退（release 构建）`、A34 0.5s `包里那份 13708800 字节，跟构建产物逐字节一致（只差打包器写的标记：UNK → NSS）`；A32 54.1s 增量 clippy）；`python -m unittest scripts.test_rc_installer` 13 条；反向验证：把 `PORTIO_7Z` 指到 `where.exe`（拆不了包）→ `0 通过 / 1 失败`、退出码 **1**，去掉后回到 PASS | 未跑 | 未跑 | 「包没问题」原来只核了包外面的名字与体积，没核包里装的是哪份 exe：A34 用 7-Zip 把 A11 认的那份包拆到临时目录（只拆不装、拆完删掉），拿里面的 `portio-app.exe` 与构建产物逐字节对，只精确放过打包器改写的那几位 `__TAURI_BUNDLE_TYPE_VAR_` 标记（实测 RC8 的包两边同 13709312 字节、SHA-256 不同，差的 3 字节正落在这串上） |
| 2026-11-20 | `v1.0.8-RC10` | `scripts/rc.py` → **35 通过 / 0 失败 / 0 未验**，300.7s，**退出码 0**（先打包再整跑：A11 `3382936 字节 ← release\bundle\nsis`、A33 14.4s `撑过 14s 没退（release 构建）`、A34 0.5s `包里那份 13709312 字节，跟构建产物逐字节一致（只差标记：UNK → NSS）`、A35 1.3s `163 条通过（按平台跳 1 条）`；A32 52.3s）；`python -m unittest scripts.test_rc_scripts` 9 条；反向验证：往 `scripts/` 塞一个必定失败的 `test_zzz_negative.py` → A35 `0 通过 / 1 失败`、退出码 **1**，删掉即回 PASS | 未跑 | 未跑 | 1.0.8 段收口这一项补的是「CI 里跑的那 154 条本地从没跑过」：A1 是 `cargo test`、A32 是 fmt/clippy，`scripts/test_*.py` 只在 `ci.yml` 里跑，于是改完 `rc.py` 忘了跑对应单测时，本地三十几项全绿而推上去才红。A35 把这一批按 CI 同一条 discover 命令纳入整跑，且「Ran 0 tests / 解析不到条数」一律判红 |

每一轮 RC 回归跑完，在表格里加一行；过不了的那几项写进下一轮的「下一步」。
| 2026-11-20 | `v1.0.9-RC1` | A1–A36：**36 通过 / 0 失败 / 0 未验**，276.5s，退出码 0（新增 A36：进真 webview 读到 `版本 1.0.9-RC1、DOM 94619 字节、xterm 1 个（release 构建）`；A35 随之 181 条；A11 `3382341 字节`、A34 包里那份逐字节一致、A33 14.8s、A32 41.7s） | 未跑 | 未跑 | 窗口起来了不等于界面画出来了：A33 的标题是配置文件写死的，这轮补上「真 webview 里界面到底加载出来没有」；不带 `CARGO_TARGET_DIR` 时会拿到旧 debug，实测界面里还是 **1.0.7-RC3**——以前这种情形 A33 是绿的 |
| 2026-11-20 | `v1.0.9-RC2` | A1–A37：**37 通过 / 0 失败 / 0 未验**，95.4s，退出码 0（新增 A37：`7 条在真窗口里跑过（split-test、clip-test、fold-test、ctx-test、find-test、find-pane-test、transfer-test）；跑前存下、跑完写回的偏好一字没动（release 构建）`；A35 涨到 205 条；A31 十张图重出到 1.0.9-RC2） |
| 2026-11-20 | `v1.0.9-RC3` | A1–A38：**38 通过 / 0 失败 / 0 未验**，288.5s，退出码 0（新增 A38：一次性 profile 里跑九条会改设置的自检，真偏好库指纹三次一致、`theme.txt` 跑完仍是 `light`；反向验证两次翻红；A35 239 条） |
| 2026-11-21 | `v1.0.9-RC4` | A1–A39：**39 通过 / 0 失败 / 0 未验**，329.0s，退出码 0（新增 A39：最后两条会写盘的自检进真窗口 + 真后端，跑完会话清单按原字节收回；反向验证两次翻红；A35 278 条；A11 `Portio_1.0.9-RC4_x64-setup.exe 3381773 字节`；A34 包里那份 `13709312 字节`逐字节一致；A32 44.6s；A1 97 passed） | 未跑 | 未跑 | 上一版把「会改设置」的九条搬进去之后，只剩 `#sessions-test` / `#hosts-test` 还在无头里——那里没有后端，`sessions.json` 一个字节都没被写过。这轮补的就是「真的写了、而且我收得回来」。 |
| 2026-11-21 | `v1.0.9-RC5` | A1–A40：**40 通过 / 0 失败 / 0 未验**，128.7s，退出码 0（新增 A40：窄窗那条在真窗口里按 1024 / 900 两档视口跑，终端宽度 834px / 710px 按档收窄；反向验证把换视口做成空转即翻红；A35 336 条；A11 `Portio_1.0.9-RC5_x64-setup.exe 3382696 字节`；A34 包里那份 `13709312 字节`逐字节一致；A31 十张重出到 1.0.9-RC5） | 未跑 | 未跑 | 这一轮前半段被两件事拖住：C 盘掉到 0 字节（连脚本都写不出来），以及 A1 撞上 `rustc-LLVM ERROR: out of memory` / `页面文件太小 os error 1455`。前者清了 329 MB 旧安装包与 1.3 GB 的 flutter 临时目录（另有 2.1 GB 旧客户端日志被删但空间还被打开着的句柄占着）；后者给 A1 加了「按证据降并行度重跑」，并在结论里写明是机器的问题。整跑时 C 盘稳在 1.3 GB 左右。 |
| 2026-11-21 | `v1.0.9-RC6` | A1–A41：**41 通过 / 0 失败 / 0 未验**，344.3s，退出码 0（新增 A41：最后两条自检进真窗口 + 真后端——先证现场（Tauri 桥 / 真偏好 / 底色对 `theme.txt` / `sessions_read` 真回话），再存/收/核 `theme.txt` / `sessions.json` / `known_hosts`；反向验证两次翻红：换成一次性空 profile 时报「界面底色是 dark、真 app-data 是 light」，往 `sessions.json` 写一笔并让还原空转时报「没收回原样」；A35 336 → 377 条；A11 `Portio_1.0.9-RC6_x64-setup.exe 3382412 字节`；A34 包里那份 `13709312 字节`逐字节一致；A31 十张重出到 1.0.9-RC6） | 未跑 | 未跑 | 上一版把窄窗搬完，只剩这两条还在无头里。它们跟前几条不一样：**本来就不该写盘**（跑完 `sessions.json` 连冒都没冒出来），所以这轮的判据重心是「这轮到底是不是在我的真偏好里跑的」——一次性 profile 那套用错地方，它们会空偏好里绿得漂亮却跟我的会话清单一句没说上。21 条界面自检至此全部在真窗口里跑过。另把「头部编号写死」那条测试改成按计划表最大编号比，免得每加一项就改一次测试。 |
