"use strict";

const state = { config: null, current: null, rows: [], chartRows: [], fullMatrix: false };
const palette = ["#0f6d70", "#e56b3f", "#d7a22a"];
const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
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

function selectedEye() {
  return state.config.eyes.find((eye) => eye.id === $("eye-select").value);
}

function fillSelect(element, values, label) {
  element.replaceChildren(...values.map((value) => option(value, label ? label(value) : value)));
}

function refreshEyeControls() {
  const eye = selectedEye();
  fillSelect($("focal-select"), eye.fixed_focal_lengths_mm, (value) => Number(value).toFixed(value % 1 ? 2 : 1));
  fillSelect($("pupil-select"), eye.pupil_diameters_mm, (value) => Number(value).toFixed(1));
  $("axial-value").textContent = `${eye.reported_axial_length_mm.toFixed(2)} mm`;
  $("posterior-value").textContent = `${eye.posterior_pole_diameter_mm.toFixed(2)} mm`;
  $("index-value").textContent = eye.image_medium_refractive_index.toFixed(3);
  void calculateCurrent();
}

function requestFromControls() {
  return {
    eye_id: $("eye-select").value,
    focal_length_mm: Number($("focal-select").value),
    pupil_diameter_mm: Number($("pupil-select").value),
    source_demand_D: Number($("demand-select").value),
  };
}

function fixed(value, digits = 3) {
  return Number(value).toFixed(digits);
}

function showToast(message, error = false) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.toggle("error", error);
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 3000);
}

function renderResult(result) {
  state.current = result;
  $("conservative-value").textContent = fixed(result.conservative_source_diameter_mm);
  $("geometric-value").textContent = fixed(result.geometric_min_source_diameter_mm);
  $("distance-value").textContent = fixed(result.source_distance_mm, 2);
  $("blur-value").textContent = fixed(result.pupil_blur_diameter_mm);
  $("diagram-demand").textContent = `${fixed(result.source_demand_D, 0)} D`;
  $("source-label").textContent = `${fixed(result.conservative_source_diameter_mm)} mm`;
  $("lens-label").textContent = `${fixed(result.fixed_focal_length_mm, 2)} mm`;
  $("target-label").textContent = `${fixed(result.posterior_pole_diameter_mm, 2)} mm`;
  const geometricZero = result.pupil_blur_alone_covers_target;
  $("interpretation").querySelector("p").textContent = geometricZero
    ? "当前瞳孔离焦 footprint 已覆盖目标边缘，因此几何最小值为 0；实际设计仍应采用推荐全重叠尺寸，不能使用零面积光源。"
    : `当前 footprint 尚不能独立覆盖后极目标；推荐使用 ${fixed(result.conservative_source_diameter_mm)} mm 光源，使目标完整位于全重叠平台内。`;
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
    showToast(`计算失败：${error.message}`, true);
  }
}

async function loadChartRows() {
  const request = { eye_id: $("eye-select").value, pupil_diameter_mm: Number($("pupil-select").value) };
  const payload = await api("/api/sweep", { method: "POST", body: JSON.stringify(request) });
  state.chartRows = payload.rows;
  state.rows = payload.rows;
  state.fullMatrix = false;
  $("matrix-description").textContent = `当前眼模型、${fixed(request.pupil_diameter_mm, 1)} mm 瞳孔和三个固定焦距的 ${payload.row_count} 个工况。`;
  renderChart();
  renderTable(state.rows);
  $("download-csv").disabled = false;
}

function svgElement(name, attributes = {}, text = "") {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
  if (text) node.textContent = text;
  return node;
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
  const focals = [...new Set(state.chartRows.map((row) => row.fixed_focal_length_mm))].sort((a,b) => a-b);
  const values = state.chartRows.map((row) => row[metric]);
  const yMax = Math.max(...values) * 1.12 || 1;
  const xPos = (x) => left + (x - xs[0]) / (xs.at(-1) - xs[0]) * plotWidth;
  const yPos = (y) => top + plotHeight - y / yMax * plotHeight;

  svg.append(svgElement("text", { x: left, y: 22, class: "chart-title" }, `${selectedEye().label} · ${fixed(Number($("pupil-select").value),1)} mm 瞳孔 · ${metricLabel}`));
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
  svg.append(svgElement("text", { x: left+plotWidth/2, y: height-10, "text-anchor": "middle", class: "chart-text" }, "物方需求 / D"));
  svg.append(svgElement("text", { x: 16, y: top+plotHeight/2, transform: `rotate(-90 16 ${top+plotHeight/2})`, "text-anchor": "middle", class: "chart-text" }, "直径 / mm"));

  focals.forEach((focal, index) => {
    const rows = state.chartRows.filter((row) => row.fixed_focal_length_mm === focal).sort((a,b) => a.source_demand_D-b.source_demand_D);
    const points = rows.map((row) => `${xPos(row.source_demand_D)},${yPos(row[metric])}`).join(" ");
    svg.append(svgElement("polyline", { points, class: "chart-line", stroke: palette[index] }));
    rows.forEach((row) => {
      const dot = svgElement("circle", { cx: xPos(row.source_demand_D), cy: yPos(row[metric]), r: 4, fill: palette[index], class: "chart-dot" });
      dot.append(svgElement("title", {}, `f=${focal} mm, ${row.source_demand_D} D: ${fixed(row[metric])} mm`));
      svg.append(dot);
    });
    const legendX = width - right - 190 + index * 66;
    svg.append(svgElement("line", { x1: legendX, x2: legendX+16, y1: 23, y2: 23, stroke: palette[index], "stroke-width": 3 }));
    svg.append(svgElement("text", { x: legendX+21, y: 27, class: "chart-text" }, `${focal}`));
  });
}

function renderTable(rows) {
  const body = $("results-body");
  body.replaceChildren();
  const fragment = document.createDocumentFragment();
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const values = [row.eye_label, fixed(row.fixed_focal_length_mm,2), fixed(row.pupil_diameter_mm,1), fixed(row.source_demand_D,0), fixed(row.source_distance_mm,2), fixed(row.geometric_min_source_diameter_mm), fixed(row.conservative_source_diameter_mm), fixed(row.retinal_defocus_D,2)];
    values.forEach((value) => { const td = document.createElement("td"); td.textContent = value; tr.append(td); });
    fragment.append(tr);
  });
  body.append(fragment);
}

function downloadUrl(path) {
  const link = document.createElement("a");
  link.href = path;
  link.hidden = true;
  document.body.append(link);
  link.click();
  setTimeout(() => link.remove(), 1000);
}

async function fullSweep() {
  try {
    $("full-sweep").disabled = true;
    $("full-sweep").textContent = "正在生成…";
    const payload = await api("/api/sweep", { method: "POST", body: "{}" });
    state.rows = payload.rows;
    state.fullMatrix = true;
    renderTable(state.rows);
    $("matrix-description").textContent = `完整实验矩阵，共 ${payload.row_count} 个工况；可直接导出 CSV。`;
    showToast(`已生成 ${payload.row_count} 个可复现工况。`);
  } catch (error) {
    showToast(`完整扫描失败：${error.message}`, true);
  } finally {
    $("full-sweep").disabled = false;
    $("full-sweep").textContent = "生成全部 252 工况";
  }
}

async function initialize() {
  try {
    state.config = await api("/api/config");
    $("experiment-id").textContent = state.config.experiment_id;
    $("case-count").textContent = state.config.case_count;
    $("wavelength-value").textContent = `${fixed(state.config.wavelength_nm, 0)} nm`;
    fillSelect($("eye-select"), state.config.eyes, (eye) => eye.label);
    [...$("eye-select").options].forEach((item, index) => { item.value = state.config.eyes[index].id; });
    fillSelect($("demand-select"), state.config.source_demands_D, (value) => fixed(value, 0));
    $("server-label").textContent = "本地模型已连接";
    $("server-label").parentElement.classList.add("ready");
    refreshEyeControls();
  } catch (error) {
    $("server-label").textContent = "模型连接失败";
    showToast(`程序初始化失败：${error.message}`, true);
  }
}

$("experiment-form").addEventListener("submit", calculateCurrent);
$("eye-select").addEventListener("change", refreshEyeControls);
$("focal-select").addEventListener("change", calculateCurrent);
$("pupil-select").addEventListener("change", calculateCurrent);
$("demand-select").addEventListener("change", calculateCurrent);
$("metric-select").addEventListener("change", renderChart);
$("full-sweep").addEventListener("click", fullSweep);
$("download-json").addEventListener("click", () => {
  if (!state.current) return;
  downloadUrl(`/api/case.json?${new URLSearchParams(requestFromControls())}`);
});
$("download-csv").addEventListener("click", () => {
  const query = state.fullMatrix ? "" : `?${new URLSearchParams({eye_id: $("eye-select").value, pupil_diameter_mm: $("pupil-select").value})}`;
  downloadUrl(`/api/sweep.csv${query}`);
});

void initialize();
