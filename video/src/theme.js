// The look of a video. blogwriter/design.py designs a new one for every video (palette, fonts, moving
// background, transitions, pace) and passes it in as `theme`; nothing here is a preset look.
import {loadFont as Inter} from "@remotion/google-fonts/Inter";
import {loadFont as BebasNeue} from "@remotion/google-fonts/BebasNeue";
import {loadFont as SpaceGrotesk} from "@remotion/google-fonts/SpaceGrotesk";
import {loadFont as Unbounded} from "@remotion/google-fonts/Unbounded";
import {loadFont as PlayfairDisplay} from "@remotion/google-fonts/PlayfairDisplay";
import {loadFont as Manrope} from "@remotion/google-fonts/Manrope";
import {loadFont as Oswald} from "@remotion/google-fonts/Oswald";
import {loadFont as Sora} from "@remotion/google-fonts/Sora";
import {loadFont as DMSerifDisplay} from "@remotion/google-fonts/DMSerifDisplay";
import {loadFont as Fraunces} from "@remotion/google-fonts/Fraunces";
import {loadFont as Archivo} from "@remotion/google-fonts/Archivo";
import {loadFont as Syne} from "@remotion/google-fonts/Syne";
import {loadFont as RobotoSlab} from "@remotion/google-fonts/RobotoSlab";
import {loadFont as Anton} from "@remotion/google-fonts/Anton";
import {loadFont as Lora} from "@remotion/google-fonts/Lora";
import {loadFont as IBMPlexSans} from "@remotion/google-fonts/IBMPlexSans";
import {loadFont as Outfit} from "@remotion/google-fonts/Outfit";
import {loadFont as BricolageGrotesque} from "@remotion/google-fonts/BricolageGrotesque";
import {loadFont as InstrumentSerif} from "@remotion/google-fonts/InstrumentSerif";
import {loadFont as Lexend} from "@remotion/google-fonts/Lexend";
import {loadFont as Poppins} from "@remotion/google-fonts/Poppins";
import {loadFont as Montserrat} from "@remotion/google-fonts/Montserrat";
import {loadFont as LibreBaskerville} from "@remotion/google-fonts/LibreBaskerville";
import {loadFont as WorkSans} from "@remotion/google-fonts/WorkSans";
import {loadFont as Rubik} from "@remotion/google-fonts/Rubik";
import {loadFont as BarlowCondensed} from "@remotion/google-fonts/BarlowCondensed";
import {loadFont as ArchivoBlack} from "@remotion/google-fonts/ArchivoBlack";
import {loadFont as AbrilFatface} from "@remotion/google-fonts/AbrilFatface";
import {loadFont as Merriweather} from "@remotion/google-fonts/Merriweather";
import {loadFont as Nunito} from "@remotion/google-fonts/Nunito";
import {loadFont as DMSans} from "@remotion/google-fonts/DMSans";
import {loadFont as mono} from "@remotion/google-fonts/JetBrainsMono";
import {loadFont as telugu} from "@remotion/google-fonts/NotoSansTelugu";
import {loadFont as devanagari} from "@remotion/google-fonts/NotoSansDevanagari";

const LOADERS = {Inter, BebasNeue, SpaceGrotesk, Unbounded, PlayfairDisplay, Manrope, Oswald, Sora, DMSerifDisplay, Fraunces, Archivo, Syne, RobotoSlab, Anton, Lora, IBMPlexSans, Outfit, BricolageGrotesque, InstrumentSerif, Lexend, Poppins, Montserrat, LibreBaskerville, WorkSans, Rubik, BarlowCondensed, ArchivoBlack, AbrilFatface, Merriweather, Nunito, DMSans};
const WEIGHTS = {Inter: ["400", "600", "800", "900"], BebasNeue: ["400"], SpaceGrotesk: ["400", "500", "700"], Unbounded: ["400", "600", "800", "900"], PlayfairDisplay: ["400", "700", "900"], Manrope: ["400", "600", "800"], Oswald: ["400", "500", "700"], Sora: ["400", "600", "800"], DMSerifDisplay: ["400"], Fraunces: ["400", "700", "900"], Archivo: ["400", "600", "800", "900"], Syne: ["400", "600", "800"], RobotoSlab: ["400", "700", "900"], Anton: ["400"], Lora: ["400", "700"], IBMPlexSans: ["400", "600", "700"], Outfit: ["400", "600", "800", "900"], BricolageGrotesque: ["400", "600", "800"], InstrumentSerif: ["400"], Lexend: ["400", "600", "800"], Poppins: ["400", "600", "800", "900"], Montserrat: ["400", "600", "800", "900"], LibreBaskerville: ["400", "700"], WorkSans: ["400", "600", "800"], Rubik: ["400", "600", "800", "900"], BarlowCondensed: ["400", "600", "800"], ArchivoBlack: ["400"], AbrilFatface: ["400"], Merriweather: ["400", "700", "900"], Nunito: ["400", "700", "900"], DMSans: ["400", "600", "800"]};
const loaded = {};
// a font is fetched only when a video uses it, once per render
const face = (key) => {
  if (!LOADERS[key]) key = "Inter";
  if (!loaded[key]) loaded[key] = LOADERS[key]("normal", {weights: WEIGHTS[key], subsets: ["latin"]}).fontFamily;
  return loaded[key];
};
const te = telugu("normal", {weights: ["400", "700"], subsets: ["telugu"]}).fontFamily;
const hi = devanagari("normal", {weights: ["400", "700"], subsets: ["devanagari"]}).fontFamily;
const monoFace = mono("normal", {weights: ["500", "700"], subsets: ["latin"]}).fontFamily;
const indic = `${hi}, ${te}, sans-serif`;        // Hindi and Telugu Shorts fall back to Noto in every look

// used only if no design is passed (a render started by hand)
const FALLBACK = {bg: "#0a0c10", panel: "#141a24", line: "#273041", text: "#f4f1ea", muted: "#97a1ad", accent: "#ffb703",
  hot: "#ff4d4d", cool: "#4cc9f0", violet: "#9b5de5", light: false, back: "aurora", display: "Inter", body: "Inter",
  upper: false, weight: 900, cuts: ["slideBlur", "pushCut", "zoomBlur"], speed: 1, damping: 16, stagger: 2.5};

// C and FONT are read by every component; useTheme() fills them from the design before anything draws.
// Each render uses one design for all of its frames, so this stays deterministic.
export const C = {...FALLBACK};
export const FONT = {display: "", body: "", mono: `${monoFace}, monospace`};
export const SERIES = [];

export function useTheme(design) {
  const t = {...FALLBACK, ...(design && typeof design === "object" ? design : {})};
  Object.assign(C, t);
  FONT.display = `${face(t.display)}, ${indic}`;
  FONT.body = `${face(t.body)}, ${indic}`;
  SERIES.splice(0, SERIES.length, t.accent, t.cool, t.hot, t.violet);
  return t;
}

// "#rrggbb" + alpha -> rgba(), for glows and shades that follow the theme
export const alpha = (hex, a) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};

export const TRANSITION = 15;     // frames two scenes overlap (blogwriter/video.py times the audio with this)
