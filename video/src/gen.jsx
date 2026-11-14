// The generative visual language. blogwriter/design.py invents a recipe for every video (C.fx) and this file draws
// it: backdrop layers built from shapes, counts, sizes, motions and blurs; transitions built from a clip shape,
// an angle, blur and scale; the way words enter; film texture. The numbers are continuous, so no two videos share
// a look. Everything is seeded by the recipe, so each render of one video is identical.
import React from "react";
import {AbsoluteFill, Img, random, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import {C, alpha} from "./theme";

const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const ease = (t) => 1 - Math.pow(1 - clamp(t), 3);
const colour = (name) => ({accent: C.accent, hot: C.hot, cool: C.cool, violet: C.violet, text: C.text}[name] || C.accent);

// ---- backdrop layers -----------------------------------------------------------------------------------------
const Shape = ({shape, s, col, stroke, rot}) => {
  const line = stroke ? {border: `${Math.max(1.5, s * 0.04)}px solid ${col}`} : {background: col};
  const box = {position: "absolute", left: -s / 2, top: -s / 2, width: s, height: s, transform: `rotate(${rot}deg)`};
  if (shape === "circle" || shape === "dot") return <div style={{...box, borderRadius: "50%", ...line}}/>;
  if (shape === "ring") return <div style={{...box, borderRadius: "50%", border: `${Math.max(1.5, s * 0.05)}px solid ${col}`}}/>;
  if (shape === "square") return <div style={{...box, borderRadius: s * 0.12, ...line}}/>;
  if (shape === "line") return <div style={{...box, height: Math.max(2, s * 0.03), top: 0, background: col, borderRadius: 4}}/>;
  if (shape === "plus") return (
    <div style={box}>
      <div style={{position: "absolute", left: "45%", width: "10%", height: "100%", background: col}}/>
      <div style={{position: "absolute", top: "45%", height: "10%", width: "100%", background: col}}/>
    </div>
  );
  if (shape === "triangle") return (
    <svg style={box} viewBox="0 0 100 100"><polygon points="50,6 96,92 4,92" fill={stroke ? "none" : col} stroke={col}
                                                     strokeWidth={stroke ? 5 : 0}/></svg>
  );
  const outline = {fill: stroke ? "none" : col, stroke: col, strokeWidth: stroke ? 5 : 0, strokeLinejoin: "round"};
  const path = {
    hex: <polygon points="50,4 93,27 93,73 50,96 7,73 7,27" {...outline}/>,
    diamond: <polygon points="50,4 96,50 50,96 4,50" {...outline}/>,
    star: <polygon points="50,4 61,38 96,38 68,59 79,93 50,72 21,93 32,59 4,38 39,38" {...outline}/>,
    chevron: <polyline points="22,6 72,50 22,94" fill="none" stroke={col} strokeWidth={14} strokeLinecap="round" strokeLinejoin="round"/>,
    arc: <path d="M8,80 A42,42 0 0 1 92,80" fill="none" stroke={col} strokeWidth={12} strokeLinecap="round"/>,
    squiggle: <path d="M4,50 Q16,18 28,50 T52,50 T76,50 T98,50" fill="none" stroke={col} strokeWidth={9} strokeLinecap="round"/>,
    cross: <path d="M18,18 L82,82 M82,18 L18,82" fill="none" stroke={col} strokeWidth={13} strokeLinecap="round"/>,
  }[shape];
  if (path) return <svg style={box} viewBox="0 0 100 100">{path}</svg>;
  if (shape === "pill") return <div style={{...box, height: s * 0.42, top: s * 0.29, borderRadius: s, ...line}}/>;
  // blob: a soft colour field
  return <div style={{...box, borderRadius: "50%", background: `radial-gradient(circle, ${col}, transparent 68%)`}}/>;
};

const Layer = ({L, seed}) => {
  const frame = useCurrentFrame() * (C.speed || 1);
  const {width, height} = useVideoConfig();
  const n = Math.round(clamp(L.count, 1, 80));
  const col = alpha(colour(L.color), clamp(L.opacity, 0.02, 0.5));
  const items = [];
  for (let k = 0; k < n; k++) {
    const r = (tag) => random(`${seed}${L.shape}${k}${tag}`);
    const s = Math.max(4, Math.min(width, height) * clamp(L.size, 0.004, 0.7) * (0.5 + r("s")));
    const v = (L.speed ?? 1) * (0.4 + r("v"));
    let x = r("x") * width, y = r("y") * height, rot = r("r") * 360;
    const t = frame * v;
    if (L.drift === "up") y = ((y - t) % (height + s) + height + s) % (height + s);
    else if (L.drift === "down") y = (y + t) % (height + s);
    else if (L.drift === "left") x = ((x - t) % (width + s) + width + s) % (width + s);
    else if (L.drift === "right") x = (x + t) % (width + s);
    else if (L.drift === "orbit") {
      const a = r("a") * 6.283 + t / 300, rad = (0.15 + 0.4 * r("d")) * Math.min(width, height);
      x = width / 2 + Math.cos(a) * rad * 1.6; y = height / 2 + Math.sin(a) * rad;
    } else {                     // float
      x += Math.sin(t / 90 + k) * 40; y += Math.cos(t / 110 + k * 1.3) * 30;
    }
    rot += t * 0.2 * (r("w") - 0.5);
    const pulse = L.drift === "pulse" ? 0.75 + 0.25 * Math.sin(t / 30 + k) : 1;
    items.push(
      <div key={k} style={{position: "absolute", left: x, top: y, transform: `scale(${pulse})`}}>
        <Shape shape={L.shape} s={s} col={col} stroke={L.stroke} rot={rot}/>
      </div>
    );
  }
  // a blob is already a soft gradient, and a full-screen blur is the slowest thing to render: keep blurs small
  const blur = L.shape === "blob" ? 0 : clamp(L.blur, 0, 8);
  return <AbsoluteFill style={{filter: blur ? `blur(${blur}px)` : undefined}}>{items}</AbsoluteFill>;
};

export const GenLayers = ({i = 0}) => {
  const fx = C.fx || {};
  const g = fx.gradient || {};
  return (
    <>
      <AbsoluteFill style={{background: `radial-gradient(ellipse at ${g.x ?? 50}% ${g.y ?? 40}%, ${alpha(colour(g.color || "accent"), g.strength ?? 0.12)}, transparent 70%)`}}/>
      {(fx.layers || []).map((L, k) => <Layer key={k} L={L} seed={`${fx.seed || ""}${k}${L.fixed ? "" : i}`}/>)}
    </>
  );
};

// ---- film texture: grain and vignette, drawn over everything -------------------------------------------------
export const Texture = () => {
  const frame = useCurrentFrame();
  const t = (C.fx || {}).texture || {};
  return (
    <>
      {t.grain > 0 && <AbsoluteFill style={{opacity: clamp(t.grain, 0, 0.25), mixBlendMode: C.light ? "multiply" : "overlay",
                                            pointerEvents: "none"}}>
        {/* still (no shimmer) and tiled at its own size, so the grain stays fine at 4K instead of a stretched blur */}
        <AbsoluteFill style={{backgroundImage: `url(${staticFile("grain.png")})`, backgroundSize: "512px 512px"}}/>
      </AbsoluteFill>}
      {t.vignette > 0 && <AbsoluteFill style={{pointerEvents: "none",
        background: `radial-gradient(ellipse at center, transparent 55%, ${alpha(C.light ? "#000000" : "#000000", clamp(t.vignette, 0, 0.7))})`}}/>}
    </>
  );
};

// ---- how words enter -------------------------------------------------------------------------------------------
// p: the word's spring (0..1); returns the style for that word
export const wordEnter = (p, size, k) => {
  const e = ((C.fx || {}).text || {}).enter || "rise";
  const q = clamp(p);
  switch (e) {
    case "blur": return {opacity: q, filter: `blur(${(1 - q) * 22}px)`, transform: `scale(${1.15 - 0.15 * p})`};
    case "scale": return {opacity: q, transform: `scale(${0.3 + 0.7 * p})`};
    case "slide": return {opacity: q, transform: `translateX(${(1 - p) * size * 1.2}px)`};
    case "drop": return {opacity: q, transform: `translateY(${(1 - p) * -size * 0.8}px)`};
    case "mask": return {clipPath: `inset(${(1 - q) * 100}% 0 0 0)`, transform: `translateY(${(1 - p) * size * 0.4}px)`};
    case "write": return {clipPath: `inset(-20% ${(1 - q) * 100}% -20% 0)`};      // written on left to right
    case "flip": return {opacity: q, transform: `rotateY(${(1 - p) * 90}deg)`, transformOrigin: "left center"};
    case "spread": return {opacity: q, letterSpacing: `${(1 - q) * size * 0.25}px`, filter: `blur(${(1 - q) * 8}px)`};
    case "tilt": return {opacity: q, transform: `rotate(${(1 - p) * (k % 2 ? 12 : -12)}deg) translateY(${(1 - p) * size * 0.3}px)`};
    default: return {opacity: clamp(p * 1.4), filter: `blur(${(1 - q) * 14}px)`,
                     transform: `translateY(${(1 - p) * size * 0.5}px) rotateX(${(1 - p) * 60}deg)`};
  }
};

// ---- a transition built from parameters: clip shape, angle, blur, scale ----------------------------------------
const clipFor = (shape, p, angle) => {
  const q = ease(p);
  if (shape === "circle") return `circle(${q * 75}% at 50% 50%)`;
  if (shape === "diamond") return `polygon(50% ${50 - q * 100}%, ${50 + q * 100}% 50%, 50% ${50 + q * 100}%, ${50 - q * 100}% 50%)`;
  if (shape === "split") return `inset(${(1 - q) * 50}% 0 ${(1 - q) * 50}% 0)`;
  if (shape === "bars") return `inset(0 ${(1 - q) * 50}% 0 ${(1 - q) * 50}%)`;
  if (shape === "corner") return `circle(${q * 150}% at ${angle % 2 ? 0 : 100}% ${angle % 3 ? 0 : 100}%)`;
  // diagonal wipe at an angle
  const a = (angle * Math.PI) / 180, w = 160 * q - 30;
  const dx = Math.cos(a) * 30;
  return `polygon(${-30 + dx}% -10%, ${w + dx}% -10%, ${w - dx}% 110%, ${-30 - dx}% 110%)`;
};

export const genCut = (cut) => ({
  props: {},
  component: ({children, presentationDirection, presentationProgress: p}) => {
    const enter = presentationDirection === "entering";
    const blur = cut.blur || 0, scale = cut.scale || 0;
    if (enter) {
      return (
        <AbsoluteFill style={{clipPath: cut.shape === "fade" ? undefined : clipFor(cut.shape, p, cut.angle || 0),
                              opacity: cut.shape === "fade" ? ease(p) : 1,
                              filter: blur ? `blur(${(1 - ease(p)) * blur}px)` : undefined,
                              transform: `scale(${1 + scale * (1 - ease(p))}) rotate(${(cut.spin || 0) * (1 - ease(p))}deg)`}}>
          {children}
        </AbsoluteFill>
      );
    }
    return (
      <AbsoluteFill style={{filter: blur ? `blur(${ease(p) * blur * 0.6}px)` : undefined,
                            transform: `scale(${1 - scale * 0.5 * ease(p)})`, opacity: 1 - 0.5 * ease(p)}}>
        {children}
      </AbsoluteFill>
    );
  },
});
