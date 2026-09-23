"""Part 2 extended word problems — six shapes, each a real paper's item generalised.

The trap with a word problem is over-determination. The previous
``two_vehicles_meeting`` gave the bus's speed *and* the car's lead *and* the
midpoint meeting; those three facts fix each other (v = 5·Δv for the paper's
timings), so every generated variant described two vehicles that could not
meet where the stem said they did. Here each builder draws the *free*
quantities, solves for the rest, and rejects the draw unless every derived
number is one a key would print.

    2026 Q23  gold_carat_mixture
    2025 Q22  two_vehicles_meeting
    2023 Q22  two_brigades_work
    2024 Q22  plan_versus_actual_output
    2020 Q22  two_tanks_of_fuel
    2022 Q21  car_catches_truck
"""
from __future__ import annotations

import random
from fractions import Fraction

from app.nvo_gen.part2_bank import Part2Item, part2
from app.nvo_gen.poly import num_plain, num_tex
from app.nvo_gen.registry import Retry

F = Fraction
_ATTEMPTS = 600


def _dec(v: Fraction, places: int = 2) -> bool:
    return (10 ** places) % F(v).denominator == 0


def _clock(minutes_after_midnight: Fraction) -> str:
    total = int(minutes_after_midnight)
    return f"{total // 60} h {total % 60} min" if total % 60 else f"{total // 60} h"


def _clock_tex(minutes_after_midnight: Fraction) -> str:
    total = int(minutes_after_midnight)
    h, m = divmod(total, 60)
    return f"${h}$ часà и ${m}$ минути" if m else f"${h}$ часà"


# ═══════════════════════════════════════════════════════════════════════════

@part2("open_word_problem")
def gold_carat_mixture(rng: random.Random) -> Part2Item:
    """2026 Q23: a carat is a twenty-fourth; blend two alloys; dilute one.

    Part В used to be the paper's numbers verbatim (10,5 g of 18 carat taken
    to 14 carat) in every variant. It is now drawn too: the bracelet's mass is
    m·c₁/c₂, kept to one decimal place.
    """
    for _ in range(_ATTEMPTS):
        mass = rng.choice([48, 72, 96, 120, 144, 168, 60, 84])
        carats = rng.choice([9, 12, 14, 18])
        pure = F(mass * carats, 24)
        if pure.denominator != 1:
            continue
        (c1, c2) = rng.choice([(9, 18), (12, 18), (9, 14), (14, 18), (9, 22), (12, 22)])
        m1, m2 = rng.choice(range(20, 81, 10)), rng.choice(range(20, 81, 10))
        blended = F(m1 * c1 + m2 * c2, m1 + m2)
        if blended.denominator != 1 or m1 == m2 and rng.random() < 0.7:
            continue
        hi, lo = rng.choice([(18, 14), (18, 12), (22, 18), (14, 9), (18, 9), (22, 14)])
        plate = F(rng.choice(range(35, 241, 5)), 10)       # 3,5 … 24,0 g
        bracelet = plate * hi / lo
        if not _dec(bracelet, 1) or not _dec(plate, 1):
            continue
        break
    else:
        raise Retry("no carat draw closed")

    name = rng.choice(["Ани", "Мария", "Елена", "Деси", "Калина", "Вяра"])
    relative = rng.choice(["баба си", "леля си", "дядо си"])
    return Part2Item(
        code=f"word_gold_{mass}_{carats}_{m1}_{c1}_{m2}_{c2}_{hi}_{lo}_{plate}",
        topic="open_word_problem",
        stem=("Мярката за чистота на златото се нарича карат и показва каква част от "
              "дадена златна сплав е чисто злато. Злато $1$ карат означава, че "
              "$\\dfrac{1}{24}$ от масата на сплавта е чисто злато. За изработване на "
              "бижута се използва най-често злато $9$, $14$ или $18$ карата."),
        parts=(
            f"А) Намерете колко грама чисто злато има в ${mass}$ g злато ${carats}$ карата.",
            f"Б) Златар смесил ${m1}$ g злато ${c1}$ карата и ${m2}$ g злато ${c2}$ карата. "
            f"Колко карата е получената сплав?",
            f"В) {name} наследила от {relative} златна плочка от злато ${hi}$ карата с маса "
            f"${num_tex(plate)}$ g. Тя поръчала от плочката да ѝ направят гривна, като "
            f"добавят сребро така, че златото да стане ${lo}$ карата. Колко грама ще "
            "тежи гривната? (Среброто не се измерва в карати.)",
        ),
        points=(2, 4, 5),
        answers=(f"{num_plain(pure)} g", f"{num_plain(blended)} карата",
                 f"{num_plain(bracelet)} g"),
        marking=(
            f"А) Записване, че златото е $\\frac{{{carats}}}{{24}}$ от сплавта — 1 т.; "
            f"отговор ${num_tex(pure)}$ g — 1 т.\n"
            f"Б) Съставяне на уравнението ${m1} \\cdot \\frac{{{c1}}}{{24}} + {m2} \\cdot "
            f"\\frac{{{c2}}}{{24}} = {m1 + m2} \\cdot \\frac{{x}}{{24}}$ — 3 т.; "
            f"отговор ${num_tex(blended)}$ карата — 1 т.\n"
            f"В) Означаване на масата на среброто с $x$ — 1 т.; съставяне на "
            f"$\\frac{{{hi}}}{{24}} \\cdot {num_tex(plate)} = \\frac{{{lo}}}{{24}}"
            f"\\left({num_tex(plate)} + x\\right)$ — 2 т.; решаване, "
            f"$x = {num_tex(bracelet - plate)}$ g — 1 т.; отговор ${num_tex(bracelet)}$ g — 1 т."
        ),
    )


@part2("open_word_problem", band="medium")
def two_vehicles_meeting(rng: random.Random) -> Part2Item:
    """2025 Q22: a bus, a later and faster car, a meeting at the midpoint.

    Free: departure time, the bus's travel time Tb, the car's delay d, and the
    speed difference Δ. Then v·Tb = (v + Δ)(Tb − d) forces v = Δ(Tb − d)/d —
    the paper's 20 min, 2 h and 15 km/h give 75 km/h. Fuel closes the item:
    the car tops up exactly what it burnt over half the route.
    """
    for _ in range(_ATTEMPTS):
        start = rng.choice([7, 8, 9, 10]) * 60 + rng.choice([0, 0, 30])
        tb = rng.choice([90, 120, 150, 180])
        d = rng.choice([15, 20, 30, 36, 40, 45])
        delta = rng.choice([10, 15, 20, 25])
        v = F(delta * (tb - d), d)
        if v.denominator != 1 or not 50 <= v <= 90 or v + delta > 120:
            continue
        half = v * tb / 60
        if half.denominator != 1:
            continue
        per100 = F(rng.choice(range(50, 91, 2)), 10)       # 5,0 … 9,0 L
        litres = per100 * half / 100
        if not _dec(litres, 1):
            continue
        break
    else:
        raise Retry("no meeting draw closed")

    towns = rng.choice([("A", "B"), ("A", "B"), ("M", "N")])
    vehicle = rng.choice(["автобус", "камион"])
    moved = "потегля" if vehicle == "автобус" else "тръгва"
    return Part2Item(
        code=f"word_meet_{start}_{tb}_{d}_{delta}_{per100}_{vehicle}",
        topic="open_word_problem",
        stem=(f"В {_clock_tex(start)} от град ${towns[0]}$ към град ${towns[1]}$ {moved} "
              f"{vehicle}, който се движи с постоянна скорост. След ${d}$ минути от град "
              f"${towns[1]}$ към град ${towns[0]}$ с пълен резервоар потегля автомобил. Той "
              f"се движи с постоянна скорост, която е с ${delta}$ km/h по-голяма от "
              f"скоростта на {'автобуса' if vehicle == 'автобус' else 'камиона'}. В "
              f"{_clock_tex(start + tb)} превозните средства се срещат на бензиностанция "
              f"по средата на пътя между град ${towns[0]}$ и град ${towns[1]}$."),
        parts=(
            "А) Намерете скоростта на автомобила и разстоянието между двата града.",
            f"Б) На бензиностанцията шофьорът на автомобила допълва резервоара с "
            f"${num_tex(litres)}$ литра гориво. Намерете разхода на гориво на "
            f"автомобила за $100$ km.",
        ),
        points=(7, 4),
        answers=(f"{num_plain(v + delta)} km/h; {num_plain(2 * half)} km",
                 f"{num_plain(per100)} L"),
        marking=(
            f"А) Означаване на скоростта ($x$ km/h) — 1 т.; изразяване на времената "
            f"$\\frac{{{tb}}}{{60}}$ h и $\\frac{{{tb - d}}}{{60}}$ h — 2 т.; уравнение от "
            f"равните половини на пътя — 2 т.; скорост на автомобила ${num_tex(v + delta)}$ "
            f"km/h — 1 т.; разстояние ${num_tex(2 * half)}$ km — 1 т.\n"
            f"Б) Изминат от автомобила път ${num_tex(half)}$ km — 2 т.; пропорция — 1 т.; "
            f"разход ${num_tex(per100)}$ L на $100$ km — 1 т."
        ),
    )


@part2("open_word_problem", band="medium")
def two_brigades_work(rng: random.Random) -> Part2Item:
    """2023 Q22: two brigades with different head-counts and rates.

    Free: both rates, how many fewer the second brigade has, the daily
    surplus, the reinforcement and the number of days. The head-count comes
    from r₁x + e = r₂(x − f); the total number of rooms is then *computed*
    from the days, which is what keeps part Б whole — before, the total was
    drawn and only one combination in nine divided evenly.
    """
    for _ in range(_ATTEMPTS):
        ra = rng.choice([2, 3, 4])
        rb = ra + rng.choice([1, 1, 2])
        fewer = rng.choice([2, 3, 4])
        surplus = rng.randint(1, 8)
        x = F(surplus + rb * fewer, rb - ra)
        if x.denominator != 1 or not 6 <= x <= 20 or x - fewer < 3:
            continue
        x = int(x)
        join = rng.choice([2, 3, 4, 5])
        days = rng.choice([3, 4, 5, 6])
        total = ra * x * (days + 1) + rb * (x - fewer + join) * days
        if total % 10 and rng.random() < 0.9:
            continue                        # the papers favour round totals
        break
    else:
        raise Retry("no brigade draw closed")

    word = {2: "двама", 3: "трима", 4: "четирима"}[fewer]
    join_word = {2: "двама", 3: "трима", 4: "четирима", 5: "петима"}[join]
    # (they do, one does, the unit, one unit)
    they, one, unit, unit1 = rng.choice([
        ("боядисват", "боядисва", "стаи", "стая"),
        ("шпакловат", "шпаклова", "стаи", "стая"),
        ("облицоват с плочки", "облицова с плочки", "бани", "баня"),
    ])
    return Part2Item(
        code=f"word_brigades_{ra}_{rb}_{fewer}_{surplus}_{join}_{days}_{unit}_{they}",
        topic="open_word_problem",
        stem=(f"Две строителни бригади {they} комплекс, състоящ се от еднакви {unit}. "
              f"В едната бригада всеки от работниците {one} по ${ra}$ {unit} "
              f"дневно. В другата бригада работниците са с {word} по-малко от първата и "
              f"всеки от тях {one} по ${rb}$ {unit} дневно. За един ден "
              f"работниците от втората бригада {they} с ${surplus}$ "
              f"{unit if surplus != 1 else unit1} повече от тези от първата бригада."),
        parts=(
            "А) Намерете броя на работниците във всяка от бригадите.",
            f"Б) Двете бригади заедно трябва да {they} ${total}$ {unit} от "
            f"комплекса. Първата бригада започва работа един ден по-рано, а към втората "
            f"бригада се присъединяват още {join_word} работници. По колко дни е работила "
            f"всяка от бригадите?",
        ),
        points=(5, 6),
        answers=(f"{x} и {x - fewer} работници",
                 f"първата {days + 1} дни, втората {days} дни"),
        marking=(
            f"А) Означаване с $x$ на работниците в първата бригада — 1 т.; уравнение "
            f"${ra}x + {surplus} = {rb}\\left(x - {fewer}\\right)$ — 2 т.; $x = {x}$ — 1 т.; "
            f"отговор ${x}$ и ${x - fewer}$ работници — 1 т.\n"
            f"Б) Дневна производителност ${ra * x}$ и ${rb * (x - fewer + join)}$ {unit} — 2 т.; "
            f"уравнение ${ra * x}\\left(y + 1\\right) + {rb * (x - fewer + join)}y = {total}$ — 2 т.; "
            f"$y = {days}$ — 1 т.; отговор ${days + 1}$ и ${days}$ дни — 1 т."
        ),
    )


_OUTPUT_CONTEXTS = [
    # (who, plans to, actually, unit TeX, unit plain, thing, what came out)
    ("Бригада дървосекачи", "да добива", "добива", r"\ \text{m}^3", "m³",
     "дървен материал", "добитият материал е"),
    ("Цех за мебели", "да произвежда", "произвежда", "", "", "шкафа",
     "произведените шкафове са"),
    ("Печатница", "да отпечатва", "отпечатва", "", "", "книги",
     "отпечатаните книги са"),
    ("Ферма", "да прибира", "прибира", r"\ \text{t}", "t", "зърно",
     "прибраното зърно е"),
    ("Пекарна", "да изпича", "изпича", "", "", "хляба", "изпечените хлябове са"),
]


@part2("open_word_problem")
def plan_versus_actual_output(rng: random.Random) -> Part2Item:
    """2024 Q22: planned rate, actual rate, finished k days early with a surplus.

    The paper's 75 → 84 m³/day, 3 days early, 180 m³ over gives 48 planned
    days, 3600 m³ planned against 3780 m³ produced, and a 5% increase. Free:
    the two rates, the planned days and how early; the surplus is derived.
    """
    for _ in range(_ATTEMPTS):
        p = rng.choice(range(40, 121, 5))
        q = p + rng.choice([4, 5, 6, 8, 9, 10, 12, 15, 20])
        early = rng.choice([2, 3, 4, 5])
        T = rng.randint(15, 60)
        surplus = q * (T - early) - p * T
        if surplus < 20 or surplus % 5:
            continue
        pct = F(surplus * 100, p * T)
        if not _dec(pct, 1):
            continue
        break
    else:
        raise Retry("no plan/actual draw closed")

    who, plan, actual, u, u_plain, thing, result = rng.choice(_OUTPUT_CONTEXTS)
    amount = lambda n: f"${n}{u}$ {thing}"
    plain = lambda n: f"{n} {u_plain}" if u_plain else f"{n}"
    return Part2Item(
        code=f"word_plan_{p}_{q}_{early}_{T}_{thing}",
        topic="open_word_problem",
        stem=(f"{who} планира {plan} по {amount(p)} на ден. В действителност "
              f"{actual} по {amount(q)} на ден и завършва работата ${early}$ дни "
              f"по-рано от предвиденото време. Оказва се, че {result} с "
              f"{amount(surplus)} повече от планираното."),
        parts=(
            "А) За колко дни е била планирана работата?",
            "Б) Какво количество е било планирано и какво е произведено реално?",
            "В) С колко процента е увеличен планираният обем?",
        ),
        points=(7, 2, 2),
        answers=(f"{T} дни",
                 f"планирано {plain(p * T)}, реално {plain(q * (T - early))}",
                 f"{num_plain(pct)}%"),
        marking=(
            f"А) Означаване с $x$ на планираните дни — 1 т.; реалните дни $x - {early}$ — 1 т.; "
            f"уравнение ${q}\\left(x - {early}\\right) = {p}x + {surplus}$ — 3 т.; решаване — 1 т.; "
            f"отговор ${T}$ дни — 1 т.\n"
            f"Б) ${p * T}$ и ${q * (T - early)}$ — 2 т.\n"
            f"В) $\\frac{{{surplus}}}{{{p * T}}} \\cdot 100\\%$ — 1 т.; ${num_tex(pct)}\\%$ — 1 т."
        ),
    )


_BROTHERS = [("Иван", "Стоян"), ("Петър", "Георги"), ("Николай", "Димитър"),
             ("Мартин", "Калоян"), ("Борис", "Васил")]


@part2("open_word_problem")
def two_tanks_of_fuel(rng: random.Random) -> Part2Item:
    """2020 Q22: two tanks in a ratio, one topped up and one drawn down, then
    driven dry at different consumptions — with a known gap in distance.

    Paper: ratio 2, +15 L, −10 L, 12 and 8 L/100 km, 150 km apart → x = 29.
    Free: all of those except x, which is solved for and must be whole.
    """
    for _ in range(_ATTEMPTS):
        m = rng.choice([2, 2, 3])
        add, use = rng.choice(range(5, 26, 5)), rng.choice(range(5, 21, 5))
        ci, cs = rng.choice([(12, 8), (10, 6), (9, 6), (12, 9), (10, 8), (8, 5)])
        x = rng.randint(12, 40)
        big = m * x - use
        if big <= 5:
            continue
        ds = F(100 * (x + add), cs)
        di = F(100 * big, ci)
        gap = ds - di
        if ds.denominator != 1 or di.denominator != 1 or gap <= 0 or gap % 10:
            continue
        break
    else:
        raise Retry("no fuel draw closed")

    a, b = rng.choice(_BROTHERS)
    times = {2: "два пъти", 3: "три пъти"}[m]
    return Part2Item(
        code=f"word_fuel_{m}_{add}_{use}_{ci}_{cs}_{x}",
        topic="open_word_problem",
        stem=(f"В четвъртък в резервоара на автомобила на {a} имало {times} повече "
              f"гориво, отколкото в резервоара на автомобила на брат му {b}. В петък {b} "
              f"долял ${add}$ L гориво в автомобила си, а {a} изразходвал ${use}$ L от "
              f"горивото в автомобила си. В събота всеки от тях тръгнал на път със своя "
              f"автомобил и изразходвал цялото налично гориво. Оказало се, че {b} изминал "
              f"${int(gap)}$ km по-дълго разстояние от брат си. Автомобилът на {a} "
              f"изразходва ${ci}$ L на $100$ km, а този на {b} — ${cs}$ L на $100$ km. "
              f"Нека $x$ е количеството гориво в четвъртък в резервоара на {b}."),
        parts=(
            f"А) Изразете чрез $x$ какво разстояние е изминал в събота {b}.",
            f"Б) Изразете чрез $x$ какво разстояние е изминал в събота {a}.",
            f"В) Намерете количеството гориво в четвъртък в резервоара на {a}.",
            f"Г) Намерете колко километра е изминал в събота {b}.",
        ),
        points=(2, 2, 4, 3),
        answers=(f"100(x + {add})/{cs} km",
                 f"100({m}x - {use})/{ci} km",
                 f"{m * x} L",
                 f"{int(ds)} km"),
        marking=(
            f"А) $\\dfrac{{100\\left(x + {add}\\right)}}{{{cs}}}$ km — 2 т.\n"
            f"Б) $\\dfrac{{100\\left({m}x - {use}\\right)}}{{{ci}}}$ km — 2 т.\n"
            f"В) Уравнение $\\dfrac{{100\\left(x + {add}\\right)}}{{{cs}}} - "
            f"\\dfrac{{100\\left({m}x - {use}\\right)}}{{{ci}}} = {int(gap)}$ — 2 т.; "
            f"$x = {x}$ — 1 т.; отговор ${m * x}$ L — 1 т.\n"
            f"Г) ${int(ds)}$ km — 3 т."
        ),
    )


@part2("open_word_problem", band="medium")
def car_catches_truck(rng: random.Random) -> Part2Item:
    """2022 Q21: B lies between A and C; a truck leaves B, a car leaves A later
    and catches it some distance before C.

    Paper: AB = 45 km, truck 60 km/h at 9:00, car 85 km/h at 10:45, caught 34 km
    before C → 16:45, arrives 17:09, AC = 544 km, 32,64 L at 6 L/100 km. Free:
    everything but the catch-up time, which must fall on a quarter hour.
    """
    for _ in range(_ATTEMPTS):
        ab = rng.choice(range(20, 71, 5))
        vt = rng.choice([50, 55, 60, 65, 70])
        vc = vt + rng.choice([15, 20, 25, 30])
        t0 = rng.choice([7, 8, 9]) * 60 + rng.choice([0, 30])
        lead = rng.choice([30, 45, 60, 75, 90, 105])
        gap = ab + F(vt * lead, 60)
        catch = gap / (vc - vt) * 60                     # minutes
        if catch.denominator != 1 or catch % 15 or not 60 <= catch <= 360:
            continue
        rest = rng.choice(range(10, 61))
        tail = F(rest * 60, vc)
        if tail.denominator != 1:
            continue
        ac = vc * catch / 60 + rest
        per100 = rng.choice([5, 6, 7, 8])
        fuel = ac * per100 / 100
        if not _dec(fuel, 2) or ac.denominator != 1:
            continue
        break
    else:
        raise Retry("no catch-up draw closed")

    start_car = t0 + lead
    return Part2Item(
        code=f"word_catch_{ab}_{vt}_{vc}_{t0}_{lead}_{rest}_{per100}",
        topic="open_word_problem",
        stem=(f"Град $B$ е между градовете $A$ и $C$, а разстоянието между градовете $A$ "
              f"и $B$ е ${ab}$ km. В {_clock_tex(t0)} от град $B$ към град $C$ тръгва "
              f"камион със скорост ${vt}$ km/h, а в {_clock_tex(start_car)} от град $A$ "
              f"към $C$ тръгва лека кола със скорост ${vc}$ km/h, която настига камиона "
              f"${rest}$ km преди град $C$."),
        parts=(
            "А) В колко часà колата е настигнала камиона?",
            "Б) В колко часà леката кола е пристигнала в град $C$?",
            "В) Колко километра е разстоянието от град $A$ до град $C$?",
            f"Г) Колко литра гориво е изразходвала леката кола за пътуването от град $A$ "
            f"до град $C$, ако разходът ѝ за $100$ km е ${per100}$ литра?",
        ),
        points=(5, 2, 2, 2),
        answers=(_clock(start_car + catch), _clock(start_car + catch + tail),
                 f"{num_plain(ac)} km", f"{num_plain(fuel)} L"),
        marking=(
            f"А) Означаване с $x$ на времето на колата до настигането — 1 т.; път на "
            f"камиона ${vt}\\left(x + \\frac{{{lead}}}{{60}}\\right)$ — 1 т.; уравнение "
            f"${vc}x = {vt}\\left(x + \\frac{{{lead}}}{{60}}\\right) + {ab}$ — 2 т.; "
            f"настигане в {_clock(start_car + catch)} — 1 т.\n"
            f"Б) Време за оставащите ${rest}$ km: ${num_tex(tail)}$ min — 1 т.; "
            f"{_clock(start_car + catch + tail)} — 1 т.\n"
            f"В) $AC = {num_tex(ac)}$ km — 2 т.\n"
            f"Г) ${num_tex(fuel)}$ L — 2 т."
        ),
    )
