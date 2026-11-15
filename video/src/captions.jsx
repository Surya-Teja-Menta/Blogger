// The caption style (one: the glass pill, the owner's choice; the table keeps the door open for more); blogwriter/palettes.py picks one per video (theme.caption), so the captions are not the same box
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
};

export const captionStyle = (name, vertical) => (CAPTION_STYLES[name] || CAPTION_STYLES.pill)(vertical);
