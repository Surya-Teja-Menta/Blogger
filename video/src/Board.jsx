// One-take evidence board: every scene is a card pinned on a big board, joined by red string. The camera
// glides from card to card without a cut. The cards carry no sentences (numbers, photos, source names only),
// so one picture track fits every language's audio; the words live in the audio and the subtitles.
// Only what is near the camera is drawn (the background is a screen-space pattern), which keeps renders fast.
import React from "react";
import {AbsoluteFill, Audio, Img, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig} from "remotion";

export const FONT = "'Noto Sans', 'Noto Sans Devanagari', 'Noto Sans Telugu', 'Nirmala UI', 'Segoe UI', sans-serif";
const PAPER = "#f3eee4";
const INK = "#1d1d1f";
const MOVE = 26;   // frames the camera takes to travel to the next card

const starts = (scenes) => scenes.reduce((acc, s, i) => [...acc, i ? acc[i - 1] + scenes[i - 1].frames : 0], []);

function layout(i, vertical) {
  // a zigzag, so the string between cards is visible while the camera travels
  const side = i % 2 ? 1 : -1;
  return vertical ? {x: side * 200, y: i * 1500, w: 900, h: 1180} : {x: i * 1650, y: side * 330, w: 1300, h: 760};
}

const tilt = (i) => ((i * 37) % 5) - 2;

function countUp(text, p) {
  // "$115B" counts 0 -> 115 while keeping its prefix, suffix and decimals; years are shown as they are
  const m = /^([^\d]*)([\d][\d,]*\.?\d*)(.*)$/.exec(text || "");
  if (!m || /^(19|20)\d\d$/.test(text)) return text;
  const target = parseFloat(m[2].replace(/,/g, ""));
  const decimals = (m[2].split(".")[1] || "").length;
  const value = (target * p).toFixed(decimals);
  const shown = m[2].includes(",") ? Number(value).toLocaleString("en-US", {minimumFractionDigits: decimals}) : value;
  return m[1] + shown + m[3];
}

const Pin = ({style}) => (
  <div style={{position: "absolute", width: 30, height: 30, borderRadius: 15, ...style,
               background: "radial-gradient(circle at 35% 35%, #ff6b6b, #a4161a)", boxShadow: "0 3px 5px rgba(0,0,0,.45)"}}/>
);

const Photo = ({src, box, zoom}) => (
  <div style={{position: "absolute", left: box.left, top: box.top, width: box.width, height: box.height, background: "#fff",
               padding: 12, transform: `rotate(${box.rot}deg)`, boxShadow: "0 10px 22px rgba(0,0,0,.35)"}}>
    <div style={{width: "100%", height: "100%", overflow: "hidden", background: "#ddd"}}>
      <Img src={staticFile(src)} style={{width: "100%", height: "100%", objectFit: "cover", transform: `scale(${zoom})`}}/>
    </div>
    <Pin style={{top: -12, left: "50%", marginLeft: -15}}/>
  </div>
);

// where the prints go: one large, or two/three overlapping like cuttings
const SPOTS = {
  long: [[{left: 60, top: 70, width: 700, height: 560, rot: -2}],
         [{left: 50, top: 60, width: 560, height: 420, rot: -3}, {left: 330, top: 300, width: 470, height: 360, rot: 4}],
         [{left: 40, top: 50, width: 520, height: 380, rot: -3}, {left: 380, top: 250, width: 420, height: 320, rot: 4},
          {left: 90, top: 420, width: 340, height: 260, rot: 2}]],
  tall: [[{left: 70, top: 80, width: 760, height: 600, rot: -2}],
         [{left: 50, top: 70, width: 600, height: 440, rot: -3}, {left: 280, top: 360, width: 560, height: 400, rot: 4}],
         [{left: 40, top: 60, width: 560, height: 400, rot: -3}, {left: 330, top: 300, width: 520, height: 380, rot: 4},
          {left: 90, top: 560, width: 420, height: 260, rot: 2}]],
};

function Card({scene, i, vertical, local, accent}) {
  const {fps} = useVideoConfig();
  const {w, h} = layout(i, vertical);
  const arrived = spring({frame: local - MOVE / 2, fps, config: {damping: 200}});
  const zoom = 1 + 0.08 * Math.min(1, Math.max(0, local / Math.max(1, scene.frames)));
  const images = (scene.images || []).slice(0, 3);
  const spots = images.length ? SPOTS[vertical ? "tall" : "long"][images.length - 1] : [];
  // the figure sits beside the photos (wide) or under them (tall); alone it fills the card
  const numberBox = !images.length ? {left: 0, right: 0, top: h / 2 - 120, textAlign: "center", fontSize: vertical ? 220 : 240}
    : vertical ? {left: 40, right: 40, top: 770, textAlign: "center", fontSize: 170}
    : {left: 800, right: 50, top: 260, textAlign: "center", fontSize: 150};
  return (
    <div style={{position: "absolute", left: -w / 2, top: -h / 2, width: w, height: h, background: PAPER,
                 transform: `rotate(${tilt(i)}deg)`, boxShadow: "0 18px 40px rgba(0,0,0,.5)", fontFamily: FONT}}>
      <Pin style={{top: 14, left: 14}}/><Pin style={{top: 14, right: 14}}/>
      {!images.length && scene.kind !== "outro" && (
        <div style={{position: "absolute", left: 50, top: 10, fontSize: 300, fontWeight: 900, color: "rgba(0,0,0,.05)"}}>
          {String(i + 1).padStart(2, "0")}
        </div>
      )}
      {images.map((src, k) => <Photo key={src + k} src={src} box={spots[k]} zoom={zoom}/>)}
      {scene.kind === "quote" && (
        <div style={{position: "absolute", right: 60, top: 0, fontSize: 300, lineHeight: 1, color: accent,
                     fontFamily: "Georgia, serif", opacity: arrived}}>&ldquo;</div>
      )}
      {scene.kind === "outro" && (
        <div style={{position: "absolute", left: w / 2 - 190, top: vertical ? 250 : 120, opacity: arrived}}>
          {[2, 1, 0].map((k) => (
            <div key={k} style={{position: "absolute", left: k * 24, top: k * 24, width: 330, height: 430, background: "#fff",
                                 boxShadow: "0 8px 20px rgba(0,0,0,.3)", transform: `rotate(${k * 3 - 3}deg)`}}>
              {k === 0 && <div style={{margin: 40, fontSize: 90, fontWeight: 900, color: accent}}>PDF</div>}
              {k === 0 && [0, 1, 2, 3, 4].map((r) => <div key={r} style={{margin: "18px 40px", height: 14, background: "#ccc", width: 250 - r * 28}}/>)}
            </div>
          ))}
          <div style={{position: "absolute", left: 130, top: 480, fontSize: 140, color: accent,
                       transform: `translateY(${10 * Math.sin(local / 6)}px)`}}>&darr;</div>
        </div>
      )}
      {scene.number && (
        <div style={{position: "absolute", ...numberBox, fontWeight: 900, color: accent, letterSpacing: -3, lineHeight: 1,
                     opacity: arrived, whiteSpace: "nowrap"}}>
          {countUp(scene.number, Math.min(1, Math.max(0, (local - MOVE) / 30)))}
        </div>
      )}
      {scene.source && (
        <div style={{position: "absolute", right: 40, bottom: 34, padding: "10px 22px", background: INK, color: "#fff",
                     fontSize: vertical ? 40 : 34, fontWeight: 600, transform: "rotate(-1.5deg)", opacity: arrived}}>
          {scene.source}
        </div>
      )}
    </div>
  );
}

export const Board = ({scenes, captions = [], accent = "#e63946"}) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const vertical = height > width;
  const begin = starts(scenes);
  let cur = 0;
  while (cur + 1 < scenes.length && frame >= begin[cur + 1]) cur++;
  const local = frame - begin[cur];

  // camera: glide from the previous card to this one (pulling back mid-way), then drift in slowly
  const p = cur === 0 ? 1 : spring({frame: local, fps, config: {damping: 200}, durationInFrames: MOVE});
  const a = layout(Math.max(0, cur - 1), vertical), b = layout(cur, vertical);
  const camX = a.x + (b.x - a.x) * p, camY = a.y + (b.y - a.y) * p;
  const fit = vertical ? width / 1180 : width / 1720;     // the board shows around the card
  const zoom = fit * (1 - 0.25 * Math.sin(Math.PI * p)) * (1 + 0.04 * local / Math.max(1, scenes[cur].frames));
  const toScreen = (q) => ({x: width / 2 + (q.x - camX) * zoom, y: height / 2 + (q.y - camY) * zoom});

  const pins = scenes.map((_, i) => layout(i, vertical));
  const near = [cur - 1, cur, cur + 1].filter((i) => i >= 0 && i < scenes.length);
  const caption = captions.find((c) => frame >= c.from && frame < c.to);
  const grid = 90 * zoom;

  return (
    <AbsoluteFill style={{backgroundColor: "#171310", overflow: "hidden",
                          backgroundImage: "linear-gradient(rgba(255,255,255,.035) 2px, transparent 2px)," +
                                           "linear-gradient(90deg, rgba(255,255,255,.035) 2px, transparent 2px)",
                          backgroundSize: `${grid}px ${grid}px`,
                          backgroundPosition: `${-camX * zoom}px ${-camY * zoom}px`}}>
      <svg style={{position: "absolute", inset: 0}} width={width} height={height}>
        {near.filter((i) => i > 0).map((i) => {
          const from = toScreen(pins[i - 1]), to = toScreen(pins[i]);
          const len = Math.hypot(to.x - from.x, to.y - from.y);
          const drawn = i < cur ? 1 : i === cur ? p : 0;
          return <line key={i} x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="#c1121f" strokeWidth={6 * zoom}
                       strokeDasharray={len} strokeDashoffset={len * (1 - drawn)}/>;
        })}
      </svg>
      {near.map((i) => {
        const at = toScreen(pins[i]);
        return (
          <div key={i} style={{position: "absolute", left: at.x, top: at.y, transform: `scale(${zoom})`}}>
            <Card scene={scenes[i]} i={i} vertical={vertical} local={i === cur ? local : i < cur ? scenes[i].frames : 0}
                  accent={accent}/>
          </div>
        );
      })}

      {caption && (
        <div style={{position: "absolute", left: 50, right: 50, top: vertical ? height * 0.79 : undefined,
                     bottom: vertical ? undefined : 70, textAlign: "center"}}>
          <span style={{display: "inline", background: "rgba(0,0,0,.8)", color: "#fff", fontFamily: FONT,
                        fontSize: vertical ? 60 : 46, fontWeight: 800, lineHeight: 1.45, padding: "6px 18px",
                        boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone"}}>{caption.text}</span>
        </div>
      )}
      <div style={{position: "absolute", left: 0, bottom: 0, height: 8, background: accent,
                   width: `${(100 * frame) / Math.max(1, durationInFrames - 1)}%`}}/>

      {scenes.map((s, i) => s.audio && (
        <Sequence key={"a" + i} from={begin[i] + 8}><Audio src={staticFile(s.audio)}/></Sequence>
      ))}
    </AbsoluteFill>
  );
};
