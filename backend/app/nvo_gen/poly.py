"""Exact polynomials in one variable, and expressions that know their own LaTeX.

Part 2 algebra items print an expression and then key an answer that depends
on what that expression *is*. Writing the LaTeX by hand and the arithmetic by
hand, side by side, is how the bank shipped the 2021 Q22 equation with
``x(x - 4)/9`` where the paper has ``x(0,5x - 4)/9`` — one character, and the
x² terms stopped cancelling, so every variant needed the quadratic formula.

So an item builds one ``Expr`` tree. The same tree renders the stem and
evaluates to a ``Poly``; they cannot disagree.

    x = var()
    e = frac((x + 3) ** 2, 18) - frac(x * lin(Fraction(1, 2), -4), 9)
    e.tex()        # \\dfrac{\\left(x + 3\\right)^2}{18} - \\dfrac{x\\left(0{,}5x - 4\\right)}{9}
    e.poly()       # exact coefficients
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence, Union

from app.nvo_gen.distractors import bg_number

Num = Union[int, Fraction]


# ─── polynomials ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Poly:
    """Coefficients lowest degree first, trailing zeros stripped."""

    c: tuple[Fraction, ...]

    @staticmethod
    def of(*coeffs: Num) -> "Poly":
        out = [Fraction(v) for v in coeffs]
        while out and out[-1] == 0:
            out.pop()
        return Poly(tuple(out))

    @property
    def degree(self) -> int:
        return len(self.c) - 1

    def coeff(self, k: int) -> Fraction:
        return self.c[k] if k < len(self.c) else Fraction(0)

    def __add__(self, o: "Poly") -> "Poly":
        n = max(len(self.c), len(o.c))
        return Poly.of(*(self.coeff(i) + o.coeff(i) for i in range(n)))

    def __neg__(self) -> "Poly":
        return Poly.of(*(-v for v in self.c))

    def __sub__(self, o: "Poly") -> "Poly":
        return self + (-o)

    def __mul__(self, o: "Poly") -> "Poly":
        if not self.c or not o.c:
            return Poly(())
        out = [Fraction(0)] * (len(self.c) + len(o.c) - 1)
        for i, a in enumerate(self.c):
            for j, b in enumerate(o.c):
                out[i + j] += a * b
        return Poly.of(*out)

    def scale(self, k: Num) -> "Poly":
        return Poly.of(*(v * Fraction(k) for v in self.c))

    def __pow__(self, n: int) -> "Poly":
        out = Poly.of(1)
        for _ in range(n):
            out = out * self
        return out

    def __call__(self, x: Num) -> Fraction:
        return sum((v * Fraction(x) ** i for i, v in enumerate(self.c)), Fraction(0))

    def tex(self, var: str = "x") -> str:
        """Normal form, highest degree first: ``4x^2 + 26x``."""
        if not self.c:
            return "0"
        terms = []
        for k in range(self.degree, -1, -1):
            v = self.coeff(k)
            if v == 0:
                continue
            mag = abs(v)
            if k == 0:
                body = bg_number(mag)
            else:
                pw = var if k == 1 else f"{var}^{k}"
                body = pw if mag == 1 else f"{bg_decimalish(mag)}{pw}"
            terms.append(("-" if v < 0 else "+", body))
        first_sign, first = terms[0]
        out = ("-" if first_sign == "-" else "") + first
        for sign, body in terms[1:]:
            out += f" {sign} {body}"
        return out


def bg_decimalish(v: Fraction) -> str:
    """A coefficient: a terminating decimal prints as one (0,5x), else a fraction."""
    if v.denominator == 1:
        return str(v.numerator)
    if 100 % v.denominator == 0:
        return bg_number(float(v))
    return bg_number(v)


# ─── expressions ────────────────────────────────────────────────────────────

class Expr:
    """An expression tree that renders LaTeX and evaluates to a ``Poly``."""

    #: binding strength: 3 atom, 2 product/power, 1 sum
    prec = 3

    def poly(self) -> Poly:
        raise NotImplementedError

    def tex(self) -> str:
        raise NotImplementedError

    def is_negative_leading(self) -> bool:
        return False

    # arithmetic builds trees
    def __add__(self, o: "Expr | Num") -> "Expr":
        return Sum([(1, self), (1, _lift(o))])

    def __radd__(self, o: Num) -> "Expr":
        return Sum([(1, _lift(o)), (1, self)])

    def __sub__(self, o: "Expr | Num") -> "Expr":
        return Sum([(1, self), (-1, _lift(o))])

    def __rsub__(self, o: Num) -> "Expr":
        return Sum([(1, _lift(o)), (-1, self)])

    def __mul__(self, o: "Expr | Num") -> "Expr":
        if not isinstance(o, Expr):
            return Scaled(Fraction(o), self)
        return Prod([self, o])

    def __rmul__(self, o: Num) -> "Expr":
        return Scaled(Fraction(o), self)

    def __pow__(self, n: int) -> "Expr":
        return Power(self, n)


class Leaf(Expr):
    """A polynomial printed in normal form — ``x``, ``3``, ``2x - 5``."""

    def __init__(self, p: Poly, name: str = "x"):
        self.p = p
        self.name = name
        self.prec = 3 if len([v for v in p.c if v != 0]) <= 1 else 1

    def poly(self) -> Poly:
        return self.p

    def _constant_first(self) -> bool:
        # "4 - x", the way the papers write it, rather than "-x + 4"
        return self.p.degree == 1 and self.p.c[1] < 0 and self.p.c[0] > 0

    def tex(self) -> str:
        if self._constant_first():
            return f"{bg_number(self.p.c[0])} - {Poly.of(0, -self.p.c[1]).tex(self.name)}"
        return self.p.tex(self.name)

    def is_negative_leading(self) -> bool:
        return bool(self.p.c) and self.p.c[-1] < 0 and not self._constant_first()


class Sum(Expr):
    prec = 1

    def __init__(self, terms: Sequence[tuple[int, Expr]]):
        flat: list[tuple[int, Expr]] = []
        for s, e in terms:
            if isinstance(e, Sum) and s == 1:
                flat.extend(e.terms)
            else:
                flat.append((s, e))
        self.terms = flat

    def poly(self) -> Poly:
        out = Poly(())
        for s, e in self.terms:
            out = out + (e.poly() if s > 0 else -e.poly())
        return out

    def tex(self) -> str:
        parts: list[str] = []
        for i, (s, e) in enumerate(self.terms):
            if i > 0 and e.is_negative_leading() and isinstance(e, (Leaf, Scaled)) and e.prec >= 2:
                # a negative single term or a negative multiple of a bracket
                # prints "- 3" / "+ 2(x + 1)", never "+ (-3)" / "- (-2(x + 1))"
                s, e = -s, (Leaf(-e.p, e.name) if isinstance(e, Leaf) else Scaled(-e.k, e.e))
            body = e.tex()
            needs_paren = (s < 0 and e.prec <= 1) or (e.is_negative_leading() and i > 0)
            if needs_paren:
                body = rf"\left({body}\right)"
            if i == 0:
                parts.append(("-" if s < 0 else "") + body)
            else:
                parts.append(f" {'-' if s < 0 else '+'} {body}")
        return "".join(parts)

    def is_negative_leading(self) -> bool:
        s, e = self.terms[0]
        return s < 0 or e.is_negative_leading()


class Prod(Expr):
    prec = 2

    def __init__(self, factors: Sequence[Expr]):
        self.factors = list(factors)

    def poly(self) -> Poly:
        out = Poly.of(1)
        for f in self.factors:
            out = out * f.poly()
        return out

    def tex(self) -> str:
        out = []
        for i, f in enumerate(self.factors):
            body = f.tex()
            if f.prec <= 1 or (i > 0 and f.is_negative_leading()):
                body = rf"\left({body}\right)"
            elif i > 0 and out and out[-1][-1:].isdigit() and body[:1].isdigit():
                body = rf"\cdot {body}"
            out.append(body)
        return "".join(out)

    def is_negative_leading(self) -> bool:
        return self.factors[0].is_negative_leading()


class Scaled(Expr):
    """``k·(expr)``: a number in front of a bracket, fractions printed as fractions."""

    prec = 2

    def __init__(self, k: Fraction, e: Expr):
        self.k, self.e = k, e

    def poly(self) -> Poly:
        return self.e.poly().scale(self.k)

    def tex(self) -> str:
        k = self.k
        mag = abs(k)
        coef = "" if mag == 1 else (bg_number(mag) if mag.denominator == 1
                                    else rf"\dfrac{{{mag.numerator}}}{{{mag.denominator}}}")
        body = self.e.tex()
        if self.e.prec <= 2 and coef:
            body = rf"\left({body}\right)"
        elif self.e.prec <= 1:
            body = rf"\left({body}\right)"
        return ("-" if k < 0 else "") + coef + body

    def is_negative_leading(self) -> bool:
        return self.k < 0


class Power(Expr):
    prec = 2

    def __init__(self, base: Expr, n: int):
        self.base, self.n = base, n

    def poly(self) -> Poly:
        return self.base.poly() ** self.n

    def tex(self) -> str:
        b = self.base.tex()
        if not (isinstance(self.base, Leaf) and b.isalpha() and len(b) == 1):
            b = rf"\left({b}\right)"
        return f"{b}^{self.n}"


class Over(Expr):
    """``\\dfrac{expr}{d}`` with an integer denominator."""

    prec = 3

    def __init__(self, num: Expr, den: int):
        self.num, self.den = num, den

    def poly(self) -> Poly:
        return self.num.poly().scale(Fraction(1, self.den))

    def tex(self) -> str:
        return rf"\dfrac{{{self.num.tex()}}}{{{self.den}}}"


def _lift(v: "Expr | Num") -> Expr:
    return v if isinstance(v, Expr) else Leaf(Poly.of(v))


def interval_tex_named(rel: str, bound: Fraction, name: str) -> str:
    return interval_tex(rel, bound).replace("x \\in", f"{name} \\in", 1)


def var(name: str = "x") -> Expr:
    return Leaf(Poly.of(0, 1), name)


def lin(a: Num, b: Num, name: str = "x") -> Expr:
    """``ax + b`` as one printed unit."""
    return Leaf(Poly.of(b, a), name)


def leaf(p: Poly, name: str = "x") -> Expr:
    """A polynomial printed as one unit in normal form."""
    return Leaf(p, name)


def const(v: Num) -> Expr:
    return Leaf(Poly.of(v))


def frac(e: Expr, den: int) -> Expr:
    return Over(e, den)


# ─── solving what these items reduce to ─────────────────────────────────────

def linear_root(p: Poly) -> Fraction:
    """The root of a polynomial that must have reduced to degree one."""
    if p.degree != 1:
        raise ValueError(f"expected a linear polynomial, got degree {p.degree}")
    return -p.coeff(0) / p.coeff(1)


def solve_linear_inequality(lhs: Poly, rhs: Poly, rel: str) -> tuple[str, Fraction]:
    """Reduce ``lhs rel rhs`` to ``x rel' bound``. Both sides' x² must cancel."""
    d = lhs - rhs
    if d.degree != 1:
        raise ValueError(f"inequality does not reduce to a linear one (degree {d.degree})")
    a, b = d.coeff(1), d.coeff(0)
    bound = -b / a
    flip = {"<": ">", ">": "<", r"\le": r"\ge", r"\ge": r"\le"}
    return (rel if a > 0 else flip[rel]), bound


def satisfies(x: Fraction, rel: str, bound: Fraction) -> bool:
    return {"<": x < bound, ">": x > bound, r"\le": x <= bound, r"\ge": x >= bound}[rel]


def interval_tex(rel: str, bound: Fraction) -> str:
    b = num_tex(bound)
    return {
        "<": rf"x \in \left(-\infty; {b}\right)",
        r"\le": rf"x \in \left(-\infty; {b}\right]",
        ">": rf"x \in \left({b}; +\infty\right)",
        r"\ge": rf"x \in \left[{b}; +\infty\right)",
    }[rel]


def num_tex(v: Fraction) -> str:
    """A key value: integer, terminating decimal (2{,}5), or a fraction."""
    v = Fraction(v)
    if v.denominator == 1:
        return str(v.numerator)
    if 100 % v.denominator == 0:
        return bg_number(float(v))
    return bg_number(v)


def num_plain(v: Fraction) -> str:
    """The same, for a plain-text key a grader compares against: 2,5 or -8/5."""
    v = Fraction(v)
    if v.denominator == 1:
        return str(v.numerator)
    if 100 % v.denominator == 0:
        return f"{float(v):g}".replace(".", ",")
    return f"{v.numerator}/{v.denominator}"


def is_nice(v: Fraction, *, max_den: int = 6) -> bool:
    """A bound a key would print: an integer, a half/fifth/quarter, or a small fraction."""
    return Fraction(v).denominator <= max_den
