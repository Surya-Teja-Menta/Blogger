import React from "react";
import {Composition, Still} from "remotion";
import {Video} from "./Video";
import {Thumb} from "./Thumb";
import {TRANSITION} from "./theme";

// Props come from blogwriter/video.py (--props=job.json). These defaults only make the studio open.
const demo = {
  channel: "Adyora",
  scenes: [
    {frames: 120, kind: "hook", kicker: "Breaking down", headline: "A $115 billion bet on light", highlight: "light",
     number: "$115B", images: [], source: "reuters.com"},
    {frames: 120, kind: "map", kicker: "Where", headline: "Two countries, one supply chain", countries: ["India", "China"]},
    {frames: 120, kind: "stat", kicker: "The deal", number: "46%", label: "of revenue from data centers"},
    {frames: 150, kind: "outro", kicker: "Full report in the description", headline: "Demo", label: "46 verified facts"},
  ],
  captions: [],
  thumbText: "A bet on light",
  thumbHighlight: "light",
};

// scenes overlap during each transition, so the video is shorter than the sum of the scenes
const length = ({props}) => ({
  durationInFrames: Math.max(1, props.scenes.reduce((n, s) => n + s.frames, 0) - TRANSITION * (props.scenes.length - 1)),
});

export const Root = () => (
  <>
    <Composition id="Long" component={Video} width={1920} height={1080} fps={30}
                 durationInFrames={300} defaultProps={demo} calculateMetadata={length}/>
    <Composition id="Short" component={Video} width={1080} height={1920} fps={30}
                 durationInFrames={300} defaultProps={demo} calculateMetadata={length}/>
    <Still id="Thumb" component={Thumb} width={1280} height={720} defaultProps={demo}/>
  </>
);
