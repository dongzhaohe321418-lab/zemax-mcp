"""Self-check both compiled reports and render language-specific contact sheets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent
REPORT = HERE / "qa_report.json"
SPECS = {
    "zh-CN": {
        "pdf": HERE / "eye_illumination_experiment_report.pdf",
        "contact": HERE / "qa_contact_sheet.png",
        "required": ["技术摘要", "ABCD", "OpticStudio", "蒙特卡洛", "可复现工作流", "限制、不确定性", "真实实验状态", "附录"],
        "font_tokens": ("SimSun", "Song"),
    },
    "en": {
        "pdf": HERE / "eye_illumination_experiment_report_en.pdf",
        "contact": HERE / "qa_contact_sheet_en.png",
        "required": ["Technical summary", "ABCD", "OpticStudio", "Monte Carlo", "reproducible workflow", "Limitations", "NOT READY", "Appendix"],
        "font_tokens": ("Times",),
    },
}


def contact_sheet(doc: fitz.Document, target: Path) -> list[int]:
    selected = sorted({0, doc.page_count // 4, doc.page_count // 2, 3 * doc.page_count // 4, doc.page_count - 1})
    previews = []
    for index in selected:
        pix = doc[index].get_pixmap(matrix=fitz.Matrix(0.75, 0.75), alpha=False)
        previews.append((index + 1, Image.frombytes("RGB", (pix.width, pix.height), pix.samples)))
    width = max(image.width for _, image in previews)
    label_height = 30
    contact = Image.new("RGB", (width * len(previews), previews[0][1].height + label_height), "white")
    draw = ImageDraw.Draw(contact)
    for column, (page_number, image) in enumerate(previews):
        x = column * width
        contact.paste(image, (x, label_height))
        draw.text((x + 8, 8), f"Page {page_number}", fill="black")
    contact.save(target)
    return [index + 1 for index in selected]


def inspect(language: str, spec: dict) -> dict:
    pdf = spec["pdf"]
    doc = fitz.open(pdf)
    text = "\n".join(page.get_text() for page in doc)
    fonts = sorted({font[3] for page in doc for font in page.get_fonts(full=True)})
    expected_fonts = [name for name in fonts if any(token in name for token in spec["font_tokens"])]
    checks = {
        "language": language,
        "pdf": pdf.name,
        "page_count": doc.page_count,
        "embedded_raster_image_instances": sum(len(page.get_images(full=True)) for page in doc),
        "font_names": fonts,
        "expected_font_names": expected_fonts,
        "missing_required_text": [item for item in spec["required"] if item not in text],
        "sparse_pages": [index + 1 for index, page in enumerate(doc) if len(page.get_text().strip()) < 30],
        "all_pages_a4": all(abs(page.rect.width / page.rect.height - 210 / 297) < 0.02 for page in doc),
        "status": "passed",
    }
    checks["preview_pages"] = contact_sheet(doc, spec["contact"])
    if (
        doc.page_count < 15
        or checks["embedded_raster_image_instances"] < 5
        or not expected_fonts
        or checks["missing_required_text"]
        or not checks["all_pages_a4"]
    ):
        checks["status"] = "failed"
    return checks


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    reports = {language: inspect(language, spec) for language, spec in SPECS.items()}
    result = {
        "status": "passed" if all(item["status"] == "passed" for item in reports.values()) else "failed",
        "reports": reports,
    }
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
