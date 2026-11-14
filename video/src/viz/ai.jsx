// Deep learning, LLM / GenAI and GenAI-architecture techniques (blogwriter/vizlib.py, families "dl", "llm", "genai"):
// how networks learn and generate, how language models are trained, served, steered and wired into products.
import {Arrow, C, Card, Chip, Ico, Packet, React, Txt, alpha, box, clamp, fitFs, fmt, gauss, glide, glowF, lerp, pal, pop, rng, row,
        smoothPath, spread, timing, tw} from "./kit";

const cyc = (t, start, period) => { const x = (t - start) / period; return {n: Math.floor(x), ph: x - Math.floor(x), on: t >= start}; };
const later = (T, wait) => (T.k > 0 ? T.k : T.t - wait);          // the key moment, or a fixed time when no word names it

// ================================================================================================= deep learning
export const Backprop = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), L = e.layers.map((v) => Math.round(Math.min(6, Math.max(1, v))));
  const xs = spread(L.length + 1, B.x0, B.x1).slice(0, L.length), lossX = B.x1 - B.W * 0.08;
  const ys = L.map((m) => row(m, B.cy - Math.min(B.H * 0.4, m * 48), B.cy + Math.min(B.H * 0.4, m * 48)));
  const fwd = glide(T.t - 16, 2.2) * (L.length - 1), back = later(T, 80) > 0 ? glide(later(T, 80), 2.2) * (L.length - 1) : -1;
  const layerLit = (l) => (back >= 0 ? (L.length - 1 - l <= back ? 2 : 1) : l <= fwd ? 1 : 0);
  return (
    <g>
      {ys.slice(0, -1).map((col, l) => col.flatMap((y, k) => ys[l + 1].map((y2, j) => {
        const lit = layerLit(l + 1);
        return <line key={`${l}-${k}-${j}`} x1={xs[l]} y1={y} x2={xs[l + 1]} y2={y2} stroke={lit === 2 ? C.hot : lit ? alpha(pal(e, 0), 0.7) : alpha(C.muted, 0.25)} strokeWidth={lit === 2 ? 3 + ((k + j) % 3) * 1.5 : 2}/>;
      })))}
      {ys.map((col, l) => col.map((y, k) => <circle key={`n${l}${k}`} cx={xs[l]} cy={y} r={20 * pop(T.t - l * 5)} fill={layerLit(l) === 2 ? C.hot : layerLit(l) ? pal(e, 0) : alpha(C.panel, 0.95)}
                                              stroke={pal(e, 0)} strokeWidth={3}/>))}
      <Card x={lossX - 80} y={B.cy - 50} w={160} h={100} label={e.text || "loss"} color={C.hot} p={pop(T.t - 50)} fs={B.fs} lit={fwd >= L.length - 1.01 ? 0.6 : 0}/>
      <Arrow a={[xs[L.length - 1] + 26, B.cy]} b={[lossX - 84, B.cy]} draw={clamp(fwd - (L.length - 2))} color={pal(e, 0)}/>
      <Txt x={B.cx} y={B.y0 + B.fs * 0.4} size={B.fs} color={back >= 0 ? C.hot : pal(e, 0)}>{back >= 0 ? "← gradients flow back, weights adjust" : "forward pass →"}</Txt>
    </g>
  );
};

export const Cnn = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.stages.length;
  const xs = spread(n + 2, B.x0, B.x1), base = Math.min(B.H * 0.8, (B.W / (n + 2)) * 1.1);
  return (
    <g>
      <g opacity={clamp(T.t / 10)}>
        {Array.from({length: 36}, (_, j) => <rect key={j} x={xs[0] - base / 2 + (j % 6) * (base / 6)} y={B.cy - base / 2 + Math.floor(j / 6) * (base / 6)} width={base / 6 - 2} height={base / 6 - 2}
                                                fill={alpha(C.text, 0.15 + 0.6 * (((j * 7) % 11) / 11))}/>)}
        <Txt x={xs[0]} y={B.cy + base / 2 + B.fs * 0.8} size={B.fs * 0.85} color={C.muted}>image</Txt>
      </g>
      {e.stages.map((s, k) => {
        const size = base * (0.85 - (0.55 * k) / Math.max(1, n)), depth = 3 + k * 2, p = glide(T.t - 12 - k * 14, 1);
        return (
          <g key={k} opacity={clamp(p * 2)}>
            {Array.from({length: depth}, (_, d) => <rect key={d} x={xs[k + 1] - size / 2 + d * 7 - depth * 3} y={B.cy - size / 2 - d * 7 + depth * 3} width={size} height={size} rx={6}
                                                       fill={alpha(pal(e, k), 0.18)} stroke={pal(e, k)} strokeWidth={2}/>)}
            <Txt x={xs[k + 1]} y={B.cy + base / 2 + B.fs * 0.8} size={fitFs(s, B.fs * 0.85, (B.W / (n + 2)) * 0.95)} color={pal(e, k)}>{s}</Txt>
            <Packet pts={[[xs[k] + base * 0.3, B.cy], [xs[k + 1] - size / 2 - 20, B.cy]]} t={(T.t - 12 - k * 14) / 16} color={pal(e, k)}/>
          </g>
        );
      })}
      <Chip x={xs[n + 1]} y={B.cy} text={e.output || "label"} color={C.hot} p={pop(T.t - 14 - n * 14)} fs={B.fs * 1.1} fill lit={later(T, 90) > 0 ? 0.6 : 0}/>
    </g>
  );
};

export const Rnn = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.tokens.length, xs = spread(n, B.x0, B.x1), cw = Math.min(150, (B.W / n) * 0.6);
  const step = Math.max(0, (T.t - 16) / 22);
  return (
    <g>
      {e.tokens.map((t, k) => {
        const on = step > k, p = pop(T.t - 16 - k * 22);
        return (
          <g key={k}>
            <Chip x={xs[k]} y={B.y1 - B.fs} text={t} color={pal(e, 1)} p={pop(T.t - k * 3)} fs={B.fs} fill/>
            <Arrow a={[xs[k], B.y1 - B.fs * 2]} b={[xs[k], B.cy + cw / 2 + 4]} draw={glide(T.t - 12 - k * 22)} color={C.muted} width={3}/>
            <rect x={xs[k] - cw / 2} y={B.cy - cw / 2} width={cw} height={cw} rx={16} fill={on ? alpha(pal(e, 0), 0.25 + 0.1 * k) : alpha(C.panel, 0.95)} stroke={pal(e, 0)} strokeWidth={on ? 5 : 3}/>
            <Txt x={xs[k]} y={B.cy} size={B.fs * 0.85} color={on ? C.text : C.muted}>state</Txt>
            {k < n - 1 && <Arrow a={[xs[k] + cw / 2, B.cy]} b={[xs[k + 1] - cw / 2 - 4, B.cy]} draw={clamp(step - k - 0.4)} color={C.hot} width={5} label={k === 0 ? "memory" : ""} fs={B.fs * 0.8}/>}
            {k < n - 1 && <Packet pts={[[xs[k] + cw / 2, B.cy], [xs[k + 1] - cw / 2, B.cy]]} t={step - k - 0.4} color={C.hot}/>}
          </g>
        );
      })}
    </g>
  );
};

export const Transformer = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), N = e.blocks;
  const bw = Math.min(B.W * 0.4, 520), x = B.cx - bw / 2, top = B.y0 + 10, h = (B.H - 30) / N;
  const flow = cyc(T.t, 24, 90);
  return (
    <g>
      {Array.from({length: N}, (_, b) => {
        const y = B.y1 - (b + 1) * h, p = glide(T.t - b * 14, 1.1);
        const parts = [["attention", pal(e, 0), 0.62], ["feed-forward", C.cool, 0.2]];
        return (
          <g key={b} opacity={clamp(p * 2)}>
            <rect x={x - 20} y={y + 6} width={bw + 40} height={h - 12} rx={18} fill="none" stroke={alpha(C.muted, 0.6)} strokeWidth={3} strokeDasharray="10 8"/>
            {parts.map(([nm, col, fy], k) => (
              <g key={k}>
                <rect x={x} y={y + h * fy - h * 0.13} width={bw} height={h * 0.26} rx={12} fill={alpha(col, 0.3)} stroke={col} strokeWidth={3}/>
                <Txt x={B.cx} y={y + h * fy} size={Math.min(B.fs, h * 0.16)}>{nm}</Txt>
                <path d={`M${x + bw + 10},${y + h * fy + h * 0.2} C${x + bw + 70},${y + h * fy + h * 0.2} ${x + bw + 70},${y + h * fy - h * 0.2} ${x + bw + 10},${y + h * fy - h * 0.2}`}
                      fill="none" stroke={C.hot} strokeWidth={3} strokeDasharray="6 6"/>
              </g>
            ))}
            {b === 0 && <Txt x={x + bw + 80} y={y + h * 0.62} size={B.fs * 0.75} anchor="start" color={C.hot}>+ residual</Txt>}
          </g>
        );
      })}
      {flow.on && <circle cx={B.cx} cy={lerp(B.y1, top, flow.ph)} r={12} fill={C.hot} style={{filter: glowF(C.hot, 0.8)}}/>}
      <Txt x={x - 30} y={B.cy} size={B.fs} anchor="end" color={C.muted}>{N > 1 ? `× ${N}` : ""}</Txt>
      {e.text && <Txt x={x - 30} y={B.y0 + B.fs} size={B.fs * 0.9} anchor="end" color={pal(e, 0)}>{e.text}</Txt>}
    </g>
  );
};

export const Gan = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), round = Math.floor(Math.max(0, T.t - 20) / 40), q = clamp(round / 4);
  const gen = [B.x0 + B.W * 0.25, B.cy - B.H * 0.15], dis = [B.x1 - B.W * 0.22, B.cy], noise = [B.x0 + B.W * 0.06, B.cy - B.H * 0.15], real = [B.x0 + B.W * 0.45, B.y1 - 60];
  const fooled = q >= 1 && later(T, 140) > 0, c = cyc(T.t, 20, 40);
  return (
    <g>
      <g opacity={clamp(T.t / 10)}>{Array.from({length: 16}, (_, j) => <rect key={j} x={noise[0] - 40 + (j % 4) * 20} y={noise[1] - 40 + Math.floor(j / 4) * 20} width={18} height={18} fill={alpha(C.text, ((j * 37) % 10) / 10)}/>)}</g>
      <Card x={gen[0] - 100} y={gen[1] - 60} w={200} h={120} icon="sparkles" label="generator" color={pal(e, 0)} p={pop(T.t)} fs={B.fs * 0.85}/>
      <Card x={dis[0] - 100} y={dis[1] - 60} w={200} h={120} icon="scan-line" label="discriminator" color={C.violet} p={pop(T.t - 6)} fs={B.fs * 0.8}/>
      <Card x={real[0] - 80} y={real[1] - 45} w={160} h={90} icon="image" label={`real ${e.text || "data"}`} color={C.cool} p={pop(T.t - 10)} fs={B.fs * 0.75}/>
      <Packet pts={[[noise[0] + 45, noise[1]], [gen[0] - 100, gen[1]]]} t={c.ph * 3} color={C.muted}/>
      <Packet pts={[[gen[0] + 100, gen[1]], [dis[0] - 100, dis[1] - 20]]} t={c.ph * 2 - 0.6} color={pal(e, 0)}/>
      <Packet pts={[[real[0] + 80, real[1]], [dis[0] - 100, dis[1] + 20]]} t={c.ph * 2 - 0.6} color={C.cool}/>
      <Txt x={dis[0]} y={dis[1] + 100} size={B.fs} color={fooled ? C.hot : C.violet}>{fooled ? "can't tell: fooled" : c.ph > 0.85 ? "fake!" : "real or fake?"}</Txt>
      <Txt x={gen[0]} y={gen[1] - 90} size={B.fs * 0.85} color={C.muted}>{`fakes get better`}</Txt>
      <rect x={gen[0] - 100} y={gen[1] + 70} width={200} height={12} rx={6} fill={alpha(C.muted, 0.25)}/>
      <rect x={gen[0] - 100} y={gen[1] + 70} width={200 * q} height={12} rx={6} fill={pal(e, 0)}/>
    </g>
  );
};

export const Autoencoder = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), widths = [1, 0.7, 0.38, 0.7, 1], xs = spread(5, B.x0, B.x1), H = B.H * 0.85;
  const p = glide(T.t - 10, 3), lit = p * 5;
  return (
    <g>
      {widths.map((w, k) => {
        const on = lit > k, mid = k === 2;
        return (
          <g key={k}>
            {k < 4 && <path d={`M${xs[k] + 22},${B.cy - (H * w) / 2} L${xs[k + 1] - 22},${B.cy - (H * widths[k + 1]) / 2} L${xs[k + 1] - 22},${B.cy + (H * widths[k + 1]) / 2} L${xs[k] + 22},${B.cy + (H * w) / 2} Z`}
                            fill={alpha(k < 2 ? pal(e, 0) : C.cool, on ? 0.18 : 0.05)}/>}
            <rect x={xs[k] - 22} y={B.cy - (H * w) / 2} width={44} height={H * w} rx={12} fill={on ? (mid ? C.hot : alpha(k < 2 ? pal(e, 0) : C.cool, 0.7)) : alpha(C.panel, 0.95)}
                  stroke={mid ? C.hot : C.muted} strokeWidth={3} style={{filter: mid && on ? glowF(C.hot, 0.6) : undefined}}/>
          </g>
        );
      })}
      <Txt x={xs[0]} y={B.y0 + B.fs * 0.2} size={B.fs * 0.85} color={C.muted}>input</Txt>
      <Txt x={xs[4]} y={B.y0 + B.fs * 0.2} size={B.fs * 0.85} color={C.muted}>rebuilt</Txt>
      <Txt x={(xs[0] + xs[2]) / 2} y={B.y1 - B.fs * 0.2} size={B.fs * 0.85} color={pal(e, 0)}>encoder</Txt>
      <Txt x={(xs[2] + xs[4]) / 2} y={B.y1 - B.fs * 0.2} size={B.fs * 0.85} color={C.cool}>decoder</Txt>
      <Txt x={xs[2]} y={B.cy - (H * 0.38) / 2 - B.fs * 0.8} size={B.fs * 0.9} color={C.hot} op={clamp(lit - 2)}>{e.text || "bottleneck"}</Txt>
    </g>
  );
};

// ================================================================================================= LLMs and GenAI
export const KvCache = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.tokens.length, per = Math.max(18, (end - T.at - 40) / (n + 0.5));
  const step = Math.min(n, Math.floor(Math.max(0, T.t - 14) / per) + 1), cw = Math.min(110, (B.W * 0.62) / n), x0 = B.x0 + B.W * 0.3, rowK = B.cy - cw * 0.7, rowV = B.cy + cw * 0.7;
  return (
    <g>
      <Txt x={x0 - 30} y={rowK} size={B.fs} anchor="end" color={pal(e, 0)}>keys</Txt>
      <Txt x={x0 - 30} y={rowV} size={B.fs} anchor="end" color={C.cool}>values</Txt>
      {e.tokens.slice(0, step).map((t, k) => {
        const isNew = k === step - 1, p = pop(T.t - 14 - k * per);
        return (
          <g key={k} opacity={clamp(p * 2)}>
            <Txt x={x0 + (k + 0.5) * cw} y={B.y0 + B.fs * 0.6} size={fitFs(t, B.fs * 0.85, cw * 0.95)}>{t}</Txt>
            {[rowK, rowV].map((y, r) => <rect key={r} x={x0 + k * cw + 4} y={y - cw * 0.4} width={cw - 8} height={cw * 0.8} rx={8} fill={isNew ? alpha(C.hot, 0.6) : alpha(r ? C.cool : pal(e, 0), 0.4)}
                                               stroke={isNew ? C.hot : r ? C.cool : pal(e, 0)} strokeWidth={isNew ? 4 : 2}/>)}
          </g>
        );
      })}
      <Txt x={B.cx} y={B.y1 - B.fs * 0.4} size={B.fs * 0.9} color={C.hot}>only the new token is computed; the rest is reused from the cache</Txt>
    </g>
  );
};

export const Moe = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), nE = e.experts, n = e.tokens.length;
  const ex = B.x1 - B.W * 0.18, ey = row(nE, B.y0 + 30, B.y1 - 30), eh = Math.min(70, (B.H - 20) / nE - 10), router = [B.cx - B.W * 0.05, B.cy];
  const per = Math.max(30, (end - T.at - 30) / (n + 0.4)), k = Math.min(n - 1, Math.floor(Math.max(0, T.t - 20) / per)), ph = clamp(((T.t - 20) % per) / per);
  const picks = (j) => Array.from({length: e.top}, (_, m) => (j * 3 + m * 2 + 1) % nE);
  return (
    <g>
      {e.tokens.map((t, j) => <Chip key={j} x={B.x0 + B.W * 0.1} y={row(n, B.y0 + 60, B.y1 - 60)[j]} text={t} color={pal(e, j)} p={pop(T.t - j * 4)} fs={B.fs} fill lit={j === k ? 0.6 : 0}/>)}
      <Card x={router[0] - 90} y={router[1] - 60} w={180} h={120} icon="split" label="router" color={C.hot} p={pop(T.t - 8)} fs={B.fs * 0.9}/>
      {ey.map((y, m) => {
        const on = picks(k).includes(m) && ph > 0.4;
        return <Card key={m} x={ex - 110} y={y - eh / 2} w={220} h={eh} label={`expert ${m + 1}`} color={on ? pal(e, k) : C.muted} p={pop(T.t - 10 - m * 3)} fs={Math.min(B.fs * 0.85, eh * 0.4)} lit={on ? 0.6 : 0} dim={!on}/>;
      })}
      <Packet pts={[[B.x0 + B.W * 0.1 + 60, row(n, B.y0 + 60, B.y1 - 60)[k]], [router[0] - 90, router[1]]]} t={ph * 2.5} color={pal(e, k)}/>
      {picks(k).map((m) => <Packet key={m} pts={[[router[0] + 90, router[1]], [ex - 110, ey[m]]]} t={(ph - 0.4) * 2.5} color={pal(e, k)}/>)}
      <Txt x={router[0]} y={router[1] + 100} size={B.fs * 0.85} color={C.muted}>{`top ${e.top} of ${nE} experts`}</Txt>
    </g>
  );
};

export const Lora = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), S = Math.min(B.H * 0.85, B.W * 0.32), x0 = B.x0 + B.W * 0.08, y0 = B.cy - S / 2;
  const q = glide(T.t - 30, 1.4), merge = glide(later(T, 100), 1.4), thin = S * 0.14;
  const ax = x0 + S + 80, bx = ax + thin + 40;
  return (
    <g>
      <rect x={x0} y={y0} width={S} height={S} rx={10} fill={alpha(C.muted, 0.25)} stroke={C.muted} strokeWidth={3} opacity={clamp(T.t / 10)}/>
      {Array.from({length: 64}, (_, j) => <rect key={j} x={x0 + 8 + (j % 8) * ((S - 16) / 8)} y={y0 + 8 + Math.floor(j / 8) * ((S - 16) / 8)} width={(S - 16) / 8 - 4} height={(S - 16) / 8 - 4}
                                              rx={3} fill={alpha(C.text, 0.12 + ((j * 13) % 7) / 20)}/>)}
      <Ico name="lock" x={x0 + S - 26} y={y0 + 26} size={34} color={C.text}/>
      <Txt x={x0 + S / 2} y={y0 + S + B.fs * 0.8} size={B.fs * 0.85} color={C.muted}>frozen weights</Txt>
      <g opacity={clamp(q * 2)}>
        <Txt x={ax - 40} y={B.cy} size={B.fs * 1.4}>+</Txt>
        <rect x={ax} y={y0} width={thin} height={S} rx={8} fill={alpha(C.hot, 0.6)} stroke={C.hot} strokeWidth={3}/>
        <Txt x={bx - 22} y={B.cy} size={B.fs}>×</Txt>
        <rect x={bx} y={B.cy - thin / 2} width={S} height={thin} rx={8} fill={alpha(C.hot, 0.6)} stroke={C.hot} strokeWidth={3}/>
        <Txt x={(ax + bx + S) / 2} y={y0 + S + B.fs * 0.8} size={B.fs * 0.85} color={C.hot}>small trainable pieces</Txt>
      </g>
      {merge > 0 && <Txt x={B.cx} y={B.y0 + B.fs * 0.4} size={B.fs} color={pal(e, 0)} op={merge}>{`${e.text || "fine-tuning"}: train a tiny fraction of the weights`}</Txt>}
    </g>
  );
};

export const Quantize = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), levels = e.bits === "8" ? 16 : 6, q = glide(later(T, 60), 1.6);
  const vals = React.useMemo(() => Array.from({length: 24}, (_, k) => Math.sin(k * 1.7) * 0.8 + Math.cos(k * 0.6) * 0.2), []);
  const snap = (v) => Math.round(((v + 1) / 2) * (levels - 1)) / (levels - 1) * 2 - 1;
  const x0 = B.x0 + 20, w = B.W * 0.6, Y = (v) => B.cy - v * (B.H * 0.38);
  return (
    <g>
      {Array.from({length: levels}, (_, l) => { const v = (l / (levels - 1)) * 2 - 1; return <line key={l} x1={x0} y1={Y(v)} x2={x0 + w} y2={Y(v)} stroke={alpha(C.hot, 0.35 * q)} strokeWidth={2}/>; })}
      {vals.map((v, k) => {
        const x = x0 + (k + 0.5) * (w / vals.length), y = Y(lerp(v, snap(v), q));
        return <g key={k}><line x1={x} y1={B.cy} x2={x} y2={y} stroke={alpha(pal(e, 0), 0.5)} strokeWidth={3}/><circle cx={x} cy={y} r={9} fill={q > 0.5 ? C.hot : pal(e, 0)}/></g>;
      })}
      {[["32-bit", 1, pal(e, 0)], [`${e.bits}-bit`, Number(e.bits) / 32, C.hot]].map(([t, s, col], k) => (
        <g key={k} opacity={k ? q : 1}>
          <rect x={B.x0 + B.W * 0.7} y={B.y0 + 30 + k * 120} width={B.W * 0.26 * s} height={70} rx={10} fill={alpha(col, 0.5)} stroke={col} strokeWidth={3}/>
          <Txt x={B.x0 + B.W * 0.7} y={B.y0 + 14 + k * 120} size={B.fs * 0.85} anchor="start" color={col}>{`${t} model`}</Txt>
        </g>
      ))}
    </g>
  );
};

export const Rlhf = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), xs = spread(3, B.x0, B.x1), y = B.cy;
  const s1 = glide(T.t - 10, 1), s2 = glide(T.t - 60, 1), s3 = glide(later(T, 110), 1.2);
  return (
    <g>
      <g opacity={clamp(s1 * 2)}>
        <Txt x={xs[0]} y={B.y0 + B.fs * 0.4} size={B.fs} color={pal(e, 0)}>1. people compare</Txt>
        {["answer A", "answer B"].map((t, k) => <Card key={k} x={xs[0] - 110} y={y - 110 + k * 120} w={220} h={95} label={t} color={k ? C.muted : C.cool} p={1} fs={B.fs * 0.85} lit={k === 0 && s1 > 0.8 ? 0.5 : 0}/>)}
        {s1 > 0.8 && <Txt x={xs[0] + 150} y={y - 62} size={B.fs * 0.9} color={C.cool}>✓ better</Txt>}
      </g>
      <Arrow a={[xs[0] + 120, y]} b={[xs[1] - 120, y]} draw={s2} color={C.muted}/>
      <Card x={xs[1] - 110} y={y - 70} w={220} h={140} icon="scale" label="reward model" color={C.violet} p={pop(T.t - 60)} fs={B.fs * 0.85}/>
      <Txt x={xs[1]} y={B.y0 + B.fs * 0.4} size={B.fs} color={C.violet} op={s2}>2. learns their taste</Txt>
      <Arrow a={[xs[1] + 120, y]} b={[xs[2] - 120, y]} draw={s3} color={C.muted} label="score" fs={B.fs * 0.8}/>
      <Card x={xs[2] - 110} y={y - 70} w={220} h={140} icon="brain-circuit" label="model" color={pal(e, 0)} p={pop(later(T, 110))} fs={B.fs} lit={s3 > 0.9 ? 0.6 : 0}/>
      <Txt x={xs[2]} y={B.y0 + B.fs * 0.4} size={B.fs} color={pal(e, 0)} op={s3}>3. tuned to score higher</Txt>
      {e.text && <Txt x={B.cx} y={B.y1 - B.fs * 0.3} size={B.fs * 0.9} color={C.muted} op={s3}>{e.text}</Txt>}
    </g>
  );
};

export const Agent = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), stages = [["think", "brain"], ["act", "wrench"], ["observe", "eye"]];
  const R = Math.min(B.H * 0.27, B.W * 0.18), cx = B.x0 + B.W * 0.36, cy = B.cy + B.H * 0.08, P = (k) => [cx + R * Math.cos(-Math.PI / 2 + (2 * Math.PI * k) / 3), cy + R * Math.sin(-Math.PI / 2 + (2 * Math.PI * k) / 3)];
  const loop = Math.max(0, (T.t - 20) / 30), cur = Math.floor(loop) % 3, turn = Math.floor(loop / 3), tool = turn % e.tools.length, done = later(T, 160) > 0;
  const tx = B.x1 - B.W * 0.16, ty = row(e.tools.length, B.y0 + 50, B.y1 - 50);
  return (
    <g>
      <Chip x={cx} y={B.y0 + B.fs * 0.6} text={e.task || "the task"} color={C.text} p={pop(T.t)} fs={B.fs} fill/>
      <circle cx={cx} cy={cy} r={R} fill="none" stroke={alpha(C.muted, 0.4)} strokeWidth={4} strokeDasharray="8 10"/>
      {stages.map(([nm, ic], k) => { const [x, y] = P(k), on = k === cur && !done; return (
        <g key={k}>
          <circle cx={x} cy={y} r={60} fill={on ? alpha(pal(e, k), 0.4) : alpha(C.panel, 0.95)} stroke={pal(e, k)} strokeWidth={on ? 6 : 3} style={{filter: on ? glowF(pal(e, k), 0.7) : undefined}}/>
          <Ico name={ic} x={x} y={y - 12} size={38} color={pal(e, k)}/>
          <Txt x={x} y={y + 28} size={B.fs * 0.8}>{nm}</Txt>
        </g>); })}
      {ty.map((y, k) => <Card key={k} x={tx - 100} y={y - 40} w={200} h={80} label={e.tools[k]} color={k === tool && cur === 1 && !done ? C.hot : C.muted} p={pop(T.t - 10 - k * 4)} fs={B.fs * 0.85}
                                lit={k === tool && cur === 1 && !done ? 0.6 : 0}/>)}
      {cur === 1 && !done && <Packet pts={[P(1), [tx - 100, ty[tool]]]} t={(loop % 1) * 1.4} color={C.hot}/>}
      {cur === 2 && !done && <Packet pts={[[tx - 100, ty[tool]], P(2)]} t={(loop % 1) * 1.4} color={C.cool}/>}
      {done && <Chip x={cx} y={cy} text="done ✓" color={pal(e, 0)} p={pop(later(T, 160))} fs={B.fs * 1.1} fill lit={0.6}/>}
    </g>
  );
};

export const Sampling = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.items.length, q = glide(later(T, 50), 1.6);
  const temp = e.temp === "high" ? 2.2 : 0.45, raw = e.items.map((it) => Math.exp(Math.log(Math.max(1e-6, it.value)))), tot = raw.reduce((s, x) => s + x, 0);
  const base = raw.map((x) => x / tot), tilt = raw.map((x) => Math.pow(x, 1 / temp)), tt = tilt.reduce((s, x) => s + x, 0), now = base.map((b, k) => lerp(b, tilt[k] / tt, q));
  const xs = spread(n, B.x0, B.x1), bot = B.y1 - B.fs * 1.4, top = B.y0 + B.fs * 1.6, bw = Math.min(120, (B.W / n) * 0.55), mx = Math.max(...now, ...base);
  const cut = 0.92; let acc = 0; const order = [...now.keys()].sort((a, b) => now[b] - now[a]); const kept = new Set(); order.forEach((k) => { if (acc < cut) kept.add(k); acc += now[k]; });
  return (
    <g>
      <Txt x={B.x0} y={B.y0 + B.fs * 0.4} size={B.fs} anchor="start" color={q > 0.5 ? C.hot : C.muted}>{q > 0.5 ? (e.temp === "high" ? "high temperature: flatter, more surprising" : "low temperature: sharper, safer") : "next-word chances"}</Txt>
      {e.items.map((it, k) => {
        const h = ((bot - top) * now[k]) / mx, off = q > 0.9 && !kept.has(k);
        return (
          <g key={k} opacity={off ? 0.3 : 1}>
            <rect x={xs[k] - bw / 2} y={bot - h} width={bw} height={h} rx={8} fill={alpha(off ? C.muted : pal(e, k), 0.8)}/>
            <Txt x={xs[k]} y={bot + B.fs * 0.8} size={B.fs}>{it.text}</Txt>
            {off && <Txt x={xs[k]} y={bot - h - B.fs * 0.8} size={B.fs * 0.8} color={C.hot}>cut (top-p)</Txt>}
          </g>
        );
      })}
    </g>
  );
};

export const Beam = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), W = e.width, words = e.words, depth = 3;
  const levels = [[{w: "", parent: -1, keep: true}]];
  let wi = 0;
  for (let d = 1; d <= depth; d++) {
    const prev = levels[d - 1].map((n, i) => [n, i]).filter(([n]) => n.keep), next = [];
    prev.forEach(([, i]) => { for (let c = 0; c < 2; c++) next.push({w: words[wi++ % words.length], parent: i, keep: false}); });
    next.forEach((n, j) => { n.keep = j % 2 === 0 && j / 2 < W; });
    if (!next.some((n) => n.keep)) next[0].keep = true;
    levels.push(next);
  }
  const xs = spread(depth + 1, B.x0, B.x1), ys = levels.map((lv) => spread(lv.length, B.y0, B.y1));
  return (
    <g>
      {levels.map((lv, d) => lv.map((n, j) => {
        if (d === 0) return <circle key={`r${j}`} cx={xs[0]} cy={B.cy} r={14} fill={C.text}/>;
        const p = glide(T.t - 10 - d * 26, 1), pruned = !n.keep && T.t > 10 + d * 26 + 18, px = xs[d - 1], py = d === 1 ? B.cy : ys[d - 1][n.parent];
        return (
          <g key={`${d}-${j}`} opacity={clamp(p * 2) * (pruned ? 0.3 : 1)}>
            <line x1={px + 50} y1={py} x2={lerp(px + 50, xs[d] - 50, p)} y2={lerp(py, ys[d][j], p)} stroke={n.keep ? pal(e, 0) : C.muted} strokeWidth={n.keep ? 5 : 2}/>
            <Chip x={xs[d]} y={ys[d][j]} text={n.w} color={n.keep ? pal(e, 0) : C.muted} p={1} fs={Math.min(B.fs * 0.85, (B.H / lv.length) * 0.4)} fill={n.keep} strike={pruned ? 1 : 0}/>
          </g>
        );
      }))}
      <Txt x={B.x1} y={B.y0} size={B.fs * 0.85} anchor="end" color={C.muted}>{`keep the best ${W}`}</Txt>
    </g>
  );
};

export const Chunking = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.chunk === "small" ? 6 : 3, dx = B.x0 + 20, dw = B.W * 0.3, dh = B.H - 20;
  const cut = glide(T.t - 30, 1.6), emb = glide(later(T, 80), 1.6), ch = dh / n, ov = ch * 0.25;
  return (
    <g>
      <rect x={dx} y={B.y0 + 10} width={dw} height={dh} rx={8} fill={alpha(C.panel, 0.95)} stroke={C.muted} strokeWidth={3}/>
      {Array.from({length: 18}, (_, k) => <rect key={k} x={dx + 20} y={B.y0 + 30 + k * ((dh - 40) / 18)} width={dw * (0.6 + 0.3 * ((k * 7) % 3) / 2)} height={6} rx={3} fill={alpha(C.text, 0.25)}/>)}
      {e.text && <Txt x={dx + dw / 2} y={B.y0 - 4} size={B.fs * 0.85} color={C.muted}>{e.text}</Txt>}
      {Array.from({length: n}, (_, k) => {
        const y = B.y0 + 10 + k * ch - (k ? ov : 0), h = ch + (k ? ov : 0) + (k < n - 1 ? ov : 0), col = pal(e, k), x = lerp(dx, dx + dw + 60 + (k % 2) * 30, cut);
        return (
          <g key={k} opacity={clamp(cut * 3 - k * 0.2)}>
            <rect x={x} y={y + k * 6 * cut} width={dw * 0.8} height={h} rx={8} fill={alpha(col, 0.18)} stroke={col} strokeWidth={3}/>
            <Arrow a={[x + dw * 0.8 + 6, y + h / 2 + k * 6 * cut]} b={[B.x1 - B.W * 0.2, y + h / 2 + k * 6 * cut]} draw={clamp(emb * 2 - k * 0.15)} color={col} width={3}/>
            {emb > 0.4 && Array.from({length: 6}, (_, j) => <rect key={j} x={B.x1 - B.W * 0.18 + j * 26} y={y + h / 2 + k * 6 * cut - 10} width={22} height={20} rx={4} fill={alpha(col, 0.3 + 0.12 * ((j * k + j) % 5))}/>)}
          </g>
        );
      })}
      {cut > 0.8 && <Txt x={dx + dw + 60 + dw * 0.4} y={B.y0 - 4} size={B.fs * 0.8} color={C.muted}>chunks overlap a little</Txt>}
    </g>
  );
};

export const Guardrails = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), y = B.cy, xs = [B.x0 + B.W * 0.06, B.x0 + B.W * 0.3, B.cx + B.W * 0.05, B.x1 - B.W * 0.28, B.x1 - B.W * 0.05];
  const c = cyc(T.t, 20, 70), blocked = c.n % 3 === 1, blockOut = c.n % 3 === 2;
  const gate = (x, label, hit) => (
    <g>
      <rect x={x - 70} y={y - 110} width={140} height={220} rx={14} fill={alpha(hit ? C.hot : C.panel, hit ? 0.25 : 0.95)} stroke={hit ? C.hot : C.cool} strokeWidth={4} style={{filter: hit ? glowF(C.hot, 0.6) : undefined}}/>
      <Ico name="shield-check" x={x} y={y - 60} size={42} color={hit ? C.hot : C.cool}/>
      <Txt x={x} y={y - 10} size={B.fs * 0.8}>{label}</Txt>
      {e.checks.slice(0, 3).map((ck, k) => <Txt key={k} x={x} y={y + 24 + k * B.fs * 0.9} size={B.fs * 0.65} color={C.muted}>{ck}</Txt>)}
    </g>
  );
  const ph = c.ph, stopAt = blocked ? 0.25 : blockOut ? 0.75 : 1;
  return (
    <g>
      <Ico name="user" x={xs[0]} y={y} size={60} color={C.text} op={clamp(T.t / 10)}/>
      {gate(xs[1], "input check", blocked && ph > 0.22 && ph < 0.6)}
      <Card x={xs[2] - 90} y={y - 70} w={180} h={140} icon="brain-circuit" label="LLM" color={pal(e, 0)} p={pop(T.t - 6)} fs={B.fs}/>
      {gate(xs[3], "output check", blockOut && ph > 0.72)}
      <Ico name="message-circle" x={xs[4]} y={y} size={56} color={C.text} op={clamp(T.t / 10)}/>
      {c.on && <Packet pts={[[xs[0] + 40, y], [xs[4] - 40, y]]} t={Math.min(ph, stopAt - 0.02)} color={(blocked && ph > 0.22) || (blockOut && ph > 0.72) ? C.hot : C.cool}/>}
      {c.on && (blocked || blockOut) && ph > stopAt - 0.02 && <Txt x={blocked ? xs[1] : xs[3]} y={y + 150} size={B.fs} color={C.hot}>blocked</Txt>}
    </g>
  );
};

export const LlmTraining = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.stages.length, xs = spread(n, B.x0, B.x1), icons = ["library", "graduation-cap", "heart-handshake", "rocket"];
  const step = Math.max(0, (T.t - 16) / 34);
  return (
    <g>
      {e.stages.map((s, k) => {
        const on = step > k, p = pop(T.t - 16 - k * 34);
        return (
          <g key={k}>
            {k > 0 && <Arrow a={[xs[k - 1] + 110, B.cy]} b={[xs[k] - 112, B.cy]} draw={clamp(step - k + 0.3)} color={C.muted} width={4}/>}
            <Card x={xs[k] - 110} y={B.cy - 80} w={220} h={160} icon={icons[k % 4]} label={s} color={pal(e, k)} p={p} fs={fitFs(s, B.fs * 0.9, 200)} lit={on && step < k + 1 ? 0.6 : 0}/>
            <circle cx={xs[k]} cy={B.cy + 130} r={14 + 10 * k} fill={alpha(pal(e, k), 0.3)} stroke={pal(e, k)} strokeWidth={3} opacity={clamp(p * 2)}/>
          </g>
        );
      })}
      <Txt x={B.cx} y={B.y0 + B.fs * 0.3} size={B.fs * 0.9} color={C.muted}>the same model, more useful at each stage</Txt>
    </g>
  );
};

export const Prompt = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.parts.length, W = Math.min(B.W * 0.6, 760), x0 = B.cx - W / 2, top = B.y0 + 10, h = (B.H - 40) / n;
  const per = Math.max(16, (end - T.at - 40) / (n + 0.6));
  return (
    <g>
      <rect x={x0 - 14} y={top - 6} width={W + 28} height={B.H - 14} rx={18} fill="none" stroke={C.hot} strokeWidth={4} strokeDasharray="12 8" opacity={clamp(T.t / 10)}/>
      <Txt x={x0 + W + 30} y={top + 10} size={B.fs * 0.85} anchor="start" color={C.hot}>context window</Txt>
      {e.parts.map((p, k) => {
        const s = pop(T.t - 10 - k * per), y = top + k * h;
        return (
          <g key={k} opacity={clamp(s * 2)} transform={`translate(0,${(1 - s) * -60})`}>
            <rect x={x0} y={y + 6} width={W} height={h - 12} rx={12} fill={alpha(pal(e, k), 0.25)} stroke={pal(e, k)} strokeWidth={3}/>
            <Txt x={x0 + 24} y={y + h / 2} size={Math.min(B.fs, h * 0.36)} anchor="start">{p}</Txt>
          </g>
        );
      })}
    </g>
  );
};

// ================================================================================================= GenAI architecture
export const LlmGateway = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.models.length, gx = B.x0 + B.W * 0.38, mx = B.x1 - B.W * 0.13, my = row(n, B.y0 + 50, B.y1 - 50);
  const c = cyc(T.t, 24, 56), fail = later(T, 120) > 0, pick = fail ? 1 % n : 0, steps = ["auth", "cache", "router"];
  return (
    <g>
      <Ico name="users" x={B.x0 + 50} y={B.cy} size={70} color={C.text} op={clamp(T.t / 10)}/>
      <rect x={gx - 130} y={B.cy - 150} width={260} height={300} rx={18} fill={alpha(C.panel, 0.95)} stroke={pal(e, 0)} strokeWidth={4} opacity={clamp(pop(T.t - 4) * 2)}/>
      <Txt x={gx} y={B.cy - 175} size={B.fs} color={pal(e, 0)}>LLM gateway</Txt>
      {steps.map((s, k) => <Chip key={k} x={gx} y={B.cy - 90 + k * 90} text={s} color={pal(e, k)} p={pop(T.t - 8 - k * 4)} fs={B.fs * 0.85} lit={c.on && Math.floor(c.ph * 6) === k + 1 ? 0.6 : 0}/>)}
      {my.map((y, k) => {
        const down = fail && k === 0;
        return (
          <g key={k}>
            <Card x={mx - 110} y={y - 45} w={220} h={90} icon={down ? "circle-x" : "brain-circuit"} label={e.models[k]} color={down ? C.hot : k === pick ? C.cool : C.muted} p={pop(T.t - 12 - k * 4)} fs={B.fs * 0.85}
                  lit={k === pick && c.ph > 0.6 ? 0.6 : 0} dim={down}/>
            <line x1={gx + 130} y1={B.cy} x2={mx - 110} y2={y} stroke={k === pick ? C.cool : alpha(C.muted, 0.3)} strokeWidth={k === pick ? 4 : 2} strokeDasharray={k === pick ? undefined : "6 8"}/>
          </g>
        );
      })}
      {c.on && <Packet pts={[[B.x0 + 90, B.cy], [gx - 130, B.cy], [gx, B.cy + 90], [gx + 130, B.cy], [mx - 110, my[pick]]]} t={c.ph} color={C.hot}/>}
      {fail && <Txt x={B.x1} y={B.y0 + 4} size={B.fs * 0.85} anchor="end" color={C.hot}>a model failed: fallback to the next</Txt>}
    </g>
  );
};

export const Ingest = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), stages = [["load", "file-text"], ["chunk", "scissors"], ["embed", "binary"], ["vector DB", "database"]];
  const xs = spread(stages.length + 1, B.x0, B.x1), c = cyc(T.t, 20, 60);
  return (
    <g>
      {e.sources.map((s, k) => <Chip key={k} x={xs[0]} y={row(e.sources.length, B.y0 + 60, B.y1 - 60)[k]} text={s} color={pal(e, k)} p={pop(T.t - k * 4)} fs={B.fs * 0.9} fill/>)}
      {stages.map(([nm, ic], k) => (
        <g key={k}>
          <Arrow a={[xs[k] + (k ? 90 : 70), B.cy]} b={[xs[k + 1] - 92, B.cy]} draw={glide(T.t - 10 - k * 8)} color={C.muted} width={3}/>
          <Card x={xs[k + 1] - 90} y={B.cy - 70} w={180} h={140} icon={ic} label={nm} color={pal(e, k + 1)} p={pop(T.t - 10 - k * 8)} fs={B.fs * 0.85}
                lit={c.on && Math.floor(c.ph * 4) === k ? 0.6 : 0}/>
        </g>
      ))}
      {c.on && <Packet pts={[[xs[0] + 70, B.cy], [xs[4], B.cy]]} t={c.ph} color={C.hot}/>}
    </g>
  );
};

export const SemanticCache = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), cache = [B.cx, B.cy], llm = [B.x1 - B.W * 0.12, B.cy];
  const first = glide(T.t - 16, 1.6), second = later(T, 90) > 0 ? glide(later(T, 90), 1.6) : 0, sim = second > 0.5;
  return (
    <g>
      <Card x={cache[0] - 120} y={cache[1] - 80} w={240} h={160} icon="zap" label="semantic cache" color={C.cool} p={pop(T.t)} fs={B.fs * 0.8} lit={sim ? 0.6 : 0}/>
      <Card x={llm[0] - 100} y={llm[1] - 70} w={200} h={140} icon="brain-circuit" label="LLM" color={pal(e, 0)} p={pop(T.t - 6)} fs={B.fs} dim={sim}/>
      <Chip x={B.x0 + B.W * 0.16} y={B.y0 + 40} text={e.old} color={C.muted} p={pop(T.t - 10)} fs={fitFs(e.old, B.fs * 0.8, B.W * 0.3)} fill/>
      <Packet pts={[[B.x0 + B.W * 0.16, B.y0 + 60], [cache[0] - 120, cache[1] - 30], [llm[0] - 100, llm[1]]]} t={first} color={C.muted}/>
      {second > 0 && <g>
        <Chip x={B.x0 + B.W * 0.16} y={B.y1 - 40} text={e.new} color={C.hot} p={pop(later(T, 90))} fs={fitFs(e.new, B.fs * 0.8, B.W * 0.3)} fill/>
        <Packet pts={[[B.x0 + B.W * 0.16, B.y1 - 60], [cache[0] - 120, cache[1] + 30], [B.x0 + B.W * 0.16, B.y1 - 60]]} t={second} color={C.cool}/>
        {sim && <Txt x={cache[0]} y={cache[1] + 115} size={B.fs * 0.9} color={C.cool}>same meaning: stored answer, no model call</Txt>}
      </g>}
    </g>
  );
};

export const MultiAgent = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.agents.length, plan = [B.cx, B.y0 + 60], xs = spread(n, B.x0, B.x1), ay = B.cy + B.H * 0.15;
  const out = glide(T.t - 30, 1.2), back = glide(later(T, 110), 1.2);
  return (
    <g>
      <Card x={plan[0] - 130} y={plan[1] - 50} w={260} h={100} icon="list-checks" label="planner" color={pal(e, 0)} p={pop(T.t)} fs={B.fs * 0.9} sub={e.task}/>
      {xs.map((x, k) => (
        <g key={k}>
          <Arrow a={[plan[0], plan[1] + 52]} b={[x, ay - 62]} draw={out} color={pal(e, k + 1)} width={3}/>
          <Card x={x - 100} y={ay - 60} w={200} h={120} icon={["search", "code", "badge-check", "pen-tool"][k % 4]} label={e.agents[k]} color={pal(e, k + 1)} p={pop(T.t - 20 - k * 6)} fs={B.fs * 0.85}
                lit={out > 0.9 && back < 0.1 ? 0.4 + 0.3 * Math.sin((T.t + k * 10) / 6) : 0}/>
          {back > 0 && <Packet pts={[[x, ay - 62], [plan[0], plan[1] + 52]]} t={back - k * 0.08} color={pal(e, k + 1)}/>}
        </g>
      ))}
      {back > 0.95 && <Txt x={plan[0]} y={B.y1 - 6} size={B.fs} color={pal(e, 0)}>results combined</Txt>}
    </g>
  );
};

export const AI = {backprop: Backprop, cnn: Cnn, rnn: Rnn, transformer: Transformer, gan: Gan, autoencoder: Autoencoder,
  kvcache: KvCache, moe: Moe, lora: Lora, quantize: Quantize, rlhf: Rlhf, agent: Agent, sampling: Sampling, beam: Beam,
  chunking: Chunking, guardrails: Guardrails, llmtraining: LlmTraining, prompt: Prompt, llmgateway: LlmGateway,
  ingest: Ingest, semanticcache: SemanticCache, multiagent: MultiAgent};
