"use strict";

const state = {
  config: null,
  current: null,
  rows: [],
  chartRows: [],
  fullMatrix: false,
  chartSeriesKey: "fixed_focal_length_mm",
  chartSeriesParameter: "focal_length_mm",
};
const palette = ["#0f6d70", "#e56b3f", "#d7a22a"];
const $ = (id) => document.getElementById(id);

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
  $(`range-${id}-limits`).textContent = `${specification.minimum}–${specification.maximum} ${unit} · ${specification.provenance}`;
}

function updateRangeOutput(id, unit, digits = 2) {
  $(`range-${id}-value`).textContent = `${fixed($(`range-${id}`).value, digits)} ${unit}`;
  if (id === "axial") $("axial-value").textContent = `${fixed($("range-axial").value, 2)} mm`;
}

function componentLabel(parameter) {
  const labels = {
    corneal_curvature_radius_mm: "角膜曲率半径",
    corneal_equivalent_power_D: "角膜等效屈光力",
    crystalline_lens_thickness_mm: "晶状体厚度",
    crystalline_lens_equivalent_power_D: "晶状体等效屈光力",
    corneal_equivalent_focal_length_mm: "角膜等效焦距",
    crystalline_lens_equivalent_focal_length_mm: "晶状体等效焦距",
  };
  const value = parameter.value !== undefined ? parameter.value : `${parameter.minimum}–${parameter.maximum}`;
  const unit = parameter.name.endsWith("_D") ? "D" : "mm";
  return `${labels[parameter.name] || parameter.name}: ${value} ${unit}（参考，不独立追迹）`;
}

function renderRangeProvenance(eye) {
  const parameters = eye.range_parameters;
  $("range-provenance-text").textContent = [
    parameters.effective_focal_length_mm.provenance,
    parameters.axial_length_mm.provenance,
    parameters.pupil_diameter_mm.provenance,
  ].join("；");
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
  fillSelect($("external-lens-select"), lensValues, (value) => value === 0 ? "0（无外镜）" : `${value}`);
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
  $("analysis-title").textContent = rangeMode ? "参数范围灵敏度" : "固定焦距对比";
  $("parameter-summary-title").innerHTML = rangeMode
    ? '<span aria-hidden="true">◆</span> 当前后极参数 · 眼轴可调'
    : '<span aria-hidden="true">◆</span> 已知后极参数 · 只读';
  $("method-focal").textContent = rangeMode
    ? "焦距由用户在 PPT 区间内手动选择，不由物距反求或自动拟合。"
    : "焦距只能取配置中的三个离散固定值。";
  $("method-axial").textContent = rangeMode
    ? "眼轴可在声明区间内独立变化；后极约化距离随之更新。"
    : "后极平面由报告眼轴和像方折射率固定。";
  $("full-sweep").textContent = rangeMode ? "生成三水平范围网格" : "生成全部 252 工况";
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
  $("diagram-demand").textContent = `${fixed(result.source_demand_D, result.mode === "range" ? 1 : 0)} D`;
  $("source-label").textContent = `${fixed(result.conservative_source_diameter_mm)} mm`;
  $("lens-label").textContent = result.external_lens_power_D
    ? `${fixed(result.effective_focal_length_mm, 2)} mm · 外镜 ${result.external_lens_power_D} D`
    : `${fixed(result.effective_focal_length_mm, 2)} mm`;
  $("target-label").textContent = `${fixed(result.posterior_pole_diameter_mm, 2)} mm`;
  $("axial-value").textContent = `${fixed(result.axial_length_mm, 2)} mm`;
  const modeText = result.mode === "range" ? "范围探索值" : "固定网格值";
  const interpretation = result.pupil_blur_alone_covers_target
    ? "瞳孔离焦 footprint 已覆盖目标边缘，因此几何最小值为 0；实际设计仍应采用推荐全重叠尺寸。"
    : `建议使用 ${fixed(result.conservative_source_diameter_mm)} mm 光源，使目标完整位于全重叠平台内。`;
  $("interpretation").querySelector("p").textContent = `${modeText}：${interpretation}`;
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
    $("interpretation").querySelector("p").textContent = `当前组合不可计算：${error.message}`;
    showToast(`计算失败：${error.message}`, true);
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
    $("matrix-description").textContent = `当前参数的三水平灵敏度扫描：${payload.row_count} 个有效工况，跳过 ${payload.skipped_count} 个机械顺序无效工况。`;
  } else {
    const request = { eye_id: $("eye-select").value, pupil_diameter_mm: Number($("pupil-select").value) };
    const payload = await api("/api/sweep", { method: "POST", body: JSON.stringify(request) });
    state.chartRows = payload.rows;
    state.rows = payload.rows;
    state.chartSeriesKey = "fixed_focal_length_mm";
    state.chartSeriesParameter = "focal_length_mm";
    state.fullMatrix = false;
    $("matrix-description").textContent = `当前眼模型、${fixed(request.pupil_diameter_mm, 1)} mm 瞳孔和三个固定焦距的 ${payload.row_count} 个工况。`;
  }
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

function seriesUnit(parameter) {
  return parameter === "pupil_diameter_mm" || parameter === "focal_length_mm" || parameter === "axial_length_mm" ? "mm" : "";
}

function seriesName(parameter) {
  return { focal_length_mm: "有效焦距", axial_length_mm: "眼轴", pupil_diameter_mm: "瞳孔" }[parameter] || parameter;
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

  svg.append(svgElement("text", { x: left, y: 22, class: "chart-title" }, `${selectedEye().label} · ${metricLabel} · ${seriesLabel}`));
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
      row.eye_label,
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
    if (currentMode() === "range") {
      const payload = await api("/api/range-grid", { method: "POST", body: JSON.stringify(requestFromControls()) });
      state.rows = payload.rows;
      state.fullMatrix = true;
      renderTable(state.rows);
      $("matrix-description").textContent = `范围三水平网格：请求 ${payload.requested_count} 个组合，完成 ${payload.row_count} 个，跳过 ${payload.skipped_count} 个机械顺序无效组合。`;
      showToast(`已生成 ${payload.row_count} 个范围探索工况。`);
    } else {
      const payload = await api("/api/sweep", { method: "POST", body: "{}" });
      state.rows = payload.rows;
      state.fullMatrix = true;
      renderTable(state.rows);
      $("matrix-description").textContent = `固定基准完整矩阵，共 ${payload.row_count} 个工况。`;
      showToast(`已生成 ${payload.row_count} 个基准工况。`);
    }
  } catch (error) {
    showToast(`扫描失败：${error.message}`, true);
  } finally {
    $("full-sweep").disabled = false;
    $("full-sweep").textContent = currentMode() === "range" ? "生成三水平范围网格" : "生成全部 252 工况";
  }
}

async function modeChanged() {
  updateModeCopy();
  await calculateCurrent();
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
$("mode-select").addEventListener("change", modeChanged);
$("eye-select").addEventListener("change", refreshEyeControls);
$("focal-select").addEventListener("change", calculateCurrent);
$("pupil-select").addEventListener("change", calculateCurrent);
$("demand-select").addEventListener("change", calculateCurrent);
$("external-lens-select").addEventListener("change", calculateCurrent);
$("metric-select").addEventListener("change", renderChart);
$("sensitivity-select").addEventListener("change", loadChartRows);
$("full-sweep").addEventListener("click", fullSweep);

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

void initialize();
