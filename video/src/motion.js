// The video's own motion feel: how every piece arrives (an anime.js easing curve the design picked for THIS
// video, with its overshoot and duration) and in what order a group of pieces appears (anime.js-style stagger:
// from the first, the last, the centre, the edges or at random). Everything is a pure function of the frame, so
// every render of a frame is identical (anime.js's own engine and timers are never used, only its curves).
import {cubicBezier, eases, spring} from "animejs/easings";
import {random} from "remotion";
import {C} from "./theme";

const DEFAULT = {ease: "spring", bounce: 0.3, frames: 20, from: "first", gap: 1.6};
const curves = {};

const motion = () => ({...DEFAULT, ...((C.fx || {}).motion || {})});

// the easing function (0 -> 1, may overshoot) for the current design
export const curve = () => {
  const m = motion();
  const b = Math.min(1, Math.max(0, m.bounce));
  const key = `${m.ease}|${b}`;
  if (!curves[key]) {
    curves[key] =
      m.ease === "outBack" ? eases.outBack(1 + 2 * b)
        : m.ease === "outElastic" ? eases.outElastic(1, 0.8 - 0.3 * b)        // period 0.5-0.8: lively, never violent
          : m.ease === "spring" ? spring({bounce: 0.1 + 0.5 * b, duration: 600}).ease
            : m.ease === "snap" ? cubicBezier(0.2, 0.9, 0.1, 1)
              : eases[m.ease] || eases.outExpo;
  }
  return curves[key];
};

// progress of a piece `t` frames after it starts arriving (0 before, 1 once settled); slow stretches it
export const pop = (t, slow = 1) => {
  const dur = Math.max(4, motion().frames * slow);
  if (!(t > 0)) return 0;
  if (t >= dur) return 1;
  return curve()(t / dur);
};

// a gentler, never-overshooting version for things that draw or slide rather than land
export const glide = (t, slow = 1) => {
  const dur = Math.max(4, motion().frames * 1.4 * slow);
  if (!(t > 0)) return 0;
  if (t >= dur) return 1;
  return eases.outCubic(t / dur);
};

// the delay (in frames) of piece k of n in a group, in the design's stagger order
export const delay = (k, n, seed = "s") => {
  const m = motion();
  const mid = (n - 1) / 2;
  const rank = m.from === "last" ? n - 1 - k
    : m.from === "center" ? Math.abs(k - mid)
      : m.from === "edges" ? mid - Math.abs(k - mid)
        : m.from === "random" ? random(`${seed}-${k}`) * (n - 1)
          : k;
  return rank * m.gap;
};
