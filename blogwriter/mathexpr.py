"""The graph shots' expression grammar (same as video/src/expr.js): numbers, x, one parameter a, + - * / ^,
brackets, sin cos tan exp log sqrt abs, pi and e. Used to check a model's curve before the video is made: it
must parse and be finite over most of its range. Never eval()."""
import math
import re
from typing import Callable, List, Optional

FUNCS = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp, "log": math.log, "sqrt": math.sqrt,
         "abs": abs}
CONSTS = {"pi": math.pi, "e": math.e}
TOKEN = re.compile(r"\d*\.?\d+(?:e[+-]?\d+)?|[a-z]+|[-+*/^()]")


def compile_expr(src: str, second: str = "a") -> Callable[[float, float], float]:
    """f(x, second): a curve's parameter "a", or "y" for a surface over x and y."""
    text = str(src).lower()
    toks = TOKEN.findall(text)
    if "".join(toks) != re.sub(r"\s+", "", text) or not toks or len(toks) > 80:
        raise ValueError(f"bad expression {src!r}")
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take(want=None):
        t = peek()
        if t is None or (want and t != want):
            raise ValueError(f"expected {want or 'more'} in {src!r}")
        pos[0] += 1
        return t

    def expr():
        f = term()
        while peek() in ("+", "-"):
            op, l, r = take(), f, term()
            f = (lambda l, r: lambda x, a: l(x, a) + r(x, a))(l, r) if op == "+" else \
                (lambda l, r: lambda x, a: l(x, a) - r(x, a))(l, r)
        return f

    def term():
        f = unary()
        while peek() in ("*", "/"):
            op, l, r = take(), f, unary()
            f = (lambda l, r: lambda x, a: l(x, a) * r(x, a))(l, r) if op == "*" else \
                (lambda l, r: lambda x, a: l(x, a) / r(x, a))(l, r)
        return f

    def unary():
        if peek() == "-":
            take()
            f = unary()
            return lambda x, a: -f(x, a)
        return power()

    def power():
        base = atom()
        if peek() != "^":
            return base
        take()
        ex = unary()
        return lambda x, a: base(x, a) ** ex(x, a)

    def atom():
        t = take()
        if re.match(r"\d|\.", t):
            v = float(t)
            return lambda x, a: v
        if t == "x":
            return lambda x, a: x
        if t == second:
            return lambda x, a: a
        if t in CONSTS:
            v = CONSTS[t]
            return lambda x, a: v
        if t in FUNCS:
            fn = FUNCS[t]
            take("(")
            inner = expr()
            take(")")
            return lambda x, a: fn(inner(x, a))
        if t == "(":
            inner = expr()
            take(")")
            return inner
        raise ValueError(f"unknown {t!r} in {src!r}")

    f = expr()
    if pos[0] != len(toks):
        raise ValueError(f"trailing {toks[pos[0]]!r} in {src!r}")
    return f


def finite_share(f: Callable, x0: float, x1: float, params: List[float]) -> float:
    """Share of sample points (over x and the parameter's values) where the curve is a real, finite number."""
    good = total = 0
    for a in params:
        for k in range(81):
            x = x0 + (x1 - x0) * k / 80
            total += 1
            try:
                y = f(x, a)
                good += isinstance(y, float) and math.isfinite(y) and abs(y) < 1e6
            except (ValueError, ZeroDivisionError, OverflowError, TypeError):
                pass
    return good / max(1, total)


def check_graph(raw) -> Optional[dict]:
    """A graph shot the video can draw, or None."""
    if not isinstance(raw, dict):
        return None
    try:
        x0, x1 = (float(v) for v in raw.get("x", [-5, 5])[:2])
    except (TypeError, ValueError):
        return None
    if not x0 < x1 or x1 - x0 > 1e4:
        return None
    param = raw.get("param") if isinstance(raw.get("param"), dict) else None
    try:
        sweep = [float(param["from"]), float(param["to"])] if param else []
    except (KeyError, TypeError, ValueError):
        sweep = []
    curves = []
    for c in (raw.get("curves") or [])[:3]:
        if not isinstance(c, dict):
            continue
        fn = str(c.get("fn", "")).strip()
        tex = str(c.get("tex", "")).strip()[:60]
        try:
            f = compile_expr(fn)
        except ValueError:
            continue
        if finite_share(f, x0, x1, sweep or [1.0]) < 0.8:
            continue
        curves.append({"fn": fn, "tex": tex})
    if not curves:
        return None
    uses_a = any(re.search(r"(?<![a-z])a(?![a-z])", c["fn"].lower()) for c in curves)
    mark = raw.get("mark") if raw.get("mark") in ("tangent", "area", "point") else ""
    out = {"curves": curves, "x": [x0, x1], "mark": mark}
    if uses_a:
        out["param"] = {"from": sweep[0] if sweep else 1.0, "to": sweep[1] if sweep else 1.0}
    return out


SURFACE_MARKS = ("descent", "minimum", "residuals", "")


def check_surface(raw) -> Optional[dict]:
    """A 3D surface shot the video can draw (z = f(x, y) over a box), or None: the function must parse, be finite
    almost everywhere and not be flat. Data points (for residuals) are kept inside the box."""
    if not isinstance(raw, dict):
        return None
    fn = str(raw.get("fn", "")).strip()[:80]
    try:
        f = compile_expr(fn, second="y")
    except ValueError:
        return None

    def span(key):
        try:
            lo, hi = sorted(float(v) for v in (raw.get(key) or [-3, 3])[:2])
        except (TypeError, ValueError):
            lo, hi = -3.0, 3.0
        return (lo, hi) if 0 < hi - lo <= 1e4 else (-3.0, 3.0)

    (x0, x1), (y0, y1) = span("x"), span("y")
    zs = []
    for i in range(21):
        for j in range(21):
            try:
                z = f(x0 + (x1 - x0) * i / 20, y0 + (y1 - y0) * j / 20)
            except (ValueError, ZeroDivisionError, OverflowError, TypeError):
                continue
            if isinstance(z, float) and math.isfinite(z) and abs(z) < 1e6:
                zs.append(z)
    if len(zs) < 0.9 * 441 or max(zs) - min(zs) < 1e-6:
        return None
    mark = raw.get("mark") if raw.get("mark") in SURFACE_MARKS else ""

    def inside(v, lo, hi):
        return min(hi, max(lo, float(v)))

    points = []
    for pt in (raw.get("points") or [])[:30]:
        try:
            x, y, z = (float(v) for v in pt[:3])
        except (TypeError, ValueError):
            continue
        if all(math.isfinite(v) for v in (x, y, z)):
            points.append([round(inside(x, x0, x1), 4), round(inside(y, y0, y1), 4), round(z, 4)])
    if mark == "residuals" and len(points) < 4:
        mark = ""
    try:
        sx, sy = (float(v) for v in (raw.get("start") or [])[:2])
        start = [inside(sx, x0, x1), inside(sy, y0, y1)]
    except (TypeError, ValueError):
        start = [x0 + 0.85 * (x1 - x0), y0 + 0.2 * (y1 - y0)]       # a high corner, for the ball to roll from
    return {"fn": fn, "tex": str(raw.get("tex", "")).strip()[:60], "x": [x0, x1], "y": [y0, y1], "mark": mark,
            "start": [round(v, 4) for v in start], "points": points if mark == "residuals" else []}
