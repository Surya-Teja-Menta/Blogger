// A library technique used as a shot's motion graphic (blogwriter/vizlib.py GRAPHIC_TYPES, chosen by the art
// director in blogwriter/graphics.py): the shot's backdrop and headline, and the technique on the diagram canvas.
import React from "react";
import {AbsoluteFill, useCurrentFrame} from "remotion";
import {Backdrop, Camera, Particles, Title} from "../fx";
import {C} from "../theme";
import {VIZ} from "./index";

const VizGraphic = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const g = s.graphic || {};
  const Part = VIZ[g.type];
  if (!Part) return null;
  const rect = vertical ? [80, 600, 1000, 1390] : [150, 310, 1770, 925];
  return (
    <AbsoluteFill>
      <Backdrop word={s.kicker} i={i}/>
      <Particles n={30} seed={`v${i}`}/>
      <Camera i={i} amount={0.5}>
        <AbsoluteFill>
          <svg width="100%" height="100%" viewBox={vertical ? "0 0 1080 1920" : "0 0 1920 1080"} style={{overflow: "visible"}}>
            <Part e={{...g, color: C.accent, at: g.at ?? 8}} rect={rect} frame={frame} end={s.frames || 300} seed={(i || 0) * 31 + 7} vertical={vertical}/>
          </svg>
        </AbsoluteFill>
        <AbsoluteFill><Title s={s} vertical={vertical} maxWidth={vertical ? 940 : 1500}/></AbsoluteFill>
      </Camera>
    </AbsoluteFill>
  );
};

export const VIZ_GRAPHICS = new Proxy({}, {get: (_, name) => (VIZ[name] ? VizGraphic : undefined)});
