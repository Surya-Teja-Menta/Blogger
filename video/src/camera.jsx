// The camera of a video, thought like an operator's. Before, every shot got the same slow push with a small sway. Now
// blogwriter/camera.py plans a move for each shot (theme-independent, seeded by the title) and this file performs it:
//   push      a dolly-in toward the subject            pull    a reveal: starts close, eases back out
//   truck     slides sideways past the subject          pedestal rises or sinks a little
//   arc       a slow curve: slide plus a slight roll    drift   a held camera: a breath of handheld sway
//   dutch     a rare tilted frame for a tense moment    rack    a push while the background pulls into focus
// and on the shot's key moment a quick punch-in (the crash zoom a cinematographer cuts on a beat), a focus point the
// scale grows from, and a camera that never stops: every move keeps a trace of organic sway. Text stays crisp: only
// small 2D moves, no perspective tilt. Without a plan (an old render) the shot gets the plain push it always had.
import React, {createContext, useContext} from "react";
import {noise2D} from "@remotion/noise";

export const CamContext = createContext(null);
export const useCam = () => useContext(CamContext);

const inOut = (t) => {
  const x = Math.min(1, Math.max(0, t));
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
};
const bump = (f) => (f < 0 ? 0 : f < 5 ? f / 5 : Math.exp(-(f - 5) / 9));          // up in 5 frames, then settling

// {transform, transformOrigin} of the camera at `frame` of a shot `duration` frames long
export const cameraStyle = ({cam, frame, duration, i, amount, width, height}) => {
  const plan = cam || {move: "push"};
  const t = frame / Math.max(1, duration), s = inOut(t), dir = plan.dir || (i % 2 ? 1 : -1);
  const a = amount * (plan.amount ?? 1);
  const sway = (key, period) => noise2D(`${key}-${i}`, frame / period, 0);
  let sc = 1, tx = 0, ty = 0, rot = 0;
  switch (plan.move) {
    case "pull": sc = 1 + 0.06 * a * (1 - s); break;
    case "truck": tx = dir * (s - 0.5) * 0.034 * width * a; sc = 1.012; break;
    case "pedestal": ty = dir * (s - 0.5) * 0.036 * height * a; sc = 1.012; break;
    case "arc": tx = dir * (s - 0.5) * 0.028 * width * a; rot = dir * (s - 0.5) * 1.2 * a; sc = 1.015 + 0.025 * a * s; break;
    case "dutch": rot = dir * (plan.dutch || 1) * inOut(t * 2.5); sc = 1.03 + 0.025 * s; break;
    case "rack": sc = 1 + 0.03 * a * s; break;
    case "drift": tx = sway("hx", 70) * 12 * a; ty = sway("hy", 80) * 8 * a; rot = sway("hr", 110) * 0.3 * a; sc = 1.012; break;
    default: sc = 1 + 0.06 * a * s;                                                   // push (and the old plain push)
  }
  tx += sway("tx", 160) * 5 * a;
  ty += sway("ty", 180) * 3 * a;
  if (plan.punch != null) sc *= 1 + 0.035 * a * bump(frame - plan.punch);
  return {transform: `translate(${tx}px, ${ty}px) rotate(${rot}deg) scale(${sc})`,
          transformOrigin: `${(plan.fx ?? 0.5) * 100}% ${(plan.fy ?? 0.45) * 100}%`};
};

// how far the backdrop is out of focus at `frame` (a "rack" shot pulls it sharp as the headline lands)
export const rackBlur = (cam, frame) => (cam && cam.move === "rack" ? 14 * (1 - inOut(frame / 40)) : 0);
