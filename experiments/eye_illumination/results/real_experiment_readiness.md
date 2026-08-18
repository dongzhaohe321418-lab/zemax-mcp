# 真实实验适用性验证报告

生成日期：2026-08-18

计算状态：**VERIFIED_WITHIN_FIRST_ORDER_MODEL**

真实实验状态：**NOT_READY**

## 结论

当前 252 个结果已经在同一近轴等效眼契约内完成独立重算，并通过既有 OpticStudio Paraxial 交叉验证；这说明代码、单位和一阶公式彼此一致。**它们仍不能直接作为小鸡或人体眼部照明的最终光源尺寸、功率或曝光处方。**

最主要的定量原因是：保守源边缘到瞳孔边缘的最大光线角在全部 252 个工况中均超过项目设置的 10° 近轴筛查线；实际范围为 15.02°–37.59°。另有 140 个工况的工作 F 数低于 4。因而 OpticStudio 的 Paraxial 一致性验证不能替代真实曲面、真实折射和辐射度验证。

## 独立复算结果

| 检查 | 结果 |
|---|---:|
| 主矩阵行数 | 252 |
| 复合主键重复行 | 0 |
| 缺失数值 | 0 |
| 物距公式最大差值 | 4.286e-09 mm |
| 源映射系数最大差值 | 4.790e-10 |
| 瞳孔映射系数最大差值 | 4.895e-10 |
| 保守直径最大差值 | 4.591e-09 mm |
| 面积公式最大差值 | 4.956e-09 mm² |

## 已验证与未验证的边界

- **已验证**：配置水平、252 行矩阵完整性、无重复工况、单位换算、ABCD 闭式公式、覆盖恒等式、确定性蒙特卡洛复现，以及 OpticStudio Paraxial 边界一致性。
- **未验证**：真实眼主平面、角膜/晶状体多曲面和梯度折射率、视网膜曲率、像差、散射、透射、真实光源角分布、绝对辐照度、温升、光化学风险、个体差异和生物学终点。
- **数据来源限制**：PPT 使用大量近似值且未附原始文献；650 nm 不在 PPT 中；儿童和成人眼轴范围是灵敏度假设；每种眼的中间焦距是区间算术中点，不是实测值。

## 阻止直接进入真实实验的条件

1. **真实解剖与主平面未标定**：当前把完整眼轴直接约化为薄透镜到后极距离；PPT 不足以唯一确定角膜、晶状体、主平面和视网膜曲率。
2. **全部工况超出项目近轴角度筛查线**：最大边缘光线角为 15.02°–37.59°；现有 Zemax 证据使用 Paraxial 面，不能量化真实高角度误差。
3. **绝对辐射度和安全剂量缺失**：没有经校准的光谱辐亮度/功率、带宽、曝光时间、组织透射、热危害和光化学危害计算。
4. **覆盖验收标准未定义**：几何支持域和全重叠平台不是实测最低照度、均匀性、信噪比或生物学终点。
5. **伦理与操作控制未记录**：活体小鸡或人体实验需要机构审批、风险评估、硬件限幅/联锁、停止规则和受训人员确认。

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
