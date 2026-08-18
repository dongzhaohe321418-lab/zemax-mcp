# Experiment log

This index is intentionally concise. One immutable JSON file under `experiments/runs/` represents each milestone. Large binary artifacts under `experiments/artifacts/` are stored with Git LFS.

| Experiment | Date (UTC) | Backend | Objective | Status |
|---|---|---|---|---|
| eye-illumination-650nm-v1 | 2026-08-14 | Independent ABCD + OpticStudio 24.1 ZOS-API | Full posterior-pole source sizing, defocus/lens sensitivity, and cross-validation | Passed |
| eye-illumination-latex-report-v1 | 2026-08-14 | XeLaTeX + deterministic result generators | 29-page Chinese SimSun experiment report, data figures, optical/workflow diagrams, and automated PDF QA | Passed |
| eye-illumination-60-120d-v2 | 2026-08-14 | Independent ABCD + OpticStudio 24.1 ZOS-API + XeLaTeX | Replace the main object-demand sweep with 60–120 D in 10 D steps, retain a physical 10 D external-lens reference, and rebuild all reports | Passed |
| eye-illumination-fixed-focal-60-120d-v3 | 2026-08-14 | Fixed-parameter ABCD + OpticStudio 24.1 ZOS-API + XeLaTeX | Supersede continuous focal-length fitting with three fixed focal lengths per eye and size sources at a fixed posterior-pole plane across 252 cases | Passed |
| eye-illumination-ppt-range-explorer-v1 | 2026-08-18 | Independent-parameter ABCD + local Web application | Preserve the validated fixed-focal baseline while adding manual PPT-range exploration, sensitivity curves, constrained external lenses, range grids, and exports | Passed |

When adding a run, add one row here in the same commit. Do not rewrite prior experimental observations; add a superseding run instead.
