"use strict";

const i18n = window.OpticBenchI18n;
const savedLanguage = (() => {
  try { return window.localStorage.getItem("opticbench-language"); } catch (_) { return null; }
})();

const state = {
  language: savedLanguage === "en" ? "en" : "zh-CN",
  config: null,
  current: null,
  rows: [],
  chartRows: [],
  fullMatrix: false,
  chartSeriesKey: "fixed_focal_length_mm",
  chartSeriesParameter: "focal_length_mm",
  zemaxReady: false,
  zemaxConnectionPassed: false,
  zemaxRunning: false,
  zemaxJobId: null,
  zemaxPreflight: null,
  zemaxJob: null,
  matrixSummary: null,
  batchStatus: null,
  serverStatus: "connecting",
};
const palette = ["#0f6d70", "#e56b3f", "#d7a22a"];
const $ = (id) => document.getElementById(id);
const staticTextNodes = [];
const staticAttributes = [];

function msg(key, values = {}) {
  return i18n.message(state.language, key, values);
}

function localizedEyeLabel(eye) {
  return i18n.eyeLabel(state.language, eye);
}

function localizedBackendMessage(value) {
  return i18n.backendMessage(state.language, value);
}

function captureStaticTranslations() {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    const trimmed = node.nodeValue.trim();
    if (trimmed && i18n.staticEnglish[trimmed]) staticTextNodes.push({ node, original: node.nodeValue, trimmed });
    node = walker.nextNode();
  }
  document.querySelectorAll("[aria-label], [placeholder]").forEach((element) => {
    ["aria-label", "placeholder"].forEach((name) => {
      const value = element.getAttribute(name);
      if (value && i18n.staticEnglish[value]) staticAttributes.push({ element, name, value });
    });
  });
}

function applyStaticTranslations() {
  const english = state.language === "en";
  staticTextNodes.forEach(({ node, original, trimmed }) => {
    if (!english) {
      node.nodeValue = original;
      return;
    }
    const leading = original.match(/^\s*/)[0];
    const trailing = original.match(/\s*$/)[0];
    node.nodeValue = `${leading}${i18n.staticEnglish[trimmed]}${trailing}`;
  });
  staticAttributes.forEach(({ element, name, value }) => {
    element.setAttribute(name, english ? i18n.staticEnglish[value] : value);
  });
  document.documentElement.lang = english ? "en" : "zh-CN";
  document.title = english ? "Posterior-Pole Illumination Parameter Lab" : "后极照明参数实验台";
  $("meta-description").content = english
    ? "Fixed-focal posterior-pole illumination simulation for chick and human eyes"
    : "小鸡与人眼固定焦距后极照明仿真实验程序";
  $("report-pdf-link").href = english ? "/report-en.pdf" : "/report.pdf";
  $("lang-zh").setAttribute("aria-pressed", String(!english));
  $("lang-en").setAttribute("aria-pressed", String(english));
}

function renderServerStatus() {
  const label = state.serverStatus === "connected" ? msg("serverConnected")
    : state.serverStatus === "failed" ? msg("serverFailed")
      : (state.language === "en" ? "Connecting to local model" : "模型连接中");
  $("server-label").textContent = label;
}

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function option(value, label = value) {
  const element = document.createElement("option");
  element.value = value;
  element.textContent = label;
  return element;
}

function fillSelect(element, values, label) {
  element.replaceChildren(...values.map((value) => option(value, label ? label(value) : value)));
}

function fixed(value, digits = 3) {
  return Number(value).toFixed(digits);
}

function currentMode() {
  return $("mode-select").value;
}

function selectedEye() {
  return state.config.eyes.find((eye) => eye.id === $("eye-select").value);
}

function showToast(message, error = false) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.toggle("error", error);
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 3500);
}

function setRangeControl(id, specification, unit) {
  const input = $(`range-${id}`);
  input.min = specification.minimum;
  input.max = specification.maximum;
  input.step = specification.step;
  input.value = specification.default;
  $(`range-${id}-value`).textContent = `${fixed(specification.default, id === "demand" ? 0 : 2)} ${unit}`;
  $(`range-${id}-limits`).textContent = `${specification.minimum}–${specification.maximum} ${unit} · ${localizedBackendMessage(specification.provenance)}`;
}

function updateRangeOutput(id, unit, digits = 2) {
  $(`range-${id}-value`).textContent = `${fixed($(`range-${id}`).value, digits)} ${unit}`;
  if (id === "axial") $("axial-value").textContent = `${fixed($("range-axial").value, 2)} mm`;
}

function componentLabel(parameter) {
  const labels = state.language === "en" ? {
    corneal_curvature_radius_mm: "Corneal curvature radius",
    corneal_equivalent_power_D: "Corneal equivalent power",
    crystalline_lens_thickness_mm: "Crystalline-lens thickness",
    crystalline_lens_equivalent_power_D: "Crystalline-lens equivalent power",
    corneal_equivalent_focal_length_mm: "Corneal equivalent focal length",
    crystalline_lens_equivalent_focal_length_mm: "Crystalline-lens equivalent focal length",
  } : {
    corneal_curvature_radius_mm: "角膜曲率半径",
    corneal_equivalent_power_D: "角膜等效屈光力",
    crystalline_lens_thickness_mm: "晶状体厚度",
    crystalline_lens_equivalent_power_D: "晶状体等效屈光力",
    corneal_equivalent_focal_length_mm: "角膜等效焦距",
    crystalline_lens_equivalent_focal_length_mm: "晶状体等效焦距",
  };
  const value = parameter.value !== undefined ? parameter.value : `${parameter.minimum}–${parameter.maximum}`;
  const unit = parameter.name.endsWith("_D") ? "D" : "mm";
  return `${labels[parameter.name] || parameter.name}: ${value} ${unit} (${msg("referenceOnly")})`;
}

function renderRangeProvenance(eye) {
  const parameters = eye.range_parameters;
  $("range-provenance-text").textContent = [
    parameters.effective_focal_length_mm.provenance,
    parameters.axial_length_mm.provenance,
    parameters.pupil_diameter_mm.provenance,
  ].map(localizedBackendMessage).join(state.language === "en" ? "; " : "；");
  const list = $("component-reference-list");
  list.replaceChildren(...parameters.reference_component_parameters.map((parameter) => {
    const item = document.createElement("li");
    item.textContent = componentLabel(parameter);
    return item;
  }));
}

function configureRangeControls(eye) {
  const ranges = eye.range_parameters;
  setRangeControl("focal", ranges.effective_focal_length_mm, "mm");
  setRangeControl("axial", ranges.axial_length_mm, "mm");
  setRangeControl("pupil", ranges.pupil_diameter_mm, "mm");
  setRangeControl("demand", state.config.range_explorer.source_demand_D, "D");
  const lensValues = state.config.range_explorer.external_lens_powers_D.values;
  fillSelect($("external-lens-select"), lensValues, (value) => value === 0 ? msg("noExternalLens") : `${value}`);
  renderRangeProvenance(eye);
}

function refreshEyeControls() {
  const eye = selectedEye();
  fillSelect($("focal-select"), eye.fixed_focal_lengths_mm, (value) => Number(value).toFixed(value % 1 ? 2 : 1));
  fillSelect($("pupil-select"), eye.pupil_diameters_mm, (value) => Number(value).toFixed(1));
  configureRangeControls(eye);
  $("axial-value").textContent = `${eye.reported_axial_length_mm.toFixed(2)} mm`;
  $("posterior-value").textContent = `${eye.posterior_pole_diameter_mm.toFixed(2)} mm`;
  $("index-value").textContent = eye.image_medium_refractive_index.toFixed(3);
  updateModeCopy();
  void calculateCurrent();
}

function updateModeCopy() {
  const rangeMode = currentMode() === "range";
  $("baseline-fields").hidden = rangeMode;
  $("range-fields").hidden = !rangeMode;
  $("range-provenance").hidden = !rangeMode;
  $("sensitivity-select").hidden = !rangeMode;
  $("sensitivity-label").hidden = !rangeMode;
  $("analysis-title").textContent = rangeMode ? msg("sensitivityTitle") : msg("baselineTitle");
  $("parameter-summary-title").innerHTML = rangeMode
    ? `<span aria-hidden="true">◆</span> ${msg("currentPosteriorAdjustable")}`
    : `<span aria-hidden="true">◆</span> ${msg("knownPosteriorReadOnly")}`;
  $("method-focal").textContent = rangeMode
    ? msg("rangeFocalMethod")
    : msg("baselineFocalMethod");
  $("method-axial").textContent = rangeMode
    ? msg("rangeAxialMethod")
    : msg("baselineAxialMethod");
  $("full-sweep").textContent = rangeMode ? msg("rangeGridButton") : msg("fullSweepButton");
  state.fullMatrix = false;
  if (!rangeMode) $("axial-value").textContent = `${selectedEye().reported_axial_length_mm.toFixed(2)} mm`;
}

function requestFromControls() {
  if (currentMode() === "range") {
    return {
      mode: "range",
      eye_id: $("eye-select").value,
      focal_length_mm: Number($("range-focal").value),
      axial_length_mm: Number($("range-axial").value),
      pupil_diameter_mm: Number($("range-pupil").value),
      source_demand_D: Number($("range-demand").value),
      external_lens_power_D: Number($("external-lens-select").value),
    };
  }
  return {
    mode: "baseline",
    eye_id: $("eye-select").value,
    focal_length_mm: Number($("focal-select").value),
    pupil_diameter_mm: Number($("pupil-select").value),
    source_demand_D: Number($("demand-select").value),
  };
}

function renderResult(result) {
  state.current = result;
  $("conservative-value").textContent = fixed(result.conservative_source_diameter_mm);
  $("geometric-value").textContent = fixed(result.geometric_min_source_diameter_mm);
  $("distance-value").textContent = fixed(result.source_distance_mm, 2);
  $("blur-value").textContent = fixed(result.pupil_blur_diameter_mm);
  $("edge-angle-value").textContent = `${fixed(result.maximum_source_pupil_ray_angle_deg, 1)}°`;
  $("f-number-value").textContent = `F/${fixed(result.working_f_number, 2)}`;
  $("readiness-value").textContent = msg("readiness");
  $("diagram-demand").textContent = `${fixed(result.source_demand_D, result.mode === "range" ? 1 : 0)} D`;
  $("source-label").textContent = `${fixed(result.conservative_source_diameter_mm)} mm`;
  $("lens-label").textContent = result.external_lens_power_D
    ? `${fixed(result.effective_focal_length_mm, 2)} mm · ${msg("externalLens", { power: result.external_lens_power_D })}`
    : `${fixed(result.effective_focal_length_mm, 2)} mm`;
  $("target-label").textContent = `${fixed(result.posterior_pole_diameter_mm, 2)} mm`;
  $("axial-value").textContent = `${fixed(result.axial_length_mm, 2)} mm`;
  const modeText = result.mode === "range" ? msg("rangeValue") : msg("baselineValue");
  const interpretation = result.pupil_blur_alone_covers_target
    ? msg("blurCovers")
    : msg("fullOverlap", { diameter: fixed(result.conservative_source_diameter_mm) });
  const scopeWarning = result.paraxial_screening_pass
    ? msg("scopePass")
    : msg("scopeFail", { angle: fixed(result.maximum_source_pupil_ray_angle_deg, 1) });
  $("interpretation").querySelector("p").textContent = `${modeText}${state.language === "en" ? ": " : "："}${interpretation} ${scopeWarning}`;
  $("download-json").disabled = false;
  renderDiagram(result);
}

function renderDiagram(result) {
  const center = 150;
  const sourceHalf = Math.max(9, Math.min(52, result.conservative_source_diameter_mm * 4.1));
  const pupilHalf = Math.max(10, result.pupil_diameter_mm * 7.2);
  const targetHalf = Math.max(18, result.posterior_pole_diameter_mm * 7.2);
  const source = $("source-shape");
  source.setAttribute("y", center - sourceHalf);
  source.setAttribute("height", sourceHalf * 2);
  $("target-line").setAttribute("y1", center - targetHalf);
  $("target-line").setAttribute("y2", center + targetHalf);
  const paths = [
    `M90 ${center-sourceHalf} L390 ${center-pupilHalf} L665 ${center-targetHalf}`,
    `M90 ${center-sourceHalf} L390 ${center+pupilHalf} L665 ${center+targetHalf}`,
    `M90 ${center+sourceHalf} L390 ${center-pupilHalf} L665 ${center-targetHalf}`,
    `M90 ${center+sourceHalf} L390 ${center+pupilHalf} L665 ${center+targetHalf}`,
  ];
  ["ray-one", "ray-two", "ray-three", "ray-four"].forEach((id, index) => $(id).setAttribute("d", paths[index]));
}

async function calculateCurrent(event) {
  if (event) event.preventDefault();
  try {
    const result = await api("/api/calculate", { method: "POST", body: JSON.stringify(requestFromControls()) });
    renderResult(result);
    await loadChartRows();
  } catch (error) {
    $("interpretation").querySelector("p").textContent = msg("calculationImpossible", { error: localizedBackendMessage(error.message) });
    showToast(msg("calculationFailed", { error: localizedBackendMessage(error.message) }), true);
  }
}

async function loadChartRows() {
  if (currentMode() === "range") {
    const request = { ...requestFromControls(), vary_by: $("sensitivity-select").value };
    const payload = await api("/api/range-sensitivity", { method: "POST", body: JSON.stringify(request) });
    state.chartRows = payload.rows;
    state.rows = payload.rows;
    state.chartSeriesKey = "series_value";
    state.chartSeriesParameter = payload.vary_by;
    state.fullMatrix = false;
    state.matrixSummary = { type: "rangeSensitivity", rows: payload.row_count, skipped: payload.skipped_count };
  } else {
    const request = { eye_id: $("eye-select").value, pupil_diameter_mm: Number($("pupil-select").value) };
    const payload = await api("/api/sweep", { method: "POST", body: JSON.stringify(request) });
    state.chartRows = payload.rows;
    state.rows = payload.rows;
    state.chartSeriesKey = "fixed_focal_length_mm";
    state.chartSeriesParameter = "focal_length_mm";
    state.fullMatrix = false;
    state.matrixSummary = { type: "baseline", rows: payload.row_count, pupil: fixed(request.pupil_diameter_mm, 1) };
  }
  renderMatrixDescription();
  renderChart();
  state.batchStatus = state.rows.length ? { type: "rows", rows: state.rows.length } : { type: "waiting" };
  renderTable(state.rows);
  $("download-csv").disabled = false;
}

function renderMatrixDescription() {
  if (!state.matrixSummary) return;
  const summary = state.matrixSummary;
  if (summary.type === "rangeSensitivity") {
    $("matrix-description").textContent = msg("rangeSensitivitySummary", summary);
  } else if (summary.type === "rangeGrid") {
    $("matrix-description").textContent = msg("rangeGridSummary", summary);
  } else if (summary.type === "baselineFull") {
    $("matrix-description").textContent = msg("baselineFullSummary", summary);
  } else {
    $("matrix-description").textContent = msg("baselineSummary", summary);
  }
}

function svgElement(name, attributes = {}, text = "") {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
  if (text) node.textContent = text;
  return node;
}

function seriesUnit(parameter) {
  return parameter === "pupil_diameter_mm" || parameter === "focal_length_mm" || parameter === "axial_length_mm" ? "mm" : "";
}

function seriesName(parameter) {
  return {
    focal_length_mm: msg("focalName"),
    axial_length_mm: msg("axialName"),
    pupil_diameter_mm: msg("pupilName"),
  }[parameter] || parameter;
}

function renderChart() {
  const svg = $("sweep-chart");
  svg.replaceChildren();
  if (!state.chartRows.length) return;
  const metric = $("metric-select").value;
  const metricLabel = $("metric-select").selectedOptions[0].textContent;
  const width = 880, height = 410, left = 72, right = 24, top = 50, bottom = 58;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const xs = [...new Set(state.chartRows.map((row) => row.source_demand_D))].sort((a,b) => a-b);
  const series = [...new Set(state.chartRows.map((row) => row[state.chartSeriesKey]))].sort((a,b) => a-b);
  const values = state.chartRows.map((row) => row[metric]);
  const yMax = Math.max(...values) * 1.12 || 1;
  const xSpan = xs.at(-1) - xs[0] || 1;
  const xPos = (x) => left + (x - xs[0]) / xSpan * plotWidth;
  const yPos = (y) => top + plotHeight - y / yMax * plotHeight;
  const seriesLabel = `${seriesName(state.chartSeriesParameter)} / ${seriesUnit(state.chartSeriesParameter)}`;

  svg.append(svgElement("text", { x: left, y: 22, class: "chart-title" }, `${localizedEyeLabel(selectedEye())} · ${metricLabel} · ${seriesLabel}`));
  for (let i = 0; i <= 5; i += 1) {
    const yValue = yMax * i / 5;
    const y = yPos(yValue);
    svg.append(svgElement("line", { x1: left, x2: width-right, y1: y, y2: y, class: "chart-grid" }));
    svg.append(svgElement("text", { x: left-10, y: y+4, "text-anchor": "end", class: "chart-text" }, fixed(yValue, 1)));
  }
  xs.forEach((x) => {
    const pos = xPos(x);
    svg.append(svgElement("line", { x1: pos, x2: pos, y1: top, y2: height-bottom, class: "chart-grid" }));
    svg.append(svgElement("text", { x: pos, y: height-bottom+24, "text-anchor": "middle", class: "chart-text" }, fixed(x, 0)));
  });
  svg.append(svgElement("line", { x1: left, x2: left, y1: top, y2: height-bottom, class: "chart-axis" }));
  svg.append(svgElement("line", { x1: left, x2: width-right, y1: height-bottom, y2: height-bottom, class: "chart-axis" }));
  svg.append(svgElement("text", { x: left+plotWidth/2, y: height-10, "text-anchor": "middle", class: "chart-text" }, msg("demandAxis")));
  svg.append(svgElement("text", { x: 16, y: top+plotHeight/2, transform: `rotate(-90 16 ${top+plotHeight/2})`, "text-anchor": "middle", class: "chart-text" }, msg("diameterAxis")));

  series.forEach((seriesValue, index) => {
    const rows = state.chartRows.filter((row) => row[state.chartSeriesKey] === seriesValue).sort((a,b) => a.source_demand_D-b.source_demand_D);
    const points = rows.map((row) => `${xPos(row.source_demand_D)},${yPos(row[metric])}`).join(" ");
    svg.append(svgElement("polyline", { points, class: "chart-line", stroke: palette[index % palette.length] }));
    rows.forEach((row) => {
      const dot = svgElement("circle", { cx: xPos(row.source_demand_D), cy: yPos(row[metric]), r: 4, fill: palette[index % palette.length], class: "chart-dot" });
      dot.append(svgElement("title", {}, `${seriesName(state.chartSeriesParameter)}=${seriesValue} ${seriesUnit(state.chartSeriesParameter)}, ${row.source_demand_D} D: ${fixed(row[metric])} mm`));
      svg.append(dot);
    });
    const legendX = width - right - 205 + index * 70;
    svg.append(svgElement("line", { x1: legendX, x2: legendX+16, y1: 23, y2: 23, stroke: palette[index % palette.length], "stroke-width": 3 }));
    svg.append(svgElement("text", { x: legendX+21, y: 27, class: "chart-text" }, `${seriesValue}`));
  });
}

function renderTable(rows) {
  const body = $("results-body");
  body.replaceChildren();
  const fragment = document.createDocumentFragment();
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const values = [
      state.language === "en" ? localizedEyeLabel(row.eye_id) : row.eye_label,
      fixed(row.effective_focal_length_mm, 2),
      fixed(row.axial_length_mm, 2),
      fixed(row.pupil_diameter_mm, 1),
      fixed(row.external_lens_power_D, 0),
      fixed(row.source_demand_D, 0),
      fixed(row.source_distance_mm, 2),
      fixed(row.geometric_min_source_diameter_mm),
      fixed(row.conservative_source_diameter_mm),
      fixed(row.retinal_defocus_D, 2),
    ];
    values.forEach((value) => { const td = document.createElement("td"); td.textContent = value; tr.append(td); });
    fragment.append(tr);
  });
  body.append(fragment);
  $("download-zemax-batch").disabled = rows.length === 0;
  if (!state.batchStatus || state.batchStatus.type === "rows" || state.batchStatus.type === "waiting") {
    state.batchStatus = rows.length ? { type: "rows", rows: rows.length } : { type: "waiting" };
  }
  renderBatchStatus();
  updateZemaxButtons();
}

function renderBatchStatus() {
  const status = state.batchStatus || { type: "waiting" };
  const values = status.values || status;
  const key = {
    rows: "batchRows",
    waiting: "batchWaiting",
    validating: "validatingRows",
    complete: "batchNotRun",
    failed: "generationFailed",
  }[status.type] || "batchWaiting";
  $("zemax-batch-status").textContent = msg(key, values);
}

function downloadUrl(path) {
  const link = document.createElement("a");
  link.href = path;
  link.hidden = true;
  document.body.append(link);
  link.click();
  setTimeout(() => link.remove(), 1000);
}

function zemaxCaseInput(row) {
  return {
    mode: row.mode,
    eye_id: row.eye_id,
    focal_length_mm: row.effective_focal_length_mm,
    axial_length_mm: row.axial_length_mm,
    pupil_diameter_mm: row.pupil_diameter_mm,
    source_demand_D: row.source_demand_D,
    external_lens_power_D: row.external_lens_power_D,
  };
}

async function downloadZemaxBatch() {
  if (!state.rows.length) return;
  const button = $("download-zemax-batch");
  try {
    button.disabled = true;
    button.textContent = msg("packaging");
    state.batchStatus = { type: "validating" };
    renderBatchStatus();
    const response = await fetch("/api/zemax-batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cases: state.rows.map(zemaxCaseInput) }),
    });
    if (!response.ok) {
      const payload = await response.json();
      throw new Error(payload.error || `HTTP ${response.status}`);
    }
    const blob = await response.blob();
    const batchId = response.headers.get("X-Zemax-Batch-Id") || "eye-zemax-batch";
    const digest = response.headers.get("X-Content-SHA256") || "unknown";
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${batchId}.zip`;
    link.hidden = true;
    document.body.append(link);
    link.click();
    setTimeout(() => { URL.revokeObjectURL(link.href); link.remove(); }, 1000);
    state.batchStatus = { type: "complete", batch: batchId, digest: digest.slice(0, 16) };
    renderBatchStatus();
    showToast(msg("batchGenerated", { rows: state.rows.length }));
  } catch (error) {
    state.batchStatus = { type: "failed", error: localizedBackendMessage(error.message) };
    renderBatchStatus();
    showToast(msg("batchGenerationFailed", { error: localizedBackendMessage(error.message) }), true);
  } finally {
    button.disabled = false;
    button.textContent = msg("generateBatch");
  }
}

function checkLabel(element, ok, okText, badText) {
  element.textContent = ok ? okText : badText;
  element.classList.toggle("pass-text", ok);
  element.classList.toggle("fail-text", !ok);
}

function updateZemaxButtons() {
  const confirmed = $("zemax-confirm").checked;
  $("zemax-test").disabled = !state.zemaxReady || !confirmed || !state.current || state.zemaxRunning;
  $("zemax-run-table").disabled = !state.zemaxReady || !confirmed || !state.zemaxConnectionPassed
    || state.rows.length === 0 || state.zemaxRunning;
  $("zemax-step-test").classList.toggle("locked", !state.zemaxReady);
  $("zemax-step-result").classList.toggle("locked", !state.zemaxConnectionPassed && !state.zemaxRunning);
}

function renderPreflight(result) {
  checkLabel(
    $("zemax-runtime-check"),
    result.platform_supported && result.python_64bit && result.compiler_found && result.powershell_found,
    msg("runtimeReady", { version: result.python_version }),
    msg("requirementsMissing"),
  );
  checkLabel(
    $("zemax-api-check"),
    result.installation_exists && Object.values(result.api_dlls).every(Boolean),
    msg("dllsFound", { count: 3 }),
    msg("dllsFound", { count: Object.values(result.api_dlls).filter(Boolean).length }),
  );
  $("zemax-license-check").textContent = msg("notTested");
  $("zemax-license-check").className = "";
  $("zemax-preflight-message").textContent = localizedBackendMessage(result.next_action);
  $("zemax-step-detect").classList.toggle("complete", result.ready);
  $("zemax-verification-label").textContent = msg("waitingConnection");
  $("zemax-verification-detail").textContent = msg("preflightNoLicense");
  $("zemax-verification-state").className = "verification-state pending";
}

async function detectZemax() {
  const button = $("zemax-detect");
  try {
    button.disabled = true;
    button.textContent = msg("detecting");
    const path = $("zemax-install-path").value.trim();
    const query = path ? `?${new URLSearchParams({ opticstudio_dir: path })}` : "";
    const result = await api(`/api/zemax/preflight${query}`);
    state.zemaxPreflight = result;
    state.zemaxReady = result.ready;
    state.zemaxConnectionPassed = false;
    if (!path && result.selected_installation) $("zemax-install-path").value = result.selected_installation;
    renderPreflight(result);
    updateZemaxButtons();
    showToast(result.ready ? msg("preflightPassed") : localizedBackendMessage(result.next_action), !result.ready);
  } catch (error) {
    state.zemaxReady = false;
    $("zemax-preflight-message").textContent = msg("detectionFailed", { error: localizedBackendMessage(error.message) });
    updateZemaxButtons();
    showToast(msg("zemaxDetectionFailed", { error: localizedBackendMessage(error.message) }), true);
  } finally {
    button.disabled = false;
    button.textContent = msg("redetect");
  }
}

function renderZemaxJob(job, notify = true) {
  state.zemaxJob = job;
  state.zemaxRunning = ["queued", "running"].includes(job.status);
  const panel = $("zemax-verification-state");
  const verification = job.verification;
  if (state.zemaxRunning) {
    panel.className = "verification-state running";
    $("zemax-verification-label").textContent = job.stage === "OPTICSTUDIO" ? msg("zemaxRunning") : msg("preparingBatch");
    $("zemax-verification-detail").textContent = localizedBackendMessage(job.message);
    $("zemax-job-message").textContent = msg("dontClose", { batch: job.batch_id, cases: job.case_count });
  } else if (job.status === "pass") {
    panel.className = "verification-state pass";
    $("zemax-verification-label").textContent = msg("paraxialPass");
    $("zemax-verification-detail").textContent = localizedBackendMessage(job.message);
    $("zemax-license-check").textContent = verification.api_license_valid ? msg("licenseMeasured") : msg("notConfirmed");
    $("zemax-license-check").className = verification.api_license_valid ? "pass-text" : "fail-text";
    $("zemax-step-result").classList.add("complete");
    if (job.mode === "connection_test") state.zemaxConnectionPassed = true;
    $("zemax-job-message").textContent = msg("jobPassed", { batch: job.batch_id, cases: job.case_count });
    if (notify) showToast(msg("passToast", { cases: job.case_count }));
  } else {
    panel.className = "verification-state fail";
    $("zemax-verification-label").textContent = msg("fail");
    $("zemax-verification-detail").textContent = localizedBackendMessage(job.message);
    $("zemax-license-check").textContent = verification?.api_license_valid ? msg("licenseFailed") : msg("notConfirmed");
    $("zemax-license-check").className = "fail-text";
    $("zemax-job-message").textContent = msg("jobFailed", { batch: job.batch_id });
    if (notify) showToast(msg("failToast"), true);
  }
  if (verification) {
    $("zemax-passed-count").textContent = `${verification.passed_case_count} / ${verification.expected_case_count}`;
    $("zemax-max-error").textContent = verification.maximum_boundary_error_um == null
      ? "—" : `${Number(verification.maximum_boundary_error_um).toExponential(3)} µm`;
    $("zemax-version").textContent = verification.opticstudio_versions.join(", ") || "—";
  }
  const evidence = $("zemax-evidence");
  if (job.result_available) {
    evidence.href = `/api/zemax/jobs/${job.job_id}/evidence.zip`;
    evidence.setAttribute("aria-disabled", "false");
    evidence.classList.remove("disabled-link");
  }
  updateZemaxButtons();
}

async function pollZemaxJob(jobId) {
  try {
    const job = await api(`/api/zemax/jobs/${jobId}`);
    renderZemaxJob(job);
    if (["queued", "running"].includes(job.status)) {
      setTimeout(() => pollZemaxJob(jobId), 1000);
    }
  } catch (error) {
    state.zemaxRunning = false;
    $("zemax-verification-state").className = "verification-state fail";
    $("zemax-verification-label").textContent = msg("statusReadFailed");
    $("zemax-verification-detail").textContent = localizedBackendMessage(error.message);
    updateZemaxButtons();
  }
}

async function startZemaxJob(mode) {
  const sourceRows = mode === "connection_test" ? [state.current] : state.rows;
  if (!sourceRows.length || !$("zemax-confirm").checked) return;
  try {
    state.zemaxRunning = true;
    updateZemaxButtons();
    $("zemax-evidence").classList.add("disabled-link");
    $("zemax-evidence").setAttribute("aria-disabled", "true");
    const job = await api("/api/zemax/jobs", {
      method: "POST",
      body: JSON.stringify({
        confirm: true,
        mode,
        opticstudio_dir: $("zemax-install-path").value.trim(),
        cases: sourceRows.map(zemaxCaseInput),
      }),
    });
    state.zemaxJobId = job.job_id;
    renderZemaxJob(job);
    setTimeout(() => pollZemaxJob(job.job_id), 500);
  } catch (error) {
    state.zemaxRunning = false;
    $("zemax-verification-state").className = "verification-state fail";
    $("zemax-verification-label").textContent = msg("cannotStart");
    $("zemax-verification-detail").textContent = localizedBackendMessage(error.message);
    updateZemaxButtons();
    showToast(msg("cannotStartZemax", { error: localizedBackendMessage(error.message) }), true);
  }
}

async function fullSweep() {
  try {
    $("full-sweep").disabled = true;
    $("full-sweep").textContent = msg("generating");
    if (currentMode() === "range") {
      const payload = await api("/api/range-grid", { method: "POST", body: JSON.stringify(requestFromControls()) });
      state.rows = payload.rows;
      state.fullMatrix = true;
      state.batchStatus = { type: "rows", rows: state.rows.length };
      renderTable(state.rows);
      state.matrixSummary = { type: "rangeGrid", requested: payload.requested_count, rows: payload.row_count, skipped: payload.skipped_count };
      renderMatrixDescription();
      showToast(msg("rangeGridGenerated", { rows: payload.row_count }));
    } else {
      const payload = await api("/api/sweep", { method: "POST", body: "{}" });
      state.rows = payload.rows;
      state.fullMatrix = true;
      state.batchStatus = { type: "rows", rows: state.rows.length };
      renderTable(state.rows);
      state.matrixSummary = { type: "baselineFull", rows: payload.row_count };
      renderMatrixDescription();
      showToast(msg("baselineGenerated", { rows: payload.row_count }));
    }
  } catch (error) {
    showToast(msg("sweepFailed", { error: localizedBackendMessage(error.message) }), true);
  } finally {
    $("full-sweep").disabled = false;
    $("full-sweep").textContent = currentMode() === "range" ? msg("rangeGridButton") : msg("fullSweepButton");
  }
}

async function modeChanged() {
  updateModeCopy();
  await calculateCurrent();
}

function setLanguage(language, persist = true) {
  state.language = language === "en" ? "en" : "zh-CN";
  if (persist) {
    try { window.localStorage.setItem("opticbench-language", state.language); } catch (_) { /* local preference only */ }
  }
  applyStaticTranslations();
  renderServerStatus();
  if (!state.config) return;

  [...$("eye-select").options].forEach((item, index) => {
    item.textContent = localizedEyeLabel(state.config.eyes[index]);
  });
  const lensValues = state.config.range_explorer.external_lens_powers_D.values;
  [...$("external-lens-select").options].forEach((item, index) => {
    const value = lensValues[index];
    item.textContent = value === 0 ? msg("noExternalLens") : `${value}`;
  });
  renderRangeProvenance(selectedEye());
  updateModeCopy();
  if (state.current) renderResult(state.current);
  renderMatrixDescription();
  if (state.chartRows.length) renderChart();
  if (state.rows.length) renderTable(state.rows);
  if (state.zemaxPreflight) renderPreflight(state.zemaxPreflight);
  if (state.zemaxJob) renderZemaxJob(state.zemaxJob, false);
  renderBatchStatus();
  updateZemaxButtons();
}

async function initialize() {
  try {
    state.config = await api("/api/config");
    $("experiment-id").textContent = state.config.experiment_id;
    $("case-count").textContent = state.config.case_count;
    $("wavelength-value").textContent = `${fixed(state.config.wavelength_nm, 0)} nm`;
    fillSelect($("eye-select"), state.config.eyes, (eye) => localizedEyeLabel(eye));
    [...$("eye-select").options].forEach((item, index) => { item.value = state.config.eyes[index].id; });
    fillSelect($("demand-select"), state.config.source_demands_D, (value) => fixed(value, 0));
    state.serverStatus = "connected";
    renderServerStatus();
    $("server-label").parentElement.classList.add("ready");
    refreshEyeControls();
  } catch (error) {
    state.serverStatus = "failed";
    renderServerStatus();
    showToast(msg("initializationFailed", { error: localizedBackendMessage(error.message) }), true);
  }
}

$("experiment-form").addEventListener("submit", calculateCurrent);
$("mode-select").addEventListener("change", modeChanged);
$("eye-select").addEventListener("change", refreshEyeControls);
$("focal-select").addEventListener("change", calculateCurrent);
$("pupil-select").addEventListener("change", calculateCurrent);
$("demand-select").addEventListener("change", calculateCurrent);
$("external-lens-select").addEventListener("change", calculateCurrent);
$("metric-select").addEventListener("change", renderChart);
$("sensitivity-select").addEventListener("change", loadChartRows);
$("full-sweep").addEventListener("click", fullSweep);
$("download-zemax-batch").addEventListener("click", downloadZemaxBatch);
$("zemax-detect").addEventListener("click", detectZemax);
$("zemax-confirm").addEventListener("change", updateZemaxButtons);
$("zemax-install-path").addEventListener("input", () => {
  state.zemaxReady = false;
  state.zemaxConnectionPassed = false;
  $("zemax-preflight-message").textContent = msg("pathChanged");
  updateZemaxButtons();
});
$("lang-zh").addEventListener("click", () => setLanguage("zh-CN"));
$("lang-en").addEventListener("click", () => setLanguage("en"));
$("zemax-test").addEventListener("click", () => startZemaxJob("connection_test"));
$("zemax-run-table").addEventListener("click", () => startZemaxJob("table"));

[["focal", "mm", 2], ["axial", "mm", 2], ["pupil", "mm", 2], ["demand", "D", 0]].forEach(([id, unit, digits]) => {
  $(`range-${id}`).addEventListener("input", () => updateRangeOutput(id, unit, digits));
  $(`range-${id}`).addEventListener("change", calculateCurrent);
});

$("download-json").addEventListener("click", () => {
  if (!state.current) return;
  downloadUrl(`/api/case.json?${new URLSearchParams(requestFromControls())}`);
});
$("download-csv").addEventListener("click", () => {
  if (currentMode() === "range") {
    const params = new URLSearchParams({ ...requestFromControls(), vary_by: $("sensitivity-select").value });
    downloadUrl(`${state.fullMatrix ? "/api/range-grid.csv" : "/api/range-sensitivity.csv"}?${params}`);
    return;
  }
  const query = state.fullMatrix ? "" : `?${new URLSearchParams({eye_id: $("eye-select").value, pupil_diameter_mm: $("pupil-select").value})}`;
  downloadUrl(`/api/sweep.csv${query}`);
});

captureStaticTranslations();
setLanguage(state.language, false);
void initialize();
