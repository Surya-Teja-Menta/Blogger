// Direction: what turns a built-up slide into a taught shot.
//  - Focus, a director's camera. Each piece is given the frame its word is spoken (at) and its place on screen (box).
//    The camera pushes in on the piece being introduced, moves on with the build, and pulls back to show the whole
//    picture before the cut. The headline gives way while the camera is in close.
//  - Pen, a teacher's pen (Rough.js): a hand-drawn circle or underline, drawn on stroke by stroke, around the piece
//    the voice is pointing at.
// Both are pure functions of the frame, so every render of a frame is identical.
import React, {useMemo} from "react";
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from "remotion";
import rough from "roughjs";
import {clamp} from "./fx";
import {C, alpha} from "./theme";

const MOVE = 26;            // frames a camera move takes
const DWELL = 42;           // pieces introduced closer together than this are framed together
const ZOOM = 1.38;          // the closest the camera comes

const inOut = (t) => {
  const x = clamp(t);
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
};
const union = (a, b) => [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])];

// the camera's stops for one shot: pieces that open the shot are the stage (no move), pieces introduced close
// together are framed together, and the camera always pulls back to the whole picture before the cut
export const focusPlan = (keys, {width, height, frames, start = 20}) => {
  const tail = Math.min(50, frames * 0.16);
  const live = keys.filter((k) => k && k.box && k.box.every(Number.isFinite) && k.at >= start && k.at < frames - tail - 14)
    .sort((a, b) => a.at - b.at);
  const groups = [];
  for (const k of live) {
    const last = groups[groups.length - 1];
    if (last && k.at - last.at < DWELL) last.box = union(last.box, k.box);
    else groups.push({at: k.at, box: [...k.box]});
  }
  const stops = groups.map(({at, box}) => {
    const bw = Math.max(box[2] - box[0], width * 0.2), bh = Math.max(box[3] - box[1], height * 0.2);
    // even a subject too big to frame closer gets a gentle push toward it; only one that fills the frame does not
    const fills = bw > width * 0.8 && bh > height * 0.7;
    const z = Math.max(1.12, Math.min(ZOOM, (width * 0.62) / bw, (height * 0.6) / bh));
    return fills ? {at, x: width / 2, y: height / 2, z: 1} : {at, x: (box[0] + box[2]) / 2, y: (box[1] + box[3]) / 2, z};
  });
  if (stops.length) stops.push({at: Math.max(stops[stops.length - 1].at + MOVE, frames - tail), x: width / 2, y: height / 2, z: 1});
  return stops;
};

// where the camera is now: each stop eases in from wherever the camera was when it began
export const useFocus = (stops) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  let v = {x: width / 2, y: height / 2, z: 1};
  for (const s of stops) {
    if (frame < s.at) break;
    const q = inOut((frame - s.at) / MOVE);
    v = {x: v.x + (s.x - v.x) * q, y: v.y + (s.y - v.y) * q, z: v.z + (s.z - v.z) * q};
  }
  return v;
};

// the content as the camera sees it: the subject is brought toward the middle of the frame (a little above it,
// clear of the captions) as the camera closes in
export const Focus = ({view, children}) => {
  const {width, height} = useVideoConfig();
  const {x, y, z} = view;
  const pull = clamp((z - 1) / 0.25);
  const tx = x * (1 - z) + (width / 2 - x) * pull * 0.85;
  const ty = y * (1 - z) + (height * 0.5 - y) * pull * 0.85;
  return (
    <AbsoluteFill style={{transformOrigin: "0 0", transform: `translate(${tx}px, ${ty}px) scale(${z})`}}>
      {children}
    </AbsoluteFill>
  );
};

// the headline steps aside while the camera is in close, and comes back with the whole picture
export const headlineShown = (view) => 1 - clamp((view.z - 1.03) / 0.1);

const gen = rough.generator();

// a hand-drawn mark around box [x0, y0, x1, y1], drawn on from `at`: a loose double circle (or an underline for a
// long flat piece), or as asked: "underline", "box", "cross". The strokes are the same in every frame (seeded).
export const Pen = ({box, at, color, seed = 1, kind}) => {
  const frame = useCurrentFrame();
  const shape = kind || ((box[2] - box[0]) > 4.5 * (box[3] - box[1]) ? "underline" : "circle");
  const paths = useMemo(() => {
    const opt = {seed: 1 + (seed % 9973), roughness: 1.4, bowing: 1.2, strokeWidth: 5, stroke: "x"};
    const w = box[2] - box[0], h = box[3] - box[1];
    const ds = shape === "underline" ? [gen.line(box[0] - 10, box[3] + 14, box[2] + 16, box[3] + 10, opt)]
      : shape === "box" ? [gen.rectangle(box[0] - 14, box[1] - 12, w + 28, h + 24, opt)]
        : shape === "cross" ? [gen.line(box[0] - 8, box[1] - 8, box[2] + 8, box[3] + 8, opt), gen.line(box[2] + 8, box[1] - 8, box[0] - 8, box[3] + 8, opt)]
          : [gen.ellipse((box[0] + box[2]) / 2, (box[1] + box[3]) / 2, w * 1.3 + 40, h * 1.35 + 34, opt)];
    return ds.flatMap((d) => gen.toPaths(d).map((p) => p.d));
  }, [box.join(","), seed, shape]);
  if (frame < at) return null;
  const draw = (k) => inOut((frame - at - k * 9) / 16);         // the second pass follows the first, like a quick hand
  const col = color || C.hot;
  return (
    <g style={{filter: `drop-shadow(0 0 6px ${alpha(col, 0.45)})`}}>
      {paths.map((d, k) => (
        <path key={k} d={d} fill="none" stroke={col} strokeWidth={k ? 3.5 : 5} strokeLinecap="round" strokeLinejoin="round"
              pathLength={1} strokeDasharray={1} strokeDashoffset={1 - draw(k)} opacity={k ? 0.75 : 1}/>
      ))}
    </g>
  );
};
