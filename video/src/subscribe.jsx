// The channel's subscribe moment: once, about a third of the way in, a card slides up in the lower right with the
// owl and the channel's name; a cursor glides in and presses Subscribe, the button turns to Subscribed and the bell
// rings, and the card slides away. It wears the video's own fonts, colours and arrival curve.
import React from "react";
import {Img, staticFile, useCurrentFrame} from "remotion";
import {clamp, ease} from "./fx";
import {Icon} from "./graphics";
import {pop} from "./motion";
import {C, FONT, alpha} from "./theme";

export const SUBSCRIBE_FRAMES = 150;      // how long the card stays (5 s); the captions step aside meanwhile
const RED = "#ff0033";                    // the button's red, as viewers know it

// the cursor's arrow
const Arrow = () => (
  <svg width={46} height={56} viewBox="0 0 23 28" style={{overflow: "visible", filter: "drop-shadow(0 4px 8px rgba(0,0,0,.35))"}}>
    <path d="M1 1 L1 22 L7 17 L11 26 L15 24 L11 15 L19 15 Z" fill="#ffffff" stroke="#111111" strokeWidth={1.6} strokeLinejoin="round"/>
  </svg>
);

export const Subscribe = ({at, name, vertical}) => {
  const frame = useCurrentFrame();
  const t = frame - at;
  if (C.clean || vertical || t < 0 || t > SUBSCRIBE_FRAMES) return null;
  const inP = pop(t);
  const out = ease(clamp((t - (SUBSCRIBE_FRAMES - 18)) / 18));
  const click = 58, done = click + 5;
  const subscribed = t >= done;
  const press = t >= click && t < click + 10 ? Math.sin(((t - click) / 10) * Math.PI) : 0;
  // the cursor comes in from below right and lands on the button, then drifts off
  const move = ease(clamp((t - 18) / 34));
  const leave = ease(clamp((t - 84) / 24));
  const cx = 372 + (1 - move) * 260 + leave * 160, cy = 40 + (1 - move) * 150 + leave * 120;
  const ring = subscribed ? Math.sin((t - done) / 2.2) * Math.max(0, 1 - (t - done) / 40) * 22 : 0;
  return (
    <div style={{position: "absolute", right: 44, bottom: 30, transform: `translateY(${(1 - inP) * 140 + out * 160}px)`,
                 opacity: clamp(inP * 1.6) * (1 - out)}}>
      <div style={{display: "flex", alignItems: "center", gap: 18, padding: "12px 14px 12px 12px", borderRadius: 999,
                   background: alpha(C.panel, 0.94), border: `1.5px solid ${alpha(C.text, 0.12)}`,
                   boxShadow: `0 18px 50px ${alpha("#000000", C.light ? 0.18 : 0.5)}, 0 0 40px ${alpha(C.accent, 0.18)}`}}>
        <Img src={staticFile("logo.png")} style={{width: 68, height: 68, borderRadius: "50%"}}/>
        <div style={{display: "flex", flexDirection: "column", lineHeight: 1.05, marginRight: 4}}>
          <span style={{fontFamily: FONT.display, fontWeight: C.weight, fontSize: 36, color: C.text,
                        textTransform: C.upper ? "uppercase" : "none"}}>{name}</span>
          <span style={{fontFamily: FONT.body, fontWeight: 700, fontSize: 19, color: C.muted, marginTop: 4}}>
            {subscribed ? "Thanks for subscribing" : "Subscribe for more"}
          </span>
        </div>
        <div style={{display: "flex", alignItems: "center", gap: 10, padding: "14px 24px", borderRadius: 999,
                     background: subscribed ? alpha(C.text, 0.1) : RED, color: subscribed ? C.text : "#ffffff",
                     fontFamily: FONT.body, fontWeight: 800, fontSize: 24, letterSpacing: 0.3,
                     transform: `scale(${1 - 0.08 * press})`}}>
          {subscribed && <span style={{display: "inline-flex", transform: `rotate(${ring}deg)`, transformOrigin: "50% 10%"}}>
            <Icon name="bell-ring" size={26} color={C.text} width={2.2}/>
          </span>}
          {subscribed ? "Subscribed" : "Subscribe"}
        </div>
      </div>
      {t > 14 && t < 112 && (
        <div style={{position: "absolute", left: cx, top: cy, transform: `scale(${1 - 0.15 * press})`,
                     opacity: clamp((t - 14) / 6) * (1 - leave)}}>
          <Arrow/>
        </div>
      )}
    </div>
  );
};
