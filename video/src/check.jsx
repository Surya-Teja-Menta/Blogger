// ---- check: a question for the viewer. The answers land one by one, a ring counts down while the narration
// pauses ("think"), then the right answer lights up and the others fade, with the one-line reason. -----------
import React from "react";
import {AbsoluteFill, useCurrentFrame} from "remotion";
import {Backdrop, Camera, Title, Words, clamp, ease} from "./fx";
import {Icon} from "./graphics";
import {delay, pop} from "./motion";
import {C, FONT, alpha} from "./theme";

const LETTERS = ["A", "B", "C", "D"];

export const CheckScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const opts = s.options || [];
  const think = s.think ?? 40, reveal = Math.max(think + 20, s.reveal ?? 90);
  const shown = frame >= reveal;
  const r = pop(frame - reveal);
  const left = clamp((reveal - frame) / Math.max(1, reveal - think));       // 1 -> 0 while the viewer thinks
  const secs = Math.max(1, Math.ceil((reveal - frame) / 30));
  const radius = ((C.fx || {}).cards || {}).radius ?? 22;
  const ring = 2 * Math.PI * 34;
  return (
    <AbsoluteFill>
      <Backdrop word="" i={i}/>
      <Camera i={i} amount={0.3}>
        <Title s={s} vertical={vertical}/>
        <div style={{position: "absolute", left: vertical ? 70 : 160, right: vertical ? 70 : 160, top: vertical ? 520 : 285,
                     display: "flex", justifyContent: "center"}}>
          <Words text={s.question} size={vertical ? 72 : 70} delay={4} align="center" maxWidth={vertical ? 940 : 1600}/>
        </div>
        <div style={{position: "absolute", left: vertical ? 80 : 140, right: vertical ? 80 : 140, top: vertical ? 860 : 520,
                     display: "flex", flexDirection: vertical ? "column" : "row", gap: vertical ? 24 : 28,
                     justifyContent: "center", alignItems: "stretch"}}>
          {opts.map((o, k) => {
            const p = pop(frame - 16 - 5 * k - delay(k, opts.length, "opt"));
            const right = k === s.answer;
            const fade = shown && !right ? 0.62 * clamp(r) : 0;
            const win = shown && right ? clamp(r) : 0;
            return (
              <div key={k} style={{flex: vertical ? "none" : 1, maxWidth: vertical ? "none" : 440, padding: "24px 28px",
                                   borderRadius: radius, display: "flex", alignItems: "center", gap: 18,
                                   background: win ? alpha(C.accent, 0.12 + 0.08 * win) : alpha(C.panel, 0.92),
                                   border: `3px solid ${win ? C.accent : alpha(C.text, 0.12)}`,
                                   boxShadow: win ? `0 0 ${30 + 30 * win}px ${alpha(C.accent, 0.35)}` : `0 14px 40px ${alpha("#000000", C.light ? 0.08 : 0.35)}`,
                                   opacity: clamp(p * 1.5) * (1 - fade),
                                   transform: `translateY(${(1 - p) * 40}px) scale(${1 + 0.05 * win})`}}>
                <div style={{width: 58, height: 58, borderRadius: 29, flexShrink: 0, display: "flex", alignItems: "center",
                             justifyContent: "center", fontFamily: FONT.display, fontWeight: C.weight, fontSize: 32,
                             background: win ? C.accent : alpha(C.text, 0.08), color: win ? (C.light ? "#fff" : C.bg) : C.text}}>
                  {LETTERS[k]}
                </div>
                <div style={{fontFamily: FONT.body, fontWeight: 800, fontSize: vertical ? 44 : 38, color: C.text, lineHeight: 1.15,
                             flex: 1}}>{o}</div>
                {shown && <Icon name={right ? "circle-check" : "circle-x"} size={46} color={right ? C.accent : C.muted}
                                draw={ease((frame - reveal) / 14)} width={2.2}/>}
              </div>
            );
          })}
        </div>
        {frame >= think - 6 && frame < reveal + 10 && (
          <div style={{position: "absolute", left: "50%", top: vertical ? 1360 : 790, transform: "translateX(-50%)",
                       display: "flex", alignItems: "center", gap: 20,
                       opacity: clamp((frame - think + 6) / 8) * (1 - clamp((frame - reveal) / 10))}}>
            <svg width={84} height={84} viewBox="0 0 84 84">
              <circle cx={42} cy={42} r={34} fill={alpha(C.panel, 0.9)} stroke={alpha(C.text, 0.12)} strokeWidth={6}/>
              <circle cx={42} cy={42} r={34} fill="none" stroke={C.accent} strokeWidth={6} strokeLinecap="round"
                      strokeDasharray={ring} strokeDashoffset={ring * (1 - left)} transform="rotate(-90 42 42)"/>
              <text x={42} y={54} textAnchor="middle" fontFamily={FONT.display} fontWeight={C.weight} fontSize={36}
                    fill={C.text}>{secs}</text>
            </svg>
            <span style={{fontFamily: FONT.body, fontWeight: 800, fontSize: vertical ? 40 : 34, color: C.muted,
                          letterSpacing: 1}}>Pause and think</span>
          </div>
        )}
        {shown && s.why && (
          <div style={{position: "absolute", left: vertical ? 80 : 200, right: vertical ? 80 : 200, top: vertical ? 1380 : 790,
                       textAlign: "center", fontFamily: FONT.body, fontWeight: 700, fontSize: vertical ? 44 : 38,
                       color: C.text, opacity: clamp((frame - reveal - 6) / 10),
                       transform: `translateY(${(1 - clamp((frame - reveal - 6) / 12)) * 16}px)`}}>
            <span style={{color: C.accent, fontWeight: 800}}>Why: </span>{s.why}
          </div>
        )}
      </Camera>
    </AbsoluteFill>
  );
};
