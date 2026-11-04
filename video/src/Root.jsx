import React from "react";
import {Composition, Still} from "remotion";
import {Board} from "./Board";
import {Thumb} from "./Thumb";

// Props come from blogwriter/video.py (--props=job.json). These defaults only make the studio open.
const demo = {
  fps: 30,
  accent: "#e63946",
  scenes: [
    {frames: 120, kind: "hook", number: "$115B", images: [], source: "", audio: ""},
    {frames: 120, kind: "outro", number: "", images: [], source: "", audio: ""},
  ],
  captions: [],
  thumbText: "Demo",
};

const length = ({props}) => ({
  durationInFrames: Math.max(1, props.scenes.reduce((n, s) => n + s.frames, 0)),
  fps: props.fps,
});

export const Root = () => (
  <>
    <Composition id="Long" component={Board} width={1920} height={1080} fps={30}
                 durationInFrames={240} defaultProps={demo} calculateMetadata={length}/>
    <Composition id="Short" component={Board} width={1080} height={1920} fps={30}
                 durationInFrames={240} defaultProps={demo} calculateMetadata={length}/>
    <Still id="Thumb" component={Thumb} width={1280} height={720} defaultProps={demo}/>
  </>
);
