// Rich diagram parts: pictures that MOVE and let the viewer see how a thing works, each a general building block the
// diagram designer (blogwriter/diagram.py) composes for a sentence. Every part fills a region of the canvas and
// is a pure function of the frame (layouts are computed once, with seeded or deterministic algorithms), so every
// render of a frame is identical and everything is vector, crisp at any resolution.
//   Plot     a function drawn live; a parameter slider that sweeps and bends it; a point tracing it with its tangent
//            and projections; a shaded area      (expr.js, d3-scale)
//   Network  a force-directed (or layered) graph; a wave spreads through it with pulses riding the edges (d3-force)
//   Tree     a hierarchy that grows level by level; a chosen path lights up from the root                (d3-hierarchy)
//   Grid     a matrix / pixel board; a window slides over it and fills an output grid (convolution, pooling,
//            moving averages)
//   Venn     two or three sets that drift together and overlap, the overlap named
//   Cycle    a loop of stages with a comet circling it, lighting each stage in turn
//   Cursor   a mouse pointer that glides to a piece and clicks it (the "interactive" feel)
import React, {useMemo} from "react";
import {forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY} from "d3-force";
import {stratify, tree as d3tree} from "d3-hierarchy";
import {useCurrentFrame} from "remotion";
import {randomLcg} from "d3-random";
import {scaleLinear} from "d3-scale";
import {clamp, ease} from "./fx";
import {compile} from "./expr";
import {glide, pop} from "./motion";
import {C, FONT, alpha} from "./theme";

export const mixHex = (a, b, t) => {
  const p = (h) => { const s = String(h).replace("#", ""); const f = s.length === 3 ? s.split("").map((x) => x + x).join("") : s.padEnd(6, "0");
    return [0, 2, 4].map((k) => parseInt(f.slice(k, k + 2), 16) || 0); };
  const A = p(a), B = p(b);
  return `rgb(${A.map((v, k) => Math.round(v + (B[k] - v) * clamp(t))).join(",")})`;
};
export const smoothstep = (t) => { const x = clamp(t); return x * x * (3 - 2 * x); };

// text with a halo in the background colour, so it reads over lines and fills
export const Txt = ({x, y, children, size = 28, color, anchor = "middle", weight = 800, op = 1, mono = false, rotate, halo = true}) => (
  <text x={x} y={y} fontSize={size} fontFamily={mono ? FONT.mono : FONT.body} fontWeight={weight} fill={color || C.text}
        textAnchor={anchor} dominantBaseline="central" opacity={op} stroke={halo ? C.bg : "none"} strokeWidth={size * 0.3} paintOrder="stroke"
        strokeLinejoin="round" transform={rotate ? `rotate(${rotate} ${x} ${y})` : undefined}>{children}</text>
);

export const Caption = ({text, rect, at, frame, size}) => (text ? (
  <Txt x={(rect[0] + rect[2]) / 2} y={rect[3] + size * 0.2} size={size} color={C.muted} op={clamp((frame - at - 8) / 14)}>{text}</Txt>
) : null);

// ---------------------------------------------------------------------------------------------------------------
export const Plot = ({e, rect, frame, end, seed = 0, vertical}) => {
  const [x0, y0, x1, y1] = rect;
  const fs = vertical ? 34 : 30, at = e.at ?? 0;
  const sw = e.sweep;
  const pad = {l: fs * 3.2, r: 28, t: 26, b: fs * 2.4 + (sw ? 96 : 0)};
  const lo = e.lo ?? -5, hi = e.hi ?? 5;
  const f = useMemo(() => { try { return compile(e.expr, "a"); } catch (err) { return () => NaN; } }, [e.expr]);
  const g = useMemo(() => { if (!e.expr2) return null; try { return compile(e.expr2, "a"); } catch (err) { return () => NaN; } }, [e.expr2]);
  const t0 = at + 45, t1 = Math.max(t0 + 30, end - 25);
  const swT = sw ? smoothstep((frame - t0) / (t1 - t0)) : 0;
  const a = sw ? sw.from + (sw.to - sw.from) * swT : (e.a ?? 1);

  // the vertical range holds the curve at every value of the parameter, trimmed of spikes
  const range = useMemo(() => {
    const ys = [];
    const as = sw ? [0, 0.25, 0.5, 0.75, 1].map((k) => sw.from + (sw.to - sw.from) * k) : [e.a ?? 1];
    for (const av of as) for (const fn of [f, g]) {
      if (!fn) continue;
      for (let k = 0; k <= 160; k++) { const y = fn(lo + ((hi - lo) * k) / 160, av); if (Number.isFinite(y)) ys.push(y); }
    }
    ys.sort((p, q) => p - q);
    if (!ys.length) return [-1, 1];
    let a0 = ys[Math.floor(ys.length * 0.01)], a1 = ys[Math.min(ys.length - 1, Math.ceil(ys.length * 0.99))];
    if (a0 > 0 && a0 < (a1 - a0) * 0.6) a0 = 0;                    // include the axis when the curve is near it
    if (a1 < 0 && -a1 < (a1 - a0) * 0.6) a1 = 0;
    if (!(a1 - a0 > 1e-9)) { a0 -= 1; a1 += 1; }
    const padY = (a1 - a0) * 0.1;
    return [a0 - padY, a1 + padY];
  }, [f, g, lo, hi, sw && sw.from, sw && sw.to, e.a]);
  const [ylo, yhi] = range;
  const sx = scaleLinear([lo, hi], [x0 + pad.l, x1 - pad.r]), sy = scaleLinear([ylo, yhi], [y1 - pad.b, y0 + pad.t]);
  const path = (fn, av) => {
    let d = "", pen = false;
    for (let k = 0; k <= 240; k++) {
      const x = lo + ((hi - lo) * k) / 240, y = fn(x, av);
      if (!Number.isFinite(y) || y > yhi + (yhi - ylo) * 2 || y < ylo - (yhi - ylo) * 2) { pen = false; continue; }
      d += `${pen ? "L" : "M"}${sx(x).toFixed(1)},${sy(y).toFixed(1)}`;
      pen = true;
    }
    return d;
  };
  const draw = ease((frame - at - 6) / 40), clipId = `plotclip${seed}`;
  const xAxisY = ylo < 0 && yhi > 0 ? sy(0) : y1 - pad.b, yAxisX = lo < 0 && hi > 0 ? sx(0) : x0 + pad.l;
  const color = e.color, second = color === C.cool ? C.hot : C.cool;
  const xt = sx.ticks(6).filter((v) => Math.abs(v) > 1e-9), yt = sy.ticks(5).filter((v) => Math.abs(v) > 1e-9);
  const fmt = (v) => (Math.abs(v) >= 1000 ? `${v / 1000}k` : String(+v.toFixed(2)));
  const appear = clamp((frame - at) / 14);

  // a point that traces the curve, with its tangent and its distances to the axes
  let trace = null;
  if (e.trace) {
    const tp = smoothstep((frame - (at + 35)) / Math.max(30, end - at - 70));
    const x = lo + (hi - lo) * (0.06 + 0.88 * tp), y = f(x, a), h = (hi - lo) / 400;
    const m = (f(x + h, a) - f(x - h, a)) / (2 * h);
    if (Number.isFinite(y) && Number.isFinite(m) && y > ylo && y < yhi) trace = {x, y, m};
  }
  // the shaded area wipes in left to right on its moment
  const shadeAt = e.glow ? e.glow.at : at + 0.55 * (end - at);
  const shade = e.shade && e.shade.length === 2 ? (() => {
    const [s0, s1] = [Math.max(lo, Math.min(...e.shade)), Math.min(hi, Math.max(...e.shade))];
    const grow = glide(frame - shadeAt, 1.6);
    const upto = s0 + (s1 - s0) * grow;
    let d = `M${sx(s0)},${sy(0 > ylo && 0 < yhi ? 0 : ylo)}`;
    for (let k = 0; k <= 80; k++) { const x = s0 + ((upto - s0) * k) / 80, y = f(x, a); d += `L${sx(x).toFixed(1)},${sy(Math.max(ylo, Math.min(yhi, Number.isFinite(y) ? y : 0))).toFixed(1)}`; }
    return grow > 0 ? `${d}L${sx(upto)},${sy(0 > ylo && 0 < yhi ? 0 : ylo)}Z` : null;
  })() : null;

  return (
    <g opacity={appear}>
      <defs><clipPath id={clipId}><rect x={x0 + pad.l - 4} y={y0 + pad.t - 8} width={x1 - x0 - pad.l - pad.r + 8} height={y1 - y0 - pad.t - pad.b + 16}/></clipPath></defs>
      {xt.map((v) => <line key={`gx${v}`} x1={sx(v)} x2={sx(v)} y1={y0 + pad.t} y2={y1 - pad.b} stroke={alpha(C.muted, 0.14)} strokeWidth={2}/>)}
      {yt.map((v) => <line key={`gy${v}`} y1={sy(v)} y2={sy(v)} x1={x0 + pad.l} x2={x1 - pad.r} stroke={alpha(C.muted, 0.14)} strokeWidth={2}/>)}
      <line x1={x0 + pad.l} x2={x1 - pad.r} y1={xAxisY} y2={xAxisY} stroke={C.muted} strokeWidth={3.5} strokeLinecap="round"/>
      <line x1={yAxisX} x2={yAxisX} y1={y0 + pad.t} y2={y1 - pad.b} stroke={C.muted} strokeWidth={3.5} strokeLinecap="round"/>
      {xt.map((v) => <Txt key={`tx${v}`} x={sx(v)} y={Math.min(y1 - pad.b + fs * 0.9, xAxisY + fs * 0.9)} size={fs * 0.78} color={C.muted} weight={600}>{fmt(v)}</Txt>)}
      {yt.map((v) => <Txt key={`ty${v}`} x={x0 + pad.l - 12} y={sy(v)} size={fs * 0.78} color={C.muted} weight={600} anchor="end">{fmt(v)}</Txt>)}
      {e.xlabel && <Txt x={(x0 + x1) / 2 + pad.l / 2} y={y1 - pad.b + fs * 1.95} size={fs} color={C.text}>{e.xlabel}</Txt>}
      {e.ylabel && <Txt x={x0 + fs * 0.7} y={(y0 + y1) / 2 - pad.b / 2} size={fs} color={C.text} rotate={-90}>{e.ylabel}</Txt>}
      <g clipPath={`url(#${clipId})`}>
        {shade && <path d={shade} fill={alpha(C.hot, 0.32)} stroke="none"/>}
        {g && <path d={path(g, a)} fill="none" stroke={second} strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" pathLength={1}
                    strokeDasharray={1} strokeDashoffset={1 - draw} style={{filter: `drop-shadow(0 0 8px ${alpha(second, 0.5)})`}}/>}
        <path d={path(f, a)} fill="none" stroke={color} strokeWidth={7.5} strokeLinecap="round" strokeLinejoin="round" pathLength={1}
              strokeDasharray={1} strokeDashoffset={1 - draw} style={{filter: `drop-shadow(0 0 10px ${alpha(color, 0.55)})`}}/>
        {trace && (() => {
          const d = (hi - lo) * 0.13, px = sx(trace.x), py = sy(trace.y);
          return (
            <g>
              <line x1={px} x2={px} y1={py} y2={xAxisY} stroke={alpha(C.text, 0.55)} strokeWidth={3} strokeDasharray="10 9"/>
              <line y1={py} y2={py} x1={yAxisX} x2={px} stroke={alpha(C.text, 0.55)} strokeWidth={3} strokeDasharray="10 9"/>
              <line x1={sx(trace.x - d)} y1={sy(trace.y - trace.m * d)} x2={sx(trace.x + d)} y2={sy(trace.y + trace.m * d)}
                    stroke={C.accent === color ? C.hot : C.accent} strokeWidth={6} strokeLinecap="round"/>
              <circle cx={px} cy={py} r={15} fill={C.hot} stroke={C.bg} strokeWidth={4} style={{filter: `drop-shadow(0 0 12px ${alpha(C.hot, 0.9)})`}}/>
            </g>
          );
        })()}
      </g>
      {trace && <Txt x={x1 - pad.r} y={sw ? y1 - 44 - 44 : y1 - pad.b + fs * 1.95} size={fs * 0.9} color={C.hot} anchor="end" mono>slope {trace.m.toFixed(1)}</Txt>}
      {sw && (() => {
        const ty = y1 - 44, ta = x0 + pad.l, tb = x1 - pad.r, kx = ta + (tb - ta) * swT;
        return (
          <g>
            <line x1={ta} x2={tb} y1={ty} y2={ty} stroke={alpha(C.muted, 0.45)} strokeWidth={10} strokeLinecap="round"/>
            <line x1={ta} x2={kx} y1={ty} y2={ty} stroke={color} strokeWidth={10} strokeLinecap="round"/>
            <circle cx={kx} cy={ty} r={21} fill={C.text} stroke={color} strokeWidth={6} style={{filter: `drop-shadow(0 4px 10px ${alpha("#000", 0.45)})`}}/>
            <Txt x={ta} y={ty - 44} size={fs} color={color} anchor="start" mono>{sw.name} = {a.toFixed(Math.abs(sw.to - sw.from) < 5 ? 2 : 1)}</Txt>
          </g>
        );
      })()}
    </g>
  );
};

// ---------------------------------------------------------------------------------------------------------------
const NODE_R = (W, H) => clamp(Math.min(W, H) / 11, 24, 44);

export const Network = ({e, rect, frame, end, seed = 0, vertical}) => {
  const [x0, y0, x1, y1] = rect, W = x1 - x0, H = y1 - y0, at = e.at ?? 0;
  const fs = vertical ? 36 : 32, R = NODE_R(W, H);
  const layers = e.layout === "layers";
  const key = JSON.stringify([e.nodes, e.edges, e.layout]);
  const lay = useMemo(() => {
    const nodes = e.nodes.map((n) => ({...n}));
    const pos = {};
    if (layers) {
      const cols = [...new Set(nodes.map((n) => n.layer ?? 0))].sort((p, q) => p - q);
      cols.forEach((L, ci) => {
        const col = nodes.filter((n) => (n.layer ?? 0) === L);
        col.forEach((n, ri) => { pos[n.id] = [cols.length > 1 ? ci / (cols.length - 1) : 0.5, (ri + 1) / (col.length + 1)]; });
      });
    } else {
      const links = e.edges.map(([a, b]) => ({source: a, target: b}));
      const m = Math.min(W, H);
      const sim = forceSimulation(nodes).randomSource(randomLcg(0.37)).stop()
        .force("link", forceLink(links).id((d) => d.id).distance(m * 0.3).strength(0.85))
        .force("charge", forceManyBody().strength(-m * 1.3))
        .force("x", forceX(0).strength(0.07)).force("y", forceY(0).strength(0.1))
        .force("collide", forceCollide(R * 2.1));
      for (let k = 0; k < 400; k++) sim.tick();
      const xs = nodes.map((n) => n.x), ys = nodes.map((n) => n.y);
      const bx = [Math.min(...xs), Math.max(...xs)], by = [Math.min(...ys), Math.max(...ys)];
      nodes.forEach((n) => { pos[n.id] = [(n.x - bx[0]) / Math.max(1e-6, bx[1] - bx[0]), (n.y - by[0]) / Math.max(1e-6, by[1] - by[0])]; });
    }
    const px = (u) => x0 + R + 30 + u * (W - 2 * R - 60), py = (v) => y0 + R + 24 + v * (H - 2 * R - 90);
    const at2 = {};
    nodes.forEach((n) => { at2[n.id] = [px(pos[n.id][0]), py(pos[n.id][1])]; });
    // how many hops the wave is from its start (follows the arrows in a layered net)
    const start = e.start && at2[e.start] ? [e.start] : layers ? nodes.filter((n) => (n.layer ?? 0) === Math.min(...nodes.map((q) => q.layer ?? 0))).map((n) => n.id) : [nodes[0].id];
    const depth = {};
    start.forEach((id) => { depth[id] = 0; });
    for (let round = 0; round < nodes.length; round++) {
      e.edges.forEach(([a, b]) => {
        if (depth[a] !== undefined && depth[b] === undefined) depth[b] = depth[a] + 1;
        if (!layers && depth[b] !== undefined && depth[a] === undefined) depth[a] = depth[b] + 1;
      });
    }
    return {at2, depth, start, maxD: Math.max(0, ...Object.values(depth))};
  }, [key, W, H]);
  const sAt = e.glow ? e.glow.at : at + 0.5 * (end - at);
  const step = Math.max(6, Math.min(18, (end - sAt - 24) / (lay.maxD + 1)));
  const idxOf = Object.fromEntries(e.nodes.map((n, k) => [n.id, k]));
  const lit = (id) => (lay.depth[id] === undefined ? 0 : clamp((frame - (sAt + lay.depth[id] * step)) / 9));
  return (
    <g>
      {e.edges.map(([a, b], k) => {
        const [ax, ay] = lay.at2[a], [bx, by] = lay.at2[b];
        const born = 8 + 3 * Math.max(idxOf[a], idxOf[b]) + 6, grow = ease((frame - at - born) / 18);
        const da = lay.depth[a], db = lay.depth[b];
        const u = da === undefined || db === undefined ? 0 : clamp((frame - (sAt + da * step + 3)) / step);
        const on = u >= 1 ? 1 : 0;
        return (
          <g key={`e${k}`} opacity={grow}>
            <line x1={ax} y1={ay} x2={ax + (bx - ax) * grow} y2={ay + (by - ay) * grow} stroke={on ? e.color : alpha(C.muted, 0.6)} strokeWidth={on ? 6 : 4} strokeLinecap="round"/>
            {u > 0 && u < 1 && <circle cx={ax + (bx - ax) * u} cy={ay + (by - ay) * u} r={11} fill={C.hot} style={{filter: `drop-shadow(0 0 12px ${alpha(C.hot, 0.95)})`}}/>}
          </g>
        );
      })}
      {e.nodes.map((n, k) => {
        const [nx, ny] = lay.at2[n.id], p = pop(frame - at - k * 3), L = lit(n.id);
        const ring = L > 0 && L < 1 ? 1 - L : 0;
        const isStart = lay.start.includes(n.id);
        return (
          <g key={`n${n.id}`} opacity={clamp(p * 2)}>
            {ring > 0 && <circle cx={nx} cy={ny} r={R * (1 + 1.1 * (1 - ring))} fill="none" stroke={C.hot} strokeWidth={5} opacity={ring}/>}
            <circle cx={nx} cy={ny} r={R * (0.5 + 0.5 * p) * (1 + 0.12 * Math.sin(Math.PI * L))} fill={L > 0.5 ? alpha(isStart ? C.hot : e.color, 0.92) : alpha(C.panel, 0.95)}
                    stroke={L > 0.5 ? (isStart ? C.hot : e.color) : alpha(C.muted, 0.9)} strokeWidth={5}
                    style={{filter: L > 0.5 ? `drop-shadow(0 0 ${14 * L}px ${alpha(e.color, 0.8)})` : undefined}}/>
            {n.text && <Txt x={nx} y={ny + R + fs * 0.85} size={fs} color={L > 0.5 ? C.text : C.muted}>{n.text}</Txt>}
          </g>
        );
      })}
      <Caption text={e.text} rect={rect} at={at} frame={frame} size={fs}/>
    </g>
  );
};

// ---------------------------------------------------------------------------------------------------------------
export const Tree = ({e, rect, frame, end, seed = 0, vertical}) => {
  const [x0, y0, x1, y1] = rect, W = x1 - x0, H = y1 - y0, at = e.at ?? 0;
  const fs0 = vertical ? 36 : 32;
  const lay = useMemo(() => {
    try {
      const root = stratify().id((d) => d.id).parentId((d) => d.parent || null)(e.nodes);
      const leaves = Math.max(1, root.leaves().length), depth = Math.max(1, root.height);
      const padX = 70, padY = 54;
      d3tree().size([W - 2 * padX, H - 2 * padY - 40])(root);
      const slot = (W - 2 * padX) / leaves;
      const fs = clamp(slot / 7.2, vertical ? 21 : 18, fs0);
      return {nodes: root.descendants().map((n) => ({id: n.id, text: n.data.text || "", x: x0 + padX + n.x, y: y0 + padY + n.y, depth: n.depth, parent: n.parent && n.parent.id})), fs, depth};
    } catch (err) { return {nodes: [], fs: fs0, depth: 1}; }
  }, [JSON.stringify(e.nodes), W, H]);
  const byId = Object.fromEntries(lay.nodes.map((n) => [n.id, n]));
  const chain = [];                       // the path that lights up: root to the chosen node
  for (let n = byId[e.path]; n; n = n.parent && byId[n.parent]) chain.unshift(n.id);
  const pAt = e.glow ? e.glow.at : at + 0.6 * (end - at);
  const stepAt = (id) => pAt + chain.indexOf(id) * 15;
  const onPath = (id) => chain.includes(id) && frame >= stepAt(id);
  const w = (n) => Math.max(64, n.text.length * lay.fs * 0.62 + 34), h = lay.fs * 1.9;
  const birth = (n) => at + n.depth * 16;
  return (
    <g>
      {lay.nodes.filter((n) => n.parent).map((n) => {
        const p = byId[n.parent], grow = ease((frame - birth(n)) / 16), hot = onPath(n.id) && chain.includes(n.parent);
        const my = (p.y + n.y) / 2;
        const d = `M${p.x},${p.y + h / 2} C${p.x},${my} ${n.x},${my} ${n.x},${n.y - h / 2}`;
        return <path key={`l${n.id}`} d={d} fill="none" stroke={hot ? C.hot : alpha(C.muted, 0.75)} strokeWidth={hot ? 7 : 4.5} strokeLinecap="round"
                     pathLength={1} strokeDasharray={1} strokeDashoffset={1 - grow} style={{filter: hot ? `drop-shadow(0 0 10px ${alpha(C.hot, 0.8)})` : undefined}}/>;
      })}
      {lay.nodes.map((n) => {
        const p = pop(frame - birth(n) - 6), hot = onPath(n.id), root = !n.parent;
        const c = hot ? C.hot : root ? e.color : alpha(C.muted, 0.95);
        return (
          <g key={`n${n.id}`} opacity={clamp(p * 2)} transform={`translate(${n.x},${n.y}) scale(${0.6 + 0.4 * p})`}>
            <rect x={-w(n) / 2} y={-h / 2} width={w(n)} height={h} rx={h / 2} fill={hot ? alpha(C.hot, 0.3) : alpha(C.panel, 0.96)} stroke={c} strokeWidth={hot || root ? 5 : 3.5}
                  style={{filter: hot ? `drop-shadow(0 0 14px ${alpha(C.hot, 0.8)})` : undefined}}/>
            <Txt x={0} y={1} size={lay.fs} color={hot || root ? C.text : C.muted}>{n.text}</Txt>
          </g>
        );
      })}
      <Caption text={e.text} rect={rect} at={at} frame={frame} size={fs0}/>
    </g>
  );
};

// ---------------------------------------------------------------------------------------------------------------
export const Grid = ({e, rect, frame, end, seed = 0, vertical}) => {
  const [x0, y0, x1, y1] = rect, W = x1 - x0, H = y1 - y0, at = e.at ?? 0;
  const {rows, cols} = e, k = e.scan || 0;
  const outR = k ? rows - k + 1 : 0, outC = k ? cols - k + 1 : 0;
  const inW = k ? W * 0.58 : W, cell = Math.min(inW / cols, (H - 30) / rows, 150);
  const gx = x0 + (inW - cell * cols) / 2 + (k ? 0 : 0), gy = y0 + (H - 30 - cell * rows) / 2;
  const oCell = k ? Math.min((W * 0.34) / outC, (H - 30) / outR, cell * 1.15) : 0;
  const ox = x1 - oCell * outC - W * 0.02, oy = y0 + (H - 30 - oCell * outR) / 2;
  const vals = e.values, vmax = Math.max(1, ...vals.map(Math.abs)), vmin = Math.min(0, ...vals);
  const heat = (v) => mixHex(C.panel, e.color, 0.12 + 0.88 * ((v - vmin) / Math.max(1e-9, vmax - vmin)));
  const outs = useMemo(() => {
    if (!k) return [];
    const o = [];
    for (let r = 0; r < outR; r++) for (let c = 0; c < outC; c++) {
      const w = [];
      for (let i = 0; i < k; i++) for (let j = 0; j < k; j++) w.push(vals[(r + i) * cols + c + j]);
      o.push(e.op === "max" ? Math.max(...w) : e.op === "mean" ? w.reduce((s, v) => s + v, 0) / w.length : w.reduce((s, v) => s + v, 0));
    }
    return o;
  }, [JSON.stringify(vals), k, e.op, rows, cols]);
  const sAt = e.glow ? e.glow.at : at + 0.3 * (end - at);
  const stepF = k ? Math.max(5, Math.min(16, (end - sAt - 30) / (outs.length || 1))) : 1;
  const idx = k && frame >= sAt ? Math.min(outs.length - 1, Math.floor((frame - sAt) / stepF)) : -1;
  const fsz = cell * (e.show === "heat" ? 0 : 0.42), ofs = oCell * 0.4;
  const fmt = (v) => (Number.isInteger(v) ? String(v) : v.toFixed(1));
  const lights = new Set((e.cells || []).map(([r, c]) => r * cols + c));
  const lightAt = e.glow ? e.glow.at : at + 30;
  return (
    <g>
      {vals.map((v, n) => {
        const r = Math.floor(n / cols), c = n % cols, p = pop(frame - at - (r + c) * 1.6);
        const inWin = idx >= 0 && r >= Math.floor(idx / outC) && r < Math.floor(idx / outC) + k && c >= idx % outC && c < (idx % outC) + k;
        const flash = lights.has(n) ? clamp((frame - lightAt) / 10) : 0;
        return (
          <g key={`c${n}`} opacity={clamp(p * 2)} transform={`translate(${gx + c * cell + cell / 2},${gy + r * cell + cell / 2}) scale(${0.5 + 0.5 * p + 0.12 * Math.sin(Math.PI * flash)})`}>
            <rect x={-cell / 2 + 3} y={-cell / 2 + 3} width={cell - 6} height={cell - 6} rx={cell * 0.14} fill={e.show === "numbers" ? alpha(C.panel, 0.95) : heat(v)}
                  stroke={flash > 0.5 ? C.hot : inWin ? C.hot : alpha(C.muted, 0.55)} strokeWidth={flash > 0.5 || inWin ? 5 : 2.5}/>
            {e.show !== "heat" && <Txt x={0} y={1} size={fsz} color={e.show === "numbers" ? C.text : mixHex(C.text, C.bg, 0.08)}>{fmt(v)}</Txt>}
          </g>
        );
      })}
      {k > 0 && idx >= 0 && (() => {
        const r = Math.floor(idx / outC), c = idx % outC;
        return <rect x={gx + c * cell} y={gy + r * cell} width={cell * k} height={cell * k} rx={cell * 0.18} fill={alpha(C.hot, 0.14)} stroke={C.hot} strokeWidth={7}
                     style={{filter: `drop-shadow(0 0 14px ${alpha(C.hot, 0.8)})`}}/>;
      })()}
      {k > 0 && (
        <g opacity={clamp((frame - sAt + 10) / 14)}>
          <Txt x={(gx + cell * cols + ox) / 2} y={gy + (cell * rows) / 2} size={cell * 0.6} color={C.muted}>→</Txt>
          {outs.map((v, n) => {
            const r = Math.floor(n / outC), c = n % outC, shown = n <= idx;
            return (
              <g key={`o${n}`} opacity={shown ? 1 : 0.28}>
                <rect x={ox + c * oCell + 3} y={oy + r * oCell + 3} width={oCell - 6} height={oCell - 6} rx={oCell * 0.14} fill={shown ? heat(e.op === "mean" || e.op === "max" ? v : v / (k * k)) : alpha(C.panel, 0.8)}
                      stroke={n === idx ? C.hot : alpha(C.muted, 0.5)} strokeWidth={n === idx ? 5 : 2.5}/>
                {shown && <Txt x={ox + c * oCell + oCell / 2} y={oy + r * oCell + oCell / 2 + 1} size={ofs}>{fmt(+v.toFixed(1))}</Txt>}
              </g>
            );
          })}
        </g>
      )}
      <Caption text={e.text} rect={rect} at={at} frame={frame} size={vertical ? 36 : 32}/>
    </g>
  );
};

// ---------------------------------------------------------------------------------------------------------------
export const Venn = ({e, rect, frame, end, seed = 0, vertical}) => {
  const [x0, y0, x1, y1] = rect, W = x1 - x0, H = y1 - y0, at = e.at ?? 0;
  const fs = vertical ? 38 : 34, n = e.sets.length;
  const R = Math.min(H * (n === 3 ? 0.3 : 0.38), W * (n === 3 ? 0.21 : 0.24));
  const cx = (x0 + x1) / 2, cy = n === 3 ? y0 + H * 0.5 : y0 + H * 0.48;
  const sAt = e.glow ? e.glow.at : at + 0.4 * (end - at);
  const q = glide(frame - sAt, 1.8), ov = e.overlap ?? 0.35;
  const cols = [e.color, C.cool === e.color ? C.violet : C.cool, C.violet === e.color || C.hot === e.color ? C.accent : C.hot];
  const centers = e.sets.map((s, k) => {
    if (n === 2) { const d = (2 * R * 1.45) + (2 * R * (1 - ov) - 2 * R * 1.45) * q; return [cx + (k ? d / 2 : -d / 2), cy]; }
    const rho = (R * 1.55) + ((2 * R * (1 - ov)) / Math.sqrt(3) - R * 1.55) * q;
    const ang = -Math.PI / 2 + (2 * Math.PI * k) / 3;
    return [cx + rho * Math.cos(ang), cy + rho * Math.sin(ang) * 0.95 + (n === 3 ? R * 0.1 : 0)];
  });
  const clipId = `vennclip${seed}`;
  const mid = n === 2 ? [(centers[0][0] + centers[1][0]) / 2, cy] : [(centers[0][0] + centers[1][0] + centers[2][0]) / 3, (centers[0][1] + centers[1][1] + centers[2][1]) / 3];
  const blend = C.light ? "multiply" : "screen";
  return (
    <g>
      <defs><clipPath id={clipId}><circle cx={centers[1][0]} cy={centers[1][1]} r={R}/></clipPath></defs>
      {e.sets.map((s, k) => {
        const p = pop(frame - at - k * 6), [px, py] = centers[k];
        return (
          <g key={`s${k}`} opacity={clamp(p * 2)}>
            <circle cx={px} cy={py} r={R * (0.6 + 0.4 * p)} fill={alpha(cols[k], 0.34)} stroke={cols[k]} strokeWidth={6} style={{mixBlendMode: blend, filter: `drop-shadow(0 0 12px ${alpha(cols[k], 0.4)})`}}/>
          </g>
        );
      })}
      {n === 2 && q > 0.05 && <circle cx={centers[0][0]} cy={centers[0][1]} r={R} fill={alpha(C.text, 0.22 * q)} clipPath={`url(#${clipId})`}/>}
      {e.sets.map((s, k) => {
        const [px, py] = centers[k], dx = px - mid[0], dy = py - mid[1], len = Math.hypot(dx, dy) || 1;
        const lx = n === 2 ? px + (k ? 1 : -1) * 0 : px + (dx / len) * (R + fs * 0.9), ly = n === 2 ? py - R - fs * 0.9 : py + (dy / len) * (R + fs * 0.9);
        return <Txt key={`t${k}`} x={lx} y={ly} size={fs} color={cols[k]} op={clamp((frame - at - 10 - k * 6) / 12)}>{s.text}</Txt>;
      })}
      {e.both && <Txt x={mid[0]} y={mid[1]} size={fs * 0.95} color={C.text} op={clamp((q - 0.7) / 0.3)}>{e.both}</Txt>}
      <Caption text={e.text} rect={rect} at={at} frame={frame} size={fs}/>
    </g>
  );
};

// ---------------------------------------------------------------------------------------------------------------
export const Cycle = ({e, rect, frame, end, seed = 0, vertical}) => {
  const [x0, y0, x1, y1] = rect, W = x1 - x0, H = y1 - y0, at = e.at ?? 0;
  const fs = vertical ? 38 : 34, n = e.nodes.length;
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2 - 8, rx = W * 0.36, ry = H * 0.33;
  const ang = (k) => -Math.PI / 2 + (2 * Math.PI * k) / n;
  const pt = (a) => [cx + rx * Math.cos(a), cy + ry * Math.sin(a)];
  const cAt = at + n * 8 + 12, period = Math.max(90, Math.min(150, (end - cAt) / 1.6));
  const theta = ang(0) + (frame >= cAt ? (2 * Math.PI * (frame - cAt)) / period : 0);
  const near = (k) => {
    if (frame < cAt) return 0;
    let d = Math.abs(((theta - ang(k)) % (2 * Math.PI) + 3 * Math.PI) % (2 * Math.PI) - Math.PI);
    return 1 - clamp(d / 0.55);
  };
  const w = (t) => Math.max(110, t.length * fs * 0.6 + 44), h = fs * 1.95;
  return (
    <g>
      <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill="none" stroke={alpha(C.muted, 0.35)} strokeWidth={4} strokeDasharray="4 14" strokeLinecap="round" opacity={clamp((frame - at) / 14)}/>
      {Array.from({length: 12}, (_, j) => {
        if (frame < cAt) return null;
        const a = theta - j * 0.07, [px, py] = pt(a);
        return <circle key={`tail${j}`} cx={px} cy={py} r={14 - j * 0.9} fill={C.hot} opacity={(1 - j / 12) * 0.9} style={j === 0 ? {filter: `drop-shadow(0 0 14px ${alpha(C.hot, 0.95)})`} : undefined}/>;
      })}
      {e.nodes.map((t, k) => {
        const [px, py] = pt(ang(k)), p = pop(frame - at - k * 8), L = near(k);
        return (
          <g key={`n${k}`} opacity={clamp(p * 2)} transform={`translate(${px},${py}) scale(${(0.6 + 0.4 * p) * (1 + 0.1 * L)})`}>
            <rect x={-w(t) / 2} y={-h / 2} width={w(t)} height={h} rx={h / 2} fill={L > 0.2 ? alpha(e.color, 0.35 + 0.4 * L) : alpha(C.panel, 0.96)} stroke={L > 0.2 ? e.color : alpha(C.muted, 0.9)} strokeWidth={5}
                  style={{filter: L > 0.2 ? `drop-shadow(0 0 ${16 * L}px ${alpha(e.color, 0.85)})` : undefined}}/>
            <Txt x={0} y={1} size={fs} color={L > 0.2 ? C.text : C.muted}>{t}</Txt>
          </g>
        );
      })}
      {e.text && <Txt x={cx} y={cy} size={fs * 1.25} color={e.color} op={clamp((frame - at - 14) / 16)}>{e.text}</Txt>}
    </g>
  );
};

// ---------------------------------------------------------------------------------------------------------------
// a mouse pointer glides to a piece, presses, and a ripple spreads: the viewer sees something being operated
export const Cursor = ({box, at, from}) => {
  const frame = useCurrentFrame();
  const tx = (box[0] + box[2]) / 2, ty = (box[1] + box[3]) / 2;
  const sx = from ? from[0] : tx + 260, sy = from ? from[1] : ty + 210;
  const t = glide(frame - (at - 22), 1.1), x = sx + (tx - sx) * t, y = sy + (ty - sy) * t;
  const since = frame - at;
  if (frame < at - 22 || since > 70) return null;
  const press = since >= 0 && since < 6 ? 0.82 : 1, fade = since > 50 ? 1 - (since - 50) / 20 : 1;
  const ripple = since >= 0 ? clamp(since / 22) : 0;
  return (
    <g opacity={fade}>
      {since >= 0 && since < 26 && <circle cx={tx} cy={ty} r={14 + 80 * ripple} fill="none" stroke={C.accent} strokeWidth={6 * (1 - ripple) + 1} opacity={1 - ripple}/>}
      <g transform={`translate(${x},${y}) scale(${press})`} style={{filter: `drop-shadow(0 6px 10px ${alpha("#000", 0.55)})`}}>
        <path d="M0,0 L0,46 L12,35 L21,56 L31,51 L22,31 L38,31 Z" fill={C.text} stroke={C.bg} strokeWidth={4} strokeLinejoin="round"/>
      </g>
    </g>
  );
};
