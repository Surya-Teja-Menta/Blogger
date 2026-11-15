// The skeleton of a video: where its parts sit, not what colour they are. blogwriter/skeleton.py draws a layout plan
// for every video (theme.layout) and no two videos in a row share a choice, so the layout, and not only the skin,
// changes from video to video:
//   decor    what decorates the big-type shots (drifting shapes, rules, corner brackets, dots, a band, a frame, nothing)
//   kicker   the small label above a headline: on every shot, only where a new part begins, or never
//   outro    the end card: cover left, cover right, centred, or a ribbon
//   flow     how a chain of steps runs: a line, a stair down, a zigzag, a rise
//   capAlign where the captions of a wide video sit: centred or at the left, under the headline
//   logo     which top corner the channel badge sits in
//   progress the thin progress line at the top or at the bottom
//   hub      the players round a centre: a ring, or a fan beside a centre at the left or right
//   spot     the spotlight's centre at the left or the right
//   versus   the two sides split on a diagonal or straight
//   stack    the stacked cards centred, at the left or at the right
//   quote    the quote under its mark, centred, or beside a big mark
//   list     the list as a column, staggered, or in two columns
//   title    the headline at the left, the centre or the right
//   hook     the words of a big-type shot: centred, at the left, or one to a line
import React from "react";
import {AbsoluteFill, random, useCurrentFrame, useVideoConfig} from "remotion";
import {C, SERIES, alpha} from "./theme";
import {Shape} from "./gen";

const DEFAULT = {decor: "shapes", kicker: "all", outro: "side", flow: "line", capAlign: "center", logo: "tl", progress: "top",
  hub: "ring", spot: "left", versus: "diag", stack: "center", quote: "left", list: "stack", title: "left", hook: "center"};
export const layoutOf = () => ({...DEFAULT, ...(C.layout || {})});

// does this shot show its label? (a shot with `partStart` opens a new part of the lesson)
export const kickerShown = (s) => {
  const mode = layoutOf().kicker;
  return !!s.kicker && (mode === "all" || (mode === "parts" && !!s.partStart));
};
export const kickerPolicy = (s) => (s.kicker && !kickerShown(s) ? {...s, kicker: ""} : s);

const ease = (t) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);

// the places a decoration may sit: around the edges, away from the headline in the middle
const SLOTS = [[0.12, 0.2], [0.88, 0.22], [0.14, 0.8], [0.86, 0.8], [0.05, 0.5], [0.95, 0.5], [0.5, 0.08], [0.5, 0.92]];
const SHAPE_KINDS = ["circle", "ring", "square", "triangle", "plus", "hex", "diamond", "star", "chevron", "arc", "squiggle", "cross", "pill"];

export const Decor = ({i = 0, vertical = false}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const mode = layoutOf().decor;
  const r = (tag, k = 0) => random(`${(C.fx || {}).seed || ""}${i}${mode}${tag}${k}`);
  const col = (k) => SERIES[k % SERIES.length];
  if (mode === "none") return null;
  if (mode === "rules") {
    const n = 1 + Math.floor(r("n") * 2.99);
    return (
      <svg width={width} height={height} style={{position: "absolute"}}>
        {Array.from({length: n}, (_, k) => {
          const p = ease((frame - 8 - k * 7) / 24), fromRight = r("s", k) > 0.5, len = width * (0.25 + 0.3 * r("l", k));
          const y = height * (k % 2 ? 0.7 + 0.18 * r("y", k) : 0.12 + 0.2 * r("y", k));
          return <line key={k} x1={fromRight ? width : 0} y1={y} x2={fromRight ? width - len * p : len * p} y2={y}
                       stroke={col(k)} strokeWidth={4 + 4 * r("w", k)} strokeLinecap="round"/>;
        })}
      </svg>
    );
  }
  if (mode === "brackets") {
    const arm = (vertical ? 90 : 120) + 50 * r("a"), inset = vertical ? 50 : 60;
    const corners = [[0, 0, 1, 1], [1, 0, -1, 1], [0, 1, 1, -1], [1, 1, -1, -1]].filter((_, k) => k < 2 || r("c", k) > 0.4);
    return (
      <svg width={width} height={height} style={{position: "absolute"}}>
        {corners.map(([cx, cy, dx, dy], k) => {
          const p = ease((frame - 4 - k * 6) / 20), x = cx ? width - inset : inset, y = cy ? height - inset : inset;
          return <path key={k} d={`M${x},${y + dy * arm * p} L${x},${y} L${x + dx * arm * p},${y}`} fill="none" stroke={col(k)}
                       strokeWidth={6} strokeLinecap="square" opacity={0.7}/>;
        })}
      </svg>
    );
  }
  if (mode === "dots") {
    const corners = [[0.07, 0.12], [0.93, 0.88], [0.07, 0.88], [0.93, 0.12]];
    const picks = [Math.floor(r("c") * 4), (Math.floor(r("c") * 4) + 2) % 4].slice(0, r("two") > 0.4 ? 2 : 1);
    return (
      <svg width={width} height={height} style={{position: "absolute"}}>
        {picks.flatMap((c, q) => Array.from({length: 30}, (_, k) => {
          const gx = k % 6, gy = Math.floor(k / 6), p = ease((frame - 6 - (gx + gy) * 2 - q * 10) / 16);
          const x = width * corners[c][0] + (c % 2 ? -1 : 1) * gx * 26, y = height * corners[c][1] + (c > 1 ? -1 : 1) * gy * 26;
          return <circle key={`${q}_${k}`} cx={x} cy={y} r={5 * p} fill={col(q)} opacity={0.45}/>;
        }))}
      </svg>
    );
  }
  if (mode === "band") {
    const tilt = -14 + 28 * r("t"), p = ease((frame - 2) / 24);
    return (
      <AbsoluteFill style={{overflow: "hidden"}}>
        <div style={{position: "absolute", left: "-10%", right: "-10%", top: `${vertical ? 36 : 38 + 6 * r("y")}%`, height: vertical ? 300 : 220,
                     background: `linear-gradient(90deg, transparent, ${alpha(C.accent, 0.1)} 20%, ${alpha(C.accent, 0.1)} 80%, transparent)`,
                     borderTop: `3px solid ${alpha(C.accent, 0.35)}`, borderBottom: `3px solid ${alpha(C.cool, 0.3)}`,
                     transform: `rotate(${tilt}deg) scaleX(${p})`}}/>
      </AbsoluteFill>
    );
  }
  if (mode === "frame") {
    const inset = vertical ? 44 : 40, p = ease((frame - 2) / 26);
    return (
      <svg width={width} height={height} style={{position: "absolute"}}>
        <rect x={inset} y={inset} width={width - 2 * inset} height={height - 2 * inset} rx={r("rx") * 30} fill="none" stroke={alpha(C.accent, 0.45)}
              strokeWidth={3} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p}/>
        {[0, 1, 2, 3].map((k) => <rect key={k} x={(k % 2 ? width - inset : inset) - 8} y={(k > 1 ? height - inset : inset) - 8} width={16} height={16}
                                       fill={col(k)} opacity={p * 0.8}/>)}
      </svg>
    );
  }
  // shapes: three or four outlines in seeded places, of seeded kinds, sizes and turns
  const n = 3 + Math.floor(r("n") * 1.99);
  const order = SLOTS.map((s, k) => [r("o", k), s]).sort((a, b) => a[0] - b[0]).slice(0, n).map((x) => x[1]);
  return (
    <AbsoluteFill>
      {order.map(([sx, sy], k) => {
        const p = ease((frame - 4 - k * 5) / 20), s = (vertical ? 70 : 90) + 120 * r("s", k);
        const kind = SHAPE_KINDS[Math.floor(r("k", k) * SHAPE_KINDS.length)];
        return (
          <div key={k} style={{position: "absolute", left: width * sx, top: height * sy, opacity: 0.55 * p, transform: `scale(${p})`}}>
            <Shape shape={kind} s={s} col={col(k + 1)} stroke rot={frame * (0.3 + 0.5 * r("w", k)) * (k % 2 ? 1 : -1) + 360 * r("r", k)}/>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
