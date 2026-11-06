// Diagram parts that show chance and data happening, not described. The diagram designer (blogwriter/diagram.py)
// places them in a region of its canvas, for any topic. Nothing here knows the subject.
//  - Samples: random values (d3-random, seeded) drop one by one into a histogram (d3-array bins, d3-scale axis).
//    The first few fall slowly, then time speeds up like a time-lapse. Each dot can be the average of n values. On
//    its cue the jagged outline melts into the smooth bell that fits it (flubber), and the average is marked.
//  - Physics: balls dropped into a real physics simulation (matter-js), through an optional peg lattice whose pegs
//    light up when struck, into optional bins. Slow motion first, then fast-forward, then the bell that fits the pile.
// Every value comes from a seeded generator or a fixed-step simulation, so every render of a frame is identical
// (each render machine recomputes the same simulation from the start).
import React, {useMemo} from "react";
import Matter from "matter-js";
import {randomBernoulli, randomBeta, randomExponential, randomInt, randomLcg, randomNormal, randomUniform} from "d3-random";
import {deviation, mean} from "d3-array";
import {scaleLinear} from "d3-scale";
import {curveCatmullRom, line} from "d3-shape";
import {interpolate as morphPath} from "flubber";
import {clamp, ease} from "./fx";
import {Pen} from "./direct";
import {pop} from "./motion";
import {C, FONT, alpha} from "./theme";

export const seedOf = (text) => {
  let h = 2166136261;
  for (const ch of String(text || "")) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return ((h >>> 0) % 100000) / 100000;
};
const hex = (c) => {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(c || "").trim());
  return m ? [0, 2, 4].map((k) => parseInt(m[1].slice(k, k + 2), 16)) : null;
};
export const mix = (a, b, t) => {
  const A = hex(a), B = hex(b);
  if (!A || !B) return t < 0.5 ? a : b;
  return `rgb(${A.map((v, k) => Math.round(v + (B[k] - v) * t)).join(",")})`;
};
const fmt = (v) => (Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2));
const nice = (t) => String(+t.toFixed(3));
const txt = (size, color, weight = 800, font = FONT.body) => ({fill: color || C.muted, fontFamily: font, fontWeight: weight, fontSize: size,
                                                                style: {paintOrder: "stroke", stroke: alpha(C.bg, 0.8), strokeWidth: 6}});

// where one raw value comes from, on 0..1 (dice: 1..6; coin: 0 or 1)
export const SOURCES = {
  uniform: (src) => randomUniform.source(src)(0, 1),
  skewed: (src) => randomBeta.source(src)(1.5, 5),
  exponential: (src) => {
    const e = randomExponential.source(src)(5);
    return () => { let v = e(); while (v > 1) v = e(); return v; };
  },
  bimodal: (src) => {
    const a = randomBeta.source(src)(4, 14), b = randomBeta.source(src)(14, 4), c = randomUniform.source(src)(0, 1);
    return () => (c() < 0.5 ? a() : b());
  },
  normal: (src) => {
    const g = randomNormal.source(src)(0.5, 0.14);
    return () => Math.min(1, Math.max(0, g()));
  },
  dice: (src) => randomInt.source(src)(1, 7),
  coin: (src) => randomBernoulli.source(src)(0.5),
};

// ---- samples: e = {source, n, count, lo, hi, unit, text, mean, fit: {at}}; rect = [x0, y0, x1, y1] in pixels ---
export const Samples = ({e, rect, frame, end, seed = 0, vertical}) => {
  const source = SOURCES[e.source] ? e.source : "skewed";
  const n = Math.max(1, Math.min(100, Math.round(e.n || 1)));
  const draws = Math.max(30, Math.min(600, Math.round(e.count || 300)));
  const dice = source === "dice", coin = source === "coin";
  const lo = dice ? 1 : e.lo ?? 0, hi = dice ? 6 : e.hi ?? (coin ? 1 : 100);
  const fs = vertical ? 32 : 26;
  const box = {x0: rect[0] + 8, x1: rect[2] - 8, y0: rect[1] + fs * 3.6, y1: rect[3] - fs * 2.2};
  const start = e.at ?? 0;

  const data = useMemo(() => {
    const src = randomLcg(seedOf(`${seed}|${source}|${n}|${draws}`));
    const one = SOURCES[source](src);
    const draw = () => {
      let sum = 0;
      for (let j = 0; j < n; j++) sum += one();
      return dice ? sum / n : lo + ((hi - lo) * sum) / n;
    };
    const vals = Array.from({length: draws}, draw);
    // one bin per possible value when there are few (dice, coins), else enough to show the shape
    const step = dice ? 1 / n : coin ? (hi - lo) / n : 0;
    const exact = step && (hi - lo) / step <= 40;
    const B = exact ? Math.round((hi - lo) / step) + 1 : Math.round(Math.min(60, Math.max(20, 16 + 5 * Math.sqrt(n))));
    const w = exact ? step : (hi - lo) / B;
    const first = exact ? lo - step / 2 : lo;
    const binOf = (v) => Math.max(0, Math.min(B - 1, Math.floor((v - first) / w + 1e-9)));
    const finals = new Array(B).fill(0);
    vals.forEach((v) => finals[binOf(v)]++);
    const pop1 = Array.from({length: 1200}, () => (dice ? one() : lo + (hi - lo) * one()));
    return {vals, bins: vals.map(binOf), B, w, first, finals, top: Math.max(...finals), m: mean(vals), sd: deviation(vals) || w, pop1};
  }, [seed, source, n, draws, lo, hi]);

  const X = scaleLinear().domain([data.first, data.first + data.B * data.w]).range([box.x0, box.x1]);
  const Y = scaleLinear().domain([0, data.top / 0.85]).range([box.y1, box.y0]);
  const bw = (box.x1 - box.x0) / data.B;

  // when each dot lands: the first few slowly (the idea), then faster and faster (a time-lapse)
  const run = Math.max(60, end - start);
  const intro = n > 1 ? 3 : 2;
  const t0 = start + 8, gap = Math.max(16, Math.min(36, run * 0.08)), t1 = start + run * 0.7, fall = 14;
  const rest0 = t0 + (intro + 0.5) * gap;
  const lands = data.vals.map((_, k) => (k < intro ? t0 + (k + 1) * gap
    : rest0 + (t1 - rest0) * Math.sqrt((k - intro + 1) / Math.max(1, draws - intro))));
  const counts = new Array(data.B).fill(0), last = new Array(data.B).fill(-99);
  const flying = [];
  data.vals.forEach((v, k) => {
    if (frame >= lands[k] + fall) { counts[data.bins[k]]++; last[data.bins[k]] = lands[k] + fall; }
    else if (frame >= lands[k]) flying.push(k);
  });
  const landed = counts.reduce((a, b) => a + b, 0);

  // the bell that fits, and the histogram's outline that melts into it
  const tB = e.fit ? e.fit.at ?? start + run * 0.8 : Infinity;
  const pdf = (x) => Math.exp(-(((x - data.m) / data.sd) ** 2) / 2) / (data.sd * Math.sqrt(2 * Math.PI));
  const bellPts = useMemo(() => Array.from({length: 61}, (_, k) => {
    const x = data.first + (data.B * data.w * k) / 60;
    return [X(x), Math.min(box.y1, Y(draws * data.w * pdf(x)))];
  }), [data, rect.join(",")]);
  const melt = useMemo(() => {
    if (!e.fit) return null;
    const steps = [[box.x0, box.y1]];
    data.finals.forEach((c, b) => { steps.push([box.x0 + b * bw, Y(c)], [box.x0 + (b + 1) * bw, Y(c)]); });
    steps.push([box.x1, box.y1]);
    try { return morphPath(steps, [[box.x0, box.y1], ...bellPts, [box.x1, box.y1]], {maxSegmentLength: 12}); } catch (err) { return null; }
  }, [data, bellPts, !!e.fit]);
  const q = Number.isFinite(tB) ? ease((frame - tB) / 26) : 0;

  const axis = ease((frame - start) / 16);
  const ticks = X.copy().domain([lo, hi]).ticks(6).filter((t) => t >= lo - 1e-9 && t <= hi + 1e-9);
  const colOf = (b) => mix(C.accent, C.cool || C.accent, Math.min(1, Math.abs(b + 0.5 - (data.m - data.first) / data.w) / (data.B * 0.35)));
  // the inset (where single values come from) and the counter keep to the side away from the average and its label
  const where = (data.m - data.first) / (data.B * data.w);
  const iw = Math.min(320, (box.x1 - box.x0) * 0.32), cw = Math.max(fs * 5, String(e.text || "").length * fs * 0.56) + 28;
  const inset = n > 1 ? {x: where < 0.4 ? box.x1 - iw - cw : box.x0, y: rect[1], w: iw, h: fs * 3.1} : null;
  const counterX = where > 0.6 ? (inset ? inset.x + iw + 20 : box.x0) : box.x1;
  const counterAnchor = where > 0.6 ? "start" : "end";
  const markAt = Number.isFinite(tB) ? tB : e.mean ? start + run * 0.85 : Infinity;

  return (
    <g>
      {inset && (() => {
        const pb = 22, pc = new Array(pb).fill(0);
        data.pop1.forEach((v) => { pc[Math.max(0, Math.min(pb - 1, Math.floor(((v - lo) / (hi - lo || 1)) * pb)))]++; });
        const pm = Math.max(...pc), o = pop(frame - start - 4);
        return (
          <g opacity={o}>
            <rect x={inset.x} y={inset.y} width={inset.w} height={inset.h} rx={14} fill={alpha(C.panel, 0.85)} stroke={alpha(C.text, 0.15)} strokeWidth={2}/>
            {pc.map((c, b) => {
              const h = (c / pm) * (inset.h - 20) * ease((frame - start - 6 - b) / 12);
              return <rect key={b} x={inset.x + 10 + (b * (inset.w - 20)) / pb} width={(inset.w - 20) / pb - 2} y={inset.y + inset.h - 8 - h}
                           height={h} fill={alpha(C.muted, 0.55)} rx={2}/>;
            })}
          </g>
        );
      })()}
      <line x1={box.x0} y1={box.y1} x2={box.x0 + (box.x1 - box.x0) * axis} y2={box.y1} stroke={alpha(C.text, 0.6)} strokeWidth={3}/>
      {ticks.map((t, k) => (
        <g key={k} opacity={clamp((frame - start - 4 - k * 2) / 8)}>
          <line x1={X(t)} x2={X(t)} y1={box.y1} y2={box.y1 + 10} stroke={alpha(C.text, 0.5)} strokeWidth={2}/>
          <text x={X(t)} y={box.y1 + fs * 1.4} textAnchor="middle" {...txt(fs)}>{nice(t)}</text>
        </g>
      ))}
      {e.unit && <text x={box.x1} y={box.y1 + fs * 2.6} textAnchor="end" {...txt(fs)} opacity={axis}>{e.unit}</text>}
      {counts.map((c, b) => {
        const flash = clamp(1 - (frame - last[b]) / 9), h = box.y1 - Y(c);
        return c > 0 && <rect key={b} x={box.x0 + b * bw + 1.5} width={Math.max(1, bw - 3)} y={box.y1 - h} height={h} rx={Math.min(6, bw / 4)}
                              fill={flash > 0 ? mix(colOf(b), "#ffffff", flash * 0.5) : colOf(b)} opacity={1 - 0.7 * q}/>;
      })}
      {flying.map((k) => {
        const b = data.bins[k], t = clamp((frame - lands[k]) / fall), top = Y(counts[b] + 1);
        const fromInset = inset && k < intro;
        const xs = fromInset ? inset.x + inset.w + 26 : X(data.vals[k]), ys = fromInset ? inset.y + inset.h / 2 : box.y0 - 30;
        const x = xs + (box.x0 + (b + 0.5) * bw - xs) * ease(t * 1.4), y = ys + (top - ys) * t * t;
        return <circle key={k} cx={x} cy={y} r={k < intro ? 14 : 8} fill={C.accent} stroke={C.panel} strokeWidth={3}
                       style={{filter: `drop-shadow(0 0 10px ${alpha(C.accent, 0.9)})`}}/>;
      })}
      {inset && Array.from({length: intro}, (_, k) => {
        const t = clamp((frame - (lands[k] - gap * 0.8)) / (gap * 0.8));
        if (t <= 0 || t >= 1) return null;
        const cx = inset.x + inset.w + 26, cy = inset.y + inset.h / 2, e2 = ease(t * 1.3);
        return Array.from({length: Math.min(n, 12)}, (_, j) => {
          const sx = inset.x + 14 + ((j * 97 + k * 31) % Math.max(1, inset.w - 28)), sy = inset.y + 12 + ((j * 53) % Math.max(1, inset.h - 24));
          return <circle key={`${k}-${j}`} cx={sx + (cx - sx) * e2} cy={sy + (cy - sy) * e2} r={7 * (1 - 0.5 * e2)}
                         fill={C.cool || C.accent} opacity={1 - clamp((t - 0.8) * 5)}/>;
        });
      })}
      {melt && q > 0 && <path d={melt(q)} fill={alpha(C.accent, 0.18 + 0.1 * q)} stroke={C.hot} strokeWidth={5} strokeLinejoin="round"
                              style={{filter: `drop-shadow(0 0 14px ${alpha(C.hot, 0.6)})`}}/>}
      {e.fit && q >= 1 && <path d={line().curve(curveCatmullRom)(bellPts)} fill="none" stroke={C.hot} strokeWidth={6} pathLength={1}
                                strokeDasharray={1} strokeDashoffset={1 - ease((frame - tB - 26) / 20)}/>}
      {frame > markAt - 10 && (e.mean || e.fit) && (
        <g opacity={clamp((frame - markAt + 10) / 12)}>
          <line x1={X(data.m)} x2={X(data.m)} y1={box.y1} y2={box.y0 - 6} stroke={C.text} strokeWidth={3} strokeDasharray="10 9"/>
          <text x={X(data.m)} y={box.y0 - 18} textAnchor="middle" {...txt(fs * 1.5, C.text, C.weight, FONT.display)}>
            {fmt(data.m)}{e.unit ? ` ${e.unit}` : ""}</text>
        </g>
      )}
      {(e.mean || e.fit) && frame > markAt + 30 && (
        <Pen box={[X(data.m) - fs * 4, box.y0 - fs * 2.4, X(data.m) + fs * 4, box.y0 - 10]} at={markAt + 30} seed={seed + 3} kind="underline"/>
      )}
      <g opacity={clamp((frame - t0) / 10)}>
        <text x={counterX} y={rect[1] + fs * 2} textAnchor={counterAnchor} {...txt(fs * 2.6, C.accent, C.weight, FONT.display)}>{landed}</text>
        {e.text && <text x={counterX} y={rect[1] + fs * 3.2} textAnchor={counterAnchor} {...txt(fs)}>{e.text}</text>}
      </g>
    </g>
  );
};

// ---- physics: e = {balls, pegs (rows), bins, drop: "center" | "spread", text, fit: {at}} ---------------------------
const STEP = 1000 / 60;            // two physics steps per video frame (30 fps)

const simulate = ({rows, bins, balls, sx, sy, rb, rp, cx, left, right, top, binTop, floor, frames, spacing, spread, seed, stuck}) => {
  const {Engine, Bodies, Body, Composite, Events, Sleeping} = Matter;
  const engine = Engine.create({enableSleeping: true});
  engine.gravity.y = 1;
  const fixed = {isStatic: true, restitution: 0.05, friction: 0.02};
  const pegs = [];
  // a staggered lattice: even rows over the bin centres, odd rows over the bin walls, so each peg sends a ball half
  // a bin left or right
  for (let r = 0; r < rows; r++) {
    const first = r % 2 ? left + sx : left + sx / 2, last = r % 2 ? right - sx : right - sx / 2;
    for (let x = first; x <= last + 1e-6; x += sx) {
      pegs.push({x, y: top + r * sy, body: Bodies.circle(x, top + r * sy, rp, {...fixed, label: `peg${pegs.length}`})});
    }
  }
  const walls = [Bodies.rectangle(left - 10, (top + floor) / 2 - 60, 20, floor - top + 160, fixed),
                 Bodies.rectangle(right + 10, (top + floor) / 2 - 60, 20, floor - top + 160, fixed),
                 Bodies.rectangle((left + right) / 2, floor + 20, right - left + 60, 40, fixed)];
  if (bins) for (let j = 1; j < bins; j++) walls.push(Bodies.rectangle(left + j * ((right - left) / bins), (binTop + floor) / 2, 4, floor - binTop, fixed));
  Composite.add(engine.world, [...pegs.map((p) => p.body), ...walls]);
  const hits = pegs.map(() => []);
  let now = 0;
  Events.on(engine, "collisionStart", (ev) => ev.pairs.forEach(({bodyA, bodyB}) => {
    [bodyA, bodyB].forEach((b) => { if (b.label && b.label.startsWith("peg")) hits[+b.label.slice(3)].push(now); });
  }));
  const pos = new Float32Array(frames * balls * 2).fill(NaN);
  const rnd = randomUniform.source(randomLcg(seed))(-1, 1);
  const bodies = [];
  for (let f = 0; f < frames; f++) {
    now = f;
    while (bodies.length < balls && f >= 2 + bodies.length * spacing) {
      const x = spread ? (left + right) / 2 + rnd() * ((right - left) / 2 - rb * 2) : cx + rnd() * 0.8;
      const b = Bodies.circle(x, top - sy * 1.2, rb, {restitution: 0.05, friction: 0.01, frictionAir: 0.03, density: 0.002});
      bodies.push(b);
      Composite.add(engine.world, b);
    }
    Engine.update(engine, STEP);
    Engine.update(engine, STEP);
    bodies.forEach((b, k) => {
      if (b.position.y < stuck && b.speed < 0.08) {           // balanced on a peg or a wall top: knock it off
        Sleeping.set(b, false);
        Body.setVelocity(b, {x: (k % 2 ? 1 : -1) * 0.9, y: 0.2});
      }
      pos[(f * balls + k) * 2] = b.position.x;
      pos[(f * balls + k) * 2 + 1] = b.position.y;
    });
  }
  return {pos, pegs: pegs.map(({x, y}) => ({x, y})), hits, finalX: bodies.map((b) => b.position.x)};
};

export const Physics = ({e, rect, frame, end, seed = 0, vertical}) => {
  const fs = vertical ? 32 : 26;
  const rows = 2 * Math.round(Math.max(0, Math.min(12, e.pegs ?? 10)) / 2);
  const spread = e.drop === "spread" || !rows;
  const bins = e.bins === false ? 0 : rows ? rows + 1 : Math.max(3, Math.min(15, Math.round(e.bins || 9)));
  const cols = bins || 9;
  const W = rect[2] - rect[0], H = rect[3] - rect[1];
  const sx = Math.min(W / cols, (H * 0.95) / (rows * 0.68 + 4.2));      // the bins and the lattice share one width
  const sy = sx * 0.68, rb = sx * 0.15, rp = sx * 0.1;
  const width = cols * sx, cx = (rect[0] + rect[2]) / 2, left = cx - width / 2, right = cx + width / 2;
  const top = rect[1] + Math.max(sy * 2.2, fs * 3.6 + sy * 0.8), floor = rect[3];
  const binTop = bins ? top + rows * sy + (rows ? 6 : 0) : floor;
  // only as many balls as the fullest bin can hold
  const perRow = Math.max(1, Math.floor((sx - 4) / (2 * rb))), layer = 2 * rb * 0.87;
  const choose = (nn, k) => { let r = 1; for (let j = 1; j <= k; j++) r = (r * (nn - j + 1)) / j; return r; };
  const share = rows ? choose(rows, rows / 2) / 2 ** rows : 1.6 / cols;
  const room = bins ? Math.floor((floor - binTop) / layer) * perRow : 400;
  const balls = Math.max(20, Math.min(160, Math.round(e.balls || 110), Math.floor((room / share) * 0.8)));
  // slow motion for the first bounces, then a time-lapse until every ball has landed
  const start = e.at ?? 0, run = Math.max(90, end - start);
  const spacing = 3, need = 2 + balls * spacing + 80;
  const a = run * 0.24, slow = 0.4, done = run * 0.78;
  const speed = Math.min(5, Math.max(1, (need - a * slow) / Math.max(1, done - a)));
  const simAt = (f) => (f < 0 ? 0 : f < a ? f * slow : a * slow + (f - a) * speed);
  const frames = Math.ceil(simAt(run)) + 2;
  const stuck = bins ? binTop - 1 : rows ? top + rows * sy : -Infinity;      // above this a resting ball is stuck
  const sim = useMemo(() => simulate({rows, bins, balls, sx, sy, rb, rp, cx, left, right, top, binTop, floor,
                                      frames, spacing, spread, seed: seedOf(`${seed}|physics`), stuck}),
                      [rows, bins, balls, rect.join(","), frames, spread, seed]);
  const t = Math.min(frames - 1.001, simAt(frame - start));
  const f0 = Math.floor(t), fr = t - f0;
  const at = (k) => {
    const p = (f0 * balls + k) * 2, q = ((f0 + 1) * balls + k) * 2;
    const x0 = sim.pos[p], y0 = sim.pos[p + 1], x1 = sim.pos[q], y1 = sim.pos[q + 1];
    if (Number.isNaN(x0)) return Number.isNaN(x1) || fr < 0.5 ? null : [x1, y1];
    return [x0 + (x1 - x0) * fr, y0 + (y1 - y0) * fr];
  };
  const binOf = (x) => Math.max(0, Math.min(cols - 1, Math.floor((x - left) / sx)));
  const finals = sim.finalX.map(binOf);
  const counts = new Array(cols).fill(0);
  finals.forEach((b) => counts[b]++);
  const landed = sim.finalX.reduce((m, _, k) => { const p = at(k); return m + (p && p[1] > (bins ? binTop : top + rows * sy) + 6 ? 1 : 0); }, 0);
  // the bell that fits the pile
  const tB = e.fit ? e.fit.at ?? start + run * 0.82 : Infinity;
  const m = mean(finals) ?? cols / 2, sd = deviation(finals) || 1;
  const hpb = layer / perRow;
  const bell = Array.from({length: cols * 6 + 1}, (_, j) => {
    const b = j / 6 - 0.5;
    return [left + (b + 0.5) * sx, floor - (balls * Math.exp(-(((b - m) / sd) ** 2) / 2) / (sd * Math.sqrt(2 * Math.PI))) * hpb];
  });
  const tallest = counts.indexOf(Math.max(...counts));
  const colOf = (b) => mix(C.accent, C.cool || C.accent, Math.min(1, Math.abs(b - m) / (cols / 2)));
  const show = ease((frame - start) / 14);
  return (
    <g>
      <path d={`M${cx - sx * 1.6},${top - sy * 2.2} L${cx - rb * 1.8},${top - sy * 1.3} M${cx + sx * 1.6},${top - sy * 2.2} L${cx + rb * 1.8},${top - sy * 1.3}`}
            stroke={alpha(C.text, 0.5)} strokeWidth={5} strokeLinecap="round" opacity={spread ? 0 : show}/>
      <rect x={left - 4} y={top - sy * 0.8} width={width + 8} height={floor - top + sy * 0.8 + 4} rx={16}
            fill={alpha(C.panel, 0.5)} stroke={alpha(C.text, 0.18)} strokeWidth={2} opacity={show}/>
      {bins > 0 && Array.from({length: bins + 1}, (_, j) => (
        <line key={j} x1={left + j * sx} x2={left + j * sx} y1={binTop} y2={floor} stroke={alpha(C.text, 0.35)} strokeWidth={3}
              opacity={ease((frame - start - j) / 12)}/>
      ))}
      <line x1={left} x2={right} y1={floor} y2={floor} stroke={alpha(C.text, 0.55)} strokeWidth={4} opacity={show}/>
      {sim.pegs.map((p, k) => {
        const hs = sim.hits[k];
        let lastHit = -99;
        for (let j = hs.length - 1; j >= 0; j--) if (hs[j] <= t) { lastHit = hs[j]; break; }
        const glow = clamp(1 - (t - lastHit) / 5);
        return <circle key={k} cx={p.x} cy={p.y} r={rp * (1 + 0.5 * glow)} fill={glow > 0 ? mix(C.text, C.accent, glow) : alpha(C.text, 0.55)}
                       opacity={pop(frame - start - 2 - ((p.y - top) / sy) * 1.5)}
                       style={{filter: glow > 0 ? `drop-shadow(0 0 ${10 * glow}px ${C.accent})` : undefined}}/>;
      })}
      {finals.map((b, k) => {
        const p = at(k);
        return p && <circle key={k} cx={p[0]} cy={p[1]} r={rb} fill={colOf(b)} stroke={alpha(C.bg, 0.6)} strokeWidth={1.5}/>;
      })}
      {frame > tB && <path d={line().curve(curveCatmullRom)(bell)} fill="none" stroke={C.hot} strokeWidth={6} strokeLinecap="round"
                           pathLength={1} strokeDasharray={1} strokeDashoffset={1 - ease((frame - tB) / 28)}
                           style={{filter: `drop-shadow(0 0 12px ${alpha(C.hot, 0.7)})`}}/>}
      {bins > 0 && frame > tB + 30 && (
        <Pen box={[left + tallest * sx - 6, floor - counts[tallest] * hpb - 20, left + (tallest + 1) * sx + 6, floor]} at={tB + 30} seed={seed + 5}/>
      )}
      <g opacity={clamp((frame - start - 20) / 10)}>
        <text x={right} y={top - sy * 0.8 - fs * 1.5} textAnchor="end" {...txt(fs * 2.6, C.accent, C.weight, FONT.display)}>{landed}</text>
        {e.text && <text x={right} y={top - sy * 0.8 - fs * 0.4} textAnchor="end" {...txt(fs)}>{e.text}</text>}
      </g>
    </g>
  );
};
