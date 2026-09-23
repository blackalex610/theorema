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

  * **The model could only say right or wrong.** A proof with the right
    method and one slip earned 0 of 12, where the official scheme awards the
    steps — „1 т. за съставяне и опростяване на уравнението”.

So: each sub-part is checked on its own and earns its own points. A key that
is a number, a set of numbers, a time or a polynomial like „3x + 10” is
compared exactly, here, for free, and the key's own part-mark rules for short
answers are applied here too. What cannot be compared mechanically goes to the
model as an examiner (``ai_mark``): it gets the marking scheme and each
sub-part's maximum and awards any whole number of points from 0 to it.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Sequence

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


# ─── partial credit the official keys define for short answers ──────────────

_SET_SPLIT = re.compile(r"\s+и\s+|[,;]")


def _answer_set(text: str) -> list[str]:
    return [p.strip() for p in _SET_SPLIT.split(text or "") if p.strip()]


def short_partial_credit(given: str, key: str, max_points: int,
                         partial_credit: dict[str, int] | None = None) -> int:
    """Points a short answer earns when it is not fully right, by the key's own rules.

    Short answers in Part 1 are marked on the answer alone; the key gives part
    marks only where it says so. Two rules cover the corpus:

    * a set of roots — 2026 Q15 „0 и 25”, „2 т., при един верен отговор”: each
      correct value earns its share, as long as the student did not list more
      values than the key has (no scattering guesses to collect credit);
    * an item's own list — 2026 Q21 „2 т., ако е написано 4x; 3 т., ако е
      написано 4x и 5x” — carried on the item as ``partial_credit``: answer →
      points, where an answer „4x и 5x” means both were written.
    """
    best = 0
    for alt, pts in (partial_credit or {}).items():
        wanted = _answer_set(alt)
        written = _answer_set(given)
        if len(wanted) == 1:
            ok = any(match_answer(w, wanted[0]) is True for w in written) and len(written) == 1
        else:
            ok = all(any(match_answer(w, a) is True for w in written) for a in wanted)
        if ok:
            best = max(best, min(pts, max_points))

    if " и " in key and not _NEEDS_JUDGEMENT.search(_clean(key)):
        keys = _answer_set(key)
        written = _answer_set(given)
        if 1 < len(keys) and 0 < len(written) <= len(keys):
            right = sum(1 for k in keys if any(match_answer(w, k) is True for w in written))
            best = max(best, max_points * right // len(keys))
    return best


# ─── the model as an examiner ───────────────────────────────────────────────

#: ai_mark(statement=, marking=, kind=, parts=[{label, key, max_points, answer}],
#:         image_data_url=) -> (points per part, feedback per part, extracted answer)
AiMark = Callable[..., tuple[list[int], list[str], str]]

EXAMINER_PROMPT = (
    "Ти си квалифициран оценител на Националното външно оценяване по математика "
    "в VII клас. Оценяваш решението на ученик по официалната схема за оценяване, "
    "точно както на истинския изпит.\n"
    "Правила:\n"
    "1. Оценявай всяка подточка поотделно. Можеш да дадеш всеки цял брой точки от 0 "
    "до максимума на подточката — НЕ само 0 или максимума.\n"
    "2. Частичните точки се дават по схемата: за всяка вярно направена стъпка или "
    "верен междинен резултат (напр. „за съставяне на уравнението — 2 т.“), дори ако "
    "крайният отговор е грешен или липсва.\n"
    "3. Отговорът в полето „верен отговор“ е верен. Не решавай задачата наново и не го "
    "оспорвай.\n"
    "4. Всяко друго вярно и пълно решение, различно от схемата, получава максималния "
    "брой точки. При непълно решение давай точки според получените междинни резултати.\n"
    "5. Грешка в пресмятането, след която решението продължава логично, отнема само "
    "точките за засегнатите стъпки.\n"
    "6. Празна, напълно грешна или несвързана с условието подточка получава 0 точки.\n"
    "Отговори САМО с JSON, без markdown:\n"
    '{"parts": [{"part": "А", "points": <цяло число>, "feedback": "<1–2 изречения на '
    'български: какво е вярно и за какво се губят точки>"}], '
    '"extracted_answer": "<крайните отговори на ученика>"}'
)
SHORT_ANSWER_RULE = (
    "\nТова е задача с кратък свободен отговор: оценява се само записаният отговор, "
    "без решение. Частични точки се дават само ако схемата изрично ги предвижда "
    "(напр. „2 т., при един верен отговор“)."
)


def build_examiner_request(*, statement: str, marking: str | None, kind: str,
                           parts: Sequence[dict]) -> tuple[str, str]:
    """(system prompt, user text) for one question and the sub-parts to mark."""
    system = EXAMINER_PROMPT + (SHORT_ANSWER_RULE if kind == "short" else "")
    lines = [f"Задача:\n{statement}", "",
             "Схема за оценяване:\n" + (marking or "(няма подробна схема — оценявай по "
                                                  "верния отговор и правилата)"), "",
             "Подточки за оценяване:"]
    for p in parts:
        label = p["label"] or "(цялата задача)"
        lines.append(f"{label}: максимум {p['max_points']} т.; верен отговор: {p['key']}; "
                     f"отговор на ученика: {p['answer'] or '(вижте снимката)'}")
    return system, "\n".join(lines)


def parse_marks(raw: str, parts: Sequence[dict]) -> tuple[list[int], list[str], str]:
    """Read the examiner's JSON. Every number is clamped to its sub-part's
    maximum; a sub-part the reply leaves out earns nothing and says so.
    Raises ValueError when the reply is not the JSON asked for."""
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError("no JSON object in the examiner's reply")
    data = json.loads(m.group(0))
    marked = data.get("parts")
    if not isinstance(marked, list):
        raise ValueError("the reply has no 'parts' list")

    def norm(label: str) -> str:
        return (label or "").strip().rstrip(")").upper().replace("A", "А").replace("B", "В")

    by_label = {norm(str(e.get("part", ""))): e for e in marked if isinstance(e, dict)}
    points, feedback = [], []
    for i, p in enumerate(parts):
        entry = by_label.get(norm(p["label"]))
        if entry is None and len(marked) == len(parts) and isinstance(marked[i], dict):
            entry = marked[i]
        if entry is None:
            points.append(0)
            feedback.append("Няма оценка за тази подточка.")
            continue
        try:
            got = round(float(str(entry.get("points", 0)).replace(",", ".")))
        except ValueError:
            got = 0
        points.append(max(0, min(int(got), int(p["max_points"]))))
        feedback.append(str(entry.get("feedback", "")).strip())
    return points, feedback, str(data.get("extracted_answer", "")).strip()


def ai_mark(*, statement: str, marking: str | None, kind: str, parts: Sequence[dict],
            image_data_url: str | None = None) -> tuple[list[int], list[str], str]:
    """Ask the model to mark the given sub-parts like an НВО examiner."""
    from openai import OpenAI

    from app.config import settings

    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    system, user_text = build_examiner_request(statement=statement, marking=marking,
                                               kind=kind, parts=parts)
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    if image_data_url:
        # vision requests take a content list and do not accept response_format
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL, temperature=0,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": [
                          {"type": "text", "text": user_text},
                          {"type": "image_url", "image_url": {"url": image_data_url}}]}],
        )
    else:
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL, temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user_text}],
        )
    return parse_marks(resp.choices[0].message.content or "", parts)


# ─── one written item ────────────────────────────────────────────────────────

def grade_written(
    *,
    statement: str,
    parts: Sequence[str] | None,
    correct: str | list[str] | None,
    points: Sequence[int] | None,
    marking: str | None,
    raw_answer: str | dict[str, str],
    image_data_url: str | None,
    ai_mark: AiMark,
    kind: str = "open",
    partial_credit: dict[str, int] | None = None,
) -> WrittenGrade:
    """Grade one short-answer or extended item, sub-part by sub-part, with part marks.

    A sub-part whose answer matches the key exactly earns its points here. The
    rest go to the model in one request per question, which marks each of them
    from 0 to its maximum by the scheme — a Part 2 answer with the wrong final
    number still earns the steps it got right, as at the real exam. A Part 1
    short answer is marked on the answer alone, with the key's own part-mark
    rules applied here first. A photographed solution goes to the model whole.
    """
    letters = list(parts or [])
    keys = list(correct) if isinstance(correct, list) else [str(correct or "")]
    n = max(len(letters), 1)
    if len(keys) < n:
        keys += [""] * (n - len(keys))
    pts = list(points) if points and len(points) == n else [max(sum(points or [1]) // n, 1)] * n
    total = sum(pts)

    answers = _split_answer(raw_answer, letters)
    earned = [0] * n
    notes: list[str | None] = [None] * n
    to_model: list[int] = []
    for i in range(n):
        given, key = answers[i].strip(), keys[i]
        if image_data_url:
            to_model.append(i)
            continue
        if not given:
            notes[i] = f"Липсва отговор. Верният отговор е {key}."
            continue
        verdict = match_answer(given, key)
        if verdict is True:
            earned[i] = pts[i]
            continue
        if kind == "short":
            part = short_partial_credit(given, key, pts[i], partial_credit if n == 1 else None)
            if verdict is False or part:
                earned[i] = part
                notes[i] = (f"Частично вярно ({part} от {pts[i]} т.). " if part else
                            "Грешен отговор. ") + f"Верният отговор е {key}."
                continue
        to_model.append(i)       # a proof, a worded verdict, or a Part 2 answer with work

    extracted = "; ".join(f"{letters[i]}) {answers[i].strip()}" if letters else answers[i].strip()
                          for i in range(n) if answers[i].strip())
    if to_model:
        request = [{"label": letters[i] if letters else "", "key": keys[i],
                    "max_points": pts[i], "answer": answers[i].strip()} for i in to_model]
        try:
            got, fb, model_extracted = ai_mark(
                statement=statement, marking=marking, kind=kind, parts=request,
                image_data_url=image_data_url or None)
        except Exception:
            for i in to_model:
                notes[i] = ("Не може да бъде проверено автоматично в момента. "
                            f"Верният отговор е {keys[i]}.")
        else:
            for j, i in enumerate(to_model):
                earned[i] = max(0, min(int(got[j]), pts[i]))
                if earned[i] < pts[i]:
                    notes[i] = f"{earned[i]} от {pts[i]} т. " + (fb[j] or f"Верният отговор е {keys[i]}.")
            if image_data_url and model_extracted:
                extracted = model_extracted

    lines = [f"{letters[i] + ') ' if letters else ''}{notes[i]}" for i in range(n) if notes[i]]
    return WrittenGrade(sum(earned), total, extracted, " ".join(lines) if lines else "Вярно.")
