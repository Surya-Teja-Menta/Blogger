// Kubernetes and MLOps / AIOps / LLMOps techniques (blogwriter/vizlib.py, families "k8s" and "ops"): clusters that
// schedule, roll out, scale and heal themselves; pipelines that train, check, ship, watch and compare models.
import {Arrow, C, Card, Chip, Ico, Packet, React, Txt, alpha, box, clamp, fitFs, gauss, glide, glowF, lerp, pal, pop, row,
        smoothPath, spread, timing} from "./kit";

const cyc = (t, start, period) => { const x = (t - start) / period; return {n: Math.floor(x), ph: x - Math.floor(x), on: t >= start}; };
const later = (T, wait) => (T.k > 0 ? T.k : T.t - wait);

const Pod = ({x, y, s, color, label, p = 1, dead = false, fs = 20}) => (
  <g opacity={clamp(p * 2)} transform={`translate(${x},${y}) scale(${0.5 + 0.5 * p})`}>
    <path d={`M0,${-s / 2} L${s * 0.43},${-s / 4} L${s * 0.43},${s / 4} L0,${s / 2} L${-s * 0.43},${s / 4} L${-s * 0.43},${-s / 4} Z`} fill={alpha(dead ? C.muted : color, dead ? 0.15 : 0.4)}
          stroke={dead ? C.hot : color} strokeWidth={3}/>
    {label && <Txt x={0} y={0} size={fs}>{label}</Txt>}
    {dead && <Txt x={0} y={0} size={s * 0.45} color={C.hot}>✕</Txt>}
  </g>
);

// ================================================================================================= Kubernetes
export const K8sCluster = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), N = e.nodes, P = e.pods;
  const nx = spread(N, B.x0, B.x1), nw = Math.min(320, (B.W / N) * 0.82), ny = B.y0 + B.H * 0.42, nh = B.H * 0.56, sched = [B.cx, B.y0 + 40];
  const placed = Math.min(P, Math.floor(Math.max(0, T.t - 24) / 14));
  const node = (k) => k % N, slot = (k) => Math.floor(k / N);
  return (
    <g>
      <Card x={sched[0] - 130} y={sched[1] - 40} w={260} h={80} icon="calendar" label="scheduler" color={C.hot} p={pop(T.t)} fs={B.fs * 0.85}/>
      {nx.map((x, k) => (
        <g key={k} opacity={clamp(pop(T.t - 4 - k * 4) * 2)}>
          <rect x={x - nw / 2} y={ny} width={nw} height={nh} rx={16} fill={alpha(C.panel, 0.9)} stroke={pal(e, 0)} strokeWidth={3}/>
          <Txt x={x} y={ny + B.fs * 0.8} size={B.fs * 0.85} color={pal(e, 0)}>{`node ${k + 1}`}</Txt>
        </g>
      ))}
      {Array.from({length: placed + 1 > P ? P : placed + 1}, (_, k) => {
        const tx = nx[node(k)] - nw / 2 + 50 + (slot(k) % 3) * ((nw - 100) / 2), ty = ny + B.fs * 2.2 + Math.floor(slot(k) / 3) * 70 + 20;
        const d = k < placed ? 1 : glide(((T.t - 24) % 14) * 1.4, 0.5);
        return <Pod key={k} x={lerp(sched[0], tx, d)} y={lerp(sched[1] + 40, ty, d)} s={56} color={C.cool} label="" p={1}/>;
      })}
      <Txt x={vertical ? B.cx : B.x1} y={vertical ? B.y1 - 4 : sched[1]} size={B.fs * 0.8} anchor={vertical ? "middle" : "end"} color={C.muted}>pods placed where there is room</Txt>
    </g>
  );
};

export const Rollout = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.replicas, xs = spread(n, B.x0, B.x1), y = B.cy;
  const per = Math.max(20, (end - T.at - 40) / (n + 0.5)), step = Math.max(0, (T.t - 20) / per);
  return (
    <g>
      <Txt x={B.x0} y={B.y0 + B.fs * 0.4} size={B.fs} anchor="start" color={C.muted}>v1</Txt>
      <Txt x={B.x1} y={B.y0 + B.fs * 0.4} size={B.fs} anchor="end" color={pal(e, 0)}>v2</Txt>
      {xs.map((x, k) => {
        const swap = clamp(step - k), isNew = swap >= 1;
        return (
          <g key={k}>
            <Pod x={x} y={y - 60 * swap} s={110} color={C.muted} label="v1" p={1 - swap} fs={B.fs * 0.8}/>
            <Pod x={x} y={y + 60 * (1 - swap)} s={110} color={pal(e, 0)} label="v2" p={swap} fs={B.fs * 0.8}/>
            {isNew && <Ico name="circle-check" x={x} y={y + 90} size={30} color={pal(e, 0)}/>}
          </g>
        );
      })}
      <rect x={B.x0} y={B.y1 - 30} width={B.W} height={14} rx={7} fill={alpha(C.cool, 0.6)}/>
      <Txt x={B.cx} y={B.y1 - 44} size={B.fs * 0.85} color={C.cool}>traffic keeps flowing: no downtime</Txt>
    </g>
  );
};

export const Hpa = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), mx = e.most;
  const t = clamp((T.t - 10) / Math.max(40, end - T.at - 20)), load = Math.sin(Math.PI * t) * 0.95 + 0.05, pods = Math.max(1, Math.min(mx, Math.round(1 + (mx - 1) * Math.max(0, (load - 0.3) / 0.65))));
  const gx0 = B.x0 + 20, gw = B.W * 0.4, gy0 = B.y0 + 20, gh = B.H - 60, target = 0.6;
  const pts = Array.from({length: 40}, (_, j) => { const u = (j / 39) * t; return [gx0 + (gw * j) / 39, gy0 + gh - gh * (Math.sin(Math.PI * u) * 0.95 + 0.05)]; });
  const px = spread(mx, B.x0 + B.W * 0.5, B.x1);
  return (
    <g>
      <rect x={gx0} y={gy0} width={gw} height={gh} rx={12} fill={alpha(C.panel, 0.9)} stroke={alpha(C.muted, 0.5)} strokeWidth={2}/>
      <line x1={gx0} y1={gy0 + gh * (1 - target)} x2={gx0 + gw} y2={gy0 + gh * (1 - target)} stroke={C.hot} strokeWidth={3} strokeDasharray="8 8"/>
      <Txt x={gx0 + gw - 10} y={gy0 + gh * (1 - target) - 16} size={B.fs * 0.75} anchor="end" color={C.hot}>target CPU</Txt>
      <path d={smoothPath(pts)} fill="none" stroke={pal(e, 0)} strokeWidth={5}/>
      <Txt x={gx0 + gw / 2} y={gy0 + gh + B.fs * 0.8} size={B.fs * 0.85} color={C.muted}>CPU load</Txt>
      {px.map((x, k) => <Pod key={k} x={x} y={B.cy} s={Math.min(100, (B.W * 0.5) / mx)} color={C.cool} p={k < pods ? 1 : 0}/>)}
      <Txt x={(B.x0 + B.W * 0.5 + B.x1) / 2} y={B.cy + 90} size={B.fs} color={C.cool}>{`${pods} pod${pods > 1 ? "s" : ""}`}</Txt>
    </g>
  );
};

export const K8sService = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.pods, svc = [B.x0 + B.W * 0.38, B.cy], px = B.x1 - B.W * 0.15, py = row(n, B.y0 + 60, B.y1 - 60);
  const c = cyc(T.t, 20, 26), replaced = later(T, 90) > 0 ? Math.min(n - 1, 0) : -1;
  return (
    <g>
      <Ico name="users" x={B.x0 + 50} y={B.cy} size={70} color={C.text} op={clamp(T.t / 10)}/>
      <Card x={svc[0] - 120} y={svc[1] - 70} w={240} h={140} icon="network" label="service" sub={e.text} color={pal(e, 0)} p={pop(T.t)} fs={B.fs * 0.85}/>
      {py.map((y, k) => {
        const fresh = k === replaced, p = fresh ? pop(later(T, 90) - 10) : pop(T.t - 6 - k * 4);
        return (
          <g key={k}>
            <line x1={svc[0] + 120} y1={svc[1]} x2={px - 60} y2={y} stroke={alpha(C.muted, 0.35)} strokeWidth={3}/>
            <Pod x={px} y={y} s={100} color={fresh ? C.hot : C.cool} label="pod" p={p} fs={B.fs * 0.75}/>
          </g>
        );
      })}
      {c.on && <Packet pts={[[B.x0 + 90, B.cy], [svc[0] - 120, svc[1]], [svc[0] + 120, svc[1]], [px - 60, py[c.n % n]]]} t={c.ph} color={C.hot}/>}
      <Txt x={svc[0]} y={svc[1] + 110} size={B.fs * 0.8} color={C.muted}>one stable address</Txt>
    </g>
  );
};

export const SelfHeal = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.desired, xs = spread(n, B.x0 + B.W * 0.3, B.x1), y = B.cy;
  const k2 = later(T, 50), crashed = k2 > 0 && k2 < 40, back = k2 >= 40, victim = Math.floor(n / 2);
  return (
    <g>
      <Card x={B.x0} y={y - 90} w={B.W * 0.24} h={180} icon="refresh-cw" label="controller" color={pal(e, 0)} p={pop(T.t)} fs={B.fs * 0.85}
            sub={crashed ? "actual < desired" : "actual = desired"}/>
      {xs.map((x, k) => (
        <g key={k}>
          <Pod x={x} y={y} s={110} color={C.cool} label="" p={k === victim && back ? glide(k2 - 40, 1) : pop(T.t - k * 4)} dead={k === victim && crashed}/>
          {k === victim && crashed && k2 > 12 && <Arrow a={[B.x0 + B.W * 0.24 + 10, y]} b={[x - 60, y]} draw={glide(k2 - 12, 0.8)} color={C.hot} width={4} label="replace" fs={B.fs * 0.75}/>}
        </g>
      ))}
      <Txt x={(B.x0 + B.W * 0.3 + B.x1) / 2} y={y + 100} size={B.fs * 0.85} color={crashed ? C.hot : C.muted}>{crashed ? "a pod crashed" : "desired state kept"}</Txt>
    </g>
  );
};

export const Containers = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.apps.length, half = B.W * 0.46, q = glide(later(T, 40), 1.4);
  const stack = (x0, kind) => {
    const w = half, cw = w / n, os = kind === "vm";
    return (
      <g>
        <Txt x={x0 + w / 2} y={B.y0 + B.fs * 0.3} size={B.fs} color={os ? C.muted : pal(e, 0)}>{os ? "virtual machines" : "containers"}</Txt>
        <rect x={x0} y={B.y1 - 50} width={w} height={44} rx={8} fill={alpha(C.muted, 0.35)}/>
        <Txt x={x0 + w / 2} y={B.y1 - 28} size={B.fs * 0.8}>hardware</Txt>
        <rect x={x0} y={B.y1 - 100} width={w} height={44} rx={8} fill={alpha(os ? C.muted : pal(e, 0), 0.35)}/>
        <Txt x={x0 + w / 2} y={B.y1 - 78} size={B.fs * 0.8}>{os ? "hypervisor" : "one shared OS kernel"}</Txt>
        {e.apps.map((a, k) => {
          const x = x0 + k * cw + 6, p = pop((os ? T.t : q * 30) - k * 6), h = os ? B.H * 0.52 : B.H * 0.26;
          return (
            <g key={k} opacity={clamp(p * 2)}>
              <rect x={x} y={B.y1 - 106 - h} width={cw - 12} height={h} rx={10} fill={alpha(C.panel, 0.95)} stroke={os ? C.muted : C.cool} strokeWidth={3}/>
              <Txt x={x + (cw - 12) / 2} y={B.y1 - 106 - h + B.fs} size={fitFs(a, B.fs * 0.8, cw - 20)}>{a}</Txt>
              {os && <rect x={x + 8} y={B.y1 - 140} width={cw - 28} height={30} rx={6} fill={alpha(C.hot, 0.4)}/>}
              {os && <Txt x={x + (cw - 12) / 2} y={B.y1 - 125} size={B.fs * 0.6}>guest OS</Txt>}
            </g>
          );
        })}
      </g>
    );
  };
  return <g>{stack(B.x0, "vm")}{q > 0 && <g opacity={q}>{stack(B.x1 - half, "ct")}</g>}</g>;
};

// ================================================================================================= MLOps / AIOps / LLMOps
export const MlPipeline = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.stages.length, xs = spread(n, B.x0, B.x1), y = B.cy - 20, cw = Math.min(200, (B.W / n) * 0.8);
  const step = Math.max(0, (T.t - 16) / 18), loop = later(T, 140) > 0 ? glide(later(T, 140), 1.6) : 0;
  return (
    <g>
      {e.stages.map((s, k) => {
        const on = step > k, gate = /eval|test|valid|check/i.test(s);
        return (
          <g key={k}>
            {k > 0 && <Arrow a={[xs[k - 1] + cw / 2, y]} b={[xs[k] - cw / 2 - 4, y]} draw={clamp(step - k + 0.5)} color={C.muted} width={3}/>}
            <rect x={xs[k] - cw / 2} y={y - 45} width={cw} height={90} rx={gate ? 45 : 14} fill={on ? alpha(pal(e, k), 0.35) : alpha(C.panel, 0.95)} stroke={pal(e, k)} strokeWidth={on ? 4 : 2}
                  opacity={clamp(pop(T.t - k * 4) * 2)}/>
            <Txt x={xs[k]} y={y} size={fitFs(s, B.fs * 0.85, cw * 0.9)}>{s}</Txt>
            {gate && on && <Txt x={xs[k]} y={y - 64} size={B.fs * 0.75} color={pal(e, 0)}>quality gate ✓</Txt>}
          </g>
        );
      })}
      {loop > 0 && <g>
        <path d={`M${xs[n - 1]},${y + 50} C${xs[n - 1]},${B.y1} ${xs[1]},${B.y1} ${xs[1]},${y + 50}`} fill="none" stroke={C.hot} strokeWidth={4} strokeDasharray="10 8"
              pathLength={1} strokeDashoffset={0} opacity={loop}/>
        <Txt x={(xs[1] + xs[n - 1]) / 2} y={B.y1 - 10} size={B.fs * 0.85} color={C.hot} op={loop}>quality drops: retrain</Txt>
      </g>}
    </g>
  );
};

export const Drift = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), shift = glide(later(T, 40), 2.4) * 1.8;
  const base = B.y1 - B.fs * 1.6, X = (z) => B.x0 + 20 + ((z + 3) / 7.5) * (B.W - 40), Y = (v) => base - v * (B.H * 0.6);
  const curve = (m) => Array.from({length: 80}, (_, j) => { const z = -3 + (7.5 * j) / 79; return [X(z), Y(gauss(z, m, 0.9))]; });
  const alarm = shift > 1.2;
  return (
    <g>
      <line x1={B.x0} y1={base} x2={B.x1} y2={base} stroke={C.muted} strokeWidth={3}/>
      <path d={smoothPath(curve(0))} fill="none" stroke={C.cool} strokeWidth={5} strokeDasharray="10 8"/>
      <path d={`M${X(-3)},${base} ${curve(shift).map((p) => `L${p[0]},${p[1]}`).join(" ")} L${X(4.5)},${base} Z`} fill={alpha(alarm ? C.hot : pal(e, 0), 0.3)} stroke={alarm ? C.hot : pal(e, 0)} strokeWidth={4}/>
      <Txt x={X(0)} y={Y(1) - 20} size={B.fs * 0.85} color={C.cool}>training data</Txt>
      <Txt x={X(shift)} y={Y(1) - 50} size={B.fs * 0.85} color={alarm ? C.hot : pal(e, 0)}>live data</Txt>
      <Txt x={B.cx} y={B.y1 - 4} size={B.fs * 0.85} color={C.muted}>{e.feature}</Txt>
      {alarm && <g><Ico name="siren" x={B.x1 - 60} y={B.y0 + 40} size={56} color={C.hot}/><Txt x={B.x1 - 110} y={B.y0 + 40} size={B.fs} anchor="end" color={C.hot}>drift alert</Txt></g>}
    </g>
  );
};

export const FeatureStore = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), store = [B.cx, B.cy], c = cyc(T.t, 30, 50);
  return (
    <g>
      <Card x={B.x0} y={B.cy - 60} w={B.W * 0.18} h={120} icon="database" label="raw data" color={C.muted} p={pop(T.t)} fs={B.fs * 0.8}/>
      <rect x={store[0] - 160} y={store[1] - 140} width={320} height={280} rx={18} fill={alpha(C.panel, 0.95)} stroke={pal(e, 0)} strokeWidth={4} opacity={clamp(pop(T.t - 6) * 2)}/>
      <Txt x={store[0]} y={store[1] - 115} size={B.fs * 0.9} color={pal(e, 0)}>feature store</Txt>
      {e.features.map((f, k) => <Chip key={k} x={store[0]} y={store[1] - 60 + k * 50} text={f} color={pal(e, k + 1)} p={pop(T.t - 14 - k * 5)} fs={B.fs * 0.75} fill/>)}
      <Arrow a={[B.x0 + B.W * 0.18 + 6, B.cy]} b={[store[0] - 164, store[1]]} draw={glide(T.t - 10)} color={C.muted} label="compute once" fs={B.fs * 0.7}/>
      {[["training", "offline", -1], ["serving", "online", 1]].map(([nm, kind, s], k) => (
        <g key={k}>
          <Card x={B.x1 - B.W * 0.2} y={B.cy + s * 90 - 55} w={B.W * 0.2} h={110} icon={k ? "zap" : "graduation-cap"} label={nm} sub={kind} color={k ? C.hot : C.cool} p={pop(T.t - 20 - k * 6)} fs={B.fs * 0.8}/>
          <Arrow a={[store[0] + 164, store[1] + s * 40]} b={[B.x1 - B.W * 0.2 - 6, B.cy + s * 90]} draw={glide(T.t - 24 - k * 6)} color={k ? C.hot : C.cool}/>
          {c.on && <Packet pts={[[store[0] + 164, store[1] + s * 40], [B.x1 - B.W * 0.2 - 6, B.cy + s * 90]]} t={c.ph} color={k ? C.hot : C.cool}/>}
        </g>
      ))}
      {later(T, 100) > 0 && <Txt x={B.cx} y={B.y1 - 4} size={B.fs * 0.85} color={pal(e, 0)}>both use the very same values</Txt>}
    </g>
  );
};

export const AbTest = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), win = later(T, 120) > 0, share = win ? lerp(e.share, 1, glide(later(T, 120), 1.6)) : e.share;
  const src = [B.x0 + 60, B.cy], a = [B.x1 - B.W * 0.2, B.cy - B.H * 0.26], b = [B.x1 - B.W * 0.2, B.cy + B.H * 0.26];
  const c = cyc(T.t, 20, 14), toB = ((c.n * 7919) % 100) / 100 < share;
  return (
    <g>
      <Ico name="users" x={src[0]} y={src[1]} size={80} color={C.text} op={clamp(T.t / 10)}/>
      <path d={`M${src[0] + 50},${src[1]} C${B.cx},${src[1]} ${B.cx},${a[1]} ${a[0] - 110},${a[1]}`} fill="none" stroke={alpha(C.muted, 0.7)} strokeWidth={4 + 30 * (1 - share)}/>
      <path d={`M${src[0] + 50},${src[1]} C${B.cx},${src[1]} ${B.cx},${b[1]} ${b[0] - 110},${b[1]}`} fill="none" stroke={alpha(pal(e, 0), 0.8)} strokeWidth={4 + 30 * share}/>
      <Card x={a[0] - 110} y={a[1] - 55} w={220} h={110} icon="brain-circuit" label={e.a} color={C.muted} p={pop(T.t)} fs={B.fs * 0.85} dim={win && share > 0.95}/>
      <Card x={b[0] - 110} y={b[1] - 55} w={220} h={110} icon="brain-circuit" label={e.b} color={pal(e, 0)} p={pop(T.t - 6)} fs={B.fs * 0.85} lit={win ? 0.6 : 0}/>
      {c.on && <Packet pts={toB ? [[src[0] + 50, src[1]], [B.cx, src[1]], [b[0] - 110, b[1]]] : [[src[0] + 50, src[1]], [B.cx, src[1]], [a[0] - 110, a[1]]]} t={c.ph * 1.2} color={toB ? pal(e, 0) : C.muted}/>}
      <Txt x={B.cx} y={B.y0 + 4} size={B.fs * 0.9} color={C.muted}>{win ? "the new model wins: all traffic moves" : "a small share tries the new model"}</Txt>
      {e.show && <Txt x={b[0]} y={b[1] + 80} size={B.fs * 0.85} color={pal(e, 0)}>{`${Math.round(share * 100)}% of traffic`}</Txt>}
    </g>
  );
};

export const Anomaly = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), N = 120, play = clamp((T.t - 6) / Math.max(40, end - T.at - 20));
  const val = (j) => 0.45 + 0.08 * Math.sin(j / 6) + 0.04 * Math.sin(j * 1.7) + (j > 84 && j < 92 ? 0.38 : 0);
  const X = (j) => B.x0 + 20 + ((B.W * 0.66 - 20) * j) / (N - 1), Y = (v) => B.y1 - 30 - v * (B.H - 60), upto = Math.floor(play * (N - 1));
  const band = Array.from({length: N}, (_, j) => [X(j), Y(0.45 + 0.08 * Math.sin(j / 6) + 0.12), Y(0.45 + 0.08 * Math.sin(j / 6) - 0.12)]);
  const spike = upto > 86;
  return (
    <g>
      <path d={`M${band.map((b) => `${b[0]},${b[1]}`).join(" L")} L${band.slice().reverse().map((b) => `${b[0]},${b[2]}`).join(" L")} Z`} fill={alpha(C.cool, 0.15)} opacity={clamp(T.t / 14)}/>
      <path d={smoothPath(Array.from({length: upto + 1}, (_, j) => [X(j), Y(val(j))]))} fill="none" stroke={pal(e, 0)} strokeWidth={4}/>
      {spike && <circle cx={X(88)} cy={Y(val(88))} r={18} fill="none" stroke={C.hot} strokeWidth={5} style={{filter: glowF(C.hot, 0.8)}}/>}
      <Txt x={B.x0 + 20} y={B.y0 + 10} size={B.fs * 0.85} anchor="start" color={C.muted}>{`${e.metric}: learned normal band`}</Txt>
      {spike && <g opacity={clamp((upto - 86) / 6)}>
        <Arrow a={[X(88) + 20, Y(val(88))]} b={[B.x1 - B.W * 0.3, B.cy]} draw={1} color={C.hot}/>
        <Card x={B.x1 - B.W * 0.3} y={B.cy - 70} w={B.W * 0.28} h={140} icon="siren" label="incident opened" sub="on-call paged" color={C.hot} p={1} fs={B.fs * 0.85} lit={0.6}/>
      </g>}
    </g>
  );
};

export const Cicd = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.stages.length, xs = spread(n, B.x0, B.x1), y = B.cy, r = Math.min(70, (B.W / n) * 0.3);
  const per = Math.max(16, (end - T.at - 40) / (n + 0.5)), step = Math.max(0, (T.t - 16) / per), f = e.fail;
  return (
    <g>
      <line x1={xs[0]} y1={y} x2={xs[n - 1]} y2={y} stroke={alpha(C.muted, 0.4)} strokeWidth={6}/>
      {e.stages.map((s, k) => {
        const reached = step > k && (f < 0 || k <= f), done = step > k + 0.8 && (f < 0 || k < f), failed = k === f && step > k + 0.8, running = reached && !done && !failed;
        const col = failed ? C.hot : done ? pal(e, 0) : running ? C.violet : C.muted;
        return (
          <g key={k}>
            <circle cx={xs[k]} cy={y} r={r} fill={alpha(col, reached ? 0.35 : 0.08)} stroke={col} strokeWidth={5} style={{filter: running ? glowF(C.violet, 0.6) : undefined}}/>
            {running && <circle cx={xs[k]} cy={y} r={r + 10} fill="none" stroke={C.violet} strokeWidth={4} strokeDasharray="20 20" transform={`rotate(${T.t * 8} ${xs[k]} ${y})`}/>}
            <Txt x={xs[k]} y={y} size={r * 0.6} color={col}>{failed ? "✕" : done ? "✓" : ""}</Txt>
            <Txt x={xs[k]} y={y + r + B.fs * 0.9} size={fitFs(s, B.fs * 0.9, (B.W / n) * 0.9)} color={reached ? C.text : C.muted}>{s}</Txt>
          </g>
        );
      })}
      {f >= 0 && step > f + 0.8 && <Txt x={B.cx} y={B.y0 + 6} size={B.fs} color={C.hot}>pipeline stopped: nothing broken reaches users</Txt>}
    </g>
  );
};

export const EvalLoop = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.cases, xs = spread(n, B.x0 + B.W * 0.22, B.x1), rows = [B.cy - 60, B.cy + 60];
  const score = (v, k) => (v === 0 ? (k * 5) % 7 < 4 : (k * 3) % 7 < 6), per = 9;
  const shown = Math.max(0, Math.floor((T.t - 20) / per)), tot = [0, 0];
  for (let k = 0; k < Math.min(n, shown); k++) for (let v = 0; v < 2; v++) tot[v] += score(v, k) ? 1 : 0;
  const winner = shown >= n ? (tot[1] >= tot[0] ? 1 : 0) : -1;
  return (
    <g>
      {[e.a, e.b].map((nm, v) => <Chip key={v} x={B.x0 + B.W * 0.1} y={rows[v]} text={nm} color={v ? pal(e, 0) : C.muted} p={pop(T.t - v * 5)} fs={B.fs} fill lit={winner === v ? 0.7 : 0}/>)}
      {xs.map((x, k) => (
        <g key={k}>
          <Txt x={x} y={B.y0 + B.fs * 0.4} size={B.fs * 0.75} color={C.muted} op={clamp((T.t - k * 2) / 10)}>{`case ${k + 1}`}</Txt>
          {[0, 1].map((v) => k < shown && <g key={v}>
            <circle cx={x} cy={rows[v]} r={24} fill={alpha(score(v, k) ? C.cool : C.hot, 0.4)} stroke={score(v, k) ? C.cool : C.hot} strokeWidth={3}/>
            <Txt x={x} y={rows[v]} size={22} color={score(v, k) ? C.cool : C.hot}>{score(v, k) ? "✓" : "✕"}</Txt>
          </g>)}
        </g>
      ))}
      {winner >= 0 && <Txt x={B.cx} y={B.y1 - 6} size={B.fs} color={pal(e, 0)}>{`${winner ? e.b : e.a} scores higher: promoted`}</Txt>}
    </g>
  );
};

export const OPS = {k8scluster: K8sCluster, rollout: Rollout, hpa: Hpa, k8sservice: K8sService, selfheal: SelfHeal,
  containers: Containers, mlpipeline: MlPipeline, drift: Drift, featurestore: FeatureStore, abtest: AbTest, anomaly: Anomaly,
  cicd: Cicd, evalloop: EvalLoop};
