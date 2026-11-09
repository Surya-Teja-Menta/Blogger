"""LaTeX that a model leaves in prose ("(\\bar X_n - \\mu)\\sqrt{n}") turned into the symbols themselves ("(X̄ₙ − μ)√n"),
so a printed report or a blog never shows backslashes. Only paragraphs that contain LaTeX are touched."""
import re

GREEK = {"alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε", "zeta": "ζ", "eta": "η",
         "theta": "θ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ",
         "phi": "φ", "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ",
         "Lambda": "Λ", "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω"}
SYMBOLS = {"infty": "∞", "to": "→", "rightarrow": "→", "Rightarrow": "⇒", "leftarrow": "←", "dots": "…", "ldots": "…",
           "cdots": "⋯", "cdot": "·", "times": "×", "div": "÷", "pm": "±", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥",
           "neq": "≠", "ne": "≠", "approx": "≈", "sim": "∼", "equiv": "≡", "propto": "∝", "sum": "∑", "prod": "∏",
           "int": "∫", "partial": "∂", "nabla": "∇", "in": "∈", "notin": "∉", "subset": "⊂", "cup": "∪", "cap": "∩",
           "forall": "∀", "exists": "∃", "mid": "|", "ell": "ℓ", "quad": " ", "qquad": "  ", "log": "log", "ln": "ln",
           "exp": "exp", "sin": "sin", "cos": "cos", "min": "min", "max": "max", "lim": "lim", "Pr": "Pr"}
BLACKBOARD = {"R": "ℝ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "C": "ℂ"}
SUP = dict(zip("0123456789+-n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ"))
SUB = dict(zip("0123456789+-nijkxm", "₀₁₂₃₄₅₆₇₈₉₊₋ₙᵢⱼₖₓₘ"))
HAS_LATEX = re.compile(r"\\[A-Za-z]{2,}|\\[()\[\]]|\$[^$\n]*\\")


def _script(text: str, mark: str, table: dict) -> str:
    def one(m):
        body = m.group(1) if m.group(1) is not None else m.group(2)
        if body and all(c in table for c in body):
            return "".join(table[c] for c in body)
        return f"{mark}({body})" if body and len(body) > 1 else f"{mark}{body}"
    return re.sub(re.escape(mark) + r"(?:\{([^{}]*)\}|(\w))", one, text)


def _convert(p: str) -> str:
    p = re.sub(r"\$\$?([^$\n]*?)\$\$?", r"\1", p)
    p = re.sub(r"\\[()\[\]]", "", p)
    for _ in range(3):                                           # \frac{a}{b}, \sqrt{x}, \bar{X} (also nested)
        p = re.sub(r"\\d?frac\{([^{}]*)\}\{([^{}]*)\}", lambda m: f"({m.group(1)})/({m.group(2)})", p)
        p = re.sub(r"\\sqrt\{([^{}]*)\}", lambda m: "√" + (m.group(1) if len(m.group(1)) == 1 else f"({m.group(1)})"), p)
        p = re.sub(r"\\(?:text|mathrm|mathbf|mathit|operatorname|textbf)\{([^{}]*)\}", r"\1", p)
        p = re.sub(r"\\mathbb\{(\w)\}", lambda m: BLACKBOARD.get(m.group(1), m.group(1)), p)
        p = re.sub(r"\\(?:bar|overline)\s*\{([^{}]*)\}", lambda m: m.group(1)[:1] + "\u0304" + m.group(1)[1:], p)
        p = re.sub(r"\\hat\s*\{([^{}]*)\}", lambda m: m.group(1)[:1] + "\u0302" + m.group(1)[1:], p)
    p = re.sub(r"\\(?:bar|overline)\s+([A-Za-z])", lambda m: m.group(1) + "\u0304", p)
    p = re.sub(r"\\hat\s+([A-Za-z])", lambda m: m.group(1) + "\u0302", p)
    p = re.sub(r"\\sqrt\s*(\w)", r"√\1", p)
    p = re.sub(r"\\(?:left|right|big|Big)\b\s*", "", p)
    p = re.sub(r"\\[,;:! ]", " ", p)
    p = re.sub(r"\\([A-Za-z]+)", lambda m: GREEK.get(m.group(1)) or SYMBOLS.get(m.group(1)) or m.group(1), p)
    p = _script(_script(p, "^", SUP), "_", SUB)
    return re.sub(r"[ \t]{2,}", " ", p).replace("\\{", "{").replace("\\}", "}")


def plain_math(text: str) -> str:
    """`text` with LaTeX turned into plain symbols, paragraph by paragraph; text without LaTeX is returned as is."""
    return "\n\n".join(_convert(p) if HAS_LATEX.search(p) else p for p in text.split("\n\n"))
