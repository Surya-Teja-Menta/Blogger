import React from "react";
import {AbsoluteFill, Img, staticFile} from "remotion";
import {C, FONT, alpha, useTheme} from "./theme";

// YouTube thumbnail in the video's theme. With a hero (the video's strongest visual, cut to its content on the same
// background) the layout follows its shape: a wide visual sits under a one- or two-line title across the top, a
// tall one beside a title column. Otherwise: the strongest photo behind three or four huge words.
export const Thumb = ({scenes, thumbText = "", thumbHighlight = "", theme = null, hero = "", heroAspect = 1.8}) => {
  useTheme(theme);
  const photo = scenes.flatMap((s) => s.images || [])[0];
  const figure = hero ? null : (scenes.find((s) => s.number) || {}).number;
  const words = thumbText.split(/\s+/).filter(Boolean);
  const mark = thumbHighlight.toLowerCase();
  const wide = hero && heroAspect >= 1.55;
  const chars = words.join(" ").length;
  const longest = Math.max(4, ...words.map((w) => w.length));
  const upperK = C.upper ? 0.62 : 0.56;               // rough width of a display character, in ems
  const size = !hero ? (C.upper ? 146 : 124)
    : wide ? Math.min(C.upper ? 150 : 128, 1080 / (upperK * Math.max(longest, Math.ceil(chars / 2) + 1)))
    : Math.min(C.upper ? 128 : 110, 520 / (upperK * longest));
  const title = (
    <div style={{fontFamily: FONT.display, fontWeight: C.weight, lineHeight: 0.95, color: C.text, fontSize: size,
                 textTransform: C.upper ? "uppercase" : "none", textShadow: C.light ? "none" : `0 8px 24px ${alpha("#000000", 0.7)}`}}>
      {words.map((w, k) => (
        <span key={k} style={{color: w.toLowerCase().includes(mark) && mark ? C.accent : C.text}}>{w} </span>
      ))}
    </div>
  );
  return (
    <AbsoluteFill style={{background: C.bg, fontVariantNumeric: "lining-nums"}}>
      <div style={{position: "absolute", width: 900, height: 900, borderRadius: "50%", left: -300, top: -300,
                   background: `radial-gradient(circle, ${alpha(C.accent, 0.35)}, transparent 65%)`}}/>
      {hero ? (
        <>
          <div style={{position: "absolute", width: 1100, height: 700, borderRadius: "50%", right: -200, bottom: -260,
                       background: `radial-gradient(ellipse, ${alpha(C.cool, 0.22)}, transparent 65%)`}}/>
          {/* the title takes the height it needs and the visual (cut out on a transparent frame) fills the rest */}
          <div style={{position: "absolute", inset: 0, padding: wide ? "40px 56px 46px" : "40px 40px 46px 56px", display: "flex",
                       flexDirection: wide ? "column" : "row", gap: wide ? 22 : 36}}>
            <div style={{width: wide ? 1060 : 520, flexShrink: 0, alignSelf: wide ? "flex-start" : "center"}}>{title}</div>
            <div style={{position: "relative", flex: 1, minWidth: 0, minHeight: 0}}>
              <Img src={staticFile(hero)} style={{position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain",
                                                  objectPosition: wide ? "50% 50%" : "100% 50%", filter: "saturate(1.1)"}}/>
            </div>
          </div>
        </>
      ) : (
        <>
          {photo && <Img src={staticFile(photo)} style={{position: "absolute", right: 0, width: "68%", height: "100%", objectFit: "cover",
                                                        filter: "contrast(1.2) saturate(1.15) brightness(.95)"}}/>}
          <AbsoluteFill style={{background: `linear-gradient(90deg, ${C.bg} 32%, ${alpha(C.bg, 0.6)} 56%, transparent 80%)`}}/>
          <div style={{position: "absolute", left: 56, top: 64, width: 780}}>
            {figure && (
              <div style={{display: "inline-block", padding: "4px 26px", borderRadius: 14, background: C.hot, color: "#fff",
                           fontFamily: FONT.display, fontWeight: C.weight, fontSize: 112, lineHeight: 1.05, transform: "rotate(-3deg)",
                           marginBottom: 26, boxShadow: `0 12px 30px ${alpha("#000000", 0.4)}`}}>{figure}</div>
            )}
            {title}
          </div>
        </>
      )}
      <div style={{position: "absolute", left: 0, bottom: 0, width: "100%", height: 14, background: `linear-gradient(90deg, ${C.cool}, ${C.accent})`}}/>
      <Img src={staticFile("logo.png")} style={{position: "absolute", right: 28, ...(hero ? {top: 28} : {bottom: 28}), width: hero ? 96 : 110,
                                               height: hero ? 96 : 110, filter: "drop-shadow(0 6px 24px rgba(0,0,0,.5))"}}/>
    </AbsoluteFill>
  );
};
