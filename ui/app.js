// Portio · S1 外壳。所有交互都是真实现；还没做的功能一律给明确提示，不留点了没反应的按钮。
const root = document.documentElement;

// ---------- Tauri 桥 ----------
// withGlobalTauri 打开后 window.__TAURI__.core.invoke 可用；纯浏览器预览时降级为 null。
const bridge = window.__TAURI__?.core ?? null;
async function call(cmd, args) {
  if (!bridge) return null;
  try {
    return await bridge.invoke(cmd, args);
  } catch (err) {
    toast(`调用 ${cmd} 失败：${err}`);
    return null;
  }
}

// ---------- 提示条 ----------
const toastBox = document.getElementById("toast");
function toast(text) {
  const el = document.createElement("div");
  el.textContent = text;
  toastBox.appendChild(el);
  setTimeout(() => el.remove(), 2600);
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
function applyTheme(theme) {
  root.dataset.theme = theme;
  localStorage.setItem("portio.theme", theme);
}
function applyDensity(density) {
  root.dataset.density = density;
  localStorage.setItem("portio.density", density);
}
document.getElementById("btn-theme").addEventListener("click", () => {
  applyTheme(root.dataset.theme === "dark" ? "light" : "dark");
});
document.getElementById("btn-density").addEventListener("click", () => {
  const next = root.dataset.density === "compact" ? "standard" : "compact";
  applyDensity(next);
  toast(next === "compact" ? "已切换到紧凑密度" : "已切换到标准密度");
});

// ---------- 可拖拽尺寸：三处，都持久化 ----------
const PREF = {
  sidebar: { key: "portio.sidebar", min: 180, max: 420 },
  split: { key: "portio.split", min: 0.25, max: 0.75 },
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
  document.getElementById("gutter-v").style.left = `${sidebar - 3}px`;
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

document.getElementById("gutter-v").addEventListener("pointerdown", dragWith("x", (ev) => {
  const left = mainEl.getBoundingClientRect().left;
  const px = Math.min(PREF.sidebar.max, Math.max(PREF.sidebar.min, ev.clientX - left));
  applySidebar(px);
}));

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

// 侧栏把手双击 = 复位默认宽度，省得一点点拖回去
document.getElementById("gutter-v").addEventListener("dblclick", () => applySidebar(264));
document.getElementById("gutter-split").addEventListener("dblclick", () => applySplit(0.5));

// ---------- 快捷键 ----------
window.addEventListener("keydown", (e) => {
  const mod = e.ctrlKey && e.altKey;
  if (mod && e.key.toLowerCase() === "h") {
    e.preventDefault();
    windowAction("fullscreen");
    toast("全屏切换（Ctrl+Alt+H）");
  }
  if (e.ctrlKey && !e.altKey && e.key.toLowerCase() === "t") {
    e.preventDefault();
    toast("新建会话在 S2 接入，届时 Ctrl+T 会直接开标签");
  }
  if (e.ctrlKey && !e.altKey && e.key.toLowerCase() === "w") {
    e.preventDefault();
    toast("关闭标签在 S2 接入；现在只有一个标签");
  }
  if (e.key === "F5") {
    e.preventDefault();
    toast("刷新连接在 S2 接入");
  }
});

function 初次提示() {}

function 初次提示() {}

// ---------- 启动：恢复用户上次调好的尺寸 ----------
applyTheme(localStorage.getItem("portio.theme") ?? "dark");
applyDensity(localStorage.getItem("portio.density") ?? "standard");
applySidebar(readNum(PREF.sidebar.key, 264));
applySplit(readNum(PREF.split.key, 0.5));
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
