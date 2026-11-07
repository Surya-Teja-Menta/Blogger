// Film looks, after the style guides of the Lemo-Opuscar library (MIT, LemoLab, github.com/lemomo-ai/lemo-opuscar):
// the surface a video is drawn on, how its lines are drawn and what lies over it. blogwriter/looks.py picks one per
// video by its subject and passes it in the theme as `look` = {slug, surface, stroke, overlay, misregister, mono}.
// Everything here is still from frame to frame (no grain that jumps, no flicker): only the content moves.
import React from "react";
import {AbsoluteFill, random, staticFile, useVideoConfig} from "remotion";
import {C, alpha} from "./theme";

export const look = () => C.look || null;

const seeded = (key, n) => Array.from({length: n}, (_, k) => random(`${key}-${k}`));

// ---- surfaces ---------------------------------------------------------------------------------------------------
const Grain = ({opacity, blend = "soft-light"}) => (
  <AbsoluteFill style={{backgroundImage: `url(${staticFile("grain.png")})`, backgroundSize: "512px 512px",
                        opacity, mixBlendMode: blend}}/>
);

const Mottle = ({colour, n = 4, opacity = 0.06, seed = "m"}) => {
  const {width, height} = useVideoConfig();
  const r = seeded(seed, n * 3);
  return Array.from({length: n}, (_, k) => (
    <div key={k} style={{position: "absolute", width: width * (0.35 + 0.3 * r[k * 3]), height: width * (0.35 + 0.3 * r[k * 3]),
                         left: width * r[k * 3 + 1] - width * 0.2, top: height * r[k * 3 + 2] - width * 0.2, borderRadius: "50%",
                         background: `radial-gradient(circle, ${alpha(colour, opacity)}, transparent 70%)`}}/>
  ));
};

const Frame = ({colour, size}) => (       // the board's own frame: wood for a slate, aluminium for a whiteboard
  <AbsoluteFill style={{boxShadow: `inset 0 0 0 ${size}px ${colour}, inset 0 0 0 ${size + 3}px ${alpha("#000000", 0.25)},
                                    inset 0 ${size + 6}px ${size * 2}px ${alpha("#000000", 0.18)}`}}/>
);

export const Surface = ({i = 0}) => {
  const L = look();
  if (!L) return null;
  const s = L.surface;
  if (s === "slate") {
    return (
      <AbsoluteFill style={{background: C.bg}}>
        <Mottle colour="#ffffff" n={5} opacity={0.035} seed={`slate${i % 3}`}/>
        <Grain opacity={0.28}/>
        <Frame colour="#6b4a2e" size={14}/>
      </AbsoluteFill>
    );
  }
  if (s === "whiteboard") {
    const r = seeded(`ghost${i % 4}`, 18);
    return (
      <AbsoluteFill style={{background: C.bg}}>
        <AbsoluteFill style={{background: "linear-gradient(115deg, rgba(255,255,255,0) 30%, rgba(255,255,255,0.65) 45%, rgba(255,255,255,0) 60%)"}}/>
        <svg width="100%" height="100%" viewBox="0 0 1920 1080" className="look-surface" style={{position: "absolute"}}>
          {[0, 1, 2, 3, 4, 5].map((k) => (       // ghost marks of earlier lessons, barely there
            <path key={k} d={`M${200 + 1500 * r[k * 3]},${150 + 750 * r[k * 3 + 1]} q60,-30 120,0 t120,${-40 + 80 * r[k * 3 + 2]}`}
                  fill="none" stroke={alpha(C.text, 0.045)} strokeWidth={10} strokeLinecap="round"/>
          ))}
        </svg>
        <Frame colour="#c9ccd1" size={12}/>
      </AbsoluteFill>
    );
  }
  if (s === "blueprint") {
    return (
      <AbsoluteFill style={{background: C.bg}}>
        <AbsoluteFill style={{backgroundImage: `linear-gradient(${alpha(C.text, 0.07)} 1px, transparent 1px),
                                                linear-gradient(90deg, ${alpha(C.text, 0.07)} 1px, transparent 1px),
                                                linear-gradient(${alpha(C.text, 0.16)} 1.5px, transparent 1.5px),
                                                linear-gradient(90deg, ${alpha(C.text, 0.16)} 1.5px, transparent 1.5px)`,
                              backgroundSize: "24px 24px, 24px 24px, 120px 120px, 120px 120px"}}/>
        <Mottle colour="#000000" n={4} opacity={0.12} seed={`bp${i % 3}`}/>
        <Grain opacity={0.22}/>
        <AbsoluteFill style={{background: `radial-gradient(ellipse at center, transparent 55%, ${alpha("#000000", 0.28)})`}}/>
      </AbsoluteFill>
    );
  }
  if (s === "keynote") {
    return (
      <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% -10%, ${alpha(C.accent, 0.16)}, transparent 55%), ${C.bg}`}}>
        <AbsoluteFill style={{backgroundImage: `linear-gradient(${alpha(C.text, 0.035)} 1px, transparent 1px),
                                                linear-gradient(90deg, ${alpha(C.text, 0.035)} 1px, transparent 1px)`,
                              backgroundSize: "80px 80px", maskImage: "radial-gradient(ellipse at center, black 30%, transparent 80%)"}}/>
      </AbsoluteFill>
    );
  }
  if (s === "crt") {
    return (
      <AbsoluteFill style={{background: `radial-gradient(ellipse at center, ${alpha(C.accent, 0.07)}, transparent 70%), ${C.bg}`}}/>
    );
  }
  if (s === "film") {
    return (
      <AbsoluteFill style={{background: `radial-gradient(ellipse at center, ${alpha(C.text, 0.07)}, transparent 70%), ${C.bg}`}}>
        <Grain opacity={0.3} blend="overlay"/>
      </AbsoluteFill>
    );
  }
  if (s === "watercolor") {
    return (
      <AbsoluteFill style={{background: C.bg}}>
        <Mottle colour={C.cool} n={3} opacity={0.09} seed={`wc${i % 4}`}/>
        <Mottle colour={C.accent} n={2} opacity={0.06} seed={`wa${i % 4}`}/>
        <Grain opacity={0.35} blend="multiply"/>
      </AbsoluteFill>
    );
  }
  // paper: cream stock for data stories, engraving, risograph and dossier prints
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <Mottle colour={C.text} n={3} opacity={0.025} seed={`pp${i % 3}`}/>
      <Grain opacity={0.3} blend="multiply"/>
    </AbsoluteFill>
  );
};

// ---- how lines are drawn: SVG filters applied to every line, shape and formula -----------------------------------
const FILTERS = {
  // chalk: a slightly wobbling line whose grains do not all take the chalk
  chalk: (
    <filter id="look-chalk" x="-10%" y="-10%" width="120%" height="120%">
      <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="7" result="wob"/>
      <feDisplacementMap in="SourceGraphic" in2="wob" scale="3.5" xChannelSelector="R" yChannelSelector="G" result="line"/>
      <feTurbulence type="fractalNoise" baseFrequency="0.95" numOctaves="1" seed="3" result="grain"/>
      <feColorMatrix in="grain" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  2.6 0 0 0 -0.55" result="mask"/>
      <feComposite in="line" in2="mask" operator="in"/>
    </filter>
  ),
  // marker: a hand-drawn wobble, full ink
  marker: (
    <filter id="look-marker" x="-10%" y="-10%" width="120%" height="120%">
      <feTurbulence type="fractalNoise" baseFrequency="0.008" numOctaves="1" seed="11" result="wob"/>
      <feDisplacementMap in="SourceGraphic" in2="wob" scale="3" xChannelSelector="R" yChannelSelector="G"/>
    </filter>
  ),
  // ink (engraving, risograph, dossier): a printed edge, slightly rough
  ink: (
    <filter id="look-ink" x="-10%" y="-10%" width="120%" height="120%">
      <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="1" seed="5" result="rough"/>
      <feDisplacementMap in="SourceGraphic" in2="rough" scale="1.6" xChannelSelector="R" yChannelSelector="G"/>
    </filter>
  ),
  // brush (watercolour): soft wet edges that wander
  brush: (
    <filter id="look-brush" x="-10%" y="-10%" width="120%" height="120%">
      <feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="3" seed="9" result="wob"/>
      <feDisplacementMap in="SourceGraphic" in2="wob" scale="5" xChannelSelector="R" yChannelSelector="G" result="w"/>
      <feGaussianBlur in="w" stdDeviation="0.7"/>
    </filter>
  ),
};

export const LookDefs = () => {
  const L = look();
  if (!L || !FILTERS[L.stroke]) return null;
  return <svg width={0} height={0} style={{position: "absolute"}}><defs>{FILTERS[L.stroke]}</defs></svg>;
};

// the rules that put the line treatment on every shot (lines, shapes, formulas), and the look's text treatments
export const LookStyle = () => {
  const L = look();
  if (!L) return null;
  const shapes = "svg:not(.look-surface) :is(path, line, polyline, polygon, circle, ellipse, rect)";
  const rules = [];
  // !important: the line treatment wins over a shape's own glow (chalk, ink and paint do not glow)
  if (FILTERS[L.stroke]) rules.push(`.look-root ${shapes}, .look-root .katex { filter: url(#look-${L.stroke}) !important; }`);
  if (L.stroke === "technical") rules.push(`.look-root ${shapes} { filter: drop-shadow(0 0 2px ${alpha(C.text, 0.55)}) !important; }`);
  if (L.surface === "crt") rules.push(`.look-root { text-shadow: 0 0 8px ${alpha(C.accent, 0.55)}; }`);
  return <style>{rules.join("\n")}</style>;
};

// over everything: halftone dots (print), scanlines (CRT), a film vignette; nothing that moves
export const LookOverlay = () => {
  const L = look();
  if (!L || C.clean) return null;
  if (L.overlay === "halftone") {
    return <AbsoluteFill style={{backgroundImage: `radial-gradient(${alpha(C.text, 0.07)} 1.2px, transparent 1.4px)`,
                                 backgroundSize: "7px 7px", mixBlendMode: "multiply", pointerEvents: "none"}}/>;
  }
  if (L.overlay === "scanlines") {
    return (
      <>
        <AbsoluteFill style={{backgroundImage: "repeating-linear-gradient(0deg, rgba(0,0,0,0.28) 0px, rgba(0,0,0,0.28) 2px, transparent 2px, transparent 4px)"}}/>
        <AbsoluteFill style={{background: "radial-gradient(ellipse at center, transparent 60%, rgba(0,0,0,0.55) 100%)"}}/>
      </>
    );
  }
  if (L.overlay === "film") {
    return <AbsoluteFill style={{background: "radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.6) 100%)"}}/>;
  }
  return null;
};
