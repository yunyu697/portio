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
function applyDensity(density) {
  root.dataset.density = density;
  localStorage.setItem("portio.density", density);
  syncSegs();
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
  if (want) renderHosts();
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
document.getElementById("hosts-list").addEventListener("click", async (e) => {
  const btn = e.target.closest(".hz-del");
  if (!btn) return;
  const port = Number(btn.dataset.port);
  const gone = await call("hosts_forget", { host: btn.dataset.host, port });
  toast(gone ? `已删除 ${btn.dataset.host}:${port} 的记录` : "这条记录已经不在了");
  renderHosts();
});

// ---------- 可拖拽尺寸：三处，都持久化 ----------
const PREF = {
  sidebar: { key: "portio.sidebar", min: 180, max: 420 },
  split: { key: "portio.split", min: 0.32, max: 0.66 },
  // 抽屉的最小高度就是一行标题条：收起时只剩「传输队列 0 … 展开」这一行
  drawer: { key: "portio.drawer", min: 28, max: 360 },
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
}
// 终端:文件比例
function applySplit(ratio) {
  root.style.setProperty("--split", `${(ratio * 100).toFixed(2)}%`);
  localStorage.setItem(PREF.split.key, ratio.toFixed(4));
}
// 抽屉高度
let drawerLast = 172;
function applyDrawer(px) {
  const h = Math.round(px);
  root.style.setProperty("--drawer", `${h}px`);
  localStorage.setItem(PREF.drawer.key, String(h));
  // 收到一行高就算"收起"：正文整块隐藏，别在标题条下面留半指宽的空白
  const collapsed = h <= PREF.drawer.min + 2;
  document.getElementById("drawer").classList.toggle("collapsed", collapsed);
  const head = document.getElementById("drawer-head");
  if (head) head.querySelector(".right").textContent = collapsed ? "展开" : "收起";
  // 抽屉一变，终端可用高度跟着变，量一次尺寸
  requestAnimationFrame(() => fitQuietly());
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

// 文件面板折叠：整块收掉，终端铺满，右缘留一条把手（与会话栏折叠同一套做法）
const FFOLD_KEY = "portio.filesFolded";
let filesFolded = localStorage.getItem(FFOLD_KEY) === "1";
function applyFilesFold(folded) {
  filesFolded = folded;
  splitEl.classList.toggle("files-folded", folded);
  localStorage.setItem(FFOLD_KEY, folded ? "1" : "0");
  const btn = document.getElementById("files-fold");
  if (btn) btn.setAttribute("aria-label", folded ? "展开文件面板" : "折叠文件面板");
  // 终端宽度变了，等一帧让网格落定再量，否则列数按旧宽度算
  requestAnimationFrame(() => fitQuietly());
}

document.getElementById("files-fold").addEventListener("click", () => applyFilesFold(true));

// 折叠态：单击右缘把手把文件面板拉回来；展开态：双击把手回到 50%（拖拽不会误触发 dblclick）
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

// 侧栏把手双击 = 收起/展开会话栏（Ctrl+Alt+B 同效）
document.getElementById("gutter-v").addEventListener("dblclick", () => {
  if (!sidebarFolded) applyFold(true);
});
document.getElementById("gutter-split").addEventListener("dblclick", () => {
  if (filesFolded) applyFilesFold(false);
  else applySplit(0.5);
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
const findHits = { q: "", all: [], at: -1 };
let findTimer = 0;

function findScan(q) {
  const all = [];
  if (!term || !q) return all;
  const buf = term.buffer.active;
  const needle = q.toLowerCase();
  for (let row = 0; row < buf.length; row += 1) {
    const line = buf.getLine(row);
    if (!line) continue;
    const text = line.translateToString(true);
    if (!text) continue;
    const hay = text.toLowerCase();
    let at = hay.indexOf(needle);
    while (at !== -1) {
      all.push({ row, col: at });
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
  term.select(hit.col, hit.row, findHits.q.length);
  term.scrollToLine(Math.max(0, hit.row - Math.floor(term.rows / 2)));
  findPaint();
}

function findRefresh() {
  findHits.q = findInput.value;
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
applySidebar(readNum(PREF.sidebar.key, 264));
if (sidebarFolded) applyFold(true);
applySplit(Math.min(PREF.split.max, Math.max(PREF.split.min, readNum(PREF.split.key, 0.5))));
if (filesFolded) applyFilesFold(true);
applyDrawer(readNum(PREF.drawer.key, 172));


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
  // Ctrl+F 归查找条：先拦住，别让 ^F 被当成输入发给远端
  t.attachCustomKeyEventHandler((ev) => {
    if (ev.type === "keydown" && ev.ctrlKey && !ev.altKey && ev.key.toLowerCase() === "f") return false;
    return true;
  });
  t.open(el);
  const cell = { id: cellId, el, term: t, fit, sid, tab };
  tab.cells.push(cell);
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
        hint: picked ? `${picked.length} 字符` : "无选中",
        disabled: !picked,
        run: () => navigator.clipboard.writeText(picked).then(() => toast("选中内容已复制")),
      },
      { label: "粘贴", run: () => pasteInto(cell) },
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
    const id = await bridge.invoke("ssh_connect", {
      host: spec.host,
      port: Number(spec.port ?? 22) || 22,
      user: spec.user,
      password,
      keyfile: spec.auth === "key" ? String(spec.keyfile ?? "") : null,
      cols: cell.term.cols,
      rows: cell.term.rows,
      onHandshake: null,
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

async function pasteInto(cell) {
  try {
    const text = await navigator.clipboard.readText();
    if (!text) return;
    if (cell.sid !== null) call("ssh_input", { id: cell.sid, data: text });
    else cell.term.write(text);
    cell.term.focus();
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

function createLocalTab(title = "本地 · 未连接") {
  const tab = createTab(title);
  tab.cell.term.write("Portio · 未连接。点左上「新建连接」开始。\r\n");
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
  if (prefill) {
    el("f-host").value = prefill.host ?? "";
    el("f-port").value = String(prefill.port ?? 22);
    el("f-user").value = prefill.user ?? "";
    el("f-auth").value = prefill.auth === "key" ? "key" : "password";
    el("f-key").value = prefill.keyfile ?? "";
    el("f-password").value = "";
    el("field-key").hidden = prefill.auth !== "key";
    el("field-password").hidden = prefill.auth === "key";
  } else {
    el("f-user").value = localStorage.getItem("portio.user") ?? "";
    el("f-host").value = "";
    el("f-password").value = "";
  }
  modal.classList.add("open");
  (prefill?.auth === "key" ? el("f-host") : el("f-password")).focus();
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
}

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
