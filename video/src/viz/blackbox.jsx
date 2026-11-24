// "blackbox": the picture of every "how does it work inside?" video. A closed box takes things in and gives things out; on
// the key word an x-ray scan sweeps down it, the shell turns transparent, and the machinery inside is seen working: each
// stage a card, the data a stream of dots that changes colour as the stages change it. Any topic: an engine, a compiler, a
// kidney, a language model, a phone. (The stages come from the script; the motion is the same everywhere.)
import {React, box, clamp, ease, glide, lerp, pop, pal, timing, Txt, Card, C, alpha} from "./kit";

export const BlackBox = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.inside.length;
  const bw = B.W * (vertical ? 0.62 : 0.5), bh = B.H * (vertical ? 0.64 : 0.74), bx = B.cx - bw / 2, by = B.cy - bh / 2 + B.fs * 0.4;
  const scan = clamp(T.k / 34), open = ease(scan), cy = by + bh / 2;
  const ins = e.inputs, outs = e.outputs, pillW = B.W * 0.17, pillH = B.fs * 1.7;
  const slot = (k, m) => by + bh * ((k + 1) / (m + 1));
  // the stages, in a row (wide) or a column (vertical), inside the box
  const sw = vertical ? bw * 0.78 : (bw * 0.86) / n - 18, sh = vertical ? (bh * 0.8) / n - 14 : bh * 0.5;
  const sx = (i) => (vertical ? B.cx - sw / 2 : bx + bw * 0.07 + i * (sw + 18)), sy = (i) => (vertical ? by + bh * 0.1 + i * (sh + 14) : cy - sh / 2);
  const mid = (i) => (vertical ? [sx(i) + sw / 2, sy(i) + sh / 2] : [sx(i) + sw / 2, cy]);
  const route = [[bx, cy], ...Array.from({length: n}, (_, i) => mid(i)), [bx + bw, cy]];
  const at = (p) => {                                         // a point a share p of the way along the route
    const q = clamp(p) * (route.length - 1), i = Math.min(route.length - 2, Math.floor(q)), u = q - i;
    return [lerp(route[i][0], route[i + 1][0], u), lerp(route[i][1], route[i + 1][1], u), q];
  };
  const tint = (q) => { const i = Math.min(3, Math.floor((q / (route.length - 1)) * 4)); return [pal(e, 1), pal(e, 2), pal(e, 3), pal(e, 0)][i]; };
  const flowing = scan > 0.4;
  return (
    <g opacity={clamp(T.t / 10)}>
      {ins.map((t, k) => {
        const p = pop(T.t - 6 - k * 6), x = bx - pillW - B.W * 0.06 + (1 - p) * -40 + (flowing ? Math.min(0.9, ((T.k - 12 - k * 9) % 70) / 70) * B.W * 0.06 : 0);
        return (
          <g key={k} opacity={clamp(p * 2)}>
            <rect x={bx - pillW - B.W * 0.07} y={slot(k, ins.length) - pillH / 2} width={pillW} height={pillH} rx={pillH / 2} fill={alpha(pal(e, 1), 0.2)} stroke={pal(e, 1)} strokeWidth={3}/>
            <Txt x={bx - pillW / 2 - B.W * 0.07} y={slot(k, ins.length)} size={B.fs * 0.8} color={C.text}>{t}</Txt>
            <path d={`M${bx - B.W * 0.06 + 6},${slot(k, ins.length)} L${bx - 6},${slot(k, ins.length)}`} stroke={pal(e, 1)} strokeWidth={5} markerEnd="" strokeLinecap="round"/>
            <path d={`M${bx - 6},${slot(k, ins.length)} l-16,-10 m16,10 l-16,10`} stroke={pal(e, 1)} strokeWidth={5} fill="none" strokeLinecap="round"/>
          </g>
        );
      })}
      {outs.map((t, k) => {
        const p = flowing ? pop(T.k - 30 - k * 8) : 0, x = bx + bw + B.W * 0.01;
        return (
          <g key={k} opacity={clamp(p * 2)}>
            <path d={`M${x},${slot(k, outs.length)} L${x + B.W * 0.05},${slot(k, outs.length)} m-14,-10 l14,10 l-14,10`} stroke={pal(e, 0)} strokeWidth={5} fill="none" strokeLinecap="round"/>
            <rect x={x + B.W * 0.06} y={slot(k, outs.length) - pillH / 2} width={pillW} height={pillH} rx={pillH / 2} fill={alpha(pal(e, 0), 0.2)} stroke={pal(e, 0)} strokeWidth={3}/>
            <Txt x={x + B.W * 0.06 + pillW / 2} y={slot(k, outs.length)} size={B.fs * 0.8} color={C.text}>{t}</Txt>
          </g>
        );
      })}
      <rect x={bx} y={by} width={bw} height={bh} rx={22} fill={alpha(C.panel, 0.95)} stroke={C.muted} strokeWidth={5}/>
      {/* the machinery inside, seen once the scan has passed */}
      {e.inside.map((name, i) => {
        const seen = clamp((scan * 1.3 - (i / n) * 0.6) * 2);
        return seen > 0 ? <g key={i} opacity={seen}><Card x={sx(i)} y={sy(i)} w={sw} h={sh} label={name} color={tint((i + 1) / (n + 1) * (route.length - 1))} p={seen} fs={Math.min(B.fs * 0.95, sh * 0.34)} lit={0.25}/></g> : null;
      })}
      {flowing && Array.from({length: 14}, (_, d) => {
        const p = (((T.k * 0.011 + d / 14) % 1) + 1) % 1, [x, y, q] = at(p);
        return <circle key={d} cx={x} cy={y + (d % 2 ? 7 : -7)} r={7} fill={tint(q)} opacity={0.9} style={{filter: `drop-shadow(0 0 8px ${alpha(tint(q), 0.8)})`}}/>;
      })}
      {/* the shell: a closed dark face with a question mark, wiped away from the top by the x-ray scan */}
      <g clipPath={`url(#bbclip)`}>
        <defs><clipPath id="bbclip"><rect x={bx} y={by + bh * open} width={bw} height={Math.max(0, bh * (1 - open))}/></clipPath></defs>
        <rect x={bx} y={by} width={bw} height={bh} rx={22} fill={alpha(C.bg, 0.97)} stroke={C.muted} strokeWidth={5}/>
        <Txt x={B.cx} y={cy} size={Math.min(bh * 0.5, B.fs * 5)} color={alpha(C.muted, 0.7)} weight={900}>?</Txt>
      </g>
      {scan > 0 && scan < 1 && <g>
        <line x1={bx - 14} y1={by + bh * open} x2={bx + bw + 14} y2={by + bh * open} stroke={C.accent} strokeWidth={6} style={{filter: `drop-shadow(0 0 14px ${C.accent})`}}/>
        <rect x={bx} y={by + bh * open - 40} width={bw} height={40} fill={alpha(C.accent, 0.18)}/>
      </g>}
      <Txt x={B.cx} y={by - B.fs * 1.1} size={B.fs * 1.1} color={C.text} weight={900}>{e.name || (scan > 0.5 ? "inside the box" : "the black box")}</Txt>
      <Txt x={B.cx} y={by + bh + B.fs * 1.1} size={B.fs * 0.8} color={C.muted}>{flowing ? "what happens to the data inside" : "what goes in, and what comes out"}</Txt>
    </g>
  );
};

export const BLACKBOX = {blackbox: BlackBox};
