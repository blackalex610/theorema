"""Wrong answers, and how the real papers build them.

The distractors in an official NVO paper are not random numbers near the key —
they are the specific mistakes a 7th-grader makes. Reading all thirteen papers,
every wrong option falls into one of eight families:

  sign flip                dropped a minus                    2026 Q1, 2021 Q3
  arrested computation     stopped one step early             2026 Q7, 2024 Q17
  bracket permutation      wrong strictness/direction         2026 Q4, 2023 Q5,
                           (all four options are variants)     2022 Q5, 2021 Q5
  supplement / complement  gave 180−x or 90−x                 2023 Q11, 2024 Q10
  wrong angle in figure    read a different marked angle      2026 Q11, 2021 Q10
  reciprocal               flipped a ratio or probability     2024 Q20, 2026 Q6
  factor-sign permutation  right factors, wrong signs         2025 Q3, 2022 Q3
  off by a factor          doubled, halved, unit slip         2022 Q18, 2021 Q18

Getting these right is most of what makes a generated paper feel authentic
rather than synthetic — a student who picks a distractor should be able to see
what they did wrong.

Everything here works in exact arithmetic (``Fraction``), never floats, so a
distractor can never coincide with the key through rounding.
"""
from __future__ import annotations

import random
from fractions import Fraction
from typing import Callable, Iterable, Sequence

from app.nvo_gen.registry import Retry

Num = int | Fraction

#: The four option letters. Cyrillic, not Latin — a Latin "B" beside a Cyrillic
#: "В" is the single most common way a generated paper gives itself away.
OPTION_LETTERS: tuple[str, str, str, str] = ("А", "Б", "В", "Г")


# ─── Bulgarian number formatting ─────────────────────────────────────────────

def bg_number(value: Num, *, math_mode: bool = True) -> str:
    """Format a number the way a Bulgarian exam prints it.

    Decimal comma, not a point. In math mode the comma is wrapped as ``{,}`` so
    KaTeX sets it tight against the digits instead of adding the wide space it
    puts after a punctuation comma.
    """
    if isinstance(value, Fraction):
        if value.denominator == 1:
            value = value.numerator
        else:
            sign = "-" if value < 0 else ""
            a = abs(value)
            return rf"{sign}\frac{{{a.numerator}}}{{{a.denominator}}}"
    if isinstance(value, int):
        return str(value)
    text = f"{value:g}"
    if "." in text:
        whole, frac = text.split(".")
        return f"{whole}{{,}}{frac}" if math_mode else f"{whole},{frac}"
    return text


def is_clean_decimal(value: Fraction, *, places: int = 2) -> bool:
    """True when `value` terminates within `places` decimal digits.

    ``denominator <= 100`` is NOT the same test and is the trap: 5/3 has
    denominator 3 and passes it, but prints as 1,666… . What matters is that
    the denominator divides 10**places.
    """
    return (10 ** places) % value.denominator == 0


def bg_decimal(value: Fraction | float, *, places: int = 2, math_mode: bool = True) -> str:
    """A decimal with a Bulgarian comma and trailing zeros trimmed."""
    text = f"{float(value):.{places}f}".rstrip("0").rstrip(".")
    if "." in text:
        whole, frac = text.split(".")
        return f"{whole}{{,}}{frac}" if math_mode else f"{whole},{frac}"
    return text


# ─── the eight families ──────────────────────────────────────────────────────

def sign_flip(value: Num) -> Num:
    """Dropped a minus somewhere in the chain."""
    return -value


def supplement(degrees: Num) -> Num:
    """Gave the angle's supplement — 180° − x."""
    return 180 - degrees


def complement(degrees: Num) -> Num:
    """Gave the angle's complement — 90° − x."""
    return 90 - degrees


def doubled(value: Num) -> Num:
    return value * 2


def halved(value: Num) -> Num:
    return Fraction(value, 2) if isinstance(value, int) else value / 2


def reciprocal(value: Fraction) -> Fraction:
    """Flipped a ratio or a probability."""
    return Fraction(value.denominator, value.numerator) if value else value


def complement_probability(p: Fraction) -> Fraction:
    """Answered the opposite event — 1 − p."""
    return 1 - p


def off_by_factor(value: Num, factor: int) -> Num:
    """A unit slip: cm↔dm↔m, or a forgotten ×10."""
    return value * factor


def interval_variants(bound: str, *, direction: str, closed: bool) -> list[str]:
    """The four bracket forms of a one-sided interval.

    2026 Q4, 2023 Q5, 2022 Q5 and 2021 Q5 all do exactly this: every option is
    the same bound, and the only thing under test is whether the student got
    the direction and the strictness right. Returns the correct form first.

    `direction` is "le"/"lt" (x below the bound) or "ge"/"gt" (x above it).
    """
    up_closed = rf"\left[{bound};+\infty\right)"
    up_open = rf"\left({bound};+\infty\right)"
    down_closed = rf"\left(-\infty;{bound}\right]"
    down_open = rf"\left(-\infty;{bound}\right)"

    if direction in ("ge", "gt"):
        correct = up_closed if closed else up_open
        others = [up_open if closed else up_closed, down_closed, down_open]
    else:
        correct = down_closed if closed else down_open
        others = [down_open if closed else down_closed, up_closed, up_open]
    return [correct, *others]


def factor_sign_variants(a: str, b: str) -> list[str]:
    """(x−a)(x−b) and its three sign permutations, correct form first.

    Used wherever the stem is "разложете на множители" — 2025 Q3, 2024 Q3,
    2022 Q3, 2019 Q4 all present exactly this menu.
    """
    return [
        rf"\left({a}\right)\left({b}\right)",
        rf"\left({_flip_sign(a)}\right)\left({b}\right)",
        rf"\left({a}\right)\left({_flip_sign(b)}\right)",
        rf"\left({_flip_sign(a)}\right)\left({_flip_sign(b)}\right)",
    ]


def _flip_sign(term: str) -> str:
    if "+" in term:
        return term.replace("+", "-", 1)
    if "-" in term:
        return term.replace("-", "+", 1)
    return term


# ─── assembling an option set ────────────────────────────────────────────────

class DistractorError(Retry):
    """This draw cannot produce four distinct plausible options.

    Subclasses Retry so the assembler resamples the template instead of
    treating it as a bug — a pool that happens to collapse for one draw
    (two candidates colliding, a third rejected as implausible) is normal.
    """


def _is_implausible(value: Num, *, positive_only: bool, key: Num) -> bool:
    """Reject options that give the answer away by looking obviously wrong.

    A negative length among three positive ones, or a value two orders of
    magnitude off, is not a distractor — it is a free elimination. The real
    papers never do this.
    """
    if positive_only and value <= 0:
        return True
    if value == 0 and key != 0:
        return False  # zero is a legitimate trap in arithmetic items
    if key != 0 and value != 0:
        ratio = abs(Fraction(value) / Fraction(key))
        if ratio > 50 or ratio < Fraction(1, 50):
            return True
    return False


def numeric_options(
    key: Num,
    candidates: Sequence[Num],
    *,
    rng: random.Random,
    fmt: Callable[[Num], str] = bg_number,
    positive_only: bool = False,
    suffix: str = "",
    math: bool = True,
) -> tuple[list[str], str]:
    """Build four shuffled options from a key and a pool of wrong values.

    Returns ``(options, correct_letter)``. Options are rendered strings in the
    order they will be shown; the letter is the Cyrillic label of the key.

    More candidates than needed is normal and good — the caller offers every
    family that applies and this picks three that survive the plausibility
    filter and are distinct from each other and from the key.
    """
    seen = {_render(key, fmt, suffix, math)}
    wrongs: list[str] = []
    for cand in candidates:
        if len(wrongs) == 3:
            break
        if cand == key or _is_implausible(cand, positive_only=positive_only, key=key):
            continue
        text = _render(cand, fmt, suffix, math)
        if text in seen:
            continue
        seen.add(text)
        wrongs.append(text)

    if len(wrongs) < 3:
        raise DistractorError(
            f"only {len(wrongs)} usable distractors for key {key!r} from {len(candidates)} candidates"
        )

    return shuffle_options(_render(key, fmt, suffix, math), wrongs, rng=rng)


def _render(value: Num, fmt: Callable[[Num], str], suffix: str, math: bool) -> str:
    body = fmt(value)
    if math:
        return f"${body}$" + (f" {suffix}" if suffix else "")
    return f"{body}{(' ' + suffix) if suffix else ''}"


def shuffle_options(correct: str, wrongs: Sequence[str], *, rng: random.Random) -> tuple[list[str], str]:
    """Place the key at a random one of the four positions.

    Answer letters across a whole paper are balanced later, at assembly time —
    per-item randomness alone drifts far enough to be noticeable (2022 ran 8 of
    18 on Б).
    """
    options = list(wrongs[:3])
    slot = rng.randrange(4)
    options.insert(slot, correct)
    return options, OPTION_LETTERS[slot]


def reletter(options: Sequence[str], correct_index: int, target_index: int) -> tuple[list[str], str]:
    """Move the key to a chosen position, keeping the other options' order.

    Used by the assembler to even out the А/Б/В/Г distribution across a paper
    without regenerating any item.
    """
    rest = [opt for i, opt in enumerate(options) if i != correct_index]
    out = list(rest)
    out.insert(target_index, options[correct_index])
    return out, OPTION_LETTERS[target_index]


def angle_options(key_deg: Num, extras: Iterable[Num] = (), *, rng: random.Random) -> tuple[list[str], str]:
    """Option set for an angle-chase item, in degrees.

    Offers the supplement, the complement, the double and the half — the four
    mistakes that actually occur — plus anything the template knows is readable
    off its own figure, which is the strongest distractor of all.
    """
    pool: list[Num] = [*extras, supplement(key_deg), doubled(key_deg), halved(key_deg),
                       complement(key_deg), 180 - doubled(key_deg)]
    usable = [v for v in pool if isinstance(v, int) or (isinstance(v, Fraction) and v.denominator == 1)]
    usable = [int(v) for v in usable if 0 < int(v) < 180]
    return numeric_options(int(key_deg), usable, rng=rng, positive_only=True,
                           fmt=lambda v: f"{v}^\\circ")
