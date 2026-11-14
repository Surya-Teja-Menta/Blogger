// Design-pattern and research-paper techniques (blogwriter/vizlib.py, families "pattern" and "paper"): classes and
// objects behaving the way each pattern makes them; ablations and leaderboards read the way a paper's results do.
import {Arrow, C, Card, Chip, Ico, Packet, React, Txt, alpha, box, clamp, fitFs, fmt, glide, glowF, lerp, pal, pop, row, spread,
        timing, tw} from "./kit";

const cyc = (t, start, period) => { const x = (t - start) / period; return {n: Math.floor(x), ph: x - Math.floor(x), on: t >= start}; };
const later = (T, wait) => (T.k > 0 ? T.k : T.t - wait);

// a UML-ish class box: name bar and its methods
const ClassBox = ({x, y, w, name, methods = [], color, p = 1, fs, lit = 0}) => {
  const h = fs * 1.9 + Math.max(1, methods.length) * fs * 1.3;
  return (
    <g opacity={clamp(p * 2)}>
      <rect x={x - w / 2} y={y - h / 2} width={w} height={h} rx={10} fill={alpha(C.panel, 0.97)} stroke={color} strokeWidth={lit ? 5 : 3} style={{filter: lit ? glowF(color, lit) : undefined}}/>
      <rect x={x - w / 2} y={y - h / 2} width={w} height={fs * 1.6} rx={10} fill={alpha(color, 0.4)}/>
      <Txt x={x} y={y - h / 2 + fs * 0.8} size={fs}>{name}</Txt>
      {methods.map((m, k) => <Txt key={k} x={x - w / 2 + 16} y={y - h / 2 + fs * 2.4 + k * fs * 1.3} size={fs * 0.8} anchor="start" mono weight={600}>{m}</Txt>)}
    </g>
  );
};

export const Uml = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.classes.length;
  const parents = new Set(e.links.filter((l) => l.kind === "inherits").map((l) => l.b));
  const top = e.classes.map((_, k) => k).filter((k) => parents.has(k)), rest = e.classes.map((_, k) => k).filter((k) => !parents.has(k));
  const pos = {}, w = Math.min(280, (B.W / Math.max(top.length, rest.length, 1)) * 0.7);
  spread(top.length, B.x0, B.x1).forEach((x, j) => { pos[top[j]] = [x, B.y0 + B.H * 0.24]; });
  spread(rest.length, B.x0, B.x1).forEach((x, j) => { pos[rest[j]] = [x, B.y0 + B.H * (top.length ? 0.74 : 0.5)]; });
  return (
    <g>
      {e.links.map((l, j) => {
        const a = pos[l.a], b = pos[l.b], d = glide(T.t - 24 - j * 8, 1), inh = l.kind === "inherits";
        const tip = [b[0], b[1] + (inh ? B.H * 0.12 : 0)], mid = [lerp(a[0], tip[0], d), lerp(a[1] - B.H * 0.1, tip[1], d)];
        return (
          <g key={j}>
            <line x1={a[0]} y1={a[1] - B.H * 0.1} x2={mid[0]} y2={mid[1]} stroke={C.text} strokeWidth={3} strokeDasharray={inh ? undefined : "8 6"}/>
            {d > 0.95 && inh && <path d={`M${tip[0]},${tip[1] - 2} l-16,26 l32,0 Z`} fill={C.bg} stroke={C.text} strokeWidth={3}/>}
          </g>
        );
      })}
      {e.classes.map((c, k) => <ClassBox key={k} x={pos[k][0]} y={pos[k][1]} w={w} name={c.text} methods={c.methods} color={pal(e, k)} p={pop(T.t - k * 6)} fs={Math.min(B.fs, w / 9)}
                                         lit={parents.has(k) && later(T, 80) > 0 ? 0.5 : 0}/>)}
    </g>
  );
};

export const Observer = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.observers.length, subj = [B.x0 + B.W * 0.22, B.cy], ox = B.x1 - B.W * 0.18, oy = row(n, B.y0 + 60, B.y1 - 60);
  const sub = glide(T.t - 20, 1.2), c = cyc(later(T, 70), 0, 60), notifying = later(T, 70) > 0;
  return (
    <g>
      <Card x={subj[0] - 130} y={subj[1] - 80} w={260} h={160} icon="radio" label={e.subject} sub={notifying ? `state ${c.n % 2 ? "B" : "A"}` : "state A"} color={pal(e, 0)} p={pop(T.t)} fs={B.fs * 0.85}
            lit={notifying && c.ph < 0.15 ? 0.7 : 0}/>
      {oy.map((y, k) => (
        <g key={k}>
          <Arrow a={[ox - 115, y]} b={[subj[0] + 134, subj[1] + (k - (n - 1) / 2) * 30]} draw={sub} color={alpha(C.muted, 0.9)} width={2} dashed label={k === 0 ? "subscribe" : ""} fs={B.fs * 0.7}/>
          <Card x={ox - 110} y={y - 45} w={220} h={90} label={e.observers[k]} color={pal(e, k + 1)} p={pop(T.t - 8 - k * 5)} fs={B.fs * 0.85} lit={notifying && c.ph > 0.6 ? 0.6 : 0}/>
          {notifying && <Packet pts={[[subj[0] + 130, subj[1]], [ox - 110, y]]} t={(c.ph - 0.1) * 2} color={pal(e, k + 1)}/>}
        </g>
      ))}
      {notifying && <Txt x={subj[0]} y={subj[1] + 120} size={B.fs * 0.85} color={pal(e, 0)}>changed: everyone notified</Txt>}
    </g>
  );
};

export const Strategy = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.strategies.length, ctx = [B.x0 + B.W * 0.28, B.cy], sx = B.x1 - B.W * 0.18, sy = row(n, B.y0 + 60, B.y1 - 60);
  const per = Math.max(40, (end - T.at - 30) / n), cur = Math.min(n - 1, Math.floor(Math.max(0, T.t - 24) / per)), ph = clamp(((T.t - 24) % per) / 20);
  const slot = [ctx[0] + 150, ctx[1]];
  return (
    <g>
      <Card x={ctx[0] - 150} y={ctx[1] - 90} w={300} h={180} icon="shopping-cart" label={e.context} color={C.text} p={pop(T.t)} fs={B.fs}/>
      <rect x={slot[0] - 8} y={slot[1] - 40} width={70} height={80} rx={10} fill="none" stroke={C.hot} strokeWidth={4} strokeDasharray="8 6" opacity={clamp(T.t / 10)}/>
      {sy.map((y, k) => {
        const active = k === cur && T.t > 24, x = active ? lerp(sx, slot[0] + 130, ph) : sx, yy = active ? lerp(y, slot[1], ph) : y;
        return <Chip key={k} x={x} y={yy} text={e.strategies[k]} color={pal(e, k)} p={pop(T.t - 6 - k * 4)} fs={B.fs} fill lit={active ? 0.7 : 0}/>;
      })}
      <Txt x={ctx[0]} y={B.y1 - 6} size={B.fs * 0.85} color={C.muted}>same code, swappable behaviour</Txt>
    </g>
  );
};

export const Adapter = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), fit = glide(later(T, 60), 1.4), y = B.cy;
  const left = B.x0 + B.W * 0.2, right = B.x1 - B.W * 0.2, gap = lerp(B.W * 0.25, 0, fit);
  return (
    <g>
      <Card x={left - 150} y={y - 70} w={200} h={140} icon="laptop" label={e.client} color={pal(e, 0)} p={pop(T.t)} fs={B.fs * 0.9}/>
      <rect x={left + 50} y={y - 18} width={50} height={36} fill={pal(e, 0)} opacity={clamp(T.t / 10)}/>
      <Card x={right - 50} y={y - 70} w={200} h={140} icon="server" label={e.service} color={C.violet} p={pop(T.t - 6)} fs={B.fs * 0.9}/>
      <path d={`M${right - 50},${y - 30} l-40,0 l0,20 l20,0 l0,20 l-20,0 l0,20 l40,0`} fill="none" stroke={C.violet} strokeWidth={5} opacity={clamp(T.t / 10)}/>
      {fit === 0 && T.t > 30 && <Txt x={B.cx} y={y - 90} size={B.fs} color={C.hot}>doesn't fit</Txt>}
      {fit > 0 && <g opacity={clamp(fit * 2)} transform={`translate(0,${(1 - fit) * -120})`}>
        <rect x={left + 100} y={y - 45} width={right - 90 - left - 100} height={90} rx={14} fill={alpha(C.hot, 0.35)} stroke={C.hot} strokeWidth={4}/>
        <Txt x={(left + 100 + right - 90) / 2} y={y} size={B.fs}>adapter</Txt>
      </g>}
      {fit > 0.95 && <Packet pts={[[left + 50, y], [right - 50, y]]} t={((T.t % 40) / 40)} color={C.cool}/>}
      <Txt x={B.cx} y={B.y1 - 6} size={B.fs * 0.85} color={C.muted} op={fit}>{gap < 1 ? "now they talk" : ""}</Txt>
    </g>
  );
};

export const Decorator = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.layers.length, R = Math.min(B.H * 0.46, B.W * 0.28), core = R * 0.35;
  return (
    <g>
      {e.layers.map((l, k) => {
        const kk = n - 1 - k, r = core + ((R - core) * (k + 1)) / n, p = pop(T.t - 20 - k * 16);
        return (
          <g key={k} opacity={clamp(p * 2)}>
            <circle cx={B.cx} cy={B.cy} r={r * (0.7 + 0.3 * p)} fill={alpha(pal(e, k + 1), 0.15)} stroke={pal(e, k + 1)} strokeWidth={4} strokeDasharray={kk ? undefined : undefined}/>
            <Chip x={B.cx + r * Math.cos(-0.9 + k * 0.75) + 70} y={B.cy + r * Math.sin(-0.9 + k * 0.75)} text={`+ ${l}`} color={pal(e, k + 1)} p={p} fs={B.fs * 0.85} fill/>
          </g>
        );
      })}
      <circle cx={B.cx} cy={B.cy} r={core} fill={alpha(pal(e, 0), 0.5)} stroke={pal(e, 0)} strokeWidth={4} opacity={clamp(pop(T.t) * 2)}/>
      <Txt x={B.cx} y={B.cy} size={B.fs}>{e.core}</Txt>
    </g>
  );
};

export const Factory = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.products.length, fx = B.cx, per = 34, c = cyc(T.t, 20, per), k = c.n % n;
  return (
    <g>
      <rect x={fx - 150} y={B.cy - 100} width={300} height={200} rx={18} fill={alpha(C.panel, 0.95)} stroke={pal(e, 0)} strokeWidth={4} opacity={clamp(pop(T.t) * 2)}/>
      <Ico name="factory" x={fx} y={B.cy - 20} size={80} color={pal(e, 0)}/>
      <Txt x={fx} y={B.cy + 60} size={B.fs}>factory</Txt>
      {c.on && <g>
        <Chip x={lerp(B.x0 + 80, fx - 150, clamp(c.ph * 2.5))} y={B.cy} text={`make ${e.products[k]}`} color={C.muted} p={1} fs={B.fs * 0.8} fill/>
        {c.ph > 0.5 && <Chip x={lerp(fx + 150, B.x1 - 100, clamp((c.ph - 0.5) * 2.5))} y={B.cy} text={e.products[k]} color={pal(e, k + 1)} p={1} fs={B.fs} fill lit={0.5}/>}
      </g>}
      {e.products.slice(0, Math.min(n, c.n)).map((p, j) => <Chip key={j} x={B.x1 - 100} y={B.y0 + 40 + j * B.fs * 1.9} text={p} color={pal(e, j + 1)} p={1} fs={B.fs * 0.8}/>)}
    </g>
  );
};

export const Singleton = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), callers = 5, xs = spread(callers, B.x0, B.x1);
  const P = (k) => [xs[k], B.y0 + 40 + Math.abs(k - (callers - 1) / 2) * 24];
  return (
    <g>
      <Card x={B.cx - 120} y={B.cy + B.H * 0.12 - 60} w={240} h={120} icon="box" label={e.text || "the one instance"} color={pal(e, 0)} p={pop(T.t)} fs={B.fs * 0.9} lit={later(T, 60) > 0 ? 0.6 : 0}/>
      {Array.from({length: callers}, (_, k) => {
        const [x, y] = P(k), d = glide(T.t - 16 - k * 8, 1);
        return (
          <g key={k}>
            <Ico name="user" x={x} y={y} size={50} color={pal(e, k + 1)} op={clamp(pop(T.t - k * 4) * 2)}/>
            <Arrow a={[x, y + 34]} b={[lerp(x, B.cx, 0.85), B.cy + B.H * 0.12 - 66]} draw={d} color={pal(e, k + 1)} width={3} label={k === 0 ? "get()" : ""} fs={B.fs * 0.7}/>
          </g>
        );
      })}
      <Txt x={B.cx} y={B.cy + B.H * 0.12 + 96} size={B.fs * 0.85} color={C.muted} op={clamp((T.t - 60) / 14)}>everyone gets the very same object</Txt>
    </g>
  );
};

export const Facade = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.parts.length, front = [B.x0 + B.W * 0.32, B.cy], px = B.x1 - B.W * 0.18, py = row(n, B.y0 + 40, B.y1 - 40);
  const c = cyc(T.t, 24, 60);
  return (
    <g>
      <Ico name="user" x={B.x0 + 50} y={B.cy} size={70} color={C.text} op={clamp(T.t / 10)}/>
      <Arrow a={[B.x0 + 90, B.cy]} b={[front[0] - 110, front[1]]} draw={glide(T.t - 8)} color={C.text} width={4} label="one call" fs={B.fs * 0.75}/>
      <Card x={front[0] - 110} y={front[1] - 80} w={220} h={160} icon="door-open" label={e.front} color={pal(e, 0)} p={pop(T.t)} fs={B.fs * 0.9}/>
      {py.map((y, k) => (
        <g key={k}>
          <line x1={front[0] + 110} y1={front[1]} x2={px - 100} y2={y} stroke={alpha(C.muted, 0.4)} strokeWidth={2}/>
          {py.map((y2, j) => j > k && <line key={j} x1={px - 100} y1={y} x2={px - 100} y2={y2} stroke={alpha(C.muted, 0.12)} strokeWidth={2}/>)}
          <Card x={px - 100} y={y - 35} w={200} h={70} label={e.parts[k]} color={pal(e, k + 1)} p={pop(T.t - 6 - k * 4)} fs={B.fs * 0.8} lit={c.on && Math.floor(c.ph * n) === k ? 0.5 : 0}/>
          {c.on && <Packet pts={[[front[0] + 110, front[1]], [px - 100, y]]} t={(c.ph * n - k) * 1.2} color={pal(e, k + 1)}/>}
        </g>
      ))}
      <Txt x={(front[0] + px) / 2} y={B.y1 - 4} size={B.fs * 0.8} color={C.muted}>the tangle stays hidden behind it</Txt>
    </g>
  );
};

// ================================================================================================= research papers
export const Ablation = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), items = e.items, n = items.length + 1;
  const full = Math.max(...items.map((x) => x.value)) * 1.08, values = [full, ...items.map((x) => x.value)], labels = [e.full || "full model", ...items.map((x) => x.text)];
  const lw = Math.max(...labels.map((l) => tw(l, B.fs * 0.9))) + 30, rh = (B.H - 10) / n, mx = full * 1.05;
  return (
    <g>
      {values.map((v, k) => {
        const p = glide(T.t - 10 - k * 10, 1.2), w = ((B.W - lw - 80) * v) / mx * p, y = B.y0 + rh * k + rh * 0.2, drop = k > 0 && later(T, 80) > 0;
        return (
          <g key={k}>
            <Txt x={B.x0 + lw - 16} y={y + rh * 0.3} size={B.fs * 0.9} anchor="end" color={k ? C.text : pal(e, 0)}>{labels[k]}</Txt>
            <rect x={B.x0 + lw} y={y} width={w} height={rh * 0.6} rx={8} fill={k ? alpha(C.cool, 0.7) : pal(e, 0)}/>
            {drop && <rect x={B.x0 + lw + w} y={y} width={((B.W - lw - 80) * (full - v)) / mx * glide(later(T, 80) - k * 6, 1)} height={rh * 0.6} rx={8} fill="none" stroke={C.hot} strokeWidth={3} strokeDasharray="6 5"/>}
            {e.show && k > 0 && p > 0.9 && <Txt x={B.x0 + lw + w + 14} y={y + rh * 0.3} size={B.fs * 0.8} anchor="start" color={C.text}>{fmt(v)}</Txt>}
          </g>
        );
      })}
      {later(T, 80) > 0 && <Txt x={B.x1} y={B.y1 - 4} size={B.fs * 0.85} anchor="end" color={C.hot}>the gap = what that part contributes</Txt>}
    </g>
  );
};

export const Leaderboard = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.items.length;
  const sorted = [...e.items].sort((a, b) => b.value - a.value), rh = Math.min(90, (B.H - 20) / n), w = Math.min(B.W * 0.8, 900), x0 = B.cx - w / 2;
  const settle = glide(later(T, 50), 1.6);
  return (
    <g>
      {e.items.map((it, k) => {
        const rank = sorted.indexOf(it), y = B.y0 + 10 + lerp(k, rank, settle) * rh, ours = e.ours && it.text.toLowerCase() === e.ours.toLowerCase();
        return (
          <g key={k} opacity={clamp(pop(T.t - k * 6) * 2)}>
            <rect x={x0} y={y + 4} width={w} height={rh - 8} rx={12} fill={ours ? alpha(C.hot, 0.3) : alpha(C.panel, 0.95)} stroke={ours ? C.hot : alpha(C.muted, 0.5)} strokeWidth={ours ? 5 : 2}
                  style={{filter: ours && settle > 0.9 ? glowF(C.hot, 0.6) : undefined}}/>
            <Txt x={x0 + 40} y={y + rh / 2} size={Math.min(B.fs, rh * 0.42)} color={C.muted}>{settle > 0.95 ? `#${rank + 1}` : ""}</Txt>
            <Txt x={x0 + 90} y={y + rh / 2} size={Math.min(B.fs, rh * 0.42)} anchor="start" color={ours ? C.hot : C.text}>{it.text}</Txt>
            {e.show && <Txt x={x0 + w - 30} y={y + rh / 2} size={Math.min(B.fs, rh * 0.42)} anchor="end">{fmt(it.value)}</Txt>}
          </g>
        );
      })}
    </g>
  );
};

export const PATTERNS = {uml: Uml, observer: Observer, strategy: Strategy, adapter: Adapter, decorator: Decorator, factory: Factory,
  singleton: Singleton, facade: Facade, ablation: Ablation, leaderboard: Leaderboard};
