const API_URL = "http://127.0.0.1:8000";

const form = document.querySelector("#error-form");
const codeInput = document.querySelector("#error-code");
const fileInput = document.querySelector("#image-file");
const dropZone = document.querySelector("#drop-zone");
const fileName = document.querySelector("#file-name");
const formStatus = document.querySelector("#form-status");
const submitButton = form.querySelector("button[type=submit]");
const result = document.querySelector("#result");
const resultTitle = document.querySelector("#result-title");
const resultSource = document.querySelector("#result-source");
const resultLevel = document.querySelector("#result-level");
const resultTime = document.querySelector("#result-time");
const resultSummary = document.querySelector("#result-summary");
const resultHelp = document.querySelector("#result-help");
const resultSources = document.querySelector("#result-sources");
const probableCauses = document.querySelector("#probable-causes");
const detectedErrors = document.querySelector("#detected-errors");
const resultSteps = document.querySelector("#result-steps");
const effectiveness = document.querySelector("#effectiveness");
const feedbackYes = document.querySelector("#feedback-yes");
const feedbackNo = document.querySelector("#feedback-no");
const feedbackStatus = document.querySelector("#feedback-status");
const guideGrid = document.querySelector("#guide-grid");
const guideFilter = document.querySelector("#guide-filter");
const guideEmpty = document.querySelector("#guide-empty");
const categoryTabs = document.querySelector("#category-tabs");
let currentSolution = null;
let activeCategory = "todas";

function showStatus(message) {
  formStatus.textContent = message;
}

const STEP_TYPES = {
  configuracion: { label: "Configuración", icon: "⚙" },
  terminal: { label: "Terminal", icon: "›_" },
  advertencia: { label: "Atención", icon: "!" },
  reinicio: { label: "Reinicio", icon: "↻" },
};

async function getErrorMessage(response, fallback) {
  try {
    const payload = await response.json();
    return payload.detail || fallback;
  } catch {
    return fallback;
  }
}

function normalizeCode(value) {
  return value.trim().toUpperCase().replace(/\s+/g, " ");
}

function findGuide(codes) {
  const wanted = codes.map(normalizeCode);
  return GUIDES.find((guide) =>
    [guide.code, ...guide.aliases].some((code) => wanted.includes(normalizeCode(code)))
  );
}

function renderSteps(steps) {
  return steps.map((step, index) => {
    const item = document.createElement("li");
    const stepTag = (step.tags?.[0] || step.tipo || "configuracion").replace("configuración", "configuracion");
    item.className = `step-card step-${stepTag}`;

    const number = document.createElement("span");
    number.className = "step-number";
    number.textContent = step.number || index + 1;

    const body = document.createElement("div");
    body.className = "step-body";
    const header = document.createElement("div");
    header.className = "step-header";

    const type = STEP_TYPES[stepTag] || STEP_TYPES.configuracion;
    const tag = document.createElement("span");
    tag.className = "step-type";
    tag.textContent = `${type.icon} ${type.label}`;

    const title = document.createElement("h3");
    title.textContent = step.title;
    header.append(title, tag);
    body.appendChild(header);

    const detail = document.createElement("p");
    detail.className = "step-detail";
    detail.textContent = step.detail;
    body.appendChild(detail);

    if (step.how_to && step.how_to !== step.detail) {
      const howTo = document.createElement("p");
      howTo.className = "step-how-to";
      const howToLabel = document.createElement("strong");
      howToLabel.textContent = "Cómo hacerlo: ";
      howTo.append(howToLabel, document.createTextNode(step.how_to));
      body.appendChild(howTo);
    }

    if (step.comando) {
      const terminal = document.createElement("div");
      terminal.className = "terminal-block";
      const terminalBar = document.createElement("div");
      terminalBar.className = "terminal-bar";
      terminalBar.innerHTML = '<span class="terminal-lights"><i></i><i></i><i></i></span><span>Terminal de Windows</span>';
      const copy = document.createElement("button");
      copy.className = "copy-command";
      copy.type = "button";
      copy.textContent = "Copiar";
      copy.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(step.comando);
          copy.textContent = "✓ Copiado";
          setTimeout(() => { copy.textContent = "Copiar"; }, 2000);
        } catch {
          copy.textContent = "Selecciona el texto";
        }
      });
      terminalBar.appendChild(copy);
      terminal.appendChild(terminalBar);
      const command = document.createElement("code");
      command.textContent = step.comando;
      terminal.appendChild(command);
      body.appendChild(terminal);

      if (step.command_explanation) {
        const commandExplanation = document.createElement("p");
        commandExplanation.className = "command-explanation";
        commandExplanation.textContent = step.command_explanation;
        body.appendChild(commandExplanation);
      }
    }

    item.append(number, body);
    return item;
  });
}

function setPill(element, text) {
  element.hidden = !text;
  element.textContent = text || "";
}

function showResult({ title, summary, causes, errors, steps, solution, isGuide, level, time, help, sources }) {
  result.hidden = false;
  currentSolution = solution;
  resultTitle.textContent = title;
  resultSummary.textContent = summary;

  resultSource.className = `source-badge ${isGuide ? "is-guide" : "is-ai"}`;
  resultSource.textContent = isGuide ? "✓ Guía revisada por NoMore Errors" : "✦ Generada con IA";
  setPill(resultLevel, level && `Dificultad: ${level}`);
  setPill(resultTime, time && `⏱ ${time}`);

  probableCauses.replaceChildren();
  if (causes.length) {
    const heading = document.createElement("strong");
    heading.textContent = "Causas más probables";
    const causeList = document.createElement("ul");
    causes.forEach((cause) => {
      const item = document.createElement("li");
      item.textContent = cause;
      causeList.appendChild(item);
    });
    probableCauses.append(heading, causeList);
  }

  detectedErrors.replaceChildren(...errors.map((error) => {
    const tag = document.createElement("span");
    tag.className = "error-tag";
    tag.textContent = error;
    return tag;
  }));
  resultSteps.replaceChildren(...renderSteps(steps));

  resultHelp.hidden = !help;
  resultHelp.querySelector("p").textContent = help || "";
  resultSources.textContent = sources || "";

  updateEffectiveness(solution.effectiveness_percentage, solution.total_votes);
  feedbackYes.disabled = false;
  feedbackNo.disabled = false;
  feedbackYes.classList.remove("is-selected");
  feedbackNo.classList.remove("is-selected");
  feedbackStatus.textContent = "";
  result.scrollIntoView({ behavior: "smooth", block: "start" });
  result.focus({ preventScroll: true });
}

function showGuide(guide, detected) {
  const solution = {
    error_code: guide.code,
    solution_id: `guide_${guide.id}`,
    effectiveness_percentage: null,
    total_votes: 0,
  };
  showResult({
    title: guide.title,
    summary: guide.explanation,
    causes: guide.causes,
    errors: detected?.length ? detected : [guide.symptom || guide.code],
    steps: guide.steps,
    solution,
    isGuide: true,
    level: GUIDE_LEVELS[guide.level],
    time: guide.time,
    help: guide.help,
  });
  loadGuideStats(solution);
}

async function loadGuideStats(solution) {
  try {
    const params = new URLSearchParams({ error_code: solution.error_code, solution_id: solution.solution_id });
    const response = await fetch(`${API_URL}/api/feedback/stats?${params}`);
    if (!response.ok || currentSolution !== solution) return;
    const stats = await response.json();
    solution.effectiveness_percentage = stats.effectiveness_percentage;
    solution.total_votes = stats.total_votes;
    updateEffectiveness(stats.effectiveness_percentage, stats.total_votes);
  } catch {
    // Sin backend la guía se puede leer igual; solo faltan los votos.
  }
}

function updateEffectiveness(percentage, totalVotes) {
  effectiveness.textContent = percentage === null
    ? "Todavía no hay votos. ¡Sé el primero!"
    : `${percentage}% de personas lo solucionaron · ${totalVotes} voto${totalVotes === 1 ? "" : "s"}`;
}

function setSelectedFile(file) {
  if (!file) return;
  fileName.textContent = `📎 ${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
}

function setLoading(isLoading) {
  submitButton.disabled = isLoading;
  submitButton.classList.toggle("is-loading", isLoading);
}

fileInput.addEventListener("change", () => setSelectedFile(fileInput.files[0]));

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("is-dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("is-dragging");
  });
});

dropZone.addEventListener("drop", (event) => setSelectedFile(event.dataTransfer.files[0]));
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const code = codeInput.value.trim();
  const file = fileInput.files[0];

  if (!code && !file) {
    showStatus("Escribe un código o selecciona una imagen para continuar.");
    codeInput.focus();
    return;
  }

  if (code && !file) {
    const guide = findGuide([code]);
    if (guide) {
      showGuide(guide);
      showStatus("Tenemos una guía revisada para este error.");
      return;
    }
  }

  setLoading(true);
  showStatus(file ? "Leyendo la imagen..." : "Buscando una explicación...");

  try {
    let detectedCode = code;
    let ocrResult = null;
    if (file) {
      const body = new FormData();
      body.append("file", file);
      const ocrResponse = await fetch(`${API_URL}/api/v1/errors/ocr`, { method: "POST", body });
      if (!ocrResponse.ok) throw new Error(await getErrorMessage(ocrResponse, "No se pudo leer la imagen."));
      ocrResult = await ocrResponse.json();
      if (!ocrResult.extracted_text || !ocrResult.detected_errors.length) {
        throw new Error(ocrResult.message || "No encontramos un código claro en la imagen.");
      }
      const guide = findGuide(ocrResult.detected_errors);
      if (guide) {
        showGuide(guide, ocrResult.detected_errors);
        showStatus("Tenemos una guía revisada para este error.");
        return;
      }
      detectedCode = ocrResult.detected_errors[0];
    }

    showStatus("Preparando una solución con IA, puede tardar unos segundos...");
    const analysisResponse = await fetch(`${API_URL}/api/v1/solutions/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ error_code: detectedCode, error_text: ocrResult?.extracted_text || "" }),
    });
    if (!analysisResponse.ok) throw new Error(await getErrorMessage(analysisResponse, "No se pudo analizar el error."));
    const analysis = await analysisResponse.json();
    showResult({
      title: `Solución para ${analysis.error_code}`,
      summary: analysis.simple_explanation,
      causes: analysis.causes || analysis.probable_causes || [],
      errors: ocrResult?.detected_errors || [analysis.error_code],
      steps: analysis.steps,
      solution: analysis,
      isGuide: false,
      sources: analysis.sources_summary,
    });
    showStatus("Solución lista. Sigue los pasos en orden y revisa los avisos.");
  } catch (error) {
    const offline = error instanceof TypeError;
    showStatus(offline
      ? "No se pudo conectar con el servidor. ¿Está arrancado el backend en el puerto 8000?"
      : error.message || "No se pudo analizar el error.");
  } finally {
    setLoading(false);
  }
});

document.querySelectorAll(".chip[data-code]").forEach((chip) => {
  chip.addEventListener("click", () => {
    codeInput.value = chip.dataset.code;
    form.requestSubmit();
  });
});

document.querySelector("#result-close").addEventListener("click", () => {
  result.hidden = true;
  currentSolution = null;
  if (location.hash.startsWith("#guia/")) history.replaceState(null, "", location.pathname);
  showStatus("");
  document.querySelector("#buscar").scrollIntoView({ behavior: "smooth" });
});

async function sendFeedback(success, button) {
  if (!currentSolution) return;
  feedbackYes.disabled = true;
  feedbackNo.disabled = true;
  feedbackStatus.textContent = "Guardando tu respuesta...";

  try {
    const response = await fetch(`${API_URL}/api/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        error_code: currentSolution.error_code,
        solution_id: currentSolution.solution_id,
        success,
      }),
    });
    if (!response.ok) throw new Error(await getErrorMessage(response, "No se pudo guardar tu respuesta."));
    const feedback = await response.json();
    updateEffectiveness(feedback.effectiveness_percentage, feedback.total_votes);
    button.classList.add("is-selected");
    feedbackStatus.textContent = feedback.message;
  } catch (error) {
    feedbackStatus.textContent = error instanceof TypeError
      ? "No se pudo conectar con el servidor para guardar tu voto."
      : error.message || "No se pudo guardar tu respuesta.";
  } finally {
    feedbackYes.disabled = false;
    feedbackNo.disabled = false;
  }
}

feedbackYes.addEventListener("click", () => sendFeedback(true, feedbackYes));
feedbackNo.addEventListener("click", () => sendFeedback(false, feedbackNo));

// Galería de guías revisadas
function guideMatches(guide, query) {
  if (activeCategory !== "todas" && guide.category !== activeCategory) return false;
  if (!query) return true;
  const haystack = [guide.title, guide.summary, guide.code, ...guide.aliases].join(" ").toLowerCase();
  return haystack.includes(query);
}

function renderGuideCard(guide) {
  const category = GUIDE_CATEGORIES[guide.category];
  const card = document.createElement("button");
  card.type = "button";
  card.className = "guide-card";

  const top = document.createElement("div");
  top.className = "guide-card-top";
  const categoryLabel = document.createElement("span");
  categoryLabel.className = "guide-category";
  const icon = document.createElement("i");
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = category.icon;
  categoryLabel.append(icon, category.label);
  const level = document.createElement("span");
  level.className = `level level-${guide.level}`;
  level.textContent = GUIDE_LEVELS[guide.level];
  top.append(categoryLabel, level);

  const code = document.createElement("span");
  code.className = "guide-code";
  code.textContent = guide.symptom || guide.code;
  const title = document.createElement("h3");
  title.textContent = guide.title;
  const summary = document.createElement("p");
  summary.textContent = guide.summary;

  const foot = document.createElement("div");
  foot.className = "guide-card-foot";
  const time = document.createElement("span");
  time.textContent = `⏱ ${guide.time}`;
  const cta = document.createElement("span");
  cta.textContent = "Ver solución →";
  foot.append(time, cta);

  card.append(top, code, title, summary, foot);
  card.addEventListener("click", () => {
    history.replaceState(null, "", `#guia/${guide.id}`);
    showGuide(guide);
    showStatus("");
  });
  return card;
}

function renderGuides() {
  const query = guideFilter.value.trim().toLowerCase();
  const visible = GUIDES.filter((guide) => guideMatches(guide, query));
  guideGrid.replaceChildren(...visible.map(renderGuideCard));
  guideEmpty.hidden = visible.length > 0;
}

function renderTabs() {
  const tabs = [["todas", { label: "Todas", icon: "" }], ...Object.entries(GUIDE_CATEGORIES)];
  categoryTabs.replaceChildren(...tabs.map(([key, category]) => {
    const total = key === "todas" ? GUIDES.length : GUIDES.filter((guide) => guide.category === key).length;
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "tab";
    tab.setAttribute("aria-pressed", String(key === activeCategory));
    tab.textContent = `${category.icon} ${category.label}`.trim();
    const count = document.createElement("span");
    count.className = "tab-count";
    count.textContent = total;
    tab.appendChild(count);
    tab.addEventListener("click", () => {
      activeCategory = key;
      renderTabs();
      renderGuides();
    });
    return tab;
  }));
}

function openGuideFromHash() {
  const match = location.hash.match(/^#guia\/(.+)$/);
  const guide = match && GUIDES.find((item) => item.id === decodeURIComponent(match[1]));
  if (guide) showGuide(guide);
}

guideFilter.addEventListener("input", renderGuides);
window.addEventListener("hashchange", openGuideFromHash);
renderTabs();
renderGuides();
openGuideFromHash();
