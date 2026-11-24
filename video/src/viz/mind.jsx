// Mind-reading and perception, with the real rules: the "guess your number" cards (each card holds the numbers with one binary
// digit set, so adding the first number of each card you point to gives your number back), and optical illusions whose lines
// really are equal, measured on screen when the reveal comes.
import {React, box, clamp, ease, lerp, pal, pop, timing, Txt, C, alpha} from "./kit";

export const BinaryCards = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), K = e.cards, secret = Math.min(2 ** K - 1, Math.max(1, e.secret));
  const bitsOf = (k) => Array.from({length: 2 ** K - 1}, (_, i) => i + 1).filter((v) => (v >> k) & 1);
  const cols = vertical ? 3 : K, rows = Math.ceil(K / cols), cw = Math.min((B.W * 0.94) / cols - 14, vertical ? 300 : 230), ch = Math.min((B.H * 0.66) / rows - 14, vertical ? 260 : 330);
  const x0 = B.cx - (cols * (cw + 14)) / 2, y0 = B.y0 + B.fs * 1.5;
  const step = Math.floor(Math.max(0, T.t - 24) / 26), pointed = [];
  for (let k = 0; k < K; k++) if ((secret >> k) & 1) pointed.push(k);
  const done = clamp((T.t - 24 - K * 26) / 26);
  return (
    <g opacity={clamp(T.t / 10)}>
      {Array.from({length: K}, (_, k) => {
        const col = k % cols, row = Math.floor(k / cols), has = (secret >> k) & 1, on = k < step, vals = bitsOf(k), side = Math.ceil(Math.sqrt(vals.length)), fs = (Math.min(ch, cw) / (side + 1.6)) * 0.62;
        const lit = on && has, g = pop(T.t - 4 - k * 5);
        return (
          <g key={k} opacity={clamp(g * 2)} transform={`translate(${x0 + col * (cw + 14)},${y0 + row * (ch + 14)})`}>
            <rect width={cw} height={ch} rx={14} fill={alpha(lit ? pal(e, 2) : C.panel, lit ? 0.35 : 0.9)} stroke={lit ? pal(e, 2) : on ? C.muted : alpha(C.muted, 0.6)} strokeWidth={lit ? 6 : 3}/>
            {vals.map((v, i) => <Txt key={v} x={cw * 0.08 + ((i % side) + 0.5) * ((cw * 0.84) / side)} y={ch * 0.12 + (Math.floor(i / side) + 0.5) * ((ch * 0.8) / side)} size={fs} color={v === secret && on ? pal(e, 2) : v === 1 << k ? C.accent : C.text} weight={v === 1 << k ? 900 : 700}>{v}</Txt>)}
            <Txt x={cw / 2} y={ch + B.fs * 0.2} size={B.fs * 0.7} color={lit ? pal(e, 2) : C.muted}>{on ? (has ? "yes: it is on this card" : "no") : `card ${k + 1}`}</Txt>
          </g>
        );
      })}
      <Txt x={B.cx} y={B.y1 - B.fs * 2.2} size={B.fs * 1.1} color={C.text} op={clamp(done * 2)}>{pointed.map((k) => 1 << k).join(" + ")} = {secret}</Txt>
      <Txt x={B.cx} y={B.y1 - B.fs * 0.6} size={B.fs * 0.8} color={C.muted}>{done > 0 ? "the first number on each yes-card is a power of two: it spells your number in binary" : "think of a number, then point to the cards it is on"}</Txt>
    </g>
  );
};

export const Illusion = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), reveal = clamp((T.k > 0 ? T.k : T.t - 60) / 24), cx = B.cx, cy = B.cy - B.fs * 0.2, S = Math.min(B.W * 0.46, B.H * 0.42);
  const strokeW = Math.max(6, S * 0.03);
  let body = null, note = "";
  if (e.kind === "mullerlyer") {
    const L = S * 1.1;
    const arrow = (y, out) => (
      <g>
        {[-1, 1].map((s) => <g key={s}>{[-1, 1].map((u) => <line key={u} x1={cx + (s * L) / 2} y1={y} x2={cx + (s * L) / 2 + (out ? s : -s) * S * 0.2} y2={y + u * S * 0.16} stroke={pal(e, 1)} strokeWidth={strokeW} strokeLinecap="round"/>)}</g>)}
        <line x1={cx - L / 2} y1={y} x2={cx + L / 2} y2={y} stroke={pal(e, 2)} strokeWidth={strokeW} strokeLinecap="round"/>
      </g>
    );
    body = <g>{arrow(cy - S * 0.3, true)}{arrow(cy + S * 0.3, false)}<g opacity={reveal}>{[-1, 1].map((s) => <line key={s} x1={cx + (s * L) / 2} y1={cy - S * 0.55} x2={cx + (s * L) / 2} y2={cy + S * 0.55} stroke={C.text} strokeWidth={3} strokeDasharray="8 7"/>)}</g></g>;
    note = reveal > 0.5 ? "the two lines are exactly the same length" : "which line is longer?";
  } else if (e.kind === "ebbinghaus") {
    const ring = (x, big) => (
      <g>
        {Array.from({length: 7}, (_, i) => { const a = (i / 7) * 2 * Math.PI, rr = big ? S * 0.12 : S * 0.2, d = big ? S * 0.42 : S * 0.3; return <circle key={i} cx={x + Math.cos(a) * d} cy={cy + Math.sin(a) * d} r={rr} fill={alpha(pal(e, 1), 0.55)}/>; })}
        <circle cx={x} cy={cy} r={S * 0.16} fill={pal(e, 2)}/>
      </g>
    );
    body = <g>{ring(cx - S * 0.75, false)}{ring(cx + S * 0.75, true)}<g opacity={reveal}>{[-1, 1].map((s) => <circle key={s} cx={cx + s * S * 0.75} cy={cy} r={S * 0.16 + 6} fill="none" stroke={C.text} strokeWidth={3} strokeDasharray="8 7"/>)}</g></g>;
    note = reveal > 0.5 ? "the two middle circles are the same size" : "which middle circle is bigger?";
  } else {                                                   // hermann grid: grey ghosts at the crossings that are not there
    const n = 4, cell = S * 0.42, gap = cell * 0.22, x0 = cx - (n * (cell + gap)) / 2, y0 = cy - (n * (cell + gap)) / 2;
    body = (
      <g>
        {Array.from({length: n * n}, (_, i) => <rect key={i} x={x0 + (i % n) * (cell + gap)} y={y0 + Math.floor(i / n) * (cell + gap)} width={cell} height={cell} rx={4} fill={C.text}/>)}
        <g opacity={reveal}>{Array.from({length: (n - 1) * (n - 1)}, (_, i) => <circle key={i} cx={x0 + ((i % (n - 1)) + 1) * (cell + gap) - gap / 2} cy={y0 + (Math.floor(i / (n - 1)) + 1) * (cell + gap) - gap / 2} r={gap * 1.2} fill={C.accent}/>)}</g>
      </g>
    );
    note = reveal > 0.5 ? "the gaps between the squares are plain: the grey spots are only in your eyes" : "do you see grey spots where the lines cross?";
  }
  return <g opacity={clamp(T.t / 10)}>{body}<Txt x={B.cx} y={B.y1 - B.fs * 0.5} size={B.fs * 0.9} color={C.muted}>{note}</Txt></g>;
};

export const MIND = {binarycards: BinaryCards, illusion: Illusion};
