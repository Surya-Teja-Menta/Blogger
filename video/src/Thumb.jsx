import React from "react";
import {AbsoluteFill, Img, staticFile} from "remotion";
import {FONT} from "./Board";

// YouTube thumbnail: the hook's photos as a collage, its headline number and a few big words
export const Thumb = ({scenes, thumbText = "", accent = "#e63946"}) => {
  const hook = scenes[0] || {};
  const images = scenes.flatMap((s) => s.images || []).filter((v, i, a) => a.indexOf(v) === i).slice(0, 2);
  return (
    <AbsoluteFill style={{background: "radial-gradient(circle at 30% 40%, #2b2118, #0e1116 75%)", fontFamily: FONT}}>
      {images.map((src, k) => (
        <div key={src} style={{position: "absolute", left: 40 + k * 230, top: 70 + k * 200, width: 470, height: 360,
                               background: "#fff", padding: 12, transform: `rotate(${k ? 6 : -5}deg)`,
                               boxShadow: "0 20px 50px rgba(0,0,0,.6)"}}>
          <Img src={staticFile(src)} style={{width: "100%", height: "100%", objectFit: "cover"}}/>
        </div>
      ))}
      <svg style={{position: "absolute", inset: 0}} width={1280} height={720}>
        <line x1={250} y1={120} x2={1100} y2={600} stroke="#c1121f" strokeWidth={6}/>
      </svg>
      <div style={{position: "absolute", right: 50, top: 70, width: 620, textAlign: "right"}}>
        {hook.number && <div style={{fontSize: 170, fontWeight: 900, color: accent, letterSpacing: -5, lineHeight: 1,
                                     textShadow: "0 6px 0 rgba(0,0,0,.5)"}}>{hook.number}</div>}
        <div style={{marginTop: 24, fontSize: 76, fontWeight: 900, color: "#fff", lineHeight: 1.05,
                     textTransform: "uppercase", textShadow: "0 5px 0 rgba(0,0,0,.6)"}}>{thumbText}</div>
      </div>
    </AbsoluteFill>
  );
};
