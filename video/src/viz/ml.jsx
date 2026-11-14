// Machine-learning techniques (blogwriter/vizlib.py, family "ml"): neurons, attention, tokens, classifiers,
// clustering, training curves, generation and retrieval, each moving the way the idea works.
import {Arrow, C, Card, Chip, Ico, Packet, React, Txt, alpha, along, box, clamp, fmt, gauss, glide, glowF, lerp, pal, pop, rng,
        row, smoothPath, spread, timing, tw} from "./kit";

const cyc = (t, start, period) => { const x = (t - start) / period; return {n: Math.floor(x), ph: x - Math.floor(x), on: t >= start}; };

// --------------------------------------------------------------------------------------------------------------
export const Neuron = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.inputs.length;
  const ix = B.x0 + B.W * 0.14, iy = row(n, B.y0 + 40, B.y1 - 40), sum = [B.x0 + B.W * 0.48, B.cy], act = [B.x0 + B.W * 0.68, B.cy], out = [B.x1 - B.W * 0.1, B.cy];
  const w = [0.9, 0.35, 0.65, 0.5, 0.8], flow = cyc(T.t, 30, 60);
  return (
    <g>
      {iy.map((y, k) => (
        <g key={k}>
          <line x1={ix + 80} y1={y} x2={sum[0] - 60} y2={sum[1]} stroke={pal(e, k)} strokeWidth={3 + 10 * w[k % 5]} opacity={0.35 + 0.4 * glide(T.t - 10 - k * 4)} strokeLinecap="round"/>
          <Chip x={ix} y={y} text={e.inputs[k]} color={pal(e, k)} p={pop(T.t - k * 4)} fs={B.fs * 0.9} fill/>
          <Txt x={(ix + sum[0]) / 2} y={(y + sum[1]) / 2 - 18} size={B.fs * 0.75} color={C.muted} op={clamp((T.t - 20) / 12)}>{`w${k + 1}`}</Txt>
          {flow.on && <Packet pts={[[ix + 80, y], [sum[0] - 60, sum[1]]]} t={flow.ph * 2} color={pal(e, k)}/>}
        </g>
      ))}
      <circle cx={sum[0]} cy={sum[1]} r={60} fill={alpha(C.panel, 0.95)} stroke={C.text} strokeWidth={4} opacity={clamp(pop(T.t - 14) * 2)}/>
      <Txt x={sum[0]} y={sum[1]} size={B.fs * 1.6}>Σ</Txt>
      <Arrow a={[sum[0] + 60, sum[1]]} b={[act[0] - 70, act[1]]} draw={glide(T.t - 24)} color={C.muted}/>
      <rect x={act[0] - 70} y={act[1] - 60} width={140} height={120} rx={14} fill={alpha(C.panel, 0.95)} stroke={pal(e, 0)} strokeWidth={4} opacity={clamp((T.t - 28) / 10)}/>
      <path d={smoothPath(Array.from({length: 20}, (_, j) => { const x = -4 + (8 * j) / 19; return [act[0] - 55 + (110 * j) / 19, act[1] + 40 - 80 / (1 + Math.exp(-x * 1.4))]; }))}
            fill="none" stroke={pal(e, 0)} strokeWidth={5} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - glide(T.t - 30, 1)}/>
      <Arrow a={[act[0] + 70, act[1]]} b={[out[0] - 70, out[1]]} draw={glide(T.t - 36)} color={C.muted}/>
      <Chip x={out[0]} y={out[1]} text={e.output || "output"} color={C.hot} p={pop(T.t - 40)} fs={B.fs} fill lit={flow.on && flow.ph > 0.7 ? 0.7 : 0}/>
      {flow.on && <Packet pts={[[sum[0] + 60, sum[1]], [out[0] - 70, out[1]]]} t={(flow.ph - 0.5) * 2} color={C.hot}/>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Attention = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.tokens.length, f = e.focus;
  const xs = spread(n, B.x0, B.x1), yq = B.y0 + B.H * 0.2, yk = B.y1 - B.H * 0.2;
  const weight = (k) => (k === f ? 0.25 : k === Math.max(0, f - 3) ? 1 : k === Math.max(0, f - 2) ? 0.55 : 0.12 + 0.08 * ((k * 7) % 3));
  const q = glide(T.k > 0 ? T.k : T.t - 40, 1.6);
  return (
    <g>
      {xs.map((x, k) => <Chip key={`k${k}`} x={x} y={yk + (vertical && k % 2 ? B.fs * 2.2 : 0)} text={e.tokens[k]} color={k === f ? C.hot : pal(e, 0)} p={pop(T.t - k * 3)}
                              fs={Math.min(B.fs, ((B.W / n) * (vertical ? 1.8 : 0.95)) / Math.max(2, e.tokens[k].length * 0.62 + 1.2))} fill={weight(k) > 0.5 && q > 0.5}/>)}
      <Chip x={xs[f]} y={yq} text={e.tokens[f]} color={C.hot} p={pop(T.t - 20)} fs={B.fs * 1.1} fill lit={0.5}/>
      {xs.map((x, k) => k !== f && <line key={`l${k}`} x1={xs[f]} y1={yq + B.fs} x2={x} y2={yk - B.fs} stroke={C.hot} strokeWidth={2 + 16 * weight(k) * q}
                                          opacity={0.15 + 0.85 * weight(k) * q} strokeLinecap="round"/>)}
      <Txt x={B.x0} y={yq} size={B.fs * 0.85} anchor="start" color={C.muted} op={clamp(T.t / 12)}>looking from</Txt>
      {q > 0.8 && <Txt x={xs[Math.max(0, f - 3)]} y={yk + B.fs * (vertical ? 4 : 1.8)} size={B.fs * 0.85} color={C.hot}>most attention</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Tokenize = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const pieces = React.useMemo(() => e.text.split(/\s+/).flatMap((w) => (w.length > 6 ? [w.slice(0, Math.ceil(w.length / 2)), `${w.slice(Math.ceil(w.length / 2))}`] : [w])), [e.text]);
  const split = glide(T.k > 0 ? T.k : T.t - 40, 1.4);
  const fs = Math.min(B.fs * 1.2, (B.W * 0.9) / Math.max(10, e.text.length * 0.66));
  let x = B.cx - (pieces.reduce((s, p) => s + tw(p, fs) + fs * 1.4, 0)) / 2;
  return (
    <g>
      <Txt x={B.cx} y={B.y0 + B.H * 0.22} size={fs} op={clamp((T.t - 4) / 10) * (1 - split * 0.6)}>{e.text}</Txt>
      {pieces.map((p, k) => {
        const w = tw(p, fs) + fs * 1.4, cx = x + w / 2;
        x += w;
        return (
          <g key={k} opacity={clamp(split * 2 - k * 0.08)}>
            <rect x={cx - w / 2 + 4} y={B.cy - fs * 0.8} width={w - 8} height={fs * 1.7} rx={10} fill={alpha(pal(e, k), 0.35)} stroke={pal(e, k)} strokeWidth={3}/>
            <Txt x={cx} y={B.cy + 2} size={fs * 0.9}>{p}</Txt>
          </g>
        );
      })}
      <Txt x={B.cx} y={B.y1 - B.fs * 0.4} size={B.fs * 0.9} color={C.muted} op={clamp(split * 2 - 1)}>{`${pieces.length} tokens`}</Txt>
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Boundary = ({e, rect, frame, end, vertical, seed = 0}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const pts = React.useMemo(() => {
    const r = rng(seed + 9);
    return Array.from({length: 46}, (_, k) => { const x = r(), y = r(); const s = y - (0.5 + 0.18 * Math.sin(x * 6)) + (r() - 0.5) * 0.18; return [x, y, s > 0 ? 1 : 0]; });
  }, [seed]);
  const X = (x) => B.x0 + 30 + x * (B.W - 60), Y = (y) => B.y1 - 20 - y * (B.H - 40);
  const curve = (x, mode) => (mode === "line" ? 0.5 + (x - 0.5) * 0.15 : mode === "curve" ? 0.5 + 0.18 * Math.sin(x * 6) : 0.5 + 0.18 * Math.sin(x * 6) + 0.12 * Math.sin(x * 41));
  const q = glide(T.k > 0 ? T.k : T.t - 40, 1.8);
  const line = Array.from({length: 120}, (_, j) => { const x = j / 119; return [X(x), Y(lerp(0.5, curve(x, e.mode), q))]; });
  return (
    <g>
      {pts.map(([x, y, c], k) => <circle key={k} cx={X(x)} cy={Y(y)} r={11 * pop(T.t - k * 0.6)} fill={c ? C.cool : C.hot} opacity={0.9}/>)}
      <path d={smoothPath(line)} fill="none" stroke={C.text} strokeWidth={6} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - glide(T.t - 20, 1.4)}/>
      {e.mode === "overfit" && q > 0.8 && <Txt x={B.x1 - 10} y={B.y0 + B.fs * 0.5} size={B.fs} anchor="end" color={C.hot}>memorised the noise</Txt>}
      {e.mode === "line" && q > 0.8 && <Txt x={B.x1 - 10} y={B.y0 + B.fs * 0.5} size={B.fs} anchor="end" color={C.hot}>too simple</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Kmeans = ({e, rect, frame, end, vertical, seed = 0}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), K = e.k;
  const {pts, steps} = React.useMemo(() => {
    const r = rng(seed + 13), centers = Array.from({length: K}, (_, k) => [0.2 + 0.6 * ((k * 0.618) % 1), 0.25 + 0.5 * ((k * 0.383 + 0.2) % 1)]);
    const p = Array.from({length: e.n}, (_, j) => { const c = centers[j % K]; return [clamp(c[0] + (r() - 0.5) * 0.3, 0.02, 0.98), clamp(c[1] + (r() - 0.5) * 0.3, 0.02, 0.98)]; });
    let cs = Array.from({length: K}, (_, k) => [r(), r()]); const out = [cs];
    for (let it = 0; it < 5; it++) {
      const sums = cs.map(() => [0, 0, 0]);
      p.forEach(([x, y]) => { let b = 0; cs.forEach((c, k) => { if ((c[0] - x) ** 2 + (c[1] - y) ** 2 < (cs[b][0] - x) ** 2 + (cs[b][1] - y) ** 2) b = k; }); sums[b][0] += x; sums[b][1] += y; sums[b][2] += 1; });
      cs = sums.map((s, k) => (s[2] ? [s[0] / s[2], s[1] / s[2]] : cs[k])); out.push(cs);
    }
    return {pts: p, steps: out};
  }, [K, e.n, seed]);
  const X = (x) => B.x0 + 20 + x * (B.W - 40), Y = (y) => B.y0 + 10 + y * (B.H - 20);
  const it = clamp((T.t - 30) / 26, 0, steps.length - 1), i0 = Math.floor(it), i1 = Math.min(steps.length - 1, i0 + 1), u = it - i0;
  const cs = steps[i0].map((c, k) => [lerp(c[0], steps[i1][k][0], u), lerp(c[1], steps[i1][k][1], u)]);
  const near = (x, y) => cs.reduce((b, c, k) => ((c[0] - x) ** 2 + (c[1] - y) ** 2 < (cs[b][0] - x) ** 2 + (cs[b][1] - y) ** 2 ? k : b), 0);
  return (
    <g>
      {pts.map(([x, y], j) => <circle key={j} cx={X(x)} cy={Y(y)} r={8 * pop(T.t - j * 0.2)} fill={T.t > 30 ? pal(e, near(x, y)) : C.muted} opacity={0.85}/>)}
      {T.t > 24 && cs.map((c, k) => (
        <g key={k} transform={`translate(${X(c[0])},${Y(c[1])})`}>
          <path d="M-20,0 L20,0 M0,-20 L0,20" stroke={C.text} strokeWidth={10}/>
          <path d="M-18,0 L18,0 M0,-18 L0,18" stroke={pal(e, k)} strokeWidth={6}/>
        </g>
      ))}
      <Txt x={B.x1 - 10} y={B.y0 + B.fs * 0.5} size={B.fs * 0.9} anchor="end" color={C.muted}>{T.t > 30 ? `step ${Math.min(steps.length - 1, i0 + 1)}` : "pick random centres"}</Txt>
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const LossCurve = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const X = (t) => B.x0 + 30 + t * (B.W - 60), Y = (v) => B.y1 - B.fs * 1.4 - v * (B.H - B.fs * 2.4);
  const train = (t) => 0.08 + 0.85 * Math.exp(-t * 4.5), val = (t) => (e.overfit ? 0.18 + 0.75 * Math.exp(-t * 5) + 0.5 * Math.max(0, t - 0.45) ** 1.6 : train(t) + 0.08);
  const p = glide(T.t - 10, 3.6), N = 80;
  const line = (f) => smoothPath(Array.from({length: N}, (_, j) => [X((j / (N - 1)) * p), Y(f((j / (N - 1)) * p))]));
  const best = 0.45;
  return (
    <g>
      <line x1={X(0)} y1={Y(0)} x2={X(1)} y2={Y(0)} stroke={C.muted} strokeWidth={3}/>
      <Txt x={X(1)} y={Y(0) + B.fs * 0.9} size={B.fs * 0.85} anchor="end" color={C.muted}>training time →</Txt>
      <path d={line(train)} fill="none" stroke={C.cool} strokeWidth={6}/>
      <path d={line(val)} fill="none" stroke={C.hot} strokeWidth={6}/>
      <Txt x={X(p) - 10} y={Y(train(p)) + B.fs * 0.8} size={B.fs * 0.9} anchor="end" color={C.cool}>training</Txt>
      <Txt x={X(p) - 10} y={Y(val(p)) - B.fs * 0.8} size={B.fs * 0.9} anchor="end" color={C.hot}>validation</Txt>
      {e.overfit && p > best + 0.15 && <g opacity={clamp((p - best - 0.15) * 6)}>
        <line x1={X(best)} y1={Y(0)} x2={X(best)} y2={Y(0.95)} stroke={C.violet} strokeWidth={3} strokeDasharray="8 8"/>
        <Txt x={X(best)} y={Y(0.95) - 10} size={B.fs * 0.85} color={C.violet}>stop here</Txt>
        <Txt x={X(0.85)} y={Y(val(0.85)) - B.fs * 1.4} size={B.fs * 0.85} color={C.hot}>overfitting</Txt>
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Softmax = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.items.length;
  const ex = e.items.map((it) => Math.exp(it.value)), tot = ex.reduce((s, x) => s + x, 0), prob = ex.map((x) => x / tot);
  const mx = Math.max(...e.items.map((it) => Math.abs(it.value)), 1e-9), q = glide(T.k > 0 ? T.k : T.t - 50, 1.6);
  const xs = spread(n, B.x0, B.x1), base = B.y1 - B.fs * 1.4, top = B.y0 + B.fs * 1.4, bw = Math.min(120, (B.W / n) * 0.5);
  return (
    <g>
      <Txt x={B.x0 + 4} y={B.y0 + B.fs * 0.4} size={B.fs} anchor="start" color={q > 0.5 ? C.hot : C.muted}>{q > 0.5 ? "probabilities (add up to 1)" : "raw scores"}</Txt>
      {e.items.map((it, k) => {
        const raw = (Math.abs(it.value) / mx) * 0.8, h = (base - top) * lerp(raw, prob[k], q) * glide(T.t - 8 - k * 5, 1.2);
        return (
          <g key={k}>
            <rect x={xs[k] - bw / 2} y={base - h} width={bw} height={h} rx={8} fill={q > 0.5 ? alpha(C.hot, 0.8) : alpha(pal(e, 0), 0.8)}/>
            <Txt x={xs[k]} y={base + B.fs * 0.8} size={B.fs}>{it.text}</Txt>
            <Txt x={xs[k]} y={base - h - B.fs * 0.6} size={B.fs * 0.85} op={clamp((T.t - 16) / 10)}>{q > 0.5 ? `${Math.round(prob[k] * 100)}%` : e.show ? fmt(it.value) : ""}</Txt>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
const SHAPES = {
  circle: (x, y) => (x - 0.5) ** 2 + (y - 0.5) ** 2 < 0.1,
  square: (x, y) => Math.abs(x - 0.5) < 0.28 && Math.abs(y - 0.5) < 0.28,
  heart: (x, y) => { const X = (x - 0.5) * 2.6, Y = (0.55 - y) * 2.6; return (X * X + Y * Y - 1) ** 3 - X * X * Y ** 3 < 0; },
  star: (x, y) => { const dx = x - 0.5, dy = y - 0.5, a = Math.atan2(dy, dx), r = Math.hypot(dx, dy); return r < 0.18 + 0.16 * Math.abs(Math.cos(2.5 * a)); },
};
export const Diffusion = ({e, rect, frame, end, vertical, seed = 0}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), S = e.steps, G = 14;
  const noise = React.useMemo(() => { const r = rng(seed + 17); return Array.from({length: G * G}, () => r()); }, [seed]);
  const inside = SHAPES[e.shape] || SHAPES.circle;
  const side = Math.min(B.H * 0.78, (B.W / S) * 0.8), xs = spread(S, B.x0, B.x1), cell = side / G, y0 = B.cy - side / 2;
  return (
    <g>
      {xs.map((x, s) => {
        const clean = s / (S - 1), p = pop(T.t - 10 - s * 16);
        return (
          <g key={s} opacity={clamp(p * 2)}>
            {Array.from({length: G * G}, (_, j) => {
              const i = Math.floor(j / G), k = j % G, target = inside((k + 0.5) / G, (i + 0.5) / G) ? 1 : 0;
              const v = lerp(noise[(j * 7 + s * 13) % (G * G)], target, clean);
              return <rect key={j} x={x - side / 2 + k * cell} y={y0 + i * cell} width={cell + 0.5} height={cell + 0.5} fill={v > 0.5 ? pal(e, 0) : C.panel} opacity={0.25 + 0.75 * Math.abs(v - 0.5) * 2}/>;
            })}
            <rect x={x - side / 2} y={y0} width={side} height={side} fill="none" stroke={C.muted} strokeWidth={2}/>
            {s < S - 1 && <Arrow a={[x + side / 2 + 6, B.cy]} b={[xs[s + 1] - side / 2 - 6, B.cy]} draw={glide(T.t - 18 - s * 16)} color={C.muted} width={3}/>}
            <Txt x={x} y={y0 + side + B.fs * 0.8} size={B.fs * 0.8} color={C.muted}>{s === 0 ? "noise" : s === S - 1 ? "image" : `step ${s}`}</Txt>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const NextToken = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.items.length;
  const items = [...e.items].sort((a, b) => b.value - a.value), mx = Math.max(...items.map((x) => x.value), 1e-9);
  const pick = glide(T.k > 0 ? T.k : T.t - 60, 1.2), fs = Math.min(B.fs * 1.2, (B.W * 0.75) / Math.max(10, e.prefix.length * 0.66));
  const px = B.x0 + 20, py = B.y0 + B.fs * 1.2, endX = px + tw(e.prefix, fs) * 0.88 + fs * 0.4;
  const bx = B.x0 + B.W * 0.35, bw = B.W * 0.42, ys = row(n, B.y0 + B.H * 0.38, B.y1 - 20);
  return (
    <g>
      <Txt x={px} y={py} size={fs} anchor="start" op={clamp(T.t / 10)}>{e.prefix}</Txt>
      {pick > 0.5 && <Txt x={endX} y={py} size={fs} anchor="start" color={C.hot} op={clamp((pick - 0.5) * 3)}>{items[0].text}</Txt>}
      <rect x={endX - 4} y={py - fs * 0.6} width={4} height={fs * 1.2} fill={C.text} opacity={pick < 0.5 && Math.floor(T.t / 15) % 2 ? 1 : 0}/>
      {items.map((it, k) => {
        const p = glide(T.t - 20 - k * 6, 1.2), w = bw * (it.value / mx) * p, win = k === 0 && pick > 0.2;
        return (
          <g key={k}>
            <Txt x={bx - 20} y={ys[k]} size={B.fs} anchor="end" color={win ? C.hot : C.text}>{it.text}</Txt>
            <rect x={bx} y={ys[k] - B.fs * 0.5} width={w} height={B.fs} rx={8} fill={win ? C.hot : alpha(pal(e, 0), 0.7)} style={{filter: win ? glowF(C.hot, 0.6) : undefined}}/>
            {e.show && p > 0.9 && <Txt x={bx + w + 16} y={ys[k]} size={B.fs * 0.85} anchor="start" color={C.muted}>{fmt(it.value)}</Txt>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Context = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.tokens, W = e.window;
  const cw = (B.W - 20) / Math.min(n, 60), shownN = Math.min(n, 60), y = B.cy;
  const slide = clamp((T.t - 20) / Math.max(30, end - T.at - 40)) * Math.max(0, shownN - W);
  const x0 = B.x0 + 10 + slide * cw;
  return (
    <g>
      {Array.from({length: shownN}, (_, k) => {
        const inW = k >= slide && k < slide + W, gone = k < slide;
        return <rect key={k} x={B.x0 + 10 + k * cw + 1} y={y - 22} width={cw - 2} height={44} rx={4} fill={inW ? pal(e, (Math.floor(k / 3)) % 3) : gone ? alpha(C.muted, 0.15) : alpha(C.muted, 0.4)}
                     opacity={clamp((T.t - k * 0.4) / 8)}/>;
      })}
      <rect x={x0 - 4} y={y - 40} width={W * cw + 8} height={80} rx={12} fill="none" stroke={C.hot} strokeWidth={5} style={{filter: glowF(C.hot, 0.5)}} opacity={clamp((T.t - 12) / 10)}/>
      <Txt x={x0 + (W * cw) / 2} y={y - 64} size={B.fs} color={C.hot}>context window</Txt>
      {slide > 1 && <Txt x={B.x0 + 10} y={y + 68} size={B.fs * 0.85} anchor="start" color={C.muted}>forgotten</Txt>}
      <Txt x={B.x1 - 10} y={y + 68} size={B.fs * 0.85} anchor="end" color={C.muted}>new tokens →</Txt>
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Rag = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.docs.length;
  const q = [B.x0 + B.W * 0.13, B.y0 + 60], db = [B.x0 + B.W * 0.13, B.y1 - 70], llm = [B.x0 + B.W * 0.6, B.cy], ans = [B.x1 - B.W * 0.13, B.cy];
  const ret = glide(T.t - 30, 1.2), aug = glide(T.t - 60, 1.2), gen = glide(T.k > 0 ? T.k : T.t - 100, 1.2);
  const dy = row(n, B.y0 + 80, B.y1 - 80), dx = B.x0 + B.W * 0.36;
  return (
    <g>
      <Card x={q[0] - 130} y={q[1] - 45} w={260} h={90} icon="message-circle" label="" color={C.text} p={pop(T.t)}/>
      <Txt x={q[0] + 20} y={q[1]} size={Math.min(B.fs * 0.8, 230 / Math.max(8, e.query.length * 0.62))} anchor="middle">{e.query}</Txt>
      <Card x={db[0] - 110} y={db[1] - 60} w={220} h={120} icon="database" label="vector store" color={C.violet} p={pop(T.t - 6)} fs={B.fs * 0.8}/>
      <Arrow a={[q[0], q[1] + 45]} b={[db[0], db[1] - 62]} draw={ret} color={C.violet} label="search" fs={B.fs * 0.75}/>
      {e.docs.map((d, k) => (
        <g key={k} opacity={clamp(aug * 2 - k * 0.2)}>
          <Chip x={lerp(db[0], dx, aug)} y={lerp(db[1], dy[k], aug)} text={d} color={pal(e, k)} p={1} fs={B.fs * 0.8} fill/>
          <Packet pts={[[dx + 60, dy[k]], [llm[0] - 110, llm[1]]]} t={(T.t - 80 - k * 4) / 20} color={pal(e, k)}/>
        </g>
      ))}
      <Card x={llm[0] - 110} y={llm[1] - 80} w={220} h={160} icon="brain-circuit" label="LLM" color={pal(e, 0)} p={pop(T.t - 50)} fs={B.fs} lit={gen > 0 && gen < 1 ? 0.6 : 0}/>
      <Arrow a={[llm[0] + 110, llm[1]]} b={[ans[0] - 120, ans[1]]} draw={gen} color={C.hot}/>
      {gen > 0.6 && <g opacity={clamp((gen - 0.6) * 3)}>
        <rect x={ans[0] - 120} y={ans[1] - 60} width={240} height={120} rx={14} fill={alpha(C.hot, 0.15)} stroke={C.hot} strokeWidth={3}/>
        <Txt x={ans[0]} y={ans[1]} size={Math.min(B.fs * 0.85, 210 / Math.max(8, e.answer.length * 0.62))}>{e.answer}</Txt>
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Dropout = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), L = e.layers;
  const xs = spread(L.length, B.x0, B.x1), ys = L.map((m) => row(m, B.cy - Math.min(B.H * 0.42, m * 45), B.cy + Math.min(B.H * 0.42, m * 45)));
  const epoch = T.k > 0 ? Math.floor(T.k / 18) : -1, off = (l, k) => epoch >= 0 && l > 0 && l < L.length - 1 && ((k * 7 + l * 3 + epoch * 5) % 5 < 2);
  return (
    <g>
      {ys.slice(0, -1).map((col, l) => col.flatMap((y, k) => ys[l + 1].map((y2, j) => (
        <line key={`${l}-${k}-${j}`} x1={xs[l]} y1={y} x2={xs[l + 1]} y2={y2} stroke={alpha(C.muted, off(l, k) || off(l + 1, j) ? 0.06 : 0.35)} strokeWidth={2}/>))))}
      {ys.map((col, l) => col.map((y, k) => (
        <g key={`n${l}-${k}`}>
          <circle cx={xs[l]} cy={y} r={20 * pop(T.t - l * 6 - k)} fill={off(l, k) ? alpha(C.muted, 0.2) : pal(e, l)} stroke={off(l, k) ? C.hot : "none"} strokeWidth={3}/>
          {off(l, k) && <Txt x={xs[l]} y={y} size={22} color={C.hot}>✕</Txt>}
        </g>
      )))}
      {epoch >= 0 && <Txt x={B.cx} y={B.y1 - B.fs * 0.2} size={B.fs * 0.9} color={C.hot}>{"random neurons switched off, a new set each pass"}</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Contour = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const side = Math.min(B.H, B.W * 0.62), cx = B.cx, cy = B.cy, f = (x, y) => x * x * 0.35 + y * y * 2.2;
  const rate = {small: 0.06, good: 0.32, large: 0.88}[e.lr];
  const path = React.useMemo(() => { const p = [[-2.6, 1.3]]; for (let k = 0; k < 18; k++) { const [x, y] = p[p.length - 1]; p.push([x - rate * 0.7 * x, y - rate * 4.4 * y * 0.5]); } return p; }, [rate]);
  const P = ([x, y]) => [cx + (x / 3.2) * (side / 2), cy - (y / 1.6) * (side / 2) * 0.9];
  const shown = clamp((T.t - 24) / 4.5, 0, path.length - 1);
  return (
    <g>
      {[0.3, 0.8, 1.6, 2.8, 4.2].map((lv, k) => <ellipse key={k} cx={cx} cy={cy} rx={(Math.sqrt(lv / 0.35) / 3.2) * (side / 2)} ry={(Math.sqrt(lv / 2.2) / 1.6) * (side / 2) * 0.9}
                                                      fill={alpha(pal(e, 0), 0.05 + k * 0.025)} stroke={alpha(pal(e, 0), 0.6)} strokeWidth={3} opacity={clamp((T.t - k * 3) / 10)}/>)}
      <circle cx={cx} cy={cy} r={8} fill={C.text}/>
      {path.slice(0, Math.floor(shown) + 1).map((pt, k, arr) => k > 0 && (
        <line key={k} x1={P(arr[k - 1])[0]} y1={P(arr[k - 1])[1]} x2={P(pt)[0]} y2={P(pt)[1]} stroke={C.hot} strokeWidth={4}/>))}
      {path.slice(0, Math.floor(shown) + 1).map((pt, k) => <circle key={`d${k}`} cx={P(pt)[0]} cy={P(pt)[1]} r={9} fill={C.hot}/>)}
      <Txt x={B.x1 - 10} y={B.y0 + B.fs * 0.5} size={B.fs} anchor="end" color={C.hot}>{e.lr === "small" ? "tiny steps: slow" : e.lr === "large" ? "too big: zigzag" : "just right"}</Txt>
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Pca = ({e, rect, frame, end, vertical, seed = 0}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), ang = -0.5;
  const pts = React.useMemo(() => { const r = rng(seed + 19); return Array.from({length: e.n}, () => { const a = (r() + r() + r() - 1.5) * 1.6, b = (r() + r() - 1) * 0.35; return [a * Math.cos(ang) - b * Math.sin(ang), a * Math.sin(ang) + b * Math.cos(ang), a]; }); }, [e.n, seed]);
  const S = Math.min(B.W, B.H * 1.6) * 0.3, P = (x, y) => [B.cx + x * S, B.cy + y * S * 0.8];
  const axis = glide(T.t - 30, 1.4), proj = glide(T.k > 0 ? T.k : T.t - 70, 1.4);
  const sw = lerp(0.9, 0, glide(T.t - 30, 1.4));
  return (
    <g>
      {axis > 0 && <line x1={P(-2.6 * Math.cos(ang + sw), -2.6 * Math.sin(ang + sw))[0]} y1={P(-2.6 * Math.cos(ang + sw), -2.6 * Math.sin(ang + sw))[1]}
                         x2={P(2.6 * Math.cos(ang + sw), 2.6 * Math.sin(ang + sw))[0]} y2={P(2.6 * Math.cos(ang + sw), 2.6 * Math.sin(ang + sw))[1]} stroke={C.hot} strokeWidth={6}/>}
      {pts.map(([x, y, a], k) => {
        const [px, py] = P(x, y), [qx, qy] = P(a * Math.cos(ang), a * Math.sin(ang));
        return (
          <g key={k}>
            {proj > 0 && proj < 1 && <line x1={px} y1={py} x2={qx} y2={qy} stroke={alpha(C.muted, 0.4)} strokeWidth={2}/>}
            <circle cx={lerp(px, qx, proj)} cy={lerp(py, qy, proj)} r={9 * pop(T.t - k * 0.5)} fill={pal(e, 0)} opacity={0.85}/>
          </g>
        );
      })}
      {axis > 0.9 && <Txt x={P(2.6 * Math.cos(ang), 2.6 * Math.sin(ang))[0]} y={P(2.6 * Math.cos(ang), 2.6 * Math.sin(ang))[1] - B.fs} size={B.fs * 0.9} color={C.hot}>main direction</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Vectors = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const groups = React.useMemo(() => e.words.map((w, k) => { const g = Math.floor((k * 3) / e.words.length); const a = g * 2.1 + (k % 3) * 0.5; return [0.5 + 0.3 * Math.cos(a) + 0.05 * Math.sin(k), 0.5 + 0.32 * Math.sin(a) + 0.05 * Math.cos(k * 2), g]; }), [e.words]);
  const X = (x) => B.x0 + 30 + x * (B.W - 60), Y = (y) => B.y0 + 20 + y * (B.H - 40);
  const qpos = [lerp(groups[0][0], groups[1] ? groups[1][0] : groups[0][0], 0.5) + 0.04, groups[0][1] + 0.08];
  const q = glide(T.k > 0 ? T.k : T.t - 50, 1.3), dist = (g) => Math.hypot(g[0] - qpos[0], g[1] - qpos[1]);
  const nearest = [...groups.keys()].sort((a, b) => dist(groups[a]) - dist(groups[b])).slice(0, 3);
  return (
    <g>
      {groups.map(([x, y, g], k) => (
        <g key={k} opacity={clamp(pop(T.t - k * 3) * 2) * (q > 0.5 && !nearest.includes(k) ? 0.5 : 1)}>
          <circle cx={X(x)} cy={Y(y)} r={12} fill={pal(e, g)}/>
          <Txt x={X(x)} y={Y(y) - 28} size={B.fs * 0.85}>{e.words[k]}</Txt>
        </g>
      ))}
      {q > 0 && <g>
        {nearest.map((k) => <line key={k} x1={X(qpos[0])} y1={Y(qpos[1])} x2={X(groups[k][0])} y2={Y(groups[k][1])} stroke={C.hot} strokeWidth={4} opacity={q} strokeDasharray="8 6"/>)}
        <circle cx={X(qpos[0])} cy={Y(qpos[1])} r={16 * q} fill={C.hot} style={{filter: glowF(C.hot, 0.8)}}/>
        <Txt x={X(qpos[0])} y={Y(qpos[1]) + 38} size={B.fs} color={C.hot}>{e.query}</Txt>
      </g>}
    </g>
  );
};

export const ML = {neuron: Neuron, attention: Attention, tokenize: Tokenize, boundary: Boundary, kmeans: Kmeans,
  losscurve: LossCurve, softmax: Softmax, diffusion: Diffusion, nexttoken: NextToken, context: Context, rag: Rag,
  dropout: Dropout, contour: Contour, pca: Pca, vectors: Vectors};
