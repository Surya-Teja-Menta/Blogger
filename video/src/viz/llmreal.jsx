// "llmreal": a small real language model (GPT-2, computed in the make job by blogwriter/llmprobe.py) reading a sentence: the
// attention one of its heads really paid, word by word, and the chances it really gave to the next word. The data arrives
// inside the picture's fields (tokens, attn, next); this file only draws it.
import {React, box, clamp, ease, pal, pop, timing, Txt, C, alpha} from "./kit";

export const LlmReal = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), toks = e.tokens, n = toks.length, A = e.attn;
  const per = Math.max(9, Math.min(40, ((end - (e.at ?? 0) - 90) * 0.55) / n)), focus = Math.min(n - 1, Math.floor(Math.max(0, T.t - 20) / per)), nextOn = T.t - 20 - n * per;
  const rowY = vertical ? B.y0 + B.H * 0.16 : B.y0 + B.H * 0.3, x0 = B.x0 + B.W * (vertical ? 0.05 : 0.05), tw = (vertical ? B.W * 0.9 : B.W * 0.9) / n;
  const cx = (i) => x0 + (i + 0.5) * tw;
  const m = Math.min(vertical ? B.W * 0.5 : B.W * 0.3, B.H * (vertical ? 0.36 : 0.4)), mx = vertical ? B.x0 + B.W * 0.06 : B.x0 + B.W * 0.08, my = vertical ? B.y0 + B.H * 0.34 : rowY + B.H * 0.17, cell = m / n;
  const nx = vertical ? B.x0 + B.W * 0.62 : B.x0 + B.W * 0.55, ny = vertical ? B.y0 + B.H * 0.38 : my + B.fs * 0.6, nw = vertical ? B.W * 0.34 : B.W * 0.36;
  const word = (t) => String(t).replace(/^\s+/, "") || "·";
  return (
    <g opacity={clamp(T.t / 10)}>
      {toks.map((t, i) => {
        const w = i === focus ? 1 : 0.55;
        return <g key={i} opacity={pop(T.t - 6 - i * 3)}>
          <rect x={cx(i) - tw * 0.46} y={rowY - B.fs * 0.8} width={tw * 0.92} height={B.fs * 1.6} rx={10} fill={alpha(i === focus ? C.accent : C.panel, i === focus ? 0.35 : 0.9)} stroke={i === focus ? C.accent : alpha(C.muted, 0.7)} strokeWidth={i === focus ? 5 : 3}/>
          <Txt x={cx(i)} y={rowY} size={Math.min(B.fs * 0.95, tw * 0.62)} color={C.text} weight={i === focus ? 900 : 700}>{word(t)}</Txt>
        </g>;
      })}
      {A[focus].slice(0, focus + 1).map((w, j) => (j === focus ? null :
        <path key={j} d={`M${cx(focus)},${rowY - B.fs * 0.9} Q${(cx(focus) + cx(j)) / 2},${rowY - B.fs * (2.2 + Math.abs(focus - j) * 0.7)} ${cx(j)},${rowY - B.fs * 0.9}`} fill="none" stroke={pal(e, 2)} strokeWidth={2 + 18 * w} strokeLinecap="round" opacity={0.25 + 0.7 * clamp(w * 2.5)}/>))}
      <Txt x={mx} y={my - B.fs * 0.9} size={B.fs * 0.8} anchor="start" color={C.muted}>who looks at whom (each row: one word's attention)</Txt>
      {A.map((row, r) => row.map((w, c) => c <= r ? <rect key={`${r}-${c}`} x={mx + c * cell} y={my + r * cell} width={cell - 2} height={cell - 2} rx={3} fill={pal(e, 2)} opacity={(r <= focus ? 0.12 + 0.88 * clamp(w * 1.6) : 0.05)}/> : null))}
      {A.map((_, r) => <rect key={r} x={mx - 3} y={my + r * cell - 3} width={m + 6} height={cell + 4} rx={4} fill="none" stroke={r === focus ? C.accent : "none"} strokeWidth={3}/>)}
      <g opacity={clamp(nextOn / 20)}>
        <Txt x={nx} y={ny - B.fs * 1.3} size={B.fs * 0.85} anchor="start" color={C.muted}>the model's chances for the next word</Txt>
        {e.next.slice(0, 4).map(([w, p], k) => (
          <g key={k}>
            <rect x={nx} y={ny + k * B.fs * 1.7} width={nw * clamp(p / (e.next[0][1] * 1.1)) * ease(clamp(nextOn / 30))} height={B.fs * 1.2} rx={7} fill={k === 0 ? C.accent : alpha(C.accent, 0.4)}/>
            <Txt x={nx + 10} y={ny + k * B.fs * 1.7 + B.fs * 0.6} size={B.fs * 0.85} anchor="start" color={C.text}>{word(w)}{e.show ? `  ${Math.round(p * 100)}%` : ""}</Txt>
          </g>))}
      </g>
      <Txt x={B.cx} y={B.y1 - B.fs * 0.2} size={B.fs * 0.75} color={C.muted}>{`a small real model (GPT-2): layer ${e.layer + 1}, head ${e.head + 1}`}</Txt>
    </g>
  );
};

export const LLMREAL = {llmreal: LlmReal};
