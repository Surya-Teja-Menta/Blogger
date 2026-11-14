// Chart techniques (blogwriter/vizlib.py, family "chart"): each draws itself on, then makes its point on the key
// moment (the glow word): a slice pulls out, a marker slides, a curve tightens.
import {hierarchy, pack, treemap, treemapSquarify} from "d3-hierarchy";
import {arc as d3arc, area as d3area, curveMonotoneX, pie as d3pie, stack as d3stack} from "d3-shape";
import {Arrow, C, Caption, Chip, Num, React, Ring, Txt, alpha, box, clamp, ease, fmt, gauss, glide, glowF, lerp, pal, pop,
        rng, row, smoothPath, spread, timing, tw} from "./kit";

const sum = (a) => a.reduce((s, x) => s + x, 0);
const maxOf = (a) => Math.max(1e-9, ...a);

// --------------------------------------------------------------------------------------------------------------
export const Waffle = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const tot = sum(e.items.map((x) => x.value)) || 1;
  const counts = e.items.map((x) => Math.round((100 * x.value) / tot));
  const owner = [];
  counts.forEach((c, k) => { for (let j = 0; j < c && owner.length < 100; j++) owner.push(k); });
  while (owner.length < 100) owner.push(e.items.length - 1);
  const side = Math.min(B.H * 0.92, B.W * 0.5), cell = side / 10, gx = B.x0 + (vertical ? (B.W - side) / 2 : B.W * 0.06), gy = B.y0 + (B.H - side) / 2;
  const lx = vertical ? B.x0 : gx + side + B.W * 0.06;
  return (
    <g>
      {owner.map((o, n) => {
        const r = Math.floor(n / 10), c = n % 10, p = pop(T.t - n * 0.6);
        const lit = T.k > 0 ? clamp((T.k - o * 10) / 12) : 0;
        return <rect key={n} x={gx + c * cell + cell * 0.08} y={gy + (9 - r) * cell + cell * 0.08} width={cell * 0.84} height={cell * 0.84}
                     rx={cell * 0.18} fill={alpha(pal(e, o), 0.35 + 0.6 * Math.max(p > 0.5 ? 0.4 : 0, lit))} opacity={clamp(p * 2)}/>;
      })}
      {!vertical && e.items.map((it, k) => {
        const y = B.y0 + B.H * (0.2 + (0.6 * k) / Math.max(1, e.items.length - 1 || 1));
        const op = clamp((T.k - k * 10) / 12) || clamp((T.t - 30 - k * 8) / 12) * 0.6;
        return (
          <g key={`l${k}`} opacity={op}>
            <rect x={lx} y={y - B.fs * 0.45} width={B.fs * 0.9} height={B.fs * 0.9} rx={6} fill={pal(e, k)}/>
            <Txt x={lx + B.fs * 1.4} y={y} size={B.fs} anchor="start">{it.text}</Txt>
            {e.show && <Txt x={lx + B.fs * 2.2 + tw(it.text, B.fs)} y={y} size={B.fs} anchor="start" color={pal(e, k)}>{`${counts[k]}%`}</Txt>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Treemap = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const root = treemap().tile(treemapSquarify).size([B.W, B.H]).paddingInner(8)(
    hierarchy({children: e.items.map((x, k) => ({...x, k}))}).sum((d) => d.value || 0).sort((a, b) => b.value - a.value));
  return (
    <g>
      {root.leaves().map((l, n) => {
        const p = glide(T.t - n * 5), d = l.data, w = l.x1 - l.x0, h = l.y1 - l.y0;
        const lit = T.k > 0 && n === 0 ? 0.6 + 0.4 * Math.sin(T.k / 6) : 0;
        const f = Math.min(B.fs * 1.1, w / Math.max(3, d.text.length * 0.6), h / 2.2);
        return (
          <g key={n} opacity={clamp(p * 2)}>
            <rect x={B.x0 + l.x0} y={B.y0 + l.y0} width={w * p} height={h} rx={12} fill={alpha(pal(e, d.k), 0.3 + 0.25 * lit)}
                  stroke={pal(e, d.k)} strokeWidth={lit ? 6 : 3} style={{filter: lit ? glowF(pal(e, d.k), lit) : undefined}}/>
            {f > 14 && <Txt x={B.x0 + l.x0 + w / 2} y={B.y0 + l.y0 + h / 2 - (e.show ? f * 0.45 : 0)} size={f}>{d.text}</Txt>}
            {f > 14 && e.show && <Txt x={B.x0 + l.x0 + w / 2} y={B.y0 + l.y0 + h / 2 + f * 0.7} size={f * 0.85} color={pal(e, d.k)}>{fmt(d.value)}</Txt>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Sankey = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const left = [...new Set(e.flows.map((f) => f.from))], right = [...new Set(e.flows.map((f) => f.to).filter((n) => !left.includes(n)))];
  const mids = [...new Set(e.flows.map((f) => f.to).filter((n) => left.includes(n)))];
  const cols = [left.filter((n) => !mids.includes(n)), mids, right].filter((c) => c.length);
  const colX = row(cols.length, B.x0 + B.W * 0.08, B.x1 - B.W * 0.08);
  const tot = (n) => Math.max(sum(e.flows.filter((f) => f.from === n).map((f) => f.value)), sum(e.flows.filter((f) => f.to === n).map((f) => f.value)));
  const scale = (B.H * 0.75) / Math.max(...cols.map((c) => sum(c.map(tot))));
  const pos = {};
  cols.forEach((c, ci) => {
    const h = sum(c.map(tot)) * scale + (c.length - 1) * 18;
    let y = B.cy - h / 2;
    c.forEach((n) => { pos[n] = {x: colX[ci], y, h: tot(n) * scale, out: 0, in: 0}; y += tot(n) * scale + 18; });
  });
  const nodeW = 22;
  return (
    <g>
      {e.flows.map((f, k) => {
        const a = pos[f.from], b = pos[f.to], w = f.value * scale;
        const y0 = a.y + a.out + w / 2, y1 = b.y + b.in + w / 2;
        a.out += w; b.in += w;
        const x0 = a.x + nodeW / 2, x1 = b.x - nodeW / 2, p = glide(T.t - 10 - k * 6, 1.5), xm = lerp(x0, x1, p);
        const lit = T.k > 0 && k === 0 ? 0.5 + 0.5 * Math.sin(T.k / 6) : 0;
        return <path key={k} d={`M${x0},${y0} C${(x0 + x1) / 2},${y0} ${(x0 + x1) / 2},${y1} ${xm},${lerp(y0, y1, p)}`} fill="none"
                     stroke={alpha(pal(e, k), 0.45 + 0.3 * lit)} strokeWidth={Math.max(3, w)} style={{filter: lit ? glowF(pal(e, k), lit) : undefined}}/>;
      })}
      {Object.entries(pos).map(([n, a], k) => {
        const left = a.x < B.cx;
        return (
          <g key={n} opacity={clamp(pop(T.t - k * 4) * 2)}>
            <rect x={a.x - nodeW / 2} y={a.y} width={nodeW} height={Math.max(8, a.h)} rx={6} fill={C.text}/>
            <Txt x={a.x + (left ? -nodeW : nodeW)} y={a.y + a.h / 2} size={B.fs} anchor={left ? "end" : "start"}>{n}</Txt>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Funnel = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const items = [...e.items].sort((a, b) => b.value - a.value), mx = maxOf(items.map((x) => x.value));
  const n = items.length, gap = 10, h = (B.H - gap * (n - 1)) / n, fw = vertical ? B.W : B.W * 0.62;
  return (
    <g>
      {items.map((it, k) => {
        const w0 = fw * (0.25 + 0.75 * it.value / mx), w1 = fw * (0.25 + 0.75 * (items[k + 1] ? items[k + 1].value : it.value * 0.7) / mx);
        const y = B.y0 + k * (h + gap), cx = vertical ? B.cx : B.x0 + fw / 2, p = glide(T.t - k * 9);
        const lit = T.k > 0 && k === n - 1 ? 0.5 + 0.5 * Math.sin(T.k / 6) : 0;
        return (
          <g key={k} opacity={clamp(p * 2)}>
            <path d={`M${cx - w0 / 2 * p},${y} L${cx + w0 / 2 * p},${y} L${cx + w1 / 2 * p},${y + h} L${cx - w1 / 2 * p},${y + h} Z`}
                  fill={alpha(pal(e, k), 0.4 + 0.3 * lit)} stroke={pal(e, k)} strokeWidth={3} style={{filter: lit ? glowF(pal(e, k), lit) : undefined}}/>
            <Txt x={cx} y={y + h / 2} size={Math.min(B.fs, h * 0.45)}>{it.text}</Txt>
            {e.show && <Txt x={vertical ? cx : B.x0 + fw + 30} y={y + h / 2 + (vertical ? h * 0.32 : 0)} size={Math.min(B.fs, h * 0.45)}
                            anchor={vertical ? "middle" : "start"} color={pal(e, k)}>{fmt(it.value)}</Txt>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Radar = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const n = e.axes.length, R = Math.min(B.H, B.W) * 0.36, cx = B.cx, cy = B.cy + 6;
  const mx = maxOf([...e.a, ...(e.b || [])]);
  const ang = (k) => -Math.PI / 2 + (2 * Math.PI * k) / n;
  const P = (k, v) => [cx + R * v * Math.cos(ang(k)), cy + R * v * Math.sin(ang(k))];
  const poly = (vals, p) => vals.map((v, k) => P(k, (v / mx) * p).join(",")).join(" ");
  const pa = glide(T.t - 18, 1.6), pb = glide(T.k, 1.6);
  return (
    <g>
      {[0.25, 0.5, 0.75, 1].map((r, j) => <polygon key={j} points={e.axes.map((_, k) => P(k, r).join(",")).join(" ")} fill="none"
                                                    stroke={alpha(C.muted, 0.3)} strokeWidth={2} opacity={clamp(T.t / 12)}/>)}
      {e.axes.map((a, k) => {
        const [x, y] = P(k, 1.18);
        return <Txt key={k} x={x} y={y} size={B.fs * 0.9} color={C.muted} op={clamp((T.t - k * 3) / 12)}>{a}</Txt>;
      })}
      <polygon points={poly(e.a, pa)} fill={alpha(pal(e, 0), 0.3)} stroke={pal(e, 0)} strokeWidth={4} opacity={clamp(pa * 3)}/>
      {e.b && e.b.length > 0 && <polygon points={poly(e.b, pb)} fill={alpha(C.hot, 0.3)} stroke={C.hot} strokeWidth={4} opacity={clamp(pb * 3)}/>}
      {(e.names || []).map((nm, k) => (
        <g key={`n${k}`} opacity={k ? clamp(pb * 2) : clamp(pa * 2)}>
          <rect x={B.x0 + 4} y={B.y0 + k * B.fs * 1.6} width={B.fs * 0.8} height={B.fs * 0.8} rx={5} fill={k ? C.hot : pal(e, 0)}/>
          <Txt x={B.x0 + B.fs * 1.3} y={B.y0 + k * B.fs * 1.6 + B.fs * 0.4} size={B.fs * 0.9} anchor="start">{nm}</Txt>
        </g>
      ))}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Heatmap = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const R = e.rows.length, K = e.cols.length, lw = Math.max(...e.rows.map((r) => tw(r, B.fs))) + 20;
  const cw = Math.min((B.W - lw) / K, 220), ch = (B.H - B.fs * 1.8) / R, x0 = B.x0 + lw + (B.W - lw - cw * K) / 2, y0 = B.y0 + B.fs * 1.8;
  const mx = maxOf(e.values), mn = Math.min(...e.values);
  const best = e.values.indexOf(Math.max(...e.values));
  return (
    <g>
      {e.cols.map((c, j) => <Txt key={`c${j}`} x={x0 + cw * (j + 0.5)} y={B.y0 + B.fs * 0.7} size={B.fs * 0.85} color={C.muted} op={clamp(T.t / 12)}>{c}</Txt>)}
      {e.rows.map((r, i) => <Txt key={`r${i}`} x={x0 - 14} y={y0 + ch * (i + 0.5)} size={B.fs * 0.85} anchor="end" color={C.muted} op={clamp(T.t / 12)}>{r}</Txt>)}
      {e.values.map((v, n) => {
        const i = Math.floor(n / K), j = n % K, q = (v - mn) / Math.max(1e-9, mx - mn), p = glide(T.t - 8 - (i + j) * 3);
        const lit = T.k > 0 && n === best ? 0.5 + 0.5 * Math.sin(T.k / 6) : 0;
        return (
          <g key={n}>
            <rect x={x0 + j * cw + 4} y={y0 + i * ch + 4} width={cw - 8} height={ch - 8} rx={8} fill={alpha(pal(e, 0), 0.08 + 0.85 * q * p)}
                  stroke={lit ? C.hot : "none"} strokeWidth={5} style={{filter: lit ? glowF(C.hot, lit) : undefined}}/>
            {e.show && <Txt x={x0 + (j + 0.5) * cw} y={y0 + (i + 0.5) * ch} size={Math.min(B.fs, ch * 0.4)} op={p}>{fmt(v)}</Txt>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
const Axes = ({B, T, xlabel, ylabel}) => (
  <g opacity={clamp(T.t / 12)}>
    <line x1={B.x0} y1={B.y1 - B.fs * 1.4} x2={B.x1} y2={B.y1 - B.fs * 1.4} stroke={C.muted} strokeWidth={3}/>
    {xlabel && <Txt x={B.cx} y={B.y1 - B.fs * 0.45} size={B.fs * 0.9} color={C.muted}>{xlabel}</Txt>}
    {ylabel && <Txt x={B.x0 + 4} y={B.y0 + B.fs * 0.5} size={B.fs * 0.9} color={C.muted} anchor="start">{ylabel}</Txt>}
  </g>
);

export const Histogram = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const n = e.values.length, mx = maxOf(e.values), base = B.y1 - B.fs * 1.4, top = B.y0 + B.fs * 0.6;
  const bw = B.W / n;
  return (
    <g>
      <Axes B={B} T={T} xlabel={e.xlabel}/>
      {e.values.map((v, k) => {
        const p = glide(T.t - 10 - k * 4, 1.2), h = ((base - top) * v * p) / mx;
        const lit = k === e.highlight && T.k > 0 ? 0.5 + 0.5 * Math.sin(T.k / 6) : 0;
        return (
          <g key={k}>
            <rect x={B.x0 + k * bw + 3} y={base - h} width={bw - 6} height={h} rx={4} fill={alpha(lit ? C.hot : pal(e, 0), 0.75)}
                  style={{filter: lit ? glowF(C.hot, lit) : undefined}}/>
            {e.show && p > 0.9 && <Txt x={B.x0 + (k + 0.5) * bw} y={base - h - B.fs * 0.6} size={Math.min(B.fs * 0.8, bw * 0.5)}>{fmt(v)}</Txt>}
          </g>
        );
      })}
      {T.k > 0 && <path d={smoothPath(e.values.map((v, k) => [B.x0 + (k + 0.5) * bw, base - ((base - top) * v) / mx]))} fill="none"
                        stroke={C.text} strokeWidth={4} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - glide(T.k, 1.6)}/>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Boxplot = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const all = e.groups.flatMap((g) => [g.min, g.q1, g.median, g.q3, g.max]);
  const lo = Math.min(...all), hi = Math.max(...all), lw = Math.max(...e.groups.map((g) => tw(g.text, B.fs))) + 30;
  const X = (v) => B.x0 + lw + ((v - lo) / Math.max(1e-9, hi - lo)) * (B.W - lw - 30);
  const rh = Math.min(B.H / e.groups.length, 150);
  return (
    <g>
      {e.groups.map((g, k) => {
        const s = [g.min, g.q1, g.median, g.q3, g.max].sort((a, b) => a - b);
        const y = B.y0 + rh * (k + 0.5) + (B.H - rh * e.groups.length) / 2, p = glide(T.t - k * 10, 1.4), h = rh * 0.45;
        const lit = T.k > 0 ? 0.5 + 0.5 * Math.sin(T.k / 6) : 0, col = pal(e, k);
        const mid = (s[1] + s[3]) / 2;
        const xs = (v) => X(lerp(mid, v, p));
        return (
          <g key={k} opacity={clamp(p * 3)}>
            <Txt x={B.x0 + lw - 20} y={y} size={B.fs} anchor="end">{g.text}</Txt>
            <line x1={xs(s[0])} y1={y} x2={xs(s[4])} y2={y} stroke={C.muted} strokeWidth={3}/>
            {[s[0], s[4]].map((v, j) => <line key={j} x1={xs(v)} y1={y - h * 0.35} x2={xs(v)} y2={y + h * 0.35} stroke={C.muted} strokeWidth={3}/>)}
            <rect x={xs(s[1])} y={y - h / 2} width={Math.max(2, xs(s[3]) - xs(s[1]))} height={h} rx={6} fill={alpha(col, 0.35)} stroke={col} strokeWidth={3}/>
            <line x1={xs(s[2])} y1={y - h / 2} x2={xs(s[2])} y2={y + h / 2} stroke={C.hot} strokeWidth={6} style={{filter: lit ? glowF(C.hot, lit) : undefined}}/>
            {e.show && T.k > 0 && <Txt x={xs(s[2])} y={y - h / 2 - B.fs * 0.6} size={B.fs * 0.85} color={C.hot}>{fmt(s[2])}</Txt>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Ridgeline = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const lo = Math.min(...e.groups.map((g) => g.mean - 3 * g.sd)), hi = Math.max(...e.groups.map((g) => g.mean + 3 * g.sd));
  const lw = Math.max(...e.groups.map((g) => tw(g.text, B.fs))) + 26, n = e.groups.length;
  const X = (v) => B.x0 + lw + ((v - lo) / (hi - lo)) * (B.W - lw), step = (B.H * 0.78) / n, amp = step * 1.7;
  return (
    <g>
      {e.groups.map((g, k) => {
        const base = B.y0 + B.H * 0.2 + step * (k + 1), p = glide(T.t - k * 10, 1.5), col = pal(e, k);
        const m = lerp(e.groups[0].mean, g.mean, T.k > 0 ? glide(T.k - k * 6, 1.6) : 0);     // all start where the first is
        const pts = Array.from({length: 61}, (_, j) => { const v = lo + ((hi - lo) * j) / 60; return [X(v), base - amp * p * gauss(v, m, g.sd)]; });
        return (
          <g key={k}>
            <path d={`M${X(lo)},${base} ${pts.map((q) => `L${q[0]},${q[1]}`).join(" ")} L${X(hi)},${base} Z`} fill={alpha(col, 0.4)} stroke={col} strokeWidth={3}/>
            <Txt x={B.x0 + lw - 16} y={base - 6} size={B.fs * 0.9} anchor="end" op={clamp(p * 2)}>{g.text}</Txt>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Bubble = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const root = pack().size([B.W, B.H]).padding(10)(hierarchy({children: e.items.map((x, k) => ({...x, k}))}).sum((d) => d.value || 0));
  return (
    <g>
      {root.leaves().map((l, n) => {
        const p = pop(T.t - n * 6), d = l.data, col = pal(e, d.k);
        const lit = T.k > 0 && n === 0 ? 0.5 + 0.5 * Math.sin(T.k / 6) : 0;
        const f = Math.min(B.fs * 1.2, (l.r * 1.6) / Math.max(3, d.text.length * 0.6));
        return (
          <g key={n} opacity={clamp(p * 2)} transform={`translate(${B.x0 + l.x},${B.y0 + l.y}) scale(${p * (1 + 0.04 * Math.sin((T.t + n * 9) / 14))})`}>
            <circle r={l.r} fill={alpha(col, 0.35)} stroke={col} strokeWidth={lit ? 6 : 3} style={{filter: lit ? glowF(col, lit) : undefined}}/>
            {f > 13 && <Txt x={0} y={e.show ? -f * 0.4 : 0} size={f}>{d.text}</Txt>}
            {f > 13 && e.show && <Txt x={0} y={f * 0.75} size={f * 0.85} color={col}>{fmt(d.value)}</Txt>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
const TwoColumn = ({e, rect, frame, end, vertical, dumbbell}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const vals = e.items.flatMap((x) => [x.a, x.b]), lo = Math.min(...vals), hi = Math.max(...vals);
  if (dumbbell) {
    const lw = Math.max(...e.items.map((x) => tw(x.text, B.fs))) + 30;
    const X = (v) => B.x0 + lw + ((v - lo) / Math.max(1e-9, hi - lo)) * (B.W - lw - 40);
    const rh = (B.H - B.fs * 2) / e.items.length;
    return (
      <g>
        {[e.left, e.right].map((t, k) => t && <g key={k} opacity={clamp(T.t / 12)}><circle cx={B.x0 + lw + k * 260} cy={B.y0 + B.fs * 0.6} r={B.fs * 0.35} fill={k ? C.hot : pal(e, 0)}/>
          <Txt x={B.x0 + lw + k * 260 + B.fs * 0.6} y={B.y0 + B.fs * 0.6} size={B.fs * 0.85} anchor="start">{t}</Txt></g>)}
        {e.items.map((it, k) => {
          const y = B.y0 + B.fs * 2 + rh * (k + 0.5), p = glide(T.k > 0 ? T.k - k * 5 : -1, 1.4), a = X(it.a), b = X(it.b);
          return (
            <g key={k} opacity={clamp((T.t - k * 6) / 10)}>
              <Txt x={B.x0 + lw - 20} y={y} size={B.fs} anchor="end">{it.text}</Txt>
              <line x1={a} y1={y} x2={lerp(a, b, p)} y2={y} stroke={alpha(C.text, 0.5)} strokeWidth={8} strokeLinecap="round"/>
              <circle cx={a} cy={y} r={B.fs * 0.45} fill={pal(e, 0)}/>
              <circle cx={lerp(a, b, p)} cy={y} r={B.fs * 0.45} fill={C.hot} opacity={clamp(p * 3)}/>
              {e.show && p > 0.95 && <Txt x={b + (b >= a ? 1 : -1) * B.fs * 1.4} y={y} size={B.fs * 0.85} color={C.hot}>{fmt(it.b)}</Txt>}
            </g>
          );
        })}
      </g>
    );
  }
  const Y = (v) => B.y1 - B.fs * 0.6 - ((v - lo) / Math.max(1e-9, hi - lo)) * (B.H - B.fs * 2.4);
  const xa = B.x0 + B.W * 0.3, xb = B.x1 - B.W * 0.3;
  return (
    <g>
      {[[xa, e.left], [xb, e.right]].map(([x, t], k) => (
        <g key={k} opacity={clamp(T.t / 12)}>
          <line x1={x} y1={B.y0 + B.fs * 1.4} x2={x} y2={B.y1} stroke={alpha(C.muted, 0.5)} strokeWidth={3}/>
          <Txt x={x} y={B.y0 + B.fs * 0.5} size={B.fs} color={C.muted}>{t}</Txt>
        </g>
      ))}
      {e.items.map((it, k) => {
        const p = glide(T.k > 0 ? T.k - k * 5 : -1, 1.5), ya = Y(it.a), yb = Y(it.b), col = it.b >= it.a ? C.cool : C.hot;
        return (
          <g key={k} opacity={clamp((T.t - 10 - k * 6) / 10)}>
            <line x1={xa} y1={ya} x2={lerp(xa, xb, p)} y2={lerp(ya, yb, p)} stroke={col} strokeWidth={5}/>
            <circle cx={xa} cy={ya} r={10} fill={col}/>
            {p > 0.98 && <circle cx={xb} cy={yb} r={10} fill={col}/>}
            <Txt x={xa - 24} y={ya} size={B.fs * 0.9} anchor="end">{e.show ? `${it.text} ${fmt(it.a)}` : it.text}</Txt>
            {p > 0.9 && <Txt x={xb + 24} y={yb} size={B.fs * 0.9} anchor="start" color={col}>{e.show ? `${fmt(it.b)} ${it.text}` : it.text}</Txt>}
          </g>
        );
      })}
    </g>
  );
};
export const Slope = (props) => <TwoColumn {...props}/>;
export const Dumbbell = (props) => <TwoColumn {...props} dumbbell/>;

// --------------------------------------------------------------------------------------------------------------
export const Lollipop = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const items = [...e.items].sort((a, b) => b.value - a.value), mx = maxOf(items.map((x) => x.value));
  const n = items.length, xs = spread(n, B.x0, B.x1), base = B.y1 - B.fs * 1.4, top = B.y0 + B.fs * 1.2;
  return (
    <g>
      <line x1={B.x0} y1={base} x2={B.x1} y2={base} stroke={C.muted} strokeWidth={3} opacity={clamp(T.t / 10)}/>
      {items.map((it, k) => {
        const p = glide(T.t - 8 - k * 7, 1.3), y = base - (base - top) * (it.value / mx) * p;
        const lit = T.k > 0 && k === 0 ? 0.5 + 0.5 * Math.sin(T.k / 6) : 0;
        return (
          <g key={k}>
            <line x1={xs[k]} y1={base} x2={xs[k]} y2={y} stroke={alpha(pal(e, 0), 0.8)} strokeWidth={6}/>
            <circle cx={xs[k]} cy={y} r={B.fs * 0.55} fill={lit ? C.hot : pal(e, 0)} opacity={clamp(p * 3)} style={{filter: lit ? glowF(C.hot, lit) : undefined}}/>
            <Txt x={xs[k]} y={base + B.fs * 0.8} size={Math.min(B.fs, (B.W / n) / Math.max(3, it.text.length * 0.6))}>{it.text}</Txt>
            {e.show && p > 0.9 && <Txt x={xs[k]} y={y - B.fs * 1.1} size={B.fs * 0.85}>{fmt(it.value)}</Txt>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Area = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const n = e.series[0].values.length, keys = e.series.map((_, k) => `s${k}`);
  const data = Array.from({length: n}, (_, j) => Object.fromEntries(e.series.map((s, k) => [`s${k}`, Math.max(0, s.values[j])])));
  const layers = d3stack().keys(keys)(data), top = maxOf(layers[layers.length - 1].map((d) => d[1]));
  const lw = vertical ? 0 : Math.max(...e.series.map((s) => tw(s.text, B.fs))) + 40;
  const X = (j) => B.x0 + ((B.W - lw) * j) / (n - 1), Y = (v) => B.y1 - (v / top) * (B.H - B.fs);
  const p = glide(T.t - 6, 2.2);
  const shape = d3area().x((d, j) => X(j)).y0((d) => Y(d[0])).y1((d) => Y(d[1])).curve(curveMonotoneX);
  return (
    <g>
      <defs><clipPath id={`areaclip${e.at}`}><rect x={B.x0} y={B.y0 - 40} width={(B.W - lw) * p + 2} height={B.H + 80}/></clipPath></defs>
      <g clipPath={`url(#areaclip${e.at})`}>
        {layers.map((L, k) => <path key={k} d={shape(L)} fill={alpha(pal(e, k), T.k > 0 && k === layers.length - 1 ? 0.75 : 0.5)} stroke={pal(e, k)} strokeWidth={3}/>)}
      </g>
      {!vertical && layers.map((L, k) => {
        const d = L[n - 1];
        return <Txt key={`t${k}`} x={X(n - 1) + 20} y={Y((d[0] + d[1]) / 2)} size={B.fs * 0.9} anchor="start" color={pal(e, k)} op={clamp((p - 0.9) * 10)}>{e.series[k].text}</Txt>;
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Bump = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const n = e.series[0].values.length, m = e.series.length;
  const ranks = Array.from({length: n}, (_, j) => {
    const order = e.series.map((s, k) => [s.values[j], k]).sort((a, b) => b[0] - a[0]).map((x) => x[1]);
    const r = []; order.forEach((k, pos) => { r[k] = pos; }); return r;
  });
  const lw = Math.max(...e.series.map((s) => tw(s.text, B.fs * 0.9))) + 30;
  const X = (j) => B.x0 + ((B.W - lw) * j) / (n - 1), Y = (r) => B.y0 + B.fs + ((B.H - B.fs * 2) * r) / Math.max(1, m - 1);
  const p = glide(T.t - 6, 2.6);
  return (
    <g>
      {e.series.map((s, k) => {
        const pts = ranks.map((r, j) => [X(j), Y(r[k])]), lit = T.k > 0 && ranks[n - 1][k] === 0;
        return (
          <g key={k}>
            <path d={smoothPath(pts)} fill="none" stroke={pal(e, k)} strokeWidth={lit ? 9 : 6} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p}
                  opacity={T.k > 0 && !lit ? 0.45 : 1} style={{filter: lit ? glowF(pal(e, k), 0.8) : undefined}}/>
            {pts.map((q, j) => <circle key={j} cx={q[0]} cy={q[1]} r={9} fill={pal(e, k)} opacity={p * (n - 1) >= j - 0.05 ? 1 : 0}/>)}
            <Txt x={X(n - 1) + 22} y={Y(ranks[n - 1][k])} size={B.fs * 0.9} anchor="start" color={pal(e, k)} op={clamp((p - 0.9) * 10)}>{s.text}</Txt>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Gauge = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const R = Math.min(B.W * 0.42, B.H * 0.66), cx = B.cx, cy = B.y0 + R + B.fs * 0.8;
  const zones = e.zones && e.zones.length ? e.zones : [];
  const zc = [C.cool, C.accent, C.hot];
  const A = (v) => Math.PI + Math.PI * v;
  const v = clamp(e.value) * glide(T.t - 12, 2.2) + (T.k > 0 ? 0.015 * Math.sin(T.k / 3) : 0);
  return (
    <g>
      {(zones.length ? zones : [""]).map((z, k, all) => {
        const a0 = A(k / all.length), a1 = A((k + 1) / all.length);
        const d = d3arc().innerRadius(R * 0.78).outerRadius(R).startAngle(a0 + Math.PI / 2).endAngle(a1 + Math.PI / 2)();
        const mid = (a0 + a1) / 2;
        return (
          <g key={k} opacity={clamp((T.t - k * 4) / 12)}>
            <path d={d} transform={`translate(${cx},${cy})`} fill={alpha(zones.length ? zc[k % 3] : pal(e, 0), 0.55)}/>
            {z && <Txt x={cx + R * 1.08 * Math.cos(mid)} y={cy + R * 1.08 * Math.sin(mid) - 8} size={B.fs * 0.85} color={C.muted}>{z}</Txt>}
          </g>
        );
      })}
      <line x1={cx} y1={cy} x2={cx + R * 0.86 * Math.cos(A(v))} y2={cy + R * 0.86 * Math.sin(A(v))} stroke={C.text} strokeWidth={9} strokeLinecap="round"/>
      <circle cx={cx} cy={cy} r={R * 0.08} fill={C.text}/>
      {e.text && <Txt x={cx} y={cy + R * 0.08 + B.fs * 1.2} size={B.fs * 1.1}>{e.text}</Txt>}
      {e.show && <Txt x={cx} y={cy - R * 0.38} size={B.fs * 1.6} color={pal(e, 0)}>{`${Math.round(v * 100)}%`}</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Rings = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const n = e.items.length, R = Math.min(B.H * 0.46, B.W * 0.3), cx = vertical ? B.cx : B.x0 + R + 20, cy = B.cy, thick = (R * 0.62) / n;
  return (
    <g>
      {e.items.map((it, k) => {
        const r = R - k * (thick + 8), p = glide(T.t - 8 - k * 8, 2), col = pal(e, k);
        const a = 2 * Math.PI * clamp(it.value) * p;
        const d = d3arc().innerRadius(r - thick).outerRadius(r).startAngle(0).endAngle(a).cornerRadius(thick / 2)();
        return (
          <g key={k}>
            <circle cx={cx} cy={cy} r={r - thick / 2} fill="none" stroke={alpha(col, 0.15)} strokeWidth={thick}/>
            <path d={d} transform={`translate(${cx},${cy})`} fill={col} style={{filter: T.k > 0 ? glowF(col, 0.5) : undefined}}/>
            {!vertical && <g opacity={clamp(p * 2)}>
              <rect x={cx + R + 40} y={B.cy - (n * B.fs * 1.7) / 2 + k * B.fs * 1.7} width={B.fs * 0.8} height={B.fs * 0.8} rx={5} fill={col}/>
              <Txt x={cx + R + 40 + B.fs * 1.3} y={B.cy - (n * B.fs * 1.7) / 2 + k * B.fs * 1.7 + B.fs * 0.4} size={B.fs} anchor="start">
                {e.show ? `${it.text}  ${fmt(it.value * 100)}%` : it.text}</Txt></g>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Normal = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const base = B.y1 - B.fs * 1.6, top = B.y0 + B.fs, X = (z) => B.cx + (z / 3.6) * (B.W / 2), Y = (y) => base - y * (base - top);
  const draw = glide(T.t - 6, 2);
  const pts = Array.from({length: 121}, (_, j) => { const z = -3.6 + (7.2 * j) / 120; return [X(z), Y(gauss(z))]; });
  const bands = [[3, "99.7%"], [2, "95%"], [1, "68%"]];
  return (
    <g>
      <line x1={B.x0} y1={base} x2={B.x1} y2={base} stroke={C.muted} strokeWidth={3}/>
      {e.sigma && bands.map(([s, txt], k) => {
        const q = glide(T.k - k * 14, 1.4);
        if (q <= 0) return null;
        const seg = pts.filter((pt) => Math.abs((pt[0] - B.cx) / (B.W / 2) * 3.6) <= s * q + 1e-6);
        return (
          <g key={k}>
            <path d={`M${seg[0][0]},${base} ${seg.map((pt) => `L${pt[0]},${pt[1]}`).join(" ")} L${seg[seg.length - 1][0]},${base} Z`} fill={alpha(pal(e, k), 0.32)}/>
            <Txt x={s === 1 ? B.cx : X(s - 0.5)} y={s === 1 ? base - (base - top) * 0.45 : base - (base - top) * (s === 2 ? 0.22 : 0.07) - B.fs * 0.2}
                 size={B.fs * (s === 1 ? 1 : 0.8)} op={q}>{s === 1 ? `±1σ ${txt}` : `±${s}σ ${txt}`}</Txt>
          </g>
        );
      })}
      <path d={smoothPath(pts)} fill="none" stroke={pal(e, 0)} strokeWidth={6} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - draw}/>
      <line x1={B.cx} y1={base} x2={B.cx} y2={top} stroke={C.hot} strokeWidth={3} strokeDasharray="8 8" opacity={clamp((draw - 0.8) * 5)}/>
      {e.unit && <Txt x={B.cx} y={B.y1 - B.fs * 0.5} size={B.fs * 0.9} color={C.muted}>{e.unit}</Txt>}
      {e.text && <Txt x={B.x0 + 10} y={top} size={B.fs * 0.9} anchor="start" color={C.muted} op={clamp((T.t - 20) / 14)}>{e.text}</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Cdf = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const base = B.y1 - B.fs * 1.4, top = B.y0 + B.fs * 0.6;
  const F = (z) => 1 / (1 + Math.exp(-1.7 * z));
  const X = (z) => B.x0 + ((z + 3.5) / 7) * B.W, Y = (f) => base - f * (base - top);
  const pts = Array.from({length: 81}, (_, j) => { const z = -3.5 + (7 * j) / 80; return [X(z), Y(F(z))]; });
  const target = e.percentile / 100, zt = Math.log(target / (1 - target)) / 1.7;
  const q = glide(T.k, 1.8), z = lerp(-3.2, zt, q), px = X(z), py = Y(F(z));
  return (
    <g>
      <line x1={B.x0} y1={base} x2={B.x1} y2={base} stroke={C.muted} strokeWidth={3}/>
      <line x1={B.x0} y1={base} x2={B.x0} y2={top} stroke={C.muted} strokeWidth={3}/>
      <path d={smoothPath(pts)} fill="none" stroke={pal(e, 0)} strokeWidth={6} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - glide(T.t - 6, 2)}/>
      {T.k > 0 && <g>
        <line x1={px} y1={base} x2={px} y2={py} stroke={C.hot} strokeWidth={3} strokeDasharray="8 8"/>
        <line x1={B.x0} y1={py} x2={px} y2={py} stroke={C.hot} strokeWidth={3} strokeDasharray="8 8"/>
        <circle cx={px} cy={py} r={13} fill={C.hot} style={{filter: glowF(C.hot, 0.8)}}/>
        <Txt x={px} y={py - B.fs * 1.1} size={B.fs * 1.1} color={C.hot} op={clamp(q * 3)}>{`p${fmt(e.percentile)}`}</Txt>
        {e.text && <Txt x={Math.min(px + 30, B.x1 - tw(e.text, B.fs * 0.9))} y={base - B.fs * 0.9} size={B.fs * 0.9} anchor="start" op={clamp((q - 0.8) * 5)}>{e.text}</Txt>}
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Intervals = ({e, rect, frame, end, vertical, seed = 0}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), r = rng(seed + 7);
  const n = e.count, missing = new Set(Array.from({length: e.miss}, (_, k) => Math.floor(((k + 0.5) * n) / Math.max(1, e.miss) + 1) % n));
  const X = (v) => B.cx + v * (B.W * 0.36), rh = (B.H - B.fs * 1.6) / n;
  return (
    <g>
      <line x1={B.cx} y1={B.y0} x2={B.cx} y2={B.y1 - B.fs * 1.2} stroke={C.hot} strokeWidth={4} opacity={clamp(T.t / 10)}/>
      {e.text && <Txt x={B.cx} y={B.y1 - B.fs * 0.5} size={B.fs * 0.9} color={C.hot}>{e.text}</Txt>}
      {Array.from({length: n}, (_, k) => {
        const miss = missing.has(k), c = miss ? (r() > 0.5 ? 1 : -1) * (0.75 + 0.3 * r()) : (r() - 0.5) * 0.7, half = 0.38 + 0.12 * r();
        const p = glide(T.t - 8 - k * 2.2, 0.8), y = B.y0 + rh * (k + 0.5);
        const lit = miss && T.k > 0 ? 0.5 + 0.5 * Math.sin(T.k / 5) : 0;
        const col = miss ? C.hot : pal(e, 0);
        return (
          <g key={k} opacity={clamp(p * 2) * (T.k > 0 && !miss ? 0.55 : 1)}>
            <line x1={X(c - half * p)} y1={y} x2={X(c + half * p)} y2={y} stroke={col} strokeWidth={Math.max(3, rh * 0.35)} strokeLinecap="round"
                  style={{filter: lit ? glowF(col, lit) : undefined}}/>
            <circle cx={X(c)} cy={y} r={Math.max(4, rh * 0.32)} fill={C.text}/>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Calendar = ({e, rect, frame, end, vertical, seed = 0}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), r = rng(seed + 3);
  const W = e.weeks, cell = Math.min((B.W - 10) / W, (B.H - B.fs * 1.8) / 7), x0 = B.cx - (cell * W) / 2, y0 = B.y0 + B.fs * 1.6;
  const vals = Array.from({length: W * 7}, (_, n) => { const base = 0.15 + 0.6 * (n / (W * 7)); return clamp(base + (r() - 0.5) * 0.7); });
  const sweep = (T.t - 6) * 2.4;
  return (
    <g>
      {e.text && <Txt x={x0} y={B.y0 + B.fs * 0.6} size={B.fs} anchor="start" op={clamp(T.t / 10)}>{e.text}</Txt>}
      {vals.map((v, n) => {
        const c = Math.floor(n / 7), d = n % 7, on = sweep >= n;
        const lit = T.k > 0 && v > 0.8 ? 0.4 + 0.3 * Math.sin((T.k + n) / 5) : 0;
        return <rect key={n} x={x0 + c * cell + 2} y={y0 + d * cell + 2} width={cell - 4} height={cell - 4} rx={cell * 0.2}
                     fill={on ? alpha(pal(e, 0), 0.12 + 0.85 * v) : alpha(C.muted, 0.12)} stroke={lit ? C.hot : "none"} strokeWidth={3}/>;
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Butterfly = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const n = e.rows.length, mx = maxOf([...e.left, ...e.right]), lab = Math.max(...e.rows.map((x) => tw(x, B.fs * 0.85))) + 24;
  const half = (B.W - lab) / 2, rh = (B.H - B.fs * 1.8) / n, y0 = B.y0 + B.fs * 1.8;
  return (
    <g>
      {[e.lname, e.rname].map((t, k) => t && <Txt key={k} x={k ? B.cx + lab / 2 + half / 2 : B.cx - lab / 2 - half / 2} y={B.y0 + B.fs * 0.6}
                                                size={B.fs} color={k ? C.hot : pal(e, 0)} op={clamp(T.t / 10)}>{t}</Txt>)}
      {e.rows.map((rw, k) => {
        const y = y0 + rh * (n - 1 - k), p = glide(T.t - 8 - k * 5, 1.3);
        const wl = (half * e.left[k]) / mx * p, wr = (half * e.right[k]) / mx * p;
        return (
          <g key={k}>
            <rect x={B.cx - lab / 2 - wl} y={y + 3} width={wl} height={rh - 6} rx={5} fill={alpha(pal(e, 0), 0.8)}/>
            <rect x={B.cx + lab / 2} y={y + 3} width={wr} height={rh - 6} rx={5} fill={alpha(C.hot, 0.8)}/>
            <Txt x={B.cx} y={y + rh / 2} size={Math.min(B.fs * 0.85, rh * 0.6)} color={C.muted}>{rw}</Txt>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Numberline = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const X = (v) => B.x0 + 30 + ((v - e.lo) / (e.hi - e.lo)) * (B.W - 60), y = B.cy + B.fs;
  const sorted = [...e.values].sort((a, b) => a - b);
  const mean = sorted.reduce((s, x) => s + x, 0) / sorted.length;
  const med = sorted.length % 2 ? sorted[(sorted.length - 1) / 2] : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2;
  const target = e.marker === "median" ? med : mean, q = glide(T.k, 1.6);
  const counts = {};
  return (
    <g>
      <line x1={B.x0} y1={y} x2={B.x1} y2={y} stroke={C.muted} strokeWidth={4} opacity={clamp(T.t / 10)}/>
      {[e.lo, e.hi].map((v, k) => <Txt key={k} x={X(v)} y={y + B.fs * 1.1} size={B.fs * 0.85} color={C.muted} op={clamp(T.t / 10)}>{e.show ? fmt(v) : ""}</Txt>)}
      {e.unit && <Txt x={B.x1} y={y + B.fs * 2.2} size={B.fs * 0.85} anchor="end" color={C.muted}>{e.unit}</Txt>}
      {e.values.map((v, k) => {
        counts[v] = (counts[v] || 0) + 1;
        const stack = counts[v] - 1, p = pop(T.t - 10 - k * 6), dy = (1 - p) * -120;
        return <circle key={k} cx={X(v)} cy={y - 22 - stack * 34 + dy} r={14} fill={pal(e, 0)} opacity={clamp(p * 2)}/>;
      })}
      {e.marker !== "none" && T.k > 0 && <g>
        <path d={`M${X(lerp(e.lo, target, q))},${y + 6} l-16,30 l32,0 Z`} fill={C.hot} style={{filter: glowF(C.hot, 0.7)}}/>
        <Txt x={X(lerp(e.lo, target, q))} y={y + B.fs * 2.1} size={B.fs} color={C.hot}>{e.show ? `${e.marker} ${fmt(target)}` : e.marker}</Txt>
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Beeswarm = ({e, rect, frame, end, vertical, seed = 0}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), g = e.groups.length;
  const lw = Math.max(...e.groups.map((x) => tw(x, B.fs))) + 30, rh = (B.H - B.fs * 1.4) / g, r = Math.max(6, Math.min(14, rh / 9));
  const dots = useDots(e, seed, g);
  return (
    <g>
      {e.groups.map((name, k) => <Txt key={k} x={B.x0 + lw - 18} y={B.y0 + rh * (k + 0.5)} size={B.fs} anchor="end" op={clamp(T.t / 10)}>{name}</Txt>)}
      {dots.map((d, n) => {
        const p = glide(T.t - 8 - n * 0.5, 0.9), cy = B.y0 + rh * (d.g + 0.5) + d.off * r * 2.05;
        const cx = B.x0 + lw + d.x * (B.W - lw - 20);
        const lit = T.k > 0 && d.x > 0.85 ? 0.6 : 0;
        return <circle key={n} cx={cx} cy={lerp(B.y0 - 30, cy, p)} r={r} fill={lit ? C.hot : pal(e, d.g)} opacity={clamp(p * 2) * 0.9}/>;
      })}
      {e.text && <Txt x={B.x0 + lw + (B.W - lw) / 2} y={B.y1 - B.fs * 0.4} size={B.fs * 0.9} color={C.muted}>{e.text}</Txt>}
    </g>
  );
};
const useDots = (e, seed, g) => React.useMemo(() => {
  const r = rng(seed + 11), out = [];
  for (let k = 0; k < g; k++) {
    const used = {};
    for (let j = 0; j < Math.round(e.n / g); j++) {
      const z = (r() + r() + r() - 1.5) * 0.36 + 0.42 + k * 0.1, x = clamp(z, 0.03, 0.97), bin = Math.round(x * 40);
      used[bin] = (used[bin] || 0) + 1;
      const c = used[bin] - 1;
      out.push({g: k, x, off: c % 2 ? -Math.ceil(c / 2) : Math.ceil(c / 2)});
    }
  }
  return out;
}, [e.n, g, seed]);

// --------------------------------------------------------------------------------------------------------------
export const Scatter = ({e, rect, frame, end, vertical, seed = 0}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const pts = React.useMemo(() => {
    const r = rng(seed + 5);
    return Array.from({length: 46}, () => { const x = r() * 2 - 1, n = (r() + r() + r() - 1.5) * 1.1; return [x, n]; });
  }, [seed]);
  const q = glide(T.k, 2), rho = lerp(e.start, e.corr, T.k > 0 ? q : 0);
  const X = (x) => B.x0 + 40 + ((x + 1) / 2) * (B.W - 80), Y = (y) => B.cy - y * (B.H * 0.36);
  return (
    <g>
      <line x1={B.x0 + 20} y1={B.y1 - B.fs * 1.2} x2={B.x1} y2={B.y1 - B.fs * 1.2} stroke={C.muted} strokeWidth={3}/>
      <line x1={B.x0 + 20} y1={B.y0} x2={B.x0 + 20} y2={B.y1 - B.fs * 1.2} stroke={C.muted} strokeWidth={3}/>
      {e.xlabel && <Txt x={B.cx} y={B.y1 - B.fs * 0.3} size={B.fs * 0.9} color={C.muted}>{e.xlabel}</Txt>}
      {e.ylabel && <Txt x={B.x0 + 34} y={B.y0 + B.fs * 0.4} size={B.fs * 0.9} color={C.muted} anchor="start">{e.ylabel}</Txt>}
      {pts.map(([x, n], k) => {
        const y = rho * x + Math.sqrt(Math.max(0, 1 - rho * rho)) * n * 0.6, p = pop(T.t - 6 - k * 0.8);
        return <circle key={k} cx={X(x)} cy={Y(clamp(y, -1.25, 1.25))} r={11 * p} fill={alpha(pal(e, 0), 0.85)}/>;
      })}
      {T.k > 0 && Math.abs(rho) > 0.2 && <line x1={X(-1)} y1={Y(-rho)} x2={X(1)} y2={Y(rho)} stroke={C.hot} strokeWidth={5} opacity={clamp((Math.abs(rho) - 0.2) * 2)}/>}
      {T.k > 0 && <Txt x={B.x1 - 20} y={B.y0 + B.fs * 0.5} size={B.fs * 1.2} anchor="end" color={C.hot}>{`r = ${rho.toFixed(2)}`}</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Confusion = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const [tp, fn, fp, tn] = e.values, side = Math.min(B.H - B.fs * 2.6, B.W * 0.55), cell = side / 2;
  const x0 = B.cx - side / 2 + B.fs, y0 = B.y0 + B.fs * 2.4;
  const cells = [[tp, "TP", true], [fn, "FN", false], [fp, "FP", false], [tn, "TN", true]];
  const mx = maxOf(e.values);
  return (
    <g>
      <Txt x={x0 + side / 2} y={B.y0 + B.fs * 0.5} size={B.fs * 0.9} color={C.muted}>predicted</Txt>
      {[e.pos, e.neg].map((t, k) => <Txt key={`c${k}`} x={x0 + cell * (k + 0.5)} y={B.y0 + B.fs * 1.5} size={B.fs * 0.9}>{t}</Txt>)}
      {[e.pos, e.neg].map((t, k) => <Txt key={`r${k}`} x={x0 - 16} y={y0 + cell * (k + 0.5)} size={B.fs * 0.9} anchor="end">{t}</Txt>)}
      {cells.map(([v, tag, good], n) => {
        const i = Math.floor(n / 2), j = n % 2, p = glide(T.t - 8 - n * 7), col = good ? C.cool : C.hot;
        const lit = T.k > 0 && !good ? 0.5 + 0.5 * Math.sin(T.k / 6) : 0;
        return (
          <g key={n} opacity={clamp(p * 2)}>
            <rect x={x0 + j * cell + 5} y={y0 + i * cell + 5} width={cell - 10} height={cell - 10} rx={12}
                  fill={alpha(col, 0.15 + 0.55 * (v / mx) * p)} stroke={col} strokeWidth={lit ? 6 : 3} style={{filter: lit ? glowF(col, lit) : undefined}}/>
            <Txt x={x0 + (j + 0.5) * cell} y={y0 + (i + 0.5) * cell - (e.show ? B.fs * 0.5 : 0)} size={B.fs * 1.1} color={col}>{tag}</Txt>
            {e.show && <Txt x={x0 + (j + 0.5) * cell} y={y0 + (i + 0.5) * cell + B.fs * 0.8} size={B.fs * 1.1}>{fmt(Math.round(v * p))}</Txt>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
const trendFn = {up: (x) => 0.15 + 0.7 * x * x, down: (x) => 0.85 - 0.7 * x, flat: (x) => 0.5 + 0.05 * Math.sin(x * 20),
                 spike: (x) => 0.3 + (x > 0.7 && x < 0.82 ? 0.6 : 0.05 * Math.sin(x * 25)), cycle: (x) => 0.5 + 0.35 * Math.sin(x * 12)};
export const Spark = ({x, y, w, h, trend, p, color, width = 5}) => {
  const f = trendFn[trend] || trendFn.flat;
  const pts = Array.from({length: 40}, (_, j) => [x + (w * j) / 39, y + h - h * f(j / 39)]);
  return <path d={smoothPath(pts)} fill="none" stroke={color} strokeWidth={width} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p}/>;
};
export const Multiples = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const n = e.items.length, cols = vertical ? 2 : Math.min(n, 3), rows = Math.ceil(n / cols);
  const cw = B.W / cols, ch = B.H / rows;
  return (
    <g>
      {e.items.map((it, k) => {
        const c = k % cols, r = Math.floor(k / cols), x = B.x0 + c * cw + 12, y = B.y0 + r * ch + 8, w = cw - 24, h = ch - 16;
        const p = glide(T.t - 6 - k * 7, 1.6), lit = T.k > 0 && (it.trend === "spike" || it.trend === "up") ? 0.5 + 0.5 * Math.sin(T.k / 6) : 0;
        return (
          <g key={k} opacity={clamp(p * 3)}>
            <rect x={x} y={y} width={w} height={h} rx={14} fill={alpha(C.panel, 0.9)} stroke={lit ? C.hot : alpha(C.muted, 0.4)} strokeWidth={lit ? 5 : 2}
                  style={{filter: lit ? glowF(C.hot, lit) : undefined}}/>
            <Txt x={x + 18} y={y + B.fs * 0.8} size={B.fs * 0.9} anchor="start">{it.text}</Txt>
            <Spark x={x + 16} y={y + B.fs * 1.6} w={w - 32} h={h - B.fs * 2.2} trend={it.trend} p={p} color={lit ? C.hot : pal(e, k)}/>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Variance = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const vals = e.values, n = vals.length, mean = vals.reduce((s, x) => s + x, 0) / n;
  const lo = Math.min(...vals), hi = Math.max(...vals), span = Math.max(1e-9, hi - lo);
  const unit = Math.min((B.H * 0.8) / span, (B.W / n) * 1.6 / Math.max(1e-9, Math.max(hi - mean, mean - lo)));
  const xs = spread(n, B.x0, B.x1), Y = (v) => B.cy - (v - mean) * unit;
  const q = glide(T.k, 1.6);
  return (
    <g>
      <line x1={B.x0} y1={Y(mean)} x2={B.x1} y2={Y(mean)} stroke={C.hot} strokeWidth={4} strokeDasharray="10 8" opacity={clamp((T.t - 12) / 10)}/>
      <Txt x={B.x0} y={Y(mean) - B.fs * 0.8} size={B.fs * 0.9} anchor="start" color={C.hot} op={clamp((T.t - 12) / 10)}>{e.show ? `mean ${fmt(mean)}` : "mean"}</Txt>
      {vals.map((v, k) => {
        const p = pop(T.t - k * 5), d = (v - mean) * unit, side = Math.abs(d);
        return (
          <g key={k}>
            {e.squares && T.k > 0 && <rect x={xs[k]} y={Math.min(Y(v), Y(mean))} width={side * q * 0.9} height={side} fill={alpha(pal(e, k), 0.28)} stroke={pal(e, k)} strokeWidth={2}/>}
            <line x1={xs[k]} y1={Y(mean)} x2={xs[k]} y2={Y(v)} stroke={pal(e, k)} strokeWidth={4} opacity={clamp((T.t - 20 - k * 3) / 10)}/>
            <circle cx={xs[k]} cy={Y(v)} r={13 * p} fill={C.text}/>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Pie = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const R = Math.min(B.H * 0.44, B.W * 0.28), cx = vertical ? B.cx : B.x0 + B.W * 0.32, cy = B.cy;
  const arcs = d3pie().value((d) => d.value).sort(null)(e.items);
  const tot = sum(e.items.map((x) => x.value)) || 1;
  const sweep = glide(T.t - 6, 2.2) * 2 * Math.PI;
  return (
    <g>
      {arcs.map((a, k) => {
        if (a.startAngle >= sweep) return null;
        const pull = T.k > 0 ? glide(T.k - k * 8, 1.2) * R * 0.1 : 0, mid = (a.startAngle + Math.min(a.endAngle, sweep)) / 2;
        const d = d3arc().innerRadius(0).outerRadius(R).startAngle(a.startAngle).endAngle(Math.min(a.endAngle, sweep)).padAngle(0.015)();
        const lx = cx + R * 1.25 * Math.sin(mid), ly = cy - R * 1.25 * Math.cos(mid);
        return (
          <g key={k}>
            <path d={d} transform={`translate(${cx + pull * Math.sin(mid)},${cy - pull * Math.cos(mid)})`} fill={alpha(pal(e, k), 0.85)} stroke={C.bg} strokeWidth={3}/>
            {sweep >= a.endAngle && <Txt x={vertical ? lx : B.x0 + B.W * 0.66} y={vertical ? ly : B.y0 + B.H * (0.2 + (0.6 * k) / Math.max(1, arcs.length - 1))}
                                         size={B.fs} anchor={vertical ? "middle" : "start"} color={pal(e, k)}>
              {e.show ? `${a.data.text} ${Math.round((100 * a.data.value) / tot)}%` : a.data.text}</Txt>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Waterfall = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  let run = 0;
  const steps = e.items.map((it, k) => { const from = k === 0 ? 0 : run; run = k === 0 ? it.value : run + it.value; return {from, to: run, it}; });
  const vals = steps.flatMap((s) => [s.from, s.to]), lo = Math.min(0, ...vals), hi = Math.max(...vals);
  const n = steps.length + 1, bw = B.W / n, base = B.y1 - B.fs * 1.6, top = B.y0 + B.fs;
  const Y = (v) => base - ((v - lo) / Math.max(1e-9, hi - lo)) * (base - top);
  return (
    <g>
      {steps.map((s, k) => {
        const p = glide(T.t - 8 - k * 9, 1.1), up = s.to >= s.from, col = k === 0 ? pal(e, 0) : up ? C.cool : C.hot;
        const ya = Y(s.from), yb = lerp(ya, Y(s.to), p), x = B.x0 + k * bw + bw * 0.15;
        return (
          <g key={k}>
            <rect x={x} y={Math.min(ya, yb)} width={bw * 0.7} height={Math.abs(yb - ya)} rx={6} fill={alpha(col, 0.8)}/>
            {k < steps.length - 1 && p > 0.95 && <line x1={x + bw * 0.7} y1={Y(s.to)} x2={x + bw} y2={Y(s.to)} stroke={C.muted} strokeWidth={2} strokeDasharray="6 6"/>}
            <Txt x={x + bw * 0.35} y={base + B.fs * 0.8} size={Math.min(B.fs * 0.85, bw / Math.max(3, s.it.text.length * 0.6))}>{s.it.text}</Txt>
            {e.show && p > 0.9 && <Txt x={x + bw * 0.35} y={Math.min(ya, yb) - B.fs * 0.6} size={B.fs * 0.8} color={col}>{`${k && up ? "+" : ""}${fmt(s.it.value)}`}</Txt>}
          </g>
        );
      })}
      {T.k > 0 && (() => {
        const x = B.x0 + steps.length * bw + bw * 0.15, p = glide(T.k, 1.3);
        return (
          <g>
            <rect x={x} y={lerp(Y(lo), Y(run), p)} width={bw * 0.7} height={Math.abs(Y(lo) - lerp(Y(lo), Y(run), p))} rx={6} fill={C.text} style={{filter: glowF(C.text, 0.5)}}/>
            <Txt x={x + bw * 0.35} y={base + B.fs * 0.8} size={B.fs * 0.85}>total</Txt>
            {e.show && <Txt x={x + bw * 0.35} y={Y(run) - B.fs * 0.6} size={B.fs * 0.85}>{fmt(run)}</Txt>}
          </g>
        );
      })()}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Stacked = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const n = e.groups.length, lw = Math.max(...e.groups.map((g) => tw(g.text, B.fs))) + 26, legendH = B.fs * 1.8;
  const rh = (B.H - legendH) / n;
  return (
    <g>
      {e.legend.map((l, k) => <g key={`l${k}`} opacity={clamp(T.t / 10)}>
        <rect x={B.x0 + lw + k * (B.W - lw) / e.legend.length} y={B.y0 + 6} width={B.fs * 0.8} height={B.fs * 0.8} rx={5} fill={pal(e, k)}/>
        <Txt x={B.x0 + lw + k * (B.W - lw) / e.legend.length + B.fs * 1.2} y={B.y0 + 6 + B.fs * 0.4} size={B.fs * 0.85} anchor="start">{l}</Txt></g>)}
      {e.groups.map((g, i) => {
        const tot = sum(g.parts) || 1, y = B.y0 + legendH + rh * i + rh * 0.15, h = rh * 0.7, p = glide(T.t - 8 - i * 8, 1.4);
        let x = B.x0 + lw;
        return (
          <g key={i}>
            <Txt x={B.x0 + lw - 16} y={y + h / 2} size={B.fs} anchor="end">{g.text}</Txt>
            {g.parts.map((v, k) => {
              const w = ((B.W - lw) * v) / tot * p, x0 = x;
              x += w;
              return (
                <g key={k}>
                  <rect x={x0} y={y} width={Math.max(0, w - 3)} height={h} rx={6} fill={alpha(pal(e, k), T.k > 0 && k === 0 ? 0.95 : 0.7)}/>
                  {e.show && w > B.fs * 2.4 && <Txt x={x0 + w / 2} y={y + h / 2} size={B.fs * 0.85}>{`${Math.round((100 * v) / tot)}%`}</Txt>}
                </g>
              );
            })}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Latency = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const base = B.y1 - B.fs * 1.6, top = B.y0 + B.fs * 1.4;
  const f = (x) => Math.pow(x, 1.6) * Math.exp(-x * 1.25);           // a skewed shape with a long right tail
  const mx = f(1.6 / 1.25);
  const X = (x) => B.x0 + (x / 9) * B.W, Y = (v) => base - (v / mx) * (base - top);
  const pts = Array.from({length: 120}, (_, j) => { const x = 0.01 + (9 * j) / 119; return [X(x), Y(f(x))]; });
  const marks = [["p50", 1.55], ["p95", 3.9], ["p99", 5.4]];
  return (
    <g>
      <line x1={B.x0} y1={base} x2={B.x1} y2={base} stroke={C.muted} strokeWidth={3}/>
      <path d={`M${X(0.01)},${base} ${pts.map((q) => `L${q[0]},${q[1]}`).join(" ")} L${X(9)},${base} Z`} fill={alpha(pal(e, 0), 0.3)} opacity={clamp((T.t - 14) / 16)}/>
      <path d={smoothPath(pts)} fill="none" stroke={pal(e, 0)} strokeWidth={5} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - glide(T.t - 4, 2)}/>
      {marks.map(([name, x], k) => {
        const q = glide(T.k - k * 10, 1.2);
        if (q <= 0) return null;
        const col = k === 2 ? C.hot : k === 1 ? C.violet : C.cool;
        return (
          <g key={k} opacity={q}>
            <line x1={X(x)} y1={base} x2={X(x)} y2={top - B.fs * 0.2} stroke={col} strokeWidth={4} strokeDasharray="8 7"/>
            <Txt x={X(x)} y={top - B.fs * 0.8} size={B.fs} color={col}>{name}</Txt>
          </g>
        );
      })}
      {T.k > 0 && e.text && <Txt x={X(7)} y={Y(f(7)) - B.fs * 1.6} size={B.fs * 0.9} color={C.hot} op={clamp((T.k - 30) / 14)}>{e.text}</Txt>}
      {e.unit && <Txt x={B.x1} y={base + B.fs * 0.9} size={B.fs * 0.85} anchor="end" color={C.muted}>{e.unit}</Txt>}
    </g>
  );
};

export const CHARTS = {waffle: Waffle, treemap: Treemap, sankey: Sankey, funnel: Funnel, radar: Radar, heatmap: Heatmap,
  histogram: Histogram, boxplot: Boxplot, ridgeline: Ridgeline, bubble: Bubble, slope: Slope, dumbbell: Dumbbell,
  lollipop: Lollipop, area: Area, bump: Bump, gauge: Gauge, rings: Rings, normal: Normal, cdf: Cdf, intervals: Intervals,
  calendar: Calendar, butterfly: Butterfly, numberline: Numberline, beeswarm: Beeswarm, scatter: Scatter,
  confusion: Confusion, multiples: Multiples, variance: Variance, pie: Pie, waterfall: Waterfall, stacked: Stacked,
  latency: Latency};
