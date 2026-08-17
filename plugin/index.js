const { entrypoints, shell } = require("uxp");
const { localFileSystem } = require("uxp").storage;
const premiere = require("premierepro");

const API_CANDIDATES = ["http://127.0.0.1:18765", "http://localhost:18765"];
let activeApi = API_CANDIDATES[0];
let currentJobId = null;
let currentFilePath = null;
let currentFolder = null;
let pollTimer = null;
let selectedOutputFolder = "";
let outputFolderWasChosen = false;

const $ = (id) => document.getElementById(id);

function setHelperOnline(online) {
  $("helperDot").classList.toggle("online", online);
  $("helperDot").title = online ? "PacheVideo Helper conectado" : "Helper desconectado";
}

function updateProgress(percent, status, detail = "") {
  const safe = Math.max(0, Math.min(100, Number(percent) || 0));
  $("progressBar").style.width = `${safe}%`;
  $("percent").textContent = `${Math.round(safe)}%`;
  $("status").textContent = status;
  if (detail) $("detail").textContent = detail;
}

function parentFolder(filePath) {
  const normalized = String(filePath || "").replace(/\\/g, "/");
  const separator = normalized.lastIndexOf("/");
  if (separator < 0) return "";
  if (separator === 0) return "/";
  if (separator === 2 && normalized[1] === ":") return normalized.slice(0, 3);
  return normalized.slice(0, separator);
}

function showOutputFolder(folder, source) {
  selectedOutputFolder = folder || "";
  $("outputFolder").value = selectedOutputFolder;
  $("outputFolder").title = selectedOutputFolder;
  $("folderHint").textContent = source;
}

async function setAutomaticOutputFolder(fallbackFolder = "") {
  if (outputFolderWasChosen) return;

  try {
    const project = await premiere.Project.getActiveProject();
    const projectFolder = parentFolder(project && project.path);
    if (projectFolder) {
      showOutputFolder(projectFolder, "Predeterminada: carpeta del proyecto de Premiere.");
      return;
    }
  } catch (_) {
    // El helper provee el destino seguro cuando no hay proyecto activo.
  }

  showOutputFolder(fallbackFolder, "Proyecto sin guardar: se usa Descargas/PacheVideo.");
}

async function chooseOutputFolder() {
  try {
    const folder = await localFileSystem.getFolder();
    if (!folder) return;
    outputFolderWasChosen = true;
    showOutputFolder(folder.nativePath, "Carpeta elegida manualmente.");
  } catch (error) {
    updateProgress(0, "No se pudo elegir la carpeta", error.message);
  }
}

async function api(path, options = {}, baseUrl = activeApi) {
  const response = await fetch(`${baseUrl}${path}`, {
    ...options,
    credentials: "omit",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

async function checkHelper() {
  let lastError = null;
  for (const candidate of API_CANDIDATES) {
    try {
      const health = await api("/health", {}, candidate);
      activeApi = candidate;
      setHelperOnline(true);
      await setAutomaticOutputFolder(health.outputFolder);
      updateProgress(0, "Listo para descargar", `Destino · ${selectedOutputFolder || health.outputFolder}`);
      $("downloadButton").disabled = false;
      return;
    } catch (error) {
      lastError = error;
    }
  }

  setHelperOnline(false);
  $("downloadButton").disabled = true;
  const reason = lastError ? `${lastError.name || "Error"}: ${lastError.message}` : "Sin respuesta";
  updateProgress(0, "El panel no puede acceder al helper", `Puerto 18765 · ${reason}. Recargá el manifiesto en UXP.`);
}

async function pasteUrl() {
  try {
    const content = await navigator.clipboard.getContent();
    if (content["text/plain"]) $("url").value = content["text/plain"].trim();
  } catch (error) {
    updateProgress(0, "No se pudo leer el portapapeles", error.message);
  }
}

function onModeChanged() {
  const audio = $("mode").value === "audio";
  $("videoQualityField").classList.toggle("hidden", audio);
  $("audioQualityField").classList.toggle("hidden", !audio);
}

async function startDownload() {
  const url = $("url").value.trim();
  if (!/^https?:\/\//i.test(url)) {
    updateProgress(0, "Ingresá una URL válida", "La dirección debe comenzar con http:// o https://");
    return;
  }

  $("downloadButton").disabled = true;
  $("importButton").disabled = true;
  $("folderButton").disabled = true;
  currentFilePath = null;
  currentFolder = null;
  updateProgress(1, "Iniciando descarga…", "Preparando yt-dlp");

  try {
    const job = await api("/downloads", {
      method: "POST",
      body: JSON.stringify({
        url,
        mode: $("mode").value,
        quality: $("mode").value === "audio" ? "max" : $("quality").value,
        audioKbps: $("audioKbps").value,
        outputFolder: selectedOutputFolder,
      }),
    });
    currentJobId = job.id;
    schedulePoll(250);
  } catch (error) {
    setHelperOnline(false);
    $("downloadButton").disabled = false;
    updateProgress(0, "No se pudo iniciar", error.message);
  }
}

function schedulePoll(delay = 650) {
  if (pollTimer) clearTimeout(pollTimer);
  pollTimer = setTimeout(pollJob, delay);
}

async function pollJob() {
  if (!currentJobId) return;
  try {
    const job = await api(`/downloads/${currentJobId}`);
    setHelperOnline(true);
    updateProgress(job.progress, job.message || "Descargando…", job.detail || "");

    if (job.status === "complete") {
      currentFilePath = job.filePath;
      currentFolder = job.folder;
      $("downloadButton").disabled = false;
      $("importButton").disabled = false;
      $("folderButton").disabled = false;
      if ($("autoImport").checked) await importCurrentFile();
      return;
    }
    if (job.status === "error") {
      $("downloadButton").disabled = false;
      updateProgress(job.progress, "Error de descarga", job.error || job.detail);
      return;
    }
    schedulePoll();
  } catch (error) {
    setHelperOnline(false);
    $("downloadButton").disabled = false;
    updateProgress(0, "Se perdió la conexión con el helper", error.message);
  }
}

async function importCurrentFile() {
  if (!currentFilePath) return;
  try {
    updateProgress(100, "Importando en Premiere…", currentFilePath);
    const project = await premiere.Project.getActiveProject();
    if (!project) throw new Error("No hay un proyecto activo en Premiere.");
    const targetBin = (await project.getInsertionBin()) || (await project.getRootItem());
    const imported = await project.importFiles([currentFilePath], true, targetBin, false);
    if (!imported) throw new Error("Premiere rechazó la importación del archivo.");
    updateProgress(100, "✓ Descargado e importado", currentFilePath);
  } catch (error) {
    updateProgress(100, "Descargado, pero no importado", error.message);
  }
}

async function openCurrentFolder() {
  if (!currentFolder) return;
  const result = await shell.openPath(currentFolder, "Abrir la carpeta de descargas de PacheVideo");
  if (result) updateProgress(100, "No se pudo abrir la carpeta", result);
}

function wireUi() {
  $("pasteButton").addEventListener("click", pasteUrl);
  $("mode").addEventListener("change", onModeChanged);
  $("chooseFolderButton").addEventListener("click", chooseOutputFolder);
  $("downloadButton").addEventListener("click", startDownload);
  $("importButton").addEventListener("click", importCurrentFile);
  $("folderButton").addEventListener("click", openCurrentFolder);
  $("reconnectButton").addEventListener("click", checkHelper);
  onModeChanged();
  checkHelper();
}

document.addEventListener("DOMContentLoaded", wireUi);

entrypoints.setup({
  panels: {
    pachevideoPanel: {
      show() {
        checkHelper();
      },
    },
  },
});
