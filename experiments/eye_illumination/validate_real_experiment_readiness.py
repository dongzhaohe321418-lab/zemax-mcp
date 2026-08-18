"""Independently audit model arithmetic and real-experiment readiness.

The exit code validates reproducibility of the first-order calculation.  It does
not turn missing anatomical, radiometric, safety, or ethics evidence into a
pass.  Those gaps are deliberately reported as a separate NOT_READY status.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
CONFIG = ROOT / "config" / "experiment.json"
RANGE_CONFIG = ROOT / "app" / "range_parameters.json"
AS_OF_DATE = "2026-08-18"


def _maximum_absolute_difference(observed: pd.Series, expected: np.ndarray) -> float:
    return float(np.max(np.abs(observed.to_numpy(dtype=float) - expected)))


def _markdown(report: dict) -> str:
    diagnostics = report["paraxial_applicability"]
    arithmetic = report["independent_recalculation"]
    blockers = "\n".join(
        f"{index}. **{item['name']}**：{item['reason']}"
        for index, item in enumerate(report["real_experiment_blockers"], start=1)
    )
    return f"""# 真实实验适用性验证报告

生成日期：{report['as_of_date']}

计算状态：**{report['calculation_validation_status']}**

真实实验状态：**{report['real_experiment_readiness_status']}**

## 结论

当前 252 个结果已经在同一近轴等效眼契约内完成独立重算，并通过既有 OpticStudio Paraxial 交叉验证；这说明代码、单位和一阶公式彼此一致。**它们仍不能直接作为小鸡或人体眼部照明的最终光源尺寸、功率或曝光处方。**

最主要的定量原因是：保守源边缘到瞳孔边缘的最大光线角在全部 {diagnostics['case_count']} 个工况中均超过项目设置的 {diagnostics['screening_angle_limit_deg']:.0f}° 近轴筛查线；实际范围为 {diagnostics['minimum_maximum_ray_angle_deg']:.2f}°–{diagnostics['maximum_maximum_ray_angle_deg']:.2f}°。另有 {diagnostics['cases_below_f_number_4']} 个工况的工作 F 数低于 4。因而 OpticStudio 的 Paraxial 一致性验证不能替代真实曲面、真实折射和辐射度验证。

## 独立复算结果

| 检查 | 结果 |
|---|---:|
| 主矩阵行数 | {arithmetic['row_count']} |
| 复合主键重复行 | {arithmetic['duplicate_case_count']} |
| 缺失数值 | {arithmetic['missing_numeric_value_count']} |
| 物距公式最大差值 | {arithmetic['maximum_source_distance_error_mm']:.3e} mm |
| 源映射系数最大差值 | {arithmetic['maximum_source_mapping_error']:.3e} |
| 瞳孔映射系数最大差值 | {arithmetic['maximum_pupil_mapping_error']:.3e} |
| 保守直径最大差值 | {arithmetic['maximum_conservative_diameter_error_mm']:.3e} mm |
| 面积公式最大差值 | {arithmetic['maximum_conservative_area_error_mm2']:.3e} mm² |

## 已验证与未验证的边界

- **已验证**：配置水平、252 行矩阵完整性、无重复工况、单位换算、ABCD 闭式公式、覆盖恒等式、确定性蒙特卡洛复现，以及 OpticStudio Paraxial 边界一致性。
- **未验证**：真实眼主平面、角膜/晶状体多曲面和梯度折射率、视网膜曲率、像差、散射、透射、真实光源角分布、绝对辐照度、温升、光化学风险、个体差异和生物学终点。
- **数据来源限制**：PPT 使用大量近似值且未附原始文献；650 nm 不在 PPT 中；儿童和成人眼轴范围是灵敏度假设；每种眼的中间焦距是区间算术中点，不是实测值。

## 阻止直接进入真实实验的条件

{blockers}

## 放行工作流

1. 用目标个体或可靠解剖数据建立真实曲面眼模型，明确坐标原点、主平面和视网膜曲率。
2. 在 OpticStudio 中使用 real ray；照明与能量问题使用带实测源文件、透射和曲面探测器的非序列模型。
3. 先在离体/仿生眼或校准探测器上验证覆盖、均匀性和绝对辐照度，并给出测量不确定度。
4. 对眼部照明按 [ISO 15004-2:2024](https://www.iso.org/standard/79919.html) 做光危害评价；非相干 LED 同时核对 [IEC 62471](https://webstore.iec.ch/en/publication/7076)，激光核对 [IEC 60825-1](https://webstore.iec.ch/en/publication/3587)。
5. 小鸡实验取得机构动物伦理/IACUC 等效审批；人体研究取得适用的 IRB/伦理审批和知情同意。
6. 只有上述证据全部记录并通过，才把候选尺寸升级为“实验设定值”；首次活体曝光从经批准的最低安全等级开始并设置硬件限幅、联锁和停止规则。

## 官方建模依据

- [Ansys：Paraxial and Parabasal Rays](https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v252/en/OpticStudio_User_Guide/OpticStudio_Help/topics/Paraxial_and_Parabasal_Rays.html)：说明近轴追迹采用小角度和低阶近似，偏离一阶条件时应谨慎解释。
- [Ansys：Paraxial sequential surface](https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v25101/en/OpticStudio_User_Guide/OpticStudio_Help/topics/Paraxial_sequential_surfaces_lens_data_editor.html)：说明 Paraxial 面是理想化模型，并给出约 F/4 的最大 OPD 精度建议。
- [Ansys：Non-Sequential Mode](https://optics.ansys.com/hc/en-us/articles/42661670424851-Exploring-Non-Sequential-Mode-in-OpticStudio)：说明非序列模式适用于照明、杂散光和探测器能量分析。

## 可复现命令

```powershell
python experiments/eye_illumination/run_experiment.py
python experiments/eye_illumination/validate_results.py
python experiments/eye_illumination/validate_real_experiment_readiness.py
python -m pytest -q
```
"""


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    range_config = json.loads(RANGE_CONFIG.read_text(encoding="utf-8"))
    validation = json.loads((RESULTS / "validation_report.json").read_text(encoding="utf-8"))
    fixed = pd.read_csv(RESULTS / "fixed_focal_source_sweep.csv")

    key_columns = ["eye_id", "fixed_focal_length_mm", "pupil_diameter_mm", "source_demand_D"]
    numeric_columns = [
        "source_demand_D",
        "source_distance_mm",
        "reported_axial_length_mm",
        "image_medium_refractive_index",
        "fixed_focal_length_mm",
        "fixed_eye_power_D",
        "pupil_diameter_mm",
        "source_mapping_coefficient",
        "pupil_mapping_coefficient",
        "conservative_source_diameter_mm",
        "conservative_source_area_mm2",
        "maximum_source_pupil_ray_angle_deg",
        "working_f_number",
    ]

    demand = fixed["source_demand_D"].to_numpy(dtype=float)
    source_distance_m = 1.0 / demand
    source_distance_mm = 1000.0 * source_distance_m
    reduced_retina_distance_m = (
        fixed["reported_axial_length_mm"].to_numpy(dtype=float)
        / (1000.0 * fixed["image_medium_refractive_index"].to_numpy(dtype=float))
    )
    power_D = 1000.0 / fixed["fixed_focal_length_mm"].to_numpy(dtype=float)
    expected_source_mapping = -reduced_retina_distance_m / source_distance_m
    expected_pupil_mapping = 1.0 + reduced_retina_distance_m / source_distance_m - reduced_retina_distance_m * power_D
    pupil_radius_m = fixed["pupil_diameter_mm"].to_numpy(dtype=float) / 2000.0
    target_radius_m = fixed["posterior_pole_diameter_mm"].to_numpy(dtype=float) / 2000.0
    expected_pupil_blur_radius_m = np.abs(expected_pupil_mapping) * pupil_radius_m
    expected_conservative_radius_m = (
        target_radius_m + expected_pupil_blur_radius_m
    ) / np.abs(expected_source_mapping)
    expected_conservative_diameter_mm = 2000.0 * expected_conservative_radius_m
    expected_conservative_area_mm2 = math.pi * (expected_conservative_diameter_mm / 2.0) ** 2
    expected_edge_slope = (
        expected_conservative_radius_m + pupil_radius_m
    ) / source_distance_m
    expected_edge_angle_deg = np.degrees(np.arctan(expected_edge_slope))
    expected_working_f_number = (
        fixed["fixed_focal_length_mm"].to_numpy(dtype=float)
        / fixed["pupil_diameter_mm"].to_numpy(dtype=float)
    )

    arithmetic = {
        "row_count": int(len(fixed)),
        "expected_row_count": 252,
        "duplicate_case_count": int(fixed.duplicated(key_columns).sum()),
        "missing_numeric_value_count": int(fixed[numeric_columns].isna().sum().sum()),
        "maximum_source_distance_error_mm": _maximum_absolute_difference(
            fixed["source_distance_mm"], source_distance_mm
        ),
        "maximum_eye_power_error_D": _maximum_absolute_difference(
            fixed["fixed_eye_power_D"], power_D
        ),
        "maximum_source_mapping_error": _maximum_absolute_difference(
            fixed["source_mapping_coefficient"], expected_source_mapping
        ),
        "maximum_pupil_mapping_error": _maximum_absolute_difference(
            fixed["pupil_mapping_coefficient"], expected_pupil_mapping
        ),
        "maximum_conservative_diameter_error_mm": _maximum_absolute_difference(
            fixed["conservative_source_diameter_mm"], expected_conservative_diameter_mm
        ),
        "maximum_conservative_area_error_mm2": _maximum_absolute_difference(
            fixed["conservative_source_area_mm2"], expected_conservative_area_mm2
        ),
        "maximum_edge_angle_error_deg": _maximum_absolute_difference(
            fixed["maximum_source_pupil_ray_angle_deg"], expected_edge_angle_deg
        ),
        "maximum_working_f_number_error": _maximum_absolute_difference(
            fixed["working_f_number"], expected_working_f_number
        ),
    }
    arithmetic_pass = (
        arithmetic["row_count"] == arithmetic["expected_row_count"]
        and arithmetic["duplicate_case_count"] == 0
        and arithmetic["missing_numeric_value_count"] == 0
        and max(
            arithmetic["maximum_source_distance_error_mm"],
            arithmetic["maximum_eye_power_error_D"],
            arithmetic["maximum_source_mapping_error"],
            arithmetic["maximum_pupil_mapping_error"],
            arithmetic["maximum_conservative_diameter_error_mm"],
            arithmetic["maximum_conservative_area_error_mm2"],
            arithmetic["maximum_edge_angle_error_deg"],
            arithmetic["maximum_working_f_number_error"],
        ) < 1e-7
    )

    screening_limit = float(fixed["paraxial_screening_angle_limit_deg"].iloc[0])
    f_number_limit = float(fixed["paraxial_screening_min_f_number"].iloc[0])
    applicability = {
        "case_count": int(len(fixed)),
        "screening_angle_limit_deg": screening_limit,
        "minimum_maximum_ray_angle_deg": float(np.min(expected_edge_angle_deg)),
        "median_maximum_ray_angle_deg": float(np.median(expected_edge_angle_deg)),
        "maximum_maximum_ray_angle_deg": float(np.max(expected_edge_angle_deg)),
        "cases_above_screening_angle": int(np.sum(expected_edge_angle_deg > screening_limit)),
        "cases_above_15_deg": int(np.sum(expected_edge_angle_deg > 15.0)),
        "minimum_working_f_number": float(np.min(expected_working_f_number)),
        "median_working_f_number": float(np.median(expected_working_f_number)),
        "maximum_working_f_number": float(np.max(expected_working_f_number)),
        "f_number_screening_limit": f_number_limit,
        "cases_below_f_number_4": int(np.sum(expected_working_f_number < f_number_limit)),
        "cases_passing_both_project_screens": int(
            np.sum(
                (expected_edge_angle_deg <= screening_limit)
                & (expected_working_f_number >= f_number_limit)
            )
        ),
    }

    source_quality = {
        "ppt_has_bibliographic_sources": False,
        "ppt_values_are_often_approximate": True,
        "wavelength_650_nm_present_in_ppt": False,
        "child_axial_range_is_model_assumption": "Model sensitivity assumption"
        in range_config["eyes"]["child_6y"]["axial_length_mm"]["provenance"],
        "adult_axial_range_is_model_assumption": "Model sensitivity assumption"
        in range_config["eyes"]["adult_18y"]["axial_length_mm"]["provenance"],
        "middle_focal_values_are_measured": False,
        "source_radiance_power_exposure_present": False,
        "anatomical_surface_prescription_complete": False,
    }

    blockers = [
        {
            "name": "真实解剖与主平面未标定",
            "reason": "当前把完整眼轴直接约化为薄透镜到后极距离；PPT 不足以唯一确定角膜、晶状体、主平面和视网膜曲率。",
        },
        {
            "name": "全部工况超出项目近轴角度筛查线",
            "reason": f"最大边缘光线角为 {applicability['minimum_maximum_ray_angle_deg']:.2f}°–{applicability['maximum_maximum_ray_angle_deg']:.2f}°；现有 Zemax 证据使用 Paraxial 面，不能量化真实高角度误差。",
        },
        {
            "name": "绝对辐射度和安全剂量缺失",
            "reason": "没有经校准的光谱辐亮度/功率、带宽、曝光时间、组织透射、热危害和光化学危害计算。",
        },
        {
            "name": "覆盖验收标准未定义",
            "reason": "几何支持域和全重叠平台不是实测最低照度、均匀性、信噪比或生物学终点。",
        },
        {
            "name": "伦理与操作控制未记录",
            "reason": "活体小鸡或人体实验需要机构审批、风险评估、硬件限幅/联锁、停止规则和受训人员确认。",
        },
    ]

    calculation_pass = arithmetic_pass and validation.get("overall_status") == "passed"
    report = {
        "schema_version": "1.0",
        "as_of_date": AS_OF_DATE,
        "experiment_id": config["experiment_id"],
        "question": "Are the calculated source sizes correct enough to guide real chick or human-eye experiments?",
        "calculation_validation_status": (
            "VERIFIED_WITHIN_FIRST_ORDER_MODEL" if calculation_pass else "CALCULATION_VALIDATION_FAILED"
        ),
        "real_experiment_readiness_status": "NOT_READY",
        "decision": "DO_NOT_USE_AS_FINAL_EXPOSURE_OR_SAFETY_SETTINGS",
        "independent_recalculation": arithmetic,
        "paraxial_applicability": applicability,
        "source_data_quality": source_quality,
        "opticstudio_validation_scope": {
            "version": validation.get("opticstudio_version"),
            "api_license_valid": validation.get("api_license_valid"),
            "case_count": validation.get("zos_case_count"),
            "maximum_boundary_error_um": validation.get("zos_bound_max_error_um"),
            "scope": "Paraxial equivalent-eye boundary agreement only",
            "does_not_establish": [
                "real-ray anatomical accuracy",
                "absolute retinal irradiance",
                "photobiological safety",
                "biological efficacy",
            ],
        },
        "real_experiment_blockers": blockers,
        "official_safety_references": [
            {
                "standard": "ISO 15004-2:2024",
                "scope": "Optical radiation safety for ophthalmic instruments directing radiation into or at the eye",
                "url": "https://www.iso.org/standard/79919.html",
            },
            {
                "standard": "IEC 62471:2006",
                "scope": "Photobiological safety of lamps and lamp systems, including LEDs and excluding lasers",
                "url": "https://webstore.iec.ch/en/publication/7076",
            },
            {
                "standard": "IEC 60825-1:2014",
                "scope": "Laser product classification and safety requirements",
                "url": "https://webstore.iec.ch/en/publication/3587",
            },
        ],
        "official_modeling_references": [
            {
                "title": "Paraxial and Parabasal Rays",
                "publisher": "Ansys",
                "url": "https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v252/en/OpticStudio_User_Guide/OpticStudio_Help/topics/Paraxial_and_Parabasal_Rays.html",
            },
            {
                "title": "Paraxial sequential surface",
                "publisher": "Ansys",
                "url": "https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v25101/en/OpticStudio_User_Guide/OpticStudio_Help/topics/Paraxial_sequential_surfaces_lens_data_editor.html",
            },
            {
                "title": "Exploring Non-Sequential Mode in OpticStudio",
                "publisher": "Ansys",
                "url": "https://optics.ansys.com/hc/en-us/articles/42661670424851-Exploring-Non-Sequential-Mode-in-OpticStudio",
            },
        ],
    }

    json_path = RESULTS / "real_experiment_readiness.json"
    markdown_path = RESULTS / "real_experiment_readiness.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if calculation_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
