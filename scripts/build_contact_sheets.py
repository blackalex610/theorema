"""Compose the extracted figure crops into labelled contact sheets.

Classification reads pictures. Reading 209 of them one at a time is wasteful
when nine fit on a sheet that is still legible, so this tiles them and stamps
each cell with the index the classifier refers to it by.

    python scripts/build_contact_sheets.py

Writes docs/nvo-figures/sheets/sheet_NN.png plus sheet_index.json, which maps
every stamped index back to its crop, paper, page and item number.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COLS, ROWS = 3, 3
CELL_W, CELL_H = 470, 350
LABEL_H = 24
GAP = 8
BG = (255, 255, 255)
LABEL_BG = (232, 236, 242)
LABEL_FG = (20, 24, 32)
BORDER = (176, 184, 196)

ROOT = Path("docs/nvo-figures")
CROPS = ROOT / "crops"
SHEETS = ROOT / "sheets"


def load_font(size: int) -> ImageFont.ImageFont:
    for path in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fit(img: Image.Image, box_w: int, box_h: int) -> Image.Image:
    scale = min(box_w / img.width, box_h / img.height, 1.0)
    if scale < 1.0:
        img = img.resize((max(1, int(img.width * scale)),
                          max(1, int(img.height * scale))), Image.LANCZOS)
    return img


def main() -> int:
    entries = json.loads((ROOT / "inventory.json").read_text(encoding="utf-8"))
    figures = [e for e in entries if e["kind_hint"] == "figure"]
    figures.sort(key=lambda e: (e["paper"], e["page"], e["crop"]))

    SHEETS.mkdir(parents=True, exist_ok=True)
    for old in SHEETS.glob("sheet_*.png"):
        old.unlink()

    font = load_font(14)
    per_sheet = COLS * ROWS
    index: list[dict] = []

    sheet_w = COLS * CELL_W + (COLS + 1) * GAP
    sheet_h = ROWS * (CELL_H + LABEL_H) + (ROWS + 1) * GAP

    for s, start in enumerate(range(0, len(figures), per_sheet), start=1):
        chunk = figures[start:start + per_sheet]
        sheet = Image.new("RGB", (sheet_w, sheet_h), BG)
        draw = ImageDraw.Draw(sheet)

        for k, entry in enumerate(chunk):
            gi = start + k + 1                      # 1-based global index
            col, row = k % COLS, k // COLS
            x = GAP + col * (CELL_W + GAP)
            y = GAP + row * (CELL_H + LABEL_H + GAP)

            item = entry["item_no"]
            tag = (f"#{gi}  {entry['year'] or '?'}  "
                   f"p{entry['page']}" + (f"  item {item}" if item else ""))
            draw.rectangle([x, y, x + CELL_W, y + LABEL_H], fill=LABEL_BG)
            draw.text((x + 7, y + 4), tag, fill=LABEL_FG, font=font)
            draw.rectangle([x, y, x + CELL_W, y + LABEL_H + CELL_H],
                           outline=BORDER, width=1)

            img = Image.open(CROPS / entry["crop"]).convert("RGB")
            img = fit(img, CELL_W - 10, CELL_H - 10)
            ox = x + (CELL_W - img.width) // 2
            oy = y + LABEL_H + (CELL_H - img.height) // 2
            sheet.paste(img, (ox, oy))

            index.append({"i": gi, "sheet": s, "crop": entry["crop"],
                          "paper": entry["paper"], "year": entry["year"],
                          "page": entry["page"], "item_no": item,
                          "stem": entry["stem"][-200:]})

        sheet.save(SHEETS / f"sheet_{s:02d}.png")

    (ROOT / "sheet_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    sheets = (len(figures) + per_sheet - 1) // per_sheet
    print(f"{len(figures)} figures -> {sheets} sheets in {SHEETS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
