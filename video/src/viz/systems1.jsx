// System-design techniques, part 1 (blogwriter/vizlib.py, family "system"): requests, caches, queues, logs,
// sharding, replication, consensus and storage engines, each a small working simulation of the mechanism.
import {Arrow, C, Card, Chip, Ico, Packet, React, Ring, Txt, alpha, along, box, clamp, ease, fmt, glide, glowF, lerp, pal,
        pop, rng, row, spread, timing, tw} from "./kit";

const cyc = (t, start, period) => { const x = (t - start) / period; return {n: Math.floor(x), ph: x - Math.floor(x), on: t >= start}; };
const hashOf = (s) => { let h = 2166136261; for (const ch of String(s)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967296; };

// --------------------------------------------------------------------------------------------------------------
export const Architecture = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.tiers.length;
  const cw = Math.min(260, (B.W / n) * 0.62), xs = spread(n, B.x0, B.x1);
  const cards = e.tiers.map((t, i) => {
    const m = t.count, ch = Math.min(150, (B.H * 0.86 - (m - 1) * 16) / m);
    return row(m, B.cy - ((m - 1) * (ch + 16)) / 2, B.cy + ((m - 1) * (ch + 16)) / 2).map((y) => ({x: xs[i], y, h: ch}));
  });
  const reqs = T.k > 0 ? 3 : 1, period = 70;
  return (
    <g>
      {cards.slice(0, -1).map((col, i) => col.flatMap((a, j) => cards[i + 1].map((b, k) => (
        <line key={`${i}-${j}-${k}`} x1={a.x + cw / 2} y1={a.y} x2={b.x - cw / 2} y2={b.y} stroke={alpha(C.muted, 0.35)} strokeWidth={3}
              opacity={clamp((T.t - 8 - i * 8) / 12)}/>))))}
      {cards.map((col, i) => col.map((c, j) => (
        <Card key={`c${i}-${j}`} x={c.x - cw / 2} y={c.y - c.h / 2} w={cw} h={c.h} icon={e.tiers[i].icon}
              label={j === 0 || col.length === 1 ? e.tiers[i].text : ""} color={pal(e, i)} p={pop(T.t - i * 8 - j * 3)} fs={B.fs * 0.9}/>
      )))}
      {Array.from({length: reqs}, (_, r) => {
        const c = cyc(T.t, 30 + r * (period / reqs), period);
        if (!c.on) return null;
        const pick = (i) => cards[i][(c.n + r) % cards[i].length];
        const there = cards.map((_, i) => [pick(i).x, pick(i).y]);
        const path = [...there, ...there.slice(0, -1).reverse()];
        return <Packet key={r} pts={path} t={c.ph} color={c.ph < 0.5 ? C.hot : C.cool} r={10}/>;
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Sequence = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.actors.length;
  const xs = spread(n, B.x0, B.x1), top = B.y0 + B.fs * 1.4, m = e.messages.length;
  const gap = Math.max(12, (end - T.at - 40) / (m + 1)), rowH = (B.H - B.fs * 3.2) / m;
  return (
    <g>
      {e.actors.map((a, k) => (
        <g key={k}>
          <Chip x={xs[k]} y={top} text={a} color={pal(e, k)} p={pop(T.t - k * 5)} fs={B.fs} fill/>
          <line x1={xs[k]} y1={top + B.fs} x2={xs[k]} y2={B.y1} stroke={alpha(C.muted, 0.5)} strokeWidth={3} strokeDasharray="10 10"
                opacity={clamp((T.t - 10) / 12)}/>
        </g>
      ))}
      {e.messages.map((msg, j) => {
        const s = 16 + j * gap, d = glide(T.t - s, 0.9), y = top + B.fs * 1.8 + rowH * (j + 0.5);
        if (T.t < s) return null;
        const a = xs[msg.from], b = xs[msg.to], back = b < a;
        return <Arrow key={j} a={[a, y]} b={[a === b ? a + 60 : b, y]} draw={d} color={back ? C.cool : C.hot} width={4} label={msg.text}
                      fs={Math.min(B.fs * 0.85, rowH * 0.5)} dashed={back}/>;
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const LoadBalancer = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.servers;
  const lb = [B.x0 + B.W * 0.36, B.cy], src = [B.x0 + B.fs * 1.6, B.cy];
  const ch = Math.min(110, (B.H * 0.9) / n - 14), ys = row(n, B.y0 + ch / 2 + 6, B.y1 - ch / 2 - 6), sx = B.x1 - B.W * 0.24;
  const period = 22, start = 24, sent = Math.max(0, Math.floor((T.t - start) / period) + 1);
  const busy = T.k > 0 ? 0 : -1;
  const target = (j, loads) => (e.algo === "round-robin" ? j % n : e.algo === "hash" ? Math.floor(hashOf(`u${j % 5}`) * n)
    : loads.indexOf(Math.min(...loads)));
  const loads = Array(n).fill(0), routes = [];
  for (let j = 0; j < sent; j++) {
    const w = loads.map((l, k) => l + (k === busy && T.k > 0 ? 3 : 0));
    const k = target(j, w);
    routes.push(k);
    loads[k] += 1;
  }
  const decay = (k) => Math.min(1, (routes.slice(-n * 2).filter((x) => x === k).length) / 3);
  return (
    <g>
      <Ico name="users" x={src[0]} y={src[1]} size={B.fs * 2.2} color={C.text} op={clamp(T.t / 10)}/>
      <Card x={lb[0] - 110} y={lb[1] - 70} w={220} h={140} icon="split" label={e.text || "load balancer"} color={pal(e, 0)} p={pop(T.t - 4)} fs={B.fs * 0.85}/>
      {ys.map((y, k) => (
        <g key={k}>
          <line x1={lb[0] + 110} y1={lb[1]} x2={sx - 100} y2={y} stroke={alpha(C.muted, 0.3)} strokeWidth={3}/>
          <Card x={sx - 100} y={y - ch / 2} w={200} h={ch} icon="server" label="" color={k === busy && T.k > 0 ? C.hot : C.cool} p={pop(T.t - 8 - k * 4)}
                lit={k === busy && T.k > 0 ? 0.6 : 0}/>
          <rect x={sx + 116} y={y - ch * 0.3} width={B.W * 0.12} height={ch * 0.6} rx={8} fill={alpha(C.muted, 0.2)}/>
          <rect x={sx + 116} y={y - ch * 0.3} width={B.W * 0.12 * decay(k)} height={ch * 0.6} rx={8} fill={k === busy && T.k > 0 ? C.hot : pal(e, 0)}/>
        </g>
      ))}
      {routes.slice(-4).map((k, r) => {
        const j = sent - Math.min(4, routes.length) + r, t = (T.t - start - j * period) / 30;
        return <Packet key={j} pts={[src, lb, [sx - 100, ys[k]]]} t={t} color={C.hot}/>;
      })}
      <Txt x={lb[0]} y={lb[1] + 110} size={B.fs * 0.85} color={C.muted} op={clamp((T.t - 20) / 12)}>{e.algo}</Txt>
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Cache = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const cl = [B.x0 + B.W * 0.1, B.cy], ca = [B.cx, B.cy], st = [B.x1 - B.W * 0.12, B.cy];
  const period = 54, start = 22, c = cyc(T.t, start, period);
  const hit = (j) => Math.floor((j + 1) * e.hit) > Math.floor(j * e.hit);
  const done = c.on ? c.n : 0;
  let hits = 0;
  for (let j = 0; j < done; j++) hits += hit(j) ? 1 : 0;
  const isHit = hit(c.n), ph = c.ph;
  const path = isHit ? [cl, ca, cl] : [cl, ca, st, ca, cl];
  const flash = c.on && ((isHit && ph > 0.4 && ph < 0.6) || (!isHit && ph > 0.18 && ph < 0.34));
  return (
    <g>
      <line x1={cl[0]} y1={cl[1]} x2={st[0]} y2={st[1]} stroke={alpha(C.muted, 0.35)} strokeWidth={4}/>
      <Card x={cl[0] - 80} y={cl[1] - 65} w={160} h={130} icon="laptop" label="app" color={C.text} p={pop(T.t)} fs={B.fs * 0.9}/>
      <Card x={ca[0] - 110} y={ca[1] - 80} w={220} h={160} icon="zap" label={e.cache} color={C.cool} p={pop(T.t - 6)} fs={B.fs} lit={flash ? 0.8 : 0}/>
      <Card x={st[0] - 100} y={st[1] - 80} w={200} h={160} icon="database" label={e.store} color={C.violet} p={pop(T.t - 12)} fs={B.fs}/>
      {c.on && <Packet pts={path} t={ph} color={isHit ? C.cool : C.hot} r={12}/>}
      {flash && <Txt x={ca[0]} y={ca[1] - 120} size={B.fs * 1.2} color={isHit ? C.cool : C.hot}>{isHit ? "HIT" : "MISS"}</Txt>}
      {done > 0 && <g opacity={clamp((T.t - start) / 20)}>
        <Txt x={B.cx} y={B.y1 - B.fs * 0.6} size={B.fs} color={C.muted}>{e.show ? `hit rate ${Math.round((100 * hits) / done)}%` : "hit rate"}</Txt>
        <rect x={B.cx - 160} y={B.y1 - B.fs * 2.2} width={320} height={14} rx={7} fill={alpha(C.muted, 0.25)}/>
        <rect x={B.cx - 160} y={B.y1 - B.fs * 2.2} width={(320 * hits) / done} height={14} rx={7} fill={C.cool}/>
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Queue = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const P = e.producers, K = e.consumers, start = 20;
  const prodGap = 16, consGap = 13 * (2 / K) * (P / 2) * 1.05;
  const t = Math.max(0, T.t - start), burst = e.burst && T.k > 0 ? Math.min(T.k, 70) : 0;
  const produced = Math.floor(t / prodGap) + Math.floor(burst / 5);
  const consumed = Math.min(produced, Math.floor(t / consGap));
  const L = Math.max(0, produced - consumed), slots = 12;
  const qx0 = B.x0 + B.W * 0.3, qx1 = B.x1 - B.W * 0.3, qh = Math.min(110, B.H * 0.3), cell = (qx1 - qx0) / slots;
  const py = row(P, B.cy - B.H * 0.3, B.cy + B.H * 0.3), cy = row(K, B.cy - B.H * 0.32, B.cy + B.H * 0.32);
  return (
    <g>
      {py.map((y, k) => <Card key={`p${k}`} x={B.x0} y={y - 45} w={150} h={90} icon="send" label="" color={C.cool} p={pop(T.t - k * 4)}/>)}
      {cy.map((y, k) => <Card key={`c${k}`} x={B.x1 - 150} y={y - 45} w={150} h={90} icon="cog" label="" color={C.violet} p={pop(T.t - 6 - k * 4)}/>)}
      <rect x={qx0} y={B.cy - qh / 2} width={qx1 - qx0} height={qh} rx={14} fill={alpha(C.panel, 0.9)} stroke={L >= slots ? C.hot : pal(e, 0)}
            strokeWidth={4} opacity={clamp(T.t / 10)} style={{filter: L >= slots ? glowF(C.hot, 0.8) : undefined}}/>
      {Array.from({length: Math.min(L, slots)}, (_, k) => (
        <rect key={k} x={qx1 - (k + 1) * cell + 5} y={B.cy - qh / 2 + 10} width={cell - 10} height={qh - 20} rx={8}
              fill={k >= slots * 0.75 ? C.hot : pal(e, 0)} opacity={0.85}/>
      ))}
      {e.text && <Txt x={(qx0 + qx1) / 2} y={B.cy - qh / 2 - B.fs * 0.9} size={B.fs}>{e.text}</Txt>}
      {L > slots && <Txt x={(qx0 + qx1) / 2} y={B.cy + qh / 2 + B.fs} size={B.fs} color={C.hot}>backlog</Txt>}
      {Array.from({length: 3}, (_, j) => {
        const ph = ((t + j * (prodGap / 3)) % prodGap) / prodGap;
        const y = py[j % P];
        return t > 0 ? <Packet key={`in${j}`} pts={[[B.x0 + 150, y], [qx0, B.cy]]} t={ph} color={C.cool} r={8}/> : null;
      })}
      {consumed > 0 && Array.from({length: K}, (_, j) => {
        const ph = ((t + j * 7) % consGap) / consGap;
        return <Packet key={`out${j}`} pts={[[qx1, B.cy], [B.x1 - 150, cy[j]]]} t={ph} color={C.violet} r={8}/>;
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const PubSub = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.subscribers.length;
  const pub = [B.x0 + B.W * 0.12, B.cy], topic = [B.cx - B.W * 0.05, B.cy], sx = B.x1 - B.W * 0.16;
  const ys = row(n, B.y0 + 60, B.y1 - 60), c = cyc(T.t, 24, 80);
  return (
    <g>
      <Card x={pub[0] - 100} y={pub[1] - 70} w={200} h={140} icon="send" label={e.publisher || "publisher"} color={C.cool} p={pop(T.t)} fs={B.fs * 0.9}/>
      <circle cx={topic[0]} cy={topic[1]} r={78} fill={alpha(pal(e, 0), 0.2)} stroke={pal(e, 0)} strokeWidth={5} opacity={clamp(T.t / 10)}
              style={{filter: c.on && c.ph > 0.3 && c.ph < 0.45 ? glowF(pal(e, 0), 1) : undefined}}/>
      <Ico name="radio-tower" x={topic[0]} y={topic[1] - 16} size={56} color={pal(e, 0)}/>
      <Txt x={topic[0]} y={topic[1] + 40} size={B.fs * 0.85}>{e.topic}</Txt>
      {ys.map((y, k) => {
        const got = c.on && c.ph > 0.82;
        return (
          <g key={k}>
            <line x1={topic[0] + 78} y1={topic[1]} x2={sx - 110} y2={y} stroke={alpha(C.muted, 0.3)} strokeWidth={3}/>
            <Card x={sx - 110} y={y - 40} w={220} h={80} label={e.subscribers[k]} color={pal(e, k + 1)} p={pop(T.t - 8 - k * 5)} fs={B.fs * 0.85}
                  lit={got ? 0.7 : 0}/>
            {c.on && <Packet pts={[[topic[0] + 78, topic[1]], [sx - 110, y]]} t={(c.ph - 0.42) / 0.4} color={pal(e, k + 1)}/>}
          </g>
        );
      })}
      {c.on && <Packet pts={[[pub[0] + 100, pub[1]], [topic[0] - 78, topic[1]]]} t={c.ph / 0.35} color={C.hot} r={12}/>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Log = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.entries.length;
  const cw = Math.min(190, (B.W - 20) / n), x0 = B.cx - (cw * n) / 2, y = B.y0 + B.H * 0.28, h = Math.min(110, B.H * 0.26);
  const shown = Math.min(n, Math.max(0, Math.floor((T.t - 10) / 12) + 1));
  return (
    <g>
      <Txt x={x0} y={y - h * 0.5 - B.fs * 0.7} size={B.fs * 0.8} color={C.muted} anchor="start" op={clamp(T.t / 10)}>oldest</Txt>
      <Txt x={x0 + cw * n} y={y - h * 0.5 - B.fs * 0.7} size={B.fs * 0.8} color={C.muted} anchor="end" op={clamp(T.t / 10)}>append here</Txt>
      {e.entries.map((t, k) => {
        const p = pop(T.t - 10 - k * 12);
        return (
          <g key={k} opacity={clamp(p * 2)} transform={`translate(${(1 - p) * 60},0)`}>
            <rect x={x0 + k * cw + 4} y={y - h / 2} width={cw - 8} height={h} rx={10} fill={alpha(pal(e, 0), 0.22)} stroke={pal(e, 0)} strokeWidth={3}/>
            <Txt x={x0 + (k + 0.5) * cw} y={y - h * 0.12} size={Math.min(B.fs * 0.85, (cw - 14) / Math.max(3, t.length * 0.62))}>{t}</Txt>
            <Txt x={x0 + (k + 0.5) * cw} y={y + h * 0.28} size={B.fs * 0.65} color={C.muted} weight={600}>{k}</Txt>
          </g>
        );
      })}
      {e.readers.map((r, j) => {
        const speed = [1.0, 0.55, 0.3][j], pos = Math.min(Math.max(0, shown - 1 - j * 1.6), Math.max(0, ((T.t - 30) / 14) * speed));
        const x = x0 + (Math.floor(pos) + 0.5) * cw, ry = y + h / 2 + B.fs * (1.4 + j * 1.9);
        return (
          <g key={j} opacity={clamp((T.t - 26 - j * 6) / 12)}>
            <path d={`M${x},${y + h / 2 + 8} l-14,24 l28,0 Z`} fill={pal(e, j + 1)}/>
            <line x1={x} y1={y + h / 2 + 30} x2={x} y2={ry - B.fs * 0.6} stroke={pal(e, j + 1)} strokeWidth={3}/>
            <Txt x={x} y={ry} size={B.fs * 0.85} color={pal(e, j + 1)}>{r}</Txt>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const HashRing = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const R = Math.min(B.H * 0.4, B.W * 0.3), cx = B.cx, cy = B.cy;
  const nodes = e.nodes.map((nm, k) => ({nm, a: (k + 0.15 * hashOf(nm)) / e.nodes.length, col: pal(e, k)}));
  const added = e.add && T.k > 0 ? {nm: e.add, a: (nodes[0].a + (nodes[1] ? nodes[1].a : 1)) / 2, col: C.hot} : null;
  const live = added ? [...nodes, added] : nodes;
  const P = (a, r = R) => [cx + r * Math.cos(2 * Math.PI * a - Math.PI / 2), cy + r * Math.sin(2 * Math.PI * a - Math.PI / 2)];
  const owner = (a, set) => { const s = [...set].sort((x, y) => x.a - y.a); return s.find((nd) => nd.a >= a) || s[0]; };
  const keys = Array.from({length: e.keys}, (_, k) => (k + 0.5) / e.keys + 0.013 * Math.sin(k * 7));
  const q = glide(T.k - 10, 1.4);
  return (
    <g>
      <circle cx={cx} cy={cy} r={R} fill="none" stroke={alpha(C.muted, 0.45)} strokeWidth={6} opacity={clamp(T.t / 12)}/>
      {keys.map((a, k) => {
        const before = owner(a % 1, nodes), after = owner(a % 1, live), moved = before !== after;
        const col = moved ? (q > 0.5 ? after.col : before.col) : before.col;
        const [x, y] = P(a % 1, R - 46), p = pop(T.t - 14 - k * 2);
        return (
          <g key={k} opacity={clamp(p * 2)}>
            <circle cx={x} cy={y} r={11} fill={col} style={{filter: moved && q > 0 ? glowF(C.hot, 1 - Math.abs(q - 0.5)) : undefined}}/>
            {moved && T.k > 0 && <Ring x={x} y={y} r={16} color={C.hot} frame={frame} from={T.key}/>}
          </g>
        );
      })}
      {live.map((nd, k) => {
        const [x, y] = P(nd.a), [lx, ly] = P(nd.a, R + 62), p = nd === added ? pop(T.k) : pop(T.t - k * 6);
        return (
          <g key={nd.nm} opacity={clamp(p * 2)}>
            <circle cx={x} cy={y} r={26 * (0.6 + 0.4 * p)} fill={nd.col} stroke={C.bg} strokeWidth={4} style={{filter: glowF(nd.col, 0.5)}}/>
            <Txt x={lx} y={ly} size={B.fs} color={nd.col}>{nd.nm}</Txt>
          </g>
        );
      })}
      <Txt x={cx} y={cy} size={B.fs * 0.9} color={C.muted} op={clamp(T.t / 14)}>clockwise</Txt>
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Shards = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.shards, keys = e.keys;
  const sorted = [...keys].sort();
  const shardOf = (key) => (e.by === "range" ? Math.min(n - 1, Math.floor((sorted.indexOf(key) * n) / keys.length))
    : Math.floor(hashOf(key) * n));
  const hot = e.hot ? shardOf(keys[0]) : -1;
  const kx = B.x0 + B.W * 0.08, ky = row(keys.length, B.y0 + 30, B.y1 - 30);
  const sx = B.x1 - B.W * 0.2, sh = Math.min(140, (B.H - (n - 1) * 16) / n), sy = row(n, B.y0 + sh / 2, B.y1 - sh / 2);
  const counts = Array(n).fill(0);
  return (
    <g>
      {sy.map((y, k) => {
        const lit = k === hot && T.k > 0 ? 0.5 + 0.5 * Math.sin(T.k / 5) : 0;
        return <Card key={k} x={sx - 130} y={y - sh / 2} w={260} h={sh} icon="database" label={`shard ${String.fromCharCode(65 + k)}`}
                     color={k === hot && T.k > 0 ? C.hot : pal(e, k)} p={pop(T.t - k * 5)} fs={B.fs * 0.85} lit={lit}/>;
      })}
      <Txt x={(kx + sx) / 2} y={B.y0 + 6} size={B.fs * 0.85} color={C.muted} op={clamp(T.t / 10)}>{e.by === "range" ? "by key range" : "by hash of key"}</Txt>
      {keys.map((key, j) => {
        const s = shardOf(key), slot = counts[s]++, d = glide(T.t - 20 - j * 8, 1.1);
        const target = [sx - 130 - 80 - slot * (B.fs * 4.2), sy[s]];
        const pos = [lerp(kx, target[0], d), lerp(ky[j], target[1], d)];
        return (
          <g key={j}>
            {d > 0 && d < 1 && <line x1={kx} y1={ky[j]} x2={pos[0]} y2={pos[1]} stroke={alpha(pal(e, s), 0.4)} strokeWidth={3} strokeDasharray="6 6"/>}
            <Chip x={pos[0]} y={pos[1]} text={key} color={pal(e, s)} p={pop(T.t - 6 - j * 3)} fs={B.fs * 0.8} lit={d >= 1 ? 0.3 : 0}/>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Replication = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.followers;
  const client = [B.x0 + B.W * 0.08, B.cy - B.H * 0.15], leader = [B.x0 + B.W * 0.36, B.cy - B.H * 0.15];
  const fx = B.x1 - B.W * 0.18, fy = row(n, B.y0 + 60, B.y1 - 60);
  const wAt = 26, delays = fy.map((_, k) => (e.mode === "sync" ? 26 : 26 + k * 14 + (k === n - 1 ? 9999 : 0)));
  const ackAt = e.mode === "sync" ? wAt + 30 + 26 : wAt + 26;
  const newVal = (k) => T.t > wAt + 24 + delays[k];
  const reader = [B.x0 + B.W * 0.36, B.y1 - 50], lag = n - 1;
  return (
    <g>
      <Card x={client[0] - 70} y={client[1] - 55} w={140} h={110} icon="user" label="client" color={C.text} p={pop(T.t)} fs={B.fs * 0.8}/>
      <Card x={leader[0] - 100} y={leader[1] - 70} w={200} h={140} icon="crown" label="leader" color={pal(e, 0)} p={pop(T.t - 4)} fs={B.fs * 0.9}
            sub={T.t > wAt + 20 ? "new" : "old"}/>
      <Packet pts={[[client[0] + 70, client[1]], [leader[0] - 100, leader[1]]]} t={(T.t - wAt) / 20} color={C.hot}/>
      {fy.map((y, k) => (
        <g key={k}>
          <line x1={leader[0] + 100} y1={leader[1]} x2={fx - 100} y2={y} stroke={alpha(C.muted, 0.3)} strokeWidth={3}/>
          <Card x={fx - 100} y={y - 50} w={200} h={100} label="follower" sub={newVal(k) ? "new" : "old"} color={newVal(k) ? pal(e, 0) : C.muted}
                p={pop(T.t - 8 - k * 4)} fs={B.fs * 0.8} lit={k === lag && T.k > 0 && !newVal(k) ? 0.7 : 0}/>
          {delays[k] < 9000 && <Packet pts={[[leader[0] + 100, leader[1]], [fx - 100, y]]} t={(T.t - wAt - 22 - delays[k] + 26) / 24} color={pal(e, 0)}/>}
        </g>
      ))}
      <Packet pts={[[leader[0] - 100, leader[1] + 20], [client[0] + 70, client[1] + 20]]} t={(T.t - ackAt) / 18} color={C.cool}/>
      {T.t > ackAt + 18 && <Txt x={client[0]} y={client[1] - 90} size={B.fs * 0.9} color={C.cool}>OK</Txt>}
      {e.mode === "async" && T.k > 0 && <g opacity={clamp(T.k / 12)}>
        <Card x={reader[0] - 90} y={reader[1] - 45} w={180} h={90} icon="eye" label="" color={C.violet} p={1}/>
        <Arrow a={[reader[0] + 90, reader[1]]} b={[fx - 100, fy[lag] + 30]} draw={glide(T.k, 1)} color={C.violet} label="read" fs={B.fs * 0.8}/>
        {T.k > 30 && <Txt x={reader[0]} y={reader[1] - 70} size={B.fs} color={C.hot}>stale!</Txt>}
      </g>}
      {e.text && <Txt x={B.cx} y={B.y0 + 4} size={B.fs * 0.9} color={C.muted}>{e.text}</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Quorum = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.n;
  const xs = spread(n, B.x0, B.x1), y = B.cy, r = Math.min(70, (B.W / n) * 0.32);
  const wSet = new Set(Array.from({length: e.writes}, (_, k) => k)), rSet = new Set(Array.from({length: e.reads}, (_, k) => n - 1 - k));
  const wp = glide(T.t - 20, 1.4), rp = glide(T.k, 1.4);
  return (
    <g>
      <Txt x={B.x0} y={B.y0 + B.fs * 0.5} size={B.fs} anchor="start" color={C.hot} op={clamp(wp * 2)}>{`write to W`}</Txt>
      <Txt x={B.x1} y={B.y0 + B.fs * 0.5} size={B.fs} anchor="end" color={C.cool} op={clamp(rp * 2)}>{`read from R`}</Txt>
      {xs.map((x, k) => {
        const w = wSet.has(k) && wp > 0.5, rd = rSet.has(k) && rp > 0.5, both = w && rd;
        return (
          <g key={k}>
            {wSet.has(k) && <Packet pts={[[B.x0 + 40, B.y0 + B.fs * 1.4], [x, y - r]]} t={wp * 1.2} color={C.hot}/>}
            {rSet.has(k) && <Packet pts={[[B.x1 - 40, B.y0 + B.fs * 1.4], [x, y - r]]} t={rp * 1.2} color={C.cool}/>}
            <circle cx={x} cy={y} r={r * pop(T.t - k * 4)} fill={both ? alpha(C.violet, 0.6) : w ? alpha(C.hot, 0.35) : rd ? alpha(C.cool, 0.35) : alpha(C.panel, 0.95)}
                    stroke={both ? C.violet : w ? C.hot : rd ? C.cool : C.muted} strokeWidth={both ? 7 : 4}
                    style={{filter: both ? glowF(C.violet, 0.5 + 0.5 * Math.sin(T.k / 5)) : undefined}}/>
            <Ico name="database" x={x} y={y} size={r * 0.9} color={C.text}/>
            {both && <Txt x={x} y={y + r + B.fs} size={B.fs * 0.9} color={C.violet}>overlap</Txt>}
          </g>
        );
      })}
      <Txt x={B.cx} y={B.y1 - B.fs * 0.4} size={B.fs * 1.1} op={clamp((rp - 0.6) * 4)}>W + R &gt; N</Txt>
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Raft = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.nodes;
  const R = Math.min(B.H * 0.36, B.W * 0.3), P = (k) => [B.cx + R * Math.cos(-Math.PI / 2 + (2 * Math.PI * k) / n), B.cy + R * Math.sin(-Math.PI / 2 + (2 * Math.PI * k) / n)];
  const dead = T.k > 0, cand = 2 % n, k2 = T.k;
  const elected = dead && k2 > 75, leader = elected ? cand : 0;
  const hb = cyc(dead ? (elected ? k2 - 75 : -1) : T.t, dead ? 0 : 16, 34);
  const role = (k) => (k === 0 && dead ? "down" : k === leader && (elected || !dead) ? "leader" : dead && k === cand && k2 > 30 ? "candidate" : "follower");
  return (
    <g>
      {Array.from({length: n}, (_, k) => {
        const [x, y] = P(k), rl = role(k), col = rl === "leader" ? pal(e, 0) : rl === "candidate" ? C.violet : rl === "down" ? C.muted : C.cool;
        const timeout = dead && !elected && k !== 0 ? clamp((k2 - (k === cand ? 0 : 12)) / 30) : 0;
        return (
          <g key={k} opacity={clamp(pop(T.t - k * 4) * 2)}>
            {timeout > 0 && timeout < 1 && <circle cx={x} cy={y} r={60} fill="none" stroke={C.hot} strokeWidth={6} pathLength={1} strokeDasharray={1}
                                                   strokeDashoffset={1 - timeout} transform={`rotate(-90 ${x} ${y})`}/>}
            <circle cx={x} cy={y} r={48} fill={alpha(col, rl === "down" ? 0.1 : 0.3)} stroke={col} strokeWidth={rl === "leader" ? 7 : 4}
                    style={{filter: rl === "leader" ? glowF(col, 0.7) : undefined}}/>
            <Ico name={rl === "leader" ? "crown" : rl === "down" ? "circle-x" : rl === "candidate" ? "vote" : "server"} x={x} y={y} size={46} color={col}/>
            <Txt x={x} y={y + 76} size={B.fs * 0.8} color={col}>{rl}</Txt>
          </g>
        );
      })}
      {hb.on && Array.from({length: n}, (_, k) => k !== leader && !(k === 0 && dead) && (
        <Packet key={`h${k}`} pts={[P(leader), P(k)]} t={hb.ph * 1.6} color={pal(e, 0)} r={8}/>))}
      {dead && k2 > 30 && k2 < 75 && Array.from({length: n}, (_, k) => k !== cand && k !== 0 && (
        <g key={`v${k}`}>
          <Packet pts={[P(cand), P(k)]} t={(k2 - 32) / 18} color={C.violet} r={8}/>
          <Packet pts={[P(k), P(cand)]} t={(k2 - 52) / 18} color={C.cool} r={8}/>
        </g>))}
      {dead && k2 > 40 && !elected && <Txt x={B.cx} y={B.cy} size={B.fs} color={C.violet}>vote for me?</Txt>}
      {elected && <Txt x={B.cx} y={B.cy} size={B.fs} color={pal(e, 0)} op={clamp((k2 - 75) / 12)}>new leader</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Partition = ({e, rect, frame, end, vertical, seed = 0}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.nodes, half = Math.ceil(n / 2);
  const pos = Array.from({length: n}, (_, k) => {
    const left = k < half, m = left ? half : n - half, j = left ? k : k - half;
    return [left ? B.x0 + B.W * 0.22 + (j % 2) * 110 : B.x1 - B.W * 0.22 - (j % 2) * 110, row(m, B.y0 + 70, B.y1 - 70)[j]];
  });
  const cut = glide(T.k, 1.2), msgs = 5;
  return (
    <g>
      {[e.left, e.right].map((t, k) => t && <Txt key={k} x={k ? B.x1 - B.W * 0.17 : B.x0 + B.W * 0.17} y={B.y0 + 4} size={B.fs} color={C.muted}
                                                 op={clamp(cut * 2)}>{t}</Txt>)}
      {Array.from({length: msgs}, (_, j) => {
        const c = cyc(T.t, 18 + j * 9, 45), a = (j * 3) % n, b = (j * 5 + half) % n;
        if (!c.on || a === b) return null;
        const across = a < half !== b < half, lost = across && T.k > 0 && cut > 0.5;
        const t = lost ? Math.min(c.ph, 0.5) : c.ph, mid = along([pos[a], pos[b]], 0.5);
        return (
          <g key={j}>
            <Packet pts={[pos[a], pos[b]]} t={t} color={lost ? C.hot : C.cool} r={9}/>
            {lost && c.ph > 0.5 && <Txt x={mid[0]} y={mid[1]} size={B.fs * 1.2} color={C.hot} op={1 - (c.ph - 0.5) * 2}>✕</Txt>}
          </g>
        );
      })}
      {pos.map(([x, y], k) => <Card key={k} x={x - 50} y={y - 45} w={100} h={90} icon="server" label="" color={k < half ? pal(e, 0) : C.violet} p={pop(T.t - k * 3)}/>)}
      {T.k > 0 && <path d={`M${B.cx},${B.y0} l-24,${B.H * 0.2} l40,${B.H * 0.15} l-34,${B.H * 0.2} l30,${B.H * 0.2} l-12,${B.H * 0.25}`}
                        fill="none" stroke={C.hot} strokeWidth={8} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - cut}
                        style={{filter: glowF(C.hot, 0.8)}}/>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Clocks = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.names.length;
  const xs = spread(n, B.x0, B.x1), R = Math.min(B.H * 0.26, (B.W / n) * 0.3), cy = B.y0 + R + B.fs;
  const rate = [1, 1.18, 0.86];
  const tl = B.y1 - B.fs * 1.8;
  return (
    <g>
      {xs.map((x, k) => {
        const a = ((T.t * rate[k]) / 60) * 2 * Math.PI;
        return (
          <g key={k} opacity={clamp(pop(T.t - k * 6) * 2)}>
            <circle cx={x} cy={cy} r={R} fill={alpha(C.panel, 0.9)} stroke={pal(e, k)} strokeWidth={6}/>
            {Array.from({length: 12}, (_, j) => <line key={j} x1={x + R * 0.82 * Math.sin((j * Math.PI) / 6)} y1={cy - R * 0.82 * Math.cos((j * Math.PI) / 6)}
                                                      x2={x + R * 0.94 * Math.sin((j * Math.PI) / 6)} y2={cy - R * 0.94 * Math.cos((j * Math.PI) / 6)} stroke={C.muted} strokeWidth={3}/>)}
            <line x1={x} y1={cy} x2={x + R * 0.75 * Math.sin(a)} y2={cy - R * 0.75 * Math.cos(a)} stroke={pal(e, k)} strokeWidth={6} strokeLinecap="round"/>
            <line x1={x} y1={cy} x2={x + R * 0.5 * Math.sin(a / 12)} y2={cy - R * 0.5 * Math.cos(a / 12)} stroke={C.text} strokeWidth={8} strokeLinecap="round"/>
            <Txt x={x} y={cy + R + B.fs * 0.9} size={B.fs} color={pal(e, k)}>{e.names[k]}</Txt>
          </g>
        );
      })}
      {T.k > 0 && <g opacity={clamp(T.k / 14)}>
        <line x1={B.x0 + 40} y1={tl} x2={B.x1 - 40} y2={tl} stroke={C.muted} strokeWidth={3}/>
        {[0, 1].map((j) => {
          const sw = glide(T.k - 20, 1.6), real = [0.42, 0.58][j], seen = [0.62, 0.38][j], x = B.x0 + 40 + (B.W - 80) * lerp(real, seen, sw);
          return <g key={j}><circle cx={x} cy={tl} r={14} fill={pal(e, j)}/><Txt x={x} y={tl - B.fs * 0.9} size={B.fs * 0.85} color={pal(e, j)}>{j ? "second" : "first"}</Txt></g>;
        })}
        {e.text && <Txt x={B.cx} y={tl + B.fs * 1.1} size={B.fs * 0.9} color={C.hot}>{e.text}</Txt>}
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Lamport = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.processes;
  const ys = row(n, B.y0 + 40, B.y1 - 30), x0 = B.x0 + B.fs * 3, x1 = B.x1 - 20;
  const events = React.useMemo(() => {
    const clock = Array(n).fill(0), list = [];
    const plan = [[0, -1], [1, -1], [0, 1], [2 % n, -1], [1, 2 % n], [2 % n, 0], [0, -1], [1, 0]];
    plan.forEach(([p, to], k) => {
      clock[p] += 1;
      const send = {p, c: clock[p], k};
      list.push(send);
      if (to >= 0 && to !== p) { clock[to] = Math.max(clock[to], clock[p]) + 1; list.push({p: to, c: clock[to], k: k + 0.6, from: send}); }
    });
    return list;
  }, [n]);
  const X = (k) => x0 + ((x1 - x0) * (k + 0.5)) / 8.6;
  return (
    <g>
      {ys.map((y, p) => (
        <g key={p} opacity={clamp(T.t / 10)}>
          <Txt x={B.x0 + 4} y={y} size={B.fs} anchor="start" color={pal(e, p)}>{`P${p + 1}`}</Txt>
          <line x1={x0} y1={y} x2={x1} y2={y} stroke={alpha(pal(e, p), 0.6)} strokeWidth={4}/>
        </g>
      ))}
      {events.map((ev, j) => {
        const at = 14 + ev.k * ((end - T.at - 40) / 8.6), p = pop(T.t - at), x = X(ev.k), y = ys[ev.p];
        return (
          <g key={j}>
            {ev.from && <Arrow a={[X(ev.from.k), ys[ev.from.p]]} b={[x, y]} draw={glide(T.t - at + 12, 0.7)} color={C.hot} width={3}/>}
            <circle cx={x} cy={y} r={16 * p} fill={pal(e, ev.p)}/>
            <Txt x={x} y={y - 34} size={B.fs * 0.85} op={clamp(p * 2)}>{ev.c}</Txt>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Lsm = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const mem = {x: B.x0 + 20, y: B.y0 + 20, w: B.W * 0.34, h: B.H * 0.32};
  const writes = Math.max(0, Math.floor((T.t - 16) / 9)), cap = 4, flushes = Math.floor(writes / cap), inMem = writes % cap;
  const l0 = Math.min(flushes, 3), compact = T.k > 0 ? glide(T.k, 1.6) : 0;
  const L0y = B.y0 + B.H * 0.48, L1y = B.y0 + B.H * 0.78, fw = B.W * 0.17;
  return (
    <g>
      <rect x={mem.x} y={mem.y} width={mem.w} height={mem.h} rx={14} fill={alpha(pal(e, 0), 0.15)} stroke={pal(e, 0)} strokeWidth={4}/>
      <Txt x={mem.x + 16} y={mem.y - B.fs * 0.1} size={B.fs * 0.85} anchor="start" color={pal(e, 0)}>memtable (RAM)</Txt>
      {Array.from({length: inMem}, (_, k) => <rect key={k} x={mem.x + 16 + k * (mem.w - 32) / cap} y={mem.y + mem.h * 0.25} width={(mem.w - 32) / cap - 10} height={mem.h * 0.5} rx={8} fill={pal(e, 0)}/>)}
      <Packet pts={[[B.x1, mem.y + mem.h / 2], [mem.x + mem.w, mem.y + mem.h / 2]]} t={((T.t - 16) % 9) / 9} color={C.hot}/>
      {e.text && <Txt x={B.x1 - 10} y={mem.y + mem.h / 2 - B.fs} size={B.fs * 0.85} anchor="end" color={C.hot}>{e.text}</Txt>}
      <Txt x={B.x0 + 4} y={L0y - B.fs * 0.9} size={B.fs * 0.85} anchor="start" color={C.muted}>level 0 (disk)</Txt>
      <Txt x={B.x0 + 4} y={L1y - B.fs * 0.9} size={B.fs * 0.85} anchor="start" color={C.muted}>level 1</Txt>
      {Array.from({length: l0}, (_, k) => {
        const x = B.x0 + 20 + k * (fw + 20), tx = B.x0 + 20 + (B.W * 0.6 - 3 * fw) / 2;
        return <rect key={k} x={lerp(x, tx + k * 6, compact)} y={lerp(L0y, L1y, compact)} width={fw} height={B.H * 0.12} rx={10}
                     fill={alpha(C.cool, 0.6 * (1 - compact * 0.6))} stroke={C.cool} strokeWidth={3} opacity={1 - compact * 0.7}/>;
      })}
      {compact > 0.6 && <rect x={B.x0 + 20} y={L1y} width={B.W * 0.6 * glide(T.k - 30, 1)} height={B.H * 0.14} rx={10} fill={alpha(C.violet, 0.6)} stroke={C.violet} strokeWidth={3}/>}
      {compact > 0.2 && <Txt x={B.x0 + B.W * 0.75} y={(L0y + L1y) / 2} size={B.fs} color={C.violet}>compaction</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const BTree = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), keys = e.keys;
  const per = Math.ceil(keys.length / Math.min(4, Math.ceil(keys.length / 3)));
  const leaves = []; for (let k = 0; k < keys.length; k += per) leaves.push(keys.slice(k, k + per));
  const seps = leaves.slice(1).map((l) => l[0]);
  const target = leaves.findIndex((l) => l.includes(e.find));
  const kw = Math.min(70, (B.W / (leaves.length * (per + 0.6)))), rootW = (seps.length + 0.5) * kw;
  const rootY = B.y0 + B.H * 0.2, leafY = B.y0 + B.H * 0.68, lxs = spread(leaves.length, B.x0, B.x1);
  const walk = glide(T.k, 1.6);
  return (
    <g>
      <rect x={B.cx - rootW / 2} y={rootY - 36} width={rootW} height={72} rx={12} fill={alpha(C.panel, 0.95)} stroke={pal(e, 0)} strokeWidth={4} opacity={clamp(pop(T.t) * 2)}/>
      {seps.map((s, k) => <Txt key={k} x={B.cx - rootW / 2 + kw * (k + 0.75)} y={rootY} size={Math.min(B.fs, kw * 0.5)}>{fmt(s)}</Txt>)}
      {leaves.map((l, i) => {
        const w = l.length * kw + 20, on = i === target && T.k > 0;
        return (
          <g key={i} opacity={clamp((T.t - 10 - i * 5) / 12)}>
            <line x1={B.cx - rootW / 2 + (i + 0.25) * kw} y1={rootY + 36} x2={lxs[i]} y2={leafY - 36} stroke={on ? C.hot : alpha(C.muted, 0.5)}
                  strokeWidth={on ? 7 : 3} pathLength={1} strokeDasharray={1} strokeDashoffset={on ? 1 - walk : 0}/>
            <rect x={lxs[i] - w / 2} y={leafY - 36} width={w} height={72} rx={12} fill={on && walk > 0.9 ? alpha(C.hot, 0.25) : alpha(C.panel, 0.95)}
                  stroke={on ? C.hot : C.cool} strokeWidth={on ? 5 : 3}/>
            {l.map((v, j) => {
              const hit = on && v === e.find && walk > 0.95;
              return <Txt key={j} x={lxs[i] - w / 2 + 10 + kw * (j + 0.5)} y={leafY} size={Math.min(B.fs, kw * 0.5) * (hit ? 1.25 : 1)} color={hit ? C.hot : C.text}>{fmt(v)}</Txt>;
            })}
          </g>
        );
      })}
      {T.k > 0 && <Txt x={B.cx} y={B.y1 - B.fs * 0.5} size={B.fs} color={C.hot} op={clamp(walk * 2)}>{`find ${fmt(e.find)}`}</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Index = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.rows, hitRow = Math.floor(n * 0.7);
  const tx = e.mode === "scan" ? B.cx - B.W * 0.18 : B.x1 - B.W * 0.4, tw2 = B.W * 0.36, rh = (B.H - 20) / n;
  const scan = e.mode !== "index" ? Math.min(hitRow, Math.max(0, (T.t - 20) / 7)) : -1;
  const jump = e.mode !== "scan" && (e.mode === "index" || T.k > 0) ? glide(e.mode === "index" ? T.t - 24 : T.k, 1.1) : 0;
  return (
    <g>
      {Array.from({length: n}, (_, k) => {
        const checking = scan >= 0 && Math.floor(scan) === k && scan < hitRow, found = (scan >= hitRow || jump > 0.95) && k === hitRow;
        return (
          <g key={k} opacity={clamp((T.t - k) / 10)}>
            <rect x={tx} y={B.y0 + 10 + k * rh} width={tw2} height={rh - 4} rx={6} fill={found ? alpha(C.hot, 0.4) : checking ? alpha(C.violet, 0.4) : alpha(C.panel, 0.9)}
                  stroke={found ? C.hot : alpha(C.muted, 0.7)} strokeWidth={found ? 4 : 2}/>
            {k === hitRow && e.find && <Txt x={tx + tw2 / 2} y={B.y0 + 10 + k * rh + rh / 2 - 2} size={Math.min(B.fs * 0.85, rh * 0.6)}>{e.find}</Txt>}
          </g>
        );
      })}
      {scan >= 0 && <Txt x={tx + tw2 + 20} y={B.y0 + 10 + Math.min(scan, hitRow) * rh + rh / 2} size={B.fs * 0.85} anchor="start" color={C.violet}>scan</Txt>}
      {e.mode !== "scan" && <g opacity={clamp((e.mode === "index" ? T.t : T.k) / 12)}>
        <rect x={B.x0 + 20} y={B.cy - 90} width={B.W * 0.2} height={180} rx={14} fill={alpha(pal(e, 0), 0.18)} stroke={pal(e, 0)} strokeWidth={4}/>
        <Ico name="book-open" x={B.x0 + 20 + B.W * 0.1} y={B.cy - 20} size={60} color={pal(e, 0)}/>
        <Txt x={B.x0 + 20 + B.W * 0.1} y={B.cy + 50} size={B.fs * 0.9}>index</Txt>
        <Arrow a={[B.x0 + 20 + B.W * 0.2, B.cy]} b={[tx - 8, B.y0 + 10 + hitRow * rh + rh / 2]} draw={jump} color={C.hot} width={6} bend={-0.15}/>
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Table = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), cols = e.columns.length, rows = e.rows.length;
  const cw = Math.min(300, B.W / cols), x0 = B.cx - (cw * cols) / 2, rh = Math.min(84, B.H / (rows + 1.3)), y0 = B.y0 + 6;
  const where = new Set(e.where), q = T.k > 0 ? glide(T.k, 1) : 0;
  return (
    <g>
      <rect x={x0} y={y0} width={cw * cols} height={rh} rx={10} fill={alpha(pal(e, 0), 0.35)} opacity={clamp(T.t / 10)}/>
      {e.columns.map((c, j) => <Txt key={j} x={x0 + cw * (j + 0.5)} y={y0 + rh / 2} size={Math.min(B.fs, rh * 0.45)} op={clamp(T.t / 10)}>{c}</Txt>)}
      {e.rows.map((r, i) => {
        const y = y0 + rh * (i + 1.15), p = glide(T.t - 10 - i * 8), sel = where.has(i);
        return (
          <g key={i} opacity={clamp(p * 2) * (q > 0 && !sel && where.size ? 1 - 0.65 * q : 1)}>
            <rect x={x0} y={y} width={cw * cols} height={rh - 6} rx={8} fill={sel && q > 0 ? alpha(C.hot, 0.3 * q) : alpha(C.panel, 0.9)}
                  stroke={sel && q > 0 ? C.hot : alpha(C.muted, 0.3)} strokeWidth={sel && q > 0 ? 4 : 2}/>
            {r.cells.map((c, j) => <Txt key={j} x={x0 + cw * (j + 0.5)} y={y + (rh - 6) / 2} size={Math.min(B.fs * 0.9, rh * 0.42)} weight={600}>{c}</Txt>)}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Schema = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.entities.length;
  const xs = spread(n, B.x0, B.x1), cw = Math.min(300, (B.W / n) * 0.72);
  const boxes = e.entities.map((en, k) => { const h = B.fs * 1.9 + en.fields.length * B.fs * 1.35; return {x: xs[k] - cw / 2, y: B.cy - h / 2, w: cw, h}; });
  return (
    <g>
      {e.links.map((l, j) => {
        const a = boxes[l.a], b = boxes[l.b], d = glide(T.t - 30 - j * 10, 1.2), lit = T.k > 0 && j === 0;
        const pa = [a.x + (a.x < b.x ? a.w : 0), a.y + a.h / 2], pb = [b.x + (b.x < a.x ? b.w : 0), b.y + b.h / 2];
        return <Arrow key={j} a={pa} b={pb} draw={d} color={lit ? C.hot : C.muted} width={lit ? 6 : 4} head={false} label={lit ? "1 : many" : ""} fs={B.fs * 0.85}/>;
      })}
      {e.entities.map((en, k) => {
        const bx = boxes[k], p = pop(T.t - k * 8);
        return (
          <g key={k} opacity={clamp(p * 2)}>
            <rect x={bx.x} y={bx.y} width={bx.w} height={bx.h} rx={14} fill={alpha(C.panel, 0.95)} stroke={pal(e, k)} strokeWidth={4}/>
            <rect x={bx.x} y={bx.y} width={bx.w} height={B.fs * 1.6} rx={14} fill={alpha(pal(e, k), 0.4)}/>
            <Txt x={bx.x + bx.w / 2} y={bx.y + B.fs * 0.8} size={B.fs}>{en.text}</Txt>
            {en.fields.map((f, j) => <Txt key={j} x={bx.x + 20} y={bx.y + B.fs * 2.4 + j * B.fs * 1.35} size={B.fs * 0.85} anchor="start" weight={600}
                                          color={/\bid\b/i.test(f) ? C.hot : C.text}>{f}</Txt>)}
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Transactions = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.ops.length;
  const ya = B.y0 + B.H * 0.3, yb = B.y0 + B.H * 0.72, x0 = B.x0 + B.fs * 4, xs = spread(n, x0, B.x1);
  const gap = Math.max(10, (T.key - T.at - 20) / n);
  const lastW = [...e.ops.keys()].filter((k) => /write|update|set|save/i.test(e.ops[k].text));
  const clash = lastW.length >= 2 ? lastW.slice(-2) : [n - 2, n - 1];
  return (
    <g>
      {[[ya, e.a, 0], [yb, e.b, 1]].map(([y, nm, k]) => (
        <g key={k} opacity={clamp(T.t / 10)}>
          <Txt x={B.x0 + 4} y={y} size={B.fs} anchor="start" color={pal(e, k)}>{nm}</Txt>
          <line x1={x0 - 20} y1={y} x2={B.x1} y2={y} stroke={alpha(pal(e, k), 0.5)} strokeWidth={4}/>
        </g>
      ))}
      <Txt x={B.x1} y={B.y1 - B.fs * 0.3} size={B.fs * 0.8} anchor="end" color={C.muted} op={clamp(T.t / 10)}>time →</Txt>
      {e.ops.map((op, j) => {
        const y = op.t === "a" ? ya : yb, p = pop(T.t - 12 - j * gap), bad = T.k > 0 && clash.includes(j);
        return <Chip key={j} x={xs[j]} y={y + (op.t === "a" ? -1 : 1) * B.fs * 1.2} text={op.text} color={bad ? C.hot : pal(e, op.t === "a" ? 0 : 1)}
                     p={p} fs={Math.min(B.fs * 0.8, (B.W / n) / Math.max(4, op.text.length * 0.66))} lit={bad ? 0.6 : 0}/>;
      })}
      {T.k > 0 && <g opacity={clamp(T.k / 10)}>
        <line x1={xs[clash[0]]} y1={ya} x2={xs[clash[1]]} y2={yb} stroke={C.hot} strokeWidth={6} strokeDasharray="12 8"/>
        <Txt x={(xs[clash[0]] + xs[clash[1]]) / 2 + 30} y={(ya + yb) / 2} size={B.fs * 1.1} color={C.hot} anchor="start">conflict</Txt>
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Mvcc = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.versions.length;
  const vx = B.x1 - B.W * 0.38, vw = B.W * 0.34, vh = Math.min(90, (B.H - 20) / n - 12);
  const shown = Math.min(n, 1 + Math.floor(Math.max(0, T.t - 10) / 24)) + (T.k > 0 ? 0 : 0);
  const vy = (k) => B.y1 - (k + 1) * (vh + 12);
  return (
    <g>
      {e.versions.slice(0, shown).map((v, k) => {
        const newest = k === shown - 1, p = pop(T.t - 10 - k * 24);
        return (
          <g key={k} opacity={clamp(p * 2)} transform={`translate(0,${(1 - p) * -40})`}>
            <rect x={vx} y={vy(k)} width={vw} height={vh} rx={12} fill={newest ? alpha(pal(e, 0), 0.3) : alpha(C.panel, 0.9)} stroke={newest ? pal(e, 0) : C.muted} strokeWidth={3}/>
            <Txt x={vx + vw / 2} y={vy(k) + vh / 2} size={Math.min(B.fs, vh * 0.42)}>{v}</Txt>
            <Txt x={vx + vw + 14} y={vy(k) + vh / 2} size={B.fs * 0.7} anchor="start" color={C.muted}>{`v${k + 1}`}</Txt>
          </g>
        );
      })}
      {e.readers.map((r, j) => {
        const last = e.readers.length - 1;                        // the last reader started last: it sees the newest version
        const sees = j === last ? shown - 1 : Math.max(0, shown - 2 - (last - 1 - j));
        const ry = vy(sees) + vh / 2 + (e.readers.length > 1 ? 0 : 0);
        const d = glide(T.k > 0 ? T.k - j * 8 : T.t - 60 - j * 10, 1.2);
        return (
          <g key={j} opacity={clamp(d * 2)}>
            <Chip x={B.x0 + B.W * 0.15} y={ry} text={r} color={pal(e, j + 1)} p={1} fs={B.fs * 0.9} fill/>
            <Arrow a={[B.x0 + B.W * 0.15 + tw(r, B.fs * 0.9) / 2 + 30, ry]} b={[vx - 10, vy(sees) + vh / 2]} draw={d} color={pal(e, j + 1)} width={4}
                   label="snapshot" fs={B.fs * 0.75}/>
          </g>
        );
      })}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const TwoPC = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.participants;
  const co = [B.cx, B.y0 + 70], xs = spread(n, B.x0, B.x1), py = B.y1 - 70;
  const phase1 = T.t - 20, vote = phase1 - 26, phase2 = T.k;
  const no = e.fail ? n - 1 : -1, decision = e.fail ? "abort" : "commit";
  return (
    <g>
      <Card x={co[0] - 130} y={co[1] - 60} w={260} h={120} icon="crown" label="coordinator" color={pal(e, 0)} p={pop(T.t)} fs={B.fs * 0.85}/>
      {xs.map((x, k) => {
        const voted = vote > 22 + k * 3, done = phase2 > 26;
        const col = done ? (e.fail ? C.hot : C.cool) : C.muted;
        return (
          <g key={k}>
            <line x1={co[0]} y1={co[1] + 60} x2={x} y2={py - 55} stroke={alpha(C.muted, 0.3)} strokeWidth={3}/>
            <Card x={x - 90} y={py - 55} w={180} h={110} icon="database" label="" color={col} p={pop(T.t - 6 - k * 4)} lit={done ? 0.5 : 0}/>
            <Packet pts={[[co[0], co[1] + 60], [x, py - 55]]} t={phase1 / 22} color={C.violet}/>
            {phase1 > 22 && <Packet pts={[[x, py - 55], [co[0], co[1] + 60]]} t={(vote - k * 3) / 22} color={k === no ? C.hot : C.cool}/>}
            {voted && <Txt x={x} y={py + 80} size={B.fs * 0.9} color={k === no ? C.hot : C.cool}>{k === no ? "✗ no" : "✓ yes"}</Txt>}
            {phase2 > 0 && <Packet pts={[[co[0], co[1] + 60], [x, py - 55]]} t={phase2 / 24} color={e.fail ? C.hot : pal(e, 0)}/>}
          </g>
        );
      })}
      <Txt x={co[0] + 170} y={co[1] - 20} size={B.fs * 0.9} anchor="start" color={C.violet} op={clamp(phase1 / 10) * (phase2 > 0 ? 0.3 : 1)}>1. prepare?</Txt>
      {phase2 > 0 && <Txt x={co[0] + 170} y={co[1] + 26} size={B.fs * 0.9} anchor="start" color={e.fail ? C.hot : pal(e, 0)}>{`2. ${decision}!`}</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const TokenBucket = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), cap = e.capacity;
  const bx = B.cx, bw = Math.min(260, B.W * 0.24), bh = Math.min(B.H * 0.62, 320), by = B.cy - bh / 2 + 30;
  const t = Math.max(0, T.t - 10), refill = 14, burst = T.k > 0;
  const reqGap = burst ? 5 : 22, reqs = Math.floor(Math.max(0, T.t - 30) / reqGap) + (burst ? Math.floor(Math.max(0, T.key - T.at - 30) / 22) : 0);
  let tokens = cap, served = [], last = 0;
  const firstReq = 30, ev = [];
  for (let j = 0; j < Math.floor(Math.max(0, T.key - T.at - firstReq) / 22) + 1 && !burst; j++) ev.push(firstReq + j * 22);
  const times = [];
  for (let s = firstReq; s <= T.t; s += 22) { if (T.at + s >= T.key) break; times.push(s); }
  for (let s = T.key - T.at; burst && s <= T.t; s += 5) times.push(s);
  times.forEach((s) => { tokens = Math.min(cap, tokens + (s - last) / refill); last = s; if (tokens >= 1) { tokens -= 1; served.push([s, true]); } else served.push([s, false]); });
  tokens = Math.min(cap, tokens + (T.t - last) / refill);
  const level = Math.floor(tokens);
  return (
    <g>
      <path d={`M${bx - bw / 2},${by} L${bx - bw / 2 + 20},${by + bh} L${bx + bw / 2 - 20},${by + bh} L${bx + bw / 2},${by}`} fill={alpha(C.panel, 0.9)}
            stroke={pal(e, 0)} strokeWidth={5} opacity={clamp(T.t / 10)}/>
      {Array.from({length: level}, (_, k) => {
        const cols = 3, r = Math.min(28, bw / 8), i = Math.floor(k / cols), j = k % cols;
        return <circle key={k} cx={bx - r * 2.3 + j * r * 2.3} cy={by + bh - r - 10 - i * r * 2.2} r={r} fill={C.hot} style={{filter: glowF(C.hot, 0.4)}}/>;
      })}
      <Packet pts={[[bx, B.y0], [bx, by + 20]]} t={(t % refill) / refill} color={C.hot} r={12}/>
      <Txt x={bx} y={B.y0 + 4} size={B.fs * 0.8} color={C.muted}>tokens drip in</Txt>
      {e.text && <Txt x={bx} y={by + bh + B.fs * 1.1} size={B.fs} color={pal(e, 0)}>{e.text}</Txt>}
      {served.slice(-5).map(([s, ok], j) => {
        const u = (T.t - s) / 26;
        return ok ? <Packet key={`${s}`} pts={[[B.x0 + 20, B.cy], [bx - bw / 2, B.cy], [B.x1 - 20, B.cy]]} t={u} color={C.cool}/>
          : <g key={`${s}`}><Packet pts={[[B.x0 + 20, B.cy + 40], [bx - bw / 2 - 30, B.cy + 40], [B.x0 + 60, B.cy + 120]]} t={u} color={C.hot}/>
              {u > 0.45 && u < 1 && <Txt x={bx - bw / 2 - 70} y={B.cy + 40} size={B.fs * 1.1} color={C.hot}>✕</Txt>}</g>;
      })}
      {burst && <Txt x={B.x0 + 30} y={B.cy - 60} size={B.fs} anchor="start" color={C.hot} op={clamp(T.k / 10)}>burst!</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Circuit = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const fails = T.k > 0 ? Math.min(3, 1 + Math.floor(T.k / 14)) : 0;
  const state = T.k < 0 ? "closed" : T.k < 42 ? "closed" : T.k < 100 ? "open" : T.k < 130 ? "half-open" : "closed";
  const states = [["closed", C.cool], ["open", C.hot], ["half-open", C.violet]];
  const sx = row(3, B.x0 + B.W * 0.15, B.x1 - B.W * 0.15), sy = B.y0 + B.H * 0.22;
  const c = cyc(T.t, 18, 30), pass = state !== "open";
  const svc = [B.x1 - B.W * 0.12, B.y0 + B.H * 0.7], app = [B.x0 + B.W * 0.1, B.y0 + B.H * 0.7], brk = [B.cx, B.y0 + B.H * 0.7];
  return (
    <g>
      {states.map(([nm, col], k) => {
        const on = state === nm;
        return <Chip key={nm} x={sx[k]} y={sy} text={nm} color={col} p={pop(T.t - k * 4)} fs={B.fs} lit={on ? 0.8 : 0} fill={on}/>;
      })}
      <Card x={app[0] - 80} y={app[1] - 60} w={160} h={120} icon="laptop" label="app" color={C.text} p={pop(T.t)} fs={B.fs * 0.8}/>
      <Card x={svc[0] - 100} y={svc[1] - 60} w={200} h={120} icon="server" label={e.text || "service"} color={T.k > 0 && T.k < 130 ? C.hot : C.cool} p={pop(T.t - 4)} fs={B.fs * 0.75}/>
      <circle cx={brk[0]} cy={brk[1]} r={50} fill={alpha(state === "open" ? C.hot : state === "half-open" ? C.violet : C.cool, 0.25)}
              stroke={state === "open" ? C.hot : state === "half-open" ? C.violet : C.cool} strokeWidth={5}/>
      <line x1={brk[0] - 30} y1={brk[1]} x2={brk[0] + 30} y2={brk[1] - (state === "open" ? 34 : 0)} stroke={C.text} strokeWidth={7} strokeLinecap="round"/>
      {c.on && (pass ? <Packet pts={[[app[0] + 80, app[1]], brk, [svc[0] - 100, svc[1]]]} t={c.ph} color={T.k > 0 && T.k < 42 ? C.hot : C.cool}/>
        : <Packet pts={[[app[0] + 80, app[1]], [brk[0] - 50, brk[1]], [app[0] + 80, app[1] + 20]]} t={c.ph} color={C.violet}/>)}
      {Array.from({length: fails}, (_, k) => <Txt key={k} x={brk[0] - 40 + k * 40} y={brk[1] + 90} size={B.fs * 1.2} color={C.hot}>✕</Txt>)}
      {state === "open" && <Txt x={brk[0]} y={brk[1] - 80} size={B.fs * 0.9} color={C.hot}>fail fast</Txt>}
    </g>
  );
};

export const SYSTEMS1 = {architecture: Architecture, sequence: Sequence, loadbalancer: LoadBalancer, cache: Cache, queue: Queue,
  pubsub: PubSub, log: Log, hashring: HashRing, shards: Shards, replication: Replication, quorum: Quorum, raft: Raft,
  partition: Partition, clocks: Clocks, lamport: Lamport, lsm: Lsm, btree: BTree, index: Index, table: Table, schema: Schema,
  transactions: Transactions, mvcc: Mvcc, twopc: TwoPC, tokenbucket: TokenBucket, circuit: Circuit};
