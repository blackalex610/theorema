"""Pull the Part 2 items, and their official marking, out of the papers.

Part 2 is hand-authored because an 11-point proof is marked on intermediate
results, and inventing that mark allocation is the expensive half. The thirteen
papers already contain 39 of them, and the *otgovori* editions carry the
ministry's own breakdown -- so this is transcription, not invention.

    python scripts/extract_part2_items.py --paper nvo-7-klas-math-v2-otgovori-20.06.2025

Writes plain text to docs/nvo-figures/part2-source/<paper>.txt for reading.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pymupdf

NVOS = Path("C:/Users/pc/Desktop/matematika hristov/NVOS")
OUT = Path("docs/nvo-figures/part2-source")

# Part 2 opens with the instruction to write the answer out in full; the
# extended items are numbered from there to the end of the question section.
START = re.compile(r"(Задачи\s*(?:от|с)\s*.{0,40}свободен\s*отговор|"
                   r"запишете\s+(?:пълните\s+)?решени|"
                   r"Отговорите\s+на\s+задачи)", re.IGNORECASE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", required=True, help="PDF stem, without .pdf")
    ap.add_argument("--from-page", type=int, default=1)
    ap.add_argument("--to-page", type=int, default=0, help="0 = last")
    args = ap.parse_args()

    pdf = NVOS / f"{args.paper}.pdf"
    if not pdf.exists():
        print(f"no such paper: {pdf}", file=sys.stderr)
        return 2

    doc = pymupdf.open(pdf)
    last = args.to_page or doc.page_count
    chunks = []
    for pno in range(args.from_page - 1, min(last, doc.page_count)):
        text = doc[pno].get_text("text")
        chunks.append(f"\n{'=' * 70}\n=== page {pno + 1} ===\n{'=' * 70}\n{text}")
    doc.close()

    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{args.paper}.txt"
    dest.write_text("".join(chunks), encoding="utf-8")
    print(f"{len(chunks)} pages -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
