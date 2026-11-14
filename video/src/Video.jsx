// The whole video: shots joined by the theme's transitions, act stings, the channel badge, progress, captions and
// the film finish on top. Rendered silently; blogwriter/video.py lays the mixed narration, music and effects on after.
import React from "react";
import {AbsoluteFill, Img, Sequence, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import {TransitionSeries, springTiming} from "@remotion/transitions";
import {wipe} from "@remotion/transitions/wipe";
import {flip} from "@remotion/transitions/flip";
import {iris} from "@remotion/transitions/iris";
import {clockWipe} from "@remotion/transitions/clock-wipe";
import {pushCut} from "@remotion/transitions/push-cut";
import {CUTS, ChapterSting, Finish, clamp} from "./fx";
import {SCENES} from "./scenes";
import {GRAPHICS} from "./graphics";
import {VIZ_GRAPHICS} from "./viz/graphic";
import {Texture, genCut} from "./gen";
import {DiagramScene} from "./diagram";
import {SUBSCRIBE_FRAMES, Subscribe} from "./subscribe";
import {C, FONT, TRANSITION, alpha, useTheme} from "./theme";
import {LookDefs, LookOverlay, LookStyle} from "./looks";
import {LayoutAudit} from "./audit";

const STING = 26;     // frames the act sting covers before the shot's own animation starts

const cut = (name, width, height) => {
  if (name && typeof name === "object") return genCut(name);      // a transition invented for this video
  if (CUTS[name]) return CUTS[name]();
  if (name === "pushCut") return pushCut({flashColor: C.accent, flashOpacity: 0.25});
  if (name === "iris") return iris({width, height});
  if (name === "clock") return clockWipe({width, height});
  if (name === "flip") return flip({direction: "from-right"});
  return wipe({direction: "from-left"});
};

const Badge = ({channel, vertical}) => (
  <div style={{position: "absolute", left: vertical ? 50 : 70, top: vertical ? 120 : 56, display: "flex", alignItems: "center",
               gap: 14}}>
    <Img src={staticFile("logo.png")} style={{width: vertical ? 72 : 60, height: vertical ? 72 : 60,
                                             filter: `drop-shadow(0 4px 14px ${alpha("#000000", 0.35)})`}}/>
  </div>
);

// karaoke captions for Shorts: the line pops in and the word being spoken lights up
const Caption = ({captions, vertical, aside = 0}) => {
  const frame = useCurrentFrame();
  const c = captions.find((x) => frame >= x.from && frame < x.to);
  if (!c) return null;
  const words = c.text.split(/\s+/);
  const total = words.reduce((n, w) => n + w.length + 1, 0);
  const spoken = clamp((frame - c.from) / Math.max(1, c.to - c.from)) * total;
  const pop = clamp((frame - c.from) / 5);
  let acc = 0;
  return (
    <div style={{position: "absolute", left: 50, right: 50 + aside, top: vertical ? "74%" : undefined, bottom: vertical ? undefined : 34,
                 textAlign: "center", transform: `scale(${0.9 + 0.1 * pop})`}}>
      <span data-caption="1" style={{display: "inline-block", padding: "14px 26px", borderRadius: 24, background: alpha(C.light ? "#ffffff" : "#000000", 0.55),
                    backdropFilter: "blur(10px)", fontFamily: FONT.body, fontWeight: 800, fontSize: vertical ? 62 : 40,
                    lineHeight: 1.35, color: C.text}}>
        {words.map((w, k) => {
          const start = acc;
          acc += w.length + 1;
          const on = spoken >= start && spoken < acc;
          return <span key={k} style={{color: on ? C.accent : C.text, display: "inline-block",
                                       transform: `scale(${on ? 1.1 : 1})`, marginRight: 14}}>{w}</span>;
        })}
      </span>
    </div>
  );
};

// film bars for the big moments (the cold open, each new act): they slide in, hold, and slide away
const Letterbox = ({spans, vertical}) => {
  const frame = useCurrentFrame();
  const {height} = useVideoConfig();
  if (vertical || C.clean) return null;
  const k = spans.reduce((m, [a, b]) => Math.max(m, Math.min(clamp((frame - a) / 12), clamp((b - frame) / 16))), 0);
  if (k <= 0) return null;
  const h = height * 0.1 * (1 - Math.pow(1 - k, 3));
  return (
    <>
      <div style={{position: "absolute", left: 0, right: 0, top: 0, height: h, background: "#000"}}/>
      <div style={{position: "absolute", left: 0, right: 0, bottom: 0, height: h, background: "#000"}}/>
    </>
  );
};

export const Video = ({scenes, captions = [], channel = "", theme = null, clean = false, subscribe = null, audit = false}) => {
  useTheme(theme);
  C.clean = clean;              // a frame for the thumbnail: the visual alone
  const frame = useCurrentFrame();
  const {width, height, durationInFrames} = useVideoConfig();
  const vertical = height > width;
  const starts = scenes.reduce((acc, s, k) => [...acc, k ? acc[k - 1] + scenes[k - 1].frames - TRANSITION : 0], []);
  const bars = scenes.map((s, k) => (k === 0 ? [0, Math.min(s.frames, 150)] : s.chapter ? [starts[k], starts[k] + STING + 45] : null))
    .filter(Boolean);
  return (
    <AbsoluteFill className="look-root" style={{background: clean ? "transparent" : C.bg, fontVariantNumeric: "lining-nums",
                                                 filter: C.look && C.look.mono ? "grayscale(1) contrast(1.06)" : undefined}}>
      <LookDefs/>
      <LookStyle/>
      <TransitionSeries>
        {scenes.map((s, i) => {
          // a shot the art director gave a motion graphic plays that instead of its template
          // a diagram drawn for this sentence beats both
          const Scene = (s.diagram && DiagramScene) || (s.graphic && (GRAPHICS[s.graphic.type] || VIZ_GRAPHICS[s.graphic.type])) || SCENES[s.kind] || SCENES.photo;
          const scene = (x) => <Scene s={x} i={i} vertical={vertical}/>;
          // a shot that opens an act starts its own animation once the sting has passed; its cues move with it
          const late = (f) => (f == null ? f : Math.max(0, f - STING));
          const shot = s.chapter ? {...s, cue: late(s.cue), hcue: late(s.hcue), think: late(s.think), reveal: late(s.reveal), graphic: s.graphic && {
            ...s.graphic, at: late(s.graphic.at), words: (s.graphic.words || []).map(late),
            center: s.graphic.center && {...s.graphic.center, at: late(s.graphic.center.at)},
            nodes: (s.graphic.nodes || []).map((nd) => ({...nd, at: late(nd.at)}))},
            parts: s.parts && s.parts.map((p) => ({...p, at: late(p.at)})),
            steps: s.steps && s.steps.map((p) => ({...p, at: late(p.at)})),
            diagram: s.diagram && {elements: s.diagram.elements.map((e) => {
              const m = (x) => x && {...x, at: late(x.at)};
              return {...e, at: late(e.at), move: m(e.move), glow: m(e.glow), hide: m(e.hide), mark: m(e.mark), fit: m(e.fit)};
            })}} : s;
          return (
            <React.Fragment key={i}>
              {i > 0 && <TransitionSeries.Transition presentation={cut(C.cuts[i % C.cuts.length], width, height)}
                                                     timing={springTiming({config: {damping: 200}, durationInFrames: TRANSITION})}/>}
              <TransitionSeries.Sequence durationInFrames={s.frames}>
                {s.chapter ? (
                  <>
                    <Sequence from={STING - 6}>{scene(shot)}</Sequence>
                    <ChapterSting kicker={s.chapter.kicker} title={s.chapter.title} vertical={vertical}/>
                  </>
                ) : scene(s)}
              </TransitionSeries.Sequence>
            </React.Fragment>
          );
        })}
      </TransitionSeries>
      <Finish/>
      {!clean && <Texture/>}
      <LookOverlay/>
      <Letterbox spans={bars} vertical={vertical}/>
      {!clean && <Badge channel={channel} vertical={vertical}/>}
      {/* while the subscribe card is up, the captions step aside so the two never overlap */}
      <Caption captions={captions} vertical={vertical} aside={subscribe && !clean && !vertical
        ? 560 * clamp(Math.min((frame - subscribe.at) / 12, (subscribe.at + SUBSCRIBE_FRAMES - frame) / 12)) : 0}/>
      {subscribe && <Subscribe at={subscribe.at} name={subscribe.name || channel} vertical={vertical}/>}
      {audit && <LayoutAudit key={frame}/>}
      <div style={{position: "absolute", left: 0, top: 0, height: clean ? 0 : 5, background: `linear-gradient(90deg, ${C.cool}, ${C.accent})`,
                   width: `${(100 * frame) / Math.max(1, durationInFrames - 1)}%`, boxShadow: `0 0 12px ${C.accent}`}}/>
    </AbsoluteFill>
  );
};
