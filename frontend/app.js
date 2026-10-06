const API_URL = "http://127.0.0.1:8000";

const form = document.querySelector("#error-form");
const codeInput = document.querySelector("#error-code");
const fileInput = document.querySelector("#image-file");
const dropZone = document.querySelector("#drop-zone");
const fileName = document.querySelector("#file-name");
const formStatus = document.querySelector("#form-status");
const result = document.querySelector("#result");
const resultTitle = document.querySelector("#result-title");
const resultSummary = document.querySelector("#result-summary");
const probableCauses = document.querySelector("#probable-causes");
const detectedErrors = document.querySelector("#detected-errors");
const resultSteps = document.querySelector("#result-steps");
const effectiveness = document.querySelector("#effectiveness");
const feedbackYes = document.querySelector("#feedback-yes");
const feedbackNo = document.querySelector("#feedback-no");
const feedbackStatus = document.querySelector("#feedback-status");
let currentSolution = null;

function showStatus(message) {
  formStatus.textContent = message;
}

const STEP_TYPES = {
  configuracion: { label: "Configuración", icon: "⚙" },
  terminal: { label: "Terminal", icon: "⌘" },
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

function renderSteps(steps) {
  return steps.map((step, index) => {
    const item = document.createElement("li");
    const stepTag = step.tags?.[0] || step.tipo || "configuracion";
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
    header.appendChild(tag);

    const title = document.createElement("h3");
    title.textContent = step.title;
    header.appendChild(title);
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
          copy.textContent = "Copiado";
        } catch {
          copy.textContent = "Selecciona el comando";
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

function showResult(title, summary, causes, errors, steps, solution) {
  result.hidden = false;
  currentSolution = solution;
  resultTitle.textContent = title;
  resultSummary.textContent = summary;
  probableCauses.replaceChildren();
  if (causes.length) {
    const heading = document.createElement("strong");
    heading.textContent = "Causas probables";
    probableCauses.appendChild(heading);
    const causeList = document.createElement("ul");
    causes.forEach((cause) => {
      const item = document.createElement("li");
      item.textContent = cause;
      causeList.appendChild(item);
    });
    probableCauses.appendChild(causeList);
  }
  detectedErrors.replaceChildren(...errors.map((error) => {
    const tag = document.createElement("span");
    tag.className = "error-tag";
    tag.textContent = error;
    return tag;
  }));
  resultSteps.replaceChildren(...renderSteps(steps));
  updateEffectiveness(solution.effectiveness_percentage, solution.total_votes);
  feedbackYes.disabled = false;
  feedbackNo.disabled = false;
  feedbackYes.classList.remove("is-selected");
  feedbackNo.classList.remove("is-selected");
  feedbackStatus.textContent = "";
  result.scrollIntoView({ behavior: "smooth", block: "start" });
}

function updateEffectiveness(percentage, totalVotes) {
  effectiveness.textContent = percentage === null
    ? "Todavía no hay votos."
    : `${percentage}% de efectividad · ${totalVotes} voto${totalVotes === 1 ? "" : "s"}`;
}

function setSelectedFile(file) {
  if (!file) return;
  fileInput.files = new DataTransfer().files;
  fileName.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const code = codeInput.value.trim();
  const file = fileInput.files[0];
  const button = form.querySelector("button[type=submit]");

  if (!code && !file) {
    showStatus("Escribe un código o selecciona una imagen para continuar.");
    return;
  }

  button.disabled = true;
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
      detectedCode = ocrResult.detected_errors[0] || "Texto de error detectado";
    }

    const analysisResponse = await fetch(`${API_URL}/api/v1/solutions/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ error_code: detectedCode, error_text: ocrResult?.extracted_text || "" }),
    });
    if (!analysisResponse.ok) throw new Error(await getErrorMessage(analysisResponse, "No se pudo analizar el error."));
    const analysis = await analysisResponse.json();
    showResult(
      `Solución para ${analysis.error_code}`,
      analysis.simple_explanation,
      analysis.causes || analysis.probable_causes || [],
      ocrResult?.detected_errors || [analysis.error_code],
      analysis.steps,
      analysis,
    );
    showStatus("Solución lista. Sigue los pasos en orden y revisa las advertencias.");
  } catch (error) {
    showStatus(error.message || "No se pudo conectar con el servidor.");
  } finally {
    button.disabled = false;
  }
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
    feedbackStatus.textContent = error.message || "No se pudo guardar tu respuesta.";
  } finally {
    feedbackYes.disabled = false;
    feedbackNo.disabled = false;
  }
}

feedbackYes.addEventListener("click", () => sendFeedback(true, feedbackYes));
feedbackNo.addEventListener("click", () => sendFeedback(false, feedbackNo));