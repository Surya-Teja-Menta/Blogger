import React from "react";
import {AbsoluteFill, Img, staticFile} from "remotion";
import {C, FONT, alpha, useTheme} from "./theme";

// YouTube thumbnail in the video's theme: the strongest photo, three or four huge words with one in the accent,
// and the headline figure
export const Thumb = ({scenes, thumbText = "", thumbHighlight = "", theme = null}) => {
  useTheme(theme);
  const photo = scenes.flatMap((s) => s.images || [])[0];
  const figure = (scenes.find((s) => s.number) || {}).number;
  const words = thumbText.split(/\s+/).filter(Boolean);
  const mark = thumbHighlight.toLowerCase();
  return (
    <AbsoluteFill style={{background: C.bg, fontVariantNumeric: "lining-nums"}}>
      <div style={{position: "absolute", width: 900, height: 900, borderRadius: "50%", left: -300, top: -300,
                   background: `radial-gradient(circle, ${alpha(C.accent, 0.35)}, transparent 65%)`}}/>
      {photo && <Img src={staticFile(photo)} style={{position: "absolute", right: 0, width: "68%", height: "100%", objectFit: "cover",
                                                    filter: "contrast(1.2) saturate(1.15) brightness(.95)"}}/>}
      <AbsoluteFill style={{background: `linear-gradient(90deg, ${C.bg} 32%, ${alpha(C.bg, 0.6)} 56%, transparent 80%)`}}/>
      <div style={{position: "absolute", left: 56, top: 64, width: 780}}>
        {figure && (
          <div style={{display: "inline-block", padding: "4px 26px", borderRadius: 14, background: C.hot, color: "#fff",
                       fontFamily: FONT.display, fontWeight: C.weight, fontSize: 112, lineHeight: 1.05, transform: "rotate(-3deg)",
                       marginBottom: 26, boxShadow: `0 12px 30px ${alpha("#000000", 0.4)}`}}>{figure}</div>
        )}
        <div style={{fontFamily: FONT.display, fontWeight: C.weight, fontSize: C.upper ? 146 : 124, lineHeight: 0.95, color: C.text,
                     textTransform: C.upper ? "uppercase" : "none", textShadow: C.light ? "none" : `0 8px 24px ${alpha("#000000", 0.7)}`}}>
          {words.map((w, k) => (
            <span key={k} style={{color: w.toLowerCase().includes(mark) && mark ? C.accent : C.text}}>{w} </span>
          ))}
        </div>
      </div>
      <div style={{position: "absolute", left: 0, bottom: 0, width: "100%", height: 14, background: `linear-gradient(90deg, ${C.cool}, ${C.accent})`}}/>
      <Img src={staticFile("logo.png")} style={{position: "absolute", right: 28, bottom: 28, width: 110, height: 110,
                                               filter: "drop-shadow(0 6px 24px rgba(0,0,0,.5))"}}/>
    </AbsoluteFill>
  );
};
