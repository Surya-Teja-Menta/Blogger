// Motion graphics: diagrams built from line icons, drawn on, connected and kept moving. blogwriter/graphics.py lets a
// language model pick one per shot and fill it (s.graphic = {type, center, nodes, ...}); each node carries `at`, the
// frame its word is spoken, so every piece lands on the voice. Layouts are fixed here, so they always look right.
import React from "react";
import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {icons} from "lucide";
import {Backdrop, Camera, Kicker, Particles, Words, clamp, countUp, ease} from "./fx";
import {C, FONT, SERIES, alpha} from "./theme";

const pascal = (name) => String(name || "").replace(/(^|-)([a-z0-9])/g, (_, __, c) => c.toUpperCase());

// a Lucide icon whose strokes draw themselves on (draw 0 -> 1)
export const Icon = ({name, size = 120, color, draw = 1, width = 1.5}) => {
  const node = icons[pascal(name)] || icons.Sparkles;
  const col = color || C.accent;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={col} strokeWidth={width}
         strokeLinecap="round" strokeLinejoin="round"
         style={{overflow: "visible", filter: `drop-shadow(0 0 ${size / 14}px ${alpha(col, 0.55)})`}}>
      {node[2].map(([tag, a], k) => React.createElement(tag, {...a, key: k, pathLength: 1, strokeDasharray: 1,
                                                              strokeDashoffset: 1 - clamp(draw)}))}
    </svg>
  );
};

// glass disc with a drawn-on icon, a ripple when it lands and a slow breathing pulse after
const Disc = ({icon, at, size, color, label, labelSize, below = true}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: frame - at, fps, config: {damping: 12, mass: 0.8}});
  const t = frame - at;
  const ripple = ((t % 70) + 70) % 70 / 70;
  return (
    <div style={{display: "flex", flexDirection: below ? "column" : "row", alignItems: "center", gap: below ? 22 : 30,
                 opacity: clamp(p * 2), transform: `scale(${(0.4 + 0.6 * p) * (1 + 0.025 * Math.sin(t / 11))})`}}>
      <div style={{position: "relative", width: size, height: size, flexShrink: 0}}>
        {t > 0 && <div style={{position: "absolute", inset: 0, borderRadius: "50%", border: `3px solid ${color}`,
                               transform: `scale(${1 + ripple * 0.7})`, opacity: (1 - ripple) * 0.6}}/>}
        <div style={{position: "absolute", inset: 0, borderRadius: "50%", display: "flex", alignItems: "center",
                     justifyContent: "center", border: `3px solid ${alpha(color, 0.75)}`,
                     background: `radial-gradient(circle at 35% 30%, ${alpha(color, 0.3)}, ${alpha(C.panel, 0.92)} 72%)`,
                     boxShadow: `0 0 ${size / 2}px ${alpha(color, 0.35)}, inset 0 0 ${size / 4}px ${alpha(color, 0.18)}`}}>
          <Icon name={icon} size={size * 0.5} color={color} draw={ease((t - 3) / 24)}/>
        </div>
      </div>
      {label && (
        <div style={{fontFamily: FONT.body, fontWeight: 800, fontSize: labelSize, color: C.text, lineHeight: 1.08,
                     textAlign: below ? "center" : "left", maxWidth: below ? size * 1.9 : 640,
                     opacity: clamp((t - 6) / 10), transform: `translateY(${(1 - ease((t - 6) / 14)) * 20}px)`,
                     textShadow: `0 2px 20px ${alpha(C.bg, 0.8)}`}}>{label}</div>
      )}
    </div>
  );
};

// cubic curve helpers: a gentle arc between two points, and a point along it
const arc = (a, b, bend) => {
  const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const c = [mx - dy * bend, my + dx * bend];
  return {d: `M${a[0]},${a[1]} Q${c[0]},${c[1]} ${b[0]},${b[1]}`, c};
};
const along = (a, c, b, t) => [(1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t * t * b[0],
                               (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t * t * b[1]];

// a link that draws itself from a to b once `at` passes, then carries glowing packets along it for good
const Link = ({a, b, at, bend = 0.12, color, dashed}) => {
  const frame = useCurrentFrame();
  const draw = ease((frame - at) / 22);
  const {d, c} = arc(a, b, bend);
  return (
    <g>
      <path d={d} fill="none" stroke={alpha(color, 0.25)} strokeWidth={14} strokeLinecap="round" pathLength={1}
            strokeDasharray={1} strokeDashoffset={1 - draw}/>
      <path d={d} fill="none" stroke={color} strokeWidth={4} strokeLinecap="round" pathLength={1}
            strokeDasharray={dashed ? "0.02 0.015" : 1} strokeDashoffset={dashed ? -frame / 300 : 1 - draw}
            opacity={dashed ? draw : 1}/>
      {draw >= 1 && [0, 1, 2].map((k) => {
        const t = ((frame - at) / 45 + k / 3) % 1;
        const [x, y] = along(a, c, b, t);
        return <circle key={k} cx={x} cy={y} r={9} fill={C.text} opacity={Math.sin(Math.PI * t)}
                       style={{filter: `drop-shadow(0 0 10px ${color}) drop-shadow(0 0 22px ${color})`}}/>;
      })}
    </g>
  );
};

const Header = ({s, vertical}) => (
  <div style={{position: "absolute", left: vertical ? 70 : 120, right: vertical ? 70 : 120, top: vertical ? 250 : 112}}>
    <Kicker text={s.kicker} size={vertical ? 32 : 26}/>
    <Words text={s.headline} highlight={s.highlight} size={vertical ? 84 : 78} delay={2} markAt={s.hcue}
           maxWidth={vertical ? 940 : 1500}/>
  </div>
);

const Frame = ({s, i, vertical, children, header = true, hue}) => (
  <AbsoluteFill>
    <Backdrop word={s.kicker} i={i} hue={hue}/>
    <Particles n={30} seed={`g${i}`}/>
    <Camera i={i} amount={0.5}>
      {children}
      {header && <Header s={s} vertical={vertical}/>}
    </Camera>
  </AbsoluteFill>
);

// ---- flow: A -> B -> C, the path drawn as each step is named, data running along it -------------------------
const Flow = ({s, i, vertical}) => {
  const {width, height} = useVideoConfig();
  const nodes = s.graphic.nodes;
  const n = nodes.length;
  const size = vertical ? 200 : n > 3 ? 210 : 240;
  const pos = nodes.map((_, k) => vertical
    ? [width / 2, 720 + (k + 0.5) * (1050 / n)]
    : [width * (0.14 + 0.72 * (n === 1 ? 0.5 : k / (n - 1))), height * 0.62]);
  return (
    <Frame s={s} i={i} vertical={vertical}>
      <svg width={width} height={height} style={{position: "absolute"}}>
        {pos.slice(1).map((b, k) => <Link key={k} a={pos[k]} b={b} at={nodes[k + 1].at - 10}
                                          bend={vertical ? 0.25 * (k % 2 ? 1 : -1) : 0.18 * (k % 2 ? 1 : -1)}
                                          color={SERIES[k % SERIES.length]}/>)}
      </svg>
      {nodes.map((nd, k) => (
        <div key={k} style={{position: "absolute", left: pos[k][0], top: pos[k][1],
                             transform: vertical ? "translate(-100px, -50%)" : "translate(-50%, -" + size / 2 + "px)"}}>
          <Disc icon={nd.icon} at={nd.at} size={size} color={SERIES[k % SERIES.length]} label={nd.label}
                labelSize={vertical ? 46 : 40} below={!vertical}/>
        </div>
      ))}
    </Frame>
  );
};

// ---- hub: one centre with its players around it, connected by spokes, rings turning behind -------------------
const Hub = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const g = s.graphic, nodes = g.nodes, n = nodes.length;
  const cx = width / 2, cy = vertical ? 1180 : height * 0.61;
  const rx = vertical ? 360 : 640, ry = vertical ? 470 : 250;
  const turn = frame * 0.0015;
  const pos = nodes.map((_, k) => {
    const a = -Math.PI / 2 + (2 * Math.PI * k) / n + turn;
    return [cx + rx * Math.cos(a), cy + ry * Math.sin(a)];
  });
  const centerAt = g.center.at;
  return (
    <Frame s={s} i={i} vertical={vertical}>
      <svg width={width} height={height} style={{position: "absolute"}}>
        {[1, 1.45, 1.9].map((r, k) => (
          <ellipse key={k} cx={cx} cy={cy} rx={rx * r * 0.55} ry={ry * r * 0.55} fill="none" stroke={alpha(C.text, 0.1)}
                   strokeWidth={2} strokeDasharray="6 14" strokeDashoffset={frame * (k % 2 ? 0.6 : -0.6)}/>
        ))}
        {pos.map((p, k) => <Link key={k} a={[cx, cy]} b={p} at={nodes[k].at - 8} bend={0.04}
                                 color={SERIES[(k + 1) % SERIES.length]}/>)}
      </svg>
      <div style={{position: "absolute", left: cx, top: cy, transform: "translate(-50%, -50%)"}}>
        <Disc icon={g.center.icon} at={centerAt} size={vertical ? 260 : 250} color={C.accent}/>
      </div>
      <div style={{position: "absolute", left: cx, top: cy + (vertical ? 150 : 145), transform: "translateX(-50%)",
                   fontFamily: FONT.display, fontWeight: C.weight, fontSize: vertical ? 54 : 46, color: C.text,
                   whiteSpace: "nowrap", opacity: clamp((frame - centerAt - 6) / 10),
                   textTransform: C.upper ? "uppercase" : "none"}}>{g.center.label}</div>
      {nodes.map((nd, k) => (
        <div key={k} style={{position: "absolute", left: pos[k][0], top: pos[k][1], transform: "translate(-50%, -60px)"}}>
          <Disc icon={nd.icon} at={nd.at} size={vertical ? 150 : 120} color={SERIES[(k + 1) % SERIES.length]}
                label={nd.label} labelSize={vertical ? 40 : 34}/>
        </div>
      ))}
    </Frame>
  );
};

// ---- grid: a unit chart, 100 icons with the share filled in a sweep, the figure counting up beside it ---------
const Grid = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const g = s.graphic;
  const pct = clamp(parseFloat(String(g.number).replace(/,/g, "")) / 100);
  const at = g.at;
  const cell = vertical ? 82 : 58;
  const fill = ease((frame - at) / 50) * pct * 100;
  const grid = (
    <div style={{display: "grid", gridTemplateColumns: `repeat(10, ${cell}px)`, gap: vertical ? 10 : 8}}>
      {Array.from({length: 100}, (_, k) => {
        const on = k < fill;
        const show = clamp((frame - 4 - k * 0.25) / 8);
        return (
          <div key={k} style={{opacity: show, transform: `scale(${(0.5 + 0.5 * show) * (on ? 1.06 : 0.9)})`}}>
            <Icon name={g.icon} size={cell} color={on ? C.accent : alpha(C.text, 0.26)} width={on ? 2 : 1.5}/>
          </div>
        );
      })}
    </div>
  );
  const figure = (
    <div style={{display: "flex", flexDirection: "column", gap: 14, maxWidth: vertical ? 900 : 640}}>
      <div style={{fontFamily: FONT.display, fontWeight: C.weight, fontSize: vertical ? 190 : 200, lineHeight: 0.9,
                   color: C.accent, textShadow: `0 0 60px ${alpha(C.accent, 0.45)}`}}>
        {countUp(g.number, ease((frame - at) / 50))}
      </div>
      <div style={{fontFamily: FONT.body, fontWeight: 800, fontSize: vertical ? 52 : 46, color: C.text, lineHeight: 1.15,
                   opacity: clamp((frame - at - 8) / 12)}}>{g.label}</div>
    </div>
  );
  return (
    <Frame s={s} i={i} vertical={vertical}>
      <AbsoluteFill style={{flexDirection: vertical ? "column" : "row", alignItems: "center", justifyContent: "center",
                            gap: vertical ? 70 : 130, paddingTop: vertical ? 420 : 230}}>
        {figure}
        {grid}
      </AbsoluteFill>
    </Frame>
  );
};

// ---- kinetic: the headline slams in word by word over turning shapes, the key word boxed --------------------
const Kinetic = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const g = s.graphic;
  const words = (s.headline || "").split(/\s+/).filter(Boolean);
  const mark = (s.highlight || "").toLowerCase().split(/\s+/).filter(Boolean);
  const longest = Math.max(...words.map((w) => w.length), 4);
  const size = Math.min(vertical ? 150 : 180, ((vertical ? 920 : 1320) / longest) * 1.6);
  const ghost = (words.find((w) => mark.includes(w.toLowerCase().replace(/[^\w]/g, ""))) || words[0] || "").toUpperCase();
  return (
    <AbsoluteFill>
      <Backdrop word="" i={i}/>
      <AbsoluteFill style={{alignItems: "center", justifyContent: "center", overflow: "hidden"}}>
        <div style={{fontFamily: FONT.display, fontWeight: 900, fontSize: vertical ? 420 : 520, whiteSpace: "nowrap",
                     color: "transparent", WebkitTextStroke: `3px ${alpha(C.text, 0.08)}`,
                     transform: `translateX(${200 - frame * 1.6}px)`}}>{ghost}</div>
      </AbsoluteFill>
      <svg width={width} height={height} style={{position: "absolute"}}>
        {[0, 1, 2, 3].map((k) => {
          const x = width * [0.15, 0.85, 0.78, 0.2][k], y = height * [0.22, 0.25, 0.8, 0.78][k];
          const r = [90, 60, 120, 50][k];
          const p = ease((frame - 4 - k * 5) / 20);
          return k % 2
            ? <rect key={k} x={x - r} y={y - r} width={2 * r} height={2 * r} rx={18} fill="none" stroke={SERIES[k]}
                    strokeWidth={4} opacity={0.5 * p} transform={`rotate(${frame * 0.6 + k * 20} ${x} ${y}) scale(1)`}/>
            : <circle key={k} cx={x} cy={y} r={r * p} fill="none" stroke={SERIES[k]} strokeWidth={4} opacity={0.5}
                      strokeDasharray="10 12" strokeDashoffset={frame}/>;
        })}
        {[0, 1].map((k) => {
          const p = ease((frame - 10 - k * 8) / 25);
          const y = height * (k ? 0.74 : 0.27);
          return <line key={`l${k}`} x1={k ? width : 0} y1={y} x2={k ? width - width * 0.42 * p : width * 0.42 * p} y2={y}
                       stroke={k ? C.cool : C.accent} strokeWidth={6} strokeLinecap="round"/>;
        })}
      </svg>
      {(g.nodes || []).slice(0, 2).map((nd, k) => (
        <div key={k} style={{position: "absolute", left: k ? undefined : (vertical ? 70 : 90), right: k ? (vertical ? 70 : 90) : undefined,
                             top: vertical ? (k ? 1560 : 300) : (k ? 120 : 790),
                             transform: `translateY(${Math.sin((frame + k * 40) / 25) * 14}px)`}}>
          <Disc icon={nd.icon} at={nd.at} size={vertical ? 170 : 150} color={SERIES[(k + 1) % SERIES.length]}/>
        </div>
      ))}
      <Camera i={i} amount={0.4}>
        <AbsoluteFill style={{alignItems: "center", justifyContent: "center", padding: vertical ? "0 70px" : "0 300px"}}>
          <div style={{display: "flex", flexWrap: "wrap", justifyContent: "center", gap: `${size * 0.1}px ${size * 0.28}px`,
                       maxWidth: vertical ? 940 : 1320}}>
            {words.map((w, k) => {
              const at = (g.words && g.words[k]) ?? 4 + k * 4;
              const p = spring({frame: frame - at, fps, config: {damping: 11, mass: 0.7}});
              const on = mark.includes(w.toLowerCase().replace(/[^\w]/g, ""));
              const box = ease((frame - at - 4) / 10);
              return (
                <span key={k} style={{position: "relative", display: "inline-block", fontFamily: FONT.display,
                                      fontWeight: C.weight, fontSize: size, lineHeight: 1.05, color: on && box > 0.35 ? C.bg : C.text,
                                      textTransform: C.upper ? "uppercase" : "none", opacity: clamp(p * 1.5),
                                      transform: `translateY(${(1 - p) * 120}px) scale(${0.6 + 0.4 * p}) rotate(${(1 - p) * (k % 2 ? 8 : -8)}deg)`}}>
                  {on && <span style={{position: "absolute", left: -14, right: -14, top: "8%", bottom: "4%", background: C.accent,
                                       borderRadius: 10, transformOrigin: "left", transform: `scaleX(${box})`, zIndex: -1,
                                       boxShadow: `0 0 50px ${alpha(C.accent, 0.5)}`}}/>}
                  {w}
                </span>
              );
            })}
          </div>
        </AbsoluteFill>
      </Camera>
    </AbsoluteFill>
  );
};

// ---- spotlight: one big icon under a radar sweep, its label and up to three tags around it --------------------
const Spotlight = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const g = s.graphic;
  const cx = vertical ? width / 2 : width * 0.32, cy = vertical ? 1000 : height * 0.6;
  const R = vertical ? 260 : 230;
  const at = g.center.at;
  const p = spring({frame: frame - at, fps, config: {damping: 14}});
  return (
    <Frame s={s} i={i} vertical={vertical}>
      <div style={{position: "absolute", left: cx - R * 1.9, top: cy - R * 1.9, width: R * 3.8, height: R * 3.8, borderRadius: "50%",
                   background: `conic-gradient(from ${frame * 3}deg, ${alpha(C.accent, 0.35)}, transparent 25%, transparent)`,
                   opacity: p, maskImage: "radial-gradient(circle, black 30%, transparent 70%)",
                   WebkitMaskImage: "radial-gradient(circle, black 30%, transparent 70%)"}}/>
      <svg width={width} height={height} style={{position: "absolute"}}>
        {[1.25, 1.55, 1.85].map((r, k) => (
          <circle key={k} cx={cx} cy={cy} r={R * r * (0.8 + 0.2 * p)} fill="none" stroke={alpha(C.accent, 0.35 - k * 0.08)}
                  strokeWidth={3} strokeDasharray={k === 1 ? "4 16" : undefined} strokeDashoffset={frame * (k ? 1 : -1)}/>
        ))}
      </svg>
      <div style={{position: "absolute", left: cx, top: cy, transform: "translate(-50%, -50%)"}}>
        <Disc icon={g.center.icon} at={at} size={R * 2} color={C.accent}/>
      </div>
      <div style={{position: "absolute", ...(vertical ? {left: 70, right: 70, top: cy + R * 1.5, alignItems: "center"}
                                                       : {left: width * 0.58, right: 120, top: cy - 170}),
                   display: "flex", flexDirection: "column", gap: 26}}>
        <div style={{fontFamily: FONT.display, fontWeight: C.weight, fontSize: vertical ? 84 : 80, lineHeight: 1, color: C.text,
                     textTransform: C.upper ? "uppercase" : "none", opacity: clamp((frame - at - 6) / 10),
                     transform: `translateX(${(1 - ease((frame - at - 6) / 16)) * 60}px)`}}>{g.center.label}</div>
        <div style={{display: "flex", flexWrap: "wrap", gap: 18, justifyContent: vertical ? "center" : "flex-start"}}>
          {(g.nodes || []).map((nd, k) => {
            const q = spring({frame: frame - nd.at, fps, config: {damping: 13}});
            const col = SERIES[(k + 1) % SERIES.length];
            return (
              <div key={k} style={{display: "flex", alignItems: "center", gap: 14, padding: "14px 26px 14px 18px", borderRadius: 60,
                                   background: alpha(C.panel, 0.85), border: `2px solid ${alpha(col, 0.6)}`,
                                   boxShadow: `0 0 30px ${alpha(col, 0.25)}`, opacity: clamp(q * 2), transform: `scale(${0.6 + 0.4 * q})`}}>
                <Icon name={nd.icon} size={vertical ? 52 : 46} color={col} draw={ease((frame - nd.at) / 18)} width={2}/>
                <span style={{fontFamily: FONT.body, fontWeight: 800, fontSize: vertical ? 40 : 36, color: C.text}}>{nd.label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </Frame>
  );
};

// ---- versus: two sides slide in on a diagonal split, a VS badge bursts between them ------------------------
const Versus = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const [a, b] = s.graphic.nodes;
  const pa = spring({frame: frame - a.at, fps, config: {damping: 16}});
  const pb = spring({frame: frame - b.at, fps, config: {damping: 16}});
  const vsAt = Math.max(a.at, b.at) + 4;
  const pv = spring({frame: frame - vsAt, fps, config: {damping: 9}});
  const side = (nd, k, p) => (
    <div style={{position: "absolute", display: "flex", justifyContent: "center", alignItems: "center",
                 ...(vertical ? {left: 0, right: 0, top: k ? 1300 : 560, height: 420} : {top: 300, bottom: 60, left: k ? width / 2 : 0, width: width / 2}),
                 transform: vertical ? `translateX(${(1 - p) * (k ? 1 : -1) * 700}px)` : `translateX(${(1 - p) * (k ? 1 : -1) * 900}px)`}}>
      <Disc icon={nd.icon} at={nd.at} size={vertical ? 230 : 260} color={k ? C.cool : C.accent} label={nd.label}
            labelSize={vertical ? 54 : 52}/>
    </div>
  );
  return (
    <Frame s={s} i={i} vertical={vertical}>
      <svg width={width} height={height} style={{position: "absolute"}}>
        <polygon points={vertical ? `0,${height * 0.62} ${width},${height * 0.55} ${width},${height} 0,${height}`
                                  : `${width * 0.55},0 ${width},0 ${width},${height} ${width * 0.45},${height}`}
                 fill={alpha(C.cool, 0.07)} opacity={pb}/>
        <polygon points={vertical ? `0,0 ${width},0 ${width},${height * 0.55} 0,${height * 0.62}`
                                  : `0,0 ${width * 0.55},0 ${width * 0.45},${height} 0,${height}`}
                 fill={alpha(C.accent, 0.06)} opacity={pa}/>
        <line x1={vertical ? 0 : width * 0.55} y1={vertical ? height * 0.62 : 0} x2={vertical ? width : width * 0.45}
              y2={vertical ? height * 0.55 : height} stroke={C.text} strokeOpacity={0.25} strokeWidth={3}
              pathLength={1} strokeDasharray={1} strokeDashoffset={1 - ease((frame - vsAt + 10) / 20)}/>
      </svg>
      {side(a, 0, pa)}
      {side(b, 1, pb)}
      <div style={{position: "absolute", left: width / 2, top: vertical ? height * 0.585 : height * 0.58,
                   transform: `translate(-50%, -50%) scale(${pv}) rotate(${(1 - pv) * -30}deg)`,
                   width: 150, height: 150, borderRadius: "50%", background: C.hot, display: "flex", alignItems: "center",
                   justifyContent: "center", fontFamily: FONT.display, fontWeight: 900, fontSize: 64, color: "#fff",
                   boxShadow: `0 0 0 ${10 + 6 * Math.sin(frame / 6)}px ${alpha(C.hot, 0.25)}, 0 0 80px ${alpha(C.hot, 0.6)}`}}>VS</div>
    </Frame>
  );
};

// ---- stack: layers dropping into place from the bottom up, each with its icon and name -------------------
const Stack = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const nodes = s.graphic.nodes;
  const n = nodes.length;
  const h = vertical ? 170 : Math.min(130, 560 / n);
  const w = vertical ? 900 : 1100;
  const base = vertical ? 1600 : height - 90;
  return (
    <Frame s={s} i={i} vertical={vertical}>
      {nodes.map((nd, k) => {
        const p = spring({frame: frame - nd.at, fps, config: {damping: 13, mass: 0.9}});
        const col = SERIES[k % SERIES.length];
        const y = base - (k + 1) * (h + 18);
        const indent = k * (vertical ? 30 : 50);
        return (
          <div key={k} style={{position: "absolute", left: (width - w) / 2 + indent, width: w - 2 * indent, top: y, height: h,
                               transform: `translateY(${(1 - p) * -500}px) perspective(1200px) rotateX(${(1 - p) * 40 + 8}deg)`,
                               opacity: clamp(p * 2), borderRadius: 22, display: "flex", alignItems: "center", gap: 30,
                               padding: "0 40px", background: `linear-gradient(90deg, ${alpha(col, 0.32)}, ${alpha(C.panel, 0.9)} 60%)`,
                               border: `2px solid ${alpha(col, 0.7)}`,
                               boxShadow: `0 20px 50px ${alpha("#000000", 0.35)}, 0 0 40px ${alpha(col, 0.2)}`}}>
            <Icon name={nd.icon} size={h * 0.58} color={col} draw={ease((frame - nd.at - 4) / 18)} width={1.8}/>
            <span style={{fontFamily: FONT.body, fontWeight: 800, fontSize: Math.min(h * 0.42, vertical ? 56 : 50), color: C.text}}>{nd.label}</span>
            <div style={{marginLeft: "auto", width: 16, height: 16, borderRadius: 8, background: col,
                         boxShadow: `0 0 ${12 + 8 * Math.sin((frame + k * 10) / 8)}px ${col}`}}/>
          </div>
        );
      })}
    </Frame>
  );
};

export const GRAPHICS = {flow: Flow, hub: Hub, grid: Grid, kinetic: Kinetic, spotlight: Spotlight, versus: Versus, stack: Stack};
