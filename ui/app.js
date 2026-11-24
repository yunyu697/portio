// Portio · S1 外壳。所有交互都是真实现；还没做的功能一律给明确提示，不留点了没反应的按钮。
const root = document.documentElement;
// 终端实例要尽早声明：主题/字号的设置函数在上面就可能被调用，晚声明会踩 TDZ
let term = null;
let fitAddon = null;

// 前端一有异常就把信息写进标题，出问题时不至于对着空白面板瞎猜
window.addEventListener("error", (e) => {
  document.title = "ERR: " + (e.message || e.error);
  const st = document.querySelector('.statusbar .state');
  if (st) st.textContent = 'ERR ' + (e.message || e.error);
});

// ---------- Tauri 桥 ----------
// withGlobalTauri 打开后 window.__TAURI__.core.invoke 可用；纯浏览器预览时降级为 null。
const bridge = window.__TAURI__?.core ?? null;

// 截图 / 核验钩子允许带参数：写成 `#split-demo?theme=light`，先把 `?` 之后的参数摘出来，
// 主 hash 还原成 `#split-demo`。下面各处 demo 与自检判断用的都是 location.hash，
// 带着 `?` 会让 `location.hash === "#split-demo"` 这类精确判断全部失效。
// theme 直接写进 localStorage，后面 applyTheme 读的就是它。
(function () {
  const raw = location.hash;
  if (!raw.includes("?")) return;
  const params = new URLSearchParams(raw.slice(raw.indexOf("?") + 1));
  const t = params.get("theme");
  if (t === "light" || t === "dark" || t === "system") localStorage.setItem("portio.theme", t);
  try {
    history.replaceState(null, "", "#" + raw.slice(1, raw.indexOf("?")));
  } catch {}
})();

// ---------- 运行日志 ----------
// 前端异常 / Promise 未处理拒绝都写进本机日志（Rust 侧 diag_log 落盘），只写本机、不出网。
// 没有 Tauri 桥（纯浏览器预览）时直接不记，不要因为记日志再抛一次错。
function diagLog(level, source, message) {
  if (!bridge) return;
  try {
    bridge.invoke("diag_log", { level, source, message: String(message).slice(0, 4000) }).catch(() => {});
  } catch {}
}
window.addEventListener("error", (e) =>
  diagLog("error", "ui", `${e.message || e.error} @ ${e.filename || "?"}:${e.lineno || 0}:${e.colno || 0}`)
);
window.addEventListener("unhandledrejection", (e) => {
  const r = e.reason;
  diagLog("error", "ui-promise", (r && (r.stack || r.message)) || String(r));
});

// 把 Rust 侧的原始错误翻成人话：说清"发生了什么 + 下一步怎么做"。
// 匹配不上的一律保留原文，宁可粗糙也不隐藏细节。
// 回包大小写不定：系统与协议栈常写 "Permission denied"、"No such file or directory"，
// 所以比对一律用全小写的副本，展示仍用原文——这条以前只按小写比，首字母大写的全掉进兜底。
function explainError(cmd, err) {
  const raw = String(err ?? "");
  const low = raw.toLowerCase();
  const rules = [
    [/authentication|auth failed|userauth|密码|私钥/, "认证被拒绝", "用户名、密码或私钥不对；确认登录方式与凭据后重试"],
    [/econnrefused|connection refused|actively refused/, "连接被拒绝", "端口没开或被防火墙拦了；先用 telnet 探一下 22 端口"],
    [/timed out|timeout|超时/, "连接超时", "网络不可达或服务端限流；检查网络与允许列表"],
    [/no space left|磁盘满/, "远端磁盘已满", "清理远端目录或换目标路径"],
    [/permission denied|permission|权限/, "权限不足", "该账号对目标路径没有权限；换目录或用有权限的账号"],
    [/no such file|not found|不存在/, "路径不存在", "目录可能被删或改名；刷新列表确认"],
    [/host key|hostkey/, "主机指纹变化", "可能被中间人替换；确认指纹后再决定是否继续"],
  ];
  for (const [re, title, hint] of rules) {
    if (re.test(low)) return `${title}：${hint}`;
  }
  return `${cmd} 失败：${raw}`;
}

// 后端调用一律从这个口子过：出错先翻成人话再弹 toast，调用方只看返回 null。
// fakeInvoke 是自检用的替身——无头页里没有真后端，"后端抛错"这一路不塞替身就永远跑不到。
let fakeInvoke = null;
function hasBackend() {
  return !!(fakeInvoke || bridge);
}
async function call(cmd, args) {
  const inv = fakeInvoke ?? (bridge ? bridge.invoke.bind(bridge) : null);
  if (!inv) return null;
  try {
    return await inv(cmd, args);
  } catch (err) {
    toast(explainError(cmd, err));
    return null;
  }
}
// 静默版：失败不弹 toast，由调用方自己决定说什么。救急那条用的就是它——
// 「另存没成」和「清单读坏了」是两件事，各说一句比叠两条更清楚。
async function tryInvoke(cmd, args) {
  const inv = fakeInvoke ?? (bridge ? bridge.invoke.bind(bridge) : null);
  if (!inv) return null;
  try {
    return await inv(cmd, args);
  } catch (err) {
    diagLog("error", cmd, String(err));
    return null;
  }
}

// ---------- 右键菜单 ----------
const ctxMenu = document.getElementById("ctx-menu");
function hideCtx() {
  ctxMenu.classList.remove("open");
  ctxMenu.innerHTML = "";
}
// items: [{label, hint, run, disabled} | {sep:true}]
function showCtx(x, y, items) {
  ctxMenu.innerHTML = "";
  for (const it of items) {
    if (it.sep) {
      const s = document.createElement("div");
      s.className = "ctx-sep";
      ctxMenu.appendChild(s);
      continue;
    }
    const row = document.createElement("div");
    row.className = "ctx-item" + (it.disabled ? " dis" : "");
    row.setAttribute("role", "menuitem");
    const label = document.createElement("span");
    label.textContent = it.label;
    row.appendChild(label);
    if (it.hint) {
      const hint = document.createElement("span");
      hint.className = "hint";
      hint.textContent = it.hint;
      row.appendChild(hint);
    }
    if (!it.disabled) {
      row.addEventListener("click", () => {
        hideCtx();
        try {
          it.run();
        } catch (err) {
          toast(`操作失败：${explainError("unknown", String(err))}`);
        }
      });
    }
    ctxMenu.appendChild(row);
  }
  ctxMenu.classList.add("open");
  // 先摆出来再量尺寸，超出视口就往里收，避免菜单被窗口边缘切掉
  const box = ctxMenu.getBoundingClientRect();
  ctxMenu.style.left = `${Math.max(6, Math.min(x, window.innerWidth - box.width - 8))}px`;
  ctxMenu.style.top = `${Math.max(6, Math.min(y, window.innerHeight - box.height - 8))}px`;
}
document.addEventListener("mousedown", (e) => {
  if (!ctxMenu.contains(e.target)) hideCtx();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") hideCtx();
});
window.addEventListener("blur", hideCtx);

// ---------- 提示条 ----------
const toastBox = document.getElementById("toast");
function toast(text) {
  const el = document.createElement("div");
  el.textContent = text;
  toastBox.appendChild(el);
  setTimeout(() => el.remove(), 2600);
}
// 带 #err-demo 时把几条典型报错的翻译结果摊出来，便于截图核对文案
if (location.hash === "#err-demo") {
  for (const s of [
    "authenticate: userauth failed",
    "Connection refused (os error 10061)",
    "Permission denied (os error 13)",
  ]) {
    toast(explainError("ssh_connect", s));
  }
}

// ---------- 窗口按钮 ----------
async function windowAction(action) {
  const res = await call("window_control", { action });
  if (res) syncMaxButton(res);
}
function syncMaxButton(state) {
  const btn = document.getElementById("btn-max");
  if (!btn) return;
  btn.innerHTML = state === "maximized" ? "&#10064;" : "&#9723;";
  btn.setAttribute("aria-label", state === "maximized" ? "还原" : "最大化");
}
document.getElementById("btn-min").addEventListener("click", () => windowAction("minimize"));
document.getElementById("btn-max").addEventListener("click", () => windowAction("maximize"));
document.getElementById("btn-close").addEventListener("click", () => windowAction("close"));

// 双击标题栏 = 最大化/还原，和原生窗口行为一致；点在按钮上不触发
document.querySelector(".titlebar").addEventListener("dblclick", (e) => {
  if (e.target.closest("button")) return;
  windowAction("maximize");
});

// 窗口状态变化时同步按钮字形（最大化后图标要变成"还原"）
window.addEventListener("DOMContentLoaded", async () => syncMaxButton(await call("window_state")));

// ---------- 主题与密度 ----------
function resolveTheme(pref) {
  if (pref === "system") {
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  return pref === "light" ? "light" : "dark";
}
// 设置项（主题 / 字号 / 滚动缓冲）要作用到**每个已开标签**的终端，不能只管当前这一块。
// tabs 用 var 声明是为了能在它初始化之前（启动时就调用的 applyTheme）安全判空，避开 let 的暂时性死区。
// 设置项（主题 / 字号 / 滚动缓冲）要作用到**每一格终端**（包括分屏出来的格子），不能只管当前这一块。
// tabs 用 var 声明是为了能在它初始化之前（启动时就调用的 applyTheme）安全判空，避开 let 的暂时性死区。
function eachTerm(fn) {
  if (term && !(tabs && tabs.some((t) => t.cells.some((c) => c.term === term)))) fn(term);
  if (tabs) for (const t of tabs) for (const c of t.cells) if (c.term) fn(c.term);
}
function applyTheme(pref) {
  localStorage.setItem("portio.theme", pref);
  root.dataset.theme = resolveTheme(pref);
  eachTerm((t) => { t.options.theme = terminalTheme(); });
  syncSegs();
  // 把实际生效的主题告诉外壳：下次启动窗口底色直接按它建，就不会先闪一下深色。
  // 浏览器里直接打开 ui/index.html 时没有 bridge，静默跳过。
  if (bridge) bridge.invoke("ui_theme_set", { theme: root.dataset.theme }).catch(() => {});
}
const DENSITIES = ["compact", "standard", "comfortable"];
const DENSITY_NAME = { compact: "紧凑", standard: "标准", comfortable: "宽松" };
function applyDensity(density) {
  // 三档：紧凑 24 / 标准 28 / 宽松 32（--row 只有这一处在 tokens.css 里换）
  root.dataset.density = DENSITIES.includes(density) ? density : "standard";
  localStorage.setItem("portio.density", root.dataset.density);
  syncSegs();
}
// ---------- 强调色 ----------
// 主色可换：每套只改「跟主色一起走的四个令牌」（--accent / --on-accent /
// --mark-accent / --term-cursor，色值全在 tokens.css 末段）。
// 终端 ANSI 调色板不跟着动：红绿黄蓝是终端语义（git diff、ls 上色），
// 跟着主色走会让人分不清"这是成功还是我选了蓝色"。
const ACCENT_KEY = "portio.accent";
const ACCENTS = ["teal", "azure", "violet", "amber", "rose", "lime"];
const ACCENT_NAME = { teal: "青", azure: "蓝", violet: "紫", amber: "琥珀", rose: "玫瑰", lime: "青柠" };
function readAccent() {
  const v = localStorage.getItem(ACCENT_KEY);
  return ACCENTS.includes(v) ? v : "teal";
}
function applyAccent(id) {
  const want = ACCENTS.includes(id) ? id : "teal"; // 认不出的值一律回默认，别把界面弄成没主色
  root.dataset.accent = want;
  localStorage.setItem(ACCENT_KEY, want);
  // 终端光标也是主色的一份投影（--term-cursor），换色后要把主题重挂一遍才生效
  eachTerm((t) => { t.options.theme = terminalTheme(); });
  syncAccentDots();
}
function syncAccentDots() {
  const row = document.getElementById("acc-row");
  if (!row) return;
  const cur = root.dataset.accent ?? readAccent();
  for (const dot of row.querySelectorAll(".acc-dot")) {
    const on = dot.dataset.sw === cur;
    dot.classList.toggle("on", on);
    dot.setAttribute("aria-pressed", on ? "true" : "false");
  }
  const name = document.getElementById("acc-name");
  if (name) name.textContent = ACCENT_NAME[cur] ?? ACCENT_NAME.teal;
}
// 标题栏按钮是"一键换观感"：按当前实际显示的主题取反，直接落成明确偏好。
// 之前按 dark→light→system 轮转，"系统自动"在系统本身是深色时等于没变化，
// 用户看到的就是"要点两次才变亮"——三选项照旧留在设置面板里。
document.getElementById("btn-theme").addEventListener("click", () => {
  const pref = localStorage.getItem("portio.theme") ?? "dark";
  const next = resolveTheme(pref) === "dark" ? "light" : "dark";
  applyTheme(next);
  toast(next === "light" ? "已切换到浅色主题" : "已切换到深色主题");
});
// 跟随系统时，系统切换深浅色要立即跟上（以前只在启动那一刻读一次）
window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => {
  if ((localStorage.getItem("portio.theme") ?? "dark") === "system") applyTheme("system");
});
document.getElementById("btn-density").addEventListener("click", () => {
  // 标题栏那颗是"再紧一档 / 再松一档"的一键循环：紧凑 → 标准 → 宽松 → 紧凑。
  const cur = DENSITIES.includes(root.dataset.density) ? root.dataset.density : "standard";
  const next = DENSITIES[(DENSITIES.indexOf(cur) + 1) % DENSITIES.length];
  applyDensity(next);
  toast(`已切换到${DENSITY_NAME[next]}密度`);
});

// ---------- 终端配色 ----------
// 跟界面主题解耦：不选（auto）就沿用界面深浅那套 --term-*/--ansi-*；
// 选了预设就把这九个令牌整体换成那一家，界面切深浅不再带动它（值全在 tokens.css 末段）。
// 光标不在预设里——它永远跟主色（--term-cursor 归强调色管）。
const TERM_KEY = "portio.termTheme";
const TERMS = ["auto", "dracula", "solarized", "nord"];
const TERM_NAME = { auto: "跟界面", dracula: "Dracula", solarized: "Solarized", nord: "Nord" };
function readTerm() {
  const v = localStorage.getItem(TERM_KEY);
  return TERMS.includes(v) ? v : "auto";
}
function applyTerm(id) {
  const want = TERMS.includes(id) ? id : "auto"; // 认不出的值回"跟界面"，别让终端留一套没人认得的色
  localStorage.setItem(TERM_KEY, want);
  if (want === "auto") {
    delete root.dataset.term; // 去掉属性才回到界面那套，写成 data-term="auto" 会一直压着浅色档
  } else {
    root.dataset.term = want;
  }
  // xterm 不跟 CSS 变量活，换完令牌必须把主题重挂一遍
  eachTerm((t) => { t.options.theme = terminalTheme(); });
  syncSegs();
}
// ---------- 字号 / 字体 / 密度 ----------
// 三件事分属两套尺度，别搅在一起：
//   界面字号（两档：标准 / 大一号）→ 换 tokens.css 里那一整套 --fs-*，只动界面文字；
//   终端字号（9–24，滑杆）→ 只动 xterm 的 options.fontSize，界面一个字都不许变；
//   等宽字体（自动 / JetBrains / Cascadia / Consolas）→ 换 --mono，界面小号等宽与终端一起换。
// 早先只有终端字号一条滑杆，界面字号全按 tokens 里的 11–20 定死——"看得清"这件事对不同屏幕
// 上是两回事：高分屏嫌小、老显示器嫌大，界面和终端还常常不是一个方向，所以这两档必须分开。
const UI_FONT_KEY = "portio.uiFont";
const UI_FONTS = ["standard", "large"];
const UI_FONT_NAME = { standard: "标准", large: "大一号" };
function readUiFont() {
  const v = localStorage.getItem(UI_FONT_KEY);
  return UI_FONTS.includes(v) ? v : "standard";
}
function applyUiFont(id) {
  const want = UI_FONTS.includes(id) ? id : "standard";
  localStorage.setItem(UI_FONT_KEY, want);
  if (want === "standard") {
    delete root.dataset.uiFont; // 默认档不留属性，省得以后加第三档时被 old 值压着
  } else {
    root.dataset.uiFont = want;
  }
  // 界面字号不带动终端，但界面变宽变窄会改终端可用格数，得重新量一次
  if (term) fitQuietly();
  syncSegs();
}
const MONO_KEY = "portio.mono";
const MONOS = ["auto", "jetbrains", "cascadia", "consolas"];
const MONO_NAME = { auto: "自动", jetbrains: "JetBrains", cascadia: "Cascadia", consolas: "Consolas" };
function readMono() {
  const v = localStorage.getItem(MONO_KEY);
  return MONOS.includes(v) ? v : "auto";
}
// xterm 的 fontFamily 要的是真族名串，不是 "var(--mono)"：直接把令牌解析出来给它。
// 令牌末尾一律带 monospace，装不上时仍然落在等宽字体上——比例字体会让终端每一列错位。
function termFont() {
  const stack = cssToken("--mono").trim();
  return stack || "ui-monospace, Consolas, monospace";
}
function applyMono(id) {
  const want = MONOS.includes(id) ? id : "auto";
  localStorage.setItem(MONO_KEY, want);
  if (want === "auto") {
    delete root.dataset.mono;
  } else {
    root.dataset.mono = want;
  }
  eachTerm((t) => { t.options.fontFamily = termFont(); });
  if (term) fitQuietly();
  syncSegs();
}
// ---------- 设置 ----------
const FONT_KEY = "portio.fontSize";
const SCROLL_KEY = "portio.scrollback";
function readFontSize() {
  const n = Number(localStorage.getItem(FONT_KEY));
  return Number.isFinite(n) && n >= 9 && n <= 24 ? n : 13;
}
function readScrollback() {
  const n = Number(localStorage.getItem(SCROLL_KEY));
  return Number.isFinite(n) && n >= 1000 ? n : 8000;
}
function setFontSize(px) {
  localStorage.setItem(FONT_KEY, String(px));
  eachTerm((t) => { t.options.fontSize = px; });
  // 只有当前可见的终端能量尺寸，隐藏标签等切回去时靠 activateTab 再 fit
  if (term) fitQuietly();
  syncSegs();
}
function setScrollback(rows) {
  localStorage.setItem(SCROLL_KEY, String(rows));
  eachTerm((t) => { t.options.scrollback = rows; });
  syncSegs();
}
function markSeg(id, value) {
  const box = document.getElementById(id);
  if (!box) return;
  for (const btn of box.querySelectorAll("button")) {
    btn.classList.toggle("on", btn.dataset.v === String(value));
  }
}
// ---------- 启动默认布局（会话栏 / 文件面板） ----------
// 「记住上次」就是原来的行为：折叠状态一直落盘。另外两档是给"每次都要同一个开局"的人用的——
// 干活时常常是纯终端全屏，也有人一开机就要看见两侧面板。这一层只决定**启动那一刻**的样子：
// 改它不许立刻动当前窗口，也不许顺手把「记住上次」那份记忆改掉。
// （三档常量与读写在 syncSegs 之前——启动早期就会有人调 syncSegs，放在这里会撞暂时性死区）
const BOOT_MODES = ["remember", "open", "folded"];
const BOOT_NAME = { remember: "记住上次", open: "总是展开", folded: "总是收起" };
const BOOT_SIDE_KEY = "portio.bootSide";
const BOOT_FILES_KEY = "portio.bootFiles";
function readBoot(key) {
  const v = localStorage.getItem(key);
  return BOOT_MODES.includes(v) ? v : "remember"; // 认不出的值回「记住上次」，别把开局锁死在一个没人认得的档上
}
function applyBootMode(key, mode) {
  localStorage.setItem(key, BOOT_MODES.includes(mode) ? mode : "remember");
  syncSegs();
}
// 三档落到布尔值（true = 收起）：记住上次 → 用记忆态；总是展开 → false；总是收起 → true
function bootFold(mode, remembered) {
  return mode === "open" ? false : mode === "folded" ? true : remembered;
}
// ---------- 文件面板的权限列 ----------
// 远端行比本地行多一列 drwxr-xr-x。它有用（看得出可执行 / 可写），也真占地方：
// 窄窗里 68px 常常是从文件名里抢来的。所以给一个开关，关掉时**整条轨道收走**、名字列吃掉那 68px，
// 行高一点不动（密度那档的规矩照旧）。本地行本来没有这一列，开关不碰它。
const PERM_KEY = "portio.permCols";
const PERM_MODES = ["show", "hide"];
function readPerm() {
  const v = localStorage.getItem(PERM_KEY);
  return PERM_MODES.includes(v) ? v : "show"; // 认不出的值回「显示」，别把一列信息无声地藏掉
}
function applyPerm(id) {
  const want = PERM_MODES.includes(id) ? id : "show";
  localStorage.setItem(PERM_KEY, want);
  if (want === "hide") {
    root.dataset.perm = "hide";
  } else {
    delete root.dataset.perm; // 默认档不留属性，省得以后改默认时被旧值压着
  }
  syncSegs();
}
// ---------- 启动时的终端格数 ----------
// 有人一开机就要四个格（左边跑日志、右边盯着 top），有人永远只要一格。
// 这一档跟「启动时」两行是同一类：**只决定打开应用那一刻**，改它不许当场把眼前摊成四格；
// 也只管第一个标签——用户自己新开的标签、连主机开的标签都仍是一格，别拿开局偏好去接管手上的动作。
const PANES_KEY = "portio.bootPanes";
const PANES_MODES = ["single", "quad"];
const PANES_NAME = { single: "单屏", quad: "2×2 四格" };
function readPanes() {
  const v = localStorage.getItem(PANES_KEY);
  return PANES_MODES.includes(v) ? v : "single"; // 认不出的值回单屏：别让人一开机就被四格糊住
}
function applyBootPanes(id) {
  localStorage.setItem(PANES_KEY, PANES_MODES.includes(id) ? id : "single");
  syncSegs();
}
// ---------- 面板宽度：记忆层之外再给一层默认 ----------
// 原来只有一层：拖过就落盘，开机照上次的来。可"开机就要某个固定宽度"的人没得选，
// 而上一次拖出来的宽窄，常常只是临时为某台机器、某个文件面板调的。
// 所以拆成两层：remember 照旧看记忆层；default 每次开机回到下面那档默认宽度
//（分栏回 50/50、传输队列回一行高——一个「默认布局」该有的样子）。
// 这一层只决定开机那一刻：改它不许当场改宽度，也不许把记忆层擦掉——
// 拖出来的宽度仍记在盘里，换回「记住上次」就还是它。
const LAYOUT_KEY = "portio.bootLayout";
const LAYOUT_MODES = ["remember", "default"];
const LAYOUT_NAME = { remember: "记住上次", default: "用默认" };
const DEFW_KEY = "portio.defWidth";
// 三档都落在 180–420 的拖拽区间里，且是 4px 的整数倍（对应规范 §1 的 4px 刻度）
const DEFW_MODES = [200, 264, 328];
const DEFW_NAME = { 200: "窄", 264: "标准", 328: "宽" };
const DEFW_FALLBACK = 264;
function readLayoutMode() {
  const v = localStorage.getItem(LAYOUT_KEY);
  return LAYOUT_MODES.includes(v) ? v : "remember"; // 认不出的值回「记住上次」：别让人一开机就丢了自己刚拖的宽度
}
function applyLayoutMode(id) {
  localStorage.setItem(LAYOUT_KEY, LAYOUT_MODES.includes(id) ? id : "remember");
  syncSegs();
}
function readDefWidth() {
  const n = Number(localStorage.getItem(DEFW_KEY));
  return DEFW_MODES.includes(n) ? n : DEFW_FALLBACK; // 认不出的值回「标准」，别把侧栏开成个怪宽度
}
function applyDefWidth(px) {
  const n = Number(px);
  localStorage.setItem(DEFW_KEY, String(DEFW_MODES.includes(n) ? n : DEFW_FALLBACK));
  syncSegs();
}
function syncSegs() {
  markSeg("seg-theme", localStorage.getItem("portio.theme") ?? "dark");
  markSeg("seg-density", root.dataset.density ?? "standard");
  markSeg("seg-ui-font", readUiFont());
  markSeg("seg-mono", readMono());
  markSeg("seg-scroll", readScrollback());
  markSeg("seg-term", readTerm());
  markSeg("seg-boot-side", readBoot(BOOT_SIDE_KEY));
  markSeg("seg-boot-files", readBoot(BOOT_FILES_KEY));
  markSeg("seg-perm", readPerm());
  markSeg("seg-panes", readPanes());
  markSeg("seg-layout", readLayoutMode());
  markSeg("seg-defw", String(readDefWidth()));
  syncAccentDots();
  const font = document.getElementById("set-font");
  if (font) font.value = String(readFontSize());
  const out = document.getElementById("font-val");
  if (out) out.textContent = String(readFontSize());
  const note = document.getElementById("theme-note");
  if (note) {
    const pref = localStorage.getItem("portio.theme") ?? "dark";
    note.textContent =
      pref === "system" ? `跟随系统 · 当前${root.dataset.theme === "light" ? "浅色" : "深色"}`
        : pref === "light" ? "浅色" : "深色";
  }
}
// ---------- 已知主机（指纹管理） ----------
// 只读本地 known_hosts：列出 host:port + SHA256 指纹，能删一条。
// 删一条只是让这台主机下次重新走首次信任，不降低校验标准。
let hostDemo = null; // 核验用：无头页面没有后端，用假数据看版式
function shortFp(fp) {
  const body = fp.startsWith("SHA256:") ? fp.slice(7) : fp;
  return "SHA256:" + (body.length > 10 ? body.slice(0, 10) + "…" : body);
}
function renderHostRows(recs) {
  const list = document.getElementById("hosts-list");
  const count = document.getElementById("hosts-count");
  list.textContent = "";
  count.textContent = recs.length ? `${recs.length} 条` : "无";
  if (!recs.length) {
    const empty = document.createElement("div");
    empty.className = "hosts-empty";
    empty.textContent = "还没有记录。第一次连上某台主机时会自动记住它的指纹。";
    list.append(empty);
    return;
  }
  for (const r of recs) {
    const row = document.createElement("div");
    row.className = "hz";
    const hh = document.createElement("span");
    hh.className = "hh";
    hh.textContent = r.host;
    const hp = document.createElement("span");
    hp.className = "hp";
    hp.textContent = ":" + r.port;
    hh.append(hp);
    const hf = document.createElement("code");
    hf.className = "hf";
    hf.textContent = shortFp(r.fingerprint);
    hf.title = r.fingerprint;
    const del = document.createElement("button");
    del.className = "hz-del";
    del.type = "button";
    del.textContent = "删除";
    del.dataset.host = r.host;
    del.dataset.port = String(r.port);
    del.title = `删掉 ${r.host}:${r.port} 的记录`;
    row.append(hh, hf, del);
    list.append(row);
  }
}
async function renderHosts() {
  if (hostDemo) {
    renderHostRows(hostDemo);
    return;
  }
  const recs = await call("hosts_list");
  renderHostRows(Array.isArray(recs) ? recs : []);
}

const settingsModal = document.getElementById("settings-modal");
function toggleSettings(open) {
  const want = open ?? !settingsModal.classList.contains("open");
  if (want) syncSegs();
  settingsModal.classList.toggle("open", want);
  if (want) {
    renderHosts();
    refreshLogInfo();
  }
}
if (location.hash === "#settings") toggleSettings(true);
// 核验用：无头页面上把强调色换成蓝再打开设置，给截图用（跟 #theme-light 同类）
if (location.hash === "#accent-demo" || location.hash === "#accent-demo-light") {
  applyAccent("azure");
  if (location.hash === "#accent-demo-light") applyTheme("light");
  toggleSettings(true);
}
// 核验用：换个终端配色给截图看（#term-demo / #term-demo-light）
if (location.hash === "#term-demo" || location.hash === "#term-demo-light") {
  applyTerm("nord");
  if (location.hash === "#term-demo-light") applyTheme("light");
  toggleSettings(true);
}
// 核验用：界面字号「大一号」+ 终端字号 18 + 宽松密度，三个一起摆出来给截图看
// （#font-demo / #font-demo-light）。它们各自是独立的设置，这里只是把它们同时调到明显位置。
if (location.hash === "#font-demo" || location.hash === "#font-demo-light") {
  applyUiFont("large");
  setFontSize(18);
  applyDensity("comfortable");
  applyMono("consolas");
  if (location.hash === "#font-demo-light") applyTheme("light");
  toggleSettings(true);
}
document.getElementById("btn-settings").addEventListener("click", () => toggleSettings());
document.getElementById("btn-set-close").addEventListener("click", () => toggleSettings(false));
settingsModal.addEventListener("click", (e) => {
  if (e.target === settingsModal) toggleSettings(false);
});
document.getElementById("seg-theme").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (btn) applyTheme(btn.dataset.v);
});
document.getElementById("seg-density").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (btn) applyDensity(btn.dataset.v);
});
document.getElementById("seg-ui-font").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  applyUiFont(btn.dataset.v);
  toast(`界面字号：${UI_FONT_NAME[btn.dataset.v] ?? UI_FONT_NAME.standard}`);
});
document.getElementById("seg-mono").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  applyMono(btn.dataset.v);
  toast(`等宽字体：${MONO_NAME[btn.dataset.v] ?? MONO_NAME.auto}`);
});
document.getElementById("seg-boot-side").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  applyBootMode(BOOT_SIDE_KEY, btn.dataset.v);
  toast(`会话栏启动时：${BOOT_NAME[btn.dataset.v] ?? BOOT_NAME.remember}（下次打开生效）`);
});
document.getElementById("seg-boot-files").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  applyBootMode(BOOT_FILES_KEY, btn.dataset.v);
  toast(`文件面板启动时：${BOOT_NAME[btn.dataset.v] ?? BOOT_NAME.remember}（下次打开生效）`);
});
document.getElementById("seg-perm").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  // 这一档是立刻看得见效果的：藏起来那一下，文件名马上多出 68px，不用等下次打开
  applyPerm(btn.dataset.v);
  toast(btn.dataset.v === "hide" ? "文件面板：权限列已隐藏" : "文件面板：权限列已显示");
});
document.getElementById("seg-panes").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  // 跟「启动时」两行同一套口径：只落盘，不把眼前的标签摊开
  applyBootPanes(btn.dataset.v);
  toast(`开局格数：${PANES_NAME[btn.dataset.v] ?? PANES_NAME.single}（下次打开生效）`);
});
document.getElementById("seg-layout").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  // 只管开机：改完不动眼前宽度（跟「启动时」两行同一套口径）
  applyLayoutMode(btn.dataset.v);
  toast(`面板宽度：${LAYOUT_NAME[btn.dataset.v] ?? LAYOUT_NAME.remember}（下次打开生效）`);
});
document.getElementById("seg-defw").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  applyDefWidth(btn.dataset.v);
  toast(`默认会话栏宽度：${DEFW_NAME[Number(btn.dataset.v)] ?? DEFW_NAME[DEFW_FALLBACK]}（下次打开生效）`);
});
document.getElementById("acc-row").addEventListener("click", (e) => {
  const dot = e.target.closest(".acc-dot");
  if (!dot) return;
  applyAccent(dot.dataset.sw);
  toast(`强调色：${ACCENT_NAME[dot.dataset.sw]}`);
});
document.getElementById("seg-scroll").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (btn) setScrollback(Number(btn.dataset.v));
});
document.getElementById("seg-term").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  applyTerm(btn.dataset.v);
  toast(`终端配色：${TERM_NAME[btn.dataset.v] ?? TERM_NAME.auto}`);
});
document.getElementById("set-font").addEventListener("input", (e) => setFontSize(Number(e.target.value)));
document.getElementById("hosts-list").addEventListener("click", async (e) => {
  const btn = e.target.closest(".hz-del");
  if (!btn) return;
  const port = Number(btn.dataset.port);
  // 核验页（#hosts-demo / #hosts-test）没有后端：删的就是内存里那几条，
  // 好让"点完少一行、计数跟着变"这条路也被真走过一遍，而不是靠假数据摆样子。
  let gone;
  if (hostDemo) {
    const before = hostDemo.length;
    hostDemo = hostDemo.filter((r) => !(r.host === btn.dataset.host && r.port === port));
    gone = hostDemo.length !== before;
  } else {
    gone = await call("hosts_forget", { host: btn.dataset.host, port });
  }
  toast(gone ? `已删除 ${btn.dataset.host}:${port} 的记录` : "这条记录已经不在了");
  renderHosts();
});

// ---------- 运行日志区块 ----------
// 打开设置时读一次路径与体积。浏览器预览（无 Tauri 桥）时如实说明看不到日志，不假装。
async function refreshLogInfo() {
  const pathEl = document.getElementById("log-path");
  const bytesEl = document.getElementById("log-bytes");
  const info = await call("diag_info");
  if (!info) {
    pathEl.textContent = "浏览器预览没有本机日志";
    pathEl.title = "";
    bytesEl.textContent = "—";
    return;
  }
  pathEl.textContent = info.path;
  pathEl.title = info.path;
  bytesEl.textContent = info.bytes ? `${fmtSize(info.bytes)}` : "还没写过东西";
}

document.getElementById("btn-log-open").addEventListener("click", async () => {
  const ok = await call("diag_reveal");
  if (ok === null || ok === undefined) return; // 失败原因 call 里已经 toast 过
  toast("已在文件管理器里定位日志文件");
});

document.getElementById("btn-log-copy").addEventListener("click", async () => {
  const info = await call("diag_info");
  const tail = await call("diag_tail", { lines: 20 });
  if (!info) return;
  const ver = document.querySelector(".titlebar .brand .ver")?.textContent || "?";
  const head = [
    `Portio ${ver}`,
    `日志：${info.path}（${info.bytes} 字节）`,
    `屏幕：${screen.width}×${screen.height} @${window.devicePixelRatio}x · 窗口 ${innerWidth}×${innerHeight}`,
    `系统：${navigator.userAgent}`,
  ].join("\n");
  copyText(`${head}\n\n最近日志：\n${tail || "(空)"}`);
});

// ---------- 可拖拽尺寸：三处，记忆层 ----------
// 每个尺寸拆两半：setX 只改界面，applyX 改界面 + 落盘（给用户手拖用）。
// 拆的理由跟面板收放那次一样——开机按「打开时」偏好落尺寸时，不许顺手把记忆层改写掉；
// 否则「用默认」开一次，上次拖出来的宽度就没了。
const PREF = {
  sidebar: { key: "portio.sidebar", min: 180, max: 420 },
  split: { key: "portio.split", min: 0.32, max: 0.66 },
  // 抽屉的最小高度就是一行标题条：收起时只剩「传输队列 0 … 展开」这一行
  drawer: { key: "portio.drawer", min: 28, max: 360 },
};
const DEFAULT_DRAWER = 172;

function readNum(key, fallback) {
  const raw = localStorage.getItem(key);
  const n = raw === null ? NaN : Number(raw);
  return Number.isFinite(n) ? n : fallback;
}

// 侧栏宽度
function setSidebarUI(px) {
  root.style.setProperty("--sidebar", `${Math.round(px)}px`);
}
function applySidebar(px) {
  setSidebarUI(px);
  localStorage.setItem(PREF.sidebar.key, String(Math.round(px)));
}
// 终端:文件比例
function setSplitUI(ratio) {
  root.style.setProperty("--split", `${(ratio * 100).toFixed(2)}%`);
}
function applySplit(ratio) {
  setSplitUI(ratio);
  localStorage.setItem(PREF.split.key, ratio.toFixed(4));
}
function clampSplit(ratio) {
  return Math.min(PREF.split.max, Math.max(PREF.split.min, ratio));
}
// 抽屉高度
let drawerLast = DEFAULT_DRAWER;
function setDrawerUI(px) {
  const h = Math.round(px);
  root.style.setProperty("--drawer", `${h}px`);
  // 收到一行高就算"收起"：正文整块隐藏，别在标题条下面留半指宽的空白
  const collapsed = h <= PREF.drawer.min + 2;
  document.getElementById("drawer").classList.toggle("collapsed", collapsed);
  const head = document.getElementById("drawer-head");
  if (head) head.querySelector(".right").textContent = collapsed ? "展开" : "收起";
  // 抽屉一变，终端可用高度跟着变，量一次尺寸
  requestAnimationFrame(() => fitQuietly());
}
function applyDrawer(px) {
  setDrawerUI(px);
  localStorage.setItem(PREF.drawer.key, String(Math.round(px)));
}
// 侧栏宽度该用哪个：记住上次 → 记忆层；用默认 → 默认档。折叠态不归它管（setFoldUI 自己归零）。
function layoutWidth() {
  return readLayoutMode() === "default" ? readDefWidth() : readNum(PREF.sidebar.key, readDefWidth());
}
// 开机落一次三处尺寸：只动界面、不写盘，记忆层原样留着
function applyBootLayout() {
  const useDefault = readLayoutMode() === "default";
  if (!sidebarFolded) setSidebarUI(useDefault ? readDefWidth() : readNum(PREF.sidebar.key, readDefWidth()));
  setSplitUI(useDefault ? 0.5 : clampSplit(readNum(PREF.split.key, 0.5)));
  setDrawerUI(useDefault ? DEFAULT_DRAWER : readNum(PREF.drawer.key, DEFAULT_DRAWER));
}

// 把手不再按像素贴边：位置由栅格与 CSS 的 calc() 决定（见 index.html 的 .main/.split/.gutter-h），
// 窗口缩放、栅格夹取都不会错位。这里只保留拖拽起止与尺寸落盘。
const mainEl = document.getElementById("main");
const splitEl = document.getElementById("split");
const stageEl = document.querySelector(".stage");

// 通用拖拽：按轴更新，松手落盘。拖拽期间给把手加 .dragging，胶囊把手变长变实。
function dragWith(axis, onMove) {
  return (e) => {
    e.preventDefault();
    const handle = e.currentTarget;
    if (handle && handle.classList) handle.classList.add("dragging");
    document.body.classList.add(axis === "x" ? "dragging" : "dragging-x");
    const move = (ev) => onMove(ev);
    const up = () => {
      document.body.classList.remove("dragging", "dragging-x");
      if (handle && handle.classList) handle.classList.remove("dragging");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
}

// ---------- 启动默认布局：三档怎么落到折叠态（具体读写见 syncSegs 之前那一块） ----------
// 会话栏折叠：收起后整块让给终端，只留一条把手；鼠标移上去箭头才亮
const FOLD_KEY = "portio.sidebarFolded";
let sidebarFolded = localStorage.getItem(FOLD_KEY) === "1";
// 只改界面，不落盘：启动时按「启动时」偏好强行展开/收起，不能借此改掉记忆态
function setFoldUI(folded) {
  sidebarFolded = folded;
  mainEl.classList.toggle("collapsed", folded);
  document.getElementById("gutter-v").classList.toggle("folded", folded);
  if (folded) {
    root.style.setProperty("--sidebar", "0px");
  } else {
    setSidebarUI(layoutWidth());
  }
  // 折叠展开改变了终端可用宽度，布局稳定后再 fit 一次，否则列数不对
  requestAnimationFrame(() => fitQuietly());
}
function applyFold(folded) {
  setFoldUI(folded);
  localStorage.setItem(FOLD_KEY, folded ? "1" : "0");
}
function applyBootSide() {
  setFoldUI(bootFold(readBoot(BOOT_SIDE_KEY), localStorage.getItem(FOLD_KEY) === "1"));
}

document.getElementById("gutter-v").addEventListener("pointerdown", dragWith("x", (ev) => {
  if (sidebarFolded) return; // 折叠态下的拖拽不调宽，交给 click 去展开
  const left = mainEl.getBoundingClientRect().left;
  const px = Math.min(PREF.sidebar.max, Math.max(PREF.sidebar.min, ev.clientX - left));
  applySidebar(px);
}));

// 折叠态：单击把手展开；展开态：双击把手收起（拖拽不会误触发 dblclick）
document.getElementById("gutter-v").addEventListener("click", () => {
  if (sidebarFolded) applyFold(false);
});

// 文件面板折叠：整块收掉，终端铺满，右缘留一条把手（与会话栏折叠同一套做法）
// 入口是终端标题条上那颗常驻按钮——文件面板收起来之后它自己没了，只能靠它再打开。
const FFOLD_KEY = "portio.filesFolded";
let filesFolded = localStorage.getItem(FFOLD_KEY) === "1";
// 同样拆成"只改界面"与"改界面 + 落盘"两半，启动时的强行展开/收起不许改记忆态
function setFilesFoldUI(folded) {
  filesFolded = folded;
  splitEl.classList.toggle("files-folded", folded);
  const btn = document.getElementById("files-fold");
  if (btn) {
    btn.setAttribute("aria-label", folded ? "展开文件面板" : "折叠文件面板");
    btn.setAttribute("title", folded ? "展开文件面板（Ctrl+Alt+F）" : "折叠文件面板（Ctrl+Alt+F）");
    btn.setAttribute("aria-pressed", folded ? "true" : "false");
  }
  // 折叠态右缘把手的提示语要跟着变：这时候它不是"拖比例"，是"点一下拉回来"
  const gut = document.getElementById("gutter-split");
  if (gut) gut.title = folded ? "点击展开文件面板" : "拖动调整终端与文件面板比例";
  // 终端宽度变了，等一帧让网格落定再量，否则列数按旧宽度算
  requestAnimationFrame(() => fitQuietly());
}
function applyFilesFold(folded) {
  setFilesFoldUI(folded);
  localStorage.setItem(FFOLD_KEY, folded ? "1" : "0");
}
function applyBootFiles() {
  setFilesFoldUI(bootFold(readBoot(BOOT_FILES_KEY), localStorage.getItem(FFOLD_KEY) === "1"));
}

document.getElementById("files-fold").addEventListener("click", () => applyFilesFold(!filesFolded));

// 折叠态：单击右缘把手把文件面板拉回来；展开态：双击把手把文件面板收起来
// （与会话栏把手同一套手势，不再双击回 50% 比例）
document.getElementById("gutter-split").addEventListener("click", () => {
  if (filesFolded) applyFilesFold(false);
});

document.getElementById("gutter-split").addEventListener("pointerdown", dragWith("x", (ev) => {
  if (filesFolded) return; // 折叠态的把手只用来展开，不调比例
  const box = splitEl.getBoundingClientRect();
  const ratio = (ev.clientX - box.left) / box.width;
  applySplit(Math.min(PREF.split.max, Math.max(PREF.split.min, ratio)));
}));

document.getElementById("gutter-drawer").addEventListener("pointerdown", dragWith("y", (ev) => {
  const box = stageEl.getBoundingClientRect();
  const px = Math.min(PREF.drawer.max, Math.max(PREF.drawer.min, box.bottom - ev.clientY));
  applyDrawer(px);
}));

// 抽屉：点标题栏折叠/展开，比拖拽更常用。原来 `drawerLast` 声明在下面，这里先挪上来。
document.getElementById("drawer-head").addEventListener("click", () => {
  const cur = parseFloat(getComputedStyle(root).getPropertyValue("--drawer")) || 172;
  if (cur > PREF.drawer.min + 2) {
    drawerLast = cur;
    applyDrawer(PREF.drawer.min);
  } else {
    applyDrawer(Math.max(drawerLast, 120));
  }
});

// 两条把手同一套手势：双击把手收起这一侧；收起后单击贴边把手还原（Ctrl+Alt+B / Ctrl+Alt+F 同效）
document.getElementById("gutter-v").addEventListener("dblclick", () => {
  if (!sidebarFolded) applyFold(true);
});
document.getElementById("gutter-split").addEventListener("dblclick", () => {
  if (!filesFolded) applyFilesFold(true);
});

// ---------- 快捷键 ----------
window.addEventListener("keydown", (e) => {
  const mod = e.ctrlKey && e.altKey;
  if (mod && e.key.toLowerCase() === "h") {
    e.preventDefault();
    windowAction("fullscreen");
    toast("全屏切换（Ctrl+Alt+H）");
  }
  if (mod && e.key.toLowerCase() === "b") {
    e.preventDefault();
    applyFold(!sidebarFolded);
    toast(sidebarFolded ? "会话栏已收起（Ctrl+Alt+B 恢复）" : "会话栏已展开");
  }
  if (mod && e.key.toLowerCase() === "f") {
    e.preventDefault();
    applyFilesFold(!filesFolded);
    toast(filesFolded ? "文件面板已收起（Ctrl+Alt+F 恢复）" : "文件面板已展开");
  }
  if (e.ctrlKey && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "w") {
    e.preventDefault();
    if (tabs.length <= 1) return toast("只剩一个标签了，再关就空窗口");
    closeTab(activeId);
  }
  // 分屏：Ctrl+Shift+D 左右分（竖线），Ctrl+Shift+E 上下分（横线）。
  // 顺手照顾中文输入法与"大写字母"的两种 key 写法（D / d、E / e）
  if (e.ctrlKey && e.shiftKey && !e.altKey && ["d", "e"].includes(e.key.toLowerCase())) {
    e.preventDefault();
    const tab = activeTab();
    if (!tab) return;
    splitTab(tab, e.key.toLowerCase() === "d" ? "v" : "h");
    const n = tab.cells.length;
    toast(n ? `已分成 ${n} 格（Ctrl+Shift+W 关掉当前格）` : "分屏失败");
    return;
  }
  // 关当前格（只关一格，不关标签）；只有一格时提示改用 Ctrl+W
  if (e.ctrlKey && e.shiftKey && !e.altKey && e.key.toLowerCase() === "w") {
    e.preventDefault();
    const tab = activeTab();
    if (!tab) return;
    if (tab.cells.length < 2) return toast("只有一格，关标签用 Ctrl+W");
    closeCell(tab, tab.cell);
    toast(tab.cells.length === 1 ? "已回到单格" : `还剩 ${tab.cells.length} 格`);
    return;
  }
  if (e.ctrlKey && !e.altKey && e.key.toLowerCase() === "f") {
    e.preventDefault();
    findToggle(true);
  }
  if (e.key === "F5") {
    e.preventDefault();
    // 重绘而不是重连：清掉 xterm 的渲染缓存，尺寸也跟着重新量一次
    if (term) {
      term.refresh(0, term.rows - 1);
      fitQuietly();
      toast("终端已重绘");
    }
  }
});

// ---------- 终端查找（Ctrl+F） ----------
// 不引 xterm 的 search addon：用公共 API 扫 buffer，命中那条用 select() 高亮、scrollToLine() 跳过去。
// 扫的是 buffer 文本而不是可视区，所以滚进滚动缓冲的旧行一样找得到。
const findBar = document.getElementById("find");
const findInput = document.getElementById("find-q");
const findCount = document.getElementById("find-n");
const findHits = { q: "", all: [], at: -1, term: null };
let findTimer = 0;

// 终端把一条长命令折成两行时，逐行扫就永远搜不到跨折点的那半截——用户看到的是"明明有，搜不到"。
// 所以先按 isWrapped 把连续几行拼成一条"逻辑行"再扫，命中再映射回 (行, 格)；跨折行的命中
// 记一个按格累加的长度，select() 自己会绕过折行把它整段选上。
// 一行的"实际有字"长度：末尾补位的空白不算内容。有的 xterm 版本给了 getTrimmedLength，
// 手上这个没有，就自己从后往前数——末行若把补位空白也当内容，查询词会凭空跨过一片空气拼上。
function findTrimmed(line) {
  if (typeof line.getTrimmedLength === "function") return line.getTrimmedLength();
  let n = line.length;
  while (n > 0) {
    const cell = line.getCell(n - 1);
    const s = cell ? cell.getChars() : "";
    const blank = !s || s === " " || (typeof cell?.getCode === "function" && cell.getCode() === 0);
    if (!blank) return n;
    n -= 1;
  }
  return n;
}

function findGroups(buf) {
  const groups = [];
  let group = null;
  for (let row = 0; row < buf.length; row += 1) {
    const line = buf.getLine(row);
    if (!line) {
      group = null;
      continue;
    }
    if (line.isWrapped && group) group.rows.push({ row, line });
    else {
      group = { rows: [{ row, line }] };
      groups.push(group);
    }
  }
  return groups;
}

function findScan(q) {
  const all = [];
  if (!term || !q) return all;
  const buf = term.buffer.active;
  const needle = q.toLowerCase();
  for (const group of findGroups(buf)) {
    const last = group.rows.length - 1;
    // 快路：先按行拼一遍文本（末行去掉补位空白），扫不到就直接跳过，不建逐格映射。
    const quick = group.rows.map(({ line }, i) => line.translateToString(i === last));
    if (quick.join("").toLowerCase().indexOf(needle) === -1) continue;

    // 慢路：逐格建映射。translateToString 给的是"字符下标"，而 select() 要的是"格号"：
    // 宽字符占两格却只出一个字符，一行里只要有中文，字符下标就会比格号小。
    const chars = [];
    const where = [];
    group.rows.forEach(({ row, line }, i) => {
      const upto = i === last ? findTrimmed(line) : line.length;
      for (let c = 0; c < upto; c += 1) {
        const cell = line.getCell(c);
        if (!cell) continue;
        const s = cell.getChars() || " ";
        for (let k = 0; k < s.length; k += 1) {
          chars.push(s[k]);
          where.push({ row, col: c });
        }
      }
    });
    const hay = chars.join("").toLowerCase();
    let at = hay.indexOf(needle);
    while (at !== -1) {
      const from = where[at];
      const to = where[at + needle.length - 1];
      let span;
      if (to.row === from.row) {
        span = to.col - from.col + 1;
      } else {
        // 跨折行：从起点到本行末 + 中间整行 + 末行到终点，全按格算
        span = 0;
        for (const { row, line } of group.rows) {
          if (row < from.row) continue;
          if (row > to.row) break;
          if (row === from.row) span += line.length - from.col;
          else if (row === to.row) span += to.col + 1;
          else span += line.length;
        }
      }
      all.push({ row: from.row, col: from.col, span });
      at = hay.indexOf(needle, at + needle.length);
    }
  }
  return all;
}

function findPaint() {
  const n = findHits.all.length;
  findCount.textContent = n ? `${findHits.at + 1}/${n}` : "0/0";
  findCount.classList.toggle("bad", !!findHits.q && n === 0);
}

// 命中序号怎么走：首跳从 -1 出发，往后 +1 落到第一条、往前 -1 落到最后一条，其余按环回绕。
// 抽成纯函数是为了能不依赖 xterm 单独验（见 autopilot-log 里那条单测）。
function findStep(n, at, delta) {
  if (!n) return -1;
  if (at < 0) return delta > 0 ? 0 : n - 1;
  return (at + delta + n) % n;
}

function findJump(delta) {
  const n = findHits.all.length;
  if (!n) {
    findPaint();
    return;
  }
  findHits.at = findStep(n, findHits.at, delta);
  const hit = findHits.all[findHits.at];
  // span 是按格算的跨折行长度；老条目没有这个字段时退回"查询词长度"（单行情形两者该相等）
  term.select(hit.col, hit.row, hit.span ?? findHits.q.length);
  term.scrollToLine(Math.max(0, hit.row - Math.floor(term.rows / 2)));
  findPaint();
}

function findRefresh() {
  findHits.q = findInput.value;
  // 记下这次扫的是哪一格：分屏之后换格要能认出"命中不属于当前这个 buffer"
  findHits.term = term ?? null;
  findHits.all = findScan(findHits.q);
  findHits.at = -1;
  if (term) term.clearSelection();
  if (findHits.all.length) findJump(1);
  else findPaint();
}

function findToggle(open) {
  const want = open ?? findBar.hidden;
  clearTimeout(findTimer);
  if (want) {
    if (!findBar.hidden) {
      findInput.select();
      return;
    }
    findBar.hidden = false;
    requestAnimationFrame(() => findBar.classList.add("open"));
    findInput.focus();
    findInput.select();
    findRefresh();
  } else {
    findBar.classList.remove("open");
    // 等淡出跑完再真隐藏，避免"啪"一下消失
    findTimer = setTimeout(() => { findBar.hidden = true; }, 240);
    if (term) {
      term.clearSelection();
      term.focus();
    }
    findHits.at = -1;
  }
}

findInput.addEventListener("input", findRefresh);
findInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    findJump(e.shiftKey ? -1 : 1);
  } else if (e.key === "Escape") {
    e.preventDefault();
    findToggle(false);
  }
});
document.getElementById("find-prev").addEventListener("click", () => findJump(-1));
document.getElementById("find-next").addEventListener("click", () => findJump(1));
document.getElementById("find-x").addEventListener("click", () => findToggle(false));

function 初次提示() {}

// ---------- 启动：恢复用户上次调好的尺寸 ----------
applyTheme(localStorage.getItem("portio.theme") ?? "dark");
// #theme-light / #theme-dark：截图核验主题图标时直接锁定主题，不用靠点按钮
if (location.hash === "#theme-light") applyTheme("light");
if (location.hash === "#theme-dark") applyTheme("dark");
applyDensity(localStorage.getItem("portio.density") ?? "standard");
applyAccent(readAccent());
applyTerm(readTerm());
applyUiFont(readUiFont());
applyMono(readMono());
applyPerm(readPerm());
// 尺寸这一层：先按「启动时」定两块面板的收放（展开时会顺手把该用的宽度落上去），
// 再按「打开时」那一档落三处尺寸。两步都只动界面，记忆层一个字都不改。
applyBootSide();
applyBootLayout();
applyBootFiles();

// 核验用：把两处「启动时」摆出来给截图看（#boot-demo / #boot-demo-light）——
// 会话栏设成「总是收起」、文件面板设成「总是展开」，再按启动那一刻的口径落一遍，
// 所以画面里会话栏已经让位、右侧文件面板还在。这句放在尺寸恢复之后，
// 因为 setFoldUI / setFilesFoldUI 要碰 mainEl / splitEl（它们在更早的段落里才初始化）。
if (location.hash === "#boot-demo" || location.hash === "#boot-demo-light") {
  applyBootMode(BOOT_SIDE_KEY, "folded");
  applyBootMode(BOOT_FILES_KEY, "open");
  applyBootSide();
  applyBootFiles();
  if (location.hash === "#boot-demo-light") applyTheme("light");
  toggleSettings(true);
}

// 核验用：把权限列藏起来的样子摆出来（#perm-demo / #perm-demo-light 看文件面板本身，
// #perm-demo-set 额外把设置面板也打开看那两档）。无头页没有后端，文件面板里只有一行
// "空目录"提示，所以塞两条真行进去才看得出列怎么挪的。
if (location.hash === "#perm-demo" || location.hash === "#perm-demo-light" || location.hash === "#perm-demo-set") {
  const fakeRemote = [
    ["▸", "dir", "release-notes-v0.4-draft", "drwxr-xr-x", "—", "2026-11-20 09:12"],
    ["·", "", "portio_1.0.7-RC5_x64-setup.exe", "-rw-rw-r--", "4.36 MB", "2026-11-20 09:12"],
  ];
  const fakeLocal = [
    ["·", "", "portio-installer-notes.md", "6.2 KB", "2026-11-20 09:12"],
  ];
  const fill = (host, rows, perm) => {
    if (!host) return;
    host.textContent = "";
    for (const r of rows) {
      const row = document.createElement("div");
      row.className = `fp-row${r[1] ? " " + r[1] : ""}${perm ? " has-perm" : ""}`;
      row.innerHTML =
        `<span class="ico">${r[0]}</span><span class="nm">${r[2]}</span>` +
        (perm ? `<span class="pm">${r[3]}</span>` : "") +
        `<span class="sz">${perm ? r[4] : r[3]}</span><span class="tm">${perm ? r[5] : r[4]}</span>`;
      host.append(row);
    }
  };
  fill(document.getElementById("remote-list"), fakeRemote, true);
  fill(document.getElementById("local-list"), fakeLocal, false);
  applyPerm("hide");
  if (location.hash === "#perm-demo-light") applyTheme("light");
  if (location.hash === "#perm-demo-set") toggleSettings(true);
}


// ---------- 尽快把窗口放出来 ----------
// 窗口在 tauri.conf.json 里是 visible:false：主题和尺寸都恢复好之后再 show，
// 用户看到的第一帧就是画好的界面，不会先闪一块空底色。
// 放在终端初始化之前调用——xterm 那一段最费时间，没必要等它。
function revealWindow() {
  if (!bridge || revealWindow.done) return;
  revealWindow.done = true;
  bridge.invoke("window_ready", {}).catch(() => {
    /* 显示失败也别把界面卡住，用户还能从任务栏点出来 */
  });
}
requestAnimationFrame(() => requestAnimationFrame(revealWindow));
// 兜底：万一前面有异常把 rAF 链断了，1.2 秒后无论如何也把窗口放出来
setTimeout(revealWindow, 1200);

// 状态栏时钟，避免状态栏全是死文本
const clock = document.getElementById("clock");
function tick() {
  const d = new Date();
  clock.textContent = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
tick();
setInterval(tick, 30_000);

// ---------- 终端 ----------
// ---------- 终端与标签 ----------
// 每个标签一个独立 xterm 实例，各自一个 SSH 会话；切换标签只是切换可见容器，
// 后台标签的会话仍在跑（这是 Xshell / 浏览器标签的共同习惯）。
const termHost = document.getElementById("term");
const tabsBox = document.getElementById("tabs");
var tabs = [];
let activeId = null;
let tabSeq = 0;
let cellSeq = 0; // 分屏格子的自增号，只用来给 DOM 打标记，不参与逻辑
// term / fitAddon 已在文件顶部声明（那里要避免 TDZ），这里只做"指向当前标签"
let sessionId = null;

// 终端配色也来自 tokens.css：这里只读令牌，不再写死色值（改配色去改令牌，别改这里）
function cssToken(name) {
  const v = getComputedStyle(root).getPropertyValue(name).trim();
  return v;
}
function terminalTheme() {
  return {
    background: cssToken("--term-bg"),
    foreground: cssToken("--term-fg"),
    cursor: cssToken("--term-cursor"),
    selectionBackground: cssToken("--term-selection"),
    black: cssToken("--ansi-black"),
    red: cssToken("--ansi-red"),
    green: cssToken("--ansi-green"),
    yellow: cssToken("--ansi-yellow"),
    blue: cssToken("--ansi-blue"),
    magenta: cssToken("--ansi-magenta"),
    cyan: cssToken("--ansi-cyan"),
    white: cssToken("--ansi-white"),
  };
}

// 分屏后一个标签里有好几格，每格都要按自己的格子尺寸重算 cols/rows；
// 隐藏标签里的格子等切回去时由 activateTab 再量。
function fitQuietly() {
  const tab = activeTab();
  const cells = tab ? tab.cells : [];
  for (const c of cells) {
    try {
      c.fit.fit();
    } catch (e) {
      // 容器还没布局完时 fit 会抛，这里吞掉即可，ResizeObserver 稍后会再来一次
    }
  }
  if (!cells.length && fitAddon) {
    try {
      fitAddon.fit();
    } catch (e) {
      /* 同上 */
    }
  }
}

function tabById(id) {
  return tabs.find((t) => t.id === id) ?? null;
}
function activeTab() {
  return tabById(activeId);
}
// 分屏后"当前终端"是某个标签里的某一格；这层间接让 sftp / 查找条这类只管当前格的功能不用改太多
function activeCell() {
  const tab = activeTab();
  return tab ? tab.cell : null;
}
function cellBySid(sid) {
  for (const t of tabs) for (const c of t.cells) if (c.sid === sid) return c;
  return null;
}

function renderTabs() {
  tabsBox.textContent = "";
  for (const t of tabs) {
    const el = document.createElement("div");
    el.className = "tab" + (t.id === activeId ? " active" : "");
    el.title = t.title;
    const dot = document.createElement("span");
    dot.className = "dot";
    if (t.cells.some((c) => c.sid !== null)) dot.style.background = "var(--accent)";
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = t.title;
    el.append(dot, name);
    // 只剩一个标签时不给关闭按钮，避免误关成空窗口
    if (tabs.length > 1) {
      const x = document.createElement("span");
      x.className = "x";
      x.textContent = "×";
      x.title = "关闭标签";
      x.addEventListener("click", (ev) => {
        ev.stopPropagation();
        closeTab(t.id);
      });
      el.append(x);
    }
    el.addEventListener("click", () => activateTab(t.id));
    // 标签右键：关掉这一个、关掉其它的、复制标题
    el.addEventListener("contextmenu", (ev) => {
      ev.preventDefault();
      showCtx(ev.clientX, ev.clientY, [
        { label: "关闭", hint: "Ctrl+W", run: () => closeTab(t.id) },
        {
          label: "关闭其它标签",
          hint: `${tabs.length - 1} 个`,
          disabled: tabs.length < 2,
          run: () => {
            for (const other of [...tabs]) if (other.id !== t.id) closeTab(other.id);
            activateTab(t.id);
          },
        },
        { sep: true },
        { label: "复制标题", run: () => copyText(t.title) },
      ]);
    });
    tabsBox.append(el);
  }
}

function activateTab(id) {
  const tab = tabById(id);
  if (!tab) return;
  activeId = id;
  for (const t of tabs) t.stage.classList.toggle("on", t.id === id);
  syncActiveCell(tab);
  // 切标签就收起查找条：命中的行号属于上一个标签的 buffer，留着会指错地方
  if (findBar && !findBar.hidden) findToggle(false);
  renderTabs();
  // 容器刚变可见，等一帧再量尺寸，否则 cols/rows 会算成 0
  setTimeout(() => {
    fitQuietly();
    if (tab.cell) tab.cell.term.focus();
  }, 0);
}

// 标题条右侧那串 80×24 是当前格的实时尺寸：分屏后每格列数不同，写死会骗人
function updateDims() {
  const el = document.getElementById("term-dims");
  if (el && term) el.textContent = `${term.cols}×${term.rows}`;
}

// 把"当前终端"三个全局变量指到标签里的当前格，并标出焦点框
function syncActiveCell(tab) {
  const cell = tab.cell;
  if (!cell) return;
  term = cell.term;
  fitAddon = cell.fit;
  sessionId = cell.sid;
  for (const c of tab.cells) c.el.classList.toggle("focus", c === cell);
  updateDims();
}

// 一格里放一套终端：自己一个 xterm 实例、自己的 fit、自己的会话 id
function makeCell(tab, sid = null) {
  const cellId = ++cellSeq;
  const el = document.createElement("div");
  el.className = "term-cell";
  el.dataset.cell = String(cellId);
  tab.grid.appendChild(el);
  const t = new Terminal({
    fontFamily: termFont(),
    fontSize: readFontSize(),
    lineHeight: 1.25,
    cursorBlink: true,
    scrollback: readScrollback(),
    theme: terminalTheme(),
    allowProposedApi: true,
  });
  const fit = new FitAddon.FitAddon();
  t.loadAddon(fit);
  t.open(el);
  const cell = { id: cellId, el, term: t, fit, sid, tab };
  tab.cells.push(cell);
  // Ctrl+F 归查找条；复制 / 粘贴按键统一走 clipboardAction（纯函数，见文件末尾，供 #clip-test 自检）。
  // 注意：这个 handler 依赖 cell，必须等 cell 建好再挂。
  t.attachCustomKeyEventHandler((ev) => {
    if (ev.type !== "keydown") return true;
    if (ev.ctrlKey && !ev.altKey && ev.key.toLowerCase() === "f") return false;
    const act = clipboardAction(
      { ctrl: ev.ctrlKey, shift: ev.shiftKey, alt: ev.altKey, key: ev.key },
      t.hasSelection()
    );
    if (act === "copy") {
      copySelection(cell);
      return false;
    }
    if (act === "paste") {
      pasteInto(cell);
      return false;
    }
    return true;
  });
  // 回调绑定到自己的格子，避免后台格子的输入发到别的会话
  t.onData((data) => {
    if (cell.sid !== null) call("ssh_input", { id: cell.sid, data });
  });
  t.onResize(({ cols, rows }) => {
    if (cell.sid !== null) call("ssh_resize", { id: cell.sid, cols, rows });
    if (cell.tab.cell === cell) updateDims();
  });
  // 点一下就把焦点挪到这格（多格的时候必须能看见自己正在敲哪一格）
  el.addEventListener("mousedown", () => setActiveCell(tab, cell));
  // 终端右键：复制、粘贴、清屏——鼠标党不用记 Ctrl+Shift+V 也能干活
  el.addEventListener("contextmenu", (ev) => {
    ev.preventDefault();
    setActiveCell(tab, cell);
    const picked = t.getSelection();
    showCtx(ev.clientX, ev.clientY, [
      {
        label: "复制选中",
        hint: picked ? "Ctrl+Shift+C" : "无选中",
        disabled: !picked,
        run: () => copySelection(cell),
      },
      { label: "粘贴", hint: "Ctrl+V", run: () => pasteInto(cell) },
      { label: "全选", hint: "Ctrl+A", run: () => t.selectAll() },
      { sep: true },
      { label: "清屏", hint: "Ctrl+L", run: () => sendRaw(cell, "\f") },
      { label: "清空滚动缓冲", run: () => t.clear() },
      { sep: true },
      {
        label: "竖分一格",
        hint: "Ctrl+Shift+D",
        disabled: !canSplit(tab, "v"),
        run: () => splitTab(tab, "v"),
      },
      {
        label: "横分一格",
        hint: "Ctrl+Shift+E",
        disabled: !canSplit(tab, "h"),
        run: () => splitTab(tab, "h"),
      },
      {
        label: "关闭这一格",
        hint: "Ctrl+Shift+W",
        disabled: tab.cells.length < 2,
        run: () => closeCell(tab, cell),
      },
    ]);
  });
  return cell;
}

function setActiveCell(tab, cell) {
  if (!tab.cells.includes(cell)) return;
  tab.cell = cell;
  if (tab.id === activeId) syncActiveCell(tab);
  // 查找条开着的时候换格：那些命中行号属于上一格的 buffer，不重扫就会在**这一格**的错行上高亮，
  // 计数也还是上一格的（用户看到"有计数、地方不对"）。重扫一遍，顺手把上一格的高亮收掉。
  if (findBar && !findBar.hidden && findHits.term !== term) {
    if (findHits.term) findHits.term.clearSelection();
    if (findHits.q) findRefresh();
    else findHits.term = null;
  }
  cell.term.focus();
}

// 格子数只走 1 → 2 → 4 三档：分一次变两格，再分一次直接补满四格。
// 不做 3 格是因为网格里会留一个空洞（2×2 只放三格），比"少一格"更难看。
function canSplit(tab) {
  return tab.cells.length < 4;
}
function applyGrid(tab) {
  const g = tab.gridTemplate;
  tab.grid.style.gridTemplateColumns = `repeat(${g.cols}, minmax(0, 1fr))`;
  tab.grid.style.gridTemplateRows = `repeat(${g.rows}, minmax(0, 1fr))`;
  const n = tab.cells.length;
  tab.grid.classList.toggle("multi", n > 1);
  // 三格时第一格纵向占满左列，否则 2×2 网格里会空出一个洞
  tab.grid.classList.toggle("tri", n === 3);
}
function splitTab(tab, dir) {
  if (!canSplit(tab)) return toast("最多四格；要更多终端就开新标签");
  const before = tab.cells.length;
  // 两格再分一次 = 补满四格；一格时按方向决定是左右还是上下
  const target = before === 1 ? 2 : 4;
  tab.gridTemplate =
    before === 1 ? { cols: dir === "v" ? 2 : 1, rows: dir === "v" ? 1 : 2 } : { cols: 2, rows: 2 };
  applyGrid(tab);
  const fresh = [];
  while (tab.cells.length < target) fresh.push(makeCell(tab));
  applyGrid(tab);
  const last = fresh[fresh.length - 1] ?? null;
  setActiveCell(tab, last);
  // 新建的格子刚 open 时尺寸还是 0，这时候写进去的字会被终端丢掉；
  // 等一帧、量完尺寸再写，字一定落得上。
  requestAnimationFrame(() => {
    fitQuietly();
    for (const c of fresh) {
      if (tab.spec) continue; // 连主机的格子等通道建好再写自己的横幅
      c.term.write("\x1b[2m—— 新的一格（本地，未连接）——\x1b[0m\r\n");
    }
  });
  // 已连接的标签里新开格子：每格一条通道，不能两格抢同一个 PTY（两边会互相抢输入）
  if (tab.spec) for (const c of fresh) openCellChannel(tab, c);
  return last;
}

// 给分屏出来的格子单独建一条 SSH 通道：口令只能从加密凭据里取（不弹第二个密码框）
async function openCellChannel(tab, cell) {
  if (!bridge || !tab.spec) return;
  const spec = tab.spec;
  const key = credKey(spec.user, spec.host, spec.port);
  let password = null;
  if (spec.auth === "password") {
    password = await credPeek(key);
    if (!password) {
      cell.term.write(
        "\x1b[33m这格没能连上：本机没存这台主机的口令。\x1b[0m\r\n" +
          "先在主格重新连一次并勾上「记住口令」，之后分屏出来的格子会自动接上。\r\n"
      );
      return;
    }
  }
  try {
    // 握手回调用的 Channel 必须真给一个：Tauri 按通道 ID 反序列化参数，
    // 传 null 会让整条命令在参数校验阶段就被拒，这一格必然连不上。
    // 分屏格子不显示指纹提示，回调留空操作即可。
    const handoff = new window.__TAURI__.core.Channel();
    handoff.onmessage = () => {};
    const id = await bridge.invoke("ssh_connect", {
      host: spec.host,
      port: Number(spec.port ?? 22) || 22,
      user: spec.user,
      password,
      keyfile: spec.auth === "key" ? String(spec.keyfile ?? "") : null,
      cols: cell.term.cols,
      rows: cell.term.rows,
      onHandshake: handoff,
    });
    cell.sid = id;
    cell.term.write(`\r\n\x1b[2m—— 新的一格：${spec.user}@${spec.host}:${spec.port} ——\x1b[0m\r\n`);
    renderTabs();
    if (tab.id === activeId) sessionId = tab.cell.sid;
  } catch (err) {
    const raw = String(err);
    cell.term.write(
      `\r\n\x1b[31m这格连不上：${raw.includes("HOSTKEY_CHANGED") ? "主机指纹变了，去设置里确认后再连" : explainError("ssh_connect", raw)}\x1b[0m\r\n`
    );
  }
}

function closeCell(tab, cell) {
  if (tab.cells.length < 2) return;
  const idx = tab.cells.indexOf(cell);
  if (idx < 0) return;
  if (cell.sid !== null) call("ssh_disconnect", { id: cell.sid });
  cell.term.dispose();
  cell.el.remove();
  tab.cells.splice(idx, 1);
  // 关完按剩下的格数重排：1 格回单屏、2 格左右并排、3 格回到"左高右两格"
  const n = tab.cells.length;
  tab.gridTemplate = n === 1 ? { cols: 1, rows: 1 } : n === 2 ? { cols: 2, rows: 1 } : { cols: 2, rows: 2 };
  const next = tab.cells[Math.min(idx, tab.cells.length - 1)];
  tab.cell = next;
  applyGrid(tab);
  if (tab.id === activeId) syncActiveCell(tab);
  requestAnimationFrame(() => {
    fitQuietly();
    next.term.focus();
  });
}

function createTab(title, sid = null) {
  const id = ++tabSeq;
  const stage = document.createElement("div");
  stage.className = "term-pane";
  stage.dataset.id = String(id);
  const grid = document.createElement("div");
  grid.className = "panes-grid";
  stage.appendChild(grid);
  termHost.insertBefore(stage, findBar ?? null);
  const tab = {
    id,
    title,
    stage,
    grid,
    gridTemplate: { cols: 1, rows: 1 },
    cells: [],
    cell: null,
    spec: null, // 怎么连的（分屏时要用同一套参数再建一条通道）
  };
  tabs.push(tab);
  tab.cell = makeCell(tab, sid);
  applyGrid(tab);
  activateTab(id);
  return tab;
}

// 往会话里塞原始控制字符：本地格子没有会话，就写到终端自己身上
function sendRaw(cell, data) {
  if (cell.sid !== null) call("ssh_input", { id: cell.sid, data });
  else cell.term.write(data.replace("\f", ""));
}

// 键盘 → 剪贴板动作的映射。纯函数，`#clip-test` 直接用它做自检，不靠模拟键盘事件。
// 返回 "copy" / "paste" / null（null = 不拦，按键照常发给远端）
function clipboardAction(mods, hasSelection) {
  if (mods.alt) return null; // Ctrl+Alt+X 留给应用快捷键（全屏 / 折叠面板等）
  const k = String(mods.key || "").toLowerCase();
  if (mods.ctrl && mods.shift && k === "c") return "copy"; // Xshell / PuTTY 的显式复制
  if (mods.ctrl && !mods.shift && k === "insert") return "copy";
  // Ctrl+C：有选中才当复制（Windows Terminal 的习惯）；没选中就照常发 ^C，别让中断失效
  if (mods.ctrl && !mods.shift && k === "c") return hasSelection ? "copy" : null;
  if (mods.ctrl && k === "v") return "paste"; // Ctrl+V 与 Ctrl+Shift+V 都是粘贴
  if (mods.shift && !mods.ctrl && k === "insert") return "paste";
  return null;
}

// 复制当前格选中的文字
async function copySelection(cell) {
  const text = cell.term.getSelection();
  if (!text) return toast("没有选中内容：先用鼠标拖选一段");
  try {
    await navigator.clipboard.writeText(text);
    cell.term.clearSelection();
    toast(`已复制 ${text.length} 字符`);
  } catch {
    toast("复制失败：剪贴板不可用");
  }
}

async function pasteInto(cell) {
  try {
    const text = await navigator.clipboard.readText();
    if (!text) return;
    if (cell.sid !== null) call("ssh_input", { id: cell.sid, data: text });
    else cell.term.write(text);
    cell.term.focus();
    // 多行粘贴会一次执行完，给一句提示，但不阻断（命令行里本来就是这么用的）
    const lines = text.replace(/[\r\n]+$/, "").split(/\r?\n/).length;
    if (lines > 2) toast(`已粘贴 ${lines} 行：多行会一次性送下去，看清楚再回车`);
  } catch {
    toast("剪贴板读不出来，检查系统的剪贴板权限");
  }
}

function closeTab(id) {
  const idx = tabs.findIndex((t) => t.id === id);
  if (idx < 0) return;
  const tab = tabs[idx];
  // 一个标签里可能有好几格，每格都要断干净、各自 dispose
  for (const c of tab.cells) {
    if (c.sid !== null) call("ssh_disconnect", { id: c.sid });
    c.term.dispose();
  }
  tab.stage.remove();
  tabs.splice(idx, 1);
  if (tabs.length === 0) {
    createLocalTab();
    return;
  }
  if (activeId === id) {
    // 与 core 里的规则保持一致：先右邻、没有才左邻
    activateTab(tabs[Math.min(idx, tabs.length - 1)].id);
  } else {
    renderTabs();
  }
}

// 开局格数只补一次：打开应用那一刻的第一个标签按偏好摊开，之后再来的标签都是一格。
// 用一次性标记而不是"看当前有几个标签"，是因为第一个标签可能被 #tabs-demo 之类的钩子抢先建出来。
let bootPanesPending = true;
// 一格摊成 2×2：两次分屏，与 #split-demo 同一套走法（竖分到两格，再横分补满四格）
function fillQuad(tab) {
  splitTab(tab, "v");
  splitTab(tab, "h");
}
function createLocalTab(title = "本地 · 未连接") {
  const tab = createTab(title);
  tab.cell.term.write("Portio · 未连接。点左上「新建连接」开始。\r\n");
  if (bootPanesPending) {
    bootPanesPending = false;
    if (readPanes() === "quad") fillQuad(tab);
  }
  return tab;
}

// 兼容旧调用点：没有终端就补一个本地标签
function ensureTerminal() {
  if (!term) createLocalTab();
  return term;
}

// 带 #tabs-demo 时额外开两个本地标签，用来核对标签条与关闭按钮的排版
if (location.hash === "#tabs-demo") {
  createLocalTab("demo-web-01");
  createLocalTab("demo-db-02");
}
// 带 #split-demo 直接摊成 2×2 四格，核对分屏线、焦点描边与每格的 fit 尺寸
if (location.hash === "#split-demo") {
  const t = createLocalTab("split-demo");
  splitTab(t, "v");
  splitTab(t, "h");
}
// 带 #split-test 跑一遍分屏的状态机断言，结果写进 <title>（自动推进时用无头浏览器跑这一页核对）
if (location.hash === "#split-test") {
  const fails = [];
  const ok = (cond, msg) => { if (!cond) fails.push(msg); };
  const t = createLocalTab("t");
  ok(t.cells.length === 1 && t.gridTemplate.cols === 1 && t.gridTemplate.rows === 1, "1格应 1x1");
  splitTab(t, "v");
  ok(t.cells.length === 2 && t.gridTemplate.cols === 2 && t.gridTemplate.rows === 1, "竖分应 1x2");
  ok(t.cells[0].term.cols !== t.cells[1].term.cols || t.cells[0].term.cols > 0, "两格应各自量过尺寸");
  ok(t.cell === t.cells[1], "焦点应落在新格");
  splitTab(t, "h");
  ok(t.cells.length === 4 && t.gridTemplate.cols === 2 && t.gridTemplate.rows === 2, "再分应 2x2");
  splitTab(t, "v");
  ok(t.cells.length === 4 && t.gridTemplate.cols === 2 && t.gridTemplate.rows === 2, "满四格后不该再分");
  const before = t.cells.length;
  closeCell(t, t.cell);
  ok(t.cells.length === before - 1 && t.grid.classList.contains("tri"), "四格关一格应成三格且补洞");
  closeCell(t, t.cell);
  ok(t.cells.length === 2 && t.gridTemplate.cols === 2 && t.gridTemplate.rows === 1, "三格关一格应成左右两格");
  closeCell(t, t.cell);
  ok(t.cells.length === 1 && t.gridTemplate.cols === 1 && t.gridTemplate.rows === 1, "两格关一格应回单屏");
  ok(!t.grid.classList.contains("multi"), "单格时不该有焦点描边类");
  document.title = fails.length ? "ERR: " + fails.join(" / ") : "SELFTEST-OK";
}

// 带 #panes-test 核一遍「开局格数」：只作用于第一个标签、改设置不动眼前、认不出的值回单屏
if (location.hash === "#panes-test") {
  const fails = [];
  const ok = (cond, msg) => { if (!cond) fails.push(msg); };
  const seen = {};
  const prevKey = localStorage.getItem(PANES_KEY);
  const prevPending = bootPanesPending;
  const made = [];
  const segOn = () =>
    [...document.querySelectorAll("#seg-panes button")].filter((b) => b.classList.contains("on")).map((b) => b.dataset.v)[0];
  try {
    // ① 出厂态：没选过就是单屏，盘里不该有键
    localStorage.removeItem(PANES_KEY);
    syncSegs();
    ok(readPanes() === "single", `没选过时读到的应是单屏：${readPanes()}`);
    ok(segOn() === "single", `出厂时 seg 应选单屏：${segOn()}`);
    ok(localStorage.getItem(PANES_KEY) === null, "出厂时盘里不该有键");

    // ② 选 2×2：立刻落盘、seg 跟着走，但眼前一个标签都不许被摊开
    bootPanesPending = false;
    const t0 = createLocalTab("panes-0");
    made.push(t0.id);
    const cellsBefore = t0.cells.length;
    applyBootPanes("quad");
    ok(localStorage.getItem(PANES_KEY) === "quad", `选 2×2 应落盘 quad：${localStorage.getItem(PANES_KEY)}`);
    ok(segOn() === "quad", `选完之后 seg 应选 2×2：${segOn()}`);
    ok(t0.cells.length === cellsBefore, `改开局格数不许动眼前这一下：${cellsBefore} → ${t0.cells.length}`);

    // ③ 模拟一次开机：第一个标签摊成 2×2，第二个标签仍是一格
    bootPanesPending = true;
    const t1 = createLocalTab("panes-1");
    made.push(t1.id);
    ok(t1.cells.length === 4, `2×2 开局应 4 格：${t1.cells.length}`);
    ok(t1.gridTemplate.cols === 2 && t1.gridTemplate.rows === 2, `2×2 开局应是 2×2 网格：${t1.gridTemplate.cols}×${t1.gridTemplate.rows}`);
    ok(t1.grid.classList.contains("multi"), "四格应有焦点描边类");
    const t2 = createLocalTab("panes-2");
    made.push(t2.id);
    ok(t2.cells.length === 1, `第二个标签应仍是一格：${t2.cells.length}`);
    ok(bootPanesPending === false, "开局偏好只消费一次");

    // ④ 单屏档：同样只影响下一个开局标签
    applyBootPanes("single");
    bootPanesPending = true;
    const t3 = createLocalTab("panes-3");
    made.push(t3.id);
    ok(t3.cells.length === 1, `单屏开局应 1 格：${t3.cells.length}`);

    // ⑤ 认不出的档位读成单屏，且不许把垃圾回写进盘
    localStorage.setItem(PANES_KEY, "tri");
    ok(readPanes() === "single", `认不出的档位应读成单屏：${readPanes()}`);
    applyBootPanes("tri");
    ok(localStorage.getItem(PANES_KEY) === "single", `认不出的档位不该回写进盘：${localStorage.getItem(PANES_KEY)}`);

    seen.cells = made.map((id) => tabs.find((t) => t.id === id)?.cells.length ?? -1);
  } finally {
    // 清场：测试里建的标签全关掉（关到空时会自动补一个本地标签），键与一次性标记照原样放回
    for (const id of made) closeTab(id);
    if (prevKey === null) localStorage.removeItem(PANES_KEY);
    else localStorage.setItem(PANES_KEY, prevKey);
    bootPanesPending = prevPending;
    syncSegs();
  }
  document.title = fails.length ? "ERR: " + fails.join(" / ") : `PANES-SELFTEST-OK ${JSON.stringify(seen)}`;
}

// 带 #layout-test 核一遍「面板宽度」两层：记忆层照旧记、默认层只给开机用、认不出的值各回各的默认
if (location.hash === "#layout-test") {
  const fails = [];
  const ok = (cond, msg) => { if (!cond) fails.push(msg); };
  const seen = {};
  const prev = {
    layout: localStorage.getItem(LAYOUT_KEY),
    defw: localStorage.getItem(DEFW_KEY),
    side: localStorage.getItem(PREF.sidebar.key),
    split: localStorage.getItem(PREF.split.key),
    drawer: localStorage.getItem(PREF.drawer.key),
  };
  const segOn = (id) =>
    [...document.querySelectorAll(`#${id} button`)].filter((b) => b.classList.contains("on")).map((b) => b.dataset.v)[0];
  const varOf = (name) => root.style.getPropertyValue(name);
  try {
    // ① 出厂态：两层都没选过 → 记住上次 / 标准，盘里不该有键
    localStorage.removeItem(LAYOUT_KEY);
    localStorage.removeItem(DEFW_KEY);
    syncSegs();
    ok(readLayoutMode() === "remember", `没选过时读到的应是记住上次：${readLayoutMode()}`);
    ok(segOn("seg-layout") === "remember", `出厂时 seg 应选记住上次：${segOn("seg-layout")}`);
    ok(segOn("seg-defw") === "264", `出厂时宽度档应选标准：${segOn("seg-defw")}`);
    ok(localStorage.getItem(LAYOUT_KEY) === null && localStorage.getItem(DEFW_KEY) === null, "出厂时盘里不该有这两个键");

    // ② 拖一次宽度：记忆层落盘、界面跟着走
    setFoldUI(false);
    applySidebar(360);
    ok(varOf("--sidebar") === "360px", `拖完 --sidebar 应是 360px：${varOf("--sidebar")}`);
    ok(localStorage.getItem(PREF.sidebar.key) === "360", `拖完应落盘 360：${localStorage.getItem(PREF.sidebar.key)}`);

    // ③ 切成「用默认 + 窄」：按开机口径重落一次 → 侧栏 200、分栏 50/50、抽屉 172，
    //    但记忆层一点不许被改写（盘里仍是 360 / 0.66 / 200）
    applySplit(0.66);
    applyDrawer(200);
    applyLayoutMode("default");
    applyDefWidth(200);
    applyBootLayout();
    ok(varOf("--sidebar") === "200px", `用默认应落到 200px：${varOf("--sidebar")}`);
    ok(varOf("--split") === "50.00%", `用默认分栏应回 50.00%：${varOf("--split")}`);
    ok(varOf("--drawer") === "172px", `用默认抽屉应回 172px：${varOf("--drawer")}`);
    ok(localStorage.getItem(PREF.sidebar.key) === "360", `用默认不许改写宽度记忆：${localStorage.getItem(PREF.sidebar.key)}`);
    ok(localStorage.getItem(PREF.split.key) === "0.6600", `用默认不许改写分栏记忆：${localStorage.getItem(PREF.split.key)}`);
    ok(localStorage.getItem(PREF.drawer.key) === "200", `用默认不许改写抽屉记忆：${localStorage.getItem(PREF.drawer.key)}`);

    // ④ 换回「记住上次」：再落一次 → 三处都回到记忆层
    applyLayoutMode("remember");
    applyBootLayout();
    ok(varOf("--sidebar") === "360px", `记住上次应回到 360px：${varOf("--sidebar")}`);
    ok(varOf("--split") === "66.00%", `记住上次分栏应回到 66.00%：${varOf("--split")}`);
    ok(varOf("--drawer") === "200px", `记住上次抽屉应回到 200px：${varOf("--drawer")}`);
    seen.layout = [varOf("--sidebar"), varOf("--split"), varOf("--drawer")];

    // ⑤ 认不出的值：各回各的默认，且不许把垃圾回写进盘
    localStorage.setItem(LAYOUT_KEY, "auto");
    localStorage.setItem(DEFW_KEY, "300");
    ok(readLayoutMode() === "remember", `认不出的布局档应读成记住上次：${readLayoutMode()}`);
    ok(readDefWidth() === 264, `不在三档里的宽度应读成标准：${readDefWidth()}`);
    applyLayoutMode("auto");
    applyDefWidth(300);
    ok(localStorage.getItem(LAYOUT_KEY) === "remember", `认不出的布局档不该回写进盘：${localStorage.getItem(LAYOUT_KEY)}`);
    ok(localStorage.getItem(DEFW_KEY) === "264", `不在三档里的宽度不该回写进盘：${localStorage.getItem(DEFW_KEY)}`);
  } finally {
    // 清场：五个键按原样放回，尺寸与选中态都按开机口径重落一遍
    for (const [k, v] of [
      [LAYOUT_KEY, prev.layout], [DEFW_KEY, prev.defw], [PREF.sidebar.key, prev.side],
      [PREF.split.key, prev.split], [PREF.drawer.key, prev.drawer],
    ]) {
      if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v);
    }
    applyBootSide();
    applyBootLayout();
    syncSegs();
  }
  document.title = fails.length ? "ERR: " + fails.join(" / ") : `LAYOUT-SELFTEST-OK ${JSON.stringify(seen)}`;
}

new ResizeObserver(() => fitQuietly()).observe(termHost);
window.addEventListener("resize", () => fitQuietly());

// ---------- 会话状态 ----------
function setStatus(text, tone) {
  const el = document.querySelector(".statusbar .state");
  el.innerHTML = `<i></i>${text}`;
  el.style.color = tone === "ok" ? "var(--accent)" : tone === "bad" ? "var(--danger)" : "";
  el.querySelector("i").style.background =
    tone === "ok" ? "var(--accent)" : tone === "bad" ? "var(--danger)" : "var(--text-3)";
}

// 会话列表由 renderSessions() 从 localStorage 统一渲染，不再单独插行

// ---------- 快捷键一览 ----------
const keysModal = document.getElementById("keys-modal");
function toggleKeys(open) {
  const want = open ?? !keysModal.classList.contains("open");
  keysModal.classList.toggle("open", want);
}
document.getElementById("btn-keys").addEventListener("click", () => toggleKeys());
document.getElementById("btn-keys-close").addEventListener("click", () => toggleKeys(false));
keysModal.addEventListener("click", (e) => {
  if (e.target === keysModal) toggleKeys(false);
});
// 带了 #keys 直接展开，方便截图核对与文档深链
if (location.hash === "#keys") toggleKeys(true);
// 带 #fold-demo 直接收起会话栏，核对折叠态把手
if (location.hash === "#fold-demo") applyFold(true);
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && keysModal.classList.contains("open")) {
    e.preventDefault();
    toggleKeys(false);
    return;
  }
  if (e.ctrlKey && !e.altKey && (e.key === "/" || e.key === "?")) {
    e.preventDefault();
    toggleKeys();
  }
});

// ---------- 连接对话框 ----------
const modal = document.getElementById("connect-modal");
const authSelect = document.getElementById("f-auth");
document.getElementById("btn-new").addEventListener("click", () => openConnect());
document.getElementById("btn-cancel").addEventListener("click", () => modal.classList.remove("open"));
authSelect.addEventListener("change", () => {
  const isKey = authSelect.value === "key";
  document.getElementById("field-key").hidden = !isKey;
  document.getElementById("field-password").hidden = isKey;
});
// 认证方式自绘下拉：真实 <select> 只作值容器（.value / change 契约不变），
// 弹层与箭头由触发器 + 菜单项承担，底色/选中/hover 全走令牌。
const authTrigger = document.getElementById("auth-trigger");
const authMenu = document.getElementById("auth-menu");
const authLabel = document.getElementById("auth-label");
const authItems = Array.from(document.querySelectorAll("#auth-menu .dd-item"));
const AUTH_LABEL = { password: "密码", key: "私钥文件" };
function syncAuthUI() {
  const v = authSelect.value;
  authLabel.textContent = AUTH_LABEL[v] ?? v;
  authItems.forEach((it) =>
    it.setAttribute("aria-selected", it.dataset.value === v ? "true" : "false")
  );
}
function setAuthOpen(open) {
  authMenu.hidden = !open;
  authTrigger.setAttribute("aria-expanded", open ? "true" : "false");
}
authTrigger.addEventListener("click", (e) => {
  e.stopPropagation();
  setAuthOpen(authMenu.hidden);
});
authItems.forEach((it) =>
  it.addEventListener("click", (e) => {
    e.stopPropagation();
    authSelect.value = it.dataset.value;
    authSelect.dispatchEvent(new Event("change"));
    syncAuthUI();
    setAuthOpen(false);
  })
);
document.addEventListener("click", (e) => {
  if (!document.getElementById("auth-dd").contains(e.target)) setAuthOpen(false);
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !authMenu.hidden) setAuthOpen(false);
});
syncAuthUI();
// ---------- 记住口令 ----------
// 口令不落会话清单，走 portio-core 的加密层单独存 credentials.json；
// 键与会话清单同一个（user@host:port）——换账号就是另一条，不会串。
function credKey(user, host, port) {
  return `${user}@${host}:${Number(port ?? 22) || 22}`;
}
async function credPeek(key) {
  if (!bridge || !key || !key.includes("@")) return null;
  return await call("cred_get", { key });
}
// 面板打开 / 主机改成另一台时刷一次：存过就把勾打上，占位提示也换掉。
async function refreshRemember() {
  const el = (id) => document.getElementById(id);
  const user = el("f-user").value.trim();
  const host = el("f-host").value.trim();
  const port = Number(el("f-port").value) || 22;
  const saved = user && host ? await credPeek(credKey(user, host, port)) : null;
  el("f-remember").checked = Boolean(saved);
  el("f-password").placeholder = saved ? "已保存口令，留空沿用" : "不会落盘";
}

function openConnect(prefill = null) {
  const el = (id) => document.getElementById(id);
  // 六项一律重写一遍：只写"有预填的"那几项，会让上一次的端口 / 认证方式 / 私钥路径留在框里，
  // 点「新建连接」时看到的还是上一台机器的参数（端口 2222、认证还停在密钥），
  // 一不小心就带着别人的私钥路径去连新主机。
  const auth = prefill?.auth === "key" ? "key" : "password";
  el("f-host").value = prefill ? (prefill.host ?? "") : "";
  el("f-port").value = String(prefill?.port ?? 22);
  el("f-user").value = prefill
    ? (prefill.user ?? "")
    : (localStorage.getItem("portio.user") ?? "");
  el("f-auth").value = auth;
  syncAuthUI();
  el("f-key").value = prefill?.keyfile ?? "";
  el("f-password").value = "";
  el("field-key").hidden = auth !== "key";
  el("field-password").hidden = auth === "key";
  modal.classList.add("open");
  (auth === "key" ? el("f-host") : el("f-password")).focus();
  refreshRemember();
}

// 改了主机/用户名/端口就重新看有没有存过口令，避免拿着 A 的口令去连 B。
for (const id of ["f-host", "f-port", "f-user"]) {
  document.getElementById(id).addEventListener("blur", () => refreshRemember());
}

// ---------- 会话记忆 ----------
// 真相在应用数据目录的 sessions.json（后端负责读写），内存里这份只是镜像。
// 只存"怎么连"，不存密码：密码用完即弃，私钥记路径不记内容。
const SESS_LEGACY = "portio.sessions"; // 早期版本写在 localStorage 里，只用于一次性迁移
let sessionStore = { version: 1, records: [] };

function sessionKey(s) {
  return `${s.user}@${s.host}:${s.port ?? 22}`;
}
function readSessions() {
  return sessionStore.records;
}
function persistSessions() {
  // 写盘也从这个口子走：自检里塞 fakeInvoke 时，"存完到底写了什么"才核得到
  const inv = fakeInvoke ?? (bridge ? bridge.invoke.bind(bridge) : null);
  if (!inv) return;
  Promise.resolve()
    .then(() => inv("sessions_write", { json: JSON.stringify(sessionStore) }))
    .catch((err) => toast(`会话清单没存住：${explainError("sessions_write", String(err))}`));
}
// 时间字段跟磁盘那头叫同一个名字（`last_used`，见 crates/core/src/store.rs）。
// 早先这边写的是 `last`、后端按 `last_used` 读，落盘一次就把"最近用过"抹成 0——
// 重开之后列表全挤进「更早」，`最近使用` 一组空着。读的时候两名字都认，老文件不至于炸。
function lastUsed(s) {
  return Number(s.last_used ?? s.last ?? 0) || 0;
}
function saveSession(rec) {
  const key = sessionKey(rec);
  const next = sessionStore.records.filter((s) => sessionKey(s) !== key);
  sessionStore.records = [{ ...rec, last_used: Date.now() }, ...next].slice(0, 40);
  persistSessions();
  renderSessions();
}
function removeSession(key) {
  sessionStore.records = sessionStore.records.filter((s) => sessionKey(s) !== key);
  persistSessions();
  renderSessions();
}
// 启动时从磁盘拉一次；老版本留在 localStorage 里的记录顺手迁过来
// 两条失败要分开处理：读不出来（文件系统/权限）说什么都没用，只能照着 toast 去查；
// 读出来了但解析不了（半截写入、断电）才是危险的那种——这时候如果直接从空清单起步，
// 用户随手存一条会话就会把整份文件盖掉，原来那些记录再也找不回来。所以先让后端另存一份。
async function loadSessions() {
  if (!hasBackend()) return renderSessions();
  const raw = await tryInvoke("sessions_read", {});
  let records = [];
  let broken = false;
  let unreadable = false;
  if (raw === null) {
    // 与"还没有会话"（后端给空串）区分：这里是真的读不出来
    unreadable = true;
  } else {
    const text = String(raw).trim();
    if (text) {
      try {
        const obj = JSON.parse(text);
        if (Array.isArray(obj)) records = obj;
        else if (obj && typeof obj === "object") records = Array.isArray(obj.records) ? obj.records : [];
        else broken = true; // 合法 JSON 但不是一份清单（比如 `null`），跟读不懂一样处理
      } catch (e) {
        broken = true;
      }
    }
  }
  if (unreadable) {
    toast("会话清单读不出来（文件系统权限或磁盘问题），这次从空清单开始——先别存新会话，文件可能还在");
  }
  if (broken) {
    const kept = await tryInvoke("sessions_salvage", {});
    const name = kept ? String(kept).split(/[\\/]/).pop() : "";
    toast(
      name
        ? `会话清单读坏了，原文件已另存为 ${name}，这次从空清单开始`
        : "会话清单读坏了，原文件也没能另存——先别存新会话，去应用数据目录把 sessions.json 拷出来"
    );
  }
  sessionStore.records = records;
  const legacy = localStorage.getItem(SESS_LEGACY);
  if (sessionStore.records.length === 0 && legacy) {
    try {
      const arr = JSON.parse(legacy);
      if (Array.isArray(arr) && arr.length) {
        sessionStore.records = arr;
        persistSessions();
      }
    } catch (e) {
      /* 老数据坏了就丢了，不阻塞启动 */
    }
    localStorage.removeItem(SESS_LEGACY);
  }
  renderSessions();
}
// ---------- 会话分组 ----------
// 分组只是本机视图上的组织方式，跟着这台机器走，不写进 sessions.json（免得动数据格式）。
// 折叠状态也记在本地，重启后还是你收起来的样子。
const GROUPS_KEY = "portio.groups";
const GFOLD_KEY = "portio.foldGroups";
function readGroupsMap() {
  try {
    const o = JSON.parse(localStorage.getItem(GROUPS_KEY) || "{}");
    return o && typeof o === "object" ? o : {};
  } catch (e) {
    return {};
  }
}
function groupsOf(key) {
  return String(readGroupsMap()[key] ?? "").trim();
}
function setGroups(key, tag) {
  const m = readGroupsMap();
  if (tag) m[key] = tag;
  else delete m[key];
  localStorage.setItem(GROUPS_KEY, JSON.stringify(m));
}
function foldedSet() {
  try {
    const a = JSON.parse(localStorage.getItem(GFOLD_KEY) || "[]");
    return new Set(Array.isArray(a) ? a : []);
  } catch (e) {
    return new Set();
  }
}
function isFolded(label) {
  return foldedSet().has(label);
}
function toggleFold(label) {
  const s = foldedSet();
  if (s.has(label)) s.delete(label);
  else s.add(label);
  localStorage.setItem(GFOLD_KEY, JSON.stringify([...s]));
  renderSessions();
}
function caret() {
  const el = document.createElement("span");
  el.className = "caret";
  el.textContent = "▾";
  return el;
}

function renderSessions() {
  const sidebar = document.querySelector(".sidebar");
  const all = readSessions();
  const q = (document.getElementById("sess-search").value || "").trim().toLowerCase();
  // 搜索覆盖主机、用户名、端口和备注名——运维记得住的是"那台 web 机"
  const matched = q
    ? all.filter((s) =>
        `${s.user}@${s.host}:${s.port ?? 22} ${s.name ?? ""}`.toLowerCase().includes(q)
      )
    : all;
  // 最近用过的排前面：运维真正在敲的是那两三台机器，不该埋在列表深处
  const list = [...matched].sort((a, b) => lastUsed(b) - lastUsed(a));
  const recent = list.filter((s) => lastUsed(s)).slice(0, 5);
  const older = list.filter((s) => !recent.includes(s));
  sidebar.querySelectorAll(".sess-row, .sess-group").forEach((el) => el.remove());
  document.getElementById("session-count").textContent = q
    ? `${list.length}/${all.length}`
    : String(all.length);
  const empty = sidebar.querySelector(".empty");
  if (empty) empty.hidden = all.length > 0;
  // "搜不到"和"一条都没有"要说清楚，别让人以为是数据丢了
  let hint = sidebar.querySelector(".sess-empty");
  if (q && list.length === 0) {
    if (!hint) {
      hint = document.createElement("div");
      hint.className = "sess-empty";
      document.getElementById("sess-actions").after(hint);
    }
    hint.textContent = `没有匹配「${q}」的会话`;
  } else if (hint) {
    hint.remove();
  }
  // 有搜索词就平铺（用户要的是"哪些匹配"）；没搜索词时先按用户分组，剩下的再分"最近使用 / 更早"
  let groups;
  if (q) {
    groups = [{ label: "", items: list }];
  } else {
    const named = list.filter((s) => groupsOf(sessionKey(s)));
    if (named.length) {
      const tags = new Set(named.map((s) => groupsOf(sessionKey(s))));
      groups = [...tags]
        .sort((a, b) => a.localeCompare(b, "zh"))
        .map((tag) => ({ label: tag, items: named.filter((s) => groupsOf(sessionKey(s)) === tag), tag }));
      const rest = list.filter((s) => !groupsOf(sessionKey(s)));
      if (rest.length) {
        groups.push({ label: "未分组", items: rest, tag: "未分组" });
      }
    } else {
      groups = [
        { label: "最近使用", items: recent },
        { label: "更早", items: older },
      ];
    }
  }
  let anchor = document.getElementById("sess-search");
  for (const g of groups) {
    if (g.label && g.items.length) {
      const folded = isFolded(g.label);
      const head = document.createElement("div");
      head.className = folded ? "sess-group folded" : "sess-group";
      head.dataset.group = g.tag ?? g.label;
      head.append(caret(), document.createTextNode(g.label));
      const count = document.createElement("span");
      count.className = "gcount";
      count.textContent = String(g.items.length);
      head.append(count);
      head.title = folded ? "展开这组" : "收起这组";
      head.addEventListener("click", () => toggleFold(g.label));
      if (g.tag && g.label !== "未分组") {
        head.addEventListener("contextmenu", (ev) => {
          ev.preventDefault();
          showCtx(ev.clientX, ev.clientY, [
            { label: folded ? "展开" : "收起", run: () => toggleFold(g.label) },
            { sep: true },
            {
              label: "解散这个分组",
              hint: `${g.items.length} 台`,
              run: () => {
                for (const s of g.items) setGroups(sessionKey(s), "");
                renderSessions();
                toast(`「${g.label}」已解散，会话回到未分组`);
              },
            },
          ]);
        });
      }
      anchor.after(head);
      anchor = head;
      if (folded) continue;
    }
    for (const s of g.items) {
    const row = document.createElement("div");
    row.className = "sess-row";
    row.title = `${sessionKey(s)} · 双击连上，单击编辑`;
    const dot = document.createElement("span");
    dot.className = "dot";
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = s.name || `${s.user}@${s.host}`;
    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = s.port && Number(s.port) !== 22 ? `:${s.port}` : s.auth === "key" ? "key" : "";
    const del = document.createElement("span");
    del.className = "del";
    del.textContent = "×";
    del.title = "从列表里删掉（不影响已连会话）";
    del.addEventListener("click", (ev) => {
      ev.stopPropagation();
      removeSession(sessionKey(s));
    });
    row.append(dot, name, meta, del);
    // 单击：把参数填进对话框，人工确认后再连（密码类必须这样）
    row.addEventListener("click", () => openConnect(s));
    // 双击：密钥认证可直接重连；密码认证没有密码，只能把光标停在密码框
    row.addEventListener("dblclick", () => {
      if (s.auth === "key") connectWith({ ...s, keyfile: s.keyfile });
      else openConnect(s);
    });
    // 会话行右键：连上、改参数、复制地址、删掉这条记录
    row.addEventListener("contextmenu", (ev) => {
      ev.preventDefault();
      const key = sessionKey(s);
      showCtx(ev.clientX, ev.clientY, [
        {
          label: "连接",
          hint: s.auth === "key" ? "密钥" : "要输密码",
          run: () => (s.auth === "key" ? connectWith({ ...s, keyfile: s.keyfile }) : openConnect(s)),
        },
        { label: "编辑连接参数", run: () => openConnect(s) },
        { sep: true },
        { label: "分到分组…", hint: groupsOf(key) || "未分组", run: () => openGroupModal(s) },
        ...[...new Set(all.map((x) => groupsOf(sessionKey(x))).filter(Boolean))]
          .sort((a, b) => a.localeCompare(b, "zh"))
          .slice(0, 3)
          .map((tag) => ({
            label: `→ ${tag}`,
            run: () => {
              setGroups(key, tag);
              renderSessions();
            },
          })),
        groupsOf(key)
          ? { label: "移出分组", run: () => { setGroups(key, ""); renderSessions(); } }
          : { sep: true },
        { sep: true },
        { label: "复制地址", hint: `${s.user}@${s.host}:${s.port ?? 22}`, run: () => copyText(key) },
        { label: "复制 ssh 命令", run: () => copyText(`ssh ${s.user}@${s.host} -p ${s.port ?? 22}`) },
        { sep: true },
        { label: "从列表删除", run: () => removeSession(key) },
      ]);
    });
    anchor.after(row);
    anchor = row;
    }
  }
}

// 会话搜索：边打边筛，Esc 清空
document.getElementById("sess-search").addEventListener("input", renderSessions);
document.getElementById("sess-search").addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    e.currentTarget.value = "";
    renderSessions();
  }
});

// ---------- 分到分组 ----------
let groupTarget = null;
const groupModal = document.getElementById("group-modal");
function openGroupModal(s) {
  groupTarget = { key: sessionKey(s), label: s.name || `${s.user}@${s.host}` };
  document.getElementById("group-target").textContent = groupTarget.label;
  const input = document.getElementById("f-group");
  input.value = groupsOf(groupTarget.key);
  groupModal.classList.add("open");
  input.focus();
  input.select();
}
document.getElementById("btn-group-cancel").addEventListener("click", () =>
  groupModal.classList.remove("open")
);
document.getElementById("btn-group-ok").addEventListener("click", () => {
  const tag = document.getElementById("f-group").value.trim();
  if (groupTarget) setGroups(groupTarget.key, tag);
  groupModal.classList.remove("open");
  renderSessions();
});
document.getElementById("f-group").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    document.getElementById("btn-group-ok").click();
  }
});

// 导入来源收进一个下拉：一处入口，三个来源在里面选，不再各占一行挤掉会话列表。
const importWrap = document.getElementById("sess-import");
const importBtn = document.getElementById("btn-import");
const importMenu = document.getElementById("import-menu");
function setImportOpen(open) {
  importMenu.hidden = !open;
  importBtn.setAttribute("aria-expanded", open ? "true" : "false");
}
importBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  setImportOpen(importMenu.hidden);
});
// 点别处、按 Esc 都收起；菜单里选中一项后也立刻收起，别等下次点击
document.addEventListener("click", (e) => {
  if (!importWrap.contains(e.target)) setImportOpen(false);
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !importMenu.hidden) setImportOpen(false);
});

document.getElementById("btn-import-winscp").addEventListener("click", async () => {
  setImportOpen(false);
  if (!bridge) return toast("导入需要在桌面版里用");
  try {
    const res = await bridge.invoke("sessions_import_winscp", { path: null });
    const parsed = JSON.parse(String(res.json ?? "{}"));
    sessionStore.records = Array.isArray(parsed.records) ? parsed.records : [];
    renderSessions();
    const added = Number(res.added ?? 0);
    const skipped = Number(res.skipped ?? 0);
    if (added > 0) {
      toast(`从 WinSCP 导入 ${added} 台主机${skipped ? `，跳过 ${skipped} 项` : ""}`);
    } else {
      toast(skipped ? `没有新主机（跳过 ${skipped} 项）` : "WinSCP 配置里没有可导入的站点");
    }
  } catch (err) {
    toast(`导入失败：${explainError("sessions_import_winscp", String(err))}`);
  }
});

document.getElementById("btn-import-xshell").addEventListener("click", async () => {
  setImportOpen(false);
  if (!bridge) return toast("导入需要在桌面版里用");
  try {
    const res = await bridge.invoke("sessions_import_xshell", { dir: null });
    const parsed = JSON.parse(String(res.json ?? "{}"));
    sessionStore.records = Array.isArray(parsed.records) ? parsed.records : [];
    renderSessions();
    const added = Number(res.added ?? 0);
    const skipped = Number(res.skipped ?? 0);
    if (added > 0) {
      toast(`从 Xshell 导入 ${added} 台主机${skipped ? `，跳过 ${skipped} 项` : ""}`);
    } else {
      toast(skipped ? `没有新主机（跳过 ${skipped} 项）` : "Xshell 会话目录里没有可导入的主机");
    }
  } catch (err) {
    toast(`导入失败：${explainError("sessions_import_xshell", String(err))}`);
  }
});

document.getElementById("btn-import-ssh").addEventListener("click", async () => {
  setImportOpen(false);
  if (!bridge) return toast("导入需要在桌面版里用");
  try {
    const res = await bridge.invoke("sessions_import_ssh_config", { path: null });
    const parsed = JSON.parse(String(res.json ?? "{}"));
    sessionStore.records = Array.isArray(parsed.records) ? parsed.records : [];
    renderSessions();
    const added = Number(res.added ?? 0);
    const skipped = Number(res.skipped ?? 0);
    if (added > 0) {
      toast(`从 ssh config 导入 ${added} 台主机${skipped ? `，跳过 ${skipped} 项` : ""}`);
    } else {
      toast(skipped ? `没有新主机（跳过 ${skipped} 项）` : "配置里没有可导入的主机");
    }
  } catch (err) {
    toast(`导入失败：${explainError("sessions_import_ssh_config", String(err))}`);
  }
});

async function connectWith(spec) {
  const host = String(spec.host ?? "").trim();
  const port = Number(spec.port ?? 22) || 22;
  const user = String(spec.user ?? "").trim();
  if (!host || !user) return toast("主机和用户名都要填");
  const auth = spec.auth === "key" ? "key" : "password";
  const typed = auth === "password" ? String(spec.password ?? "") : "";
  const remember = Boolean(spec.remember);
  const credKeyId = credKey(user, host, port);
  let password = null;
  if (auth === "password") {
    password = typed;
    // 输入框留空时用存过的口令，这样"记住口令"才真的省事
    if (!password) password = await credPeek(credKeyId);
    if (!password) return toast("密码没填");
  }
  const keyfile = auth === "key" ? String(spec.keyfile ?? "").trim() : null;
  if (auth === "key" && !keyfile) return toast("私钥路径没填");

  const btn = document.getElementById("btn-connect");
  btn.disabled = true;
  btn.textContent = "连接中…";
  ensureTerminal();
  setStatus(`连接 ${user}@${host}:${port}…`);

  try {
    const channel = new window.__TAURI__.core.Channel();
    channel.onmessage = (note) => {
      document.getElementById("handshake-note").textContent = note
        ? `指纹 ${String(note).split("|")[0]}`
        : "";
    };
    const id = await bridge.invoke("ssh_connect", {
      host, port, user, password, keyfile,
      cols: term.cols, rows: term.rows,
      onHandshake: channel,
    });
    modal.classList.remove("open");
    setStatus(`已连接 ${user}@${host}:${port}`, "ok");
    saveSession({ host, port, user, auth, keyfile }); // 会话清单仍不存密码，密码走加密的凭据文件
    // 记住口令：勾了就存密文；取消勾选就把旧的那份删掉——别留一条用户以为已经删了口令
    if (auth === "password") {
      if (remember && typed) await call("cred_set", { key: credKeyId, password: typed });
      else if (!remember) await call("cred_forget", { key: credKeyId });
    }
    // 连接成功后开一个新标签，标题就是 user@host；旧本地标签留着不动
    const tab = createTab(`${user}@${host}`, id);
    // 记下"怎么连的"：这个标签分屏时要用同一套参数再建一条通道
    tab.spec = { host, port, user, auth, keyfile };
    tab.cell.term.write(`\r\n\x1b[2m—— 已连接 ${user}@${host}:${port} ——\x1b[0m\r\n`);
    tab.cell.term.focus();
    const home = await call("sftp_home", { id });
    if (home) loadRemote(home);
  } catch (err) {
    const raw = String(err);
    if (raw.includes("HOSTKEY_CHANGED")) {
      const [, previous, current] = raw.split("|");
      setStatus("主机密钥变了，已停手", "bad");
      toast("主机密钥与上次记录不一致，连接已中止");
      term.write(
        `\r\n\x1b[31m主机密钥变了！\x1b[0m\r\n` +
          `  记录：${previous}\r\n  本次：${current}\r\n` +
          `如果你确认服务器重装过，去「设置 → 已知主机」删掉这台机器的记录，再连一次就会重新信任。\r\n`
      );
    } else {
      const friendly = explainError("ssh_connect", raw);
      setStatus("连接失败", "bad");
      term.write(`\r\n\x1b[31m连接失败：${friendly}\x1b[0m\r\n`);
      toast(friendly);
    }
  } finally {
    btn.disabled = false;
    btn.textContent = "连接";
  }
}

// ---------- 快速连接 ----------
// 一行 "user@host:port"（也认 ssh:// 前缀和 [v6] 写法）解析成连接参数，
// 然后打开面板预填 —— 密码仍然现填，不落任何库。同主机有旧记录就把端口/认证方式当模板。
function parseQuickSpec(text, records = []) {
  let v = String(text ?? "").trim().replace(/^ssh:\/\//i, "");
  const slash = v.indexOf("/");
  if (slash > 0) v = v.slice(0, slash);
  if (!v) return null;
  let user = "";
  let rest = v;
  const at = v.lastIndexOf("@");
  if (at >= 0) {
    user = v.slice(0, at).trim();
    rest = v.slice(at + 1).trim();
  }
  let host = rest;
  let port = 22;
  const bracketed = rest.match(/^\[([^\]]+)\](?::(\d+))?$/);
  if (bracketed) {
    host = bracketed[1];
    if (bracketed[2]) port = Number(bracketed[2]);
  } else if (rest.includes(":")) {
    const [h, p] = rest.split(":");
    host = h;
    if (/^\d+$/.test(p ?? "")) port = Number(p);
  }
  host = host.trim();
  if (!host) return null;
  const tpl = records.find((r) => r.host === host && (!user || r.user === user))
    ?? records.find((r) => r.host === host);
  if (!user && tpl?.user) user = tpl.user;
  if (port === 22 && tpl?.port) port = Number(tpl.port) || 22;
  if (!user) user = localStorage.getItem("portio.user") ?? "";
  return {
    host,
    port: port || 22,
    user,
    auth: tpl?.auth === "key" ? "key" : "password",
    keyfile: tpl?.keyfile ?? "",
  };
}

function quickConnect() {
  const input = document.getElementById("quick-input");
  const spec = parseQuickSpec(input.value, sessionStore.records);
  if (!spec) return toast("先写一台主机，例如 deploy@10.0.8.12:2222");
  openConnect(spec);
  if (spec.user) localStorage.setItem("portio.user", spec.user);
}

document.getElementById("btn-quick").addEventListener("click", quickConnect);
document.getElementById("quick-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    quickConnect();
  }
});

document.getElementById("btn-connect").addEventListener("click", async () => {
  const user = document.getElementById("f-user").value.trim();
  if (user) localStorage.setItem("portio.user", user);
  await connectWith({
    host: document.getElementById("f-host").value,
    port: Number(document.getElementById("f-port").value || 22),
    user,
    auth: authSelect.value,
    password: document.getElementById("f-password").value,
    keyfile: document.getElementById("f-key").value,
    remember: document.getElementById("f-remember").checked,
  });
});

// 分组的核验入口：两台生产、一台测试（已折叠）、一台未分组
if (location.hash.startsWith("#groups-demo")) {
  saveSession({ host: "web-01.prod", port: 22, user: "deploy", auth: "key", keyfile: "~/.ssh/id_ed25519" });
  saveSession({ host: "db-01.prod", port: 2222, user: "dba", auth: "password" });
  saveSession({ host: "stage-01", port: 22, user: "qa", auth: "password" });
  saveSession({ host: "10.0.8.12", port: 22, user: "root", auth: "password" });
  setGroups("deploy@web-01.prod:22", "生产");
  setGroups("dba@db-01.prod:2222", "生产");
  setGroups("qa@stage-01:22", "测试");
  localStorage.setItem(GFOLD_KEY, JSON.stringify(["测试"]));
  renderSessions();
}

// 快速连接的核验入口：填好一行再打开面板，看解析结果对不对
if (location.hash.startsWith("#quick-demo")) {
  saveSession({ host: "10.0.8.12", port: 2222, user: "deploy", auth: "key", keyfile: "~/.ssh/id_ed25519" });
  document.getElementById("quick-input").value = "deploy@10.0.8.12:2222";
  quickConnect();
}

// 已知主机的核验入口：无头页面没有后端，先塞几条假记录看版式与删除交互
if (location.hash.startsWith("#hosts-demo")) {
  hostDemo = [
    { host: "web-01.prod", port: 22, fingerprint: "SHA256:9fKq2mZpQ0aBcDeFgHiJkLmNoPqRsTuVwXyZ01234" },
    { host: "10.0.8.12", port: 2222, fingerprint: "SHA256:Zx81MnBvC3xY7tReWqAsDfGhJkLzXcVbNm1234567" },
    { host: "stage-01.internal.example.com", port: 22, fingerprint: "SHA256:Qw3ErTyUiOpAsDfGhJkLzXcVbNm1234567890abcd" },
  ];
  toggleSettings(true);
  // 截图用：面板长到十六项之后一屏放不下，「已知主机」沉在折叠以下。`#hosts-demo-tail`
  // 把正文一路滚到底，拍的就是那一节；`#hosts-demo` 拍面板顶部（自定义）。
  if (location.hash.startsWith("#hosts-demo-tail")) {
    // 只认设置面板自己那个 .body：页面上还有连接面板、快捷键面板，它们的 .body 是 display:none，
    // querySelector(".sheet .body") 抓到的是第一个（隐藏的）那个，滚它等于什么都没做。
    const tail = () => {
      const body = document.querySelector("#settings-modal .sheet .body");
      if (body) body.scrollTop = body.scrollHeight - body.clientHeight;
    };
    setTimeout(() => {
      tail();
      requestAnimationFrame(tail);
    }, 200);
  }
}

// 截图用：只把设置面板打开、不预选任何一项，拍「自定义」面板的本来样子
if (location.hash === "#settings-demo") toggleSettings(true);

// 会话清单以前端内存镜像为准，启动时从磁盘拉一次
if (location.hash.startsWith("#find-demo")) {
  // 终端里本来就有启动 banner，直接拿它当搜索素材，验证全链路：扫 buffer → 高亮 → 计数
  const q = location.hash.includes("?")
    ? new URLSearchParams(location.hash.split("?")[1]).get("q") ?? "Portio"
    : "Portio";
  setTimeout(() => {
    findToggle(true);
    findInput.value = q;
    findRefresh();
  }, 60);
}

if (location.hash.startsWith("#sess-demo") || location.hash.startsWith("#import-demo") || location.hash.startsWith("#split-demo") || location.hash.includes("ctx-demo")) {
  saveSession({ host: "web-01.example.com", port: 22, user: "deploy", auth: "key", keyfile: "~/.ssh/id_ed25519" });
  saveSession({ host: "10.0.8.12", port: 2222, user: "root", auth: "password" });
  // 再塞一条"从没用过"的记录，好核对"更早"这组标题
  sessionStore.records.push({ host: "db-02.internal", port: 22, user: "dba", auth: "password", last_used: 0 });
  persistSessions();
  renderSessions();
  const q = new URLSearchParams(location.hash.slice(1)).get("q");
  if (q) {
    document.getElementById("sess-search").value = q;
    renderSessions();
  }
  // 截图用：把导入来源的下拉真正展开（走的是按钮自己的 click，不是另画一份菜单）
  if (location.hash.startsWith("#import-demo")) setImportOpen(true);
} else if (!location.hash.startsWith("#groups-demo")) {
  loadSessions();
}

// ---------- 后端事件 ----------
if (window.__TAURI__?.event) {
  window.__TAURI__.event.listen("shell", (e) => {
    const { id, kind, text } = e.payload ?? {};
    // 按会话 id 找到它所属的那一格，后台标签 / 分屏里另一格的输出也要落到自己的终端里
    const cell = cellBySid(id);
    if (!cell) return;
    const t = cell.term;
    if (kind === "output") t.write(text);
    if (kind === "exit") t.write(`\r\n\x1b[2m[进程退出 ${text}]\x1b[0m\r\n`);
    if (kind === "error") t.write(`\r\n\x1b[31m${text}\x1b[0m\r\n`);
    if (kind === "closed") {
      t.write("\r\n\x1b[2m[连接已断开]\x1b[0m\r\n");
      cell.sid = null;
      if (activeId === cell.tab.id) {
        sessionId = cell.tab.cell.sid;
        setStatus("连接已断开", "bad");
      }
      renderTabs();
    }
  });
}

// Ctrl+T 现在真的开对话框了（S1 时它只会提示）
window.addEventListener("keydown", (e) => {
  if (e.ctrlKey && !e.altKey && e.key.toLowerCase() === "t") {
    e.preventDefault();
    openConnect();
  }
});

// 关窗前把所有会话断干净（分屏出来的格子也算），别把服务端会话挂在那儿
window.addEventListener("beforeunload", () => {
  for (const t of tabs) {
    for (const c of t.cells) if (c.sid !== null) call("ssh_disconnect", { id: c.sid });
  }
});

// 核验用：把「开局就是 2×2」的样子摆出来（#panes-demo / #panes-demo-light / #panes-demo-set）。
// 只改本页的一次性偏好与标记，等下面那句 ensureTerminal 建标签时按四格摊开。
if (["#panes-demo", "#panes-demo-light", "#panes-demo-set"].includes(location.hash)) {
  localStorage.setItem(PANES_KEY, "quad");
  bootPanesPending = true;
}
// 启动就把终端画出来，占位文案说明下一步做什么，避免一块空白面板
ensureTerminal();
if (location.hash === "#panes-demo-light") applyTheme("light");
if (location.hash === "#panes-demo-set") toggleSettings(true);
// 演示页在启动那串 applyX 之后才改的偏好，seg 的选中态要补一次才跟得上
if (location.hash.startsWith("#panes-demo")) syncSegs();

// 核验用：把「用默认 + 宽」的样子摆出来（#layout-demo / #layout-demo-light / #layout-demo-set）。
// 演示页是在启动那串 applyX 之后才改偏好，所以改完要按开机口径重落一次尺寸，再补一次选中态。
if (["#layout-demo", "#layout-demo-light", "#layout-demo-set"].includes(location.hash)) {
  applyLayoutMode("default");
  applyDefWidth(328);
  applyBootLayout();
  if (location.hash === "#layout-demo-light") applyTheme("light");
  if (location.hash === "#layout-demo-set") toggleSettings(true);
  syncSegs();
}

// ---------- 文件双栏 ----------
const remoteListEl = document.getElementById("remote-list");
const localListEl = document.getElementById("local-list");
const remotePathEl = document.getElementById("remote-path");
const localPathEl = document.getElementById("local-path");
let remotePath = null;
let localPath = null;
const transferRows = new Map();

const escapeHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function fmtSize(n) {
  if (!n) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v < 10 && i > 0 ? v.toFixed(1) : Math.round(v)} ${units[i]}`;
}

function fmtTime(sec) {
  if (!sec) return "—";
  const d = new Date(sec * 1000);
  const pad = (x) => String(x).padStart(2, "0");
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function posixJoin(dir, name) {
  if (!dir) return name;
  return dir.endsWith("/") ? dir + name : `${dir}/${name}`;
}

function winJoin(dir, name) {
  if (!dir) return name;
  return dir.endsWith("\\") || dir.endsWith("/") ? dir + name : `${dir}\\${name}`;
}

function renderList(el, items, side) {
  el.innerHTML = "";
    if (!items.length) {
    el.innerHTML = '<span class="hint">空目录</span>';
    return;
  }
  const frag = document.createDocumentFragment();
  for (const it of items) {
    const row = document.createElement("div");
    row.className = `fp-row${it.is_dir ? " dir" : ""}${side === "remote" ? " has-perm" : ""}`;
    row.innerHTML =
      `<span class="ico">${it.is_dir ? "▸" : "·"}</span>` +
      `<span class="nm">${escapeHtml(it.name)}</span>` +
      (side === "remote" ? `<span class="pm">${escapeHtml(it.perm || "—")}</span>` : "") +
      `<span class="sz">${it.is_dir ? "—" : fmtSize(it.size)}</span>` +
      `<span class="tm">${fmtTime(it.modified)}</span>`;
    row.title = it.path;
    row.addEventListener("click", () => {
      el.querySelectorAll(".fp-row.sel").forEach((r) => r.classList.remove("sel"));
      row.classList.add("sel");
    });
    row.addEventListener("dblclick", () => {
      if (it.is_dir) {
        if (side === "remote") loadRemote(it.path);
        else loadLocal(it.path);
        return;
      }
      if (side === "remote") downloadFile(it);
      else uploadFile(it);
    });
    // 文件行右键：远端是"下载 / 新建 / 删除"，本地是"上传 / 复制路径"
    row.addEventListener("contextmenu", (ev) => {
      ev.preventDefault();
      el.querySelectorAll(".fp-row.sel").forEach((r) => r.classList.remove("sel"));
      row.classList.add("sel");
      if (side === "remote") {
        showCtx(ev.clientX, ev.clientY, [
          {
            label: "下载到本地",
            disabled: it.is_dir,
            hint: it.is_dir ? "目录不进队列" : "",
            run: () => downloadFile(it),
          },
          { label: "进入目录", disabled: !it.is_dir, run: () => loadRemote(it.path) },
          { sep: true },
          { label: "重命名", run: () => renameRemote(it) },
          { label: "新建文件夹", run: () => newRemoteDir() },
          { label: "删除", hint: it.is_dir ? "目录" : "文件", run: () => removeRemote(it) },
          { sep: true },
          { label: "复制路径", run: () => copyText(it.path) },
          { label: "刷新列表", run: () => loadRemote(remotePath) },
        ]);
      } else {
        showCtx(ev.clientX, ev.clientY, [
          { label: "上传到远端", disabled: it.is_dir, run: () => uploadFile(it) },
          { label: "进入目录", disabled: !it.is_dir, run: () => loadLocal(it.path) },
          { sep: true },
          { label: "重命名", run: () => renameLocal(it) },
          { label: "复制路径", run: () => copyText(it.path) },
          { label: "刷新列表", run: () => loadLocal(localPath) },
        ]);
      }
    });
    frag.appendChild(row);
  }
  el.appendChild(frag);
}

async function loadRemote(path) {
  if (sessionId === null) {
    remoteListEl.innerHTML = '<span class="hint">先连一台主机，远端目录才会出现。</span>';
    return;
  }
  // 这一处原来直连 bridge.invoke：路径打错、目录被删、权限不够时只剩一条没人看见的拒绝，
  // 面板还停在旧目录，一句话都没有。走 call() 才会把错因翻成人话。
  const res = await call("sftp_list", { id: sessionId, path });
  if (!res) {
    // 没有后端的预览页里 call() 也是 null——那种情况保持原样，别在物料截图上写「失败」
    if (hasBackend()) remoteListEl.innerHTML = '<span class="hint">列目录失败，原因见右下角提示。</span>';
    return;
  }
  remotePath = path;
  remotePathEl.value = path;
  document.getElementById("files-path").textContent = path;
  document.getElementById("files-mode").textContent = "SFTP";
  renderList(remoteListEl, res, "remote");
}

async function loadLocal(path) {
  const res = await call("local_list", { path: path ?? null });
  if (!res) {
    if (hasBackend()) localListEl.innerHTML = '<span class="hint">列目录失败，原因见右下角提示。</span>';
    return;
  }
  const [dir, items] = res;
  localPath = dir;
  localPathEl.value = dir;
  localStorage.setItem("portio.localPath", dir);
  renderList(localListEl, items, "local");
}

// 文件面板两块的刷新：右键菜单和刷新按钮都走这一条，省得两处各写一遍路径取值
function refreshBothDirs() {
  if (!bridge) {
    toast("浏览器预览没有真实目录");
    return;
  }
  loadRemote(document.getElementById("remote-path").value || "/");
  loadLocal(document.getElementById("local-path").value || "");
}

// 传输行：先占位，进度事件里按 key 找回来更新
// 标题条那个计数原来只在 finishTransfer 里改一次，于是传输刚开始跑的时候数字还是旧的
// （开始三条、结束一条，标题条从 0 跳到 1）。计数只跟着 transferRows 走，改一处就够。
function syncTransferCount() {
  const num = document.querySelector(".drawer .num");
  if (num) num.textContent = String(transferRows.size);
}

function transferRow(name, dir) {
  const key = `${dir}:${name}`;
  if (transferRows.has(key)) return { key, el: transferRows.get(key) };
  const body = document.querySelector(".drawer-body");
  // 空态那句要在第一行出现时就消失。它以前是 `.drawer-body` 里的裸文本，这里却按 `.hint` 找，
  // 于是永远找不到——三条传输都在跑了，抽屉顶部还挂着一句「空」。现在它是个真元素。
  body.querySelector(".drawer-empty")?.remove();
  const el = document.createElement("div");
  el.className = "tr";
  el.innerHTML =
    `<span class="ico">${dir === "up" ? "↑" : "↓"}</span>` +
    `<span class="nm">${escapeHtml(name)}<span class="arrow">·</span></span>` +
    `<span class="meta">排队</span>`;
  const bar = document.createElement("div");
  bar.className = "bar";
  bar.innerHTML = "<i></i>";
  el.appendChild(bar);
  body.appendChild(el);
  transferRows.set(key, el);
  syncTransferCount();
  return { key, el };
}

function updateTransfer(p) {
  const row = transferRows.get(`${p.dir}:${p.name}`);
  if (!row) return;
  const pct = p.total ? Math.min(100, Math.round((p.done / p.total) * 100)) : 0;
  row.querySelector(".bar i").style.width = `${pct}%`;
  row.querySelector(".meta").textContent = p.total ? `${pct}% · ${fmtSize(p.total)}` : fmtSize(p.done);
}

async function downloadFile(item) {
  const target = winJoin(localPath, item.name);
  transferRow(item.name, "down");
  // 这两条以前直连 bridge.invoke：一旦抛错（磁盘满、断线、权限不够），行会永远停在「排队」，
  // 既没人说失败，也不知道要不要重试。走 call() 收尾才落成红条 + 一句人话。
  const bytes = await call("sftp_download", { id: sessionId, remote: item.path, local: target });
  if (bytes === null && !hasBackend()) return; // 预览页没有后端：留着排队，不假报失败
  finishTransfer(item.name, "down", bytes);
  if (typeof bytes === "number") loadLocal(localPath);
}

async function uploadFile(item) {
  const target = posixJoin(remotePath, item.name);
  transferRow(item.name, "up");
  const bytes = await call("sftp_upload", { id: sessionId, local: item.path, remote: target });
  if (bytes === null && !hasBackend()) return;
  finishTransfer(item.name, "up", bytes);
  if (typeof bytes === "number") loadRemote(remotePath);
}

// ---------- 右键菜单里用到的动作 ----------
function copyText(text) {
  navigator.clipboard
    .writeText(text)
    .then(() => toast("已复制到剪贴板"))
    .catch(() => toast("复制失败：剪贴板不可用"));
}

async function newRemoteDir() {
  if (sessionId === null) {
    toast("先连一台主机，才能建远端目录");
    return;
  }
  const name = window.prompt("新目录名（建在当前远端目录下）");
  if (!name) return;
  const ok = await call("sftp_mkdir", { id: sessionId, path: posixJoin(remotePath, name) });
  if (ok !== null) {
    toast(`已建目录 ${name}`);
    loadRemote(remotePath);
  }
}

async function removeRemote(item) {
  if (sessionId === null) return;
  const what = item.is_dir ? "目录" : "文件";
  if (!window.confirm(`删除${what} ${item.path}？此操作不可撤销。`)) return;
  const ok = await call("sftp_remove", { id: sessionId, path: item.path, is_dir: item.is_dir });
  if (ok !== null) {
    toast(`已删除 ${item.name}`);
    loadRemote(remotePath);
  }
}

// 重命名只改同一目录内的名字；改名后如果撞名，服务端会直接报错，这里不替它兜底
async function renameRemote(item) {
  if (sessionId === null) return;
  const name = window.prompt(`把「${item.name}」改成：`, item.name);
  if (!name || name === item.name) return;
  const ok = await call("sftp_rename", {
    id: sessionId,
    from: item.path,
    to: posixJoin(remotePath, name),
  });
  if (ok !== null) {
    toast(`已重命名为 ${name}`);
    loadRemote(remotePath);
  }
}

async function renameLocal(item) {
  const name = window.prompt(`把「${item.name}」改成：`, item.name);
  if (!name || name === item.name) return;
  const ok = await call("local_rename", { from: item.path, to: winJoin(localPath, name) });
  if (ok !== null) {
    toast(`已重命名为 ${name}`);
    loadLocal(localPath);
  }
}

function finishTransfer(name, dir, bytes) {
  const row = transferRows.get(`${dir}:${name}`);
  if (!row) return;
  const ok = bytes !== null;
  row.querySelector(".bar i").style.width = ok ? "100%" : "0%";
  row.querySelector(".bar i").style.background = ok ? "var(--accent)" : "var(--danger)";
  row.querySelector(".meta").textContent = ok ? `完成 · ${fmtSize(bytes)}` : "失败";
  syncTransferCount();
  if (window.__TAURI__?.event) {
    // 让队列自动浮出来看一眼，用户不用自己去翻抽屉（收起态就恢复到上次的高度，别只露一行）
    if (document.getElementById("drawer").classList.contains("collapsed")) {
      applyDrawer(Math.max(drawerLast, 120));
    }
  }
}

document.getElementById("remote-up").addEventListener("click", () => {
  if (remotePath) loadRemote(remotePath.replace(/\/+$/, "").replace(/\/[^/]*$/, "") || "/");
});
document.getElementById("remote-refresh").addEventListener("click", () => remotePath && loadRemote(remotePath));
document.getElementById("local-up").addEventListener("click", () => {
  if (!localPath) return;
  const parent = localPath.replace(/[\\/]+$/, "").replace(/[\\/][^\\/]*$/, "");
  loadLocal(parent || localPath);
});
document.getElementById("local-refresh").addEventListener("click", () => loadLocal(localPath));
remotePathEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") loadRemote(remotePathEl.value.trim() || "/");
});
localPathEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") loadLocal(localPathEl.value.trim());
});
document.getElementById("remote-mkdir").addEventListener("click", () => newRemoteDir());

if (window.__TAURI__?.event) {
  window.__TAURI__.event.listen("transfer", (e) => updateTransfer(e.payload));
}

// 截图用：无头页没有后端，传输队列一直是空的（0 条 + 一句提示）。#transfer-demo 塞三行
// 不同进度——走的就是真正在用的 transferRow / updateTransfer / finishTransfer，不另画一份列表。
// 主界面与分屏两张首发图也带上它，省得物料里那个抽屉永远是空的。
if (
  location.hash.startsWith("#transfer-demo") ||
  location.hash.startsWith("#sess-demo") ||
  location.hash.startsWith("#split-demo")
) {
  const seeded = [
    { name: "site-2026-11-20.tar.gz", dir: "down", done: 45_600_000, total: 106_000_000, finished: false },
    { name: "release-notes.md", dir: "up", done: 6144, total: 0, finished: true },
    { name: "photos-2026.zip", dir: "up", done: 0, total: 0, finished: false },
  ];
  for (const p of seeded) {
    transferRow(p.name, p.dir);
    if (p.finished) finishTransfer(p.name, p.dir, p.done);
    else if (p.total) updateTransfer({ dir: p.dir, name: p.name, done: p.done, total: p.total });
  }
}

// 本地目录不用等连接，界面一出来就能看
loadLocal(localStorage.getItem("portio.localPath") || null);

// 带 #transfer-test 核一遍传输队列：空态那句必须随第一行消失，计数 / 百分比 / 完成 / 排队文案
// 必须跟着真状态走。这条是给「三条在跑了抽屉顶上还挂着一句『空』」那个 Bug 立的桩。
if (location.hash === "#transfer-test") {
  const fails = [];
  const ok = (cond, msg) => { if (!cond) fails.push(msg); };
  const seen = {};
  const body = document.querySelector(".drawer-body");
  const emptyOf = () => body.querySelector(".drawer-empty");
  const barOf = (row) => row.querySelector(".bar i").style.width;
  try {
    // ① 空队列：一句空态提示，零行
    ok(!!emptyOf(), "空队列时应留着那句空态提示");
    ok(transferRows.size === 0, `空队列时行数应是 0：${transferRows.size}`);

    // ② 第一行出现 → 空态提示必须当场消失
    transferRow("site-2026-11-20.tar.gz", "down");
    ok(!emptyOf(), "队列里有行了，空态提示还挂着");
    ok(transferRows.size === 1, `塞了一条后行数应是 1：${transferRows.size}`);

    // ③ 进度：百分比与总量都写到行尾
    updateTransfer({ dir: "down", name: "site-2026-11-20.tar.gz", done: 45_600_000, total: 106_000_000 });
    const first = transferRows.get("down:site-2026-11-20.tar.gz");
    ok(barOf(first) === "43%", `45600000/106000000 应算成 43%：${barOf(first)}`);
    ok(
      first.querySelector(".meta").textContent === "43% · 101 MB",
      `行尾应是「43% · 101 MB」：${JSON.stringify(first.querySelector(".meta").textContent)}`
    );

    // ④ 再塞一条完成的、一条排队的：计数、文案、行数三处都要对
    transferRow("release-notes.md", "up");
    finishTransfer("release-notes.md", "up", 6144);
    transferRow("photos-2026.zip", "up");
    ok(transferRows.size === 3, `三条之后行数应是 3：${transferRows.size}`);
    ok(body.querySelectorAll(".tr").length === 3, `抽屉正文里应有 3 条 .tr：${body.querySelectorAll(".tr").length}`);
    ok(
      document.querySelector(".drawer .num").textContent === "3",
      `标题条计数应是 3：${document.querySelector(".drawer .num").textContent}`
    );
    ok(!emptyOf(), "三条都在跑了，空态提示还挂着");
    const doneRow = transferRows.get("up:release-notes.md");
    ok(barOf(doneRow) === "100%", `完成的那条进度条应满格：${barOf(doneRow)}`);
    ok(
      doneRow.querySelector(".meta").textContent === "完成 · 6.0 KB",
      `完成那行的文案应是「完成 · 6.0 KB」：${JSON.stringify(doneRow.querySelector(".meta").textContent)}`
    );
    const qRow = transferRows.get("up:photos-2026.zip");
    ok(qRow.querySelector(".meta").textContent === "排队", `还没开始的那行应写排队：${qRow.querySelector(".meta").textContent}`);

    // ⑤ 几何：三行都在抽屉里，右缘不许越出抽屉
    const drawerBox = document.getElementById("drawer").getBoundingClientRect();
    ok(drawerBox.width > 0 && drawerBox.height > 0, "抽屉本身没有尺寸，界面塌了");
    for (const [key, el] of transferRows) {
      const b = el.getBoundingClientRect();
      ok(b.width > 0 && b.height > 0, `传输行 \`${key}\` 没有尺寸`);
      ok(b.right <= drawerBox.right + 0.5, `传输行 \`${key}\` 右缘越出抽屉：${b.right} > ${drawerBox.right}`);
    }
    seen.rows = transferRows.size;
    seen.num = document.querySelector(".drawer .num").textContent;
    seen.bar = barOf(first);
    seen.empty = !!emptyOf();
  } catch (err) {
    fails.push(`核传输队列的过程抛了异常：${err && err.message ? err.message : err}`);
  }
  document.title = fails.length
    ? `TRANSFER-SELFTEST-FAIL ${JSON.stringify(fails)} ${JSON.stringify(seen)}`
    : `TRANSFER-SELFTEST-OK ${JSON.stringify(seen)}`;
}

// 带 #net-fail-test 核一遍"后端出错时界面有没有话说"：列目录失败要在块里留一句、
// 传输失败要落成「失败」红条而不是永远「排队」、错因一律翻成人话。这条给的是
// 「列目录与上传下载绕过统一错误处理，出事了界面一声不响」那个 Bug 立的桩。
if (location.hash === "#net-fail-test") {
  (async () => {
    const fails = [];
    const ok = (cond, msg) => {
      if (!cond) fails.push(msg);
    };
    const seen = {};
    const toastEl = document.getElementById("toast");
    const tgBefore = [...toastEl.children];
    // toast 是一条条叠着排的（同时最多几条），要核的是最新那一条
    const lastToast = () => {
      const kids = [...toastEl.children];
      return kids.length ? kids[kids.length - 1].textContent : "";
    };
    const prevSid = sessionId;
    const prevRemotePath = remotePath;
    const prevRemoteHtml = remoteListEl.innerHTML;
    const prevLocalHtml = localListEl.innerHTML;
    const drawerBody = document.querySelector(".drawer-body");
    const failRows = [];
    try {
      // ① 错因翻译：四类最常见的回包都要说清"发生了什么 + 下一步"，认不出的保留原文并带上命令名
      const cases = [
        ["No such file or directory", "路径不存在："],
        ["Permission denied", "权限不足："],
        ["Connection refused", "连接被拒绝："],
        ["remote disk full: no space left on device", "远端磁盘已满："],
      ];
      for (const [raw, want] of cases) {
        const got = explainError("sftp_list", raw);
        ok(got.startsWith(want), `「${raw}」应翻成「${want}…」：${got}`);
      }
      const odd = explainError("sftp_list", "EOF while reading");
      ok(odd.startsWith("sftp_list 失败：") && odd.includes("EOF while reading"), `认不出的错应保留原文并带命令名：${odd}`);

      // ② 造一个会抛错的后端：无头页里没有真后端，这手不塞替身就永远跑不到
      fakeInvoke = async (cmd) => {
        if (cmd === "sftp_list") throw new Error("No such file or directory");
        if (cmd === "local_list") throw new Error("Permission denied");
        if (cmd === "sftp_download") throw new Error("no space left on device");
        if (cmd === "sftp_upload") throw new Error("timed out");
        return null;
      };
      sessionId = 4242;

      // ③ 远端列目录失败：一句话要在块里，路径条不许被写成一个打错的路径，进程不许抛
      const pathBefore = document.getElementById("files-path").textContent;
      let threw = null;
      try {
        await loadRemote("/nope");
      } catch (err) {
        threw = err && err.message ? err.message : String(err);
      }
      ok(threw === null, `列目录失败不该抛出去：${threw}`);
      ok(remoteListEl.textContent.includes("列目录失败"), `远端块应留一句失败说明：${remoteListEl.textContent}`);
      ok(lastToast().startsWith("路径不存在："), `错因应弹成「路径不存在：…」：${lastToast()}`);
      ok(
        document.getElementById("files-path").textContent === pathBefore,
        `列目录失败不该把路径条改成打错的路径：${document.getElementById("files-path").textContent}`
      );

      // ④ 本地列目录失败：一样要有话说
      threw = null;
      try {
        await loadLocal("C:/nope");
      } catch (err) {
        threw = err && err.message ? err.message : String(err);
      }
      ok(threw === null, `本地列目录失败不该抛出去：${threw}`);
      ok(localListEl.textContent.includes("列目录失败"), `本地块应留一句失败说明：${localListEl.textContent}`);
      ok(lastToast().startsWith("权限不足："), `本地权限不足应弹成「权限不足：…」：${lastToast()}`);

      // ⑤ 下载失败：行要收成「失败」，进度条清零且用危险色，绝不能永远停在「排队」
      await downloadFile({ name: "a.bin", path: "/tmp/a.bin", is_dir: false });
      const rowD = transferRows.get("down:a.bin");
      failRows.push("down:a.bin");
      ok(!!rowD, "下载失败后应留下这一行");
      ok(rowD && rowD.querySelector(".meta").textContent === "失败", `下载失败的行应写「失败」：${rowD && rowD.querySelector(".meta").textContent}`);
      ok(rowD && rowD.querySelector(".bar i").style.width === "0%", `失败的行进度条应清零：${rowD && rowD.querySelector(".bar i").style.width}`);
      const probe = document.createElement("div");
      probe.style.background = "var(--danger)";
      document.body.append(probe);
      const dangerBg = getComputedStyle(probe).backgroundColor;
      probe.remove();
      ok(
        rowD && getComputedStyle(rowD.querySelector(".bar i")).backgroundColor === dangerBg,
        "失败的行进度条要用危险色"
      );
      ok(lastToast().startsWith("远端磁盘已满："), `磁盘满应弹成「远端磁盘已满：…」：${lastToast()}`);

      // ⑥ 上传失败：同样收成「失败」；两条都失败时计数是 2
      await uploadFile({ name: "b.bin", path: "C:\\b.bin", is_dir: false });
      const rowU = transferRows.get("up:b.bin");
      failRows.push("up:b.bin");
      ok(rowU && rowU.querySelector(".meta").textContent === "失败", `上传失败的行应写「失败」：${rowU && rowU.querySelector(".meta").textContent}`);
      ok(
        document.querySelector(".drawer .num").textContent === "2",
        `两条失败行也要算进标题条计数：${document.querySelector(".drawer .num").textContent}`
      );
      ok(lastToast().startsWith("连接超时："), `超时应弹成「连接超时：…」：${lastToast()}`);

      seen.remote = remoteListEl.textContent.trim().slice(0, 12);
      seen.failed = failRows.length;
    } catch (err) {
      fails.push(`核后端出错这一路的过程抛了异常：${err && err.message ? err.message : err}`);
    } finally {
      // 收场：替身摘掉、会话号与路径还原、试出来的行连同计数一起清掉，两块列表回到原来那行提示
      fakeInvoke = null;
      sessionId = prevSid;
      remotePath = prevRemotePath;
      for (const key of failRows) {
        const el = transferRows.get(key);
        if (el) el.remove();
        transferRows.delete(key);
      }
      syncTransferCount();
      if (transferRows.size === 0 && !drawerBody.querySelector(".drawer-empty")) {
        const empty = document.createElement("div");
        empty.className = "drawer-empty";
        empty.textContent = "空。上传、下载、同步的进度都会在这里。";
        drawerBody.append(empty);
      }
      for (const t of [...toastEl.children]) if (!tgBefore.includes(t)) t.remove();
      remoteListEl.innerHTML = prevRemoteHtml;
      localListEl.innerHTML = prevLocalHtml;
    }
    document.title = fails.length
      ? `NET-FAIL-SELFTEST-FAIL ${JSON.stringify(fails)} ${JSON.stringify(seen)}`
      : `NET-FAIL-SELFTEST-OK ${JSON.stringify(seen)}`;
  })();
}

// #ctx-demo：真的派发一次右键事件，用真实 handler 出菜单，便于截图核对（不是另画一份假菜单）
if (location.hash.includes("ctx-demo")) {
  // 无头环境没有后端，本地目录读不出来，这里塞几行假文件，让文件行右键有真实目标可打
  renderList(
    localListEl,
    [
      { name: "report-2026.pdf", path: "C:\\tmp\\report-2026.pdf", is_dir: false, size: 1048576, modified: 1763460000 },
      { name: "logs", path: "C:\\tmp\\logs", is_dir: true, size: 0, modified: 1763460000 },
    ],
    "local"
  );
  const which = location.hash.includes("term")
    ? ".term-cell"
    : location.hash.includes("tab")
      ? ".tab"
      : location.hash.includes("file")
        ? ".fp-row"
        : ".sess-row";
  const target = document.querySelector(which);
  if (target) {
    const r = target.getBoundingClientRect();
    target.dispatchEvent(
      new MouseEvent("contextmenu", { bubbles: true, clientX: r.left + 60, clientY: r.top + r.height })
    );
  }
}

// #clip-test：复制粘贴按键映射的状态机自检，结果写进 <title>，和 #split-test 一样当回归门禁。
// 只测纯函数 clipboardAction，不依赖真实键盘 / 剪贴板。
if (location.hash.includes("clip-test")) {
  const cases = [
    [{ ctrl: true, shift: true, key: "C" }, false, "copy"], // Ctrl+Shift+C 无选中也走复制（随后提示没选中）
    [{ ctrl: true, shift: false, key: "Insert" }, false, "copy"], // Ctrl+Insert（Xshell 习惯）
    [{ ctrl: true, shift: false, key: "c" }, true, "copy"], // Ctrl+C 有选中 → 复制
    [{ ctrl: true, shift: false, key: "c" }, false, null], // Ctrl+C 无选中 → 照发 ^C
    [{ ctrl: true, shift: false, key: "v" }, false, "paste"], // Ctrl+V
    [{ ctrl: true, shift: true, key: "V" }, false, "paste"], // Ctrl+Shift+V
    [{ ctrl: false, shift: true, key: "Insert" }, false, "paste"], // Shift+Insert（PuTTY 习惯）
    [{ ctrl: true, shift: true, key: "d" }, false, null], // 分屏键不被剪贴板抢走
    [{ ctrl: true, shift: false, key: "w" }, false, null], // 关标签键不被抢
    [{ ctrl: true, alt: true, shift: false, key: "f" }, false, null], // Ctrl+Alt+F 留给折叠面板
  ];
  const bad = cases.filter(([m, sel, want]) => clipboardAction(m, sel) !== want);
  const ok = bad.length === 0;
  document.title = ok
    ? `CLIP-SELFTEST-OK ${cases.length}`
    : `CLIP-SELFTEST-FAIL ${bad.length}/${cases.length}`;
}

// ---------- 面板级右键菜单 ----------
// 桌面应用里不该冒出浏览器那套菜单：全局先兜住默认菜单，再由每个面板按自己的能力给菜单。
// 面板覆盖：会话栏 / 标签条 / 文件面板（标题条与两块正文）/ 传输抽屉 / 状态栏 / 标题栏。
document.addEventListener("contextmenu", (ev) => ev.preventDefault(), { capture: true });

const sidebarEl = document.querySelector(".sidebar");
const titlebarEl = document.querySelector(".titlebar");
const statusEl = document.querySelector(".statusbar");
const drawerEl = document.getElementById("drawer");
const filesPaneEl = document.querySelector(".pane.files");

// 会话栏空白处：新建、导入、收起；点在会话行/分组头上时不抢，那两处有自己的菜单
sidebarEl.addEventListener("contextmenu", (ev) => {
  if (ev.target.closest(".sess-row, .sess-group, button, input, .menu")) return;
  showCtx(ev.clientX, ev.clientY, [
    { label: "新建连接", hint: "Ctrl+N", run: () => openConnect() },
    {
      label: "导入会话",
      hint: "SSH 配置 / Xshell / WinSCP",
      run: () => document.getElementById("btn-import").click(),
    },
    { sep: true },
    {
      label: "收起会话栏",
      hint: "Ctrl+Alt+B",
      disabled: sidebarFolded,
      run: () => applyFold(true),
    },
  ]);
});

// 标签条空白处：这块以前是浏览器菜单的重灾区（标题栏那么长一条空白）
document.getElementById("tabs").addEventListener("contextmenu", (ev) => {
  if (ev.target.closest(".tab")) return; // 标签项自己的菜单
  showCtx(ev.clientX, ev.clientY, [
    { label: "新建连接", hint: "Ctrl+N", run: () => openConnect() },
    {
      label: "关闭当前标签",
      hint: "Ctrl+W",
      disabled: tabs.length < 2,
      run: () => closeTab(activeId),
    },
  ]);
});

// 文件面板标题条：折叠/展开与刷新，别的地方点不到这两个常驻动作
filesPaneEl.querySelector(".pane-head").addEventListener("contextmenu", (ev) => {
  showCtx(ev.clientX, ev.clientY, [
    {
      label: filesFolded ? "展开文件面板" : "折叠文件面板",
      hint: "Ctrl+Alt+F",
      run: () => applyFilesFold(!filesFolded),
    },
    { sep: true },
    { label: "刷新两侧目录", run: () => refreshBothDirs() },
  ]);
});

// 终端面板标题条：和面板里的功能对应——查找、清屏、文件面板收放
document.querySelector(".pane.term .pane-head").addEventListener("contextmenu", (ev) => {
  showCtx(ev.clientX, ev.clientY, [
    { label: "查找", hint: "Ctrl+F", run: () => findToggle(true) },
    { label: "清屏", hint: "Ctrl+L", run: () => sendRaw(activeCell(), "\f") },
    { sep: true },
    {
      label: filesFolded ? "展开文件面板" : "折叠文件面板",
      hint: "Ctrl+Alt+F",
      run: () => applyFilesFold(!filesFolded),
    },
  ]);
});

// 文件面板两块正文的空白处（不在文件行上）：远端给"刷新/新建目录/上一层"，本地给"刷新/上一层"
for (const block of filesPaneEl.querySelectorAll(".fp-block")) {
  const side = block.dataset.side;
  block.addEventListener("contextmenu", (ev) => {
    if (ev.target.closest(".fp-row")) return; // 文件行有自己的菜单
    if (ev.target.closest(".fp-path, input")) return; // 地址栏留给输入框本身
    const items =
      side === "remote"
        ? [
            { label: "刷新远端目录", run: () => loadRemote(document.getElementById("remote-path").value || "/") },
            { label: "新建目录", hint: "在这个目录里建", run: () => newRemoteDir() },
            { sep: true },
            { label: "回到上一级", run: () => document.getElementById("remote-up").click() },
          ]
        : [
            { label: "刷新本地目录", run: () => loadLocal(document.getElementById("local-path").value || "") },
            { sep: true },
            { label: "回到上一级", run: () => document.getElementById("local-up").click() },
          ];
    showCtx(ev.clientX, ev.clientY, items);
  });
}

// 传输抽屉：右键只管这条抽屉自己的收放，不做队列操作（队列行还没做单条取消）
drawerEl.addEventListener("contextmenu", (ev) => {
  if (ev.target.closest(".drawer-head button")) return;
  const collapsed = drawerEl.classList.contains("collapsed");
  showCtx(ev.clientX, ev.clientY, [
    {
      label: collapsed ? "展开传输队列" : "收起传输队列",
      hint: "只留一行",
      run: () => document.getElementById("drawer-head").click(),
    },
  ]);
});

// 状态栏：把诊断信息捞出来最快的地方，出事时用户第一反应就是往这儿一点
statusEl.addEventListener("contextmenu", (ev) => {
  showCtx(ev.clientX, ev.clientY, [
    { label: "复制诊断信息", hint: "版本 / 系统 / 最近日志", run: () => document.getElementById("btn-log-copy").click() },
    { label: "打开运行日志", run: () => document.getElementById("btn-log-open").click() },
  ]);
});

// 标题栏空白处：窗口自己的三个动作，跟右上角按钮一一对应
titlebarEl.addEventListener("contextmenu", (ev) => {
  // 标签条是标题栏里的一大块，它有自己的菜单，别被这里的窗口菜单抢走
  if (ev.target.closest("button, .tab, #tabs")) return;
  const maxed = document.getElementById("btn-max").getAttribute("aria-label") === "还原";
  showCtx(ev.clientX, ev.clientY, [
    { label: "最小化", run: () => windowAction("minimize") },
    { label: maxed ? "还原窗口" : "最大化", run: () => windowAction("maximize") },
    { sep: true },
    { label: "关闭 Portio", run: () => windowAction("close") },
  ]);
});

// #fold-test：文件面板折叠的回归门禁。量真实栅格（终端宽、文件面板宽、把手宽），结果写 <title>。
// 折叠要求：文件面板宽度归 0、终端吃满整列、把手正好 10px 且换成 ‹ 字形。
if (location.hash.includes("fold-test")) {
  document.body.classList.add("dragging"); // 关过渡，只量终态
  const w = (sel) => document.querySelector(sel).getBoundingClientRect().width;
  const gv = document.getElementById("gutter-split");
  const rows = [];
  const snap = (tag) => {
    rows.push({
      tag,
      cls: splitEl.classList.contains("files-folded"),
      term: Math.round(w(".pane.term")),
      files: Math.round(w(".pane.files")),
      gutter: Math.round(w("#gutter-split")),
      split: Math.round(w("#split")),
      glyph: getComputedStyle(gv, "::after").content,
    });
  };
  applyFilesFold(false);
  snap("open");
  applyFilesFold(true);
  snap("fold");
  applyFilesFold(false);
  snap("back");
  const f = rows[1];
  const checks = [
    f.cls === true,
    f.files === 0,
    Math.abs(f.term - (f.split - 10)) <= 1,
    f.gutter === 10,
    f.glyph.includes("‹"),
    rows[2].cls === false && rows[2].files > 0,
  ];
  const ok = checks.every(Boolean);
  document.title = ok
    ? `FOLD-SELFTEST-OK ${JSON.stringify(rows)}`
    : `FOLD-SELFTEST-FAIL ${JSON.stringify(rows)}`;
}

// #ctx-test：九处面板右键菜单的回归门禁。
// 判两件事：①每个面板都得把浏览器默认菜单拦下来（defaultPrevented 为真）；
// ②每个面板开出来的是"自己那份"菜单——条目文字逐条比对，防止某处被邻居的菜单抢走。
// 动态文案（折叠/展开、收起/展开、最大化/还原）两种写法都算过。
if (location.hash.includes("ctx-test")) {
  const cases = [
    { name: "会话栏", el: sidebarEl, items: ["新建连接", "导入会话", "收起会话栏"], alt: ["新建连接", "导入会话", "收起会话栏"] },
    { name: "标签条", el: document.getElementById("tabs"), items: ["新建连接", "关闭当前标签"], alt: ["新建连接", "关闭当前标签"] },
    { name: "文件面板标题条", el: filesPaneEl.querySelector(".pane-head"), items: ["折叠文件面板", "刷新两侧目录"], alt: ["展开文件面板", "刷新两侧目录"] },
    { name: "文件面板·远端", el: filesPaneEl.querySelector('[data-side="remote"]'), items: ["刷新远端目录", "新建目录", "回到上一级"], alt: ["刷新远端目录", "新建目录", "回到上一级"] },
    { name: "文件面板·本地", el: filesPaneEl.querySelector('[data-side="local"]'), items: ["刷新本地目录", "回到上一级"], alt: ["刷新本地目录", "回到上一级"] },
    { name: "终端标题条", el: document.querySelector(".pane.term .pane-head"), items: ["查找", "清屏", "折叠文件面板"], alt: ["查找", "清屏", "展开文件面板"] },
    { name: "传输抽屉", el: drawerEl, items: ["收起传输队列"], alt: ["展开传输队列"] },
    { name: "状态栏", el: statusEl, items: ["复制诊断信息", "打开运行日志"], alt: ["复制诊断信息", "打开运行日志"] },
    { name: "标题栏", el: titlebarEl, items: ["最小化", "最大化", "关闭 Portio"], alt: ["最小化", "还原窗口", "关闭 Portio"] },
  ];
  const bad = [];
  for (const c of cases) {
    ctxMenu.classList.remove("open");
    ctxMenu.innerHTML = "";
    const ev = new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: 200, clientY: 200 });
    c.el.dispatchEvent(ev);
    const labels = [...ctxMenu.querySelectorAll(".ctx-item > span:first-child")].map((n) => n.textContent);
    const namesOk =
      labels.length === c.items.length &&
      c.items.every((want, i) => labels[i] === want || labels[i] === c.alt[i]);
    const ok = ev.defaultPrevented && ctxMenu.classList.contains("open") && namesOk;
    if (!ok) {
      bad.push({ name: c.name, prevented: ev.defaultPrevented, open: ctxMenu.classList.contains("open"), labels });
    }
  }
  ctxMenu.classList.remove("open");
  ctxMenu.innerHTML = "";
  document.title = bad.length === 0
    ? `CTX-SELFTEST-OK ${cases.length}`
    : `CTX-SELFTEST-FAIL ${JSON.stringify(bad)}`;
}

// #narrow-test：窄窗布局门禁。无头里用 --window-size 换宽度跑同一页，量的是真实几何。
// 收三类用户亲自报过的问题：导入下拉的条目会溢到侧栏外；传输队列收起后还留半截空白；
// 文件面板"能完全折叠"到底是不是真折叠（折叠后终端必须吃满整列）。
// 另加两条兜底：整页不许有横向滚动条，右键菜单贴到窗口右缘必须往回收。
if (location.hash.includes("narrow-test")) {
  document.body.classList.add("dragging", "dragging-x"); // 关过渡，只量终态
  const rect = (el) => el.getBoundingClientRect();
  const bad = [];
  const rows = {};
  const W = window.innerWidth;

  // 侧栏按最窄（180）算，这是菜单最容易被挤出去的情形
  const prevSide = parseFloat(getComputedStyle(root).getPropertyValue("--sidebar")) || 264;
  const prevFoldedMain = mainEl.classList.contains("collapsed");
  mainEl.classList.remove("collapsed");
  applySidebar(PREF.sidebar.min);

  // ① 导入下拉：整条落在侧栏里，条目文字不出菜单边框
  const trigger = document.getElementById("btn-import");
  const menu = document.getElementById("import-menu");
  menu.hidden = false;
  trigger.setAttribute("aria-expanded", "true");
  const side = rect(sidebarEl);
  const m = rect(menu);
  const items = [...menu.querySelectorAll(".item")];
  const itemRight = Math.max(...items.map((it) => rect(it).right));
  const itemLeft = Math.min(...items.map((it) => rect(it).left));
  rows.menu = {
    sideW: Math.round(side.width),
    gapToSideRight: Math.round(side.right - m.right),
    itemOverMenuRight: Math.round(itemRight - m.right),
    itemOverMenuLeft: Math.round(m.left - itemLeft),
    items: items.length,
  };
  if (m.right > side.right + 0.5) bad.push(`导入下拉右侧越出侧栏 ${Math.round(m.right - side.right)}px`);
  if (m.left < side.left - 0.5) bad.push(`导入下拉左侧越出侧栏 ${Math.round(side.left - m.left)}px`);
  if (itemRight > m.right + 0.5) bad.push(`导入条目文字越出菜单右侧 ${Math.round(itemRight - m.right)}px`);
  if (itemLeft < m.left - 0.5) bad.push(`导入条目文字越出菜单左侧 ${Math.round(m.left - itemLeft)}px`);
  // 光是盒子在框内不算数：条目里的文字得真被裁住。条目自己 overflow 可见、文字又比盒子宽，
  // 就是用户截图里那种"字跑到菜单边框外面、再被侧栏边缘切掉"的样子。
  for (const it of items) {
    const cs = getComputedStyle(it);
    const over = it.scrollWidth - it.clientWidth;
    if (over > 1 && cs.overflowX === "visible") {
      bad.push(`导入条目「${it.textContent.trim()}」文字比盒子宽 ${over}px 且没裁住`);
    }
  }
  const acts = document.getElementById("sess-actions");
  rows.menu.actionsOverflow = acts.scrollWidth - acts.clientWidth;
  if (acts.scrollWidth > acts.clientWidth + 1) {
    bad.push(`动作行横向溢出 ${acts.scrollWidth - acts.clientWidth}px（菜单会被侧栏边缘切掉）`);
  }

  // ② 传输队列收起后只占一行（等于标题条高度），正文整块不占地方
  const prevDrawer = parseFloat(getComputedStyle(root).getPropertyValue("--drawer")) || 172;
  applyDrawer(PREF.drawer.min);
  const dBox = rect(drawerEl);
  const dHead = rect(document.getElementById("drawer-head"));
  const dBody = rect(document.querySelector(".drawer-body"));
  rows.drawer = { h: Math.round(dBox.height), head: Math.round(dHead.height), body: Math.round(dBody.height) };
  if (!drawerEl.classList.contains("collapsed")) bad.push("抽屉收到一行高却没进 collapsed 态");
  if (Math.abs(dBox.height - dHead.height) > 1) bad.push(`抽屉收起后 ${Math.round(dBox.height)}px，标题条 ${Math.round(dHead.height)}px，不是一行`);
  if (dBody.height > 0.5) bad.push(`抽屉收起后正文还占 ${Math.round(dBody.height)}px`);

  // ③ 文件面板完全折叠：面板宽度归 0、终端吃满整列、把手还是 10px
  const prevFolded = filesFolded;
  applyFilesFold(true);
  const sp = rect(splitEl);
  const fp = rect(filesPaneEl);
  const tp = rect(document.querySelector(".pane.term"));
  const gp = rect(document.getElementById("gutter-split"));
  rows.fold = {
    split: Math.round(sp.width),
    files: Math.round(fp.width),
    term: Math.round(tp.width),
    gutter: Math.round(gp.width),
  };
  if (fp.width > 0.5) bad.push(`文件面板折叠后还剩 ${Math.round(fp.width)}px 宽`);
  if (Math.abs(tp.width - (sp.width - gp.width)) > 1) bad.push("文件面板折叠后终端没吃满整列");
  if (gp.width < 9 || gp.width > 11) bad.push(`折叠态把手 ${Math.round(gp.width)}px，应为 10px`);

  // ④ 整页不许有横向滚动条
  const doc = document.documentElement;
  if (doc.scrollWidth > W + 0.5) bad.push(`整页出现横向滚动 ${Math.round(doc.scrollWidth - W)}px`);

  // ⑤ 窄窗下模态不能被挤出窗口：「完成」按钮得在窗里，卡片四条边都得留出余量
  const settingsModal = document.getElementById("settings-modal");
  const wasOpen = settingsModal.classList.contains("open");
  if (!wasOpen) settingsModal.classList.add("open");
  const sheet = rect(settingsModal.querySelector(".sheet"));
  const done = rect(document.getElementById("btn-set-close"));
  rows.sheet = { w: Math.round(sheet.width), h: Math.round(sheet.height), rightGap: Math.round(W - sheet.right), bottomGap: Math.round(window.innerHeight - sheet.bottom) };
  if (sheet.right > W - 4) bad.push(`设置卡片右侧越出窗口 ${Math.round(sheet.right - W)}px`);
  if (sheet.left < 4) bad.push(`设置卡片左侧越出窗口 ${Math.round(-sheet.left)}px`);
  if (done.right > W - 4 || done.left < 0) bad.push("「完成」按钮被挤出窗口");
  if (sheet.height > window.innerHeight) bad.push(`设置卡片高 ${Math.round(sheet.height)}px 超过视口`);
  if (!wasOpen) settingsModal.classList.remove("open");

  // ⑥ 右键菜单贴到窗口右缘要往回收（窄窗最容易越界）
  showCtx(W + 200, 120, [{ label: "窄窗内收", run() {} }]);
  const cBox = rect(ctxMenu);
  if (cBox.right > W - 5) bad.push(`右键菜单右侧越出视口 ${Math.round(cBox.right - W)}px`);
  if (cBox.left < 0) bad.push(`右键菜单左侧越出视口 ${Math.round(-cBox.left)}px`);

  // 收拾现场：菜单收起、折叠与宽度都还原
  hideCtx();
  applyFilesFold(prevFolded);
  applyDrawer(prevDrawer);
  applySidebar(prevSide);
  if (prevFoldedMain) mainEl.classList.add("collapsed");
  menu.hidden = true;
  trigger.setAttribute("aria-expanded", "false");
  document.body.classList.remove("dragging", "dragging-x");

  document.title = bad.length === 0
    ? `NARROW-SELFTEST-OK w=${W} ${JSON.stringify(rows)}`
    : `NARROW-SELFTEST-FAIL w=${W} ${JSON.stringify(bad)} ${JSON.stringify(rows)}`;
}

// #theme-test：主题门禁。深 / 浅两套主题各量一遍同一组分区，比左上角与宽高——
// 主题只管颜色，几何一律不许动（用户报过"切完主题有组件错位"）。
// 再把令牌的对比度算一遍，防止哪天为了好看把分隔线调成看不见、或者把弱化文字调成读不出。
if (location.hash.includes("theme-test")) {
  const rect = (el) => el.getBoundingClientRect();
  const bad = [];
  const rows = {};

  // 令牌值是 #rrggbb 原样拿回来，换成线性亮度后按 WCAG 算对比度
  const toRgb = (v) => {
    const s = String(v || "").trim();
    if (!s.startsWith("#")) return null;
    const h = s.slice(1);
    const f = h.length === 3 ? [...h].map((c) => c + c).join("") : h;
    if (f.length !== 6) return null;
    return [0, 2, 4].map((i) => parseInt(f.slice(i, i + 2), 16));
  };
  const lin = (c) => {
    const x = c / 255;
    return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
  };
  const lum = (rgb) => 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2]);
  const ratio = (a, b) => {
    const la = lum(a), lb = lum(b);
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
  };

  const col = (name) => {
    const v = getComputedStyle(root).getPropertyValue(name);
    const rgb = toRgb(v);
    if (!rgb) bad.push(`令牌 ${name} 不是 #rrggbb 形态：${v || "空"}`);
    return rgb;
  };

  const marks = () => {
    const o = {};
    const put = (key, el) => {
      if (!el) { bad.push(`量不到 ${key}`); return; }
      const r = rect(el);
      o[key] = [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)];
      if (r.width < 1 || r.height < 1) bad.push(`${key} 尺寸为 0`);
    };
    put("titlebar", document.querySelector(".titlebar"));
    put("sidebar", sidebarEl);
    put("tabs", document.getElementById("tabs"));
    put("term", document.querySelector(".pane.term"));
    put("termhead", document.querySelector(".pane.term .pane-head"));
    put("files", document.querySelector(".pane.files"));
    put("remote", document.querySelector('.fp-block[data-side="remote"]'));
    put("local", document.querySelector('.fp-block[data-side="local"]'));
    put("drawer", drawerEl);
    put("statusbar", document.querySelector(".statusbar"));
    put("themeBtn", document.getElementById("btn-theme"));
    return o;
  };

  const prevPref = localStorage.getItem("portio.theme") || "dark";
  const geom = {};
  const tok = {};
  for (const t of ["dark", "light"]) {
    applyTheme(t);
    void document.body.offsetHeight; // 强制一次重排：量终态，不量过渡中间
    if (root.dataset.theme !== t) bad.push(`applyTheme("${t}") 之后 data-theme 是 ${root.dataset.theme}`);
    geom[t] = marks();
    tok[t] = {
      surface: col("--surface"), bg: col("--bg"), line: col("--line"), strong: col("--line-strong"),
      text: col("--text"), text2: col("--text-2"), text3: col("--text-3"),
    };
    const sun = rect(document.querySelector("#btn-theme .i-sun"));
    const moon = rect(document.querySelector("#btn-theme .i-moon"));
    rows[t] = { sun: Math.round(sun.width), moon: Math.round(moon.width), contrast: {} };
    if (t === "light" && !(sun.width > 0 && moon.width === 0)) bad.push("浅色下主题按钮没换成太阳图标");
    if (t === "dark" && !(moon.width > 0 && sun.width === 0)) bad.push("深色下主题按钮没换成月亮图标");
  }

  // ① 几何：每个分区的左上角与宽高，两套主题下必须一样（主题只该动颜色）
  let worst = 0;
  for (const key of Object.keys(geom.dark)) {
    const a = geom.dark[key], b = geom.light[key];
    if (!a || !b) continue;
    const d = Math.max(...a.map((v, i) => Math.abs(v - b[i])));
    worst = Math.max(worst, d);
    if (d > 1) bad.push(`${key} 切主题后错位 ${d}px（深 ${a} / 浅 ${b}）`);
  }
  rows.landmarks = Object.keys(geom.dark).length;
  rows.worstShift = worst;

  // ② 对比度：分隔线要看得见但不抢戏；正文、次要、弱化三档各自有下限
  const need = [
    ["line", "surface", 1.25, "分隔线对面板底"],
    ["line", "bg", 1.2, "分隔线对窗口底"],
    ["strong", "surface", 1.5, "强分隔线对面板底"],
    ["text", "surface", 10, "正文对面板底"],
    ["text2", "surface", 4.5, "次要文字对面板底"],
    ["text3", "surface", 2.9, "弱化文字对面板底"],
  ];
  for (const t of ["dark", "light"]) {
    for (const [fgs, bgs, min, why] of need) {
      const r = ratio(tok[t][fgs], tok[t][bgs]);
      rows[t].contrast[`${fgs}/${bgs}`] = Number(r.toFixed(2));
      if (r < min) bad.push(`${t} 主题${why}只有 ${r.toFixed(2)}，低于 ${min}`);
    }
  }

  applyTheme(prevPref); // 量完把主题还原成用户原来那档
  document.title = bad.length === 0
    ? `THEME-SELFTEST-OK ${JSON.stringify(rows)}`
    : `THEME-SELFTEST-FAIL ${JSON.stringify(bad)} ${JSON.stringify(rows)}`;
}

// ---------- #find-test：查找门禁（M9） ----------
// 查找这件事出错会很安静：计数多了少了、跳过去高亮的不是那一条、没命中却不变红，
// 用户只会觉得"这搜索怎么不准"，说不出哪儿不对。所以把它拆成可数的几件事：
// ① 计数与我自己重扫一遍 buffer 的结果一致 ② 每条命中的行列坐标确实落在查询词上
// ③ 首跳落在第 1 条并选中它 ④ 环回序号算得对 ⑤ 无命中转红、恢复后摘红
// ⑥ 查找条不越出终端面板、不压标题条 ⑦ 关掉后选区与序号都收拾干净。
// ⑧ 长 buffer（宽字符 / emoji / 组合字符 / ANSI / 居中 / 贴底）⑨ 跨折行命中（折点上那半截、硬换行不许拼）。
if (location.hash.startsWith("#find-test")) {
  document.body.classList.add("dragging", "dragging-x"); // 关过渡，只量终态
  const bad = [];
  const seen = {};
  const q = "Portio";

  // 自己重扫一遍 buffer，不借 findScan——自己验自己没有意义
  function recount(needle) {
    const buf = term?.buffer.active;
    if (!buf) return [];
    const out = [];
    const low = needle.toLowerCase();
    for (let row = 0; row < buf.length; row += 1) {
      const line = buf.getLine(row);
      if (!line) continue;
      const text = line.translateToString(true);
      const hay = text.toLowerCase();
      let at = hay.indexOf(low);
      while (at !== -1) {
        out.push({ row, col: at });
        at = hay.indexOf(low, at + low.length);
      }
    }
    return out;
  }

  // 逐格重扫：宽字符占两格却只出一个字符，所以"字符下标"和"格号"是两件事。
  // 这个函数按格走、把每个字符记到它所在的格号上，命中给的是真格号——用来抓
  // "把字符下标当格号，遇到中文就整体偏一位"这类退化。
  function recountCells(needle) {
    const buf = term?.buffer.active;
    if (!buf) return [];
    const out = [];
    const low = needle.toLowerCase();
    for (let row = 0; row < buf.length; row += 1) {
      const line = buf.getLine(row);
      if (!line) continue;
      let chars = "";
      const cellOf = [];
      for (let c = 0; c < line.length; c += 1) {
        const cell = line.getCell(c);
        const s = cell ? cell.getChars() : "";
        for (let k = 0; k < s.length; k += 1) cellOf.push(c);
        chars += s;
      }
      const hay = chars.toLowerCase();
      let at = hay.indexOf(low);
      while (at !== -1) {
        out.push({ row, col: cellOf[at] });
        at = hay.indexOf(low, at + low.length);
      }
    }
    return out;
  }

  function run() {
    findToggle(true);
    findInput.value = q;
    findRefresh();

    // ① 计数：自扫条数 vs 查找认为的条数 vs 面板上那行字
    const mine = recount(q);
    seen.hits = mine.length;
    seen.label = findCount.textContent;
    if (!mine.length) bad.push(`终端里扫不到 ${q}，用例前提没成立`);
    if (mine.length !== findHits.all.length) {
      bad.push(`条数不一致：自扫 ${mine.length} 条，查找认为 ${findHits.all.length} 条`);
    }
    if (findCount.textContent !== `1/${mine.length}`) {
      bad.push(`计数文字是 ${findCount.textContent}，应为 1/${mine.length}`);
    }

    // ② 坐标：逐条真的跳过去，看终端选出来的是不是查询词本身
    //    （选区是按格取的，所以这条同时验了"列号是格号而不是字符下标"——中文行上会露馅）
    const offBy = [];
    for (let i = 0; i < findHits.all.length; i += 1) {
      findHits.at = i - 1;
      findJump(1);
      const got = term.getSelection();
      if (got.toLowerCase() !== q.toLowerCase()) offBy.push({ i, row: findHits.all[i].row, got });
    }
    if (offBy.length) bad.push(`按命中跳过去，选出来的不是查询词：${JSON.stringify(offBy.slice(0, 3))}`);

    // ③ 首跳落在第 1 条，并真的选中了它
    findHits.at = -1;
    findJump(1);
    const sel = term.getSelection();
    seen.sel = sel;
    if (findHits.at !== 0) bad.push(`首跳应落在第 1 条，实际序号 ${findHits.at}`);
    if (sel.toLowerCase() !== q.toLowerCase()) {
      bad.push(`跳转后选中的是 ${JSON.stringify(sel)}，应等于 ${JSON.stringify(q)}`);
    }

    // ④ 环回：首跳 (-1,+1)→0、(-1,-1)→末条、末条再往后回 0、0 往前回到末条、没有命中返回 -1
    const cases = [[5, -1, 1, 0], [5, -1, -1, 4], [5, 4, 1, 0], [5, 0, -1, 4], [0, 0, 1, -1]];
    seen.step = cases.map(([n, a, d]) => findStep(n, a, d));
    cases.forEach(([n, a, d, want]) => {
      if (findStep(n, a, d) !== want) bad.push(`findStep(${n},${a},${d}) 得 ${findStep(n, a, d)}，应为 ${want}`);
    });
    // 真按一遍末条往后：要绕回第 1 条并选中它
    findHits.at = findHits.all.length - 1;
    findJump(1);
    if (findHits.at !== 0) bad.push(`末条往后应绕回第 1 条，实际序号 ${findHits.at}`);
    if (term.getSelection().toLowerCase() !== q.toLowerCase()) bad.push("绕回第 1 条后选中的不是查询词");

    // ⑤ 无命中转红；把查询词改回来要能摘掉红色
    findInput.value = "__portio_no_such_token__";
    findRefresh();
    seen.nohit = findCount.textContent;
    if (findCount.textContent !== "0/0") bad.push(`无命中时计数应 0/0，实际 ${findCount.textContent}`);
    if (!findCount.classList.contains("bad")) bad.push("无命中时计数没转红（缺 .bad）");
    if (findHits.all.length) bad.push("无命中时不该有命中条目");
    findInput.value = q;
    findRefresh();
    if (findCount.classList.contains("bad")) bad.push("改回有命中的词后红色没摘掉");

    // ⑥ 查找条在终端面板里：不越左右缘、不压标题条、别窄到看不清
    const pane = document.querySelector(".pane.term").getBoundingClientRect();
    const head = document.querySelector(".pane.term .pane-head").getBoundingClientRect();
    const bar = findBar.getBoundingClientRect();
    seen.geom = {
      w: Math.round(bar.width),
      gapRight: Math.round(pane.right - bar.right),
      gapHead: Math.round(bar.top - head.bottom),
    };
    if (bar.right > pane.right + 1) bad.push(`查找条右侧越出终端面板 ${Math.round(bar.right - pane.right)}px`);
    if (bar.left < pane.left - 1) bad.push(`查找条左侧越出终端面板 ${Math.round(pane.left - bar.left)}px`);
    if (bar.top < head.bottom - 1) bad.push(`查找条压住了标题条 ${Math.round(head.bottom - bar.top)}px`);
    if (seen.geom.w < 160) bad.push(`查找条只有 ${seen.geom.w}px 宽，输入框会被挤没`);

    // ⑦ 关掉：open 态撤掉、终端不留高亮、序号复位
    findToggle(false);
    if (findBar.classList.contains("open")) bad.push("关掉后查找条还是 open 态");
    if (term.getSelection()) bad.push("关掉后终端还留着高亮");
    if (findHits.at !== -1) bad.push(`关掉后命中序号没复位（现在 ${findHits.at}）`);

    // 收拾现场：让这个页在真浏览器里打开也回到正常态
    findInput.value = "";
    findHits.q = "";
    findHits.all = [];
    findHits.at = -1;
    findPaint();
    document.body.classList.remove("dragging", "dragging-x");

    longPhase();
  }

  // ---------- ⑧ 长 buffer：写 800 行，每 10 行一处命中（共 80 处）----------
  // 这一段专治"只在短 banner 上看着对"：真实远端输出里有中文（宽字符占两格）、有 emoji（代理对占两格）、
  // 有 ANSI 颜色控制符、有组合字符，而且早就滚进滚动缓冲了。命中落在这些行上，列号一偏就全偏。
  // 800 行是"一天的日志尾巴"的量级，同时也第一次量出"边打边扫"的真实开销。
  const q2 = "Portio_long";
  const LINES = 800;
  const longWant = LINES / 10;

  function longPhase() {
    let block = "";
    for (let i = 1; i <= LINES; i += 1) {
      let body;
      if (i % 10 === 0) {
        const tag = `Portio_long_${String(i).padStart(3, "0")}`;
        if (i % 40 === 20) body = `😀 表情 ${tag} 尾巴`;        // emoji 是代理对：两个 code unit 占两格
        else if (i % 20 === 0) body = `中文宽字符 ${tag} 尾巴`;   // 宽字符在查询词前面，列号要跨过它们
        else body = `\x1b[36m${tag}\x1b[0m 带色`;                // 查询词被 ANSI 颜色包着
      } else if (i % 25 === 0) {
        body = "半个词 Portio_lon 不算命中";                     // 少个尾字母的诱饵：needle 截短时会多算
      } else if (i % 40 === 7) {
        body = "e\u0301 组合字符 也不算命中";                    // 组合字符：一个格子里两个 code unit
      } else {
        body = `第 ${i} 行普通输出，这一行没什么特别的`;
      }
      block += `${body}\r\n`;
    }
    term.write(block);

    let t2 = 0;
    (function waitLong() {
      const got = recount(q2).length;
      if (got < longWant && t2 < 200) {
        t2 += 1;
        setTimeout(waitLong, 50);
        return;
      }
      checkLong(got);
      wrapPhase();
    })();
  }

  // ---------- ⑨ 跨折行：长命令折成两行时，命中的那一截骑在折点上 ----------
  // 逐行扫永远搜不到这种命中，用户只会说"明明终端里有，就是搜不出来"。这里不看条数对不对，
  // 只看三件事：① 拼起来才存在的词要搜得到，且起点落在折点前那一行的确切格号上
  // ② 跳过去选中的是整串（选区真的绕过了折行，不许被截成半截）
  // ③ 两个硬换行各写一半、拼起来正好能凑成的词，不许被算成命中。
  const q3 = "Portio_wrap";
  function wrapPhase() {
    // 填 cols-4 个 w，查询词正好从第 cols-4 格起：前 4 个字符留在折行前那一行
    const filler = "w".repeat(Math.max(1, term.cols - 4));
    term.write(`\r\n${filler}${q3} 尾巴\r\n`);
    term.write("\r\nabc\r\ndef\r\n"); // 诱饵：硬换行两侧各一半，拼起来才是 "abcdef"
    let t3 = 0;
    (function waitWrap() {
      const hit = findScan(q3)[0];
      if (!hit && t3 < 60) {
        t3 += 1;
        setTimeout(waitWrap, 50);
        return;
      }
      checkWrap(hit);
      finish();
    })();
  }

  function checkWrap(hit) {
    const cols = term.cols;
    seen.wrap = { cols, col: hit?.col, span: hit?.span };
    if (!hit) {
      bad.push(`跨折行的 ${q3} 搜不到（退回逐行扫了？）`);
      return;
    }
    const found = findScan(q3);
    if (found.length !== 1) bad.push(`跨折行命中应 1 处，实际 ${found.length} 处`);
    if (hit.col !== cols - 4) bad.push(`折行命中的起点在第 ${hit.col} 格，应为第 ${cols - 4} 格`);
    // 长度必须超出本行剩下的格数，否则说明这一条根本没绕过折行
    const left = cols - hit.col;
    if (!(hit.span > left)) bad.push(`跨折行长度 ${hit.span} 没超出本行剩余 ${left} 格`);

    findInput.value = q3;
    findRefresh();
    findHits.at = -1;
    findJump(1);
    const sel = term.getSelection();
    seen.wrap.sel = sel;
    if (sel.toLowerCase() !== q3.toLowerCase()) {
      bad.push(`跨折行跳过去选中的是 ${JSON.stringify(sel)}，应是整串 ${JSON.stringify(q3)}`);
    }

    findInput.value = "abcdef";
    findRefresh();
    seen.wrap.hard = findHits.all.length;
    if (findHits.all.length !== 0) {
      bad.push(`硬换行两侧各一半的词被算成了 ${findHits.all.length} 处命中，拼折行不能越过硬换行`);
    }

    findInput.value = "";
    findHits.q = "";
    findHits.all = [];
    findHits.at = -1;
    findPaint();
    if (term) term.clearSelection();
  }

  // 量一次"边打边扫"要扫多少东西：每次按键都会把整段 buffer 重扫一遍，
  // 这里记下行数与扫过的字符数——这条判据能抓住"只扫可视区"这种偷工（那样会漏掉滚动缓冲里的命中）。
  // （耗时在这里量不到：无头 Chrome 的虚拟时间把 performance.now 冻在定时器回调里，前后读数完全相同，
  //   所以这里只报规模，不报毫秒。）
  function scanCost(needle) {
    const buf = term.buffer.active;
    let rows = 0;
    let chars = 0;
    for (let row = 0; row < buf.length; row += 1) {
      const line = buf.getLine(row);
      if (!line) continue;
      rows += 1;
      chars += line.translateToString(true).length;
    }
    const got = findScan(needle).length;
    return { rows, chars, hits: got };
  }

  function checkLong(flushed) {
    seen.long = { wrote: longWant, flushed };
    if (flushed !== longWant) bad.push(`长 buffer 素材没写全：应 ${longWant} 处，实际 ${flushed} 处`);

    findInput.value = q2;
    findRefresh();
    const all = findHits.all;
    seen.long.hits = all.length;
    seen.long.label = findCount.textContent;
    if (all.length !== longWant) bad.push(`长 buffer 计数是 ${all.length}，应为 ${longWant}`);
    if (findCount.textContent !== `1/${longWant}`) {
      bad.push(`长 buffer 计数文字是 ${findCount.textContent}，应为 1/${longWant}`);
    }

    // 8a 逐格对：宽字符占两格只出一个字符，字符下标 ≠ 格号，两套扫法必须给出同一个格号
    const cells = recountCells(q2);
    if (cells.length !== all.length) {
      bad.push(`逐格扫得 ${cells.length} 条，查找认为 ${all.length} 条`);
    }
    const off = [];
    for (let i = 0; i < Math.min(cells.length, all.length); i += 1) {
      if (cells[i].row !== all[i].row || cells[i].col !== all[i].col) {
        off.push({ row: all[i].row, findCol: all[i].col, cellCol: cells[i].col });
      }
    }
    if (off.length) {
      bad.push(`列号对不上（把字符下标当成了格号？）：${JSON.stringify(off.slice(0, 3))}`);
    }

    // 8b 逐条跳过去，选区必须是查询词本身——中文行、emoji 行、带色行都走一遍
    const selBad = [];
    for (let i = 0; i < all.length; i += 1) {
      findHits.at = i - 1;
      findJump(1);
      const got = term.getSelection();
      if (got !== q2) selBad.push({ i, row: all[i].row, got });
    }
    if (selBad.length) bad.push(`长 buffer 里跳过去选到的不是查询词：${JSON.stringify(selBad.slice(0, 3))}`);

    // 8c 中间那条要落在视野中间：scrollToLine 的落点就是"命中行 - 半屏"
    const mid = Math.floor(term.rows / 2);
    const buf = term.buffer.active;
    const midAt = Math.floor(all.length / 2);
    findHits.at = midAt - 1;
    findJump(1);
    const hitMid = all[midAt];
    const wantY = Math.min(Math.max(0, hitMid.row - mid), buf.baseY);
    seen.long.center = { at: midAt, row: hitMid.row, viewportY: buf.viewportY, wantY, rows: term.rows, baseY: buf.baseY };
    if (Math.abs(buf.viewportY - wantY) > 1) {
      bad.push(`中间那条没滚到视野中间：viewportY ${buf.viewportY}，应 ${wantY}`);
    }
    if (hitMid.row < buf.viewportY || hitMid.row >= buf.viewportY + term.rows) {
      bad.push(`中间那条不在可视区里：行 ${hitMid.row}、视野 ${buf.viewportY}–${buf.viewportY + term.rows}`);
    }

    // 8d 最后一条：贴底时允许被夹住，但必须真的可见，且确实滚到底
    findHits.at = 0;
    findJump(-1);
    const hitLast = all[all.length - 1];
    seen.long.last = { at: findHits.at, row: hitLast.row, viewportY: buf.viewportY, baseY: buf.baseY, rows: term.rows };
    if (findHits.at !== all.length - 1) bad.push(`往前一步应落到末条，实际序号 ${findHits.at}`);
    if (buf.viewportY !== buf.baseY) bad.push(`末条没把视野滚到底：${buf.viewportY} 而非 ${buf.baseY}`);
    if (hitLast.row < buf.viewportY || hitLast.row >= buf.viewportY + term.rows) {
      bad.push(`末条不在可视区里：行 ${hitLast.row}、视野 ${buf.viewportY}–${buf.viewportY + term.rows}`);
    }

    // 8e 滚进滚动缓冲的旧行还在：整段重扫一遍条数不能变少
    const after = recountCells(q2).length;
    seen.long.after = after;
    if (after !== longWant) bad.push(`滚过之后命中条数掉了：${after}，应为 ${longWant}`);
    if (buf.baseY <= 0) bad.push(`写完 ${LINES} 行都没产生滚动，长 buffer 前提不成立`);

    // 8f "边打边扫"的扫描规模：每次按键都要把整段 buffer 重扫一遍，不能只扫可视区
    //    （只扫可视区会漏掉滚动缓冲里的命中，这条判据专门拦那种偷工）
    const cost = scanCost(q2);
    seen.long.scan = cost;
    if (cost.rows < LINES) bad.push(`只扫到 ${cost.rows} 行，应至少 ${LINES} 行`);
    if (cost.chars < 15000) bad.push(`只扫了 ${cost.chars} 个字符，整段 buffer 应有一万六左右`);
    if (cost.hits !== longWant) bad.push(`扫描复现的命中是 ${cost.hits} 条，应为 ${longWant}`);

    // 收拾现场
    findInput.value = "";
    findHits.q = "";
    findHits.all = [];
    findHits.at = -1;
    findPaint();
    if (term) term.clearSelection();
  }

  function finish() {
    document.title = bad.length === 0
      ? `FIND-SELFTEST-OK ${JSON.stringify(seen)}`
      : `FIND-SELFTEST-FAIL ${JSON.stringify(bad)} ${JSON.stringify(seen)}`;
  }

  // 终端的 banner 是异步写进 buffer 的，等它真落了再开始量（最多等 3 秒）
  // 先自己补一行：一行里塞 4 个大小写不同的查询词，这样"一行多处命中"与"多条环回"才真的被走一遍；
  // 末尾再放两个不带尾字母的 "Porti"，用来验"少扫一个字"这种退化会不会被计数抓到
  term?.write("\r\nPortio / portio / PORTIO —— 三处大小写，另加 Portio 收尾，另有 Porti、Porti 两个半截词\r\n");
  const want = 5;
  let tries = 0;
  (function wait() {
    if (!term) ensureTerminal();
    const got = recount(q).length;
    if (got < want && tries < 60) {
      tries += 1;
      setTimeout(wait, 50);
      return;
    }
    if (!got) bad.push(`等了 3 秒终端 buffer 里还没有 ${q}`);
    else if (got !== want) bad.push(`用例素材条数不对：应 ${want} 处，实际 ${got} 处`);
    run();
  })();
}
// ---------- #find-pane-test：分屏之后，查找只认"当前格" ----------
// M9 以前只验了单格：一格终端里搜索，怎么都对。分屏之后冒出一个真问题——查找条记住的是"上一格的行号"，
// 点一下别的格换焦点，计数还是旧格的、Enter 跳过去在**新格**的错行上高亮。用户看到的是"计数有、地方不对"，
// 这种 bug 不会报错，只会让人觉得"搜索不准"。这段把四格各写进自己的标记词，然后走一遍：
//   ① A 格开着查找条查到 3 处并选中第 1 处；② 切到 C 格（等价于点一下那格）——计数、命中、选区都必须立刻换成 C 格的；
//   ③ 在 C 格查它自己的词，逐条跳转只许动 C 格；④ 切回 B 格，计数再换一次；⑤ 关掉后四格都不许留高亮。
if (location.hash === "#find-pane-test") {
  (function paneFindTest() {
    document.body.classList.add("dragging", "dragging-x"); // 关过渡，只量终态
    const bad = [];
    const seen = {};
    const tab = tabById(activeId);
    if (!tab) {
      document.title = "FIND-PANE-SELFTEST-FAIL no-tab";
      return;
    }

    // 一格 → 四格（点标题条上的分屏钮走的是同一个函数）
    while (tab.cells.length < 4) splitTab(tab, "v");
    const cells = tab.cells;
    const marks = ["TOKENA", "TOKENB", "TOKENC", "TOKEND"];
    const wants = [3, 1, 2, 1];

    // 按格扫一遍某一格的 buffer（不借 findScan，免得自己验自己）
    function recountIn(t, needle) {
      const buf = t?.buffer.active;
      if (!buf) return [];
      const out = [];
      const low = needle.toLowerCase();
      for (let row = 0; row < buf.length; row += 1) {
        const line = buf.getLine(row);
        if (!line) continue;
        const hay = line.translateToString(true).toLowerCase();
        let at = hay.indexOf(low);
        while (at !== -1) {
          out.push({ row, col: at });
          at = hay.indexOf(low, at + low.length);
        }
      }
      return out;
    }

    // 四格各写自己的标记词，别格的词一格都不许出现——判"搜错了格"全靠这个。
    // 标记词放在行首：分屏之后每格只有二十来列，词要是不够前面就会被折到下一行，
    // 那样"按整词搜"会搜不到（第一版就是这么假失败的）。
    cells.forEach((c, i) => {
      let block = "";
      for (let k = 0; k < wants[i]; k += 1) block += `${marks[i]} 第 ${k + 1} 处，中文尾巴\r\n`;
      c.term.write(block);
    });

    let tries = 0;
    (function waitFlush() {
      const ready = cells.every((c, i) => recountIn(c.term, marks[i]).length >= wants[i]);
      if (!ready && tries < 80) {
        tries += 1;
        setTimeout(waitFlush, 50);
        return;
      }
      if (!ready) {
        const got = cells.map((c, i) => recountIn(c.term, marks[i]).length);
        seen.debug = {
          cells: cells.length,
          bufLen: cells.map((c) => c.term.buffer.active.length),
          line0: cells.map((c) => (c.term.buffer.active.getLine(0)?.translateToString(true) ?? "").slice(0, 32)),
        };
        bad.push(`四格素材没写全：实际 ${JSON.stringify(got)}，应 ${JSON.stringify(wants)}`);
        finish();
        return;
      }
      run();
    })();

    function othersClean(except) {
      return cells.filter((c) => c !== except && c.term.getSelection()).map((c) => c.id);
    }

    function run() {
      // ① A 格：查到 3 处，首跳选中第 1 处
      setActiveCell(tab, cells[0]);
      findToggle(true);
      findInput.value = marks[0];
      findRefresh();
      seen.a = { label: findCount.textContent, hits: findHits.all.length };
      if (findHits.all.length !== wants[0]) bad.push(`A 格应查 ${wants[0]} 处，实际 ${findHits.all.length} 处`);
      if (findCount.textContent !== `1/${wants[0]}`) {
        bad.push(`A 格计数文字是 ${findCount.textContent}，应 1/${wants[0]}`);
      }
      if (cells[0].term.getSelection() !== marks[0]) {
        bad.push(`A 格跳转后选中的是 ${JSON.stringify(cells[0].term.getSelection())}`);
      }

      // ② 切到 C 格：这个查询词在 C 格里一处都没有，计数必须立刻变成 0/0 并转红
      setActiveCell(tab, cells[2]);
      seen.switch = {
        label: findCount.textContent,
        hits: findHits.all.length,
        termIsC: findHits.term === cells[2].term,
        aSel: cells[0].term.getSelection(),
      };
      if (!seen.switch.termIsC) bad.push("切格之后查找还记着上一格的 buffer（没有重扫）");
      if (findHits.all.length !== 0) {
        bad.push(`C 格里一处 ${marks[0]} 都没有，却报了 ${findHits.all.length} 处`);
      }
      if (findCount.textContent !== "0/0") bad.push(`切格后计数应 0/0，实际 ${findCount.textContent}`);
      if (!findCount.classList.contains("bad")) bad.push("切格后无命中没转红");
      if (seen.switch.aSel !== "") bad.push("A 格还留着上一轮查询的高亮");

      // ③ C 格查自己的词：2 处，逐条跳转只许动 C 格
      findInput.value = marks[2];
      findRefresh();
      seen.c = { label: findCount.textContent, hits: findHits.all.length };
      if (findHits.all.length !== wants[2]) bad.push(`C 格应查 ${wants[2]} 处，实际 ${findHits.all.length} 处`);
      if (findCount.textContent !== `1/${wants[2]}`) {
        bad.push(`C 格计数文字是 ${findCount.textContent}，应 1/${wants[2]}`);
      }
      const cBad = [];
      for (let i = 0; i < findHits.all.length; i += 1) {
        findHits.at = i - 1;
        findJump(1);
        if (cells[2].term.getSelection() !== marks[2]) {
          cBad.push({ i, row: findHits.all[i].row, got: cells[2].term.getSelection() });
        }
      }
      seen.c.jumps = cBad.length;
      if (cBad.length) bad.push(`C 格里跳转选到的不是查询词：${JSON.stringify(cBad.slice(0, 3))}`);
      const dirty = othersClean(cells[2]);
      if (dirty.length) bad.push(`跳转把选区留在了别的格：${JSON.stringify(dirty)}`);

      // ④ 切回 B 格：B 格的词只有 1 处，计数跟着换成 B 格的
      findInput.value = marks[1];
      findRefresh(); // 此时还在 C 格，B 格的词在 C 格里 0 处
      if (findHits.all.length !== 0) bad.push(`C 格里不该有 ${marks[1]}`);
      setActiveCell(tab, cells[1]);
      seen.b = { label: findCount.textContent, hits: findHits.all.length };
      if (findHits.all.length !== wants[1]) bad.push(`B 格应查 ${wants[1]} 处，实际 ${findHits.all.length} 处`);
      if (findCount.textContent !== `1/${wants[1]}`) {
        bad.push(`B 格计数文字是 ${findCount.textContent}，应 1/${wants[1]}`);
      }
      if (cells[1].term.getSelection() !== marks[1]) bad.push("B 格跳转没选中查询词");

      // ⑤ 关掉：四格都不许留高亮，序号复位
      findToggle(false);
      const left = cells.filter((c) => c.term.getSelection()).map((c) => c.id);
      if (left.length) bad.push(`关掉查找后还有格留着高亮：${JSON.stringify(left)}`);
      if (findHits.at !== -1) bad.push(`关掉后命中序号没复位（现在 ${findHits.at}）`);

      // 收拾现场，让这个页在真浏览器里打开也回到正常态
      findInput.value = "";
      findHits.q = "";
      findHits.all = [];
      findHits.at = -1;
      findHits.term = null;
      findPaint();
      document.body.classList.remove("dragging", "dragging-x");
      finish();
    }

    function finish() {
      document.title = bad.length === 0
        ? `FIND-PANE-SELFTEST-OK ${JSON.stringify(seen)}`
        : `FIND-PANE-SELFTEST-FAIL ${JSON.stringify(bad)} ${JSON.stringify(seen)}`;
    }
  })();
}

// ---------- 无头自检：#density-test（密度三档：紧凑 / 标准 / 宽松） ----------
// 设置里能切三档，差别只在 --row（24 / 28 / 32）：面板标题条、文件栏、文件行、
// 传输行都跟着变高。这里量的是"切完高度一定对、位置一点也不许动"：
//   ① 每档 --row 读出来的值与档位对得上（24 / 28 / 32），相邻两档正好差 4px；
//   ② 八处行高元素（会话栏标题、终端标题条、文件标题条、两个文件栏、一条文件行、传输标题条、一条传输行）
//      高度在三档里都严丝合缝等于 --row；
//   ③ 同一个元素在相邻两档之间差的正好是 4px（不多不少）——差多了说明某处用了别的数；
//   ④ 切档只许改高度，左右位置与宽度一点都不许动（横向错位是这类 bug 最常见的样子）；
//   ⑤ 切完窗口不横向溢出、导入菜单不溢出会话栏；
//   ⑥ 设置里的分段控件跟着走，三档来回切都能回到标准。
// 需要人手动塞一条文件行与一条传输行进来量，量完再拿掉。
if (location.hash === "#density-test") {
  (function densityTest() {
    document.body.classList.add("dragging", "dragging-x"); // 关过渡，只量终态
    const bad = [];
    const seen = {};
    const prev = root.dataset.density ?? "standard";

    // 无头下文件列表只有一行提示、传输队列是空的，先塞两条真行进来
    const injected = [];
    function injectRow(host, cls, html) {
      if (!host) return null;
      const row = document.createElement("div");
      row.className = cls;
      row.innerHTML = html;
      host.insertBefore(row, host.firstChild);
      injected.push(row);
      return row;
    }
    const remoteRow = injectRow(
      document.getElementById("remote-list"),
      "fp-row has-perm",
      '<span class="ico">▸</span><span class="nm">etc</span><span class="pm">drwxr-xr-x</span>' +
        '<span class="sz">—</span><span class="tm">2026-11-19 10:24</span>',
    );
    const localRow = injectRow(
      document.getElementById("local-list"),
      "fp-row",
      '<span class="ico">·</span><span class="nm">notes.md</span><span class="sz">1.2 KB</span>' +
        '<span class="tm">2026-11-19 10:24</span>',
    );
    const trHost = document.querySelector(".drawer-body");
    const trRow = injectRow(
      trHost,
      "tr",
      '<span class="ico">↑</span><span class="nm">bundle.zip</span>' +
        '<span class="meta">42% · 1.2 MB/s</span>',
    );

    const landmarks = [
      ["sessHead", () => document.querySelector(".sidebar h2")],
      ["termHead", () => document.querySelector(".pane.term .pane-head")],
      ["filesHead", () => document.querySelector(".pane.files .pane-head")],
      ["remoteBar", () => document.querySelector('.fp-block[data-side="remote"] .fp-bar')],
      ["localBar", () => document.querySelector('.fp-block[data-side="local"] .fp-bar')],
      ["remoteRow", () => remoteRow],
      ["localRow", () => localRow],
      ["drawerHead", () => document.getElementById("drawer-head")],
      ["trRow", () => trRow],
    ];

    function measure(density) {
      applyDensity(density);
      void document.body.offsetHeight; // 强制重排，量终态
      const rowRaw = getComputedStyle(root).getPropertyValue("--row").trim();
      const rowPx = Math.round(parseFloat(rowRaw) * 2) / 2;
      const out = { row: rowPx, raw: rowRaw, items: {} };
      for (const [key, pick] of landmarks) {
        const el = pick();
        if (!el) continue;
        const r = el.getBoundingClientRect();
        out.items[key] = {
          h: Math.round(r.height * 2) / 2,
          left: Math.round(r.left),
          w: Math.round(r.width),
        };
      }
      return out;
    }

    function finish() {
      // 收拾现场：拿掉塞进去的两条、还原密度与 body 类
      for (const row of injected) row.remove();
      applyDensity(prev);
      document.body.classList.remove("dragging", "dragging-x");
      seen.back = { density: root.dataset.density, row: Math.round(parseFloat(getComputedStyle(root).getPropertyValue("--row")) || 0) };
      if (seen.back.density !== prev) bad.push(`切回原档位后是 ${seen.back.density}，应为 ${prev}`);
      const title = bad.length
        ? `DENSITY-SELFTEST-FAIL ${JSON.stringify(bad)} ${JSON.stringify(seen)}`
        : `DENSITY-SELFTEST-OK ${JSON.stringify(seen)}`;
      document.title = title;
    }

    try {
      const std = measure("standard");
      const cmp = measure("compact");
      const wide = measure("comfortable"); // 第三档「宽松」：多一档就必须多量一遍，别只量两档
      seen.standard = std;
      seen.compact = cmp;
      seen.comfortable = wide;
      seen.delta = { row: Math.round((std.row - cmp.row) * 2) / 2, wide: Math.round((wide.row - std.row) * 2) / 2 };

      if (std.row !== 28) bad.push(`标准档 --row 是 ${std.row}px，应为 28px`);
      if (cmp.row !== 24) bad.push(`紧凑档 --row 是 ${cmp.row}px，应为 24px`);
      if (wide.row !== 32) bad.push(`宽松档 --row 是 ${wide.row}px，应为 32px`);
      if (seen.delta.row !== 4) bad.push(`紧凑与标准只该差 4px，实际差 ${seen.delta.row}px`);
      if (seen.delta.wide !== 4) bad.push(`标准与宽松只该差 4px，实际差 ${seen.delta.wide}px`);

      const keys = Object.keys(std.items);
      if (keys.length < landmarks.length) {
        bad.push(`只找到了 ${keys.length} 处行高元素，应有 ${landmarks.length} 处（${JSON.stringify(keys)}）`);
      }
      for (const key of keys) {
        const a = std.items[key];
        const b = cmp.items[key];
        if (!b) {
          bad.push(`${key} 在紧凑档量不到`);
          continue;
        }
        if (Math.abs(a.h - std.row) > 0.6) bad.push(`${key} 标准档高 ${a.h}px，应等于 --row ${std.row}px`);
        if (Math.abs(b.h - cmp.row) > 0.6) bad.push(`${key} 紧凑档高 ${b.h}px，应等于 --row ${cmp.row}px`);
        if (Math.abs((a.h - b.h) - 4) > 0.6) bad.push(`${key} 两档高度差 ${Math.round((a.h - b.h) * 2) / 2}px，应正好 4px`);
        // 第三档「宽松」也要逐处核一遍：加一档最容易漏改某处写死的行高
        const w = wide.items[key];
        if (!w) {
          bad.push(`${key} 在宽松档量不到`);
          continue;
        }
        if (Math.abs(w.h - wide.row) > 0.6) bad.push(`${key} 宽松档高 ${w.h}px，应等于 --row ${wide.row}px`);
        if (Math.abs((w.h - a.h) - 4) > 0.6) bad.push(`${key} 标准→宽松差 ${Math.round((w.h - a.h) * 2) / 2}px，应正好 4px`);
        if (Math.abs(a.left - w.left) > 1) bad.push(`${key} 切到宽松档后左右动了 ${a.left} → ${w.left}`);
        if (Math.abs(a.w - w.w) > 1) bad.push(`${key} 切到宽松档后宽度变了 ${a.w} → ${w.w}`);
        // 切档只许改高度：横向一动就说明有东西重排了
        if (Math.abs(a.left - b.left) > 1) bad.push(`${key} 切档后左右动了 ${a.left} → ${b.left}`);
        if (Math.abs(a.w - b.w) > 1) bad.push(`${key} 切档后宽度变了 ${a.w} → ${b.w}`);
      }

      // 段落控件得跟着走（设置面板打开状态下才量得到，无头里它一直在 DOM 里）
      for (const d of ["compact", "standard", "comfortable"]) {
        applyDensity(d);
        const on = document.querySelector('#seg-density button.on');
        if (!on) bad.push(`${d} 档下设置里的密度控件没有选中项`);
        else if (on.dataset.v !== d) bad.push(`${d} 档下选中的是 ${on.dataset.v}`);
      }

      // 切完不许横向溢出
      applyDensity("compact");
      void document.body.offsetHeight;
      const de = document.documentElement;
      seen.compactOverflow = de.scrollWidth - window.innerWidth;
      if (seen.compactOverflow > 1) bad.push(`紧凑档下窗口横向溢出 ${seen.compactOverflow}px`);
      const actions = document.getElementById("sess-actions");
      if (actions) {
        const over = actions.scrollWidth - actions.clientWidth;
        seen.actionsOverflow = over;
        if (over > 1) bad.push(`紧凑档下导入那排横向溢出 ${over}px`);
      }
    } catch (err) {
      bad.push(`量密度的过程抛了异常：${err && err.message ? err.message : err}`);
    }
    finish();
  })();
}

// ---------- 无头自检：#connect-entry-test（三类连接入口，外加"新建连接必须从空白起"） ----------
// 清单 §2 的 M2 要求"新建连接 / 快速连接一行回车 / 双击会话"三条路都能走到连接面板、字段带对。
// 这三条路最终都落在 openConnect() 上，所以这里按入口一条条点，读面板六个字段。
// 顺带钉死一条容易被忽略的：改过一台密钥登录的会话之后，点「新建连接」必须回到空白——
// 端口回 22、认证回口令、私钥路径清空，两个字段框的显示也跟着换回来。
if (location.hash === "#connect-entry-test") {
  (function connectEntryTest() {
    const bad = [];
    const seen = {};
    const el = (id) => document.getElementById(id);
    const readPanel = () => ({
      open: modal.classList.contains("open"),
      host: el("f-host").value,
      port: el("f-port").value,
      user: el("f-user").value,
      auth: el("f-auth").value,
      key: el("f-key").value,
      pwd: el("f-password").value,
      keyShown: el("field-key").hidden === false,
      pwdShown: el("field-password").hidden === false,
    });
    function expect(tag, got, want) {
      if (JSON.stringify(got) !== JSON.stringify(want)) {
        bad.push(`${tag}：${JSON.stringify(got)} ≠ ${JSON.stringify(want)}`);
      }
    }
    function reset() {
      modal.classList.remove("open");
      sessionStore.records = [];
      renderSessions();
    }

    try {
      // ① 先弄脏：按"密钥 + 2222 端口"的旧会话打开面板，再关掉
      openConnect({
        host: "old.example.com",
        port: 2222,
        user: "root",
        auth: "key",
        keyfile: "C:/Users/me/.ssh/id_ed25519",
      });
      reset();
      el("btn-new").click();
      const fresh = readPanel();
      seen.fresh = fresh;
      expect("新建连接 开面板", fresh.open, true);
      expect("新建连接 主机清空", fresh.host, "");
      expect("新建连接 端口回 22", fresh.port, "22");
      expect("新建连接 认证回口令", fresh.auth, "password");
      expect("新建连接 私钥路径清空", fresh.key, "");
      expect("新建连接 私钥框收起", fresh.keyShown, false);
      expect("新建连接 口令框露出", fresh.pwdShown, true);
      expect("新建连接 口令框清空", fresh.pwd, "");

      // ② 快速连接：一行写完回车
      reset();
      el("quick-input").value = "deploy@10.0.8.12:2222";
      el("quick-input").dispatchEvent(
        new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }),
      );
      const quick = readPanel();
      seen.quick = quick;
      expect("快速连接 开面板", quick.open, true);
      expect("快速连接 主机", quick.host, "10.0.8.12");
      expect("快速连接 端口", quick.port, "2222");
      expect("快速连接 用户", quick.user, "deploy");
      expect("快速连接 认证", quick.auth, "password");
      expect("快速连接 口令框露出", quick.pwdShown, true);

      // ③ 双击会话（口令认证那台；密钥认证双击是直接连，不进面板）
      reset();
      sessionStore.records = [
        {
          name: "svc-01",
          user: "ops",
          host: "svc-01.internal",
          port: 8022,
          auth: "password",
        },
      ];
      renderSessions();
      const row = Array.from(document.querySelectorAll(".sess-row")).find((r) =>
        r.title.includes("ops@svc-01.internal"),
      );
      if (!row) {
        bad.push("双击会话这条测不到：列表里找不到 ops@svc-01.internal 那一行");
      } else {
        row.dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
        const sess = readPanel();
        seen.sess = sess;
        expect("双击会话 开面板", sess.open, true);
        expect("双击会话 主机", sess.host, "svc-01.internal");
        expect("双击会话 端口", sess.port, "8022");
        expect("双击会话 用户", sess.user, "ops");
        expect("双击会话 认证", sess.auth, "password");
        expect("双击会话 口令框露出", sess.pwdShown, true);
      }

      // ④ 快速连接认括号里的 IPv6（顺手钉住解析不把冒号当端口分隔）
      reset();
      el("quick-input").value = "ssh://ops@[fe80::1]:2200";
      el("btn-quick").click();
      const v6 = readPanel();
      seen.ipv6 = v6;
      expect("IPv6 快速连接 主机", v6.host, "fe80::1");
      expect("IPv6 快速连接 端口", v6.port, "2200");
      expect("IPv6 快速连接 用户", v6.user, "ops");

      // ⑤ 空输入不该开面板（只弹一句提示）
      reset();
      el("quick-input").value = "   ";
      el("btn-quick").click();
      expect("空输入 不开面板", readPanel().open, false);
    } catch (err) {
      bad.push(`走连接入口的过程抛了异常：${err && err.message ? err.message : err}`);
    }

    // 收拾现场：清掉塞进去的会话、关掉面板、清空快速连接框
    sessionStore.records = [];
    renderSessions();
    modal.classList.remove("open");
    el("quick-input").value = "";
    document.title = bad.length
      ? `CONNECT-ENTRY-SELFTEST-FAIL ${JSON.stringify(bad)} ${JSON.stringify(seen)}`
      : `CONNECT-ENTRY-SELFTEST-OK ${JSON.stringify(seen)}`;
  })();
}

// ---------- 无头自检：#sessions-test（会话增删改、分组、搜索，以及落盘读回来还认不认"最近用过"） ----------
// 清单 §2 的 M3（会话增删改与分组）里，逻辑部分无头全做得掉：加一条、改参数、分到分组、折叠、移出、解散、删掉、
// 搜一下。唯一不能在这里验的是"真写进 sessions.json"，那半边由 crates/app/src/session_store.rs 的单测兜。
// 这里另外钉住一个真 Bug：时间字段这边写的是 `last`、后端按 `last_used` 读，落盘一次就把"最近用过"抹成 0，
// 重开之后列表全挤进「更早」、「最近使用」一组空着。
if (location.hash === "#sessions-test") {
  (function sessionsTest() {
    const bad = [];
    const seen = {};
    const el = (id) => document.getElementById(id);
    const groupsBackup = localStorage.getItem(GROUPS_KEY);
    const foldBackup = localStorage.getItem(GFOLD_KEY);
    const heads = () =>
      Array.from(document.querySelectorAll(".sidebar .sess-group")).map((h) => ({
        tag: h.dataset.group || "",
        text: (h.textContent || "").replace(/[▾▸]/g, "").replace(/\s+/g, ""),
        folded: h.classList.contains("folded"),
      }));
    const rows = () => Array.from(document.querySelectorAll(".sidebar .sess-row"));
    const rowKeys = () => rows().map((r) => (r.title || "").split(" ·")[0]);
    function expect(tag, got, want) {
      if (JSON.stringify(got) !== JSON.stringify(want)) {
        bad.push(`${tag}：${JSON.stringify(got)} ≠ ${JSON.stringify(want)}`);
      }
    }
    function reset() {
      sessionStore.records = [];
      localStorage.removeItem(GROUPS_KEY);
      localStorage.removeItem(GFOLD_KEY);
      el("sess-search").value = "";
      renderSessions();
    }

    try {
      // ① 增：三条不同机器，最近存的排最前
      reset();
      saveSession({ host: "web-01.prod", port: 22, user: "deploy", auth: "key", keyfile: "~/.ssh/id_ed25519" });
      saveSession({ host: "db-01.prod", port: 2222, user: "dba", auth: "password" });
      saveSession({ host: "stage-01", port: 22, user: "qa", auth: "password" });
      expect("加了三条就是三条", sessionStore.records.length, 3);
      expect("最近存的排最前", sessionStore.records[0].host, "stage-01");
      expect("列表行数", rows().length, 3);
      seen.add = rowKeys();

      // ② 改：同一台机器同一个账号再存一次，不新增一条，内容换成新的并排到最前
      saveSession({ host: "web-01.prod", port: 22, user: "deploy", auth: "key", keyfile: "/home/deploy/.ssh/id_ed25519_v2" });
      expect("改参数不新增一条", sessionStore.records.length, 3);
      expect("改完排到最前", sessionStore.records[0].host, "web-01.prod");
      expect(
        "私钥路径换成新的",
        sessionStore.records[0].keyfile,
        "/home/deploy/.ssh/id_ed25519_v2",
      );
      expect("改完列表还是三行", rows().length, 3);

      // ③ 口令绝不进清单（记进 sessions.json 的是"怎么连"，口令走另一套加密文件）
      const leaky = sessionStore.records.filter((s) => s.password || s.pwd || s.passphrase);
      expect("清单里没有口令字段", leaky.length, 0);

      // ④ 上限：40 条，再存就把最久没用的挤掉
      reset();
      for (let i = 0; i < 45; i += 1) {
        saveSession({ host: `h${i}.example`, port: 22, user: "ops", auth: "password" });
      }
      expect("清单封顶 40 条", sessionStore.records.length, 40);
      expect("最老的被挤掉", sessionStore.records.some((s) => s.host === "h0.example"), false);
      expect("最新的还在", sessionStore.records.some((s) => s.host === "h44.example"), true);

      // ⑤ 分到分组：两组建起来，组头按名字排序、计数对，行数不变
      reset();
      saveSession({ host: "web-01.prod", port: 22, user: "deploy", auth: "password" });
      saveSession({ host: "db-01.prod", port: 2222, user: "dba", auth: "password" });
      saveSession({ host: "stage-01", port: 22, user: "qa", auth: "password" });
      setGroups("deploy@web-01.prod:22", "生产");
      setGroups("dba@db-01.prod:2222", "生产");
      setGroups("qa@stage-01:22", "测试");
      renderSessions();
      const byTag = () => Object.fromEntries(heads().map((h) => [h.tag, h]));
      expect("组头正好两组", Object.keys(byTag()).sort(), ["测试", "生产"].sort());
      expect("生产组计数", byTag()["生产"].text, "生产2");
      expect("测试组计数", byTag()["测试"].text, "测试1");
      expect("分完组行数不变", rows().length, 3);
      seen.groups = heads();

      // ⑥ 折叠：组头带上 folded、组员行收起；折叠状态进 localStorage（重开还收着）
      toggleFold("生产");
      expect("生产组折起来", byTag()["生产"].folded, true);
      expect("折起来后只剩测试组那一行", rows().length, 1);
      expect(
        "折叠状态确实记进 localStorage",
        JSON.parse(localStorage.getItem(GFOLD_KEY) || "[]"),
        ["生产"],
      );
      toggleFold("生产");
      expect("展开回来三行都在", rows().length, 3);
      expect("展开后 folded 摘掉", byTag()["生产"].folded, false);

      // ⑦ 移出分组：那台机器落回「未分组」组头
      setGroups("qa@stage-01:22", "");
      renderSessions();
      const tagsNow = heads().map((h) => h.tag);
      expect("移出后多出一个未分组", tagsNow.includes("未分组"), true);
      expect("未分组里正好那一台", heads().find((h) => h.tag === "未分组").text, "未分组1");

      // ⑧ 解散分组：右键那项做的就是"把这一组里每台的标签清掉再重画"。
      //    清到最后一个命名组也没了，列表就回到「最近使用 / 更早」——这正是产品该有的样子。
      for (const s of sessionStore.records) {
        if (groupsOf(sessionKey(s)) === "生产") setGroups(sessionKey(s), "");
      }
      renderSessions();
      const after = heads().map((h) => h.tag);
      expect("解散生产组后没有命名组了", after.includes("生产"), false);
      expect("解散后回到最近使用", after.includes("最近使用"), true);
      expect("解散后行数还是三行", rows().length, 3);
      for (const s of sessionStore.records) setGroups(sessionKey(s), "");
      renderSessions();
      expect("全部清干净后更好是空的", heads().map((h) => h.tag).includes("未分组"), false);

      // ⑨ 删：一条记录从清单和列表里一起消失
      removeSession("dba@db-01.prod:2222");
      expect("删掉一条剩两条", sessionStore.records.length, 2);
      expect("列表也跟着少一行", rows().length, 2);
      expect("删掉那台不再出现在列表里", rowKeys().includes("dba@db-01.prod:2222"), false);

      // ⑩ 搜索：命中才留、计数写成"命中/总数"，清空复原
      el("sess-search").value = "web";
      renderSessions();
      expect("搜索后只剩一条", rows().length, 1);
      expect("计数写成命中/总数", el("session-count").textContent, "1/2");
      el("sess-search").value = "zzz";
      renderSessions();
      expect("搜不到时列表清空", rows().length, 0);
      el("sess-search").value = "";
      renderSessions();
      expect("清空搜索复原", rows().length, 2);

      // ⑪ 重开还认"最近用过"：磁盘上那份用的是 last_used（Rust 侧字段名），读回来必须还能分「最近使用 / 更早」
      reset();
      sessionStore.records = [
        { host: "new.example", port: 22, user: "ops", auth: "password", last_used: 1763000000000 },
        { host: "old.example", port: 22, user: "ops", auth: "password", last_used: 0 },
      ];
      renderSessions();
      const labels = heads().map((h) => h.tag || (h.text || "").replace(/\d+$/, ""));
      expect("磁盘上的 last_used 认得出最近使用", labels.includes("最近使用"), true);
      expect("没用过的归到更早", labels.includes("更早"), true);
      expect("最近的排在第一行", rowKeys()[0], "ops@new.example:22");
      // 老文件里的 `last` 也认（迁移期间两种写法都可能出现）
      reset();
      sessionStore.records = [
        { host: "legacy.example", port: 22, user: "ops", auth: "password", last: 1763000000000 },
      ];
      renderSessions();
      expect("老写法 last 也能认", lastUsed(sessionStore.records[0]), 1763000000000);
      seen.diskField = { lastUsed: lastUsed({ last_used: 5 }), lastFallback: lastUsed({ last: 7 }) };
    } catch (err) {
      bad.push(`走会话增删改的过程抛了异常：${err && err.message ? err.message : err}`);
    }

    // 收拾现场：清掉塞进去的会话与分组，把 localStorage 里原有的两份恢复回去
    sessionStore.records = [];
    el("sess-search").value = "";
    localStorage.removeItem(GROUPS_KEY);
    localStorage.removeItem(GFOLD_KEY);
    if (groupsBackup !== null) localStorage.setItem(GROUPS_KEY, groupsBackup);
    if (foldBackup !== null) localStorage.setItem(GFOLD_KEY, foldBackup);
    renderSessions();
    document.title = bad.length
      ? `SESSIONS-SELFTEST-FAIL ${JSON.stringify(bad)} ${JSON.stringify(seen)}`
      : `SESSIONS-SELFTEST-OK ${JSON.stringify(seen)}`;
  })();
}

// ---------- 已知主机：列出、截断显示、按端口删除、空态 ----------
// 清单 §2 M12 的手工动作（"打开设置看列表，删一条，重连走首次信任"）里，
// "重连走首次信任"那半句在 Rust 侧用单测钉住了（known_hosts: forget_makes_the_next_connection_first_seen_again），
// 这里钉住能看见的那半句：行数、计数、指纹截断、同一台机器不同端口分开删、删空了的样子。
if (location.hash === "#hosts-test") {
  (function () {
    const bad = [];
    const seen = {};
    const expect = (label, got, want) => {
      if (got !== want) bad.push(`${label}：${JSON.stringify(got)} ≠ ${JSON.stringify(want)}`);
    };
    const byId = (id) => document.getElementById(id);
    const rows = () => [...byId("hosts-list").querySelectorAll(".hz")];
    const keys = () => rows().map((r) => r.querySelector(".hh").textContent);
    const rowOf = (key) => rows().find((r) => r.querySelector(".hh").textContent === key);
    const delOf = (key) => rowOf(key)?.querySelector(".hz-del");
    const lastToast = () => (toastBox.lastElementChild ? toastBox.lastElementChild.textContent : "");

    const LONG = "SHA256:9fKq2mZpQ0aBcDeFgHiJkLmNoPqRsTuVwXyZ01234";
    const seed = () => {
      hostDemo = [
        { host: "h.example.com", port: 22, fingerprint: LONG },
        { host: "h.example.com", port: 2222, fingerprint: "SHA256:Zx81MnBvC3xY7tReWqAsDfGhJkLz" },
        { host: "[::1]", port: 22, fingerprint: "SHA256:V6" },
      ];
      renderHosts();
    };

    try {
      seed();
      expect("三条记录该画三行", rows().length, 3);
      expect("计数写条数", byId("hosts-count").textContent, "3 条");
      expect("按给出的顺序排", JSON.stringify(keys()), JSON.stringify([
        "h.example.com:22", "h.example.com:2222", "[::1]:22",
      ]));

      // 指纹只露前 10 位，全文挂在 title 上——省宽度但不藏信息
      const fp = rowOf("h.example.com:22").querySelector(".hf");
      expect("长的指纹要截断", fp.textContent, "SHA256:" + LONG.slice(7, 17) + "…");
      expect("截断只起版式作用，全文在 title 里", fp.title, LONG);
      const shortFpCell = rowOf("[::1]:22").querySelector(".hf");
      expect("短指纹不加省略号", shortFpCell.textContent, "SHA256:V6");

      // 端口是键的一部分：删 2222 不许把 22 一起带走
      delOf("h.example.com:2222").click();
      expect("删掉一条后剩两行", rows().length, 2);
      expect("计数跟着变", byId("hosts-count").textContent, "2 条");
      expect("同机另一端口还在", keys().includes("h.example.com:22"), true);
      expect("删掉的那条不在了", keys().includes("h.example.com:2222"), false);
      expect("删完要有回执", lastToast(), "已删除 h.example.com:2222 的记录");

      // IPv6 主机名按整串显示，不能被冒号切碎
      delOf("[::1]:22").click();
      expect("IPv6 纪录也能删", rows().length, 1);
      expect("IPv6 删掉就不在列表里", keys().includes("[::1]:22"), false);

      // 删到最后一条：不留一行空白，给一句解释
      delOf("h.example.com:22").click();
      expect("删空之后没有行", rows().length, 0);
      expect("空态计数写「无」", byId("hosts-count").textContent, "无");
      const hint = byId("hosts-list").querySelector(".hosts-empty");
      expect("空态要说明怎么才会有记录", hint && hint.textContent,
        "还没有记录。第一次连上某台主机时会自动记住它的指纹。");

      // 再喂一批，确认空态之后还能正常长回来（删光了不是把面板弄死）
      seed();
      expect("空态之后还能重新列出", rows().length, 3);
      seen.lastKeys = keys();
    } catch (err) {
      bad.push(`走已知主机面板的过程抛了异常：${err && err.message ? err.message : err}`);
    } finally {
      hostDemo = null;
    }

    document.title = bad.length
      ? `HOSTS-SELFTEST-FAIL ${JSON.stringify(bad)} ${JSON.stringify(seen)}`
      : `HOSTS-SELFTEST-OK ${JSON.stringify(seen)}`;
  })();
}

// ---------- 无头自检：#broken-store-test（坏掉的会话清单不许被下一次存盘整份盖掉） ----------
// 钉的是「读坏了就从空清单起步」这条默认路径上的数据安全：没有后端可问的时候用 fakeInvoke
// 造几份回包——好好的、半截的、版本比程序新的、读失败的、连急救也失败的。
if (location.hash === "#broken-store-test") {
  (async () => {
    const fails = [];
    const seen = {};
    const ok = (cond, msg) => {
      if (!cond) fails.push(msg);
    };
    const lastToast = () => (toastBox.lastElementChild ? toastBox.lastElementChild.textContent : "");
    const rows = () => document.querySelectorAll(".sidebar .sess-row").length;
    const GOOD =
      '{"version":1,"records":[{"host":"web-01.prod","port":22,"user":"deploy","auth":"password","last_used":1763000000000}]}';
    const HALF = '{"version":1,"records":[{"host":"web-01.p';
    const calls = [];
    let readBack = GOOD;
    let writeBack = null;
    let salvageBack = "/app/data/sessions.json.broken-1763000123456";
    const prevRecords = sessionStore.records;
    const back = async (cmd, args) => {
      calls.push(cmd);
      if (cmd === "sessions_read") {
        if (readBack instanceof Error) throw readBack;
        return readBack;
      }
      if (cmd === "sessions_salvage") {
        if (salvageBack instanceof Error) throw salvageBack;
        return salvageBack;
      }
      if (cmd === "sessions_write") {
        writeBack = args && args.json;
        return "/app/data/sessions.json";
      }
      return null;
    };
    try {
      fakeInvoke = back;
      // ① 好文件：正常读出来，一次急救都不叫（别把好好的清单也另存一份）
      readBack = GOOD;
      calls.length = 0;
      await loadSessions();
      ok(sessionStore.records.length === 1, `好文件该读出 1 条：${sessionStore.records.length}`);
      ok(rows() === 1, `列表该画 1 行：${rows()}`);
      ok(!calls.includes("sessions_salvage"), `好文件不该叫急救：${JSON.stringify(calls)}`);
      ok(lastToast() === "", `好文件不该弹 toast：${lastToast()}`);

      // ② 半截写入：不抛、列表空、另存请求发出去、toast 里写清另存成什么名字
      readBack = HALF;
      calls.length = 0;
      await loadSessions();
      ok(sessionStore.records.length === 0, `坏文件只能从空清单起步：${sessionStore.records.length}`);
      ok(rows() === 0, `坏文件起步时列表该是空的：${rows()}`);
      ok(
        calls.includes("sessions_salvage"),
        `坏文件必须叫一次急救（不然下次存盘就整份盖掉）：${JSON.stringify(calls)}`
      );
      ok(
        lastToast() === "会话清单读坏了，原文件已另存为 sessions.json.broken-1763000123456，这次从空清单开始",
        `toast 要写明另存的文件名：${lastToast()}`
      );
      seen.broken = lastToast();

      // ③ 合法 JSON 但不是一份清单（null / 数字）：一样按读不懂处理
      for (const odd of ["null", "42", "\"text\""]) {
        readBack = odd;
        calls.length = 0;
        await loadSessions();
        ok(sessionStore.records.length === 0, `${odd} 不该读成清单：${sessionStore.records.length}`);
        ok(calls.includes("sessions_salvage"), `${odd} 也得先另存：${JSON.stringify(calls)}`);
      }
      // 但 {"version":1} 这种没写 records 的是"还没有会话"，不是坏文件
      readBack = '{"version":1}';
      calls.length = 0;
      await loadSessions();
      ok(sessionStore.records.length === 0, `没写 records 就是空清单：${sessionStore.records.length}`);
      ok(!calls.includes("sessions_salvage"), `空清单不用另存：${JSON.stringify(calls)}`);

      // ④ 连读都读不了（文件系统/权限）：说清是读失败，别谎称清单坏了，也别乱叫急救
      readBack = new Error("Permission denied (os error 13)");
      calls.length = 0;
      await loadSessions();
      ok(sessionStore.records.length === 0, `读失败也只能空清单起步：${sessionStore.records.length}`);
      ok(!calls.includes("sessions_salvage"), `读失败不是清单坏了：${JSON.stringify(calls)}`);
      ok(
        lastToast().startsWith("会话清单读不出来"),
        `读失败要说清是读不成：${lastToast()}`
      );

      // ⑤ 急救本身也失败：得拦一句"先别存新的"，不能让人以为已经救回来了
      readBack = HALF;
      salvageBack = new Error("disk full");
      calls.length = 0;
      await loadSessions();
      ok(
        lastToast().includes("也没能另存") && lastToast().includes("先别存新会话"),
        `急救失败要拦一句别存新的：${lastToast()}`
      );
      seen.noSalvage = lastToast();

      // ⑥ 救回来之后还能正常干活：存一条会话，落盘的就是这一条空清单加新记录
      readBack = HALF;
      salvageBack = "/app/data/sessions.json.broken-1763000123456";
      calls.length = 0;
      await loadSessions();
      saveSession({ host: "after.example", port: 22, user: "ops", auth: "password" });
      await new Promise((r) => setTimeout(r, 0)); // 写盘那条是异步发出去的，等它落地
      ok(sessionStore.records.length === 1, `坏档之后还存得进新会话：${sessionStore.records.length}`);
      ok(typeof writeBack === "string" && writeBack.length > 0, "存新会话要真写到后端");
      const written = JSON.parse(String(writeBack));
      ok(written.records.length === 1, `落盘里只有新这条：${JSON.stringify(written.records)}`);
      ok(written.records[0].host === "after.example", `落盘那条就是刚存的：${written.records[0].host}`);
    } catch (err) {
      fails.push(`走坏档启动的过程抛了异常：${err && err.message ? err.message : err}`);
    } finally {
      // 收场：替身摘掉、清单回到启动时那份（无头页里本来就是空的），列表重画回原样
      fakeInvoke = null;
      sessionStore.records = prevRecords;
      renderSessions();
    }
    document.title = fails.length
      ? `BROKEN-STORE-SELFTEST-FAIL ${JSON.stringify(fails)} ${JSON.stringify(seen)}`
      : `BROKEN-STORE-SELFTEST-OK ${JSON.stringify(seen)}`;
  })();
}

// ---------- 无头自检：#accent-test（强调色六套预置） ----------
// 验的不是"我点了按钮"——是"主色真的走到该去的地方，且没走到不该去的地方"：
// ① 换色后 --accent 与那张色片取的是同一个值；② 压在主色上的文字不许跟主色撞；
// ③ 主按钮的底色确实跟着主色走；④ 切深浅主题不改选定的色、但深浅两档主色不同；
// ⑤ 认不出的值回默认；⑥ 命令行里选中的那颗色片只有一颗；⑦ ANSI 绿不许被主色拐走。
if (location.hash === "#accent-test") {
  (function accentTest() {
    const bad = [];
    const seen = {};
    const byId = (id) => document.getElementById(id);
    const tok = (name) => getComputedStyle(root).getPropertyValue(name).trim();
    // 把令牌名换算成浏览器算出来的 rgb，才能和组件的 backgroundColor 直接比
    function rgbOf(token) {
      const probe = document.createElement("div");
      probe.style.background = `var(${token})`;
      document.body.append(probe);
      const out = getComputedStyle(probe).backgroundColor;
      probe.remove();
      return out;
    }
    function expect(what, got, want) {
      if (JSON.stringify(got) !== JSON.stringify(want)) {
        bad.push(`${what}：${JSON.stringify(got)} ≠ ${JSON.stringify(want)}`);
      }
    }
    // 断言"不相等"时别写四个参数，写清比较本身
    function expectDiff(what, got, want) {
      if (JSON.stringify(got) === JSON.stringify(want)) {
        bad.push(`${what}：${JSON.stringify(got)} 与 ${JSON.stringify(want)} 撞了，应该不同`);
      }
    }
    function dotsOn() {
      return [...byId("acc-row").querySelectorAll(".acc-dot.on")].map((d) => d.dataset.sw);
    }

    const prevTheme = localStorage.getItem("portio.theme") ?? "dark";
    const prevAccent = readAccent();
    try {
      // ① 起点干净：不带选择时落默认青
      localStorage.removeItem(ACCENT_KEY);
      applyAccent(readAccent());
      expect("没选过时是默认的青", root.dataset.accent, "teal");

      // ② 换蓝：界面主色与那颗色片必须取到同一个值（不靠两处写死对上）
      applyAccent("azure");
      const azureAccent = tok("--accent");
      expect("换色后 data-accent 是 azure", root.dataset.accent, "azure");
      expect("--accent 就是蓝那张色片的值", azureAccent, tok("--acc-azure"));
      expect("主色确实换了（跟青不一样）", azureAccent === tok("--acc-teal"), false);
      expect("落盘记下了所选颜色", localStorage.getItem(ACCENT_KEY), "azure");

      // ③ 压在主色上的文字不许跟主色撞，否则按钮上的字直接消失
      expect("--on-accent 与 --accent 不同色", tok("--on-accent") === azureAccent, false);

      // ④ 主按钮真的跟着主色走（不是只有色片好看）。
      // 换色时有 160ms 过渡，量之前先把这颗按钮的过渡关掉，否则读到的是过渡中的颜色
      const primary = document.querySelector(".btn.primary");
      primary.style.transition = "none";
      void primary.offsetHeight;
      expect("主按钮底色等于 --accent", getComputedStyle(primary).backgroundColor, rgbOf("--accent"));
      primary.style.transition = "";

      // ⑤ 切深浅主题：选的色不变，主色要换成那一档的值
      const darkAccent = tok("--accent");
      applyTheme("light");
      expect("切到浅色后选的还是蓝", root.dataset.accent, "azure");
      expect("浅色档主色换成浅的那一支", tok("--accent") === darkAccent, false);
      expect("浅色档主色就是浅色那套令牌", tok("--accent"), tok("--acc-azure"));
      applyTheme(prevTheme);

      // ⑥ 认不出的值回默认，别把界面弄成没主色
      applyAccent("chartreuse");
      expect("认不出的颜色回默认青", root.dataset.accent, "teal");

      // ⑦ 命令行里选中的色片只有一颗，且是当前那套
      applyAccent("rose");
      expect("选中的色片只有一颗", dotsOn(), ["rose"]);
      expect("设置里显示当前色的名字", byId("acc-name").textContent, "玫瑰");

      // ⑧ 终端语义色不许被主色拐走：ANSI 绿与主色是两回事
      const green = tok("--ansi-green");
      const accent = tok("--accent");
      expect("ANSI 绿不跟着主色变", green === accent, false);
      // 但终端光标要跟着，它只是主色的一份投影
      expect("终端光标跟着主色", tok("--term-cursor"), accent);

      seen.on = dotsOn();
      seen.accent = tok("--accent");
      seen.ansiGreen = green;
    } catch (err) {
      bad.push(`走强调色设置的过程抛了异常：${err && err.message ? err.message : err}`);
    } finally {
      // 收拾现场：还原主题与颜色，别把自检的选择留在机器上
      applyTheme(prevTheme);
      applyAccent(prevAccent);
    }

    document.title = bad.length
      ? `ACCENT-SELFTEST-FAIL ${JSON.stringify(bad)} ${JSON.stringify(seen)}`
      : `ACCENT-SELFTEST-OK ${JSON.stringify(seen)}`;
  })();
}

// ---------- 自检：终端配色方案（A22 / #term-theme-test）----------
// 验的是"终端配色真的跟界面主题解耦了"，而不是"按钮点了会变色"：
// ① 默认是「跟界面」、html 上没有 data-term 压着；
// ② 选 Nord 后终端九色成套换（底 / 字 / 选区 + ANSI 八色一起），且终端底色与界面底色不同源；
// ③ 这时把界面切浅色，终端那套色一动不动；
// ④ 回「跟界面」后属性消失、终端底色回到界面那套；⑤ 认不出的值回「跟界面」；
// ⑥ 真终端对象的 theme 也换了（xterm 不认 CSS 变量，只认 options.theme）；
// ⑦ 强调色与终端配色互不干扰：换主色不动 Nord 的 ANSI 绿，光标仍跟主色走。
// 期望值一律拿"改前 / 改后"互相比，不写死色值——写死就等于把配色又钉回代码里，
// 而这里的规矩是配色只许住 tokens.css。
if (location.hash === "#term-theme-test") {
  (function termThemeTest() {
    const bad = [];
    const seen = {};
    const byId = (id) => document.getElementById(id);
    const tok = (name) => getComputedStyle(root).getPropertyValue(name).trim();
    function expect(what, got, want) {
      if (JSON.stringify(got) !== JSON.stringify(want)) {
        bad.push(`${what}：${JSON.stringify(got)} ≠ ${JSON.stringify(want)}`);
      }
    }
    function expectDiff(what, got, want) {
      if (JSON.stringify(got) === JSON.stringify(want)) {
        bad.push(`${what}：${JSON.stringify(got)} 与 ${JSON.stringify(want)} 撞了，应该不同`);
      }
    }
    function onSeg() {
      return [...byId("seg-term").querySelectorAll("button.on")].map((b) => b.dataset.v);
    }
    // 抓一个真终端对象来核，别只看 CSS 变量
    let real = null;
    eachTerm((t) => { if (!real) real = t; });

    const prevTheme = localStorage.getItem("portio.theme") ?? "dark";
    const prevTerm = readTerm();
    const prevAccent = readAccent();
    try {
      // ① 起点：固定深色、清掉选择，终端跟界面同源
      applyTheme("dark");
      localStorage.removeItem(TERM_KEY);
      applyTerm(readTerm());
      expect("没选过时是「跟界面」", readTerm(), "auto");
      expect("没选过时 html 上没有 data-term", root.dataset.term, undefined);
      const autoBg = tok("--term-bg");
      const autoGreen = tok("--ansi-green");
      const darkUiBg = tok("--bg");
      expectDiff("跟界面时终端底色本来就和界面底色不同（终端是黑底画布）", autoBg, darkUiBg);

      // ② 选 Nord：九色成套换
      applyTerm("nord");
      expect("选了 Nord 后 data-term 是 nord", root.dataset.term, "nord");
      expect("落盘记下了终端配色", localStorage.getItem(TERM_KEY), "nord");
      const nordBg = tok("--term-bg");
      const nordGreen = tok("--ansi-green");
      const nordFg = tok("--term-fg");
      expectDiff("终端背景真的换了（不再是界面那套）", nordBg, autoBg);
      expectDiff("ANSI 绿也成套换了", nordGreen, autoGreen);
      expectDiff("前景跟着换（只换底不换字会看不清）", nordFg, tok("--term-bg"));

      // ⑥ 真终端对象当场就该被重挂（xterm 不认 CSS 变量，只认 options.theme）。
      // 这一条必须查在切主题之前：applyTheme 里也会顺手重挂一遍，放在后面就查不出
      // "applyTerm 自己忘了挂"这个 bug（反向验证时确实被盖住过一次）。
      if (!real) {
        bad.push("没抓到一个真终端对象，没法核 options.theme");
      } else {
        const theme = real.options.theme ?? {};
        expect("真终端的背景就是 Nord 的底", theme.background, nordBg);
        expect("真终端的绿就是 Nord 的绿", theme.green, nordGreen);
        // 光标归强调色管，不归终端预设管
        expect("真终端光标跟主色走", theme.cursor, tok("--accent"));
      }

      // ③ 界面切浅色：终端那套一动不动
      applyTheme("light");
      const lightUiBg = tok("--bg");
      expectDiff("界面底色确实变浅了", lightUiBg, darkUiBg);
      expect("界面切浅色后终端配色还是 Nord", root.dataset.term, "nord");
      expect("界面切浅色后终端背景一动不动", tok("--term-bg"), nordBg);
      expect("界面切浅色后 ANSI 绿一动不动", tok("--ansi-green"), nordGreen);
      expectDiff("终端底色没跟着界面变浅", tok("--term-bg"), lightUiBg);

      // 三套预设确实互不相同（不是同一个色板换个名字）
      applyTerm("dracula");
      expectDiff("Dracula 的底与 Nord 的底不同", tok("--term-bg"), nordBg);
      expectDiff("Dracula 的绿与 Nord 的绿不同", tok("--ansi-green"), nordGreen);

      // ④ 回「跟界面」：属性消失，终端跟回界面（此刻界面是浅色）
      applyTerm("auto");
      expect("回「跟界面」后 data-term 没了", root.dataset.term, undefined);
      const lightAutoBg = tok("--term-bg");
      expectDiff("跟回浅色界面后终端底色变了", lightAutoBg, nordBg);
      applyTheme("dark");
      expect("跟回深色界面后终端底色就是原来的值", tok("--term-bg"), autoBg);

      // ⑤ 认不出的值别留在机器上
      localStorage.setItem(TERM_KEY, "monokai");
      expect("认不出的终端配色读成「跟界面」", readTerm(), "auto");

      // ⑦ 两套互不干扰：换主色不动 Nord 的 ANSI 绿，但光标跟着主色
      applyTerm("nord");
      const beforeAccent = tok("--accent");
      applyAccent("azure");
      expectDiff("主色确实换了", tok("--accent"), beforeAccent);
      expect("换主色后 Nord 的 ANSI 绿没变", tok("--ansi-green"), nordGreen);
      expect("换主色后终端光标就是主色", tok("--term-cursor"), tok("--accent"));
      expect("seg 里选中的只有 Nord 一颗", onSeg(), ["nord"]);

      seen.term = readTerm();
      seen.termBg = nordBg;
      seen.ansiGreen = nordGreen;
      seen.autoBg = autoBg;
    } catch (err) {
      bad.push(`走终端配色设置的过程抛了异常：${err && err.message ? err.message : err}`);
    } finally {
      // 收拾现场：还原主题、终端配色与主色
      applyTheme(prevTheme);
      applyAccent(prevAccent);
      applyTerm(prevTerm);
    }

    document.title = bad.length
      ? `TERM-THEME-SELFTEST-FAIL ${JSON.stringify(bad)} ${JSON.stringify(seen)}`
      : `TERM-THEME-SELFTEST-OK ${JSON.stringify(seen)}`;
  })();
}

// 核验用：把 ANSI 八色真写进终端，一眼看出这套配色长什么样（#term-palette / #term-palette-solarized /
// #term-palette-auto）。只给截图与人工比对用，不参与任何逻辑。
if (location.hash.startsWith("#term-palette")) {
  const pick = location.hash === "#term-palette-solarized" ? "solarized"
    : location.hash === "#term-palette-auto" ? "auto" : "nord";
  applyTerm(pick);
  const names = ["黑", "红", "绿", "黄", "蓝", "紫", "青", "白"];
  const fgLine = names.map((n, i) => `\x1b[${30 + i}m${n} ${30 + i}\x1b[0m`).join("  ");
  const bgLine = names.map((n, i) => `\x1b[${40 + i}m  ${n}  ${40 + i}  \x1b[0m`).join(" ");
  setTimeout(() => {
    if (!term) return;
    term.write("\r\n\x1b[0m前台八色（30–37）\r\n" + fgLine + "\r\n\r\n底色八色（40–47）\r\n" + bgLine + "\r\n");
  }, 400);
}

// ---------- 无头自检：#boot-test（会话栏 / 文件面板的「启动时」三档） ----------
// 这一层最容易错在两处：把「启动时」当成"立刻改现在的布局"，或者顺手把记忆态一起改掉——
// 那会让人选了"总是展开"之后再想回"记住上次"，上一次手动收起的事实已经没了。
// 判据围着这件事转：
//   ① 出厂态两个 seg 都是「记住上次」，盘里没有 boot 键；
//   ② 三档语义：remember 用记忆态、open 恒展开、folded 恒收起（四种组合逐个核）；
//   ③ 改「启动时」当前窗口一点不动，也不碰 FOLD / FFOLD 这两个记忆键；
//   ④ 模拟下次启动：folded → 会话栏真收起（--sidebar 归 0）、文件面板真收掉（files-folded + aria-pressed）；
//      open → 两者都放回来；
//   ⑤ 认不出的档位回「记住上次」且盘里不留垃圾；
//   ⑥ seg 选中项跟着落盘的值走。
if (location.hash === "#boot-test") {
  (function bootTest() {
    const bad = [];
    const seen = {};
    const byId = (id) => document.getElementById(id);
    const tok = (name) => getComputedStyle(root).getPropertyValue(name).trim();
    function expect(what, got, want) {
      if (JSON.stringify(got) !== JSON.stringify(want)) {
        bad.push(`${what}：${JSON.stringify(got)} ≠ ${JSON.stringify(want)}`);
      }
    }
    function onSeg(id) {
      const box = byId(id);
      return box ? [...box.querySelectorAll("button.on")].map((b) => b.dataset.v) : [];
    }
    const sideFolded = () => mainEl.classList.contains("collapsed");
    const filesFoldedNow = () => splitEl.classList.contains("files-folded");

    const prevSide = localStorage.getItem(FOLD_KEY);
    const prevFiles = localStorage.getItem(FFOLD_KEY);
    const prevBootSide = localStorage.getItem(BOOT_SIDE_KEY);
    const prevBootFiles = localStorage.getItem(BOOT_FILES_KEY);
    try {
      // ① 出厂态
      localStorage.removeItem(BOOT_SIDE_KEY);
      localStorage.removeItem(BOOT_FILES_KEY);
      syncSegs();
      expect("没选过时会话栏「启动时」是记住上次", onSeg("seg-boot-side"), ["remember"]);
      expect("没选过时文件面板「启动时」是记住上次", onSeg("seg-boot-files"), ["remember"]);
      expect("没选过时读到的也是记住上次", readBoot(BOOT_SIDE_KEY), "remember");

      // ② 三档语义
      expect("记住上次 + 记忆态收起 → 收起", bootFold("remember", true), true);
      expect("记住上次 + 记忆态展开 → 展开", bootFold("remember", false), false);
      expect("总是展开 + 记忆态收起 → 仍展开", bootFold("open", true), false);
      expect("总是收起 + 记忆态展开 → 仍收起", bootFold("folded", false), true);

      // ③ 改「启动时」不动眼前布局、也不动记忆态
      applyFold(false);
      applyFilesFold(false);
      const sideMem = localStorage.getItem(FOLD_KEY);
      const filesMem = localStorage.getItem(FFOLD_KEY);
      applyBootMode(BOOT_SIDE_KEY, "folded");
      applyBootMode(BOOT_FILES_KEY, "folded");
      expect("选了「总是收起」后眼前的会话栏还开着", sideFolded(), false);
      expect("选了「总是收起」后眼前文件面板还开着", filesFoldedNow(), false);
      expect("选「启动时」不许改会话栏记忆态", localStorage.getItem(FOLD_KEY), sideMem);
      expect("选「启动时」不许改文件面板记忆态", localStorage.getItem(FFOLD_KEY), filesMem);

      // ④ 模拟下次启动：两处都收起
      applyBootSide();
      applyBootFiles();
      expect("「总是收起」后会话栏真收起了", sideFolded(), true);
      expect("「总是收起」后 --sidebar 归 0", tok("--sidebar"), "0px");
      expect("「总是收起」后文件面板真收掉了", filesFoldedNow(), true);
      expect("折叠钮的 aria-pressed 跟着变", byId("files-fold").getAttribute("aria-pressed"), "true");
      expect("启动覆盖不改会话栏记忆态", localStorage.getItem(FOLD_KEY), sideMem);

      // 改成「总是展开」再模拟一次：两处都放回来
      const memWidth = tok("--sidebar");
      applyBootMode(BOOT_SIDE_KEY, "open");
      applyBootMode(BOOT_FILES_KEY, "open");
      applyBootSide();
      applyBootFiles();
      expect("「总是展开」后会话栏回来了", sideFolded(), false);
      expect("「总是展开」后文件面板回来了", filesFoldedNow(), false);
      expect("折叠钮的 aria-pressed 跟着回 false", byId("files-fold").getAttribute("aria-pressed"), "false");
      expect("会话栏宽度回到记忆值（不是 0）", /px$/.test(tok("--sidebar")) && tok("--sidebar") !== "0px", true);
      seen.width = { remembered: memWidth, after: tok("--sidebar") };

      // ⑤ 认不出的档位
      localStorage.setItem(BOOT_SIDE_KEY, "sometimes");
      expect("认不出的档位读成记住上次", readBoot(BOOT_SIDE_KEY), "remember");
      applyBootMode(BOOT_SIDE_KEY, "sometimes");
      expect("认不出的档位不回写进盘", localStorage.getItem(BOOT_SIDE_KEY), "remember");

      // ⑥ 落盘与 seg 选中
      applyBootMode(BOOT_FILES_KEY, "folded");
      expect("文件面板落盘", localStorage.getItem(BOOT_FILES_KEY), "folded");
      expect("文件面板 seg 选中的只有总是收起", onSeg("seg-boot-files"), ["folded"]);
      applyBootMode(BOOT_SIDE_KEY, "remember");
      expect("会话栏 seg 选中的只有记住上次", onSeg("seg-boot-side"), ["remember"]);
    } catch (err) {
      bad.push(`走启动布局的过程抛了异常：${err && err.message ? err.message : err}`);
    } finally {
      // 收拾现场：两个 boot 键与两组折叠态都还原成进来时的样子
      if (prevBootSide === null) localStorage.removeItem(BOOT_SIDE_KEY);
      else localStorage.setItem(BOOT_SIDE_KEY, prevBootSide);
      if (prevBootFiles === null) localStorage.removeItem(BOOT_FILES_KEY);
      else localStorage.setItem(BOOT_FILES_KEY, prevBootFiles);
      applyFold(prevSide === "1");
      applyFilesFold(prevFiles === "1");
      syncSegs();
    }

    document.title = bad.length
      ? `BOOT-SELFTEST-FAIL ${JSON.stringify(bad)} ${JSON.stringify(seen)}`
      : `BOOT-SELFTEST-OK ${JSON.stringify(seen)}`;
  })();
}

// ---------- 无头自检：#perm-test（文件面板的权限列能不能真关掉） ----------
// 这一列最容易做错成"把单元格 display:none，轨道还留着 68px 空位"——
// 看着像藏了，文件名其实一点没变宽。判据围着这件事转：
//   ① 出厂态：没有 data-perm、seg 选「显示」、盘里没有这个键；
//   ② 关掉之后整条轨道收走（grid 从 5 列变 4 列），权限单元格真看不见；
//   ③ 名字列吃掉那 68px（多出来的宽度就在 68 上下），而大小 / 时间两列的右缘**一点不动**（右对齐不许挪）；
//   ④ 行高一点不动（等于 --row）、行宽一点不动；
//   ⑤ 本地行本来就 4 列，不受影响；
//   ⑥ 认不出的值读成「显示」，且不回写垃圾；
//   ⑦ 落盘与 seg 选中。
if (location.hash === "#perm-test") {
  (function permTest() {
    const bad = [];
    const seen = {};
    const byId = (id) => document.getElementById(id);
    const tok = (name) => getComputedStyle(root).getPropertyValue(name).trim();
    const px = (v) => Math.round(parseFloat(v) * 2) / 2;
    function expect(what, got, want) {
      if (JSON.stringify(got) !== JSON.stringify(want)) {
        bad.push(`${what}：${JSON.stringify(got)} ≠ ${JSON.stringify(want)}`);
      }
    }
    function near(what, got, want, tol) {
      if (!(Math.abs(got - want) <= tol)) bad.push(`${what}：${got} ≠ ${want}（差 ${px(got - want)}）`);
    }
    function onSeg(id) {
      const box = byId(id);
      return box ? [...box.querySelectorAll("button.on")].map((b) => b.dataset.v) : [];
    }
    const cols = (el) => getComputedStyle(el).gridTemplateColumns.split(/\s+/).filter(Boolean).length;

    // 无头页里文件列表只有"空目录"提示，塞一条远端行与一条本地行进来量
    const injected = [];
    function injectRow(host, cls, html) {
      if (!host) return null;
      host.textContent = "";
      const row = document.createElement("div");
      row.className = cls;
      row.innerHTML = html;
      host.append(row);
      injected.push(host);
      return row;
    }
    const remoteRow = injectRow(
      byId("remote-list"),
      "fp-row has-perm",
      '<span class="ico">▸</span><span class="nm">release-notes-v0.4-draft.md</span>' +
        '<span class="pm">drwxr-xr-x</span><span class="sz">—</span><span class="tm">2026-11-20 09:12</span>',
    );
    const localRow = injectRow(
      byId("local-list"),
      "fp-row",
      '<span class="ico">·</span><span class="nm">notes.md</span><span class="sz">6.2 KB</span>' +
        '<span class="tm">2026-11-20 09:12</span>',
    );

    const prev = localStorage.getItem(PERM_KEY);
    try {
      // ① 出厂态
      localStorage.removeItem(PERM_KEY);
      applyPerm("show");
      localStorage.removeItem(PERM_KEY);
      syncSegs();
      expect("没选过时不留 data-perm", root.dataset.perm ?? null, null);
      expect("没选过时 seg 选显示", onSeg("seg-perm"), ["show"]);
      expect("没选过时读到的也是显示", readPerm(), "show");
      expect("远端行出厂态是 5 列", cols(remoteRow), 5);

      const pmEl = remoteRow.querySelector(".pm");
      const nmEl = remoteRow.querySelector(".nm");
      const szEl = remoteRow.querySelector(".sz");
      const before = {
        pmW: px(pmEl.getBoundingClientRect().width),
        nmW: px(nmEl.getBoundingClientRect().width),
        szRight: px(szEl.getBoundingClientRect().right),
        rowW: px(remoteRow.getBoundingClientRect().width),
        rowH: px(remoteRow.getBoundingClientRect().height),
      };
      expect("权限列真的占着宽度", before.pmW > 60, true);

      // ② 关掉
      applyPerm("hide");
      void document.body.offsetHeight; // 强制重排，量终态
      expect("关掉后 data-perm 落盘在根上", root.dataset.perm, "hide");
      expect("关掉后权限单元格看不见", getComputedStyle(pmEl).display, "none");
      expect("关掉后远端行只剩 4 列", cols(remoteRow), 4);
      const hid = {
        nmW: px(nmEl.getBoundingClientRect().width),
        szRight: px(szEl.getBoundingClientRect().right),
        rowW: px(remoteRow.getBoundingClientRect().width),
        rowH: px(remoteRow.getBoundingClientRect().height),
      };
      // ③ 名字列吃掉那 68px（还有 4px 的 gap），右对齐两列一动不动
      near("关掉后名字列多出来的宽度", px(hid.nmW - before.nmW), 68 + 4, 2);
      near("关掉后大小列的右缘不许挪", hid.szRight, before.szRight, 0.5);
      // ④ 行高与行宽不许跟着变
      near("关掉后行宽不许变", hid.rowW, before.rowW, 0.5);
      near("关掉后行高等于 --row", hid.rowH, px(tok("--row")), 0.5);
      // ⑤ 本地行不受影响（它本来就没有这一列）
      expect("本地行一直是 4 列", cols(localRow), 4);
      seen.perm = { pmW: before.pmW, nmGain: px(hid.nmW - before.nmW), rowH: hid.rowH };

      // ⑥ 认不出的值
      localStorage.setItem(PERM_KEY, "collapse");
      expect("认不出的值读成显示", readPerm(), "show");
      applyPerm("collapse");
      expect("认不出的值不回写进盘", localStorage.getItem(PERM_KEY), "show");

      // ⑦ 落盘与 seg 选中，再开回来列数要回 5
      applyPerm("hide");
      expect("落盘", localStorage.getItem(PERM_KEY), "hide");
      expect("seg 选中的只有隐藏", onSeg("seg-perm"), ["hide"]);
      applyPerm("show");
      void document.body.offsetHeight;
      expect("开回来又是 5 列", cols(remoteRow), 5);
      near("开回来名字列宽度回到原值", px(nmEl.getBoundingClientRect().width), before.nmW, 0.5);
      expect("开回来 seg 选中的只有显示", onSeg("seg-perm"), ["show"]);
    } catch (err) {
      bad.push(`走权限列的过程抛了异常：${err && err.message ? err.message : err}`);
    } finally {
      // 收拾现场：删掉塞进去的行、把键与根属性还原成进来时的样子
      for (const host of injected) {
        if (!host) continue;
        host.textContent = "";
        const hint = document.createElement("span");
        hint.className = "hint";
        hint.textContent = "空目录";
        host.append(hint);
      }
      if (prev === null) localStorage.removeItem(PERM_KEY);
      else localStorage.setItem(PERM_KEY, prev);
      applyPerm(prev ?? "show");
      syncSegs();
    }

    document.title = bad.length
      ? `PERM-SELFTEST-FAIL ${JSON.stringify(bad)} ${JSON.stringify(seen)}`
      : `PERM-SELFTEST-OK ${JSON.stringify(seen)}`;
  })();
}

// 这四件事最怕的是"牵一发而动全身"：调界面字号把终端里的字挤小、换字体只换了 CSS
// 而 xterm 还拿旧族名在量格子、密度多一档却把某处行高写成别的数。
// 所以每一条都拿"改前 / 改后"互相比，并且必须落到**真终端对象**（xterm 不认 CSS 变量）：
//   ① 出厂态：没有 data-ui-font、没有 data-mono；终端 13px、族名是那串默认（含 JetBrains Mono）；
//   ② 界面字号「大一号」：--fs-13 从 13px 变 14px、真元素算出来的字号也跟着变大，而终端字号一动不动；
//   ③ 终端字号 18：真终端 18px，界面 --fs-13 一动不动（两套互不带动）；
//   ④ 字号越界（30 / 8）读回默认 13；下界 9 认；
//   ⑤ 换 Consolas：data-mono 落上、真终端族名以 Consolas 打头、末尾仍有 monospace 兜底（绝不落比例字体）；
//   ⑥ 认不出的字体名不留痕，回「自动」（属性消失）；
//   ⑦ 密度三档 24 / 28 / 32，两两差正好 4px，且设置里的 seg 跟着走；
//   ⑧ 换字体之后界面小号等宽的令牌也换了（界面与终端用的是同一个 --mono，不许只换一半）。
if (location.hash === "#font-test") {
  (function fontTest() {
    const bad = [];
    const seen = {};
    const byId = (id) => document.getElementById(id);
    const tok = (name) => getComputedStyle(root).getPropertyValue(name).trim();
    const px = (v) => Math.round(parseFloat(v) * 2) / 2;
    function expect(what, got, want) {
      if (JSON.stringify(got) !== JSON.stringify(want)) {
        bad.push(`${what}：${JSON.stringify(got)} ≠ ${JSON.stringify(want)}`);
      }
    }
    function expectDiff(what, got, want) {
      if (JSON.stringify(got) === JSON.stringify(want)) {
        bad.push(`${what}：${JSON.stringify(got)} 与 ${JSON.stringify(want)} 撞了，应该不同`);
      }
    }
    function onSeg(id) {
      const box = byId(id);
      return box ? [...box.querySelectorAll("button.on")].map((b) => b.dataset.v) : [];
    }
    let real = null;
    eachTerm((t) => { if (!real) real = t; });
    if (!real) {
      document.title = `FONT-SELFTEST-FAIL ${JSON.stringify(["没抓到一个真终端对象，后面全都核不了"])}`;
      return;
    }
    // 界面文字真算出来的字号：拿设置面板里那颗 seg 按钮量（它 font:inherit，跟着 --fs-13 走）
    const uiProbe = () => px(getComputedStyle(byId("seg-ui-font").querySelector("button")).fontSize);

    const prevUiFont = readUiFont();
    const prevMono = readMono();
    const prevFont = readFontSize();
    const prevDensity = root.dataset.density ?? "standard";
    try {
      // ① 出厂态：清掉三项选择，看默认落到哪
      localStorage.removeItem(UI_FONT_KEY);
      localStorage.removeItem(MONO_KEY);
      localStorage.removeItem(FONT_KEY);
      applyUiFont(readUiFont());
      applyMono(readMono());
      setFontSize(readFontSize());
      expect("没选过时没有 data-ui-font", root.dataset.uiFont, undefined);
      expect("没选过时没有 data-mono", root.dataset.mono, undefined);
      expect("出厂态界面字号令牌是 13px", tok("--fs-13"), "13px");
      expect("出厂态终端字号是 13", real.options.fontSize, 13);
      seen.autoFont = String(real.options.fontFamily);
      if (!String(real.options.fontFamily).includes("JetBrains Mono")) {
        bad.push(`出厂态终端族名里没有 JetBrains Mono：${JSON.stringify(real.options.fontFamily)}`);
      }
      const uiBefore = uiProbe();

      // ② 界面字号大一号：界面变大，终端不动
      applyUiFont("large");
      expect("选了「大一号」后 data-ui-font 是 large", root.dataset.uiFont, "large");
      expect("「大一号」把 --fs-13 抬到 14px", tok("--fs-13"), "14px");
      const uiAfter = uiProbe();
      expectDiff("界面上真算出来的字号确实变大了", uiAfter, uiBefore);
      if (uiAfter <= uiBefore) bad.push(`界面字号没变大：${uiBefore}px → ${uiAfter}px`);
      expect("界面字号放大后终端字号一动不动", real.options.fontSize, 13);
      applyUiFont("standard");
      expect("切回「标准」后属性消失", root.dataset.uiFont, undefined);
      expect("切回「标准」后 --fs-13 回到 13px", tok("--fs-13"), "13px");

      // ③ 终端字号 18：终端变大，界面不动
      setFontSize(18);
      expect("终端字号真的变成 18px", real.options.fontSize, 18);
      expect("落盘记下了终端字号", localStorage.getItem(FONT_KEY), "18");
      expect("终端字号变大后界面 --fs-13 一动不动", tok("--fs-13"), "13px");

      // ④ 越界与下界
      localStorage.setItem(FONT_KEY, "30");
      expect("终端字号 30 超出上限，读回默认 13", readFontSize(), 13);
      localStorage.setItem(FONT_KEY, "8");
      expect("终端字号 8 低于下限，读回默认 13", readFontSize(), 13);
      localStorage.setItem(FONT_KEY, "9");
      expect("终端字号下界 9 是认的", readFontSize(), 9);
      setFontSize(readFontSize());

      // ⑤ 换 Consolas：族名当场挂到真终端上，且末尾有 monospace 兜底
      applyMono("consolas");
      expect("选了 Consolas 后 data-mono 是 consolas", root.dataset.mono, "consolas");
      const ff = String(real.options.fontFamily);
      if (!ff.startsWith("Consolas")) bad.push(`真终端的族名没以 Consolas 打头：${JSON.stringify(ff)}`);
      if (!ff.endsWith("monospace")) bad.push(`族名末尾没有 monospace 兜底，可能落到比例字体：${JSON.stringify(ff)}`);
      expect("界面小号等宽的令牌也跟着换了", tok("--mono"), termFont());

      // ⑥ Cascadia 与 Consolas 不是同一串；认不出的名字不留痕
      applyMono("cascadia");
      if (!String(real.options.fontFamily).includes("Cascadia Mono")) {
        bad.push(`换成 Cascadia 后真终端族名没跟上：${JSON.stringify(real.options.fontFamily)}`);
      }
      expectDiff("Cascadia 与 Consolas 的族名不同", String(real.options.fontFamily), ff);
      applyMono("comic");
      expect("认不出的字体名不留属性", root.dataset.mono, undefined);
      expect("认不出的字体名读成「自动」", readMono(), "auto");
      if (!termFont().endsWith("monospace")) bad.push(`「自动」档的族名末尾也不是 monospace：${JSON.stringify(termFont())}`);

      // ⑦ 密度三档
      const rows = {};
      for (const d of ["compact", "standard", "comfortable"]) {
        applyDensity(d);
        void document.body.offsetHeight; // 强制重排再读令牌
        rows[d] = px(tok("--row"));
        const on = onSeg("seg-density");
        if (on.length !== 1 || on[0] !== d) bad.push(`${d} 档下密度 seg 选中的是 ${JSON.stringify(on)}`);
      }
      expect("紧凑档 --row 应为 24px", rows.compact, 24);
      expect("标准档 --row 应为 28px", rows.standard, 28);
      expect("宽松档 --row 应为 32px", rows.comfortable, 32);
      if (px(rows.standard - rows.compact) !== 4) {
        bad.push(`紧凑 → 标准 差 ${px(rows.standard - rows.compact)}px，应正好 4px`);
      }
      if (px(rows.comfortable - rows.standard) !== 4) {
        bad.push(`标准 → 宽松 差 ${px(rows.comfortable - rows.standard)}px，应正好 4px`);
      }

      // ⑧ seg 选中项与落盘
      applyUiFont("large");
      expect("界面字号 seg 选中的只有「大一号」", onSeg("seg-ui-font"), ["large"]);
      expect("界面字号落盘", localStorage.getItem(UI_FONT_KEY), "large");
      applyMono("consolas");
      expect("等宽字体 seg 选中的只有 Consolas", onSeg("seg-mono"), ["consolas"]);
      expect("等宽字体落盘", localStorage.getItem(MONO_KEY), "consolas");

      seen.uiBefore = uiBefore;
      seen.uiAfter = uiAfter;
      seen.fontSize = readFontSize();
      seen.row = rows;
    } catch (err) {
      bad.push(`走字号 / 字体 / 密度的过程抛了异常：${err && err.message ? err.message : err}`);
    } finally {
      // 收拾现场：三项都还原成进来时的样子
      applyUiFont(prevUiFont);
      applyMono(prevMono);
      setFontSize(prevFont);
      applyDensity(prevDensity);
    }

    document.title = bad.length
      ? `FONT-SELFTEST-FAIL ${JSON.stringify(bad)} ${JSON.stringify(seen)}`
      : `FONT-SELFTEST-OK ${JSON.stringify(seen)}`;
  })();
}
