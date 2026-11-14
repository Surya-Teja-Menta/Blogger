// General explainer techniques (blogwriter/vizlib.py, family "explain"): metaphors and familiar objects that make an
// idea land: a split screen, an iceberg, a see-saw, stairs, a chat, a terminal, dominoes, a paper card.
import {Arrow, C, Card, Chip, Ico, Packet, React, Txt, alpha, box, clamp, fitFs, glide, glowF, lerp, pal, pop, rng, row,
        smoothPath, spread, timing, tw} from "./kit";
import {Spark} from "./charts";

// --------------------------------------------------------------------------------------------------------------
export const Split = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), wipe = glide(T.k > 0 ? T.k : T.t - 50, 1.6);
  const div = lerp(B.x1 - 10, B.cx, wipe);
  const side = (x, text, icon, col, op) => (
    <g opacity={op}>
      <Ico name={icon || "circle-dot"} x={x} y={B.cy - B.H * 0.1} size={Math.min(B.H * 0.42, B.W * 0.2)} color={col}/>
      <Txt x={x} y={B.cy + B.H * 0.3} size={fitFs(text, B.fs * 1.2, B.W * 0.42)} color={col}>{text}</Txt>
    </g>
  );
  return (
    <g>
      {side(B.x0 + B.W * 0.25, e.left, e.licon, C.muted, clamp(T.t / 12))}
      {side(B.x0 + B.W * 0.75, e.right, e.ricon, pal(e, 0), clamp((wipe - 0.4) * 3))}
      <line x1={div} y1={B.y0} x2={div} y2={B.y1} stroke={C.hot} strokeWidth={6} style={{filter: glowF(C.hot, 0.6)}}/>
      <circle cx={div} cy={B.cy} r={26} fill={C.hot}/>
      <Txt x={div} y={B.cy} size={26} color={C.bg} halo={false}>⇆</Txt>
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Magnifier = ({e, rect, frame, end, vertical, seed = 0}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.count, cols = Math.ceil(Math.sqrt(n * (B.W / B.H)));
  const rowsN = Math.ceil(n / cols), cw = B.W / cols, ch = B.H / rowsN, target = Math.floor(n * 0.63);
  const pos = (k) => [B.x0 + (k % cols + 0.5) * cw, B.y0 + (Math.floor(k / cols) + 0.5) * ch];
  const path = [[B.x0 + 40, B.y0 + 40], [B.x1 - 60, B.y0 + B.H * 0.3], [B.x0 + B.W * 0.2, B.y0 + B.H * 0.6], pos(target)];
  const t = glide(T.k > 0 ? T.k : T.t - 20, 3.2);
  const segs = path.length - 1, s = Math.min(segs - 1, Math.floor(t * segs)), u = t * segs - s;
  const lens = [lerp(path[s][0], path[s + 1][0], u), lerp(path[s][1], path[s + 1][1], u)], R = Math.min(cw, ch) * 1.4, found = t > 0.98;
  return (
    <g>
      {Array.from({length: n}, (_, k) => { const [x, y] = pos(k), d = Math.hypot(x - lens[0], y - lens[1]); return (
        <Ico key={k} name={e.icon} x={x} y={y} size={Math.min(cw, ch) * 0.55 * (d < R ? 1.35 : 1)} color={k === target && found ? C.hot : d < R ? C.text : alpha(C.muted, 0.9)}
             op={clamp((T.t - k * 0.3) / 8)}/>); })}
      <circle cx={lens[0]} cy={lens[1]} r={R} fill={alpha(C.text, 0.06)} stroke={found ? C.hot : C.text} strokeWidth={7}/>
      <line x1={lens[0] + R * 0.7} y1={lens[1] + R * 0.7} x2={lens[0] + R * 1.4} y2={lens[1] + R * 1.4} stroke={found ? C.hot : C.text} strokeWidth={14} strokeLinecap="round"/>
      {found && e.find && <Chip x={lens[0]} y={lens[1] - R - B.fs} text={e.find} color={C.hot} p={1} fs={B.fs} fill/>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Iceberg = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), water = B.y0 + B.H * 0.32, cx = B.cx;
  const sink = glide(T.k > 0 ? T.k : T.t - 40, 1.6), W = Math.min(B.W * 0.5, B.H * 0.9);
  const tip = `M${cx - W * 0.18},${water} L${cx - W * 0.05},${B.y0 + 12} L${cx + W * 0.08},${B.y0 + B.H * 0.08} L${cx + W * 0.2},${water} Z`;
  const body = `M${cx - W * 0.18},${water} L${cx - W * 0.5},${water + B.H * 0.3} L${cx - W * 0.32},${B.y1 - 8} L${cx + W * 0.3},${B.y1 - 20} L${cx + W * 0.52},${water + B.H * 0.25} L${cx + W * 0.2},${water} Z`;
  const by = row(e.below.length, water + B.H * 0.16, B.y1 - B.H * 0.12);
  return (
    <g>
      <rect x={B.x0} y={water} width={B.W} height={B.y1 - water} fill={alpha(C.cool, 0.18)} opacity={clamp(T.t / 10)}/>
      <line x1={B.x0} y1={water} x2={B.x1} y2={water} stroke={C.cool} strokeWidth={4} opacity={clamp(T.t / 10)}/>
      <path d={tip} fill={alpha(C.text, 0.9)} opacity={clamp(pop(T.t - 6) * 2)}/>
      <path d={body} fill={alpha(C.text, 0.25)} stroke={alpha(C.text, 0.5)} strokeWidth={3} opacity={sink}/>
      {e.top.map((t, k) => <Txt key={k} x={cx + W * 0.34} y={B.y0 + B.H * 0.1 + k * B.fs * 1.3} size={B.fs} anchor="start" op={clamp((T.t - 10) / 10)}>{t}</Txt>)}
      {e.below.map((t, k) => <Chip key={`b${k}`} x={cx + (k % 2 ? 1 : -1) * W * 0.16} y={by[k]} text={t} color={pal(e, k + 1)} p={glide((sink - 0.3) * 40 - k * 6)} fs={B.fs * 0.85} fill/>)}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Balance = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), cx = B.cx, cy = B.cy + B.H * 0.1, L = Math.min(B.W * 0.38, 520);
  const target = e.tip === "left" ? -0.22 : e.tip === "right" ? 0.22 : 0, a = target * glide(T.k > 0 ? T.k : T.t - 50, 1.5) + (T.k > 0 ? 0.015 * Math.sin(T.k / 5) * Math.exp(-T.k / 40) : 0);
  const end0 = [cx - L * Math.cos(a), cy - L * Math.sin(a)], end1 = [cx + L * Math.cos(a), cy + L * Math.sin(a)];
  const pan = (p, items, col, k0) => items.map((t, k) => <Chip key={k} x={p[0]} y={p[1] - 64 - k * B.fs * 1.9} text={t} color={col} p={pop(T.t - 8 - (k0 + k) * 6)} fs={B.fs} fill/>);
  return (
    <g>
      <path d={`M${cx - 50},${B.y1} L${cx},${cy} L${cx + 50},${B.y1} Z`} fill={alpha(C.muted, 0.5)}/>
      <line x1={end0[0]} y1={end0[1]} x2={end1[0]} y2={end1[1]} stroke={C.text} strokeWidth={10} strokeLinecap="round"/>
      <circle cx={cx} cy={cy} r={14} fill={C.hot}/>
      {pan(end0, e.left, pal(e, 0), 0)}
      {pan(end1, e.right, C.hot, e.left.length)}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Staircase = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.steps.length;
  const sw = B.W / n, sh = (B.H * 0.8) / n, climb = clamp((T.t - 20) / Math.max(30, (end - T.at - 30)) * n * 1.1, 0, n - 0.001);
  const at = Math.floor(climb), fx = B.x0 + (at + 0.5) * sw, fy = B.y1 - (at + 1) * sh - 34;
  return (
    <g>
      {e.steps.map((s, k) => {
        const x = B.x0 + k * sw, y = B.y1 - (k + 1) * sh, on = k <= at;
        return (
          <g key={k} opacity={clamp(pop(T.t - k * 6) * 2)}>
            <rect x={x} y={y} width={sw} height={(k + 1) * sh} fill={on ? alpha(pal(e, k), 0.35) : alpha(C.panel, 0.9)} stroke={on ? pal(e, k) : C.muted} strokeWidth={3}/>
            <Txt x={x + sw / 2} y={y + Math.min(sh * 0.5, B.fs * 1.2)} size={fitFs(s, B.fs, sw * 0.85)} color={on ? C.text : C.muted}>{s}</Txt>
          </g>
        );
      })}
      <Ico name="person-standing" x={fx} y={fy} size={60} color={C.hot}/>
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Quadrant = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), pad = B.fs * 1.6;
  const X = (x) => B.x0 + pad + x * (B.W - pad * 2), Y = (y) => B.y1 - pad - y * (B.H - pad * 2), cx = X(0.5), cy = Y(0.5);
  return (
    <g>
      <rect x={X(0.5)} y={Y(1)} width={X(1) - X(0.5)} height={Y(0.5) - Y(1)} fill={alpha(pal(e, 0), 0.08)}/>
      <line x1={X(0)} y1={cy} x2={X(1)} y2={cy} stroke={C.muted} strokeWidth={3} opacity={clamp(T.t / 10)}/>
      <line x1={cx} y1={Y(0)} x2={cx} y2={Y(1)} stroke={C.muted} strokeWidth={3} opacity={clamp(T.t / 10)}/>
      <Txt x={X(0)} y={cy + B.fs * 0.9} size={B.fs * 0.85} anchor="start" color={C.muted}>{e.xlo}</Txt>
      <Txt x={X(1)} y={cy + B.fs * 0.9} size={B.fs * 0.85} anchor="end" color={C.muted}>{e.xhi}</Txt>
      <Txt x={cx + 12} y={Y(0)} size={B.fs * 0.85} anchor="start" color={C.muted}>{e.ylo}</Txt>
      <Txt x={cx + 12} y={Y(1)} size={B.fs * 0.85} anchor="start" color={C.muted}>{e.yhi}</Txt>
      {e.items.map((it, k) => {
        const p = glide(T.t - 18 - k * 8, 1.3);
        return <Chip key={k} x={lerp(cx, X(it.x), p)} y={lerp(cy, Y(it.y), p)} text={it.text} color={pal(e, k)} p={clamp(p * 2)} fs={B.fs * 0.9} fill lit={T.k > 0 && k === 0 ? 0.5 : 0}/>;
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Spectrum = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), y = B.cy, x0 = B.x0 + 30, x1 = B.x1 - 30;
  return (
    <g>
      <defs><linearGradient id={`spec${e.at}`} x1="0" x2="1"><stop offset="0" stopColor={pal(e, 0)}/><stop offset="1" stopColor={C.hot}/></linearGradient></defs>
      <rect x={x0} y={y - 10} width={(x1 - x0) * glide(T.t, 1.4)} height={20} rx={10} fill={`url(#spec${e.at})`}/>
      <Txt x={x0} y={y + B.fs * 1.6} size={B.fs} anchor="start" color={pal(e, 0)}>{e.left}</Txt>
      <Txt x={x1} y={y + B.fs * 1.6} size={B.fs} anchor="end" color={C.hot}>{e.right}</Txt>
      {e.items.map((it, k) => {
        const p = glide(T.t - 16 - k * 9, 1.4), x = lerp(B.cx, lerp(x0, x1, it.at), p), up = k % 2 === 0;
        return (
          <g key={k} opacity={clamp(p * 2)}>
            <line x1={x} y1={y} x2={x} y2={y + (up ? -70 : 70)} stroke={C.text} strokeWidth={3}/>
            <circle cx={x} cy={y} r={12} fill={C.text}/>
            <Chip x={x} y={y + (up ? -96 : 96)} text={it.text} color={pal(e, k + 1)} p={1} fs={B.fs * 0.85} fill/>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Checklist = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.items.length, ys = row(n, B.y0 + 30, B.y1 - 30), x = B.x0 + B.W * 0.22;
  const per = Math.max(14, (end - T.at - 40) / (n + 1));
  return (
    <g>
      {e.items.map((it, k) => {
        const s = 16 + k * per, on = T.t > s + 10, bad = k === e.fail, p = pop(T.t - k * 4);
        return (
          <g key={k} opacity={clamp(p * 2)}>
            <rect x={x - 30} y={ys[k] - 26} width={52} height={52} rx={10} fill={alpha(C.panel, 0.95)} stroke={on ? (bad ? C.hot : pal(e, 0)) : C.muted} strokeWidth={4}/>
            {on && <path d={bad ? `M${x - 18},${ys[k] - 14} l28,28 m0,-28 l-28,28` : `M${x - 18},${ys[k]} l10,12 l20,-26`} fill="none" stroke={bad ? C.hot : pal(e, 0)}
                         strokeWidth={7} strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - glide(T.t - s - 10, 0.5)}/>}
            <Txt x={x + 50} y={ys[k]} size={fitFs(it, B.fs * 1.1, B.W * 0.6)} anchor="start" color={on && bad ? C.hot : C.text}>{it}</Txt>
            {on && bad && <line x1={x + 50} y1={ys[k]} x2={x + 50 + tw(it, B.fs * 1.1) * glide(T.t - s - 14, 0.6)} y2={ys[k]} stroke={C.hot} strokeWidth={5}/>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Terminal = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), lh = Math.min(B.fs * 1.5, (B.H - 70) / (e.lines.length + 1));
  const x0 = B.x0 + 10, w = B.W - 20, y0 = B.y0 + 10, chars = Math.max(0, (T.t - 10) * 1.6);
  let used = 0;
  return (
    <g>
      <rect x={x0} y={y0} width={w} height={B.H - 20} rx={16} fill={alpha("#0b0f14", 0.96)} stroke={alpha(C.muted, 0.6)} strokeWidth={3}/>
      <rect x={x0} y={y0} width={w} height={44} rx={16} fill={alpha(C.muted, 0.25)}/>
      {[0, 1, 2].map((k) => <circle key={k} cx={x0 + 30 + k * 30} cy={y0 + 22} r={9} fill={["#ff5f57", "#febc2e", "#28c840"][k]}/>)}
      {e.lines.map((l, k) => {
        const cmd = l.trim().startsWith("$"), show = Math.max(0, Math.min(l.length, chars - used));
        used += cmd ? l.length : 0;
        if (!cmd && chars < used) return null;
        const text = cmd ? l.slice(0, Math.floor(show)) : l;
        return <text key={k} x={x0 + 26} y={y0 + 70 + k * lh} fontSize={lh * 0.62} fontFamily="monospace" fill={cmd ? "#7ee787" : "#c9d1d9"} dominantBaseline="central">{text}</text>;
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Chat = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.messages.length;
  const per = Math.max(16, (end - T.at - 30) / (n + 0.5)), rh = (B.H - B.fs * 1.8) / n, fs = Math.min(B.fs, rh * 0.36);
  return (
    <g>
      <Txt x={B.x0 + 20} y={B.y0 + B.fs * 0.5} size={B.fs * 0.85} anchor="start" color={C.muted}>{e.left}</Txt>
      <Txt x={B.x1 - 20} y={B.y0 + B.fs * 0.5} size={B.fs * 0.85} anchor="end" color={C.muted}>{e.right}</Txt>
      {e.messages.map((m, k) => {
        const s = 10 + k * per, p = pop(T.t - s), left = m.side === "left", w = Math.min(B.W * 0.6, tw(m.text, fs) + fs * 2), y = B.y0 + B.fs * 1.6 + rh * k;
        const x = left ? B.x0 + 20 : B.x1 - 20 - w, typing = T.t > s - 12 && T.t < s;
        return (
          <g key={k}>
            {typing && <Txt x={left ? B.x0 + 60 : B.x1 - 60} y={y + rh * 0.4} size={fs * 1.4} color={C.muted}>…</Txt>}
            <g opacity={clamp(p * 2)} transform={`translate(0,${(1 - p) * 20})`}>
              <rect x={x} y={y + 4} width={w} height={rh * 0.78} rx={rh * 0.3} fill={left ? alpha(C.panel, 0.95) : alpha(pal(e, 0), 0.45)} stroke={left ? C.muted : pal(e, 0)} strokeWidth={2}/>
              <Txt x={x + w / 2} y={y + 4 + rh * 0.39} size={fitFs(m.text, fs, w - fs)}>{m.text}</Txt>
            </g>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Browser = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), x0 = B.x0 + 10, w = B.W - 20, y0 = B.y0 + 10, h = B.H - 20;
  const load = glide(T.t - 20, 2), loaded = load > 0.98;
  return (
    <g>
      <rect x={x0} y={y0} width={w} height={h} rx={16} fill={alpha(C.panel, 0.97)} stroke={C.muted} strokeWidth={3}/>
      <rect x={x0} y={y0} width={w} height={56} rx={16} fill={alpha(C.muted, 0.2)}/>
      <rect x={x0 + 110} y={y0 + 12} width={w - 140} height={32} rx={16} fill={alpha(C.bg, 0.6)}/>
      <Ico name="lock" x={x0 + 132} y={y0 + 28} size={20} color={C.cool}/>
      <Txt x={x0 + 152} y={y0 + 28} size={20} anchor="start" weight={600}>{e.url}</Txt>
      {[0, 1, 2].map((k) => <circle key={k} cx={x0 + 24 + k * 26} cy={y0 + 28} r={8} fill={alpha(C.muted, 0.6)}/>)}
      <rect x={x0} y={y0 + 56} width={w * load} height={5} fill={pal(e, 0)} opacity={loaded ? 0 : 1}/>
      {!loaded && <circle cx={x0 + w / 2} cy={y0 + h / 2 + 20} r={30} fill="none" stroke={pal(e, 0)} strokeWidth={6} strokeDasharray="40 150" transform={`rotate(${T.t * 12} ${x0 + w / 2} ${y0 + h / 2 + 20})`}/>}
      {loaded && e.lines.map((l, k) => <Txt key={k} x={x0 + 40} y={y0 + 110 + k * B.fs * 1.7} size={k === 0 ? B.fs * 1.3 : B.fs} anchor="start" op={clamp((T.t - 70 - k * 6) / 10)}>{l}</Txt>)}
      {loaded && [0, 1, 2].map((k) => <rect key={`b${k}`} x={x0 + 40 + k * (w - 80) / 3} y={y0 + h - 130} width={(w - 120) / 3} height={90} rx={12} fill={alpha(pal(e, k), 0.25)}
                                            opacity={clamp((T.t - 80 - k * 6) / 10)}/>)}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Phone = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), h = Math.min(B.H, 640), w = h * 0.5, x0 = B.cx - w / 2, y0 = B.cy - h / 2;
  const per = Math.max(18, (end - T.at - 30) / (e.items.length + 0.5));
  return (
    <g>
      <rect x={x0} y={y0} width={w} height={h} rx={w * 0.14} fill={alpha("#0b0f14", 0.95)} stroke={C.text} strokeWidth={5}/>
      <rect x={B.cx - w * 0.15} y={y0 + 14} width={w * 0.3} height={16} rx={8} fill={C.text}/>
      {e.items.map((it, k) => {
        const p = pop(T.t - 10 - k * per), y = y0 + 60 + (e.items.length - 1 - k) * 0;
        const slot = e.items.filter((_, j) => j > k && T.t - 10 - j * per > 0).length;
        return (
          <g key={k} opacity={clamp(p * 2)} transform={`translate(0,${(1 - p) * -40 + slot * (h * 0.16)})`}>
            <rect x={x0 + 16} y={y} width={w - 32} height={h * 0.13} rx={14} fill={alpha(C.panel, 0.97)} stroke={pal(e, k)} strokeWidth={2}/>
            <Ico name="bell" x={x0 + 44} y={y + h * 0.065} size={26} color={pal(e, k)}/>
            <Txt x={x0 + 66} y={y + h * 0.065} size={fitFs(it, B.fs * 0.8, w - 100)} anchor="start">{it}</Txt>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Dashboard = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.metrics.length, cols = n > 2 && !vertical ? 2 : 1, rowsN = Math.ceil(n / cols);
  const cw = B.W / cols, ch = B.H / rowsN, alarm = e.metrics.findIndex((m) => m.trend === "spike");
  return (
    <g>
      {e.metrics.map((m, k) => {
        const x = B.x0 + (k % cols) * cw + 10, y = B.y0 + Math.floor(k / cols) * ch + 8, w = cw - 20, h = ch - 16, red = k === alarm && T.k > 0;
        const p = glide(T.t - 6 - k * 6, 2);
        return (
          <g key={k} opacity={clamp(p * 3)}>
            <rect x={x} y={y} width={w} height={h} rx={14} fill={red ? alpha(C.hot, 0.18) : alpha(C.panel, 0.95)} stroke={red ? C.hot : alpha(C.muted, 0.5)} strokeWidth={red ? 5 : 2}
                  style={{filter: red ? glowF(C.hot, 0.5 + 0.5 * Math.sin(T.k / 4)) : undefined}}/>
            <Txt x={x + 20} y={y + B.fs * 0.9} size={B.fs * 0.9} anchor="start">{m.text}</Txt>
            {red && <Txt x={x + w - 20} y={y + B.fs * 0.9} size={B.fs * 0.85} anchor="end" color={C.hot}>ALERT</Txt>}
            <Spark x={x + 20} y={y + B.fs * 1.8} w={w - 40} h={h - B.fs * 2.4} trend={m.trend} p={p} color={red ? C.hot : pal(e, k)}/>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Dominoes = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.items.length, xs = spread(n, B.x0, B.x1), h = Math.min(B.H * 0.55, 220), w = h * 0.22, base = B.cy + h * 0.45;
  const start = T.k > 0 ? T.k : T.t - 60;
  return (
    <g>
      <line x1={B.x0} y1={base} x2={B.x1} y2={base} stroke={C.muted} strokeWidth={3}/>
      {e.items.map((it, k) => {
        const fall = glide(start - k * 10, 0.6), ang = fall * 72;
        return (
          <g key={k}>
            <g transform={`rotate(${ang} ${xs[k] + w / 2} ${base})`}>
              <rect x={xs[k] - w / 2} y={base - h} width={w} height={h} rx={8} fill={fall > 0 ? alpha(C.hot, 0.6) : alpha(pal(e, 0), 0.45)} stroke={fall > 0 ? C.hot : pal(e, 0)} strokeWidth={3}/>
            </g>
            <Txt x={xs[k]} y={base + B.fs * 0.9} size={fitFs(it, B.fs * 0.85, (B.W / n) * 0.95)} color={fall > 0 ? C.hot : C.text}>{it}</Txt>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Tug = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), y = B.cy;
  const pull = e.winner === "left" ? -1 : e.winner === "right" ? 1 : 0;
  const shift = (pull ? pull * glide(T.k > 0 ? T.k : T.t - 60, 2) * B.W * 0.12 : 0) + Math.sin(T.t / 9) * 10;
  return (
    <g>
      <line x1={B.cx} y1={y - 90} x2={B.cx} y2={y + 90} stroke={C.muted} strokeWidth={3} strokeDasharray="10 8"/>
      <path d={`M${B.x0 + 110 + shift * 0.4},${y} Q${B.cx + shift},${y + 18} ${B.x1 - 110 + shift * 0.4},${y}`} fill="none" stroke={C.text} strokeWidth={9}/>
      <rect x={B.cx + shift - 8} y={y - 20} width={16} height={40} fill={C.hot}/>
      <Ico name="person-standing" x={B.x0 + 90 + shift * 0.4} y={y} size={110} color={pal(e, 0)}/>
      <Ico name="person-standing" x={B.x1 - 90 + shift * 0.4} y={y} size={110} color={C.violet}/>
      <Txt x={B.x0 + 90} y={y + 90} size={B.fs * 1.1} color={pal(e, 0)}>{e.left}</Txt>
      <Txt x={B.x1 - 90} y={y + 90} size={B.fs * 1.1} color={C.violet}>{e.right}</Txt>
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Hourglass = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), h = Math.min(B.H * 0.9, 420), w = h * 0.6, cx = B.cx, top = B.cy - h / 2;
  const run = clamp((T.t - 10) / Math.max(40, end - T.at - 30)), gone = run >= 1;
  const upper = 1 - run, sandTop = top + 20 + (h / 2 - 30) * (1 - upper);
  return (
    <g>
      <path d={`M${cx - w / 2},${top} L${cx + w / 2},${top} L${cx + 12},${B.cy} L${cx + w / 2},${top + h} L${cx - w / 2},${top + h} L${cx - 12},${B.cy} Z`}
            fill={alpha(C.panel, 0.6)} stroke={gone ? C.hot : C.text} strokeWidth={5}/>
      <clipPath id={`hg${e.at}`}><path d={`M${cx - w / 2},${top} L${cx + w / 2},${top} L${cx + 12},${B.cy} L${cx + w / 2},${top + h} L${cx - w / 2},${top + h} L${cx - 12},${B.cy} Z`}/></clipPath>
      <g clipPath={`url(#hg${e.at})`}>
        <rect x={cx - w / 2} y={sandTop} width={w} height={B.cy - sandTop} fill={pal(e, 0)}/>
        <path d={`M${cx - w / 2},${top + h} L${cx + w / 2},${top + h} L${cx + w / 2},${top + h - (h / 2) * run * 0.7} Q${cx},${top + h - (h / 2) * run * 1.2} ${cx - w / 2},${top + h - (h / 2) * run * 0.7} Z`} fill={pal(e, 0)}/>
        {!gone && <line x1={cx} y1={B.cy} x2={cx} y2={top + h} stroke={pal(e, 0)} strokeWidth={4}/>}
      </g>
      {e.text && <Txt x={cx + w / 2 + 30} y={B.cy} size={B.fs * 1.2} anchor="start" color={gone ? C.hot : C.text}>{gone ? `${e.text}!` : e.text}</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Pyramid = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.levels.length, lh = B.H / n, W = Math.min(B.W, B.H * 1.6);
  return (
    <g>
      {e.levels.map((t, k) => {
        const lvl = n - 1 - k, y = B.y0 + lvl * lh, wTop = (W * lvl) / n, wBot = (W * (lvl + 1)) / n, p = glide(T.t - k * 10, 1.1);
        return (
          <g key={k} opacity={clamp(p * 2)} transform={`translate(0,${(1 - p) * 30})`}>
            <path d={`M${B.cx - wTop / 2 + 4},${y + 4} L${B.cx + wTop / 2 - 4},${y + 4} L${B.cx + wBot / 2 - 4},${y + lh - 2} L${B.cx - wBot / 2 + 4},${y + lh - 2} Z`}
                  fill={alpha(pal(e, k), 0.5)} stroke={pal(e, k)} strokeWidth={3}/>
            <Txt x={B.cx} y={y + lh * 0.55} size={fitFs(t, Math.min(B.fs, lh * 0.45), Math.max(wTop, wBot * 0.7) * 0.8)}>{t}</Txt>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Onion = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.layers.length, R = Math.min(B.H * 0.48, B.W * 0.3);
  return (
    <g>
      {e.layers.map((t, k) => {
        const kk = n - 1 - k, r = (R * (kk + 1)) / n, p = pop(T.t - k * 9);
        return <circle key={k} cx={B.cx} cy={B.cy} r={r * p} fill={alpha(pal(e, kk), 0.22)} stroke={pal(e, kk)} strokeWidth={4}/>;
      })}
      {e.layers.map((t, k) => {
        const r = (R * (k + 0.5)) / n, p = clamp((T.t - (n - 1 - k) * 9 - 10) / 10);
        return k === 0 ? <Txt key={k} x={B.cx} y={B.cy} size={B.fs} op={p}>{t}</Txt>
          : <Txt key={k} x={B.cx} y={B.cy - r - 4} size={Math.min(B.fs * 0.9, R / n)} op={p}>{t}</Txt>;
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Puzzle = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.pieces.length, cols = Math.min(3, n), rowsN = Math.ceil(n / cols);
  const s = Math.min((B.W * 0.7) / cols, (B.H * 0.9) / rowsN), x0 = B.cx - (s * cols) / 2, y0 = B.cy - (s * rowsN) / 2;
  const snap = glide(T.k > 0 ? T.k : T.t - 40, 1.4);
  const piece = (x, y, k) => `M${x},${y} h${s * 0.38} a${s * 0.12},${s * 0.12} 0 1 1 ${s * 0.24},0 h${s * 0.38} v${s} h${-s} Z`;
  return (
    <g>
      {e.pieces.map((t, k) => {
        const c = k % cols, r = Math.floor(k / cols), tx = x0 + c * s, ty = y0 + r * s;
        const sx = tx + (c - (cols - 1) / 2) * 90, sy = ty + (r - (rowsN - 1) / 2) * 90 + (k % 2 ? 40 : -40);
        const x = lerp(sx, tx, snap), y = lerp(sy, ty, snap);
        return (
          <g key={k} opacity={clamp(pop(T.t - k * 5) * 2)}>
            <path d={piece(x, y, k)} fill={alpha(pal(e, k), 0.5)} stroke={pal(e, k)} strokeWidth={4}/>
            <Txt x={x + s / 2} y={y + s / 2} size={fitFs(t, B.fs, s * 0.85)}>{t}</Txt>
          </g>
        );
      })}
      {snap > 0.98 && <rect x={x0 - 6} y={y0 - 6} width={s * cols + 12} height={s * rowsN + 12} rx={10} fill="none" stroke={C.text} strokeWidth={4} style={{filter: glowF(C.text, 0.5)}}/>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Paper = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), w = Math.min(B.W * 0.6, B.H * 1.15), h = B.H * 0.96, x0 = B.cx - w / 2, y0 = B.y0 + 4;
  const p = glide(T.t - 4, 1.4), hl = glide(T.k > 0 ? T.k : T.t - 50, 1);
  const ft = fitFs(e.title, B.fs * 1.15, w * 0.85 * 2);
  const words = e.title.split(" "), half = Math.ceil(words.length / 2), l1 = words.slice(0, half).join(" "), l2 = words.slice(half).join(" ");
  return (
    <g opacity={clamp(p * 2)} transform={`translate(${(1 - p) * 120},0) rotate(${(1 - p) * 4} ${B.cx} ${B.cy})`}>
      <rect x={x0} y={y0} width={w} height={h} rx={6} fill="#fbfaf6" stroke={alpha("#000000", 0.2)} strokeWidth={2} style={{filter: "drop-shadow(0 18px 30px rgba(0,0,0,0.35))"}}/>
      <text x={B.cx} y={y0 + h * 0.13} fontSize={Math.min(ft, (w * 0.9) / Math.max(8, l1.length * 0.55))} fontFamily="Georgia, serif" fontWeight={700} fill="#1a1a1a" textAnchor="middle">{l1}</text>
      <text x={B.cx} y={y0 + h * 0.13 + ft * 1.2} fontSize={Math.min(ft, (w * 0.9) / Math.max(8, l2.length * 0.55))} fontFamily="Georgia, serif" fontWeight={700} fill="#1a1a1a" textAnchor="middle">{l2}</text>
      {e.who && <text x={B.cx} y={y0 + h * 0.13 + ft * 2.4} fontSize={B.fs * 0.75} fontFamily="Georgia, serif" fontStyle="italic" fill="#444" textAnchor="middle">{e.who}{e.when ? `, ${e.when}` : ""}</text>}
      {Array.from({length: 9}, (_, k) => <rect key={k} x={x0 + w * 0.1} y={y0 + h * 0.4 + k * h * 0.06} width={w * (k === 8 ? 0.5 : 0.8)} height={6} rx={3} fill="#c9c6bd"/>)}
      {e.quote && <g>
        <rect x={x0 + w * 0.08} y={y0 + h * 0.4 + 3 * h * 0.06 - B.fs * 0.6} width={(w * 0.84) * hl} height={B.fs * 1.2} fill={alpha(C.hot, 0.35)}/>
        <text x={B.cx} y={y0 + h * 0.4 + 3 * h * 0.06 + 2} fontSize={Math.min(B.fs * 0.85, (w * 0.8) / Math.max(8, e.quote.length * 0.5))} fontFamily="Georgia, serif"
              fontWeight={700} fill="#1a1a1a" textAnchor="middle" dominantBaseline="central" opacity={clamp(hl * 2)}>“{e.quote}”</text>
      </g>}
    </g>
  );
};

export const EXPLAIN = {split: Split, magnifier: Magnifier, iceberg: Iceberg, balance: Balance, staircase: Staircase,
  quadrant: Quadrant, spectrum: Spectrum, checklist: Checklist, terminal: Terminal, chat: Chat, browser: Browser, phone: Phone,
  dashboard: Dashboard, dominoes: Dominoes, tug: Tug, hourglass: Hourglass, pyramid: Pyramid, onion: Onion, puzzle: Puzzle,
  paper: Paper};
