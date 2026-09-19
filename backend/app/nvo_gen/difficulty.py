"""Four ways to sit the same paper.

``actual`` is the real thing: the item mix, the numbers and the timing of an
official NVO paper, with every knob in this module neutral. The other three are
that same paper made gentler or nastier.

**The structure never moves.** Every difficulty generates the same positions,
the same topics, the same points per position and the same А/Б/В/Г menu,
because that skeleton is what makes a paper recognisable as НВО at all — it is
the thing the corpus teardown found invariant across thirteen papers and two
restructurings. Difficulty is a *version of* that format, never a different
format. What actually changes is only:

  * **which template fills a slot.** Every template declares a band — "easy",
    "medium" or "hard" — and a profile re-weights the bands when the assembler
    chooses between the templates eligible for a position. Position 13 is a
    right-triangle item at every level; whether it is the one-step median item
    or the perpendicular-bisector chase is what moves.
  * **how nasty the numbers are.** Templates read ``slot.profile`` and size
    their own parameter pools from it via :meth:`DifficultyProfile.tier`. The
    same template is a different question at 12x + 3 = 4 than at x + 3 = 7.
  * **how long the student gets.** ``time_scale`` stretches the official
    minutes for the gentler levels and squeezes them for the hardest.

Points are deliberately *not* a knob. Part 1 totals 65 and Part 2 totals 35 at
every difficulty, so a percentage means the same thing across levels and the XP
multiplier — not a shorter paper — is what rewards taking the harder one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, TypeVar

T = TypeVar("T")

#: The bands a template may declare. A band is a property of the *template*
#: ("this shape is intrinsically a hard one"), not of the paper it lands on.
BANDS: tuple[str, ...] = ("easy", "medium", "hard")


@dataclass(frozen=True)
class DifficultyProfile:
    """One difficulty level, as a set of knobs over the unchanged blueprint.

    Frozen and built only from hashable fields so that :class:`~app.nvo_gen.
    blueprints.Slot` can carry one and stay hashable itself.
    """

    code: str
    label_bg: str
    subtitle_bg: str
    blurb_bg: str
    emoji: str
    #: Ordering for the picker, easiest first.
    rank: int
    #: Multiplier applied to a template's own weight, by the template's band.
    #: Stored as pairs rather than a dict to keep the dataclass hashable.
    band_weights: tuple[tuple[str, float], ...]
    #: Stretches (>1) or squeezes (<1) the blueprint's official minutes.
    time_scale: float
    #: XP awarded relative to sitting the real paper.
    xp_multiplier: float

    def weight_for(self, band: str) -> float:
        """How strongly to favour a template of this band at this level.

        Never returns 0: even at "easy" the hard shapes stay reachable, because
        a slot whose every template is hard must still be fillable. The weight
        just makes them rare.
        """
        for name, value in self.band_weights:
            if name == band:
                return value
        return 1.0

    def tier(self, easy: T, medium: T, actual: T, extra_hard: T | None = None) -> T:
        """Pick the variant of a parameter pool that matches this level.

        The idiom a template uses to size its own numbers:

            a = rng.choice(slot.profile.tier([2, 3, 4],
                                             [4, 5, 6, 8],
                                             [12, 15, 18, 20, 24, 25]))

        ``extra_hard`` falls back to ``actual`` so a template only has to spell
        out a fourth pool when the hardest level genuinely deserves one.
        """
        if self.code == "easy":
            return easy
        if self.code == "medium":
            return medium
        if self.code == "extra_hard":
            return actual if extra_hard is None else extra_hard
        return actual

    def minutes(self, official: int) -> int:
        """The official allowance, stretched or squeezed, rounded to 5 minutes."""
        return max(5, int(round(official * self.time_scale / 5.0)) * 5)

    @property
    def is_actual(self) -> bool:
        """True for the one level that reproduces the real paper exactly."""
        return self.code == "actual"


# ─── the four levels ─────────────────────────────────────────────────────────
# band_weights read (easy, medium, hard). "actual" is all 1.0 by definition —
# it leaves each template's own weight, which encodes how often that shape
# appears in the real papers, completely alone.

EASY = DifficultyProfile(
    code="easy",
    label_bg="Лесно",
    subtitle_bg="За начало",
    blurb_bg=(
        "Същият изпит, но с по-малки числа и по-кратки задачи. "
        "Подходящо, докато си припомняш материала."
    ),
    emoji="🌱",
    rank=0,
    band_weights=(("easy", 5.0), ("medium", 1.0), ("hard", 0.1)),
    time_scale=1.30,
    xp_multiplier=0.5,
)

MEDIUM = DifficultyProfile(
    code="medium",
    label_bg="Средно",
    subtitle_bg="Към реалното ниво",
    blurb_bg=(
        "Малко по-леко от истинския изпит. Същите теми и същият брой задачи, "
        "но без най-тежките разсъждения."
    ),
    emoji="📗",
    rank=1,
    band_weights=(("easy", 2.0), ("medium", 2.0), ("hard", 0.5)),
    time_scale=1.15,
    xp_multiplier=0.8,
)

ACTUAL = DifficultyProfile(
    code="actual",
    label_bg="Като на НВО",
    subtitle_bg="Реалният формат",
    blurb_bg=(
        "Точно както на истинското НВО: същата структура, същата трудност "
        "и същото време. Това е изпитът, за който се готвиш."
    ),
    emoji="📚",
    rank=2,
    band_weights=(("easy", 1.0), ("medium", 1.0), ("hard", 1.0)),
    time_scale=1.0,
    xp_multiplier=1.0,
)

EXTRA_HARD = DifficultyProfile(
    code="extra_hard",
    label_bg="Много трудно",
    subtitle_bg="Над нивото на НВО",
    blurb_bg=(
        "По-тежко от изпита: по-големи числа, повече стъпки и по-малко време. "
        "За когато реалният вариант вече ти е лесен."
    ),
    emoji="🔥",
    rank=3,
    band_weights=(("easy", 0.1), ("medium", 0.8), ("hard", 5.0)),
    time_scale=0.85,
    xp_multiplier=2.0,
)

PROFILES: dict[str, DifficultyProfile] = {
    p.code: p for p in (EASY, MEDIUM, ACTUAL, EXTRA_HARD)
}

#: A paper with no difficulty asked for is the real paper.
DEFAULT_DIFFICULTY = ACTUAL.code

#: What the client used to send. "standard" was the old name for the real
#: paper and "hard" for the level above it; both still arrive from stored
#: attempts and from any client that has not reloaded, and neither may 500.
_ALIASES: dict[str, str] = {
    "standard": ACTUAL.code,
    "normal": ACTUAL.code,
    "real": ACTUAL.code,
    "nvo": ACTUAL.code,
    "hard": EXTRA_HARD.code,
    "extrahard": EXTRA_HARD.code,
    "extra-hard": EXTRA_HARD.code,
    "very_hard": EXTRA_HARD.code,
}


def normalize(code: str | None) -> str:
    """Resolve any difficulty spelling — current, legacy or junk — to a code."""
    if not code:
        return DEFAULT_DIFFICULTY
    key = str(code).strip().lower().replace(" ", "_")
    if key in PROFILES:
        return key
    return _ALIASES.get(key, DEFAULT_DIFFICULTY)


def get_profile(code: str | None) -> DifficultyProfile:
    """Resolve a difficulty code to its profile, falling back rather than raising.

    Same contract as ``blueprints.get_blueprint``: a stale client that still
    posts ``difficulty='standard'`` keeps working, and a student mid-exam never
    sees a 500 because an enum drifted.
    """
    return PROFILES[normalize(code)]


def catalogue() -> list[dict[str, object]]:
    """What the difficulty picker shows. Ordered easiest-first."""
    return [
        {
            "code": p.code,
            "label": p.label_bg,
            "subtitle": p.subtitle_bg,
            "blurb": p.blurb_bg,
            "emoji": p.emoji,
            "xpMultiplier": p.xp_multiplier,
            "timeScale": p.time_scale,
            "isActual": p.is_actual,
        }
        for p in sorted(PROFILES.values(), key=lambda p: p.rank)
    ]


def band_of(pool: Sequence[str]) -> str:
    """The band a multi-band group should report — the hardest one present."""
    for band in reversed(BANDS):
        if band in pool:
            return band
    return "medium"
