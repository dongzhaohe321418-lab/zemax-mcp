"""Create and execute the reader-facing fixed-focal reproducibility notebook."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient


ROOT = Path(__file__).resolve().parent
NOTEBOOK_DIR = ROOT / "notebooks"
NOTEBOOK_PATH = NOTEBOOK_DIR / "eye_illumination_analysis.ipynb"


def code(source: str):
    return nbf.v4.new_code_cell(source.strip())


def markdown(source: str):
    return nbf.v4.new_markdown_cell(source.strip())


def build() -> None:
    NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)
    nb = nbf.v4.new_notebook()
    nb["metadata"]["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nb["cells"] = [
        markdown("""
# 650 nm fixed-focal eye-illumination experiment

## tl;dr

This executed notebook sizes a circular source for 60–120 D object-side requirements while holding the retina plane fixed and using only three discrete focal lengths per eye. It does not continuously alter focal length to force focus. The arithmetic is verified within the first-order model, but the real-experiment readiness audit is **NOT READY** because anatomy, real-ray behavior, calibrated radiometry, safety, and ethics evidence are incomplete.
        """),
        markdown("""
## Context & Methods

- Chick fixed focal lengths: 7.5, 8.0, 8.5 mm.
- Child fixed focal lengths: 13.5, 15.1, 16.7 mm.
- Adult fixed focal lengths: 12.8, 14.75, 16.7 mm.
- The reduced retina distance is the reported axial length divided by 1.336.
- Every row is one eye × focal length × pupil × object distance; no accommodation feasibility test is used.
- The geometric minimum only makes the outer footprint reach the posterior-pole edge. The conservative diameter makes the full-overlap plateau cover the complete posterior-pole disk.
        """),
        code("""
from pathlib import Path
import json
import pandas as pd
from IPython.display import display, Image

ROOT = Path.cwd()
if not (ROOT / 'config' / 'experiment.json').exists():
    ROOT = ROOT.parent
RESULTS = ROOT / 'results'
FIGURES = ROOT / 'figures'
config = json.loads((ROOT / 'config' / 'experiment.json').read_text(encoding='utf-8'))
validation = json.loads((RESULTS / 'validation_report.json').read_text(encoding='utf-8'))
readiness = json.loads((RESULTS / 'real_experiment_readiness.json').read_text(encoding='utf-8'))
config['experiment_id'], validation['overall_status'], readiness['real_experiment_readiness_status']
        """),
        markdown("## Data"),
        code("""
headline = pd.read_csv(RESULTS / 'headline_results.csv')
fixed = pd.read_csv(RESULTS / 'fixed_focal_source_sweep.csv')
defocus = pd.read_csv(RESULTS / 'defocus_pupil_sweep.csv')
axial = pd.read_csv(RESULTS / 'axial_length_sensitivity.csv')
zos = pd.read_csv(RESULTS / 'zemax' / 'zosapi_validation.csv')
display(headline.head(12))
display(fixed.groupby('eye_id').size().rename('rows'))
        """),
        markdown("""
## Fixed focal lengths change the source-size answer

The plotted recommendation is the conservative source diameter at each eye's largest configured pupil. Each panel contains exactly three focal-length curves. The curves differ because object distance, fixed power, pupil blur, and the fixed posterior-pole plane jointly determine the retinal footprint.
        """),
        code("display(Image(filename=str(FIGURES / 'source_diameter_vs_demand.png')))"),
        markdown("""
## Pupil diameter remains an explicit design input

With a fixed focal length the retinal footprint is generally defocused, so pupil diameter is no longer irrelevant. The adult endpoint comparison shows how the recommended conservative source diameter changes with pupil size and the selected fixed focal length.
        """),
        code("display(Image(filename=str(FIGURES / 'fixed_focal_pupil_comparison.png')))"),
        markdown("""
## Geometric coverage and conservative coverage are different

The geometric minimum can have severe edge roll-off. The conservative full-overlap design is larger but keeps the target inside the convolution plateau. The Monte Carlo maps use 600,000 deterministic rays per case.
        """),
        code("display(Image(filename=str(FIGURES / 'retinal_irradiance_monte_carlo.png')))"),
        markdown("""
## Real OpticStudio cross-validation

Six fixed-focal systems were built through ZOS-API. Four corner rays per system verify the analytical source/pupil footprint bounds at the reduced retina plane.
        """),
        code("""
display(zos[['case_id','fixed_focal_length_mm','source_distance_mm','pupil_diameter_mm','conservative_source_diameter_mm','bound_error_um']])
display(Image(filename=str(FIGURES / 'zosapi_cross_validation.png')))
validation
        """),
        markdown("""
## Real-experiment applicability screen

The OpticStudio evidence above uses an ideal Paraxial surface, so agreement at numerical round-off establishes implementation consistency only. The independent screen recomputes the extreme conservative-source-edge to pupil-edge angle and the working F-number for all 252 cases. Passing a screen would still require an anatomical real-ray model and calibrated bench evidence; failing it blocks promotion of the paraxial value to a physical-eye setting.
        """),
        code("""
applicability = readiness['paraxial_applicability']
display(pd.DataFrame([{
    'cases': applicability['case_count'],
    'minimum edge angle (deg)': applicability['minimum_maximum_ray_angle_deg'],
    'median edge angle (deg)': applicability['median_maximum_ray_angle_deg'],
    'maximum edge angle (deg)': applicability['maximum_maximum_ray_angle_deg'],
    'cases above 10 deg': applicability['cases_above_screening_angle'],
    'cases below F/4': applicability['cases_below_f_number_4'],
    'cases passing both screens': applicability['cases_passing_both_project_screens'],
}]))
readiness['calculation_validation_status'], readiness['decision']
        """),
        markdown("""
## Takeaways

- The primary matrix contains 252 fixed-focal rows: 3 eyes × 3 focal lengths × 4 pupils × 7 object distances.
- No row changes the assigned focal length to satisfy the object-side requirement.
- The conservative source diameter is a first-order mechanical candidate, not a final experimental or exposure setting.
- Some geometric minima become zero when pupil-driven defocus alone reaches the target; this does not mean a zero-area practical emitter is recommended.
- All 252 cases exceed the project's 10-degree paraxial angle screen; 140 cases are faster than F/4. A measured anatomical real-ray model is required.
- These are paraxial geometric results, not absolute retinal irradiance, biological efficacy, or optical-safety results.
        """),
    ]
    nbf.write(nb, NOTEBOOK_PATH)
    executed = NotebookClient(nb, timeout=180, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}}).execute()
    nbf.write(executed, NOTEBOOK_PATH)
    print(NOTEBOOK_PATH)


if __name__ == "__main__":
    build()
