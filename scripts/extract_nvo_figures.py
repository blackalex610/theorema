"""Extract every figure from the official NVO papers into a crop catalogue.

Throwaway analysis tool for the figure-coverage audit. Not imported by the
server and deliberately absent from requirements.txt -- it needs pymupdf, which
is an analysis dependency, not a runtime one.

    python scripts/extract_nvo_figures.py --probe NVOS/nvo-math_7kl_18062021.pdf
    python scripts/extract_nvo_figures.py --all

A figure is a cluster of vector drawings (and/or embedded images) that sit close
enough together to be one picture. The hard part is not finding drawings -- it
is discarding the ones that are page furniture: header rules, table gridlines,
the frame around the whole page.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import pymupdf

# --- tuning constants -------------------------------------------------------
# Every one of these is a guess calibrated against the 2021 paper in --probe
# mode, then checked across the corpus. They are named rather than inlined so a
# recalibration is one edit.

DPI = 160                  # readable at a glance without huge PNGs
GUTTER = 14.0              # pt; two drawings this close belong to one figure
PAD = 8.0                  # pt of whitespace around a crop
MIN_SIDE = 16.0            # pt; a cluster smaller than this is a bullet or tick
MIN_AREA = 1400.0          # pt^2; discards stray marks that pass MIN_SIDE
RULE_ASPECT = 18.0         # w/h above this (or its inverse) is a rule, not art
FULL_PAGE_FRAC = 0.82      # a cluster covering this much of the page is a frame
STEM_LOOKBACK = 3          # text blocks above a figure to keep as its stem
STEM_CHARS = 420           # trim the stem to something readable

ITEM_NO = re.compile(r"(?:^|\n)\s*(\d{1,2})\s*[.)]\s+")
YEAR = re.compile(r"(20\d{2})")

# The *otgovori* papers bundle their marking scheme, which is drawn as a table
# and is therefore indistinguishable from a figure to the clusterer. It is not a
# figure and must not reach classification. Its giveaway is the points column.
MARKING = re.compile(r"Общ\s+брой\s+точки|точки,\s*от\s+които|Критерии|т\.\s*за\b")


@dataclass
class Entry:
    crop: str
    paper: str
    year: int | None
    page: int
    bbox: list[float]
    item_no: int | None
    stem: str
    detection: str
    has_key: bool
    kind_hint: str


def rects_overlap(a: pymupdf.Rect, b: pymupdf.Rect, gutter: float) -> bool:
    grown = pymupdf.Rect(a.x0 - gutter, a.y0 - gutter, a.x1 + gutter, a.y1 + gutter)
    return bool(grown & b) and not (grown & b).is_empty


def cluster(rects: list[pymupdf.Rect], gutter: float) -> list[pymupdf.Rect]:
    """Merge rects transitively until nothing else touches."""
    out = [pymupdf.Rect(r) for r in rects]
    merged = True
    while merged:
        merged = False
        for i in range(len(out)):
            for j in range(len(out) - 1, i, -1):
                if rects_overlap(out[i], out[j], gutter):
                    out[i] |= out[j]
                    del out[j]
                    merged = True
    return out


def is_furniture(r: pymupdf.Rect, page_rect: pymupdf.Rect) -> str | None:
    """Return a reason to discard this cluster, or None to keep it."""
    w, h = r.width, r.height
    if w < MIN_SIDE or h < MIN_SIDE:
        return "too small"
    if w * h < MIN_AREA:
        return "too thin"
    if h > 0 and (w / h > RULE_ASPECT or h / w > RULE_ASPECT):
        return "rule"
    page_area = page_rect.width * page_rect.height
    if page_area and (w * h) / page_area > FULL_PAGE_FRAC:
        return "page frame"
    return None


def drawing_rects(page: pymupdf.Page) -> list[pymupdf.Rect]:
    rects: list[pymupdf.Rect] = []
    for d in page.get_drawings():
        r = d.get("rect")
        if r is not None and not r.is_empty and r.is_valid:
            rects.append(pymupdf.Rect(r))
    for info in page.get_images(full=True):
        try:
            for r in page.get_image_rects(info[0]):
                rects.append(pymupdf.Rect(r))
        except Exception:
            pass
    return rects


def stem_for(page: pymupdf.Page, box: pymupdf.Rect) -> tuple[str, int | None]:
    """The nearest text above a figure, plus the item number if one is in it."""
    blocks = [b for b in page.get_text("blocks") if b[6] == 0]
    above = [b for b in blocks if b[3] <= box.y0 + 4]
    above.sort(key=lambda b: b[3])
    chosen = above[-STEM_LOOKBACK:]
    text = " ".join(b[4].replace("\n", " ") for b in chosen).strip()
    text = re.sub(r"\s+", " ", text)

    item_no = None
    for b in reversed(chosen):
        m = ITEM_NO.search("\n" + b[4])
        if m:
            item_no = int(m.group(1))
            break
    return text[-STEM_CHARS:], item_no


def extract_pdf(pdf: Path, out_dir: Path, *, probe: bool = False) -> list[Entry]:
    doc = pymupdf.open(pdf)
    slug = pdf.stem
    ym = YEAR.search(pdf.stem)
    year = int(ym.group(1)) if ym else None
    has_key = "otgovori" in pdf.stem.lower()

    entries: list[Entry] = []
    stats = {"pages": 0, "raw": 0, "kept": 0}
    discards: dict[str, int] = {}

    for pno in range(doc.page_count):
        page = doc[pno]
        stats["pages"] += 1
        raw = drawing_rects(page)
        stats["raw"] += len(raw)
        if not raw:
            continue

        for n, box in enumerate(cluster(raw, GUTTER), start=1):
            reason = is_furniture(box, page.rect)
            if reason:
                discards[reason] = discards.get(reason, 0) + 1
                continue
            inner = page.get_text("text", clip=box)
            kind_hint = "marking_table" if MARKING.search(inner) else "figure"
            if kind_hint == "marking_table":
                discards["marking table"] = discards.get("marking table", 0) + 1

            stats["kept"] += 1
            clip = pymupdf.Rect(box.x0 - PAD, box.y0 - PAD, box.x1 + PAD, box.y1 + PAD) & page.rect
            name = f"{slug}_p{pno + 1:02d}_{n}.png"
            if not probe:
                pix = page.get_pixmap(clip=clip, dpi=DPI)
                pix.save(out_dir / name)
            stem, item_no = stem_for(page, box)
            entries.append(Entry(
                crop=name, paper=slug, year=year, page=pno + 1,
                bbox=[round(v, 1) for v in (box.x0, box.y0, box.x1, box.y1)],
                item_no=item_no, stem=stem, detection="vector", has_key=has_key,
                kind_hint=kind_hint,
            ))

    label = "PROBE" if probe else "     "
    print(f"{label} {pdf.name:<48} pages={stats['pages']:>3} "
          f"raw={stats['raw']:>5} kept={stats['kept']:>4} "
          f"discarded={dict(sorted(discards.items()))}")
    doc.close()
    return entries


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nvos", default=None, help="directory holding the PDFs")
    ap.add_argument("--out", default="docs/nvo-figures")
    ap.add_argument("--probe", nargs="*", help="report counts only, write nothing")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out)
    crops = out_dir / "crops"

    if args.probe is not None and not args.all:
        targets = [Path(p) for p in args.probe]
        for pdf in targets:
            extract_pdf(pdf, crops, probe=True)
        return 0

    nvos = Path(args.nvos) if args.nvos else None
    if nvos is None or not nvos.is_dir():
        print(f"--nvos must point at the directory of papers (got {nvos})", file=sys.stderr)
        return 2

    crops.mkdir(parents=True, exist_ok=True)
    all_entries: list[Entry] = []
    for pdf in sorted(nvos.glob("*.pdf")):
        all_entries.extend(extract_pdf(pdf, crops))

    inventory = out_dir / "inventory.json"
    inventory.write_text(
        json.dumps([asdict(e) for e in all_entries], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    figures = [e for e in all_entries if e.kind_hint == "figure"]
    tables = len(all_entries) - len(figures)
    print(f"\n{len(all_entries)} clusters -> {crops}")
    print(f"  {len(figures)} figures to classify")
    print(f"  {tables} marking tables tagged out")
    print(f"inventory -> {inventory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
