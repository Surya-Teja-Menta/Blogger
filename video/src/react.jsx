// Reaction stickers: on a few real punchlines (blogwriter/video.py express + punchlines) a small animated face pops up at
// the right edge, in the video's own colours: a glass disc, a face drawn in a few strokes, and one gesture. It lasts
// two seconds and is a pure function of the frame, like everything else.
import React from "react";
import {useCurrentFrame, useVideoConfig} from "remotion";
import {clamp, ease} from "./fx";
import {pop} from "./motion";
import {C, alpha} from "./theme";

const LIFE = 64;          // frames on screen

// every face is drawn in a 100 x 100 box; t runs 0..1 through the gesture
const eyes = (dx = 0, dy = 0, lid = 0) => (
  <g>
    {[38, 62].map((x) => <g key={x}>
      <ellipse cx={x} cy={44} rx={7} ry={Math.max(1.5, 8 * (1 - lid))} fill="#fbfaf7" stroke={C.text} strokeWidth={1.6}/>
      <circle cx={x + dx} cy={45 + dy} r={3.2} fill="#1b1b1f"/>
    </g>)}
  </g>
);
const mouth = (d) => <path d={d} fill="none" stroke={C.text} strokeWidth={4} strokeLinecap="round"/>;
const hand = (x, y, r = 0, s = 1) => (
  <g transform={`translate(${x},${y}) rotate(${r}) scale(${s})`}>
    {/* a mitten: palm and a thumb at the side (no single finger that could read as a gesture) */}
    <ellipse cx={-11} cy={2} rx={5} ry={9} transform="rotate(-25 -11 2)" fill={C.accent} stroke={C.bg} strokeWidth={2.5}/>
    <rect x={-11} y={-14} width={24} height={28} rx={11} fill={C.accent} stroke={C.bg} strokeWidth={2.5}/>
  </g>
);

const FACES = {
  sideeye: (t) => <>{eyes(-3.5 * ease(clamp(t * 3)), 0, 0.35)}{mouth("M38 70 L62 70")}</>,
  eyebrow: (t) => {
    const up = ease(clamp(t * 3));
    return <>{eyes(0, 0)}
      <path d={`M30 ${31 - 7 * up} Q38 ${26 - 9 * up} 46 ${31 - 7 * up}`} fill="none" stroke={C.text} strokeWidth={4} strokeLinecap="round"/>
      <path d="M54 31 L70 31" stroke={C.text} strokeWidth={4} strokeLinecap="round"/>
      <circle cx={50} cy={70} r={4 + 2 * up} fill="none" stroke={C.text} strokeWidth={4}/></>;
  },
  facepalm: (t) => {
    const k = ease(clamp(t * 2.5));
    return <>{eyes(0, 0, 0.6)}{mouth("M40 70 Q50 65 60 70")}{hand(92 - 42 * k, 74 - 30 * k, 60 - 60 * k, 1.7)}</>;
  },
  shrug: (t) => {
    const k = Math.sin(clamp(t * 1.4) * Math.PI);
    return <>{eyes(0, -1, 0.2)}{mouth("M38 70 Q50 74 62 70")}{hand(10, 74 - 16 * k, -20)}{hand(90, 74 - 16 * k, 20)}</>;
  },
  mindblown: (t) => {
    const k = ease(clamp(t * 2));
    return <>{eyes(0, 0)}<circle cx={50} cy={70} r={6} fill="none" stroke={C.text} strokeWidth={4}/>
      {Array.from({length: 7}, (_, j) => {
        const a = -Math.PI * (0.15 + 0.7 * (j / 6)), r0 = 30, r1 = 30 + 26 * k;
        return <line key={j} x1={50 + Math.cos(a) * r0} y1={42 + Math.sin(a) * r0} x2={50 + Math.cos(a) * r1} y2={42 + Math.sin(a) * r1}
                     stroke={j % 2 ? C.hot : C.accent} strokeWidth={4} strokeLinecap="round" opacity={1 - 0.4 * k}/>;
      })}</>;
  },
  sweat: (t) => {
    const k = clamp(t * 1.6);
    return <>{eyes(0, 1, 0.1)}{mouth("M38 71 Q44 66 50 71 Q56 76 62 71")}
      <path d={`M78 ${28 + 30 * k} q-6 9 0 13 q6 -4 0 -13`} fill={C.cool} opacity={1 - 0.6 * k}/></>;
  },
  eyeroll: (t) => {
    const a = -Math.PI / 2 + clamp(t * 1.4) * Math.PI * 1.6;
    return <>{eyes(3.5 * Math.cos(a), 3.5 * Math.sin(a))}{mouth("M40 70 L60 70")}</>;
  },
  slowclap: (t) => {
    const k = (1 - Math.cos(clamp(t) * Math.PI * 6)) / 2;           // three slow claps
    return <>{eyes(0, 0, 0.45)}{mouth("M40 70 L60 70")}{hand(36 + 10 * (1 - k), 92, 15)}{hand(64 - 10 * (1 - k), 92, -15)}</>;
  },
};

export const Reactions = ({items = [], vertical}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const live = (items || []).find((r) => frame >= r.at && frame < r.at + LIFE && FACES[r.kind]);
  if (!live || C.clean) return null;
  const t = frame - live.at;
  const size = vertical ? 190 : 150;
  const inP = pop(t), out = ease(clamp((t - (LIFE - 12)) / 12));
  const x = width - size - (vertical ? 50 : 34), y = height * (vertical ? 0.4 : 0.5) - size / 2;
  return (
    <div style={{position: "absolute", left: x, top: y, width: size, height: size,
                 transform: `scale(${(0.4 + 0.6 * inP) * (1 - 0.3 * out)}) rotate(${(1 - inP) * -18}deg)`, opacity: clamp(inP * 2) * (1 - out)}}>
      <svg viewBox="0 0 100 100" width={size} height={size} style={{overflow: "visible", filter: `drop-shadow(0 8px 24px ${alpha(C.bg, 0.6)})`}}>
        <circle cx={50} cy={50} r={46} fill={alpha(C.panel, 0.92)} stroke={C.accent} strokeWidth={3}/>
        {FACES[live.kind](clamp((t - 6) / (LIFE - 18)))}
      </svg>
    </div>
  );
};

export const REACTION_KINDS = Object.keys(FACES);
