# Experiment log

This index is intentionally concise. One immutable JSON file under `experiments/runs/` represents each milestone. Large binary artifacts under `experiments/artifacts/` are stored with Git LFS.

| Experiment | Date (UTC) | Backend | Objective | Status |
|---|---|---|---|---|
| eye-illumination-650nm-v1 | 2026-08-14 | Independent ABCD + OpticStudio 24.1 ZOS-API | Full posterior-pole source sizing, defocus/lens sensitivity, and cross-validation | Passed |
| eye-illumination-latex-report-v1 | 2026-08-14 | XeLaTeX + deterministic result generators | 29-page Chinese SimSun experiment report, data figures, optical/workflow diagrams, and automated PDF QA | Passed |
| eye-illumination-60-120d-v2 | 2026-08-14 | Independent ABCD + OpticStudio 24.1 ZOS-API + XeLaTeX | Replace the main object-demand sweep with 60–120 D in 10 D steps, retain a physical 10 D external-lens reference, and rebuild all reports | Passed |

When adding a run, add one row here in the same commit. Do not rewrite prior experimental observations; add a superseding run instead.
