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
    case "crane": ty = -dir * (s - 0.5) * 0.05 * height * a; sc = 1.02 + 0.03 * a * s; break;        // rises past the subject
    case "tilt": ty = dir * (0.5 - s) * 0.045 * height * a; sc = 1.03; break;                           // looks down the picture
    case "glide": tx = dir * (s - 0.5) * 0.03 * width * a; ty = (s - 0.5) * 0.025 * height * a; sc = 1.02; break;   // a diagonal slide
    case "orbit": tx = Math.sin(s * Math.PI) * 0.02 * width * a * dir; ty = (1 - Math.cos(s * Math.PI)) * 0.012 * height * a;
      rot = dir * 0.6 * a * Math.sin(s * Math.PI); sc = 1.03; break;                                   // a slow half-circle
    case "spiral": rot = dir * (s - 0.5) * 1.6 * a; sc = 1 + 0.07 * a * s; break;                       // pushes in, turning
    case "whip": { const w = inOut(Math.min(1, t * 6)); tx = dir * (1 - w) * 0.08 * width * a; sc = 1.02 + 0.03 * s; break; }  // arrives fast, settles
    case "snap": sc = 1 + (t > 0.55 ? 0.08 * a * inOut((t - 0.55) * 5) : 0.005 * s); break;              // holds, then a hard zoom
    case "handheld": tx = sway("hhx", 26) * 16 * a; ty = sway("hhy", 31) * 11 * a; rot = sway("hhr", 40) * 0.45 * a; sc = 1.025; break;
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
