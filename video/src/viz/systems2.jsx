// System-design techniques, part 2 (blogwriter/vizlib.py, family "system"): retries, networks, workflows, batch and
// stream processing, indexes, encodings, failure handling and caches.
import {Arrow, C, Card, Chip, Ico, Packet, React, Ring, Txt, alpha, along, box, clamp, ease, fmt, glide, glowF, lerp, pal,
        pop, rng, row, smoothPath, spread, timing, tw} from "./kit";

const cyc = (t, start, period) => { const x = (t - start) / period; return {n: Math.floor(x), ph: x - Math.floor(x), on: t >= start}; };
const hashOf = (s, salt = 0) => { let h = 2166136261 ^ salt; for (const ch of String(s)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967296; };

// --------------------------------------------------------------------------------------------------------------
export const Backoff = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.retries;
  const times = [0]; for (let k = 1; k <= n; k++) times.push(times[k - 1] + 2 ** (k - 1) * (e.jitter ? 1 + 0.25 * Math.sin(k * 2.3) : 1));
  const total = times[n], X = (t) => B.x0 + 40 + ((B.W - 80) * t) / total, y = B.cy;
  const reveal = glide(T.t - 8, 3.2) * (n + 1);
  return (
    <g>
      <line x1={B.x0 + 20} y1={y} x2={B.x1 - 10} y2={y} stroke={C.muted} strokeWidth={4} opacity={clamp(T.t / 10)}/>
      <Txt x={B.x1 - 10} y={y + B.fs * 1.1} size={B.fs * 0.8} anchor="end" color={C.muted}>time →</Txt>
      {times.map((t, k) => {
        if (reveal < k) return null;
        const ok = k === n, x = X(t), p = pop((reveal - k) * 20);
        return (
          <g key={k}>
            {k > 0 && <g opacity={p}>
              <path d={`M${X(times[k - 1])},${y - 30} Q${(X(times[k - 1]) + x) / 2},${y - 30 - Math.min(B.H * 0.35, (x - X(times[k - 1])) * 0.4)} ${x},${y - 30}`}
                    fill="none" stroke={pal(e, 0)} strokeWidth={3} strokeDasharray="8 7"/>
              {x - X(times[k - 1]) > tw(k === 1 ? "wait" : `wait ×${2 ** (k - 1)}`, B.fs * 0.8) &&
                <Txt x={(X(times[k - 1]) + x) / 2} y={y - 40 - Math.min(B.H * 0.35, (x - X(times[k - 1])) * 0.4)} size={B.fs * 0.8} color={pal(e, 0)}>
                  {k === 1 ? "wait" : `wait ×${2 ** (k - 1)}`}</Txt>}
            </g>}
            <circle cx={x} cy={y} r={22 * p} fill={ok ? C.cool : C.hot} style={{filter: glowF(ok ? C.cool : C.hot, 0.5)}}/>
            <Txt x={x} y={y + 1} size={B.fs * 0.9} color={C.bg} halo={false}>{ok ? "✓" : "✕"}</Txt>
          </g>
        );
      })}
      {e.jitter && T.k > 0 && <Txt x={B.cx} y={B.y1 - B.fs * 0.5} size={B.fs} color={C.violet} op={clamp(T.k / 12)}>+ jitter: retries spread out</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
const Globe = ({cx, cy, R, op}) => (
  <g opacity={op}>
    <circle cx={cx} cy={cy} r={R} fill={alpha(C.cool, 0.08)} stroke={alpha(C.muted, 0.5)} strokeWidth={3}/>
    {[-0.6, -0.3, 0, 0.3, 0.6].map((k) => <ellipse key={`a${k}`} cx={cx} cy={cy + k * R} rx={R * Math.sqrt(1 - k * k)} ry={R * 0.08} fill="none" stroke={alpha(C.muted, 0.25)} strokeWidth={2}/>)}
    {[0.3, 0.65, 1].map((k) => <ellipse key={`b${k}`} cx={cx} cy={cy} rx={R * k} ry={R} fill="none" stroke={alpha(C.muted, 0.25)} strokeWidth={2}/>)}
  </g>
);
export const Cdn = ({e, rect, frame, end, vertical, seed = 0}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const R = Math.min(B.H * 0.46, B.W * 0.3), cx = B.cx, cy = B.cy;
  const edges = Array.from({length: e.edges}, (_, k) => { const a = (2 * Math.PI * k) / e.edges + 0.4; return [cx + R * 0.72 * Math.cos(a), cy + R * 0.6 * Math.sin(a)]; });
  const origin = [B.x1 - 60, B.y0 + 60];
  const users = Array.from({length: 9}, (_, k) => { const a = k * 2.399 + 0.3, r = R * (0.25 + 0.65 * ((k * 0.37) % 1)); return [cx + r * Math.cos(a), cy + r * 0.85 * Math.sin(a)]; });
  const near = (u) => edges.reduce((b, ed) => (Math.hypot(ed[0] - u[0], ed[1] - u[1]) < Math.hypot(b[0] - u[0], b[1] - u[1]) ? ed : b), edges[0]);
  const q = glide(T.k, 1.4);
  return (
    <g>
      <Globe cx={cx} cy={cy} R={R} op={clamp(T.t / 12)}/>
      <Card x={origin[0] - 80} y={origin[1] - 50} w={160} h={100} icon="server" label={e.text || "origin"} color={C.hot} p={pop(T.t - 4)} fs={B.fs * 0.8}/>
      {users.map((u, k) => {
        const to = T.k > 0 ? near(u) : origin, d = glide(T.t - 20 - k * 3, 1), long = T.k <= 0;
        return (
          <g key={k}>
            <line x1={u[0]} y1={u[1]} x2={lerp(u[0], to[0], d)} y2={lerp(u[1], to[1], d)} stroke={long ? alpha(C.hot, 0.6) : alpha(C.cool, 0.85)} strokeWidth={long ? 3 : 4}
                  strokeDasharray={long ? "8 8" : undefined} opacity={T.k > 0 ? q : 1}/>
            <circle cx={u[0]} cy={u[1]} r={9} fill={C.text}/>
          </g>
        );
      })}
      {edges.map((ed, k) => (
        <g key={k} opacity={clamp(T.k > 0 ? q * 2 : (T.t - 30) / 20 * 0.4)}>
          <circle cx={ed[0]} cy={ed[1]} r={24} fill={alpha(pal(e, 0), 0.4)} stroke={pal(e, 0)} strokeWidth={4} style={{filter: T.k > 0 ? glowF(pal(e, 0), 0.6) : undefined}}/>
          <Ico name="zap" x={ed[0]} y={ed[1]} size={24} color={C.text}/>
        </g>
      ))}
      {T.k > 0 && <Txt x={B.x0 + 10} y={B.y1 - B.fs * 0.4} size={B.fs} anchor="start" color={pal(e, 0)} op={q}>nearest edge</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Queueing = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const gx0 = B.x0 + 30, gx1 = vertical ? B.x1 - 20 : B.x0 + B.W * 0.55, gy0 = B.y0 + 10, gy1 = B.y1 - B.fs * 1.6;
  const wait = (r) => Math.min(12, r / Math.max(0.04, 1 - r));
  const X = (r) => gx0 + ((gx1 - gx0) * r) / 1.05, Y = (w) => gy1 - ((gy1 - gy0) * w) / 12;
  const pts = Array.from({length: 60}, (_, j) => { const r = (0.98 * j) / 59; return [X(r), Y(wait(r))]; });
  const target = Math.min(1.02, e.load), now = lerp(0.3, target, glide(T.t - 20, 3.4));
  const L = Math.min(14, Math.round(Math.min(12, wait(Math.min(0.99, now))) * 1.2));
  return (
    <g>
      <line x1={gx0} y1={gy1} x2={gx1} y2={gy1} stroke={C.muted} strokeWidth={3}/>
      <line x1={gx0} y1={gy1} x2={gx0} y2={gy0} stroke={C.muted} strokeWidth={3}/>
      <line x1={X(1)} y1={gy1} x2={X(1)} y2={gy0} stroke={C.hot} strokeWidth={3} strokeDasharray="8 8"/>
      <Txt x={X(1)} y={gy1 + B.fs * 0.9} size={B.fs * 0.8} color={C.hot}>100% busy</Txt>
      <Txt x={(gx0 + gx1) / 2} y={gy1 + B.fs * 0.9} size={B.fs * 0.8} color={C.muted}>load</Txt>
      <Txt x={gx0 + 10} y={gy0 + B.fs * 0.4} size={B.fs * 0.8} color={C.muted} anchor="start">waiting time</Txt>
      <path d={smoothPath(pts)} fill="none" stroke={pal(e, 0)} strokeWidth={5} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - glide(T.t - 4, 2)}/>
      <circle cx={X(Math.min(0.98, now))} cy={Y(Math.min(12, wait(Math.min(0.98, now))))} r={14} fill={C.hot} style={{filter: glowF(C.hot, 0.8)}}/>
      {!vertical && <g>
        <rect x={B.x0 + B.W * 0.62} y={B.cy - 60} width={B.W * 0.34} height={120} rx={14} fill={alpha(C.panel, 0.9)} stroke={L > 9 ? C.hot : C.muted} strokeWidth={3}/>
        {Array.from({length: L}, (_, k) => <Ico key={k} name="user" x={B.x0 + B.W * 0.95 - 40 - k * ((B.W * 0.32 - 40) / 14)} y={B.cy} size={44}
                                               color={k > 9 ? C.hot : C.text}/>)}
        <Txt x={B.x0 + B.W * 0.79} y={B.cy - 90} size={B.fs * 0.9}>the line</Txt>
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Fanout = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.followers;
  const author = [B.x0 + B.W * 0.14, B.cy], fx = B.x1 - B.W * 0.2, fy = row(n, B.y0 + 30, B.y1 - 30), fh = Math.min(70, (B.H - 20) / n - 8);
  const write = e.mode === "write", go = T.k > 0 ? T.k : T.t - 40;
  return (
    <g>
      <Card x={author[0] - 90} y={author[1] - 70} w={180} h={140} icon={write ? "user" : "users"} label={write ? "one post" : "authors"}
            color={pal(e, 0)} p={pop(T.t)} fs={B.fs * 0.85}/>
      {fy.map((y, k) => {
        const d = glide(go - (write ? k * 3 : 0), 1), done = d >= 1;
        return (
          <g key={k}>
            <rect x={fx - 120} y={y - fh / 2} width={240} height={fh} rx={10} fill={done && write ? alpha(pal(e, 0), 0.25) : alpha(C.panel, 0.9)}
                  stroke={done && write ? pal(e, 0) : alpha(C.muted, 0.5)} strokeWidth={3} opacity={clamp(pop(T.t - k * 2) * 2)}/>
            <Txt x={fx - 100} y={y} size={Math.min(B.fs * 0.8, fh * 0.45)} anchor="start" color={C.muted}>timeline</Txt>
            {write && <Packet pts={[[author[0] + 90, author[1]], [fx - 120, y]]} t={d * 0.999} color={pal(e, 0)} r={8}/>}
            {write && done && <rect x={fx + 40} y={y - fh * 0.3} width={60} height={fh * 0.6} rx={6} fill={pal(e, 0)}/>}
          </g>
        );
      })}
      {!write && go > 0 && (() => {
        const k = Math.floor(n / 2), y = fy[k];
        return (
          <g>
            {[-1, 0, 1].map((o, j) => <Packet key={j} pts={[[author[0] + 90, author[1] + o * 40], [fx - 120, y]]} t={glide(go - j * 6, 1) * 0.999} color={pal(e, j)}/>)}
            <Txt x={fx} y={y - fh} size={B.fs * 0.85} color={C.hot}>built when opened</Txt>
          </g>
        );
      })()}
      <Txt x={(author[0] + fx) / 2} y={B.y0 + 4} size={B.fs * 0.9} color={C.muted}>{write ? "fan-out on write" : "fan-out on read"}</Txt>
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const StateMachine = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.states.length;
  const xs = spread(n, B.x0, B.x1), y = B.cy, r = Math.min(80, (B.W / n) * 0.3);
  const m = e.moves.length, per = Math.max(24, (end - T.at - 40) / (m + 1)), step = Math.max(0, (T.t - 20) / per);
  const k = Math.min(m - 1, Math.floor(step)), ph = clamp(step - k);
  const cur = step <= 0 ? e.moves[0].from : step >= m ? e.moves[m - 1].to : null;
  return (
    <g>
      {e.moves.map((mv, j) => {
        const a = [xs[mv.from], y], b = [xs[mv.to], y], back = mv.to <= mv.from, bend = back ? 0.45 : 0.32;
        const off = (pt, toward) => { const dx = toward[0] - pt[0], dy = toward[1] - pt[1], L = Math.hypot(dx, dy) || 1; return [pt[0] + (dx / L) * r, pt[1] + (dy / L) * r]; };
        return <Arrow key={j} a={off(a, b)} b={off(b, a)} draw={glide(T.t - 10 - j * 4, 1.2)} color={j === k && ph > 0 ? C.hot : C.muted} width={4}
                      bend={back ? -bend : bend} label={mv.text} fs={B.fs * 0.85}/>;
      })}
      {e.states.map((s, j) => {
        const on = cur === j || (cur === null && (ph < 0.15 ? e.moves[k].from === j : ph > 0.85 && e.moves[k].to === j));
        return (
          <g key={j} opacity={clamp(pop(T.t - j * 5) * 2)}>
            <circle cx={xs[j]} cy={y} r={r} fill={on ? alpha(pal(e, 0), 0.35) : alpha(C.panel, 0.95)} stroke={on ? pal(e, 0) : C.muted} strokeWidth={on ? 7 : 4}
                    style={{filter: on ? glowF(pal(e, 0), 0.8) : undefined}}/>
            <Txt x={xs[j]} y={y} size={Math.min(B.fs, (r * 1.7) / Math.max(3, s.length * 0.6))}>{s}</Txt>
          </g>
        );
      })}
      {cur === null && (() => {
        const mv = e.moves[k], a = [xs[mv.from], y - r], b = [xs[mv.to], y - r], mid = [(a[0] + b[0]) / 2, y - r - Math.abs(b[0] - a[0]) * 0.32];
        const pt = along([a, mid, b], ph);
        return <circle cx={pt[0]} cy={pt[1]} r={14} fill={C.hot} style={{filter: glowF(C.hot, 0.9)}}/>;
      })()}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Dag = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.tasks.length;
  const level = Array(n).fill(0);
  for (let it = 0; it < n; it++) e.deps.forEach((d) => { level[d.to] = Math.max(level[d.to], level[d.from] + 1); });
  const L = Math.max(...level) + 1, cols = Array.from({length: L}, (_, l) => level.map((v, k) => (v === l ? k : -1)).filter((k) => k >= 0));
  const lx = spread(L, B.x0, B.x1), pos = {};
  cols.forEach((c, l) => { const ys = spread(c.length, B.y0, B.y1); c.forEach((k, j) => { pos[k] = [lx[l], ys[j]]; }); });
  const cw = Math.min(220, (B.W / L) * 0.7), ch = Math.min(80, (B.H / Math.max(...cols.map((c) => c.length))) * 0.6);
  const run = Math.max(0, (T.t - 30) / 22);
  return (
    <g>
      {e.deps.map((d, j) => <Arrow key={j} a={[pos[d.from][0] + cw / 2, pos[d.from][1]]} b={[pos[d.to][0] - cw / 2 - 4, pos[d.to][1]]} draw={glide(T.t - 10 - j * 3, 1)}
                                  color={run > level[d.to] ? pal(e, 0) : C.muted} width={4}/>)}
      {e.tasks.map((t, k) => {
        const done = run > level[k] + 1, active = run > level[k] && !done;
        const [x, y] = pos[k];
        return (
          <g key={k} opacity={clamp(pop(T.t - level[k] * 6) * 2)}>
            <rect x={x - cw / 2} y={y - ch / 2} width={cw} height={ch} rx={12} fill={done ? alpha(pal(e, 0), 0.35) : active ? alpha(C.hot, 0.25) : alpha(C.panel, 0.95)}
                  stroke={done ? pal(e, 0) : active ? C.hot : C.muted} strokeWidth={active ? 5 : 3} style={{filter: active ? glowF(C.hot, 0.6) : undefined}}/>
            <Txt x={x - (done ? 14 : 0)} y={y} size={Math.min(B.fs * 0.9, (cw - 30) / Math.max(3, t.length * 0.62))}>{t}</Txt>
            {done && <Txt x={x + cw / 2 - 22} y={y} size={B.fs} color={pal(e, 0)}>✓</Txt>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const MapReduce = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), words = e.words;
  const keys = [...new Set(words)], counts = keys.map((k) => words.filter((w) => w === k).length);
  const cx = [B.x0 + B.W * 0.12, B.cx, B.x1 - B.W * 0.12], heads = ["map", "shuffle", "reduce"];
  const wy = row(words.length, B.y0 + B.fs * 2, B.y1 - 20), ky = row(keys.length, B.y0 + B.fs * 2.4, B.y1 - 40);
  const m = glide(T.t - 30, 2.2), r = glide(T.k, 1.4);
  return (
    <g>
      {heads.map((h, k) => <Txt key={k} x={cx[k]} y={B.y0 + B.fs * 0.5} size={B.fs} color={pal(e, k)} op={clamp((T.t - k * 10) / 12)}>{h}</Txt>)}
      {keys.map((k, j) => <rect key={`b${j}`} x={cx[1] - 120} y={ky[j] - 40} width={240} height={80} rx={14} fill={alpha(pal(e, j + 1), 0.15)}
                                 stroke={alpha(pal(e, j + 1), 0.7)} strokeWidth={3} opacity={clamp((T.t - 20) / 12)}/>)}
      {words.map((w, j) => {
        const kj = keys.indexOf(w), same = words.slice(0, j).filter((x) => x === w).length;
        const from = [cx[0], wy[j]], to = [cx[1] - 80 + same * 46, ky[kj]], q = clamp(m * 1.3 - j * 0.04);
        return (
          <g key={j}>
            <Chip x={lerp(from[0], to[0], q)} y={lerp(from[1], to[1], q)} text={q > 0.5 ? "1" : w} color={pal(e, kj + 1)} p={pop(T.t - j * 3)} fs={B.fs * 0.8} fill={q > 0.5}/>
          </g>
        );
      })}
      {keys.map((k, j) => (
        <g key={`r${j}`} opacity={clamp(r * 2)}>
          <Arrow a={[cx[1] + 125, ky[j]]} b={[cx[2] - 90, ky[j]]} draw={r} color={pal(e, j + 1)} width={4}/>
          <Chip x={cx[2]} y={ky[j]} text={`${k}: ${counts[j]}`} color={pal(e, j + 1)} p={r} fs={B.fs * 0.9} fill/>
        </g>
      ))}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Windows = ({e, rect, frame, end, vertical, seed = 0}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const ev = React.useMemo(() => { const r = rng(seed + 21), out = []; let t = 0.02; while (t < 0.98) { out.push(t); t += 0.015 + r() * (r() > 0.85 ? 0.12 : 0.05); } return out; }, [seed]);
  const X = (t) => B.x0 + 20 + (B.W - 40) * t, y = B.cy + B.H * 0.1;
  const play = glide(T.t - 10, 3.6);
  const wins = e.kind === "tumbling" ? [0, 0.25, 0.5, 0.75].map((a) => [a, a + 0.25])
    : e.kind === "sliding" ? [0, 0.125, 0.25, 0.375, 0.5, 0.625].map((a) => [a, a + 0.375])
      : (() => { const out = []; let s = ev[0]; for (let k = 1; k < ev.length; k++) if (ev[k] - ev[k - 1] > 0.08) { out.push([s - 0.01, ev[k - 1] + 0.01]); s = ev[k]; } out.push([s - 0.01, ev[ev.length - 1] + 0.01]); return out; })();
  return (
    <g>
      <line x1={B.x0 + 20} y1={y} x2={B.x1 - 20} y2={y} stroke={C.muted} strokeWidth={3}/>
      <Txt x={B.x1 - 20} y={y + B.fs * 1.1} size={B.fs * 0.8} anchor="end" color={C.muted}>event time →</Txt>
      {ev.map((t, k) => t <= play && <circle key={k} cx={X(t)} cy={y} r={10} fill={C.text}/>)}
      {wins.map(([a, b], k) => {
        if (a > play) return null;
        const lane = e.kind === "sliding" ? k % 3 : 0, h = B.H * 0.16, top = y - B.H * 0.22 - lane * (h * 0.45);
        const n = ev.filter((t) => t >= a && t < b && t <= play).length, closed = play >= b;
        return (
          <g key={k}>
            <rect x={X(a)} y={top} width={X(Math.min(b, play)) - X(a)} height={h} rx={10} fill={alpha(pal(e, k), closed ? 0.3 : 0.14)} stroke={pal(e, k)} strokeWidth={3}/>
            {closed && <Txt x={(X(a) + X(b)) / 2} y={top - B.fs * 0.6} size={B.fs * 0.85} color={pal(e, k)}>{n}</Txt>}
          </g>
        );
      })}
      <line x1={X(play)} y1={B.y0 + 10} x2={X(play)} y2={y + 30} stroke={C.hot} strokeWidth={3}/>
      <Txt x={B.x0 + 20} y={B.y0 + B.fs * 0.5} size={B.fs} anchor="start" color={pal(e, 0)}>{`${e.kind} windows`}</Txt>
      {e.text && <Txt x={B.x0 + 20} y={B.y1 - B.fs * 0.4} size={B.fs * 0.85} anchor="start" color={C.muted}>{e.text}</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Cdc = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.targets.length;
  const db = [B.x0 + B.W * 0.13, B.cy], pipe = [B.x0 + B.W * 0.3, B.x0 + B.W * 0.62], tx = B.x1 - B.W * 0.13, ty = row(n, B.y0 + 60, B.y1 - 60);
  const kinds = ["insert", "update", "delete"], c = cyc(T.t, 20, 36);
  return (
    <g>
      <Card x={db[0] - 110} y={db[1] - 90} w={220} h={180} icon="database" label={e.db} color={pal(e, 0)} p={pop(T.t)} fs={B.fs * 0.9}/>
      <rect x={pipe[0]} y={B.cy - 30} width={pipe[1] - pipe[0]} height={60} rx={30} fill={alpha(C.panel, 0.9)} stroke={C.muted} strokeWidth={3} opacity={clamp(T.t / 10)}/>
      <Txt x={(pipe[0] + pipe[1]) / 2} y={B.cy - 56} size={B.fs * 0.85} color={C.muted}>change stream</Txt>
      {ty.map((y, k) => (
        <g key={k}>
          <line x1={pipe[1]} y1={B.cy} x2={tx - 100} y2={y} stroke={alpha(C.muted, 0.35)} strokeWidth={3}/>
          <Card x={tx - 100} y={y - 45} w={200} h={90} label={e.targets[k]} color={pal(e, k + 1)} p={pop(T.t - 8 - k * 4)} fs={B.fs * 0.85}
                lit={c.on && c.ph > 0.85 ? 0.5 : 0}/>
          {c.on && <Packet pts={[[pipe[1], B.cy], [tx - 100, y]]} t={(c.ph - 0.55) / 0.35} color={pal(e, c.n % 3)}/>}
        </g>
      ))}
      {c.on && (() => {
        const x = lerp(pipe[0] + 60, pipe[1] - 60, clamp(c.ph / 0.55));
        return <Chip x={x} y={B.cy} text={kinds[c.n % 3]} color={pal(e, c.n % 3)} p={1} fs={B.fs * 0.7} fill/>;
      })()}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Bloom = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), m = e.bits;
  const cw = Math.min(64, (B.W - 20) / m), x0 = B.cx - (cw * m) / 2, by = B.cy + B.H * 0.12;
  const bitsOf = (s) => [0, 1, 2].map((k) => Math.floor(hashOf(s, k * 977) * m));
  const per = 30, set = new Set();
  e.items.forEach((it, j) => { if (T.t > 20 + j * per + 16) bitsOf(it).forEach((b) => set.add(b)); });
  const qb = bitsOf(e.query || "x"), allOn = qb.every((b) => set.has(b));
  const ix = spread(e.items.length, B.x0, B.x1 - B.W * 0.25);
  return (
    <g>
      {Array.from({length: m}, (_, k) => (
        <g key={k} opacity={clamp(T.t / 10)}>
          <rect x={x0 + k * cw + 2} y={by} width={cw - 4} height={cw - 4} rx={6} fill={set.has(k) ? pal(e, 0) : alpha(C.panel, 0.95)} stroke={C.muted} strokeWidth={2}/>
          <Txt x={x0 + (k + 0.5) * cw} y={by + cw / 2 - 2} size={cw * 0.42} color={set.has(k) ? C.bg : C.muted} halo={false}>{set.has(k) ? 1 : 0}</Txt>
        </g>
      ))}
      {e.items.map((it, j) => {
        const s = 20 + j * per, p = pop(T.t - s), y = B.y0 + B.fs * 1.4;
        return (
          <g key={j} opacity={clamp(p * 2)}>
            <Chip x={ix[j]} y={y} text={it} color={pal(e, 0)} p={p} fs={B.fs * 0.85} fill/>
            {bitsOf(it).map((b, k) => <Arrow key={k} a={[ix[j], y + B.fs]} b={[x0 + (b + 0.5) * cw, by - 6]} draw={glide(T.t - s - 4 - k * 3, 0.8)} color={alpha(pal(e, 0), 0.8)} width={3}/>)}
          </g>
        );
      })}
      {T.k > 0 && <g>
        <Chip x={B.x1 - B.W * 0.12} y={B.y0 + B.fs * 1.4} text={e.query} color={C.hot} p={pop(T.k)} fs={B.fs * 0.9} fill/>
        {qb.map((b, k) => <Arrow key={k} a={[B.x1 - B.W * 0.12, B.y0 + B.fs * 2.4]} b={[x0 + (b + 0.5) * cw, by - 6]} draw={glide(T.k - 6 - k * 3, 0.8)}
                                 color={set.has(b) ? C.cool : C.hot} width={4} dashed={!set.has(b)}/>)}
        <Txt x={B.cx} y={by + cw + B.fs * 1.3} size={B.fs * 1.2} color={allOn ? C.violet : C.hot} op={clamp((T.k - 24) / 10)}>
          {allOn ? "maybe in the set" : "definitely not in the set"}</Txt>
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const InvIndex = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), nd = e.docs.length, nt = e.terms.length;
  const dx = B.x1 - B.W * 0.3, dy = row(nd, B.y0 + 40, B.y1 - 40), dw = B.W * 0.5, dh = Math.min(80, (B.H - 20) / nd - 10);
  const tx = B.x0 + B.W * 0.12, ty = row(nt, B.y0 + 60, B.y1 - 60);
  return (
    <g>
      {e.docs.map((d, j) => (
        <g key={j} opacity={clamp(pop(T.t - j * 5) * 2)}>
          <rect x={dx - dw / 2} y={dy[j] - dh / 2} width={dw} height={dh} rx={10} fill={alpha(C.panel, 0.95)} stroke={C.muted} strokeWidth={2}/>
          <Ico name="file-text" x={dx - dw / 2 + 30} y={dy[j]} size={dh * 0.5} color={C.muted}/>
          <Txt x={dx - dw / 2 + 60} y={dy[j]} size={Math.min(B.fs * 0.85, (dw - 80) / Math.max(8, d.length * 0.6))} anchor="start" weight={600}>{d}</Txt>
        </g>
      ))}
      {e.terms.map((t, i) => {
        const p = pop(T.t - 20 - i * 10), lit = T.k > 0 && i === 0;
        return (
          <g key={i}>
            <Chip x={tx} y={ty[i]} text={t} color={pal(e, i)} p={p} fs={B.fs} fill lit={lit ? 0.6 : 0}/>
            {e.docs.map((d, j) => new RegExp(`\\b${t.replace(/[^\w]/g, "")}`, "i").test(d) &&
              <Arrow key={j} a={[tx + tw(t, B.fs) / 2 + 30, ty[i]]} b={[dx - dw / 2 - 6, dy[j]]} draw={glide(T.t - 28 - i * 10 - j * 3, 1)}
                     color={lit ? C.hot : alpha(pal(e, i), 0.85)} width={lit ? 6 : 3}/>)}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Encoding = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), f = e.fields;
  const jx = B.x0 + 10, jw = B.W * 0.46, lh = Math.min(B.fs * 1.35, (B.H - 40) / (f.length + 2));
  const lines = ["{", ...f.map((k, j) => `  "${k}": "…"${j < f.length - 1 ? "," : ""}`), "}"];
  const bytes = f.length * 3 + 2, bx = B.x0 + B.W * 0.54, bw = Math.min(46, (B.W * 0.44) / 8);
  const shown = Math.min(lines.length, Math.floor(Math.max(0, T.t - 10) / 6));
  const bq = glide(T.k, 1.6);
  const jLen = lines.join("").length;
  return (
    <g>
      <Txt x={jx + jw / 2} y={B.y0 + 4} size={B.fs} color={C.hot}>JSON (text)</Txt>
      <rect x={jx} y={B.y0 + B.fs} width={jw} height={B.H - B.fs * 2.6} rx={12} fill={alpha(C.panel, 0.95)} stroke={C.hot} strokeWidth={3}/>
      {lines.slice(0, shown).map((l, j) => <Txt key={j} x={jx + 20} y={B.y0 + B.fs * 1.6 + j * lh} size={lh * 0.62} anchor="start" mono weight={600}>{l}</Txt>)}
      <Txt x={bx + B.W * 0.22} y={B.y0 + 4} size={B.fs} color={C.cool} op={clamp(bq * 3)}>binary</Txt>
      {Array.from({length: Math.round(bytes * bq)}, (_, k) => (
        <rect key={k} x={bx + (k % 8) * bw} y={B.y0 + B.fs * 1.6 + Math.floor(k / 8) * bw} width={bw - 5} height={bw - 5} rx={5} fill={pal(e, 1 + (k % 3))} opacity={0.8}/>
      ))}
      {T.k > 0 && <g opacity={clamp((T.k - 30) / 14)}>
        <rect x={jx} y={B.y1 - B.fs * 1.2} width={jw} height={14} rx={7} fill={C.hot}/>
        <rect x={bx} y={B.y1 - B.fs * 1.2} width={Math.max(30, (jw * bytes) / jLen)} height={14} rx={7} fill={C.cool}/>
        <Txt x={bx + Math.max(30, (jw * bytes) / jLen) + 20} y={B.y1 - B.fs * 1.2 + 7} size={B.fs * 0.85} anchor="start" color={C.cool}>far smaller</Txt>
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Evolve = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const all = [...new Set([...e.old, ...e.new])], rh = Math.min(B.fs * 1.7, (B.H - B.fs * 3) / all.length);
  const cols = [[B.x0 + B.W * 0.2, "old schema", e.old, C.muted], [B.x1 - B.W * 0.2, "new schema", e.new, pal(e, 0)]];
  const q = glide(T.k, 1.2);
  return (
    <g>
      {cols.map(([x, head, fields, col], c) => (
        <g key={c} opacity={clamp(pop(T.t - c * 10) * 2)}>
          <Txt x={x} y={B.y0 + 4} size={B.fs} color={col}>{head}</Txt>
          <rect x={x - B.W * 0.16} y={B.y0 + B.fs} width={B.W * 0.32} height={rh * all.length + 20} rx={12} fill={alpha(C.panel, 0.95)} stroke={col} strokeWidth={3}/>
          {all.map((f, j) => {
            const has = fields.includes(f), y = B.y0 + B.fs + 10 + rh * (j + 0.5);
            const extra = c === 1 && !e.old.includes(f), missing = c === 0 && !has;
            return has ? <Txt key={j} x={x} y={y} size={rh * 0.55} color={extra && q > 0 ? C.hot : C.text}>{f}</Txt>
              : missing && q > 0.5 ? <Txt key={j} x={x} y={y} size={rh * 0.5} color={C.violet}>{`${f}: default`}</Txt> : null;
          })}
        </g>
      ))}
      {T.k > 0 && <g>
        <Arrow a={[B.cx + B.W * 0.1, B.cy - 30]} b={[B.cx - B.W * 0.1, B.cy - 30]} draw={q} color={C.hot} width={5} label="old code reads new data" fs={B.fs * 0.75}/>
        <Txt x={B.cx} y={B.cy + 30} size={B.fs * 0.8} color={C.hot} op={clamp((q - 0.6) * 3)}>new field ignored</Txt>
        <Txt x={B.cx} y={B.cy + 30 + B.fs * 1.2} size={B.fs * 0.8} color={C.violet} op={clamp((q - 0.8) * 5)}>missing field defaulted</Txt>
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Quadtree = ({e, rect, frame, end, vertical, seed = 0}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const side = Math.min(B.H, B.W * 0.6), x0 = B.cx - side / 2, y0 = B.y0 + (B.H - side) / 2;
  const pts = React.useMemo(() => {
    const r = rng(seed + 31);
    return Array.from({length: e.n}, (_, k) => k < e.n * 0.6 ? [0.62 + (r() - 0.5) * 0.3, 0.3 + (r() - 0.5) * 0.3] : [r(), r()]).map(([x, y]) => [clamp(x, 0.02, 0.98), clamp(y, 0.02, 0.98)]);
  }, [e.n, seed]);
  const quads = [];
  const split = (x, y, s, depth) => {
    const inside = pts.filter(([px, py]) => px >= x && px < x + s && py >= y && py < y + s).length;
    if (inside > e.cap && depth < 5) { quads.push({x, y, s, depth}); const h = s / 2; [[x, y], [x + h, y], [x, y + h], [x + h, y + h]].forEach(([a, b]) => split(a, b, h, depth + 1)); }
  };
  split(0, 0, 1, 0);
  const lvl = Math.max(0, (T.t - 24) / 18);
  return (
    <g>
      <rect x={x0} y={y0} width={side} height={side} fill={alpha(C.panel, 0.9)} stroke={C.muted} strokeWidth={3} opacity={clamp(T.t / 10)}/>
      {quads.filter((q) => q.depth < lvl).map((q, k) => (
        <g key={k} opacity={clamp(lvl - q.depth)}>
          <line x1={x0 + (q.x + q.s / 2) * side} y1={y0 + q.y * side} x2={x0 + (q.x + q.s / 2) * side} y2={y0 + (q.y + q.s) * side} stroke={pal(e, q.depth)} strokeWidth={3}/>
          <line x1={x0 + q.x * side} y1={y0 + (q.y + q.s / 2) * side} x2={x0 + (q.x + q.s) * side} y2={y0 + (q.y + q.s / 2) * side} stroke={pal(e, q.depth)} strokeWidth={3}/>
        </g>
      ))}
      {pts.map(([x, y], k) => <circle key={k} cx={x0 + x * side} cy={y0 + y * side} r={7 * pop(T.t - k * 0.4)} fill={C.text}/>)}
      {!vertical && <Txt x={x0 + side + 30} y={B.cy} size={B.fs * 0.9} anchor="start" color={C.muted} op={clamp(lvl / 2)}>crowded squares split</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Dns = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const hops = [["browser", "laptop"], ["resolver", "search"], ["root", "globe"], ["TLD", "network"], ["authoritative", "server"]];
  const xs = spread(hops.length, B.x0, B.x1), y = B.cy + B.fs, cw = Math.min(210, (B.W / hops.length) * 0.82);
  const legs = [[0, 1], [1, 2], [2, 1], [1, 3], [3, 1], [1, 4], [4, 1], [1, 0]];
  const step = Math.max(0, (T.t - 24) / 16), k = Math.floor(step), ph = step - k;
  return (
    <g>
      <Chip x={xs[0]} y={B.y0 + B.fs * 0.6} text={e.domain || "example.com"} color={pal(e, 0)} p={pop(T.t)} fs={B.fs * 0.9} fill/>
      {hops.map(([nm, icon], j) => <Card key={j} x={xs[j] - cw / 2} y={y - 70} w={cw} h={140} icon={icon} label={nm} color={pal(e, j)} p={pop(T.t - j * 5)}
                                        fs={Math.min(B.fs * 0.85, cw / 8)} lit={k < legs.length && legs[k][1] === j && ph > 0.8 ? 0.6 : 0}/>)}
      {legs.map(([a, b], j) => j <= k && <path key={j} d={`M${xs[a]},${y + (a < b ? -80 : 80)} Q${(xs[a] + xs[b]) / 2},${y + (a < b ? -150 : 150)} ${xs[b]},${y + (a < b ? -80 : 80)}`}
                                             fill="none" stroke={alpha(a < b ? C.hot : C.cool, 0.5)} strokeWidth={3} strokeDasharray="6 6"/>)}
      {k < legs.length && (() => {
        const [a, b] = legs[k], up = a < b, p0 = [xs[a], y + (up ? -80 : 80)], p2 = [xs[b], y + (up ? -80 : 80)], c1 = [(xs[a] + xs[b]) / 2, y + (up ? -150 : 150)];
        const pt = [(1 - ph) ** 2 * p0[0] + 2 * (1 - ph) * ph * c1[0] + ph * ph * p2[0], (1 - ph) ** 2 * p0[1] + 2 * (1 - ph) * ph * c1[1] + ph * ph * p2[1]];
        return <circle cx={pt[0]} cy={pt[1]} r={12} fill={up ? C.hot : C.cool} style={{filter: glowF(up ? C.hot : C.cool, 0.8)}}/>;
      })()}
      {k >= legs.length && <Chip x={xs[0]} y={y + 120} text="address found" color={C.cool} p={pop(T.t - 24 - legs.length * 16)} fs={B.fs * 0.85} fill/>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Handshake = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const msgs = e.kind === "tls" ? [["ClientHello", 0], ["ServerHello + certificate", 1], ["key exchange", 0], ["Finished", 1]]
    : [["SYN", 0], ["SYN-ACK", 1], ["ACK", 0]];
  const cx = B.x0 + B.W * 0.18, sx = B.x1 - B.W * 0.18, top = B.y0 + B.fs * 2.2, rh = (B.H - B.fs * 3.4) / msgs.length;
  return (
    <g>
      {[[cx, "client", "laptop"], [sx, "server", "server"]].map(([x, nm, ic], k) => (
        <g key={k}>
          <Chip x={x} y={B.y0 + B.fs * 0.8} text={nm} color={pal(e, k)} p={pop(T.t - k * 5)} fs={B.fs} fill/>
          <line x1={x} y1={top - 10} x2={x} y2={B.y1} stroke={alpha(pal(e, k), 0.6)} strokeWidth={4} opacity={clamp(T.t / 10)}/>
        </g>
      ))}
      {msgs.map(([t, dir], j) => {
        const y0 = top + rh * j, d = glide(T.t - 20 - j * 22, 1);
        const a = dir ? [sx, y0] : [cx, y0], b = dir ? [cx, y0 + rh * 0.8] : [sx, y0 + rh * 0.8];
        return d > 0 && <Arrow key={j} a={a} b={b} draw={d} color={dir ? C.cool : C.hot} width={5} label={t} fs={Math.min(B.fs * 0.9, rh * 0.38)}/>;
      })}
      {T.t > 20 + msgs.length * 22 + 10 && <Txt x={B.cx} y={B.y1 - B.fs * 0.3} size={B.fs} color={pal(e, 0)}>{e.kind === "tls" ? "encrypted channel ready" : "connected"}</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Packets = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.count;
  const sx = B.x0 + B.W * 0.1, rx = B.x1 - B.W * 0.1, y = B.cy;
  const lost = new Set(Array.from({length: Math.round(n * e.loss)}, (_, k) => Math.floor(((k + 0.6) * n) / Math.max(1, Math.round(n * e.loss)))));
  const gap = 12, travel = 40, retryAt = 20 + n * gap + 20;
  const got = [];
  return (
    <g>
      <Card x={sx - 80} y={y - 70} w={160} h={140} icon="laptop" label="sender" color={pal(e, 0)} p={pop(T.t)} fs={B.fs * 0.8}/>
      <Card x={rx - 80} y={y - 70} w={160} h={140} icon="server" label="receiver" color={pal(e, 1)} p={pop(T.t - 4)} fs={B.fs * 0.8}/>
      {Array.from({length: n}, (_, k) => {
        const isLost = lost.has(k), s = 20 + k * gap, u = (T.t - s) / travel;
        const s2 = retryAt + [...lost].indexOf(k) * gap, u2 = (T.t - s2) / travel;
        const arrived = isLost ? u2 >= 1 : u >= 1;
        if (arrived) got.push(k);
        const lane = y + ((k % 3) - 1) * 26;
        return (
          <g key={k}>
            {!isLost && u > 0 && u < 1 && <rect x={lerp(sx + 80, rx - 100, u)} y={lane - 10} width={22} height={20} rx={4} fill={pal(e, 0)}/>}
            {isLost && u > 0 && u < 0.55 && <rect x={lerp(sx + 80, rx - 100, u)} y={lane - 10} width={22} height={20} rx={4} fill={C.hot}/>}
            {isLost && u >= 0.55 && u < 1.2 && <Txt x={lerp(sx + 80, rx - 100, 0.55)} y={lane} size={B.fs} color={C.hot} op={1.2 - u}>✕</Txt>}
            {isLost && u2 > 0 && u2 < 1 && <rect x={lerp(sx + 80, rx - 100, u2)} y={lane - 10} width={22} height={20} rx={4} fill="none" stroke={C.violet} strokeWidth={3}/>}
          </g>
        );
      })}
      <Txt x={rx} y={y + 100} size={B.fs * 0.8} color={C.muted}>{`${got.length} of ${n} arrived`}</Txt>
      {T.t > retryAt && <Txt x={B.cx} y={B.y0 + B.fs * 0.5} size={B.fs * 0.9} color={C.violet}>lost ones are sent again</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Scaling = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), both = e.mode === "both";
  const g = glide(T.k > 0 ? T.k : T.t - 40, 2);
  const panel = (x0, w, kind) => {
    const cx = x0 + w / 2, cy = B.cy + B.fs * 0.6;
    if (kind === "vertical") {
      const s = 90 + 110 * g;
      return (
        <g>
          <Txt x={cx} y={B.y0 + 4} size={B.fs} color={pal(e, 0)}>scale up</Txt>
          <Card x={cx - s / 2} y={cy - s / 2} w={s} h={s} icon="server" label="" color={pal(e, 0)} p={1}/>
          <Txt x={cx} y={cy + 140} size={B.fs * 0.8} color={C.muted}>one bigger machine</Txt>
        </g>
      );
    }
    const n = 1 + Math.round(5 * g), xs = spread(Math.min(n, 3), x0 + 20, x0 + w - 20), rows = Math.ceil(n / 3);
    return (
      <g>
        <Txt x={cx} y={B.y0 + 4} size={B.fs} color={C.cool}>scale out</Txt>
        {Array.from({length: n}, (_, k) => <Card key={k} x={xs[k % 3] - 45} y={cy - rows * 50 + Math.floor(k / 3) * 100} w={90} h={86} icon="server" label="" color={C.cool}
                                                p={pop(T.t - 40 - k * 6)}/>)}
        <Txt x={cx} y={cy + 140} size={B.fs * 0.8} color={C.muted}>more machines</Txt>
      </g>
    );
  };
  return (
    <g>
      {both ? <>{panel(B.x0, B.W * 0.48, "vertical")}<line x1={B.cx} y1={B.y0 + 20} x2={B.cx} y2={B.y1} stroke={alpha(C.muted, 0.4)} strokeWidth={3}/>{panel(B.cx + 10, B.W * 0.48, "horizontal")}</>
        : panel(B.x0, B.W, e.mode)}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Failover = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.replicas;
  const client = [B.x0 + B.W * 0.1, B.cy], px = B.x0 + B.W * 0.5, ry = row(n + 1, B.y0 + 60, B.y1 - 60);
  const dead = T.k > 0, promote = dead && T.k > 45, hb = cyc(T.t, 10, 26);
  const target = promote ? 1 : 0;
  return (
    <g>
      <Card x={client[0] - 75} y={client[1] - 60} w={150} h={120} icon="users" label="clients" color={C.text} p={pop(T.t)} fs={B.fs * 0.8}/>
      {ry.map((y, k) => {
        const isPrimary = k === target, down = k === 0 && dead;
        const col = down ? C.muted : isPrimary ? pal(e, 0) : C.cool;
        return (
          <g key={k}>
            <Card x={px - 110} y={y - 50} w={220} h={100} icon={down ? "circle-x" : isPrimary ? "crown" : "copy"} label={down ? "down" : isPrimary ? "primary" : "replica"}
                  color={col} p={pop(T.t - k * 5)} fs={B.fs * 0.85} lit={isPrimary && promote ? 0.6 : 0} dim={down}/>
            {k > 0 && !dead && <Packet pts={[[px, ry[0] + 50], [px, y - 50]]} t={hb.ph} color={pal(e, 0)} r={7}/>}
          </g>
        );
      })}
      <Arrow a={[client[0] + 75, client[1]]} b={[px - 115, ry[target]]} draw={promote ? glide(T.k - 45, 1) : glide(T.t - 10, 1)} color={promote ? pal(e, 0) : C.muted} width={5}/>
      {dead && !promote && <Txt x={px + 150} y={ry[0]} size={B.fs} anchor="start" color={C.hot}>heartbeat lost…</Txt>}
      {promote && <Txt x={px + 150} y={ry[1]} size={B.fs} anchor="start" color={pal(e, 0)} op={clamp((T.k - 45) / 12)}>promoted</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Heartbeat = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.nodes;
  const R = Math.min(B.H * 0.38, B.W * 0.3), P = (k) => [B.cx + R * Math.cos(-Math.PI / 2 + (2 * Math.PI * k) / n), B.cy + R * Math.sin(-Math.PI / 2 + (2 * Math.PI * k) / n)];
  const quiet = 1, gone = T.k > 0, timeout = gone ? clamp(T.k / 50) : 0;
  return (
    <g>
      <Card x={B.cx - 80} y={B.cy - 55} w={160} h={110} icon="activity" label="monitor" color={pal(e, 0)} p={pop(T.t)} fs={B.fs * 0.8}/>
      {Array.from({length: n}, (_, k) => {
        const [x, y] = P(k), silent = k === quiet && gone, dead = silent && timeout >= 1;
        const beat = cyc(T.t, 12 + k * 5, 30);
        return (
          <g key={k} opacity={clamp(pop(T.t - k * 4) * 2)}>
            {!silent && beat.on && <circle cx={x} cy={y} r={40 + beat.ph * 30} fill="none" stroke={pal(e, 0)} strokeWidth={3} opacity={1 - beat.ph}/>}
            {!silent && <Packet pts={[[x, y], [B.cx, B.cy]]} t={beat.ph * 1.5} color={pal(e, 0)} r={6}/>}
            {silent && !dead && <circle cx={x} cy={y} r={52} fill="none" stroke={C.hot} strokeWidth={7} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - timeout}
                                        transform={`rotate(-90 ${x} ${y})`}/>}
            <circle cx={x} cy={y} r={40} fill={dead ? alpha(C.muted, 0.2) : alpha(C.cool, 0.25)} stroke={dead ? C.hot : C.cool} strokeWidth={4}/>
            <Ico name={dead ? "circle-x" : "server"} x={x} y={y} size={40} color={dead ? C.hot : C.text}/>
            {dead && <Txt x={x} y={y + 70} size={B.fs * 0.85} color={C.hot}>marked dead</Txt>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Idempotency = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const cl = [B.x0 + B.W * 0.1, B.cy], sv = [B.cx, B.cy], st = [B.x1 - B.W * 0.12, B.cy];
  const t1 = (T.t - 20) / 30, back = (T.t - 60) / 30, retry = T.k > 0 ? T.k / 30 : -1;
  return (
    <g>
      <Card x={cl[0] - 80} y={cl[1] - 65} w={160} h={130} icon="laptop" label="client" color={C.text} p={pop(T.t)} fs={B.fs * 0.8}/>
      <Card x={sv[0] - 110} y={sv[1] - 80} w={220} h={160} icon="server" label={e.text || "server"} color={pal(e, 0)} p={pop(T.t - 4)} fs={B.fs * 0.8}/>
      <Card x={st[0] - 100} y={st[1] - 70} w={200} h={140} icon="key-round" label="seen keys" color={C.violet} p={pop(T.t - 8)} fs={B.fs * 0.8}
            sub={T.t > 50 ? "key 7f3a: done" : ""}/>
      <Packet pts={[[cl[0] + 80, cl[1] - 20], [sv[0] - 110, sv[1] - 20]]} t={t1} color={C.hot}/>
      {t1 > 0 && t1 < 1.4 && <Txt x={(cl[0] + sv[0]) / 2} y={cl[1] - 60} size={B.fs * 0.8} color={C.hot}>request + key 7f3a</Txt>}
      <Packet pts={[[sv[0] + 110, sv[1]], [st[0] - 100, st[1]]]} t={(T.t - 40) / 14} color={C.violet}/>
      {back > 0 && back < 0.5 && <Packet pts={[[sv[0] - 110, sv[1] + 20], [cl[0] + 80, cl[1] + 20]]} t={back} color={C.cool}/>}
      {back >= 0.5 && back < 1.6 && <Txt x={(cl[0] + sv[0]) / 2 + 40} y={cl[1] + 20} size={B.fs * 1.2} color={C.hot}>✕ lost</Txt>}
      {retry > 0 && <g>
        <Packet pts={[[cl[0] + 80, cl[1] - 20], [sv[0] - 110, sv[1] - 20]]} t={retry} color={C.hot}/>
        {retry > 1 && <Packet pts={[[sv[0] + 110, sv[1]], [st[0] - 100, st[1]], [sv[0] + 110, sv[1] + 10]]} t={(retry - 1) * 1.4} color={C.violet}/>}
        {retry > 1.7 && <Packet pts={[[sv[0] - 110, sv[1] + 20], [cl[0] + 80, cl[1] + 20]]} t={(retry - 1.7) * 1.4} color={C.cool}/>}
        {retry > 1.3 && <Txt x={sv[0]} y={sv[1] + 120} size={B.fs} color={C.violet}>already done: same answer, no second charge</Txt>}
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Saga = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.steps.length, f = e.fail;
  const xs = spread(n, B.x0, B.x1), cw = Math.min(240, (B.W / n) * 0.72), y = B.cy - B.H * 0.08;
  const fwd = Math.max(0, (T.t - 20) / 24), failed = f >= 0 && fwd > f + 0.6, undo = failed ? Math.max(0, (T.k > 0 ? T.k : (T.t - 20 - (f + 1) * 24)) / 24) : 0;
  return (
    <g>
      {e.steps.map((s, k) => {
        const ran = fwd > k + 0.6, bad = k === f && failed, undone = failed && k < f && undo > f - k;
        const col = bad ? C.hot : undone ? C.muted : ran ? C.cool : C.muted;
        return (
          <g key={k}>
            {k > 0 && <Arrow a={[xs[k - 1] + cw / 2, y]} b={[xs[k] - cw / 2 - 4, y]} draw={clamp(fwd - k + 0.6)} color={C.cool} width={4}/>}
            <Card x={xs[k] - cw / 2} y={y - 55} w={cw} h={110} label={s} sub={bad ? "failed" : undone ? "undone" : ran ? "done" : ""} color={col} p={pop(T.t - k * 5)}
                  fs={B.fs * 0.85} lit={bad ? 0.7 : 0}/>
            {failed && k < f && undo > f - k - 1 && <Arrow a={[xs[k + 1] - cw / 2, y + 90]} b={[xs[k], y + 70]} draw={clamp(undo - (f - k - 1))} color={C.violet} width={4}
                                                      dashed label="undo" fs={B.fs * 0.75} bend={-0.15}/>}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Gossip = ({e, rect, frame, end, vertical, seed = 0}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.nodes;
  const pos = React.useMemo(() => { const r = rng(seed + 41); return Array.from({length: n}, (_, k) => { const a = (2 * Math.PI * k) / n + r() * 0.4; const rr = 0.55 + r() * 0.4; return [a, rr]; }); }, [n, seed]);
  const P = (k) => [B.cx + Math.min(B.W * 0.4, B.H * 0.9) * pos[k][1] * Math.cos(pos[k][0]), B.cy + B.H * 0.42 * pos[k][1] * Math.sin(pos[k][0])];
  const rounds = React.useMemo(() => {
    const r = rng(seed + 43), knows = new Set([0]), out = [];
    while (knows.size < n && out.length < 8) { const sends = []; [...knows].forEach((a) => { for (let j = 0; j < 2; j++) { const b = Math.floor(r() * n); if (b !== a) sends.push([a, b]); } }); sends.forEach(([, b]) => knows.add(b)); out.push(sends); }
    return out;
  }, [n, seed]);
  const per = 28, step = Math.max(0, (T.t - 20) / per), cur = Math.floor(step);
  const knowsAt = (k) => { if (k === 0) return 0; for (let r = 0; r < rounds.length; r++) if (rounds[r].some(([, b]) => b === k)) return r + 1; return 99; };
  return (
    <g>
      {cur < rounds.length && rounds[cur].map(([a, b], j) => <Packet key={j} pts={[P(a), P(b)]} t={step - cur} color={C.hot} r={8}/>)}
      {Array.from({length: n}, (_, k) => {
        const told = step >= knowsAt(k), [x, y] = P(k);
        return (
          <g key={k} opacity={clamp(pop(T.t - k * 3) * 2)}>
            <circle cx={x} cy={y} r={34} fill={told ? alpha(C.hot, 0.45) : alpha(C.panel, 0.95)} stroke={told ? C.hot : C.muted} strokeWidth={4}
                    style={{filter: told ? glowF(C.hot, 0.4) : undefined}}/>
            <Ico name="server" x={x} y={y} size={32} color={C.text}/>
          </g>
        );
      })}
      {step >= rounds.length && <Txt x={B.cx} y={B.y1 - B.fs * 0.3} size={B.fs} color={C.hot}>every node knows</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Expiry = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.items.length;
  const ys = row(n, B.y0 + 50, B.y1 - 40), x = B.x0 + B.W * 0.2, bw = B.W * 0.45, span = Math.max(90, end - T.at);
  return (
    <g>
      <Txt x={x + bw / 2 + 130} y={B.y0 + 4} size={B.fs} color={C.muted}>{e.ttl || "TTL"}</Txt>
      {e.items.map((it, k) => {
        const born = 10 + k * 12, life = span * (0.3 + (0.75 * (n - 1 - k)) / Math.max(1, n - 1));      // the first expires first
        const left = clamp(1 - (T.t - born) / life), gone = T.t - born - life;
        const op = gone > 0 ? clamp(1 - gone / 14) : clamp((T.t - born) / 8);
        return (
          <g key={k} opacity={op} transform={`translate(${gone > 0 ? gone * 6 : 0},0)`}>
            <Chip x={x} y={ys[k]} text={it} color={pal(e, k)} p={1} fs={B.fs} fill/>
            <rect x={x + 130} y={ys[k] - 12} width={bw} height={24} rx={12} fill={alpha(C.muted, 0.2)}/>
            <rect x={x + 130} y={ys[k] - 12} width={bw * left} height={24} rx={12} fill={left < 0.25 ? C.hot : pal(e, k)}/>
            <Ico name="hourglass" x={x + 130 + bw + 40} y={ys[k]} size={36} color={left < 0.25 ? C.hot : C.muted}/>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Lock = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const ls = [B.cx, B.y0 + 70], a = [B.x0 + B.W * 0.12, B.y1 - 70], b = [B.x1 - B.W * 0.12, B.y0 + 70], st = [B.x1 - B.W * 0.12, B.y1 - 70];
  const t = T.t, k = T.k, paused = t > 50, expired = t > 90, bHas = t > 100;
  return (
    <g>
      <Card x={ls[0] - 110} y={ls[1] - 60} w={220} h={120} icon="lock" label={e.text || "lock service"} color={pal(e, 0)} p={pop(t)} fs={B.fs * 0.8}/>
      <Card x={a[0] - 90} y={a[1] - 60} w={180} h={120} icon={paused && !(k > 0) ? "pause" : "user"} label="client A" sub={paused && k <= 0 ? "paused" : ""} color={C.cool}
            p={pop(t - 4)} fs={B.fs * 0.8}/>
      <Card x={b[0] - 90} y={b[1] - 60} w={180} h={120} icon="user" label="client B" color={C.violet} p={pop(t - 8)} fs={B.fs * 0.8}/>
      <Card x={st[0] - 90} y={st[1] - 60} w={180} h={120} icon="database" label="storage" color={C.text} p={pop(t - 12)} fs={B.fs * 0.8}/>
      <Arrow a={[ls[0] - 110, ls[1]]} b={[a[0] + 20, a[1] - 62]} draw={glide(t - 16, 1)} color={C.cool} width={4} label="lease, token 33" fs={B.fs * 0.75}/>
      {expired && <Txt x={a[0]} y={a[1] + 90} size={B.fs * 0.85} color={C.hot}>lease expired</Txt>}
      {bHas && <Arrow a={[ls[0] + 110, ls[1]]} b={[b[0] - 92, b[1]]} draw={glide(t - 100, 1)} color={C.violet} width={4} label="lease, token 34" fs={B.fs * 0.75}/>}
      {k > 0 && <g>
        <Arrow a={[a[0] + 90, a[1]]} b={[st[0] - 92, st[1]]} draw={glide(k, 1)} color={C.hot} width={5} label="write, token 33" fs={B.fs * 0.75}/>
        <Txt x={st[0]} y={st[1] + 95} size={B.fs} color={C.hot} op={clamp((k - 24) / 10)}>rejected: 33 &lt; 34</Txt>
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Lru = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), cap = e.capacity, seq = e.items;
  const per = Math.max(20, (end - T.at - 40) / (seq.length + 1)), step = Math.min(seq.length, Math.max(0, Math.floor((T.t - 16) / per) + 1));
  let cache = [], evicted = null, hit = false;
  for (let j = 0; j < step; j++) {
    const it = seq[j]; hit = cache.includes(it); evicted = null;
    cache = [it, ...cache.filter((x) => x !== it)];
    if (cache.length > cap) evicted = cache.pop();
  }
  const sw = Math.min(170, (B.W * 0.62) / cap), x0 = B.cx - (sw * cap) / 2, y = B.cy, ph = clamp(((T.t - 16) % per) / 14);
  const cur = step > 0 ? seq[step - 1] : null;
  return (
    <g>
      <Txt x={x0} y={y - sw * 0.9} size={B.fs * 0.8} anchor="start" color={C.muted}>most recent</Txt>
      <Txt x={x0 + sw * cap} y={y - sw * 0.9} size={B.fs * 0.8} anchor="end" color={C.muted}>least recent</Txt>
      {Array.from({length: cap}, (_, k) => <rect key={k} x={x0 + k * sw + 6} y={y - sw * 0.4} width={sw - 12} height={sw * 0.8} rx={14} fill={alpha(C.panel, 0.9)}
                                               stroke={alpha(C.muted, 0.6)} strokeWidth={3} strokeDasharray="8 6"/>)}
      {cache.map((it, k) => (
        <g key={it} transform={`translate(${x0 + k * sw + sw / 2},${y})`}>
          <rect x={-sw / 2 + 12} y={-sw * 0.34} width={sw - 24} height={sw * 0.68} rx={12} fill={alpha(pal(e, seq.indexOf(it)), it === cur ? 0.6 : 0.3)}
                stroke={pal(e, seq.indexOf(it))} strokeWidth={it === cur ? 6 : 3} style={{filter: it === cur ? glowF(pal(e, seq.indexOf(it)), 0.6) : undefined}}/>
          <Txt x={0} y={0} size={Math.min(B.fs * 1.2, sw * 0.3)}>{it}</Txt>
        </g>
      ))}
      {evicted && <g opacity={1 - ph} transform={`translate(${x0 + cap * sw + sw * 0.6},${y + ph * 80})`}>
        <Chip x={0} y={0} text={evicted} color={C.hot} p={1} fs={B.fs} fill/>
        <Txt x={0} y={-B.fs * 1.4} size={B.fs * 0.8} color={C.hot}>evicted</Txt>
      </g>}
      {cur && <Txt x={B.cx} y={y + sw * 0.8} size={B.fs} color={hit ? C.cool : C.hot}>{`use ${cur}: ${hit ? "hit, move to front" : "miss, add at front"}`}</Txt>}
    </g>
  );
};

export const SYSTEMS2 = {backoff: Backoff, cdn: Cdn, queueing: Queueing, fanout: Fanout, statemachine: StateMachine, dag: Dag,
  mapreduce: MapReduce, windows: Windows, cdc: Cdc, bloom: Bloom, invindex: InvIndex, encoding: Encoding, evolve: Evolve,
  quadtree: Quadtree, dns: Dns, handshake: Handshake, packets: Packets, scaling: Scaling, failover: Failover,
  heartbeat: Heartbeat, idempotency: Idempotency, saga: Saga, gossip: Gossip, expiry: Expiry, lock: Lock, lru: Lru};
