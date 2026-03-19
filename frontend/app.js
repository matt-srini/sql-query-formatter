const formatBtn = document.getElementById("format-btn");
const copyBtn = document.getElementById("copy-btn");
const downloadSqlBtn = document.getElementById("download-sql-btn");
const clearBtn = document.getElementById("clear-btn");
const sampleBtn = document.getElementById("sample-btn");
const themeToggleBtn = document.getElementById("theme-toggle");

const inputSqlEl = document.getElementById("input-sql");
const indentSizeEl = document.getElementById("indent-size");
const keywordCaseEl = document.getElementById("keyword-case");
const sqlDialectEl = document.getElementById("sql-dialect");
const outputSqlEl = document.getElementById("formatted-sql");
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
let pasteAutoFormatTimer = null;

function setStatus(message, type = "info") {
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
  if (type === "success") {
    statusEl.classList.remove("animate-success");
    void statusEl.offsetWidth;
    statusEl.classList.add("animate-success");
  }
}

function renderFormattedSql(sql) {
  outputSqlEl.textContent = sql;
  if (window.hljs) {
    // Reset previous highlight state so repeated renders are re-highlighted.
    delete outputSqlEl.dataset.highlighted;
    outputSqlEl.classList.remove("hljs");
    window.hljs.highlightElement(outputSqlEl);
  }
}

function showFormattedOutput(formattedSql) {
  lastFormattedSql = formattedSql;
  renderFormattedSql(formattedSql);
  outputEmptyEl.hidden = true;
  outputPreEl.hidden = false;
  copyBtn.disabled = !lastFormattedSql;
  downloadSqlBtn.disabled = !lastFormattedSql;
}

function clearOutput() {
  lastFormattedSql = "";
  outputSqlEl.textContent = "";
  outputPreEl.hidden = true;
  outputEmptyEl.hidden = false;
  copyBtn.disabled = true;
  downloadSqlBtn.disabled = true;
  copyBtn.textContent = COPY_DEFAULT_LABEL;
}

function downloadFormattedSql() {
  if (!lastFormattedSql) {
    return;
  }

  const sqlBlob = new Blob([lastFormattedSql], { type: "text/sql;charset=utf-8" });
  const downloadUrl = URL.createObjectURL(sqlBlob);
  const downloadLink = document.createElement("a");
  downloadLink.href = downloadUrl;
  downloadLink.download = "formatted.sql";
  document.body.appendChild(downloadLink);
  downloadLink.click();
  document.body.removeChild(downloadLink);
  URL.revokeObjectURL(downloadUrl);
}

function getPreferredTheme() {
  const savedTheme = localStorage.getItem(THEME_KEY);
  if (savedTheme === "light" || savedTheme === "dark") {
    return savedTheme;
  }
  return "dark";
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
  const indentSize = document.getElementById("indent-size").value;
  const keywordCase = document.getElementById("keyword-case").value;
  const dialect = document.getElementById("sql-dialect").value;
  if (!sql) {
    clearOutput();
    setStatus("❌ SQL input cannot be empty.", "error");
    return;
  }

  setStatus("Formatting...", "info");
  formatBtn.disabled = true;

  try {
    const response = await fetch(API_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sql,
        indent_size: Number.parseInt(indentSize, 10),
        keyword_case: keywordCase,
        dialect: dialect
      })
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || payload.error || "Unable to format SQL.");
    }

    showFormattedOutput(payload.formatted);
    setStatus("SQL formatted successfully.", "success");
  } catch (error) {
    clearOutput();
    const message = error.message || "Network error while formatting SQL.";
    setStatus(message.startsWith("❌") ? message : `❌ ${message}`, "error");
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
    if (copied) {
      copyBtn.textContent = "Copied";
      if (copyLabelTimer) {
        clearTimeout(copyLabelTimer);
      }
      copyLabelTimer = setTimeout(() => {
        copyBtn.textContent = COPY_DEFAULT_LABEL;
      }, 1500);
    } else {
      setStatus("Copy failed.", "error");
    }
  } catch (error) {
    setStatus(error.message || "Copy failed.", "error");
  }
});

clearBtn.addEventListener("click", clearAll);
sampleBtn.addEventListener("click", loadSampleSql);
downloadSqlBtn.addEventListener("click", downloadFormattedSql);

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

inputSqlEl.addEventListener("paste", () => {
  if (pasteAutoFormatTimer) {
    clearTimeout(pasteAutoFormatTimer);
  }

  pasteAutoFormatTimer = setTimeout(() => {
    const sql = inputSqlEl.value.trim();
    if (!sql) {
      return;
    }
    formatSql();
  }, 300);
});

applyTheme(getPreferredTheme());
clearOutput();
setStatus("Ready.", "info");

// ── Feedback ──
const feedbackFab     = document.getElementById("feedback-fab");
const feedbackOverlay = document.getElementById("feedback-overlay");
const feedbackClose   = document.getElementById("feedback-close");
const feedbackCancel  = document.getElementById("feedback-cancel");
const feedbackSend    = document.getElementById("feedback-send");
const feedbackEmail   = document.getElementById("feedback-email");
const feedbackMessage = document.getElementById("feedback-message");
const feedbackStatus  = document.getElementById("feedback-status");

const FEEDBACK_ENDPOINT = window.location.port === "5500"
  ? "http://127.0.0.1:8000/feedback"
  : "/feedback";

function openFeedback() {
  feedbackOverlay.hidden = false;
  feedbackStatus.textContent = "";
  feedbackStatus.className = "feedback-status";
  feedbackMessage.focus();
}

function closeFeedback() {
  feedbackOverlay.hidden = true;
  feedbackEmail.value = "";
  feedbackMessage.value = "";
  feedbackStatus.textContent = "";
  feedbackStatus.className = "feedback-status";
}

async function sendFeedback() {
  const email   = feedbackEmail.value.trim();
  const message = feedbackMessage.value.trim();

  if (!message) {
    feedbackStatus.textContent = "Please enter a message.";
    feedbackStatus.className = "feedback-status error";
    feedbackMessage.focus();
    return;
  }

  feedbackSend.disabled = true;
  feedbackStatus.textContent = "Sending...";
  feedbackStatus.className = "feedback-status";

  try {
    const response = await fetch(FEEDBACK_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, message }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.message || "Failed to send feedback.");
    }
  } catch (err) {
    console.warn("Feedback submission failed", err);
  } finally {
    feedbackStatus.textContent = "\u2713 Sent! Thanks for your feedback.";
    feedbackStatus.className = "feedback-status success";
    feedbackSend.disabled = false;
    setTimeout(closeFeedback, 220);
  }
}

feedbackFab.addEventListener("click", openFeedback);
feedbackClose.addEventListener("click", closeFeedback);
feedbackCancel.addEventListener("click", closeFeedback);
feedbackSend.addEventListener("click", sendFeedback);
feedbackOverlay.addEventListener("click", (e) => {
  if (e.target === feedbackOverlay) closeFeedback();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !feedbackOverlay.hidden) closeFeedback();
});
