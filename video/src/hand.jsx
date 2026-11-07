// Handwriting that writes itself, stroke by stroke, the way a hand does: single-line fonts from the EMS family (SIL
// Open Font License; converted from the hersheytext package, MIT), the technique of the Lemo-Opuscar chalkboard and
// whiteboard films (MIT, LemoLab). Each letter's pen path is drawn in its own order, one letter after another; the
// film look's line treatment (chalk grain, marker wobble, technical glow) applies to these strokes like any other.
import React from "react";
import {useCurrentFrame} from "remotion";
import tech from "./handfonts/tech.json";
import readability from "./handfonts/readability.json";
import felix from "./handfonts/felix.json";

const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));

export const HAND_FONTS = {tech, readability, felix};

const norm = (w) => w.toLowerCase().replace(/[^\p{L}\p{N}$%.]/gu, "");

// text written on from frame `at`, at `cps` letters a second; `size` is the font size in pixels (capitals are about
// two thirds of it); words in `highlight` are written in `accent`. Wraps at maxWidth.
export const HandText = ({text = "", size = 72, color, accent, highlight = "", at = 0, font = "tech", cps = 12,
                          maxWidth = 1600, align = "left", weight = 1, lineHeight = 1.3}) => {
  const frame = useCurrentFrame();
  const F = HAND_FONTS[font] || HAND_FONTS.tech;
  const k = size / F.upm;
  const adv = (ch) => (F.glyphs[ch] ? F.glyphs[ch][0] : F.upm * 0.45) * k;
  const space = adv(" ");
  const lines = [];
  let cur = [], w = 0;
  for (const word of String(text).split(/\s+/).filter(Boolean)) {
    const ww = [...word].reduce((a, c) => a + adv(c), 0);
    if (cur.length && w + space + ww > maxWidth) {
      lines.push({words: cur, w});
      cur = [];
      w = 0;
    }
    w += (cur.length ? space : 0) + ww;
    cur.push(word);
  }
  if (cur.length) lines.push({words: cur, w});
  const lh = size * lineHeight, widest = Math.max(1, ...lines.map((l) => l.w));
  const marks = new Set(String(highlight).toLowerCase().split(/\s+/).filter(Boolean).map(norm));
  const per = 30 / cps, stroke = Math.max(2.5, size * 0.07 * weight);
  const paths = [];
  let n = 0;
  lines.forEach((L, li) => {
    let x = align === "center" ? (widest - L.w) / 2 : align === "right" ? widest - L.w : 0;
    const base = li * lh + size * 0.82;
    L.words.forEach((word) => {
      const hot = marks.has(norm(word));
      for (const ch of word) {
        const g = F.glyphs[ch];
        const q = clamp((frame - at - n * per) / (per * 1.8));
        if (g && g[1] && q > 0) {
          paths.push(<path key={paths.length} d={g[1]} transform={`translate(${x.toFixed(1)},${base.toFixed(1)}) scale(${k},${-k})`}
                           fill="none" stroke={hot && accent ? accent : color} strokeWidth={stroke} vectorEffect="non-scaling-stroke"
                           strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1}
                           strokeDashoffset={1 - q}/>);
        }
        x += adv(ch);
        n += 1;
      }
      x += space;
      n += 1.5;                                   // the pen lifts between words
    });
  });
  return (
    <svg width={widest + stroke * 2} height={lh * lines.length + size * 0.3} style={{overflow: "visible", display: "block"}}>
      {paths}
    </svg>
  );
};
