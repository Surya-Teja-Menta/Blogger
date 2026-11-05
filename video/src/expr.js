// A tiny, safe maths expression compiler for graph shots: numbers, x, one parameter a, + - * / ^, brackets,
// sin cos tan exp log sqrt abs, pi and e. No eval: anything else is rejected. blogwriter/mathexpr.py is the same
// grammar in Python (it checks every expression before the video is made).
const FUNCS = {sin: Math.sin, cos: Math.cos, tan: Math.tan, exp: Math.exp, log: Math.log, sqrt: Math.sqrt, abs: Math.abs};
const CONSTS = {pi: Math.PI, e: Math.E};

export function compile(src) {
  const toks = String(src).toLowerCase().match(/\d*\.?\d+(?:e[+-]?\d+)?|[a-z]+|[-+*/^()]/g) || [];
  if (toks.join("") !== String(src).toLowerCase().replace(/\s+/g, "")) throw new Error(`bad expression ${src}`);
  let i = 0;
  const peek = () => toks[i];
  const take = (t) => {
    if (t && toks[i] !== t) throw new Error(`expected ${t} in ${src}`);
    return toks[i++];
  };
  const expr = () => {
    let f = term();
    while (peek() === "+" || peek() === "-") {
      const op = take(), l = f, r = term();
      f = op === "+" ? (x, a) => l(x, a) + r(x, a) : (x, a) => l(x, a) - r(x, a);
    }
    return f;
  };
  const term = () => {
    let f = unary();
    while (peek() === "*" || peek() === "/") {
      const op = take(), l = f, r = unary();
      f = op === "*" ? (x, a) => l(x, a) * r(x, a) : (x, a) => l(x, a) / r(x, a);
    }
    return f;
  };
  const unary = () => {
    if (peek() === "-") {
      take();
      const f = unary();
      return (x, a) => -f(x, a);
    }
    return power();
  };
  const power = () => {
    const base = atom();
    if (peek() !== "^") return base;
    take();
    const ex = unary();
    return (x, a) => Math.pow(base(x, a), ex(x, a));
  };
  const atom = () => {
    const t = take();
    if (t === undefined) throw new Error(`unexpected end of ${src}`);
    if (/^\d|^\./.test(t)) {
      const v = parseFloat(t);
      return () => v;
    }
    if (t === "x") return (x) => x;
    if (t === "a") return (x, a) => a;
    if (t in CONSTS) return () => CONSTS[t];
    if (t in FUNCS) {
      take("(");
      const f = expr();
      take(")");
      return (x, a) => FUNCS[t](f(x, a));
    }
    if (t === "(") {
      const f = expr();
      take(")");
      return f;
    }
    throw new Error(`unknown ${t} in ${src}`);
  };
  const f = expr();
  if (i !== toks.length) throw new Error(`trailing ${toks[i]} in ${src}`);
  return f;
}
