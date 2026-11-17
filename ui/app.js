// Portio · S1 外壳。所有交互都是真实现；还没做的功能一律给明确提示，不留点了没反应的按钮。
const root = document.documentElement;

// 前端一有异常就把信息写进标题，出问题时不至于对着空白面板瞎猜
window.addEventListener("error", (e) => {
  document.title = "ERR: " + (e.message || e.error);
  const st = document.querySelector('.statusbar .state');
  if (st) st.textContent = 'ERR ' + (e.message || e.error);
});

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
const termHost = document.getElementById("term");
let term = null;
let fitAddon = null;
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

function ensureTerminal() {
  if (term) return term;
  term = new Terminal({
    fontFamily: "var(--mono), Consolas, monospace",
    fontSize: 13,
    lineHeight: 1.25,
    cursorBlink: true,
    scrollback: 8000,
    theme: terminalTheme(),
    allowProposedApi: true,
  });
  fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  term.open(termHost);
  fitQuietly();
  term.write("Portio · 未连接。点左上「新建连接」开始。\r\n");

  term.onData((data) => {
    if (sessionId !== null) call("ssh_input", { id: sessionId, data });
  });
  term.onResize(({ cols, rows }) => {
    if (sessionId !== null) call("ssh_resize", { id: sessionId, cols, rows });
  });
  new ResizeObserver(() => fitQuietly()).observe(termHost);
  window.addEventListener("resize", () => fitQuietly());
  return term;
}

// ---------- 会话状态 ----------
function setStatus(text, tone) {
  const el = document.querySelector(".statusbar .state");
  el.innerHTML = `<i></i>${text}`;
  el.style.color = tone === "ok" ? "var(--accent)" : tone === "bad" ? "var(--danger)" : "";
  el.querySelector("i").style.background =
    tone === "ok" ? "var(--accent)" : tone === "bad" ? "var(--danger)" : "var(--text-3)";
}

function addSessionRow(label) {
  document.querySelector(".sidebar .empty")?.remove();
  const row = document.createElement("div");
  row.className = "tab active";
  row.style.cssText =
    "margin:8px 12px 0;border-radius:var(--r-4);height:30px;border-bottom:1px solid var(--line)";
  row.innerHTML = `<span class="dot" style="background:var(--accent)"></span><span class="name">${label}</span>`;
  document.querySelector(".sidebar").appendChild(row);
  document.getElementById("session-count").textContent = "1";
}

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
function openConnect() {
  document.getElementById("f-user").value = localStorage.getItem("portio.user") ?? "";
  modal.classList.add("open");
  document.getElementById("f-host").focus();
}

document.getElementById("btn-connect").addEventListener("click", async () => {
  const host = document.getElementById("f-host").value.trim();
  const port = Number(document.getElementById("f-port").value || 22);
  const user = document.getElementById("f-user").value.trim();
  if (!host || !user) return toast("主机和用户名都要填");
  localStorage.setItem("portio.user", user);

  const auth = authSelect.value;
  const password = auth === "password" ? document.getElementById("f-password").value : null;
  const keyfile = auth === "key" ? document.getElementById("f-key").value.trim() : null;
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
    sessionId = id;
    modal.classList.remove("open");
    setStatus(`已连接 ${user}@${host}:${port}`, "ok");
    addSessionRow(`${user}@${host}`);
    document.querySelector(".tab .name").textContent = `${user}@${host}`;
    term.focus();
    term.write(`\r\n\x1b[2m—— 已连接 ${user}@${host}:${port} ——\x1b[0m\r\n`);
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
      setStatus("连接失败", "bad");
      term.write(`\r\n\x1b[31m连接失败：${raw}\x1b[0m\r\n`);
      toast("连接失败，详情见终端");
    }
  } finally {
    btn.disabled = false;
    btn.textContent = "连接";
  }
});

// ---------- 后端事件 ----------
if (window.__TAURI__?.event) {
  window.__TAURI__.event.listen("shell", (e) => {
    const { id, kind, text } = e.payload ?? {};
    if (id !== sessionId) return;
    ensureTerminal();
    if (kind === "output") term.write(text);
    if (kind === "exit") term.write(`\r\n\x1b[2m[进程退出 ${text}]\x1b[0m\r\n`);
    if (kind === "error") term.write(`\r\n\x1b[31m${text}\x1b[0m\r\n`);
    if (kind === "closed") {
      setStatus("连接已断开", "bad");
      term.write("\r\n\x1b[2m[连接已断开]\x1b[0m\r\n");
      sessionId = null;
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

// 关窗前把连接断干净，别把服务端会话挂在那儿
window.addEventListener("beforeunload", () => {
  if (sessionId !== null) call("ssh_disconnect", { id: sessionId });
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
document.getElementById("remote-mkdir").addEventListener("click", async () => {
  const name = window.prompt("新目录名");
  if (!name) return;
  await call("sftp_mkdir", { id: sessionId, path: posixJoin(remotePath, name) });
  loadRemote(remotePath);
});

if (window.__TAURI__?.event) {
  window.__TAURI__.event.listen("transfer", (e) => updateTransfer(e.payload));
}

// 本地目录不用等连接，界面一出来就能看
loadLocal(localStorage.getItem("portio.localPath") || null);
