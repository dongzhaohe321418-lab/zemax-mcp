"""Create and execute the reader-facing reproducibility notebook."""

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
# 650 nm eye-illumination experiment

## tl;dr

This executed notebook reproduces the reduced-eye sweep, loads the real OpticStudio 24.1 cross-validation, and exposes the assumptions needed to interpret the source-size recommendations. The model is paraxial and radiometrically normalized; it does not establish retinal exposure safety.
        """),
        markdown("""
## Context & Methods

### Key Assumptions

- A rotationally symmetric effective thin eye lens represents each eye.
- Accommodation changes eye power while retinal position remains fixed.
- A uniform circular 650 nm source is imaged onto a circular posterior-pole target.
- External lens vertex distance is 5 mm for chick and 12 mm for human eyes.
- Absolute source flux, biological scattering, diffraction, aberrations, and exposure limits are not supplied by the source PPT and are not inferred.
        """),
        code("""
from pathlib import Path
import json
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Image

ROOT = Path.cwd()
if not (ROOT / 'config' / 'experiment.json').exists():
    ROOT = ROOT.parent
RESULTS = ROOT / 'results'
FIGURES = ROOT / 'figures'
config = json.loads((ROOT / 'config' / 'experiment.json').read_text(encoding='utf-8'))
validation = json.loads((RESULTS / 'validation_report.json').read_text(encoding='utf-8'))
config['experiment_id'], validation['overall_status']
        """),
        markdown("## Data"),
        code("""
headline = pd.read_csv(RESULTS / 'headline_results.csv')
focused = pd.read_csv(RESULTS / 'focused_source_sweep.csv')
defocus = pd.read_csv(RESULTS / 'defocus_pupil_sweep.csv')
axial = pd.read_csv(RESULTS / 'axial_length_sensitivity.csv')
zos = pd.read_csv(RESULTS / 'zemax' / 'zosapi_validation.csv')
display(headline)
        """),
        markdown("""
## Results

### Requested 60–120 D source-demand sweep

The main sweep now covers 60, 70, 80, 90, 100, 110, and 120 D without an external lens. At a fixed target angular field, the required physical source diameter decreases as object distance decreases. All requested demands exceed the supplied accommodation limits.
        """),
        code("display(Image(filename=str(FIGURES / 'source_diameter_vs_demand.png')))"),
        markdown("""
### External negative lenses consume accommodation reserve in a separate 10 D reference

The table and heatmap use the stated provisional vertex distances. A negative lens increases the positive accommodation required to focus the same physical source plane.
        """),
        code("display(Image(filename=str(FIGURES / 'adult_accommodation_heatmap.png')))"),
        markdown("""
### Defocus and pupil size jointly broaden retinal illumination

Blur-assisted geometric coverage is not equivalent to a useful focused image. Larger pupils increase the defocused footprint and reduce the source angular size needed for geometric coverage, but the optical result is less selective.
        """),
        code("display(Image(filename=str(FIGURES / 'defocus_blur_by_pupil.png')))"),
        markdown("""
### Real OpticStudio cross-validation

The ZOS-API validation uses OpticStudio's sequential paraxial surface and normalized real-ray batch tracing. It checks three baseline eyes, two negative-lens cases, and one deliberately unaccommodated case.
        """),
        code("""
display(zos[['case_id','accommodation_D','source_diameter_mm','mean_image_y_mm','rms_spread_um']])
display(Image(filename=str(FIGURES / 'zosapi_cross_validation.png')))
validation
        """),
        markdown("""
## Takeaways

- All focused ZOS-API cases place the source edge on the requested retinal edge to numerical precision.
- At 60 D, the required circular source diameter is about 5.95 mm for chick and 5.99 mm for either human model; at 120 D those diameters halve to about 2.98 mm and 2.99 mm.
- Every requested 60–120 D case exceeds the supplied accommodation limits for chick, child, and adult models.
- The external-lens comparison remains a separate 10 D reference because 90–120 D object distances are shorter than the provisional 12 mm human vertex distance.
- Negative external lenses rapidly reduce the set of focusable source distances.
- These are geometric/paraxial design results, not absolute irradiance or biological-safety results. A full anatomical/GRIN and measured-QLED model is the next validation layer.
        """),
    ]
    nbf.write(nb, NOTEBOOK_PATH)
    executed = NotebookClient(nb, timeout=180, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}}).execute()
    nbf.write(executed, NOTEBOOK_PATH)
    print(NOTEBOOK_PATH)


if __name__ == "__main__":
    build()
