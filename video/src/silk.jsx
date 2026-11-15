// Two luxury backdrops drawn by a fragment shader (raw WebGL, no library): "silk", slow folds of satin that catch the
// accent like gold thread, and "marble", dark stone with fine veins of the accent. A domain-warped noise, the same for
// every frame number, so a re-render is identical. It is drawn small and scaled up by the browser, which also smooths
// it, so it costs little even on a machine without a graphics card. Where WebGL is missing it falls back to a soft
// glow (and says so once in the log: `WEBGL missing`, `WEBGL ok`).
import React, {useLayoutEffect, useRef} from "react";
import {AbsoluteFill, useVideoConfig} from "remotion";
import {C, alpha} from "./theme";

const VERT = "attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}";
const FRAG = `precision mediump float;
uniform vec2 r;uniform float t;uniform float mode;uniform vec3 c0;uniform vec3 c1;uniform vec3 c2;
float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
  return mix(mix(h(i),h(i+vec2(1.,0.)),f.x),mix(h(i+vec2(0.,1.)),h(i+vec2(1.,1.)),f.x),f.y);}
float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<4;i++){v+=a*n(p);p=p*2.02+vec2(1.7,9.2);a*=.5;}return v;}
void main(){
  vec2 uv=gl_FragCoord.xy/r;vec2 p=uv*vec2(r.x/r.y,1.)*1.7;float s=t*.05;
  vec2 q=vec2(fbm(p+s),fbm(p+vec2(5.2,1.3)-s));
  vec2 w=vec2(fbm(p+3.*q+vec2(1.7,9.2)+.5*s),fbm(p+3.*q+vec2(8.3,2.8)-.4*s));
  float f=fbm(p+3.*w);
  vec3 col=mix(c0,c1,smoothstep(.15,.85,f));
  if(mode<.5){float sheen=pow(.5+.5*sin(f*10.+q.x*5.),4.);col=mix(col,c2,sheen*smoothstep(.25,.9,f));}
  else{float vein=pow(1.-abs(sin(f*7.+w.x*3.)),14.);col=mix(col,c2,vein*.9);}
  col*=1.-.4*length(uv-.5);
  gl_FragColor=vec4(col,1.);
}`;

const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
const mix = (a, b, k) => a.map((v, i) => v + (b[i] - v) * k);
let reported = false;

const Shaded = ({frame, mode}) => {
  const ref = useRef(null);
  const {width, height} = useVideoConfig();
  const w = width > height ? 480 : 270, h = width > height ? 270 : 480;
  useLayoutEffect(() => {
    const gl = ref.current && ref.current.getContext("webgl", {preserveDrawingBuffer: true});
    if (!reported) { reported = true; console.log(gl ? "WEBGL ok" : "WEBGL missing"); }
    if (!gl) return;
    const sh = (type, src) => { const o = gl.createShader(type); gl.shaderSource(o, src); gl.compileShader(o); return o; };
    const prog = gl.createProgram();
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT));
    gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog);
    gl.useProgram(prog);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, "p");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const bg = rgb(C.bg), accent = rgb(C.accent), dark = !C.light;
    // faint on purpose: the headlines on top stay readable
    const c0 = bg, c1 = mix(bg, accent, dark ? 0.12 : 0.1), c2 = mix(bg, accent, dark ? 0.5 : 0.28);
    gl.viewport(0, 0, w, h);
    gl.uniform2f(gl.getUniformLocation(prog, "r"), w, h);
    gl.uniform1f(gl.getUniformLocation(prog, "t"), frame / 30);
    gl.uniform1f(gl.getUniformLocation(prog, "mode"), mode);
    gl.uniform3fv(gl.getUniformLocation(prog, "c0"), c0);
    gl.uniform3fv(gl.getUniformLocation(prog, "c1"), c1);
    gl.uniform3fv(gl.getUniformLocation(prog, "c2"), c2);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    gl.deleteProgram(prog);
    gl.deleteBuffer(buf);
  }, [frame, mode, w, h]);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{background: `radial-gradient(ellipse at 30% 20%, ${alpha(C.accent, 0.16)}, transparent 60%)`}}/>
      <canvas ref={ref} width={w} height={h} style={{position: "absolute", left: 0, top: 0, width: "100%", height: "100%"}}/>
    </AbsoluteFill>
  );
};

export const Silk = ({frame}) => <Shaded frame={frame} mode={0}/>;
export const Marble = ({frame}) => <Shaded frame={frame} mode={1}/>;
