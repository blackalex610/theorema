"""Grading a written NVO answer the way the official key does.

Three things the submit endpoint used to get wrong, each of which moves a
student's score away from what the same paper would earn at the real exam:

  * **Every question counted one point.** The 2026 paper is 65 + 35: fourteen
    multiple-choice items worth 2–3 each, seven short answers worth 4–5, and
    three extended items worth 12, 11 and 12. Counted one-per-question, the
    three Part 2 items were 3/24 = 12,5% of the score instead of 35%.
  * **No partial credit.** The keys mark per sub-part — 2026 Q17 is „А) 2 т.,
    Б) 3 т.” — and a question was either wholly right or wholly wrong.
  * **Every short answer went to the language model**, including „2026” and
    „0 и 25”. Without an API key the model call raised 503 and the student
    could not submit the paper at all.

So: each sub-part is checked on its own and earns its own points. A key that
is a number, a set of numbers, a time or a monomial like „5x” is compared
exactly, here, for free. Only what cannot be compared mechanically — a proof,
a worded justification — goes to the model, together with the item's marking
scheme, which it was never shown before.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Sequence

#: (is_correct, extracted_answer, feedback)
AiGrade = Callable[..., tuple[bool, str, str]]

# Cyrillic х is what a student types for x on a Bulgarian keyboard. (Cyrillic у
# is not mapped to y: it would turn „август” into „авгyст”.)
_MINUS = str.maketrans({"−": "-", "–": "-", "—": "-", "х": "x", "Х": "x"})
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)?(?:/\d+)?")
_FRAC_TEX = re.compile(r"\\d?frac\{(-?\d+)\}\{(\d+)\}")
#: Answer forms a machine should not judge: proofs, verdicts on roots, reasons.
_NEEDS_JUDGEMENT = re.compile(
    r"доказ|≅|∥|признак|е решение|не е|равнобедрен|успоредник|ромб|извод|значи|"
    r"няма|еквивалент|->|=>|;.*;", re.IGNORECASE)
_MONTHS = ["януари", "февруари", "март", "април", "май", "юни", "юли", "август",
           "септември", "октомври", "ноември", "декември"]
_ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"]


def _clean(text: str) -> str:
    text = (text or "").translate(_MINUS)
    text = _FRAC_TEX.sub(r"\1/\2", text)
    text = text.replace("{,}", ",").replace("$", "").replace("\\,", " ")
    return text.strip().lower()


def _numbers(text: str) -> list[Fraction]:
    out = []
    for tok in _NUMBER.findall(text):
        tok = tok.replace(",", ".")
        if "/" in tok:
            num, den = tok.split("/")
            if int(den) == 0:
                continue
            out.append(Fraction(Fraction(num), int(den)))
        else:
            out.append(Fraction(tok))
    return out


def _month(text: str) -> int | None:
    t = text.strip().strip(".").lower()
    for i, name in enumerate(_MONTHS):
        if t == name or t.startswith(name):
            return i + 1
    if t in _ROMAN:
        return _ROMAN.index(t) + 1
    if t.isdigit() and 1 <= int(t) <= 12:
        return int(t)
    return None


_REL = re.compile(r"(<=|>=|≤|≥|<|>)\s*(-?\d+(?:[.,]\d+)?(?:/\d+)?)")
_REL_NORM = {"<=": "≤", ">=": "≥"}


def _relation(text: str) -> tuple[str, Fraction] | None:
    m = _REL.search(text)
    if m:
        return _REL_NORM.get(m.group(1), m.group(1)), _numbers(m.group(2))[0]
    # interval forms: (-∞; 5/6], [2; +∞)
    m = re.search(r"([(\[])\s*-\s*∞\s*;\s*(-?[\d.,/]+)\s*([)\]])", text)
    if m:
        return ("≤" if m.group(3) == "]" else "<"), _numbers(m.group(2))[0]
    m = re.search(r"([(\[])\s*(-?[\d.,/]+)\s*;\s*\+?\s*∞\s*\)", text)
    if m:
        return ("≥" if m.group(1) == "[" else ">"), _numbers(m.group(2))[0]
    return None


# Only the letters the papers use as unknowns — „16 h” and „35,91 L” are a time
# and a volume, not 16·h and 35,91·L.
_MONOMIAL = re.compile(r"^(-?\d*(?:[.,]\d+)?)\s*\*?\s*([xyabn])$")


def match_answer(student: str, expected: str) -> bool | None:
    """True when `student` certainly gives `expected`, False when it certainly
    does not, None when only a reader can tell.

    Deliberately lenient about *form* — units, word order, „x₁ = 0, x₂ = 25”
    against „0 и 25”, a decimal comma or point, 1/2 against 0,5 — and strict
    about *value*, because that is where the official keys are strict too.
    """
    s, e = _clean(student), _clean(expected)
    if not s:
        return False
    if _NEEDS_JUDGEMENT.search(e):
        return None

    # relations: x ≤ 5/6, or the same written as an interval
    er = _relation(e)
    if er is not None:
        sr = _relation(s)
        if sr is None:
            return None
        return sr == er

    # a monomial key such as „5x” (2026 Q21)
    em = _MONOMIAL.match(e.replace(" ", ""))
    if em:
        sm = _MONOMIAL.match(s.replace(" ", "").replace("p=", "").replace("р=", ""))
        if not sm:
            return None
        coef = lambda c: Fraction(c.replace(",", ".")) if c not in ("", "-") else Fraction(-1 if c == "-" else 1)
        return coef(em.group(1)) == coef(sm.group(1)) and em.group(2) == sm.group(2)

    # a month (2026 Q17 А: „май”, „или V, или 05”)
    if _month(e) is not None:
        sm = _month(s)
        return None if sm is None else sm == _month(e)

    # a clock time: „16 h 45 min” against „16:45”, „16 ч. и 45 мин.”
    et = _clock_minutes(e)
    if et is not None:
        st = _clock_minutes(s)
        return None if st is None else st == et

    e_vals, s_vals = _strip_assignments(e), _strip_assignments(s)
    if re.search(r"[xy]", e_vals):
        # a polynomial answer („3x + 10”, „xy - 6”): compare term by term, in any
        # order; anything with brackets or powers is left to a reader
        ep = _polynomial(e)
        if ep is None:
            return None
        sp = _polynomial(s)
        return None if sp is None else sp == ep
    en = _numbers(e_vals)
    if en:
        sn = _numbers(s_vals)
        if not sn:
            return None
        if sn == en:
            return True
        # a set of roots („0 и 25”) is unordered; anything else is read in order,
        # so „първата 7 дни, втората 6” is not matched by „6 и 7”
        unordered = len(en) == 1 or " и " in e
        if set(sn) == set(en):
            return True if unordered else None
        return False

    return None


_UNITS = re.compile(r"\b(?:cm|mm|dm|km|m|g|kg|l|h|min|см|мм|м|кг)(?:\^?[23²³])?\b|[²³°]")
_TERM = re.compile(r"([+-]?)(\d+(?:[.,]\d+)?(?:/\d+)?)?\*?((?:[xyabn])*)$")


def _polynomial(text: str) -> dict[str, Fraction] | None:
    """„4x + 10”, „10 + 4x”, „p = 4x+10 cm” → {"x": 4, "": 10}. None if it is
    not a plain sum of monomials."""
    t = _UNITS.sub("", text)
    t = re.sub(r"^\s*[a-zа-я]\w*\s*=\s*", "", t)          # „P = …”, „S = …”
    t = t.replace(" ", "").replace("·", "").replace("*", "")
    if not t or re.search(r"[()^]", t):
        return None
    terms = re.findall(r"[+-]?[^+-]+", t)
    if not terms or "".join(terms) != t:
        return None
    out: dict[str, Fraction] = {}
    for term in terms:
        m = _TERM.fullmatch(term)
        if not m or (m.group(2) is None and not m.group(3)):
            return None
        coef = Fraction(m.group(2).replace(",", ".")) if m.group(2) else Fraction(1)
        if m.group(1) == "-":
            coef = -coef
        mono = "".join(sorted(m.group(3)))
        out[mono] = out.get(mono, Fraction(0)) + coef
    return {k: v for k, v in out.items() if v != 0}


_SUBSCRIPT = re.compile(r"([xy])\s*_?\s*[₁₂12](?!\d)")


def _strip_assignments(text: str) -> str:
    """„x_1 = 4, x_2 = 5” → „4, 5”; „x = 15” → „15”. Leaves expressions alone."""
    text = _SUBSCRIPT.sub(r"\1", text)
    return re.sub(r"\b[xy]\s*=\s*", "", text)


def _clock_minutes(text: str) -> int | None:
    m = re.fullmatch(r"\s*(\d{1,2})\s*(?::|\.|h|ч\.?|часа?|часà)\s*(?:и\s*)?"
                     r"(\d{1,2})?\s*(?:min|мин\.?|минути)?\s*", text)
    if not m or (m.group(2) is None and not re.search(r"h|ч", text)):
        return None
    return int(m.group(1)) * 60 + int(m.group(2) or 0)


@dataclass
class WrittenGrade:
    score: int
    max_score: int
    extracted: str
    feedback: str

    @property
    def is_correct(self) -> bool:
        return self.score == self.max_score


def _split_answer(raw: str | dict[str, str], letters: Sequence[str]) -> list[str]:
    """One string per sub-part. The client keys parts by letter, sometimes a
    Latin A for the Cyrillic А."""
    if not letters:
        if isinstance(raw, dict):
            return [" ".join(str(v) for v in raw.values())]
        return [str(raw or "")]
    if isinstance(raw, dict):
        norm = {k.strip().upper().replace("A", "А").replace("B", "В"): str(v)
                for k, v in raw.items()}
        return [norm.get(letter, "") for letter in letters]
    # a single string for a multi-part item: „А) май Б) 15” or one line per part
    text = str(raw or "")
    pieces = re.split(r"(?:^|\s)([АБВГД])\)", text)
    if len(pieces) > 2:
        found = dict(zip(pieces[1::2], pieces[2::2]))
        return [found.get(letter, "").strip() for letter in letters]
    return [text] + [""] * (len(letters) - 1)


def grade_written(
    *,
    statement: str,
    parts: Sequence[str] | None,
    correct: str | list[str] | None,
    points: Sequence[int] | None,
    marking: str | None,
    raw_answer: str | dict[str, str],
    image_data_url: str | None,
    ai_grade: AiGrade,
) -> WrittenGrade:
    """Grade one short-answer or extended item, sub-part by sub-part."""
    letters = list(parts or [])
    keys = list(correct) if isinstance(correct, list) else [str(correct or "")]
    n = max(len(letters), 1)
    if len(keys) < n:
        keys += [""] * (n - len(keys))
    pts = list(points) if points and len(points) == n else [max(sum(points or [1]) // n, 1)] * n
    total = sum(pts)
    key_text = " | ".join(keys[:n])
    context = f"{statement}\n\nСхема за оценяване:\n{marking}" if marking else statement

    if image_data_url:
        # A photographed solution covers every part at once; the model reads it whole.
        ok, extracted, feedback = ai_grade(statement=context, correct_xy=key_text,
                                           student_work="(вижте снимката)",
                                           image_data_url=image_data_url)
        return WrittenGrade(total if ok else 0, total, extracted, feedback)

    answers = _split_answer(raw_answer, letters)
    score, notes, extracted = 0, [], []
    for i in range(n):
        label = f"{letters[i]}) " if letters else ""
        given, key = answers[i].strip(), keys[i]
        extracted.append(f"{label}{given}".strip())
        if not given:
            notes.append(f"{label}Липсва отговор. Верният отговор е {key}.")
            continue
        verdict = match_answer(given, key)
        if verdict is None:
            part_prompt = f"{context}\n\nОценява се само подточка {label.strip()}".strip()
            try:
                ok, _extr, fb = ai_grade(statement=part_prompt, correct_xy=key,
                                         student_work=given, image_data_url=None)
            except Exception:
                notes.append(f"{label}Не може да бъде проверено автоматично в момента. "
                             f"Верният отговор е {key}.")
                continue
            verdict = ok
            if not ok:
                notes.append(f"{label}{fb}")
        elif not verdict:
            notes.append(f"{label}Грешен отговор. Верният отговор е {key}.")
        if verdict:
            score += pts[i]
    feedback = " ".join(notes) if notes else "Вярно."
    return WrittenGrade(score, total, "; ".join(e for e in extracted if e), feedback)
