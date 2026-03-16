const formatBtn = document.getElementById("format-btn");
const copyBtn = document.getElementById("copy-btn");
const clearBtn = document.getElementById("clear-btn");
const sampleBtn = document.getElementById("sample-btn");
const themeToggleBtn = document.getElementById("theme-toggle");

const inputSqlEl = document.getElementById("input-sql");
const outputSqlEl = document.getElementById("output-sql");
const outputPreEl = document.getElementById("output-pre");
const outputEmptyEl = document.getElementById("output-empty");
const statusEl = document.getElementById("status");

const lightThemeLink = document.getElementById("hljs-light-theme");
const darkThemeLink = document.getElementById("hljs-dark-theme");

const THEME_KEY = "sqlFormatterTheme";
const API_ENDPOINT = window.location.port === "5500"
  ? "http://127.0.0.1:8000/format"
  : "/format";
const COPY_DEFAULT_LABEL = "Copy";

let lastFormattedSql = "";
let copyLabelTimer = null;

function setStatus(message, type = "info") {
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
}

function showFormattedOutput(formattedSql) {
  lastFormattedSql = formattedSql;
  outputSqlEl.textContent = formattedSql;
  outputEmptyEl.hidden = true;
  outputPreEl.hidden = false;
  copyBtn.disabled = !lastFormattedSql;
  if (window.hljs) {
    window.hljs.highlightElement(outputSqlEl);
  }
}

function clearOutput() {
  lastFormattedSql = "";
  outputSqlEl.textContent = "";
  outputPreEl.hidden = true;
  outputEmptyEl.hidden = false;
  copyBtn.disabled = true;
  copyBtn.textContent = COPY_DEFAULT_LABEL;
}

function getPreferredTheme() {
  const savedTheme = localStorage.getItem(THEME_KEY);
  if (savedTheme === "light" || savedTheme === "dark") {
    return savedTheme;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// Keep theme behavior isolated so button labels and highlight styles stay in sync.
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const darkMode = theme === "dark";
  darkThemeLink.disabled = !darkMode;
  lightThemeLink.disabled = darkMode;
  themeToggleBtn.textContent = darkMode ? "Light Mode" : "Dark Mode";
}

async function copyToClipboard(text) {
  if (!text) {
    return false;
  }

  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return true;
  }

  const fallbackTextArea = document.createElement("textarea");
  fallbackTextArea.value = text;
  fallbackTextArea.style.position = "fixed";
  fallbackTextArea.style.opacity = "0";
  document.body.appendChild(fallbackTextArea);
  fallbackTextArea.focus();
  fallbackTextArea.select();
  const copied = document.execCommand("copy");
  document.body.removeChild(fallbackTextArea);
  return copied;
}

async function formatSql() {
  const sql = inputSqlEl.value.trim();
  if (!sql) {
    clearOutput();
    setStatus("Please enter SQL to format.", "error");
    return;
  }

  setStatus("Formatting...", "info");
  formatBtn.disabled = true;

  try {
    const response = await fetch(API_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql })
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Unable to format SQL.");
    }

    showFormattedOutput(payload.formatted);
    setStatus("SQL formatted successfully.", "success");
  } catch (error) {
    clearOutput();
    setStatus(error.message || "Network error while formatting SQL.", "error");
  } finally {
    formatBtn.disabled = false;
  }
}

function loadSampleSql() {
  inputSqlEl.value = `SELECT u.id,
       u.email,
       d.name AS department_name,
       COUNT(o.id) AS order_count,
       SUM(o.total_amount) AS total_revenue
FROM users u
JOIN departments d ON d.id = u.department_id
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.is_active = 1
  AND o.created_at >= '2026-01-01'
GROUP BY u.id, u.email, d.name;`;
  setStatus("Sample SQL loaded.", "info");
}

function clearAll() {
  inputSqlEl.value = "";
  clearOutput();
  setStatus("Cleared.", "info");
}

formatBtn.addEventListener("click", formatSql);

copyBtn.addEventListener("click", async () => {
  try {
    const copied = await copyToClipboard(lastFormattedSql);
    setStatus(copied ? "Copied to clipboard." : "Copy failed.", copied ? "success" : "error");
    if (copied) {
      copyBtn.textContent = "Copied";
      if (copyLabelTimer) {
        clearTimeout(copyLabelTimer);
      }
      copyLabelTimer = setTimeout(() => {
        copyBtn.textContent = COPY_DEFAULT_LABEL;
      }, 1500);
    }
  } catch (error) {
    setStatus(error.message || "Copy failed.", "error");
  }
});

clearBtn.addEventListener("click", clearAll);
sampleBtn.addEventListener("click", loadSampleSql);

themeToggleBtn.addEventListener("click", () => {
  const currentTheme = document.documentElement.getAttribute("data-theme") || "light";
  const nextTheme = currentTheme === "dark" ? "light" : "dark";
  applyTheme(nextTheme);
  localStorage.setItem(THEME_KEY, nextTheme);
});

// Cmd+Enter on macOS and Ctrl+Enter on other systems formats immediately.
document.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    formatSql();
  }
});

applyTheme(getPreferredTheme());
clearOutput();
setStatus("Ready.", "info");
