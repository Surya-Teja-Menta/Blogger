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


def compile_expr(src: str) -> Callable[[float, float], float]:
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
        if t == "a":
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
