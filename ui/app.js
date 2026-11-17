// S1 只做三件真事：主题切换、密度切换、窗口按钮。
// 其余交互等 1.2 落地，先不留"看起来能点但没反应"的僵尸按钮。
const root = document.documentElement;

function toggleTheme() {
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
}

async function windowAction(action) {
  // Tauri 2：前端调用窗口命令。不在 Tauri 环境里时静默降级，方便直接用浏览器看样式。
  const tauri = window.__TAURI__;
  if (!tauri) return;
  const cur = tauri.window.getCurrentWindow();
  if (action === "minimize") await cur.minimize();
  if (action === "maximize") await cur.toggleMaximize();
  if (action === "close") await cur.close();
}

document.getElementById("btn-min")?.addEventListener("click", () => windowAction("minimize"));
document.getElementById("btn-max")?.addEventListener("click", () => windowAction("maximize"));
document.getElementById("btn-close")?.addEventListener("click", () => windowAction("close"));

// 双击标题栏 = 最大化，和原生窗口行为保持一致
document.querySelector(".titlebar")?.addEventListener("dblclick", (e) => {
  if (e.target.closest("button")) return;
  windowAction("maximize");
});

window.toggleTheme = toggleTheme;
