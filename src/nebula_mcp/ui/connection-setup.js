"use strict";

const form = document.getElementById("connection-form");
const fieldset = document.getElementById("connection-fields");
const statusLine = document.getElementById("setup-status");
const retryButton = document.getElementById("retry-state");
const saveButton = document.getElementById("save-connection");
const passwordHint = document.getElementById("password-hint");
const passwordRequired = document.getElementById("password-required");
const passwordWarning = document.getElementById("password-warning");
const fieldNames = ["addresses", "username", "password", "tls_enabled", "connect_timeout_ms"];
const fields = Object.fromEntries(fieldNames.map((name) => {
  const control = document.getElementById(name);
  return [name, {
    control,
    error: document.getElementById(`${name}-error`),
    hintId: control.getAttribute("aria-describedby"),
  }];
}));
const expired = "设置链接已失效。请回到 Codex，重新打开「配置悦数连接」。";
const saveUnknown = "未收到保存结果，无法确认是否已保存。请重新读取设置；如果链接已失效，请在 Codex 重新打开设置页确认。";
// Wait for the local server's 420-second save-response deadline before aborting.
const saveWaitMs = 430000;
let savedState = null;

function announce(message, kind = "info", focus = false) {
  statusLine.dataset.kind = kind;
  statusLine.textContent = message;
  if (focus) statusLine.focus();
}

function setBusy(busy) {
  fieldset.disabled = busy || savedState === null;
  form.setAttribute("aria-busy", String(busy));
}

function describeField(name) {
  const { control, error, hintId } = fields[name];
  const descriptions = [hintId];
  if (name === "password" && !passwordWarning.hidden) descriptions.push(passwordWarning.id);
  if (!error.hidden) descriptions.push(error.id);
  const describedBy = descriptions.filter(Boolean).join(" ");
  if (describedBy) control.setAttribute("aria-describedby", describedBy);
  else control.removeAttribute("aria-describedby");
}

function showFieldError(name, message = "") {
  const { control, error } = fields[name];
  error.textContent = message;
  error.hidden = !message;
  control.setAttribute("aria-invalid", String(Boolean(message)));
  describeField(name);
}

function updatePasswordWarning() {
  const addressChanged = savedState &&
    fields.addresses.control.value.trim() !== savedState.addresses;
  const usernameChanged = savedState &&
    fields.username.control.value.trim() !== savedState.username;
  const reuse = savedState?.has_password && fields.password.control.value === "";
  passwordWarning.hidden = !(reuse && (addressChanged || usernameChanged));
  if (!passwordWarning.hidden) {
    const changed = addressChanged ? (usernameChanged ? "地址和用户名" : "地址") : "用户名";
    passwordWarning.textContent = `${changed}已更改。密码留空时，测试会使用已保存的密码连接当前填写的地址和用户名。若不想对新连接使用原密码，请输入对应的密码。`;
  }
  describeField("password");
}

async function request(path, timeoutMs, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, {
      mode: "same-origin",
      credentials: "omit",
      cache: "no-store",
      redirect: "error",
      referrerPolicy: "no-referrer",
      signal: controller.signal,
      ...options,
    });
    const data = await response.json().catch(() => null);
    return { response, data };
  } finally {
    clearTimeout(timer);
  }
}

function isExpired(response, data) {
  const codes = ["SETUP_EXPIRED", "SETUP_SESSION_EXPIRED", "SESSION_EXPIRED", "LINK_EXPIRED", "EXPIRED"];
  return response.status === 404 || response.status === 410 || codes.includes(data?.code);
}

function stop(message, allowRead) {
  savedState = null;
  fields.password.control.value = "";
  updatePasswordWarning();
  setBusy(false);
  retryButton.hidden = !allowRead;
  announce(message, "error", true);
}

function validState(data) {
  return data != null &&
    typeof data.addresses === "string" && typeof data.username === "string" &&
    typeof data.has_password === "boolean" && typeof data.tls_enabled === "boolean" &&
    Number.isInteger(data.connect_timeout_ms) &&
    data.connect_timeout_ms >= 100 && data.connect_timeout_ms <= 300000;
}

async function loadState(focusWhenReady = false) {
  retryButton.hidden = true;
  setBusy(true);
  announce("正在读取本机连接设置…");
  try {
    const { response, data } = await request("./state", 10000);
    if (isExpired(response, data)) {
      stop(expired, false);
      return;
    }
    if (!response.ok || !validState(data)) throw new Error("Invalid state response");
    savedState = data;
    fields.addresses.control.value = data.addresses;
    fields.username.control.value = data.username;
    fields.password.control.value = "";
    fields.password.control.required = !data.has_password;
    passwordRequired.hidden = data.has_password;
    passwordHint.textContent = data.has_password
      ? "密码已保存，不会显示。留空会保留原密码，并用它测试你在此页提交的地址和用户名。"
      : "请输入数据库密码。";
    fields.tls_enabled.control.checked = data.tls_enabled;
    fields.connect_timeout_ms.control.value = String(data.connect_timeout_ms);
    fieldNames.forEach((name) => showFieldError(name));
    updatePasswordWarning();
    setBusy(false);
    announce("");
    if (focusWhenReady) fields.addresses.control.focus();
  } catch {
    stop("无法读取本机设置。可重试；如果仍无法读取，请回到 Codex 重新打开设置页。", true);
  }
}

function collectForm() {
  const values = {
    addresses: fields.addresses.control.value.trim(),
    username: fields.username.control.value.trim(),
    password: fields.password.control.value,
    tls_enabled: fields.tls_enabled.control.checked,
    connect_timeout_ms: fields.connect_timeout_ms.control.valueAsNumber,
  };
  const errors = {
    addresses: values.addresses ? "" : "请输入数据库地址，格式为「主机:端口」。",
    username: values.username ? "" : "请输入用户名。",
    password: values.password || savedState.has_password ? "" : "请输入数据库密码。",
    connect_timeout_ms: fields.connect_timeout_ms.control.validity.valid ? "" : "请输入 100 至 300000 的整数（毫秒）。",
  };
  const first = fieldNames.find((name) => errors[name]);
  fieldNames.forEach((name) => showFieldError(name, errors[name]));
  if (first) {
    announce("请检查标出的字段。", "error");
    fields[first].control.focus();
    return null;
  }
  return values;
}

async function saveConnection(event) {
  event.preventDefault();
  if (fieldset.disabled || savedState === null) return;
  const values = collectForm();
  if (values === null) return;
  setBusy(true);
  saveButton.textContent = "正在测试…";
  announce("正在测试连接。测试成功后将保存设置…");
  try {
    const { response, data } = await request("./save", saveWaitMs, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    if (isExpired(response, data)) {
      stop(expired, false);
    } else if (response.status === 200 && data?.ok === true) {
      savedState = null;
      fields.password.control.value = "";
      form.hidden = true;
      setBusy(false);
      announce("连接已测试并保存。可以关闭此标签页，返回 Codex。下次会自动读取此连接。", "success", true);
    } else if (data?.code === "SAVE_STATUS_UNKNOWN") {
      stop(saveUnknown, true);
    } else if (data?.ok === false) {
      setBusy(false);
      const message = typeof data.message === "string" && data.message.trim()
        ? data.message
        : "无法保存设置。请检查连接参数后再试。";
      if (fieldNames.includes(data.field)) {
        showFieldError(data.field, message);
        announce("请检查标出的字段。", "error");
        fields[data.field].control.focus();
      } else {
        announce(message, "error", true);
      }
    } else {
      throw new Error("Invalid save response");
    }
  } catch {
    stop(saveUnknown, true);
  } finally {
    saveButton.textContent = "测试并保存";
  }
}

for (const name of fieldNames) {
  const onEdit = () => {
    showFieldError(name);
    if (name === "addresses" || name === "username" || name === "password") updatePasswordWarning();
  };
  fields[name].control.addEventListener("input", onEdit);
  fields[name].control.addEventListener("change", onEdit);
}

form.addEventListener("submit", saveConnection);
retryButton.addEventListener("click", () => loadState(true));
loadState();
