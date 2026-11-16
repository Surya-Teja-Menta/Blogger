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
//   hud      a thin instrument layer in the accent over the whole video: a camera viewfinder (corner brackets),
//            telemetry (a scrolling ruler), a focus reticle that locks on at the punch-ins, or none
import React from "react";
import {AbsoluteFill, random, useCurrentFrame, useVideoConfig} from "remotion";
import {C, FONT, SERIES, alpha} from "./theme";
import {Shape} from "./gen";

const DEFAULT = {decor: "shapes", kicker: "all", outro: "side", flow: "line", capAlign: "center", logo: "tl", progress: "top",
  hub: "ring", spot: "left", versus: "diag", stack: "center", quote: "left", list: "stack", title: "left", hook: "center", hud: "none"};
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

// ---- hud: the instrument layer ----------------------------------------------------------------------------------------
// Drawn over every shot and under the badge and captions; the layout audit skips it (it is chrome, not content).

export const Hud = ({scenes, starts, vertical}) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const mode = layoutOf().hud;
  if (mode === "none") return null;
  const inset = vertical ? 24 : 28, arm = vertical ? 64 : 92, col = alpha(C.accent, 0.75);
  const draw = ease((frame - 2) / 22);
  let body = null;
  if (mode === "viewfinder") {
    const mid = [[width / 2, inset], [width / 2, height - inset], [inset, height / 2], [width - inset, height / 2]];
    body = (
      <>
        <svg width={width} height={height} style={{position: "absolute"}}>
          {[[0, 0, 1, 1], [1, 0, -1, 1], [0, 1, 1, -1], [1, 1, -1, -1]].map(([cx, cy, dx, dy], k) => {
            const x = cx ? width - inset : inset, y = cy ? height - inset : inset;
            return <path key={k} d={`M${x},${y + dy * arm * draw} L${x},${y} L${x + dx * arm * draw},${y}`} fill="none" stroke={col}
                         strokeWidth={4} strokeLinecap="square"/>;
          })}
          {mid.map(([x, y], k) => <path key={k} d={k < 2 ? `M${x - 9},${y} L${x + 9},${y}` : `M${x},${y - 9} L${x},${y + 9}`}
                                        stroke={alpha(C.accent, 0.4)} strokeWidth={2} opacity={draw}/>)}
        </svg>
      </>
    );
  } else if (mode === "telemetry") {
    const x = width - inset - 8, y0 = height * 0.3, y1 = height * 0.7, off = (frame * 0.7) % 20;
    body = (
      <>
        <svg width={width} height={height} style={{position: "absolute"}} opacity={draw}>
          <line x1={x} y1={y0} x2={x} y2={y1} stroke={alpha(C.accent, 0.35)} strokeWidth={2}/>
          {Array.from({length: Math.floor((y1 - y0) / 20)}, (_, k) => {
            const y = y0 + k * 20 + off, major = (k + Math.floor(frame * 0.7 / 20)) % 5 === 0;
            return y < y1 ? <line key={k} x1={x - (major ? 22 : 11)} y1={y} x2={x} y2={y} stroke={alpha(C.accent, major ? 0.6 : 0.3)} strokeWidth={2}/> : null;
          })}
          <path d={`M${x - 34},${(y0 + y1) / 2} l14,-9 l0,18 z`} fill={alpha(C.accent, 0.8)}/>
        </svg>
      </>
    );
  } else if (mode === "reticle") {
    // a focus reticle that snaps onto the subject on each punch-in (camera.py plans the moment)
    const hits = scenes.map((s, k) => (s.cam && s.cam.punch != null ? {at: starts[k] + s.cam.punch, fx: s.cam.fx, fy: s.cam.fy} : null))
      .filter((h) => h && frame >= h.at - 4 && frame < h.at + 30);
    body = hits.map((h, k) => {
      const t = frame - h.at, snap = ease((t + 4) / 8), fade = 1 - ease((t - 12) / 16), r = (vertical ? 84 : 110) * (1.7 - 0.7 * snap);
      const cx = h.fx * width, cy = h.fy * height;
      return (
        <svg key={k} width={width} height={height} style={{position: "absolute"}} opacity={fade}>
          <circle cx={cx} cy={cy} r={r} fill="none" stroke={col} strokeWidth={4} strokeDasharray="12 14"/>
          {[0, 90, 180, 270].map((a) => <line key={a} x1={cx + (r + 8) * Math.cos((a * Math.PI) / 180)} y1={cy + (r + 8) * Math.sin((a * Math.PI) / 180)}
                                              x2={cx + (r + 26) * Math.cos((a * Math.PI) / 180)} y2={cy + (r + 26) * Math.sin((a * Math.PI) / 180)}
                                              stroke={alpha(C.accent, 0.9)} strokeWidth={3}/>)}
        </svg>
      );
    });
  }
  return <AbsoluteFill data-audit="skip" style={{pointerEvents: "none"}}>{body}</AbsoluteFill>;
};
