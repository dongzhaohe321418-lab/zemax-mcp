"""Self-check the compiled report and render a contact sheet for visual QA."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent
PDF = HERE / "eye_illumination_experiment_report.pdf"
REPORT = HERE / "qa_report.json"
CONTACT = HERE / "qa_contact_sheet.png"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    doc = fitz.open(PDF)
    text = "\n".join(page.get_text() for page in doc)
    required = ["技术摘要", "ABCD", "OpticStudio", "蒙特卡洛", "可复现工作流", "限制、不确定性", "附录"]
    missing = [item for item in required if item not in text]
    image_count = sum(len(page.get_images(full=True)) for page in doc)
    fonts = sorted({font[3] for page in doc for font in page.get_fonts(full=True)})
    songti_fonts = [name for name in fonts if "SimSun" in name or "Song" in name]
    sparse_pages = [index + 1 for index, page in enumerate(doc) if len(page.get_text().strip()) < 30]
    checks = {
        "pdf": PDF.name,
        "page_count": doc.page_count,
        "embedded_raster_image_instances": image_count,
        "font_names": fonts,
        "songti_font_names": songti_fonts,
        "missing_required_text": missing,
        "sparse_pages": sparse_pages,
        "all_pages_a4": all(abs(page.rect.width / page.rect.height - 210 / 297) < 0.02 for page in doc),
        "status": "passed",
    }
    if doc.page_count < 15 or image_count < 5 or not songti_fonts or missing or not checks["all_pages_a4"]:
        checks["status"] = "failed"

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
    contact.save(CONTACT)
    checks["preview_pages"] = selected
    REPORT.write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if checks["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
