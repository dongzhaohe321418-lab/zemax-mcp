"""Build the canonical, source-backed report artifact for the eye experiment."""

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
    result: list[dict[str, object]] = []
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
        result.append(converted)
    return result


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_table(connection: sqlite3.Connection, name: str, rows: list[dict[str, object]]) -> None:
    columns = list(rows[0])
    connection.execute(
        f"CREATE TABLE {name} ({', '.join(f'[{column}]' for column in columns)})"
    )
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
    headline = read_csv(RESULTS / "headline_results.csv")
    focused = read_csv(RESULTS / "focused_source_sweep.csv")
    infinity = read_csv(RESULTS / "infinity_angular_sweep.csv")
    defocus = read_csv(RESULTS / "defocus_pupil_sweep.csv")
    zos = read_csv(RESULTS / "zemax" / "zosapi_validation.csv")
    monte = json.loads((RESULTS / "monte_carlo_summary.json").read_text(encoding="utf-8"))
    validation = json.loads((RESULTS / "validation_report.json").read_text(encoding="utf-8"))

    source_size_sql = """SELECT *, printf('%g D', source_demand_D) AS demand_label,
CASE WHEN feasible_accommodation THEN '可行' ELSE '超出调节范围' END AS feasibility
FROM headline_results"""
    adult_external_sql = """SELECT external_lens_D, printf('%g D', external_lens_D) AS lens_label,
accommodation_D, source_diameter_mm, source_area_mm2,
CASE WHEN feasible_accommodation THEN '可行' ELSE '超出调节范围' END AS feasibility
FROM focused_source_sweep
WHERE eye_id = 'adult_18y' AND source_demand_D = 10"""
    adult_defocus_sql = """SELECT defocus_D, printf('%+g D', defocus_D) AS defocus_label,
blur_diameter_mm, geometric_min_angular_diameter_deg AS geometric_min_deg,
uniform_conservative_angular_diameter_deg AS uniform_conservative_deg
FROM defocus_pupil_sweep
WHERE eye_id = 'adult_18y' AND pupil_diameter_mm = 5"""
    zos_detail_sql = """SELECT case_id, CASE WHEN accommodated THEN '是' ELSE '否' END AS accommodated,
target_radius_mm AS target_edge_mm, mean_image_y_mm AS observed_edge_mm,
ABS(mean_image_y_mm - target_radius_mm) * 1000.0 AS edge_error_um,
rms_spread_um, valid_rays, zos_file
FROM zosapi_validation"""
    summary_sql = """SELECT
(SELECT source_diameter_mm FROM headline_results WHERE eye_id='adult_18y' AND source_demand_D=10) AS adult_10D_source_diameter_mm,
(SELECT angular_diameter_deg FROM infinity_angular_sweep WHERE eye_id='adult_18y' AND source_demand_D=0 AND external_lens_D=0) AS adult_infinity_full_angle_deg,
(SELECT focused_zos_edge_max_error_um FROM validation_summary) AS zos_max_focused_edge_error_um,
(SELECT focused_capture_fraction FROM monte_carlo_summary) AS focused_capture_fraction"""

    connection = sqlite3.connect(":memory:")
    for name, rows in [
        ("headline_results", headline), ("focused_source_sweep", focused),
        ("infinity_angular_sweep", infinity), ("defocus_pupil_sweep", defocus),
        ("zosapi_validation", zos),
    ]:
        load_table(connection, name, rows)
    load_table(connection, "validation_summary", [validation])
    load_table(connection, "monte_carlo_summary", [{"focused_capture_fraction": monte["focused_adult_10D"]["captured_ray_fraction"]}])
    source_size = query_rows(connection, source_size_sql)
    adult_external = query_rows(connection, adult_external_sql)
    adult_defocus = query_rows(connection, adult_defocus_sql)
    zos_detail = query_rows(connection, zos_detail_sql)
    summary = query_rows(connection, summary_sql)
    connection.close()

    def query_source(source_id: str, label: str, path: Path, sql: str, tables: list[str]) -> dict[str, object]:
        return {"id": source_id, "label": label, "path": rel(path), "query": {"engine": "sqlite", "sql": sql, "description": "报告生成器实际执行的 SQLite 查询。", "executed_at": GENERATED_AT, "tables_used": tables}}

    sources = [
        {"id": "ppt_input", "label": "用户提供的眼部光学参数 PPT", "path": rel(EXPERIMENT / "source" / "小鸡和人眼光学仿真参数.pptx")},
        query_source("summary_query", "汇总指标 SQL", EXPERIMENT / "make_report_artifact.py", summary_sql, ["headline_results", "infinity_angular_sweep", "validation_summary", "monte_carlo_summary"]),
        query_source("source_size_query", "主要光源尺寸 SQL", RESULTS / "headline_results.csv", source_size_sql, ["headline_results"]),
        query_source("adult_external_query", "成人外置镜片 SQL", RESULTS / "focused_source_sweep.csv", adult_external_sql, ["focused_source_sweep"]),
        query_source("defocus_query", "成人离焦 SQL", RESULTS / "defocus_pupil_sweep.csv", adult_defocus_sql, ["defocus_pupil_sweep"]),
        query_source("zos_query", "OpticStudio 交叉验证 SQL", RESULTS / "zemax" / "zosapi_validation.csv", zos_detail_sql, ["zosapi_validation"]),
    ]

    manifest = {
        "version": 1,
        "surface": "report",
        "title": "小鸡与人眼 650 nm 全视网膜照明仿真",
        "description": "独立近轴模型、蒙特卡洛照度评估与 Ansys Zemax OpticStudio ZOS-API 交叉验证技术报告。",
        "generatedAt": GENERATED_AT,
        "cards": [
            {"id": "geometry", "description": "成人眼在 10 D（100 mm）物距、无外置镜片时覆盖直径 6 mm 后极部所需的圆形光源直径。", "dataset": "summary", "sourceId": "summary_query", "metrics": [{"label": "成人 10 D 光源直径 (mm)", "field": "adult_10D_source_diameter_mm", "format": "number"}]},
            {"id": "infinity", "description": "成人眼无穷远照明覆盖直径 6 mm 后极部所需的完整角直径。", "dataset": "summary", "sourceId": "summary_query", "metrics": [{"label": "无穷远完整角直径 (deg)", "field": "adult_infinity_full_angle_deg", "format": "number"}]},
            {"id": "zos_error", "description": "聚焦验证案例中独立模型与 OpticStudio 视网膜边缘位置的最大绝对误差。", "dataset": "summary", "sourceId": "summary_query", "metrics": [{"label": "ZOS 最大边缘误差 (µm)", "field": "zos_max_focused_edge_error_um", "format": "number"}]},
            {"id": "capture", "description": "成人 10 D 聚焦案例中命中目标后极部区域的蒙特卡洛光线比例。", "dataset": "summary", "sourceId": "summary_query", "metrics": [{"label": "聚焦捕获比例", "field": "focused_capture_fraction", "format": "percent"}]},
        ],
        "charts": [
            {
                "id": "source_diameter",
                "title": "物距越近，覆盖后极部所需的实体光源越小",
                "subtitle": "三种眼模型的目标视网膜直径不同，但所需角尺寸均约 20°，因此曲线接近。",
                "type": "bar", "dataset": "source_size", "sourceId": "source_size_query",
                "encodings": {"x": {"field": "demand_label", "type": "ordinal", "label": "物方屈光需求"}, "y": {"field": "source_diameter_mm", "type": "quantitative", "label": "光源直径 (mm)", "format": "number"}, "color": {"field": "eye_label", "type": "nominal", "label": "眼模型"}},
                "yAxisTitle": "光源直径 (mm)", "valueFormat": "number", "layout": "full",
            },
            {
                "id": "external_lens",
                "title": "负外置镜片显著增加成人眼调节需求",
                "subtitle": "光源固定在 100 mm；-15 D 及 -20 D 时超过成人 18 D 调节上限。",
                "type": "bar", "dataset": "adult_external", "sourceId": "adult_external_query",
                "encodings": {"x": {"field": "lens_label", "type": "ordinal", "label": "外置镜片度数"}, "y": {"field": "accommodation_D", "type": "quantitative", "label": "所需调节 (D)", "format": "number"}},
                "yAxisTitle": "所需调节 (D)", "valueFormat": "number", "layout": "full",
            },
            {
                "id": "defocus_blur",
                "title": "成人最大瞳孔下，离焦量近似线性决定模糊斑直径",
                "subtitle": "5 mm 瞳孔；正负离焦的几何模糊斑大小对称。",
                "type": "line", "dataset": "adult_defocus", "sourceId": "defocus_query",
                "encodings": {"x": {"field": "defocus_D", "type": "quantitative", "label": "离焦 (D)"}, "y": {"field": "blur_diameter_mm", "type": "quantitative", "label": "模糊斑直径 (mm)", "format": "number"}},
                "yAxisTitle": "模糊斑直径 (mm)", "valueFormat": "number", "layout": "full",
            },
        ],
        "tables": [
            {"id": "headline", "title": "无外置镜片的主要几何设计值", "subtitle": "调节可行性按照 PPT 给定调节上限判定。", "dataset": "source_size", "sourceId": "source_size_query", "defaultSort": {"field": "source_demand_D", "direction": "asc"}, "columns": [
                {"field": "eye_label", "label": "眼模型", "type": "text"}, {"field": "source_demand_D", "label": "物方需求 (D)", "format": "number"}, {"field": "source_distance_mm", "label": "物距 (mm)", "format": "number"}, {"field": "source_diameter_mm", "label": "光源直径 (mm)", "format": "number"}, {"field": "source_area_mm2", "label": "光源面积 (mm²)", "format": "number"}, {"field": "accommodation_D", "label": "调节 (D)", "format": "number"}, {"field": "feasibility", "label": "可行性", "type": "text"}
            ]},
            {"id": "adult_lens", "title": "成人眼 100 mm 物距的外置镜片扫描", "dataset": "adult_external", "sourceId": "adult_external_query", "defaultSort": {"field": "external_lens_D", "direction": "desc"}, "columns": [
                {"field": "external_lens_D", "label": "镜片 (D)", "format": "number"}, {"field": "accommodation_D", "label": "所需调节 (D)", "format": "number"}, {"field": "source_diameter_mm", "label": "光源直径 (mm)", "format": "number"}, {"field": "source_area_mm2", "label": "光源面积 (mm²)", "format": "number"}, {"field": "feasibility", "label": "可行性", "type": "text"}
            ]},
            {"id": "zos_cases", "title": "OpticStudio 真实光线追迹交叉验证", "subtitle": "5 个聚焦案例和 1 个故意不调焦案例；每个系统均保存为可打开的 .zos 文件。", "dataset": "zos_detail", "sourceId": "zos_query", "defaultSort": {"field": "case_id", "direction": "asc"}, "columns": [
                {"field": "case_id", "label": "案例", "type": "text"}, {"field": "accommodated", "label": "已调焦", "type": "text"}, {"field": "target_edge_mm", "label": "目标边缘 (mm)", "format": "number"}, {"field": "observed_edge_mm", "label": "ZOS 边缘 (mm)", "format": "number"}, {"field": "edge_error_um", "label": "边缘误差 (µm)", "format": "number"}, {"field": "rms_spread_um", "label": "RMS (µm)", "format": "number"}, {"field": "valid_rays", "label": "有效光线", "format": "number"}, {"field": "zos_file", "label": "Zemax 文件", "type": "text"}
            ]},
        ],
        "sources": sources,
        "blocks": [
            {"id": "title", "type": "markdown", "body": "# 小鸡与人眼 650 nm 全视网膜照明仿真\n\n**技术报告｜独立模型 + 蒙特卡洛 + Ansys Zemax OpticStudio 24.1**"},
            {"id": "summary", "type": "markdown", "sourceId": "summary_query", "body": "## 技术摘要\n\n本研究建立三个有效眼模型，计算圆形均匀光源覆盖指定后极部区域所需的尺寸，并扫描物距、离焦、瞳孔、眼轴和负外置镜片。自动验证状态为 **passed**；独立模型与 OpticStudio 聚焦边缘位置的最大误差为 **4.44×10⁻¹³ µm**，属于双精度数值舍入量级。"},
            {"id": "metrics", "type": "metric-strip", "cardIds": ["geometry", "infinity", "zos_error", "capture"]},
            {"id": "findings", "type": "markdown", "body": "## 关键结论与设计含义\n\n几何设计的首要控制量是视网膜覆盖角，而不是瞳孔直径。实体光源尺寸随物距变化；瞳孔主要影响离焦容差和通过量。下图把离散设计工况放在同一尺度上比较。"},
            {"id": "source_chart", "type": "chart", "chartId": "source_diameter", "layout": "full"},
            {"id": "source_explain", "type": "markdown", "sourceId": "source_size_query", "body": "成人与儿童在 **100 mm / 10 D** 工况均需约 **35.93 mm** 直径光源；小鸡需约 **35.71 mm**。小鸡的 20 D 工况超过 15.69 D 调节上限，成人的 20 D 工况超过 18 D 上限，6 岁儿童在给定 22.5 D 上限内仍可行。"},
            {"id": "headline_table", "type": "table", "tableId": "headline", "layout": "full"},
            {"id": "lens_section", "type": "markdown", "body": "## 外置负镜片建模\n\n外置薄透镜与眼的有效薄透镜通过 ABCD 矩阵串联，镜片顶点距暂定为小鸡 5 mm、人眼 12 mm。负镜片不仅提高调节需求，也轻微改变覆盖同一视网膜区域所需的光源尺寸。"},
            {"id": "lens_chart", "type": "chart", "chartId": "external_lens", "layout": "full"},
            {"id": "lens_explain", "type": "markdown", "sourceId": "adult_external_query", "body": "成人眼在 100 mm 物距时，外置镜片从 0 D 变为 -10 D，所需调节从 **10.00 D** 增至 **17.00 D**，仍在 18 D 上限内；-15 D 和 -20 D 分别需要 **20.03 D** 与 **22.79 D**，不可由该模型的成人调节范围补偿。"},
            {"id": "lens_table", "type": "table", "tableId": "adult_lens", "layout": "full"},
            {"id": "method", "type": "markdown", "body": "## 范围、定义与方法\n\n- 波长固定为 650 nm；几何追迹在近轴条件下进行。\n- 每只眼由校准后的有效薄透镜表示，视网膜位置固定，调节通过改变眼的有效屈光力实现。\n- 圆形朗伯均匀发光面在聚焦状态下成像为覆盖目标后极部的圆盘。\n- 离焦以光焦度偏差定义，边缘光线给出几何模糊斑；蒙特卡洛每个案例追迹 600,000 条光线。\n- OpticStudio 验证使用 ZOS-API 创建顺序模式 Paraxial 系统并批量追迹真实光线；生成 6 个 `.zos` 系统文件。"},
            {"id": "defocus_chart", "type": "chart", "chartId": "defocus_blur", "layout": "full"},
            {"id": "defocus_explain", "type": "markdown", "sourceId": "defocus_query", "body": "成人 5 mm 瞳孔在 ±10 D 离焦时产生约 **0.835 mm** 几何模糊斑。若要在该离焦范围仍保持均匀覆盖，应采用保守角直径而不能只采用聚焦态最小角直径；代价是有一部分光线落到目标后极部之外。"},
            {"id": "zos_section", "type": "markdown", "sourceId": "zos_query", "body": "## OpticStudio 交叉验证\n\n5 个已调焦案例的最大视网膜边缘误差为 **4.44×10⁻¹³ µm**，最大 RMS 展宽为 **5.66×10⁻¹² µm**。故意不调焦的成人 10 D 案例预测展宽 **0.82665 mm**，OpticStudio 观测值同为 **0.82665 mm**。"},
            {"id": "zos_table", "type": "table", "tableId": "zos_cases", "layout": "full"},
            {"id": "limitations", "type": "markdown", "body": "## 限制、不确定性与稳健性\n\n当前模型适合几何尺寸、调节可行性和离焦容差的第一阶段设计，但不是眼组织安全或高阶像质模型。PPT 未提供光源辐射通量、曝光时间、光谱带宽、组织透射率、角膜/晶状体曲率、折射率、像差和眼球转动范围，因此本报告不输出绝对视网膜辐照度、热剂量或光化学安全结论。PPT 第 5 页的“15 D”按上下文暂解释为 **-15 D**；镜片顶点距也属于待实测参数。眼轴敏感性已计算，但完整生物个体差异仍需实测分布。"},
            {"id": "next", "type": "markdown", "body": "## 建议的下一阶段\n\n1. 实测光源辐亮度、光谱、工作距离和曝光时间，建立绝对辐射度与 IEC/ISO 安全约束。\n2. 用角膜、房水、晶状体、玻璃体和视网膜的多曲面模型替换有效薄透镜，并加入波前像差。\n3. 实测外置镜片顶点距及倾斜/偏心，执行公差蒙特卡洛。\n4. 将目标从“覆盖后极部圆盘”扩展到眼球转动后的全视网膜包络，并用非序列模式验证遮挡、散射和杂散光。\n5. 用实验相机或离体/模型眼测得的照度图对蒙特卡洛结果做外部验证。"},
            {"id": "questions", "type": "markdown", "body": "## 尚待确认的问题\n\n- 小鸡与人眼的实际眼轴、瞳孔和调节力分布是否有原始样本数据？\n- 光源是否严格为朗伯面源，还是带透镜/导光结构？\n- “覆盖视网膜”的验收标准是几何覆盖、最低照度、均匀性，还是安全剂量？\n- 外置镜片 -15 D 的符号以及所有镜片的实际顶点距是多少？"},
        ],
    }

    return {
        "surface": "report",
        "manifest": manifest,
        "snapshot": {"version": 1, "generatedAt": GENERATED_AT, "status": "ready", "datasets": {"summary": summary, "source_size": source_size, "adult_external": adult_external, "adult_defocus": adult_defocus, "zos_detail": zos_detail}},
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
