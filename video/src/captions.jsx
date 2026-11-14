// Six caption styles; blogwriter/palettes.py picks one per video (theme.caption), so the captions are not the same box
// on every video. Each is {box, word(on)}: the style of the caption line and of one word, lit while it is spoken.
// All are drawn from the theme's colours and keep the same font size and position (Video.jsx), so the layout audit
// and the safe areas do not change.
import {C, FONT, alpha} from "./theme";

const lum = (hex) => {
  const n = parseInt(hex.slice(1), 16), ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
};
const ink = (hex) => (lum(hex) > 0.45 ? "#111111" : "#ffffff");          // readable text on that colour

export const CAPTION_STYLES = {
  // glass pill: the original
  pill: () => ({
    box: {padding: "14px 26px", borderRadius: 24, background: alpha(C.light ? "#ffffff" : "#000000", 0.55),
          backdropFilter: "blur(10px)", fontFamily: FONT.body, fontWeight: 800, color: C.text},
    word: (on) => ({color: on ? C.accent : C.text, transform: `scale(${on ? 1.06 : 1})`}),
  }),
  // condensed capitals on the picture, the spoken word swiped with a highlighter
  highlighter: () => {
    const base = C.light ? "#111111" : "#ffffff", halo = C.light ? "#ffffff" : "#000000";
    return {
      box: {padding: "6px 14px", fontFamily: FONT.display, fontWeight: C.weight, textTransform: "uppercase", letterSpacing: 1,
            color: base, textShadow: `0 3px 0 ${alpha(halo, 0.5)}, 0 0 14px ${alpha(halo, 0.65)}`, lineHeight: 1.5},
      word: (on) => (on ? {background: C.accent, color: ink(C.accent), borderRadius: 8, padding: "0 0.18em", textShadow: "none"} : {}),
    };
  },
  // plain subtitle: no box, a soft halo, the spoken word in the accent
  clean: () => {
    const base = C.light ? "#111111" : "#ffffff", halo = C.light ? "#ffffff" : "#000000";
    return {
      box: {padding: "4px 10px", fontFamily: FONT.body, fontWeight: 700, color: base,
            textShadow: `0 2px 2px ${alpha(halo, 0.85)}, 0 0 16px ${alpha(halo, 0.8)}, 0 0 4px ${alpha(halo, 0.9)}`},
      word: (on) => ({color: on ? C.accent : base}),
    };
  },
  // typewriter on a paper strip, the spoken word underlined by a marker
  paper: (vertical) => ({
    box: {padding: "10px 24px", background: C.light ? "#fffdf6" : "#f3ecdc", color: "#1a1a1a", fontFamily: FONT.mono, fontWeight: 700,
          borderRadius: 4, transform: "rotate(-0.6deg)", boxShadow: "0 6px 18px rgba(0,0,0,0.35)", fontSize: vertical ? 54 : 34},
    word: (on) => (on ? {background: `linear-gradient(transparent 58%, ${alpha(C.accent, 0.6)} 58%)`} : {}),
  }),
  // capitals on a bold bar, the spoken word in a white pill
  redbar: () => ({
    box: {padding: "8px 22px", background: C.hot, color: ink(C.hot), fontFamily: FONT.display, fontWeight: C.weight,
          textTransform: "uppercase", letterSpacing: 1, borderRadius: 6},
    word: (on) => (on ? {background: ink(C.hot), color: C.hot, borderRadius: 8, padding: "0 0.18em"} : {}),
  }),
  // neon: glowing type in the accent, no box
  glow: () => {
    const halo = C.light ? "#ffffff" : "#000000";
    return {
      box: {padding: "6px 12px", fontFamily: FONT.display, fontWeight: C.weight, color: C.light ? "#111111" : "#ffffff",
            textShadow: `0 0 8px ${alpha(C.accent, 0.85)}, 0 0 26px ${alpha(C.accent, 0.5)}, 0 2px 4px ${alpha(halo, 0.8)}`},
      word: (on) => ({color: on ? C.accent : undefined, transform: `scale(${on ? 1.08 : 1})`}),
    };
  },
};

export const captionStyle = (name, vertical) => (CAPTION_STYLES[name] || CAPTION_STYLES.pill)(vertical);
