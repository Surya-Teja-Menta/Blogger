"""The rigid-body scenes (video/src/viz/physcore.mjs, Planck.js): every scene is run in Node at its extreme settings before one
can reach a video; each must stay finite and inside the picture, and a collision must keep its total momentum."""
import json
import os
import shutil
import subprocess

import pytest

APP = os.path.join(os.path.dirname(__file__), "..", "video")
SCRIPT = """
import {run, SCENES} from "./src/viz/physcore.mjs";
const edges = [{a: 0, b: 0}, {a: 1, b: 1}, {a: 6, b: 6}, {a: 9, b: 9}, {a: 165, b: 165}, {a: 1, b: 165}, {a: 165, b: 1}, {a: -5, b: -5}, {a: NaN, b: 3}];
const out = {};
for (const scene of SCENES) for (const e of edges) for (const elastic of [true, false]) {
  const r = run({scene, ...e, elastic});
  const inside = r.frames.every((f) => f.every((b) => b.x > r.view[0] - 14 && b.x < r.view[2] + 14 && b.y > r.view[1] - 14 && b.y < r.view[3] + 14));
  out[`${scene}|${e.a}|${e.b}|${elastic}`] = [r.ok, inside, r.frames.length];
}
const c = run({scene: "collision", a: 4, b: 2, elastic: true});
const f = c.extra;
out.momentum = [f[0].pa + f[0].pb, f[f.length - 1].pa + f[f.length - 1].pb];
const r = run({scene: "ramp", a: 30, b: 0.2}), s = run({scene: "ramp", a: 12, b: 0.9});
out.ramp = [r.frames[0][0].x - r.frames[r.frames.length - 1][0].x, s.frames[0][0].x - s.frames[s.frames.length - 1][0].x];
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(not shutil.which("node") or not os.path.isdir(os.path.join(APP, "node_modules", "planck")), reason="needs Node and the video app's packages")
def test_every_scene_stays_finite_and_in_the_picture_at_its_extreme_settings():
    r = subprocess.run(["node", "--input-type=module", "-e", SCRIPT], cwd=APP, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-500:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    bad = {k: v for k, v in out.items() if "|" in k and not (v[0] and v[1])}
    assert not bad, bad
    assert abs(out["momentum"][0] - out["momentum"][1]) < 0.05 * out["momentum"][0]          # an elastic collision keeps the total push
    assert out["ramp"][0] > 3 and abs(out["ramp"][1]) < 0.05                                   # steep and slippery slides, shallow and rough sticks
