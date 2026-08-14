"""Build the canonical source-backed fixed-focal report artifact."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = Path(__file__).resolve().parent
RESULTS = EXPERIMENT / "results"
REPORT = EXPERIMENT / "report"
GENERATED_AT = "2026-08-14T00:00:00Z"


def read_csv(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    converted_rows: list[dict[str, object]] = []
    for row in rows:
        converted: dict[str, object] = {}
        for key, value in row.items():
            if value in {"True", "False"}:
                converted[key] = value == "True"
                continue
            try:
                converted[key] = float(value)
            except (TypeError, ValueError):
                converted[key] = value
        converted_rows.append(converted)
    return converted_rows


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_table(connection: sqlite3.Connection, name: str, rows: list[dict[str, object]]) -> None:
    columns = list(rows[0])
    connection.execute(f"CREATE TABLE {name} ({', '.join(f'[{column}]' for column in columns)})")
    placeholders = ", ".join("?" for _ in columns)
    connection.executemany(
        f"INSERT INTO {name} VALUES ({placeholders})",
        [[row[column] for column in columns] for row in rows],
    )


def query_rows(connection: sqlite3.Connection, sql: str) -> list[dict[str, object]]:
    cursor = connection.execute(sql)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def build() -> dict[str, object]:
    fixed = read_csv(RESULTS / "fixed_focal_source_sweep.csv")
    headline = read_csv(RESULTS / "headline_results.csv")
    zos = read_csv(RESULTS / "zemax" / "zosapi_validation.csv")
    validation = json.loads((RESULTS / "validation_report.json").read_text(encoding="utf-8"))
    monte = json.loads((RESULTS / "monte_carlo_summary.json").read_text(encoding="utf-8"))

    adult_chart_sql = """SELECT *, printf('f=%g mm', fixed_focal_length_mm) AS focal_label
FROM headline_results WHERE eye_id='adult_18y' ORDER BY fixed_focal_length_mm, source_demand_D"""
    adult_pupil_sql = """SELECT *, printf('f=%g mm', fixed_focal_length_mm) AS focal_label,
printf('%g D', source_demand_D) AS demand_label
FROM fixed_focal_source_sweep
WHERE eye_id='adult_18y' AND source_demand_D IN (60,120)
ORDER BY source_demand_D, fixed_focal_length_mm, pupil_diameter_mm"""
    headline_sql = "SELECT * FROM headline_results ORDER BY eye_id, fixed_focal_length_mm, source_demand_D"
    zos_sql = "SELECT * FROM zosapi_validation ORDER BY case_id"
    connection = sqlite3.connect(":memory:")
    load_table(connection, "fixed_focal_source_sweep", fixed)
    load_table(connection, "headline_results", headline)
    load_table(connection, "zosapi_validation", zos)
    adult_chart = query_rows(connection, adult_chart_sql)
    adult_pupil = query_rows(connection, adult_pupil_sql)
    headline = query_rows(connection, headline_sql)
    zos = query_rows(connection, zos_sql)
    connection.close()

    def case(demand: float) -> dict[str, object]:
        return next(
            row for row in adult_chart
            if row["source_demand_D"] == demand and row["fixed_focal_length_mm"] == 16.7
        )

    adult_60 = case(60.0)
    adult_120 = case(120.0)
    summary = [{
        "main_rows": validation["fixed_focal_sweep_rows"],
        "adult_60_conservative_mm": adult_60["conservative_source_diameter_mm"],
        "adult_120_conservative_mm": adult_120["conservative_source_diameter_mm"],
        "zos_bound_error_um": validation["zos_bound_max_error_um"],
        "conservative_uniformity": monte["conservative_full_overlap"]["p10_to_mean_uniformity"],
    }]

    def query_source(source_id: str, label: str, path: Path, sql: str, tables: list[str]) -> dict[str, object]:
        return {"id": source_id, "label": label, "path": rel(path), "query": {"engine": "sqlite", "sql": sql, "description": "报告生成器实际执行的 SQLite 查询。", "executed_at": GENERATED_AT, "tables_used": tables}}

    sources = [
        {"id": "ppt_input", "label": "用户提供的小鸡与人眼光学参数 PPT", "path": rel(next((EXPERIMENT / "source").glob("*.pptx")))},
        {"id": "fixed_sweep", "label": "固定焦距光源尺寸主扫描", "path": rel(RESULTS / "fixed_focal_source_sweep.csv")},
        query_source("adult_chart_query", "成人固定焦距物距曲线 SQL", RESULTS / "headline_results.csv", adult_chart_sql, ["headline_results"]),
        query_source("adult_pupil_query", "成人瞳孔敏感性 SQL", RESULTS / "fixed_focal_source_sweep.csv", adult_pupil_sql, ["fixed_focal_source_sweep"]),
        query_source("headline_query", "最大瞳孔设计值 SQL", RESULTS / "headline_results.csv", headline_sql, ["headline_results"]),
        query_source("zos_query", "OpticStudio 固定焦距验证 SQL", RESULTS / "zemax" / "zosapi_validation.csv", zos_sql, ["zosapi_validation"]),
        {"id": "validation", "label": "自动验证结果", "path": rel(RESULTS / "validation_report.json")},
        {"id": "monte", "label": "600,000 光线蒙特卡洛覆盖验证", "path": rel(RESULTS / "monte_carlo_summary.json")},
    ]

    manifest = {
        "version": 1,
        "surface": "report",
        "title": "小鸡与人眼 650 nm 固定焦距后极照明仿真",
        "description": "固定后极位置、每眼三个离散焦距、60–120 D 物方需求下的光源几何尺寸与 OpticStudio 交叉验证。",
        "generatedAt": GENERATED_AT,
        "cards": [],
        "charts": [
            {"id": "adult_demand", "title": "成人眼三个固定焦距下的保守光源直径", "subtitle": "最大瞳孔 5 mm；60–120 D，步长 10 D。", "type": "line", "dataset": "adult_chart", "sourceId": "adult_chart_query", "encodings": {"x": {"field": "source_demand_D", "type": "quantitative", "label": "物方需求 (D)"}, "y": {"field": "conservative_source_diameter_mm", "type": "quantitative", "label": "保守光源直径 (mm)", "format": "number"}, "color": {"field": "focal_label", "type": "nominal", "label": "固定焦距"}}, "yAxisTitle": "保守光源直径 (mm)", "valueFormat": "number", "layout": "full"},
            {"id": "adult_pupil", "title": "成人眼瞳孔与固定焦距对光源尺寸的共同影响", "subtitle": "60 D 与 120 D 端点工况；每条曲线保持焦距不变。", "type": "line", "dataset": "adult_pupil", "sourceId": "adult_pupil_query", "encodings": {"x": {"field": "pupil_diameter_mm", "type": "quantitative", "label": "瞳孔直径 (mm)"}, "y": {"field": "conservative_source_diameter_mm", "type": "quantitative", "label": "保守光源直径 (mm)", "format": "number"}, "color": {"field": "focal_label", "type": "nominal", "label": "固定焦距"}}, "yAxisTitle": "保守光源直径 (mm)", "valueFormat": "number", "layout": "full"},
        ],
        "tables": [
            {"id": "headline_table", "title": "最大瞳孔下的 63 个固定焦距设计工况", "subtitle": "3 个眼模型 × 3 个固定焦距 × 7 个物方需求。", "dataset": "headline", "sourceId": "headline_query", "defaultSort": {"field": "source_demand_D", "direction": "asc"}, "columns": [
                {"field": "eye_label", "label": "眼模型", "type": "text"},
                {"field": "fixed_focal_length_mm", "label": "固定焦距 (mm)", "format": "number"},
                {"field": "source_demand_D", "label": "物方需求 (D)", "format": "number"},
                {"field": "source_distance_mm", "label": "物距 (mm)", "format": "number"},
                {"field": "pupil_diameter_mm", "label": "瞳孔 (mm)", "format": "number"},
                {"field": "geometric_min_source_diameter_mm", "label": "几何最小直径 (mm)", "format": "number"},
                {"field": "conservative_source_diameter_mm", "label": "保守直径 (mm)", "format": "number"},
            ]},
            {"id": "zos_table", "title": "OpticStudio 固定焦距边界交叉验证", "subtitle": "6 个系统，每个系统追迹 4 条源面/瞳孔角点光线。", "dataset": "zos", "sourceId": "zos_query", "defaultSort": {"field": "case_id", "direction": "asc"}, "columns": [
                {"field": "case_id", "label": "案例", "type": "text"},
                {"field": "fixed_focal_length_mm", "label": "固定焦距 (mm)", "format": "number"},
                {"field": "source_distance_mm", "label": "物距 (mm)", "format": "number"},
                {"field": "pupil_diameter_mm", "label": "瞳孔 (mm)", "format": "number"},
                {"field": "conservative_source_diameter_mm", "label": "保守直径 (mm)", "format": "number"},
                {"field": "bound_error_um", "label": "边界误差 (µm)", "format": "number"},
                {"field": "zos_file", "label": "Zemax 文件", "type": "text"},
            ]},
        ],
        "sources": sources,
        "blocks": [
            {"id": "title", "type": "markdown", "body": "# 小鸡与人眼 650 nm 固定焦距后极照明仿真\n\n**技术报告｜固定后极位置 + 三个离散焦距 + OpticStudio 交叉验证**"},
            {"id": "summary", "type": "markdown", "sourceId": "validation", "body": "## 技术摘要\n\n本版纠正了旧模型的核心假设：**不再连续改变等效焦距以强制满足物方需求**。小鸡、儿童和成人各只使用三个固定焦距；后极平面由已知眼轴和像方折射率固定。完整主矩阵包含 **252 个工况**。每个工况同时给出几何最小尺寸和推荐的保守全重叠尺寸，不再输出“超过调节上限”的判定。"},
            {"id": "finding", "type": "markdown", "sourceId": "headline_query", "body": "## 固定焦距后，光源尺寸由物距、焦距和瞳孔共同决定\n\n旧版聚焦解让光源尺寸几乎只随物距缩放；纠正后，瞳孔产生的离焦 footprint 与固定焦距共同进入尺寸计算。保守直径保证整个后极目标位于源像与瞳孔模糊卷积的全重叠平台内，因此比仅让外边界碰到目标的几何最小直径更适合作为第一阶段设计值。"},
            {"id": "adult_chart", "type": "chart", "chartId": "adult_demand", "layout": "full"},
            {"id": "adult_explain", "type": "markdown", "sourceId": "adult_chart_query", "body": "在成人 5 mm 瞳孔下，三个固定焦距形成三条不同曲线；模型不会在曲线上改变焦距。60–120 D 表示七个离散物距工况，而不是需要眼睛提供同等数值调节力。"},
            {"id": "pupil_section", "type": "markdown", "sourceId": "fixed_sweep", "body": "## 瞳孔不再是聚焦像尺寸中的无关变量\n\n固定焦距通常不会把给定物距精确成像到固定后极平面，因而瞳孔直径直接控制离焦 footprint。下图用于选择同一固定焦距下的实际光阑工况；不能用一个瞳孔结果替代全部瞳孔。"},
            {"id": "pupil_chart", "type": "chart", "chartId": "adult_pupil", "layout": "full"},
            {"id": "definition", "type": "markdown", "body": "## 范围、参数与尺寸定义\n\n- 物方需求：60、70、80、90、100、110、120 D，对应物距 16.67–8.33 mm。\n- 固定焦距：小鸡 7.5/8.0/8.5 mm；儿童 13.5/15.1/16.7 mm；成人 12.8/14.75/16.7 mm。中间值采用 PPT 区间的算术中点。\n- 固定后极平面：报告眼轴除以 1.336 的约化传播距离；目标直径为小鸡 3 mm、人眼 6 mm。\n- 几何最小直径：源像与瞳孔 footprint 的外边界刚好覆盖目标。\n- 保守直径：目标完全位于卷积全重叠平台内，是当前推荐值。"},
            {"id": "headline", "type": "table", "tableId": "headline_table", "layout": "full"},
            {"id": "method", "type": "markdown", "body": "## 固定参数 ABCD 方法\n\n使用光线状态 `[y,nθ]`。对固定眼屈光力、固定物距和固定后极平面，视网膜光线高度写为 `y_r=m_s y_s+m_p y_p`。其中 `m_s` 是源面映射系数，`m_p` 是瞳孔映射系数。由两个圆盘线性映射后的支持域和全重叠域直接反解两种光源半径，全程没有求解新的眼焦距。"},
            {"id": "zos_section", "type": "markdown", "sourceId": "zos_query", "body": "## OpticStudio 验证固定焦距 footprint，而不是验证强制调焦\n\nZOS-API 创建 6 个固定焦距 Paraxial 系统，像面厚度使用相同的约化后极距离。每个系统追迹源面正负边缘与瞳孔正负边缘的 4 个组合，并将视网膜高度上下界与解析矩阵比较。"},
            {"id": "zos_table", "type": "table", "tableId": "zos_table", "layout": "full"},
            {"id": "limitations", "type": "markdown", "body": "## 限制、不确定性与稳健性\n\n中间焦距由区间端点的算术中点选取；若用户已有指定的三个实测焦距，应直接替换配置并重跑。1.336 是约化眼像方折射率假设，等效主平面位置仍未由 PPT 唯一确定。当前结果是近轴几何覆盖，不代表绝对视网膜辐照度、组织安全、像差或散射。几何最小值为零只表示瞳孔离焦 footprint 已达到目标边缘，并不表示实际可使用零面积光源。"},
            {"id": "next", "type": "markdown", "body": "## 建议的下一阶段\n\n1. 用实测值确认每个模型的三个固定焦距和等效主平面位置。\n2. 明确验收标准是几何覆盖、最低照度还是均匀性阈值。\n3. 在确认固定焦距基线后，再加入外置负镜片、实际顶点距和倾斜偏心。\n4. 用非序列探测器及实测光源辐亮度验证绝对照度和安全边界。"},
            {"id": "questions", "type": "markdown", "body": "## 尚待确认的问题\n\n- 三个固定焦距是否就是区间端点和中点，还是另有三组实测值？\n- 等效透镜主平面到后极的实际距离是多少？\n- ‘覆盖’是否需要规定最低照度或均匀性比例？"},
        ],
    }

    return {
        "surface": "report",
        "manifest": manifest,
        "snapshot": {"version": 1, "generatedAt": GENERATED_AT, "status": "ready", "datasets": {"summary": summary, "adult_chart": adult_chart, "adult_pupil": adult_pupil, "headline": headline, "zos": zos}},
        "sources": sources,
        "package_info": {"root": ".", "manifestPath": rel(REPORT / "artifact.json"), "snapshotPath": rel(REPORT / "artifact.json")},
    }


def main() -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    destination = REPORT / "artifact.json"
    destination.write_text(json.dumps(build(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
