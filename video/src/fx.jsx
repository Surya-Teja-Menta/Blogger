// Building blocks shared by every scene: entrances, kinetic text, glass cards, moving backgrounds, photo motion,
// the act sting, the transitions and the film finish. Colours and fonts come from the theme (theme.js).
import React from "react";
import {AbsoluteFill, Img, OffthreadVideo, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import {noise2D} from "@remotion/noise";
import {pop} from "./motion";
import {C, FONT, alpha} from "./theme";
import {GenLayers, wordEnter} from "./gen";
import {Surface} from "./looks";

export const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const ease = (t) => 1 - Math.pow(1 - clamp(t), 3);

export function useEnter(delay = 0, damping = 18) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return pop(frame - delay);              // the video's own arrival curve (the design picks it)
}

export function countUp(text, p) {
  // "$115B" counts 0 -> 115 keeping prefix, suffix and decimals; a year is shown as it is
  const m = /^([^\d]*)(\d[\d,]*\.?\d*)(.*)$/.exec(text || "");
  if (!m || /^(19|20)\d\d$/.test(text)) return text;
  const target = parseFloat(m[2].replace(/,/g, ""));
  const decimals = (m[2].split(".")[1] || "").length;
  const value = target * clamp(p);
  const shown = m[2].includes(",") ? Math.round(value).toLocaleString("en-US") : value.toFixed(decimals);
  return m[1] + shown + m[3];
}

// Headline that arrives word by word out of a blur; the highlighted words get a marker sweep on the spoken word.
export const Words = ({text = "", highlight = "", size = 110, delay = 0, color, font, align = "left",
                       maxWidth = 1500, lineHeight = 1.02, weight, markAt}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const display = !font || font === FONT.display;
  const marks = new Set(highlight.toLowerCase().split(/\s+/).filter(Boolean));
  const words = text.split(/\s+/).filter(Boolean);
  return (
    <div style={{fontFamily: font || FONT.display, fontSize: size, lineHeight, color: color || C.text, textAlign: align, maxWidth,
                 fontWeight: weight || (display ? C.weight : 700), letterSpacing: display && C.upper ? 1 : -0.5,
                 textTransform: display && C.upper ? "uppercase" : "none", perspective: 800}}>
      {words.map((w, i) => {
        const p = pop(frame - delay - i * (C.stagger ?? 2.5));
        const marked = marks.has(w.toLowerCase().replace(/[^\p{L}\p{N}$%.]/gu, ""));
        const sweep = clamp((frame - (markAt ?? delay + words.length * 2.5 + 4)) / 8);
        return (
          <span key={i} style={{display: "inline-block", marginRight: size * 0.24, ...wordEnter(p, size, i),
                                ...(C.look && C.look.misregister ? {textShadow: `${size * 0.06}px ${size * 0.06}px 0 ${alpha(C[C.look.misregister] || C.hot, 0.6)}`} : {}),
                                padding: marked ? `0 ${size * 0.1}px` : 0, borderRadius: size * 0.08,
                                color: marked && sweep > 0.35 ? (C.light ? "#fff" : C.bg) : undefined,
                                background: marked ? `linear-gradient(100deg, ${C.accent}, ${C.accent}) no-repeat left / ${sweep * 100}% 100%` : "none",
                                boxShadow: marked && sweep > 0.9 ? `0 0 40px ${alpha(C.accent, 0.35)}` : "none"}}>
            {w}
          </span>
        );
      })}
    </div>
  );
};

// a small tag above a headline: glass pill with a pulsing dot
export const Kicker = ({text, delay = 0, size = 28, center = false}) => {
  const frame = useCurrentFrame();
  const p = useEnter(delay);
  if (!text) return null;
  center = center || C.title === "center";
  if (C.kicker === "rule") {           // a design may prefer a drawn rule and spaced capitals to the glass pill
    return (
      <div style={{display: "flex", alignItems: "center", gap: size * 0.6, justifyContent: center ? "center" : "flex-start",
                   marginBottom: size * 0.9, opacity: p}}>
        <div style={{width: size * 2.4 * ease(p), height: 3, background: C.accent, boxShadow: `0 0 12px ${alpha(C.accent, 0.6)}`}}/>
        <div style={{fontFamily: FONT.body, fontWeight: 800, fontSize: size, letterSpacing: size * 0.3, color: C.accent,
                     textTransform: "uppercase", clipPath: `inset(0 ${(1 - clamp(p)) * 100}% 0 0)`}}>{text}</div>
      </div>
    );
  }
  return (
    <div style={{display: "flex", justifyContent: center ? "center" : "flex-start", marginBottom: size * 0.9}}>
      <div style={{display: "inline-flex", alignItems: "center", gap: size * 0.5, padding: `${size * 0.35}px ${size * 0.8}px`,
                   borderRadius: 100, background: alpha(C.panel, 0.6), border: `1.5px solid ${alpha(C.accent, 0.5)}`,
                   backdropFilter: "blur(12px)", opacity: p, transform: `translateX(${(1 - p) * -40}px)`,
                   clipPath: `inset(0 ${(1 - clamp(p)) * 100}% 0 0 round 100px)`}}>
        <div style={{width: size * 0.38, height: size * 0.38, borderRadius: size, background: C.accent,
                     boxShadow: `0 0 ${10 + 8 * Math.sin(frame / 6)}px ${C.accent}`}}/>
        <div style={{fontFamily: FONT.body, fontWeight: 800, fontSize: size, letterSpacing: size * 0.18, color: C.text,
                     textTransform: "uppercase"}}>{text}</div>
      </div>
    </div>
  );
};

// the headline block at the top of a shot; the design decides left or centred
export const Title = ({s, vertical, top, size, maxWidth}) => {
  if (C.clean) return null;
  const center = C.title === "center";
  return (
    <div style={{position: "absolute", left: vertical ? 70 : 120, right: vertical ? 70 : 120, top: top ?? (vertical ? 250 : 112),
                 display: "flex", flexDirection: "column", alignItems: center ? "center" : "flex-start"}}>
      <Kicker text={s.kicker} size={vertical ? 32 : 26}/>
      <Words text={s.headline} highlight={s.highlight} size={size || (vertical ? 84 : 78)} delay={2} markAt={s.hcue}
             maxWidth={maxWidth || (vertical ? 940 : 1600)} align={center ? "center" : "left"}/>
    </div>
  );
};

// frosted card used by charts, lists and figures
const card = () => (C.fx || {}).cards || {};
export const Glass = ({children, style = {}, p = 1, glow}) => (
  <div style={{background: card().fill === "outline" ? "transparent" : card().fill === "solid" ? C.panel
                 : C.light ? alpha("#ffffff", 0.82) : alpha(C.panel, 0.55), backdropFilter: "blur(18px)",
               border: `${card().fill === "outline" ? 2.5 : 1.5}px solid ${card().fill === "outline" ? alpha(C.accent, 0.6)
                 : C.light ? alpha(C.line, 0.9) : alpha("#ffffff", 0.09)}`, borderRadius: card().radius ?? 28,
               boxShadow: `0 30px 80px ${alpha("#000000", (C.light ? 0.12 : 0.45) * (card().shadow ?? 1))}${glow ? `, 0 0 60px ${alpha(glow, 0.18)}` : ""}`,
               opacity: clamp(p * 1.3), transform: `translateY(${(1 - p) * 60}px) scale(${0.94 + 0.06 * p})`, ...style}}>
    {children}
  </div>
);

// The scene's content moves in 3D like a camera held by an operator: a slow push across the shot plus an organic
// sway (simplex noise, @remotion/noise), never a mechanical back-and-forth. Nothing is ever perfectly still.
export const Camera = ({children, i = 0, amount: base = 1}) => {
  const amount = base * (((C.fx || {}).camera) ?? 1);
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const t = frame / Math.max(1, durationInFrames);
  const dir = i % 2 ? 1 : -1;
  // flat (no 3D tilt): a tilted layer is redrawn in perspective every frame, so text edges shimmer and soften on a
  // big screen; a slow push and a small drift keep the shot alive while every letter stays crisp
  const sway = (key, period) => noise2D(`${key}-${i}`, frame / period, 0);
  const tx = dir * t * 16 * amount + sway("tx", 160) * 6 * amount, ty = sway("ty", 180) * 4 * amount;
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{transform: `translate(${tx}px, ${ty}px) scale(${1 + 0.04 * t * amount})`}}>
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// drifting specks of light (or dust on paper); positions are seeded, so every render is identical
export const Particles = ({n = 40, seed = "p", color}) => {
  if (C.clean || C.look) return null;     // a film look is a real surface: no floating dust
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  return (
    <AbsoluteFill style={{pointerEvents: "none"}}>
      {Array.from({length: n}, (_, k) => {
        const x = random(`${seed}x${k}`) * width, y0 = random(`${seed}y${k}`) * height;
        const speed = 0.3 + random(`${seed}s${k}`) * 1.2, r = 1.5 + random(`${seed}r${k}`) * 3.5;
        const y = ((y0 - frame * speed) % height + height) % height;
        const tw = 0.35 + 0.65 * Math.abs(Math.sin(frame / (20 + k) + k));
        return <div key={k} style={{position: "absolute", left: x + 20 * Math.sin(frame / 50 + k), top: y, width: r * 2, height: r * 2,
                                    borderRadius: r, background: color || C.accent, opacity: tw * (C.light ? 0.25 : 0.55),
                                    boxShadow: C.light ? "none" : `0 0 ${r * 4}px ${color || C.accent}`}}/>;
      })}
    </AbsoluteFill>
  );
};

// The theme's moving background, used whenever a scene has no photo or footage.
export const Backdrop = ({word = "", hue, i = 0}) => {
  if (C.clean) return null;           // a thumbnail cut-out: the visual alone, on a transparent frame
  if (C.look) return <Surface i={i}/>;   // a film look draws on its own surface (looks.jsx)
  const frame = useCurrentFrame() * (C.speed || 1);     // the design's pace sets how fast the backdrop drifts
  const {width, height} = useVideoConfig();
  const h = hue || C.accent;
  const big = word && (
    <div style={{position: "absolute", left: 0, bottom: -height * 0.06, fontFamily: FONT.display, fontWeight: C.weight,
                 fontSize: Math.min(width, height) * 0.5, whiteSpace: "nowrap", textTransform: C.upper ? "uppercase" : "none",
                 color: "transparent", WebkitTextStroke: `2px ${alpha(C.text, C.light ? 0.07 : 0.06)}`,
                 transform: `translateX(${width * 0.1 - frame * 1.2}px)`}}>{word}</div>
  );
  let layer = null;
  if (C.back === "grid") {
    layer = (
      <>
        <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 60%, ${alpha(C.cool, 0.35)}, transparent 55%)`}}/>
        <AbsoluteFill style={{perspective: 600, overflow: "hidden"}}>
          <div style={{position: "absolute", left: "-50%", width: "200%", top: "52%", height: "120%", transform: "rotateX(72deg)",
                       transformOrigin: "top", backgroundImage: `linear-gradient(${alpha(C.accent, 0.5)} 2px, transparent 2px), linear-gradient(90deg, ${alpha(C.accent, 0.5)} 2px, transparent 2px)`,
                       backgroundSize: "120px 120px", backgroundPosition: `0px ${frame * 4}px`,
                       maskImage: "linear-gradient(to bottom, transparent, black 30%, black 60%, transparent)"}}/>
        </AbsoluteFill>
        <div style={{position: "absolute", left: 0, right: 0, top: "52%", height: 3, background: C.hot, boxShadow: `0 0 40px 8px ${alpha(C.hot, 0.6)}`, opacity: 0.8}}/>
      </>
    );
  } else if (C.back === "contour") {
    layer = (
      <svg width={width} height={height} style={{position: "absolute"}}>
        {Array.from({length: 16}, (_, k) => {
          const pts = Array.from({length: 33}, (_, j) => {
            const x = (j / 32) * width;
            const y = height * (0.1 + k * 0.055) + 40 * Math.sin(j / 4 + k * 0.7 + frame / 45) + 18 * Math.sin(j / 1.7 - frame / 30 + k);
            return `${j ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
          }).join(" ");
          return <path key={k} d={pts} fill="none" stroke={k % 4 === 0 ? alpha(C.accent, 0.35) : alpha(C.cool, 0.13)} strokeWidth={k % 4 === 0 ? 2.5 : 1.5}/>;
        })}
      </svg>
    );
  } else if (C.back === "rays") {
    layer = (
      <>
        <AbsoluteFill style={{background: `repeating-conic-gradient(from ${frame * 0.15}deg at 78% -10%, ${alpha(C.accent, C.light ? 0.08 : 0.1)} 0deg 6deg, transparent 6deg 18deg)`,
                              maskImage: "radial-gradient(ellipse at 78% 0%, black, transparent 75%)"}}/>
        <AbsoluteFill style={{background: `radial-gradient(circle at 78% 0%, ${alpha(C.cool, 0.25)}, transparent 50%)`}}/>
      </>
    );
  } else if (C.back === "dots") {
    layer = (
      <svg width={width} height={height} style={{position: "absolute"}}>
        {Array.from({length: 22 * 13}, (_, k) => {
          const cx = (k % 22) * (width / 21), cy = Math.floor(k / 22) * (height / 12);
          const wave = 0.5 + 0.5 * Math.sin(cx / 180 + cy / 140 - frame / 25);
          return <circle key={k} cx={cx} cy={cy} r={2 + 5 * wave}
                         fill={alpha(k % 7 === 0 ? C.hot : C.accent, (C.light ? 0.1 : 0.12) + 0.25 * wave)}/>;
        })}
      </svg>
    );
  } else if (C.back === "waves") {
    layer = (
      <svg width={width} height={height} style={{position: "absolute"}}>
        {[C.violet, C.cool, C.accent].map((col, k) => {
          const pts = Array.from({length: 41}, (_, j) => {
            const x = (j / 40) * width;
            const y = height * (0.6 + k * 0.12) + 50 * Math.sin(j / 5 + frame / (40 + 12 * k) + k) + 25 * Math.sin(j / 2.3 - frame / 33);
            return `L${x.toFixed(1)},${y.toFixed(1)}`;
          }).join(" ");
          return <path key={k} d={`M0,${height} ${pts} L${width},${height} Z`} fill={alpha(col, C.light ? 0.12 : 0.16)}/>;
        })}
      </svg>
    );
  } else if (C.back === "paper") {
    layer = (
      <>
        <AbsoluteFill style={{backgroundImage: `radial-gradient(${alpha(C.text, 0.12)} 1.5px, transparent 1.5px)`, backgroundSize: "36px 36px",
                              backgroundPosition: `${frame * 1.2}px ${frame * 0.5}px`}}/>
        {[0, 1, 2].map((k) => (
          <div key={k} style={{position: "absolute", width: 520 + k * 220, height: 520 + k * 220, borderRadius: "50%",
                               border: `2px solid ${alpha([C.accent, C.cool, C.hot][k], 0.25)}`,
                               right: -160 + 60 * Math.sin(frame / 80 + k), top: -180 + k * 90 + 40 * Math.cos(frame / 70 + k)}}/>
        ))}
        <div style={{position: "absolute", width: 380, height: 380, borderRadius: "50%", left: -120 + 30 * Math.sin(frame / 60),
                     bottom: -140, background: alpha(C.violet, 0.35), filter: "blur(10px)"}}/>
      </>
    );
  } else {
    // aurora / orbs: large blurred colour fields that wander
    const blobs = C.back === "orbs" ? [C.violet, C.cool, C.hot, C.accent] : [C.accent, C.cool, C.violet];
    layer = blobs.map((b, k) => (
      <div key={k} style={{position: "absolute", width: width * 0.55, height: width * 0.55, borderRadius: "50%",
                           left: width * (0.15 + 0.5 * random(`bx${k}${i}`)) + 160 * Math.sin(frame / (70 + 20 * k) + k * 2) - width * 0.27,
                           top: height * (0.2 + 0.5 * random(`by${k}${i}`)) + 120 * Math.cos(frame / (90 + 15 * k) + k) - width * 0.27,
                           background: `radial-gradient(circle, ${alpha(b, C.back === "orbs" ? 0.45 : C.light ? 0.15 : 0.28)}, transparent 65%)`,
                           filter: "blur(30px)"}}/>
    ));
  }
  if (C.fx && C.fx.layers && C.fx.layers.length) {
    return (
      <AbsoluteFill style={{background: C.bg, overflow: "hidden"}}>
        <GenLayers i={i}/>
        {(C.fx.bigWord ?? true) && big}
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{background: C.bg, overflow: "hidden"}}>
      {layer}
      {big}
      <Particles n={C.back === "paper" ? 18 : 34} seed={`b${i}`} color={h}/>
    </AbsoluteFill>
  );
};

// A photo that keeps moving: push-in and drift, graded to sit under text.
export const KenBurns = ({src, dir = 1, grade = 0.62, start = 1.06, end = 1.22}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const t = frame / Math.max(1, durationInFrames);
  return (
    <AbsoluteFill style={{overflow: "hidden", background: C.bg}}>
      <Img src={staticFile(src)} style={{width: "100%", height: "100%", objectFit: "cover",
        transform: `scale(${interpolate(t, [0, 1], [start, end])}) translate(${dir * t * 3}%, ${-t * 1.5}%)`,
        filter: `brightness(${C.light ? grade + 0.25 : grade}) contrast(1.1) saturate(${C.light ? 0.9 : 0.85})`}}/>
    </AbsoluteFill>
  );
};

// Real footage when the shot has a clip, else the photo; a short clip is slowed down rather than frozen.
export const Plate = ({s, i = 0, grade = 0.62}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, fps} = useVideoConfig();
  if (s.video) {
    const rate = Math.max(0.5, Math.min(1, (s.clipSeconds || 10) / (durationInFrames / fps)));
    return (
      <AbsoluteFill style={{overflow: "hidden", background: C.bg}}>
        <OffthreadVideo src={staticFile(s.video)} muted playbackRate={rate}
                        style={{width: "100%", height: "100%", objectFit: "cover",
                                transform: `scale(${interpolate(frame / Math.max(1, durationInFrames), [0, 1], [1.04, 1.12])})`,
                                filter: `brightness(${grade + 0.08}) contrast(1.1) saturate(0.9)`}}/>
      </AbsoluteFill>
    );
  }
  if (s.images && s.images[0]) return <KenBurns src={s.images[0]} dir={i % 2 ? 1 : -1} grade={grade}/>;
  return null;
};

// A photo as a floating 3D card with a light sweep across it
export const PhotoCard = ({src, w, h, p = 1, tilt = -14, delay = 0, style = {}}) => {
  const frame = useCurrentFrame();
  const sweep = ((frame - delay) % 150) / 150;
  return (
    <div style={{perspective: 1600, ...style}}>
      <div style={{width: w, height: h, borderRadius: 26, overflow: "hidden", position: "relative",
                   transform: `rotateY(${tilt * (1 - 0.3 * p) + 3 * Math.sin(frame / 60)}deg) rotateX(${4 - 2 * Math.sin(frame / 80)}deg) `
                              + `translateY(${(1 - p) * 120}px) scale(${0.85 + 0.15 * p})`,
                   opacity: clamp(p * 1.3), boxShadow: `0 50px 100px ${alpha("#000000", 0.5)}, 0 0 0 1.5px ${alpha("#ffffff", 0.15)}`}}>
        <Img src={staticFile(src)} style={{width: "100%", height: "100%", objectFit: "cover",
                                           transform: `scale(${1.08 + frame / 2500})`, filter: "contrast(1.08) saturate(1.05)"}}/>
        <div style={{position: "absolute", top: 0, bottom: 0, width: "40%", left: `${-50 + sweep * 200}%`,
                     background: "linear-gradient(100deg, transparent, rgba(255,255,255,.22), transparent)"}}/>
      </div>
    </div>
  );
};

// legibility shade over photos, in the theme's background colour
export const Shade = ({vertical, strong = 0.95}) => (
  <AbsoluteFill style={{background: vertical
    ? `linear-gradient(to top, ${alpha(C.bg, strong)} 0%, ${alpha(C.bg, 0.75)} 38%, ${alpha(C.bg, 0.1)} 65%, ${alpha(C.bg, 0.55)} 100%)`
    : `linear-gradient(to top, ${alpha(C.bg, strong)} 0%, ${alpha(C.bg, 0.55)} 40%, ${alpha(C.bg, 0)} 70%), linear-gradient(to right, ${alpha(C.bg, 0.8)}, transparent 60%)`}}/>
);

// The act sting: a band of colour sweeps across with the act title, then gets out of the way (about 1.3 s).
// The narration keeps running under it, so it costs no time.
export const ChapterSting = ({kicker, title, vertical}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  if (frame > 44) return null;
  const inP = spring({frame, fps, config: {damping: 20}});
  const out = clamp((frame - 30) / 12);
  const x = interpolate(inP, [0, 1], [-width, 0]) + ease(out) * width * 1.2;
  return (
    <AbsoluteFill style={{justifyContent: "center", pointerEvents: "none"}}>
      <div style={{position: "absolute", left: 0, right: 0, height: vertical ? 520 : 400, background: C.accent,
                   transform: `translateX(${x}px) skewX(-12deg)`, boxShadow: `0 0 120px ${alpha(C.accent, 0.5)}`}}/>
      <div style={{position: "absolute", left: 0, right: 0, height: vertical ? 520 : 400, background: C.bg,
                   transform: `translateX(${x * 1.25 - width * 0.03}px) skewX(-12deg)`, opacity: 0.0 + 0.95 * clamp(inP)}}/>
      <div style={{position: "relative", textAlign: "center", transform: `translateX(${ease(out) * width * 0.6}px)`,
                   opacity: clamp(inP * 2) * (1 - out)}}>
        <div style={{fontFamily: FONT.body, fontWeight: 800, letterSpacing: 16, fontSize: vertical ? 40 : 34, color: C.accent}}>{kicker}</div>
        <div style={{fontFamily: FONT.display, fontWeight: C.weight, fontSize: vertical ? 130 : 150, lineHeight: 1.05, color: C.text,
                     textTransform: C.upper ? "uppercase" : "none", padding: "0 80px"}}>{title}</div>
      </div>
    </AbsoluteFill>
  );
};

// Film finish over everything: grain, vignette and (on dark themes) a slow light leak.
// The film finish: a light leak (dark themes), a vignette and a grain that holds still. Grain that jumps every frame
// shimmers on a big screen like the picture is blinking, and costs the encoder most of its bitrate.
export const Finish = () => {
  if (C.clean) return null;
  const frame = useCurrentFrame();
  const x = 0, y = 0;
  return (
    <>
      {!C.light && <AbsoluteFill style={{background: `radial-gradient(circle at ${20 + 60 * (0.5 + 0.5 * Math.sin(frame / 140))}% 0%, ${alpha(C.accent, 0.12)}, transparent 45%)`,
                                         mixBlendMode: "screen"}}/>}
      <AbsoluteFill style={{background: `radial-gradient(ellipse at center, transparent 55%, ${alpha(C.light ? "#5a4a30" : "#000000", C.light ? 0.18 : 0.55)} 100%)`}}/>
      <AbsoluteFill style={{backgroundImage: `url(${staticFile("grain.png")})`, backgroundPosition: `${x}px ${y}px`,
                            opacity: C.light ? 0.05 : 0.07, mixBlendMode: "overlay"}}/>
    </>
  );
};

// ---- transitions (plain CSS, so they render the same in any headless browser) -------------------------------
const Present = (fn) => ({children, presentationDirection, presentationProgress}) => (
  <AbsoluteFill style={fn(presentationDirection === "entering", presentationProgress)}>{children}</AbsoluteFill>
);
const zoomBlurC = Present((enter, p) => enter
  ? {transform: `scale(${1.25 - 0.25 * ease(p)})`, filter: `blur(${(1 - p) * 24}px)`, opacity: clamp(p * 1.6)}
  : {transform: `scale(${1 + 0.35 * ease(p)})`, filter: `blur(${p * 24}px)`, opacity: 1 - clamp(p * 1.2)});
const slideBlurC = Present((enter, p) => enter
  ? {transform: `translateX(${(1 - ease(p)) * 100}%)`, filter: `blur(${(1 - p) * 18}px)`}
  : {transform: `translateX(${-ease(p) * 35}%) scale(${1 - 0.1 * p})`, filter: `blur(${p * 18}px)`, opacity: 1 - 0.6 * p});
const sweepC = ({children, presentationDirection, presentationProgress: p}) => presentationDirection === "entering" ? (
  <AbsoluteFill style={{clipPath: `polygon(0 0, ${ease(p) * 130}% 0, ${ease(p) * 130 - 30}% 100%, 0 100%)`}}>
    {children}
    <div style={{position: "absolute", top: 0, bottom: 0, width: 26, left: `${ease(p) * 130 - 15 - 18}%`, background: C.accent,
                 transform: "skewX(-17deg)", boxShadow: `0 0 60px 20px ${alpha(C.accent, 0.6)}`}}/>
  </AbsoluteFill>
) : <AbsoluteFill>{children}</AbsoluteFill>;
export const CUTS = {
  zoomBlur: () => ({component: zoomBlurC, props: {}}),
  slideBlur: () => ({component: slideBlurC, props: {}}),
  sweep: () => ({component: sweepC, props: {}}),
};
