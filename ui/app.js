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

// 把 Rust 侧的原始错误翻成人话：说清"发生了什么 + 下一步怎么做"。
// 匹配不上的一律保留原文，宁可粗糙也不隐藏细节。
function explainError(cmd, err) {
  const raw = String(err ?? "");
  const rules = [
    [/authentication|auth failed|userauth|密码|私钥/, "认证被拒绝", "用户名、密码或私钥不对；确认登录方式与凭据后重试"],
    [/econnrefused|connection refused|actively refused/i, "连接被拒绝", "端口没开或被防火墙拦了；先用 telnet 探一下 22 端口"],
    [/timed out|timeout|超时/, "连接超时", "网络不可达或服务端限流；检查网络与允许列表"],
    [/no space left|磁盘满/, "远端磁盘已满", "清理远端目录或换目标路径"],
    [/permission denied|permission|权限/i, "权限不足", "该账号对目标路径没有权限；换目录或用有权限的账号"],
    [/no such file|not found|不存在/, "路径不存在", "目录可能被删或改名；刷新列表确认"],
    [/host key|hostkey/i, "主机指纹变化", "可能被中间人替换；确认指纹后再决定是否继续"],
  ];
  for (const [re, title, hint] of rules) {
    if (re.test(raw)) return `${title}：${hint}`;
  }
  return `${cmd} 失败：${raw}`;
}

async function call(cmd, args) {
  if (!bridge) return null;
  try {
    return await bridge.invoke(cmd, args);
  } catch (err) {
    toast(explainError(cmd, err));
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
function applyTheme(pref) {
  localStorage.setItem("portio.theme", pref);
  root.dataset.theme = resolveTheme(pref);
  if (typeof term !== "undefined" && term) term.options.theme = terminalTheme();
  syncSegs();
}
function applyDensity(density) {
  root.dataset.density = density;
  localStorage.setItem("portio.density", density);
  syncSegs();
}
document.getElementById("btn-theme").addEventListener("click", () => {
  const pref = localStorage.getItem("portio.theme") ?? "dark";
  applyTheme(pref === "dark" ? "light" : pref === "light" ? "system" : "dark");
});
document.getElementById("btn-density").addEventListener("click", () => {
  const next = root.dataset.density === "compact" ? "standard" : "compact";
  applyDensity(next);
  toast(next === "compact" ? "已切换到紧凑密度" : "已切换到标准密度");
});

// ---------- 设置 ----------
const FONT_KEY = "portio.fontSize";
const SCROLL_KEY = "portio.scrollback";
function readFontSize() {
  const n = Number(localStorage.getItem(FONT_KEY));
  return Number.isFinite(n) && n >= 11 && n <= 18 ? n : 13;
}
function readScrollback() {
  const n = Number(localStorage.getItem(SCROLL_KEY));
  return Number.isFinite(n) && n >= 1000 ? n : 8000;
}
function setFontSize(px) {
  localStorage.setItem(FONT_KEY, String(px));
  if (typeof term !== "undefined" && term) {
    term.options.fontSize = px;
    fitQuietly();
  }
  syncSegs();
}
function setScrollback(rows) {
  localStorage.setItem(SCROLL_KEY, String(rows));
  if (typeof term !== "undefined" && term) term.options.scrollback = rows;
  syncSegs();
}
function markSeg(id, value) {
  const box = document.getElementById(id);
  if (!box) return;
  for (const btn of box.querySelectorAll("button")) {
    btn.classList.toggle("on", btn.dataset.v === String(value));
  }
}
function syncSegs() {
  markSeg("seg-theme", localStorage.getItem("portio.theme") ?? "dark");
  markSeg("seg-density", root.dataset.density ?? "standard");
  markSeg("seg-scroll", readScrollback());
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
const settingsModal = document.getElementById("settings-modal");
function toggleSettings(open) {
  const want = open ?? !settingsModal.classList.contains("open");
  if (want) syncSegs();
  settingsModal.classList.toggle("open", want);
}
if (location.hash === "#settings") toggleSettings(true);
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
document.getElementById("seg-scroll").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (btn) setScrollback(Number(btn.dataset.v));
});
document.getElementById("set-font").addEventListener("input", (e) => setFontSize(Number(e.target.value)));

// ---------- 可拖拽尺寸：三处，都持久化 ----------
const PREF = {
  sidebar: { key: "portio.sidebar", min: 180, max: 420 },
  split: { key: "portio.split", min: 0.32, max: 0.66 },
  drawer: { key: "portio.drawer", min: 34, max: 360 },
};

function readNum(key, fallback) {
  const raw = localStorage.getItem(key);
  const n = raw === null ? NaN : Number(raw);
  return Number.isFinite(n) ? n : fallback;
}

// 侧栏宽度
function applySidebar(px) {
  root.style.setProperty("--sidebar", `${Math.round(px)}px`);
  localStorage.setItem(PREF.sidebar.key, String(Math.round(px)));
  positionGutters();
}
// 终端:文件比例
function applySplit(ratio) {
  root.style.setProperty("--split", `${(ratio * 100).toFixed(2)}%`);
  localStorage.setItem(PREF.split.key, ratio.toFixed(4));
  positionGutters();
}
// 抽屉高度
function applyDrawer(px) {
  root.style.setProperty("--drawer", `${Math.round(px)}px`);
  localStorage.setItem(PREF.drawer.key, String(Math.round(px)));
  const head = document.getElementById("drawer-head");
  if (head) head.querySelector(".right").textContent = px <= PREF.drawer.min + 2 ? "展开" : "收起";
  positionGutters();
}

// 把手按当前尺寸贴边定位（绝对定位，不参与栅格）
const mainEl = document.getElementById("main");
const splitEl = document.getElementById("split");
const stageEl = document.querySelector(".stage");
function positionGutters() {
  const sidebar = parseFloat(getComputedStyle(root).getPropertyValue("--sidebar")) || 264;
  const split = parseFloat(getComputedStyle(root).getPropertyValue("--split")) || 50;
  const drawer = parseFloat(getComputedStyle(root).getPropertyValue("--drawer")) || 172;
  document.getElementById("gutter-v").style.left = sidebarFolded ? "0px" : `${sidebar - 3}px`;
  document.getElementById("gutter-split").style.left = `${splitEl.clientWidth * split / 100 - 3}px`;
  document.getElementById("gutter-drawer").style.top = `${stageEl.clientHeight - drawer - 3}px`;
  document.getElementById("gutter-drawer").style.bottom = "auto";
}

// 通用拖拽：按轴更新，松手落盘
function dragWith(axis, onMove) {
  return (e) => {
    e.preventDefault();
    document.body.classList.add(axis === "x" ? "dragging" : "dragging-x");
    const move = (ev) => onMove(ev);
    const up = () => {
      document.body.classList.remove("dragging", "dragging-x");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      positionGutters();
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
}

// 会话栏折叠：收起后整块让给终端，只留一条把手；鼠标移上去箭头才亮
const FOLD_KEY = "portio.sidebarFolded";
let sidebarFolded = localStorage.getItem(FOLD_KEY) === "1";
function applyFold(folded) {
  sidebarFolded = folded;
  mainEl.classList.toggle("collapsed", folded);
  document.getElementById("gutter-v").classList.toggle("folded", folded);
  localStorage.setItem(FOLD_KEY, folded ? "1" : "0");
  if (folded) {
    root.style.setProperty("--sidebar", "0px");
  } else {
    applySidebar(readNum(PREF.sidebar.key, 264));
  }
  positionGutters();
  // 折叠展开改变了终端可用宽度，布局稳定后再 fit 一次，否则列数不对
  requestAnimationFrame(() => fitQuietly());
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

document.getElementById("gutter-split").addEventListener("pointerdown", dragWith("x", (ev) => {
  const box = splitEl.getBoundingClientRect();
  const ratio = (ev.clientX - box.left) / box.width;
  applySplit(Math.min(PREF.split.max, Math.max(PREF.split.min, ratio)));
}));

document.getElementById("gutter-drawer").addEventListener("pointerdown", dragWith("y", (ev) => {
  const box = stageEl.getBoundingClientRect();
  const px = Math.min(PREF.drawer.max, Math.max(PREF.drawer.min, box.bottom - ev.clientY));
  applyDrawer(px);
}));

// 抽屉：点标题栏折叠/展开，比拖拽更常用
let drawerLast = 172;
document.getElementById("drawer-head").addEventListener("click", () => {
  const cur = parseFloat(getComputedStyle(root).getPropertyValue("--drawer")) || 172;
  if (cur > PREF.drawer.min + 2) {
    drawerLast = cur;
    applyDrawer(PREF.drawer.min);
  } else {
    applyDrawer(Math.max(drawerLast, 120));
  }
});

// 侧栏把手双击 = 收起/展开会话栏（Ctrl+Alt+B 同效）
document.getElementById("gutter-v").addEventListener("dblclick", () => {
  if (!sidebarFolded) applyFold(true);
});
document.getElementById("gutter-split").addEventListener("dblclick", () => applySplit(0.5));

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
  if (e.ctrlKey && !e.altKey && e.key.toLowerCase() === "w") {
    e.preventDefault();
    if (tabs.length <= 1) return toast("只剩一个标签了，再关就空窗口");
    closeTab(activeId);
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

function 初次提示() {}

// ---------- 启动：恢复用户上次调好的尺寸 ----------
applyTheme(localStorage.getItem("portio.theme") ?? "dark");
// #theme-light / #theme-dark：截图核验主题图标时直接锁定主题，不用靠点按钮
if (location.hash === "#theme-light") applyTheme("light");
if (location.hash === "#theme-dark") applyTheme("dark");
applyDensity(localStorage.getItem("portio.density") ?? "standard");
applySidebar(readNum(PREF.sidebar.key, 264));
if (sidebarFolded) applyFold(true);
applySplit(Math.min(PREF.split.max, Math.max(PREF.split.min, readNum(PREF.split.key, 0.5))));
applyDrawer(readNum(PREF.drawer.key, 172));
window.addEventListener("resize", positionGutters);

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
let tabs = [];
let activeId = null;
let tabSeq = 0;
// term / fitAddon 已在文件顶部声明（那里要避免 TDZ），这里只做"指向当前标签"
let sessionId = null;

function terminalTheme() {
  const dark = root.dataset.theme === "dark";
  return dark
    ? {
        background: "#090c10", foreground: "#dfe5ec", cursor: "#2fb39a",
        selectionBackground: "#28403b", black: "#1a2029", red: "#d2655f",
        green: "#2fb39a", yellow: "#c99a4e", blue: "#6fa8dc", magenta: "#a98bd0",
        cyan: "#4fb6c7", white: "#dfe5ec",
      }
    : {
        background: "#ffffff", foreground: "#1d242c", cursor: "#12897a",
        selectionBackground: "#cfe8e3", black: "#242c36", red: "#b8453f",
        green: "#12897a", yellow: "#96702c", blue: "#2f6ea5", magenta: "#7a5cb0",
        cyan: "#2c8fa0", white: "#ffffff",
      };
}

function fitQuietly() {
  if (!fitAddon) return;
  try {
    fitAddon.fit();
  } catch (e) {
    // 容器还没布局完时 fit 会抛，这里吞掉即可，ResizeObserver 稍后会再来一次
  }
}

function tabById(id) {
  return tabs.find((t) => t.id === id) ?? null;
}

function renderTabs() {
  tabsBox.textContent = "";
  for (const t of tabs) {
    const el = document.createElement("div");
    el.className = "tab" + (t.id === activeId ? " active" : "");
    el.title = t.title;
    const dot = document.createElement("span");
    dot.className = "dot";
    if (t.sid !== null) dot.style.background = "var(--accent)";
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
  for (const t of tabs) t.pane.classList.toggle("on", t.id === id);
  term = tab.term;
  fitAddon = tab.fit;
  sessionId = tab.sid;
  renderTabs();
  // 容器刚变可见，等一帧再量尺寸，否则 cols/rows 会算成 0
  setTimeout(() => {
    fitQuietly();
    tab.term.focus();
  }, 0);
}

function createTab(title, sid = null) {
  const id = ++tabSeq;
  const pane = document.createElement("div");
  pane.className = "term-pane";
  pane.dataset.id = String(id);
  termHost.appendChild(pane);
  const t = new Terminal({
    fontFamily: "var(--mono), Consolas, monospace",
    fontSize: readFontSize(),
    lineHeight: 1.25,
    cursorBlink: true,
    scrollback: readScrollback(),
    theme: terminalTheme(),
    allowProposedApi: true,
  });
  const fit = new FitAddon.FitAddon();
  t.loadAddon(fit);
  t.open(pane);
  const tab = { id, title, sid, term: t, fit, pane };
  tabs.push(tab);
  // 回调绑定到自己的标签，避免后台标签的输入发到别的会话
  t.onData((data) => {
    if (tab.sid !== null) call("ssh_input", { id: tab.sid, data });
  });
  t.onResize(({ cols, rows }) => {
    if (tab.sid !== null) call("ssh_resize", { id: tab.sid, cols, rows });
  });
  // 终端右键：复制、粘贴、清屏——鼠标党不用记 Ctrl+Shift+V 也能干活
  pane.addEventListener("contextmenu", (ev) => {
    ev.preventDefault();
    const picked = t.getSelection();
    showCtx(ev.clientX, ev.clientY, [
      {
        label: "复制选中",
        hint: picked ? `${picked.length} 字符` : "无选中",
        disabled: !picked,
        run: () => navigator.clipboard.writeText(picked).then(() => toast("选中内容已复制")),
      },
      { label: "粘贴", run: () => pasteInto(tab) },
      { label: "全选", hint: "Ctrl+A", run: () => t.selectAll() },
      { sep: true },
      { label: "清屏", hint: "Ctrl+L", run: () => sendRaw(tab, "\f") },
      { label: "清空滚动缓冲", run: () => t.clear() },
    ]);
  });
  activateTab(id);
  return tab;
}

// 往会话里塞原始控制字符：本地标签没有会话，就写到终端自己身上
function sendRaw(tab, data) {
  if (tab.sid !== null) call("ssh_input", { id: tab.sid, data });
  else tab.term.write(data.replace("\f", ""));
}

async function pasteInto(tab) {
  try {
    const text = await navigator.clipboard.readText();
    if (!text) return;
    if (tab.sid !== null) call("ssh_input", { id: tab.sid, data: text });
    else tab.term.write(text);
    tab.term.focus();
  } catch {
    toast("剪贴板读不出来，检查系统的剪贴板权限");
  }
}

function closeTab(id) {
  const idx = tabs.findIndex((t) => t.id === id);
  if (idx < 0) return;
  const tab = tabs[idx];
  if (tab.sid !== null) call("ssh_disconnect", { id: tab.sid });
  tab.term.dispose();
  tab.pane.remove();
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

function createLocalTab(title = "本地 · 未连接") {
  const tab = createTab(title);
  tab.term.write("Portio · 未连接。点左上「新建连接」开始。\r\n");
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
function openConnect(prefill = null) {
  const el = (id) => document.getElementById(id);
  if (prefill) {
    el("f-host").value = prefill.host ?? "";
    el("f-port").value = String(prefill.port ?? 22);
    el("f-user").value = prefill.user ?? "";
    el("f-auth").value = prefill.auth === "key" ? "key" : "password";
    el("f-key").value = prefill.keyfile ?? "";
    el("field-key").hidden = prefill.auth !== "key";
    el("field-password").hidden = prefill.auth === "key";
  } else {
    el("f-user").value = localStorage.getItem("portio.user") ?? "";
    el("f-host").value = "";
    el("f-password").value = "";
  }
  modal.classList.add("open");
  (prefill?.auth === "key" ? el("f-host") : el("f-password")).focus();
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
  if (!bridge) return;
  bridge
    .invoke("sessions_write", { json: JSON.stringify(sessionStore) })
    .catch((err) => toast(`会话清单没存住：${explainError("sessions_write", String(err))}`));
}
function saveSession(rec) {
  const key = sessionKey(rec);
  const next = sessionStore.records.filter((s) => sessionKey(s) !== key);
  sessionStore.records = [{ ...rec, last: Date.now() }, ...next].slice(0, 40);
  persistSessions();
  renderSessions();
}
function removeSession(key) {
  sessionStore.records = sessionStore.records.filter((s) => sessionKey(s) !== key);
  persistSessions();
  renderSessions();
}
// 启动时从磁盘拉一次；老版本留在 localStorage 里的记录顺手迁过来
function loadSessions() {
  if (!bridge) return renderSessions();
  bridge
    .invoke("sessions_read", {})
    .then((raw) => {
      const text = String(raw ?? "").trim();
      let parsed = { version: 1, records: [] };
      if (text) {
        const obj = JSON.parse(text);
        parsed = Array.isArray(obj) ? { version: 1, records: obj } : obj;
      }
      if (Array.isArray(parsed.records)) sessionStore.records = parsed.records;
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
    })
    .catch((err) => {
      toast(`会话清单读不出来：${explainError("sessions_read", String(err))}`);
      renderSessions();
    });
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
  const list = [...matched].sort((a, b) => (b.last ?? 0) - (a.last ?? 0));
  const recent = list.filter((s) => s.last).slice(0, 5);
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
      document.getElementById("btn-new").after(hint);
    }
    hint.textContent = `没有匹配「${q}」的会话`;
  } else if (hint) {
    hint.remove();
  }
  // 有搜索词就平铺（用户要的是"哪些匹配"），没搜索词才分"最近使用 / 更早"
  const groups = q
    ? [{ label: "", items: list }]
    : [
        { label: "最近使用", items: recent },
        { label: "更早", items: older },
      ];
  let anchor = document.getElementById("sess-search");
  for (const g of groups) {
    if (g.label && g.items.length) {
      const head = document.createElement("div");
      head.className = "sess-group";
      head.textContent = g.label;
      anchor.after(head);
      anchor = head;
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

async function connectWith(spec) {
  const host = String(spec.host ?? "").trim();
  const port = Number(spec.port ?? 22) || 22;
  const user = String(spec.user ?? "").trim();
  if (!host || !user) return toast("主机和用户名都要填");
  const auth = spec.auth === "key" ? "key" : "password";
  const password = auth === "password" ? spec.password ?? null : null;
  const keyfile = auth === "key" ? String(spec.keyfile ?? "").trim() : null;
  if (auth === "password" && !password) return toast("密码没填");
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
    saveSession({ host, port, user, auth, keyfile }); // 密码不入库
    // 连接成功后开一个新标签，标题就是 user@host；旧本地标签留着不动
    const tab = createTab(`${user}@${host}`, id);
    tab.term.write(`\r\n\x1b[2m—— 已连接 ${user}@${host}:${port} ——\x1b[0m\r\n`);
    tab.term.focus();
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
          `如果你确认服务器重装过，删掉 known_hosts 里这台机器的条目再连。\r\n`
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
  });
});

// 会话清单以前端内存镜像为准，启动时从磁盘拉一次
if (location.hash.startsWith("#sess-demo") || location.hash.includes("ctx-demo")) {
  saveSession({ host: "web-01.example.com", port: 22, user: "deploy", auth: "key", keyfile: "~/.ssh/id_ed25519" });
  saveSession({ host: "10.0.8.12", port: 2222, user: "root", auth: "password" });
  // 再塞一条"从没用过"的记录，好核对"更早"这组标题
  sessionStore.records.push({ host: "db-02.internal", port: 22, user: "dba", auth: "password", last: 0 });
  persistSessions();
  renderSessions();
  const q = new URLSearchParams(location.hash.slice(1)).get("q");
  if (q) {
    document.getElementById("sess-search").value = q;
    renderSessions();
  }
} else {
  loadSessions();
}

// ---------- 后端事件 ----------
if (window.__TAURI__?.event) {
  window.__TAURI__.event.listen("shell", (e) => {
    const { id, kind, text } = e.payload ?? {};
    // 按会话 id 找到它所属的标签，后台标签的输出也要落到自己的终端里
    const tab = tabs.find((t) => t.sid === id);
    if (!tab) return;
    const t = tab.term;
    if (kind === "output") t.write(text);
    if (kind === "exit") t.write(`\r\n\x1b[2m[进程退出 ${text}]\x1b[0m\r\n`);
    if (kind === "error") t.write(`\r\n\x1b[31m${text}\x1b[0m\r\n`);
    if (kind === "closed") {
      t.write("\r\n\x1b[2m[连接已断开]\x1b[0m\r\n");
      tab.sid = null;
      if (activeId === tab.id) {
        sessionId = null;
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

// 关窗前把所有会话断干净，别把服务端会话挂在那儿
window.addEventListener("beforeunload", () => {
  for (const t of tabs) {
    if (t.sid !== null) call("ssh_disconnect", { id: t.sid });
  }
});

// 启动就把终端画出来，占位文案说明下一步做什么，避免一块空白面板
ensureTerminal();

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
    row.className = `fp-row${it.is_dir ? " dir" : ""}`;
    row.innerHTML =
      `<span class="ico">${it.is_dir ? "▸" : "·"}</span>` +
      `<span class="nm">${escapeHtml(it.name)}</span>` +
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
  const res = await bridge.invoke("sftp_list", { id: sessionId, path });
  if (!res) { remoteListEl.innerHTML = '<span class="hint">列目录失败，详情见状态栏。</span>'; return; }
  remotePath = path;
  remotePathEl.value = path;
  document.getElementById("files-path").textContent = path;
  document.getElementById("files-mode").textContent = "SFTP";
  renderList(remoteListEl, res, "remote");
}

async function loadLocal(path) {
  const res = await bridge.invoke("local_list", { path: path ?? null });
  if (!res) return;
  const [dir, items] = res;
  localPath = dir;
  localPathEl.value = dir;
  localStorage.setItem("portio.localPath", dir);
  renderList(localListEl, items, "local");
}

// 传输行：先占位，进度事件里按 key 找回来更新
function transferRow(name, dir) {
  const key = `${dir}:${name}`;
  if (transferRows.has(key)) return { key, el: transferRows.get(key) };
  document.querySelector(".drawer-body").querySelector(".hint")?.remove();
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
  document.querySelector(".drawer-body").appendChild(el);
  transferRows.set(key, el);
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
  const bytes = await bridge.invoke("sftp_download", { id: sessionId, remote: item.path, local: target });
  finishTransfer(item.name, "down", bytes);
  if (bytes !== null) loadLocal(localPath);
}

async function uploadFile(item) {
  const target = posixJoin(remotePath, item.name);
  transferRow(item.name, "up");
  const bytes = await bridge.invoke("sftp_upload", { id: sessionId, local: item.path, remote: target });
  finishTransfer(item.name, "up", bytes);
  if (bytes !== null) loadRemote(remotePath);
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
  row.querySelector(".bar i").style.width = ok ? "100%" : "0";
  row.querySelector(".bar i").style.background = ok ? "var(--accent)" : "var(--danger)";
  row.querySelector(".meta").textContent = ok ? `完成 · ${fmtSize(bytes)}` : "失败";
  document.querySelector(".drawer .num").textContent = String(transferRows.size);
  if (window.__TAURI__?.event) {
    // 让队列自动浮出来看一眼，用户不用自己去翻抽屉
    document.querySelector(".drawer").classList.remove("collapsed");
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

// 本地目录不用等连接，界面一出来就能看
loadLocal(localStorage.getItem("portio.localPath") || null);

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
    ? ".term-pane"
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
