// The physics behind the "physics" picture: ready-made scenes (a pendulum, chaos in a double pendulum, a lever, a
// collision, a pulley, a ramp with friction, Newton's cradle) run by Planck.js (a Box2D port, MIT): real rigid bodies,
// real joints, real collisions. Plain JavaScript with no React, so a Node test can run every scene at its extreme
// settings before one ever reaches a video (tests/test_physics.py). The run is a fixed 60 steps a second from a fixed start:
// the same numbers on every machine, so a re-render is identical.
import * as planck from "planck";

const {World, Vec2, Circle, Box, Edge, RevoluteJoint, DistanceJoint, PulleyJoint} = planck;
const STEP = 1 / 60;
export const SCENES = ["pendulum", "chaos", "lever", "collision", "pulley", "ramp", "cradle"];

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, Number.isFinite(v) ? v : lo));
const dyn = (world, x, y, angle = 0) => world.createBody({type: "dynamic", position: Vec2(x, y), angle});

// Each builder returns {world, items: [{body, shape: {kind, ...}, role}], links: [{a, b, pa, pb}] (drawn as lines),
// fixed: [{kind, ...}] (static things drawn as they are), view: [x0, y0, x1, y1] in metres, steps, probe(frameData)}.
const builders = {
  pendulum(spec) {
    const L = 2.4, m = clamp(spec.a, 0.5, 4), world = new World({gravity: Vec2(0, -9.8)});
    const pivot = world.createBody({position: Vec2(0, 0)});
    const th = (clamp(spec.b, 10, 80) * Math.PI) / 180, bob = dyn(world, L * Math.sin(th), -L * Math.cos(th));
    bob.createFixture(new Circle(0.22 + 0.06 * m), {density: m / (Math.PI * (0.22 + 0.06 * m) ** 2), restitution: 0});
    world.createJoint(new RevoluteJoint({}, pivot, bob, Vec2(0, 0)));
    const items = [{body: bob, shape: {kind: "circle", r: 0.22 + 0.06 * m}, role: "bob"}];
    return {world, items, links: [{a: "pivot", b: 0}], fixed: [{kind: "pivot", x: 0, y: 0}], view: [-3.2, -3.2, 3.2, 0.6], steps: 360, mass: m, L,
      probe: (f) => { const b = f[0]; const v2 = b.vx * b.vx + b.vy * b.vy; return {ke: 0.5 * m * v2, pe: m * 9.8 * (b.y + L)}; }};
  },
  chaos(spec) {
    const world = new World({gravity: Vec2(0, -9.8)}), world2 = new World({gravity: Vec2(0, -9.8)});
    const make = (w, d) => {
      const pivot = w.createBody({position: Vec2(0, 0)});
      const a1 = (clamp(spec.b, 90, 165) * Math.PI) / 180 + d, a2 = a1 + 1.4;
      const p1 = [1.4 * Math.sin(a1), -1.4 * Math.cos(a1)], p2 = [p1[0] + 1.4 * Math.sin(a2), p1[1] - 1.4 * Math.cos(a2)];
      const b1 = dyn(w, p1[0], p1[1]), b2 = dyn(w, p2[0], p2[1]);
      b1.createFixture(new Circle(0.14), {density: 3}); b2.createFixture(new Circle(0.14), {density: 3});
      w.createJoint(new RevoluteJoint({}, pivot, b1, Vec2(0, 0)));
      w.createJoint(new RevoluteJoint({}, b1, b2, Vec2(p1[0], p1[1])));
      return [b1, b2];
    };
    const one = make(world, 0), two = make(world2, 0.05);          // the same swing, 3 degrees apart
    const items = [{body: one[0], shape: {kind: "circle", r: 0.14}, role: "a"}, {body: one[1], shape: {kind: "circle", r: 0.14}, role: "a"},
                   {body: two[0], shape: {kind: "circle", r: 0.14}, role: "b"}, {body: two[1], shape: {kind: "circle", r: 0.14}, role: "b"}];
    return {world, world2, items, links: [{a: "pivot", b: 0}, {a: 0, b: 1}, {a: "pivot", b: 2}, {a: 2, b: 3}], fixed: [{kind: "pivot", x: 0, y: 0}],
      view: [-3.2, -3.2, 3.2, 0.6], steps: 720, trail: [1, 3]};
  },
  lever(spec) {
    const world = new World({gravity: Vec2(0, -9.8)}), ma = clamp(spec.a, 1, 6), mb = clamp(spec.b, 1, 6);
    const plank = dyn(world, 0, 0.5);
    plank.createFixture(new Box(4, 0.1), {density: 0.2});
    const ra = 0.16 + 0.06 * ma, rb = 0.16 + 0.06 * mb;
    plank.createFixture(new Circle(Vec2(-3.3, 0.1 + ra), ra), {density: ma / (Math.PI * ra * ra)});
    plank.createFixture(new Circle(Vec2(3.3, 0.1 + rb), rb), {density: mb / (Math.PI * rb * rb)});
    const base = world.createBody({position: Vec2(0, 0)});
    const joint = world.createJoint(new RevoluteJoint({lowerAngle: -0.42, upperAngle: 0.42, enableLimit: true}, base, plank, Vec2(0, 0.5)));
    plank.setAngularDamping(3);
    return {world, items: [{body: plank, shape: {kind: "plank", hw: 4, hh: 0.1, circles: [[-3.3, 0.1 + ra, ra, "a"], [3.3, 0.1 + rb, rb, "b"]]}, role: "plank"}],
      links: [], fixed: [{kind: "fulcrum", x: 0, y: 0.5}], view: [-4.8, -0.6, 4.8, 3.6], steps: 300, ma, mb};
  },
  collision(spec) {
    const world = new World({gravity: Vec2(0, -9.8)}), ma = clamp(spec.a, 1, 6), mb = clamp(spec.b, 1, 6), e = spec.elastic ? 1 : 0;
    const floor = world.createBody({position: Vec2(0, 0)});
    floor.createFixture(new Edge(Vec2(-9, 0), Vec2(9, 0)), {friction: 0});
    const sa = 0.3 + 0.12 * Math.sqrt(ma), sb = 0.3 + 0.12 * Math.sqrt(mb);
    const A = dyn(world, -4, sa), B = dyn(world, 1.5, sb);
    A.createFixture(new Box(sa, sa), {density: ma / (4 * sa * sa), friction: 0, restitution: e});
    B.createFixture(new Box(sb, sb), {density: mb / (4 * sb * sb), friction: 0, restitution: e});
    A.setLinearVelocity(Vec2(3.2, 0));
    return {world, items: [{body: A, shape: {kind: "box", hw: sa, hh: sa}, role: "a"}, {body: B, shape: {kind: "box", hw: sb, hh: sb}, role: "b"}],
      links: [], fixed: [{kind: "floor", y: 0}], view: [-6, -0.6, 8, 3.4], steps: 170, ma, mb, e,
      probe: (f) => ({pa: ma * f[0].vx, pb: mb * f[1].vx})};
  },
  pulley(spec) {
    const world = new World({gravity: Vec2(0, -3)}), ma = clamp(spec.a, 1, 6), mb = clamp(spec.b, 1, 6);
    const sa = 0.3 + 0.1 * Math.sqrt(ma), sb = 0.3 + 0.1 * Math.sqrt(mb);
    const A = dyn(world, -1.6, -2.4), B = dyn(world, 1.6, -2.4);
    A.createFixture(new Box(sa, sa), {density: ma / (4 * sa * sa)});
    B.createFixture(new Box(sb, sb), {density: mb / (4 * sb * sb)});
    world.createJoint(new PulleyJoint({}, A, B, Vec2(-1.6, 2), Vec2(1.6, 2), Vec2(-1.6, -2.4), Vec2(1.6, -2.4), 1));
    return {world, items: [{body: A, shape: {kind: "box", hw: sa, hh: sa}, role: "a"}, {body: B, shape: {kind: "box", hw: sb, hh: sb}, role: "b"}],
      links: [], fixed: [{kind: "pulley", x: -1.6, y: 2}, {kind: "pulley", x: 1.6, y: 2}], ropes: [[-1.6, 2, "a"], [1.6, 2, "b"]], view: [-3.6, -4.6, 3.6, 2.9], steps: 110, ma, mb};
  },
  ramp(spec) {
    const world = new World({gravity: Vec2(0, -9.8)}), ang = (clamp(spec.a, 8, 55) * Math.PI) / 180, mu = clamp(spec.b, 0, 1.2);
    const len = 7, ground = world.createBody({position: Vec2(0, 0)});
    const x1 = len * Math.cos(ang), y1 = len * Math.sin(ang);
    ground.createFixture(new Edge(Vec2(-3.2, 0), Vec2(6.2, 0)), {friction: mu});
    ground.createFixture(new Edge(Vec2(0, 0), Vec2(x1, y1)), {friction: mu});
    ground.createFixture(new Edge(Vec2(x1, y1), Vec2(x1, 0)), {friction: mu});
    const s = 0.3, t = 5.6, nx = -Math.sin(ang), ny = Math.cos(ang);
    const box = dyn(world, t * Math.cos(ang) + nx * (s + 0.02), t * Math.sin(ang) + ny * (s + 0.02), ang);
    box.createFixture(new Box(s, s), {density: 1, friction: mu, restitution: 0});
    return {world, items: [{body: box, shape: {kind: "box", hw: s, hh: s}, role: "a"}], links: [], fixed: [{kind: "ramp", x1, y1, ang}], view: [-3.4, -0.6, 6.4, y1 + 1.4], steps: 240, ang, mu};
  },
  cradle(spec) {
    const world = new World({gravity: Vec2(0, -9.8)}), n = Math.round(clamp(spec.a, 3, 6)), r = 0.34, L = 2.6;
    const top = world.createBody({position: Vec2(0, 0)}), items = [], links = [];
    const lift = Math.round(clamp(spec.b, 1, Math.max(1, n - 2)));
    for (let i = 0; i < n; i++) {
      const x = (i - (n - 1) / 2) * (2 * r + 0.002), out = i < lift;
      const th = out ? -0.62 : 0, bx = x + L * Math.sin(th), by = -L * Math.cos(th), ball = dyn(world, bx, by);
      ball.createFixture(new Circle(r), {density: 2, restitution: 1, friction: 0});
      world.createJoint(new DistanceJoint({frequencyHz: 0, dampingRatio: 0}, top, ball, Vec2(x, 0), Vec2(bx, by)));
      items.push({body: ball, shape: {kind: "circle", r}, role: out ? "a" : "b"});
      links.push({a: "anchor" + x, b: i, ax: x, ay: 0});
    }
    return {world, items, links, fixed: [{kind: "beam", x0: -n * r - 0.3, x1: n * r + 0.3, y: 0}], view: [-3.2, -3.4, 3.2, 0.5], steps: 420, n};
  },
};

const read = (b) => { const p = b.getPosition(), v = b.getLinearVelocity(); return {x: p.x, y: p.y, a: b.getAngle(), vx: v.x, vy: v.y}; };

// Runs a scene from its start: {frames: [per step: [{x, y, a, vx, vy} per item]], items, links, fixed, view, extra: [per step]}
export const run = (spec, steps) => {
  const make = builders[spec.scene] || builders.pendulum;
  const s = make(spec), n = steps || s.steps, frames = [], extra = [], worldOf = (it) => it.world2 || s.world;
  const hold = 8;                                   // a beat at the start, before everything is let go
  for (let k = 0; k < n; k++) {
    if (k >= hold) { s.world.step(STEP, 10, 4); if (s.world2) s.world2.step(STEP, 10, 4); }
    const f = s.items.map((it, j) => read(it.body));
    frames.push(f);
    if (s.probe) extra.push(s.probe(f));
  }
  const ok = frames.every((f) => f.every((b) => [b.x, b.y, b.a].every(Number.isFinite) && Math.abs(b.x) < 60 && Math.abs(b.y) < 60));
  return {frames, extra, ok, items: s.items.map(({shape, role}) => ({shape, role})), links: s.links, fixed: s.fixed, ropes: s.ropes || [], view: s.view,
          meta: {ma: s.ma, mb: s.mb, e: s.e, ang: s.ang, mu: s.mu, n: s.n, L: s.L, mass: s.mass}, trail: s.trail || []};
};
