// Data-structure techniques (blogwriter/vizlib.py, family "data"): hash tables, stacks and queues, linked lists,
// sorting and binary search, each operated step by step.
import {Arrow, C, Chip, React, Txt, alpha, box, clamp, fitFs, fmt, glide, glowF, lerp, pal, pop, row, spread, timing, tw} from "./kit";

const hashOf = (s) => { let h = 2166136261; for (const ch of String(s)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967296; };

// --------------------------------------------------------------------------------------------------------------
export const HashTable = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), nb = e.buckets, keys = e.keys;
  const bx = B.x0 + B.W * 0.42, by = row(nb, B.y0 + 30, B.y1 - 30), bh = Math.min(70, (B.H - 20) / nb - 10);
  const kx = B.x0 + B.W * 0.08, ky = row(keys.length, B.y0 + 30, B.y1 - 30), slots = Array(nb).fill(0);
  return (
    <g>
      {by.map((y, k) => (
        <g key={k} opacity={clamp(T.t / 10)}>
          <rect x={bx - 60} y={y - bh / 2} width={120} height={bh} rx={10} fill={alpha(C.panel, 0.95)} stroke={C.muted} strokeWidth={3}/>
          <Txt x={bx} y={y} size={Math.min(B.fs * 0.85, bh * 0.5)} color={C.muted}>{`bucket ${k}`}</Txt>
        </g>
      ))}
      <Txt x={(kx + bx) / 2} y={B.y0 + 4} size={B.fs * 0.9} color={C.muted} op={clamp(T.t / 10)}>hash(key)</Txt>
      {keys.map((k, j) => {
        const b = Math.floor(hashOf(k) * nb), slot = slots[b]++, d = glide(T.t - 16 - j * 12, 1.1);
        const half = (tw(k, B.fs * 0.85) + B.fs) / 2, tx = bx + 90 + half + slot * (half * 2 + B.fs * 1.6), x = lerp(kx, tx, d), y = lerp(ky[j], by[b], d);
        return (
          <g key={j}>
            {slot > 0 && d >= 1 && <line x1={tx - half - B.fs * 1.6} y1={by[b]} x2={tx - half} y2={by[b]} stroke={C.hot} strokeWidth={3}/>}
            {slot === 0 && d >= 1 && <line x1={bx + 60} y1={by[b]} x2={tx - half} y2={by[b]} stroke={C.muted} strokeWidth={3}/>}
            <Chip x={x} y={y} text={k} color={slot > 0 ? C.hot : pal(e, b)} p={pop(T.t - j * 3)} fs={B.fs * 0.85} fill/>
          </g>
        );
      })}
      {T.k > 0 && <Txt x={B.x1 - 10} y={B.y1 - B.fs * 0.3} size={B.fs * 0.85} anchor="end" color={C.hot}>same bucket: a collision, chained</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const StackQueue = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.items.length, stack = e.kind === "stack";
  const per = 22, pushed = Math.min(n, Math.max(0, Math.floor((T.t - 10) / per) + 1)), popAt = T.k > 0 ? T.k : -1, popped = popAt > 0 ? 1 : 0;
  const ih = Math.min(80, (B.H - 60) / n), iw = Math.min(320, B.W * 0.3);
  const cx = B.cx, baseY = B.y1 - 20;
  const live = e.items.slice(0, pushed).filter((_, k) => !(popped && (stack ? k === pushed - 1 : k === 0)));
  const leaving = popped ? (stack ? e.items[pushed - 1] : e.items[0]) : null;
  return (
    <g>
      {stack ? <path d={`M${cx - iw / 2 - 14},${B.y0 + 20} L${cx - iw / 2 - 14},${baseY + 10} L${cx + iw / 2 + 14},${baseY + 10} L${cx + iw / 2 + 14},${B.y0 + 20}`}
                     fill="none" stroke={C.muted} strokeWidth={5}/>
        : <g><line x1={B.x0 + 40} y1={B.cy - ih * 0.7} x2={B.x1 - 40} y2={B.cy - ih * 0.7} stroke={C.muted} strokeWidth={4}/>
            <line x1={B.x0 + 40} y1={B.cy + ih * 0.7} x2={B.x1 - 40} y2={B.cy + ih * 0.7} stroke={C.muted} strokeWidth={4}/></g>}
      {live.map((it, j) => {
        const idx = e.items.indexOf(it), p = pop(T.t - 10 - idx * per);
        const x = stack ? cx : B.x1 - 120 - j * (iw * 0.62), y = stack ? baseY - (j + 0.5) * ih : B.cy;
        return (
          <g key={it} opacity={clamp(p * 2)} transform={`translate(0,${(1 - p) * (stack ? -60 : 0)})`}>
            <rect x={x - (stack ? iw : iw * 0.56) / 2} y={y - ih * 0.42} width={stack ? iw : iw * 0.56} height={ih * 0.84} rx={10} fill={alpha(pal(e, idx), 0.45)} stroke={pal(e, idx)} strokeWidth={3}/>
            <Txt x={x} y={y} size={fitFs(it, B.fs, (stack ? iw : iw * 0.56) * 0.85)}>{it}</Txt>
          </g>
        );
      })}
      {leaving && <g opacity={clamp(1 - popAt / 40)} transform={`translate(${stack ? 0 : -popAt * 6},${stack ? -popAt * 4 : 0})`}>
        <Chip x={stack ? cx : B.x0 + 120} y={stack ? B.y0 + 40 : B.cy} text={leaving} color={C.hot} p={1} fs={B.fs} fill/>
      </g>}
      <Txt x={stack ? cx + iw / 2 + 40 : B.x0 + 40} y={stack ? B.y0 + 40 : B.cy - ih * 1.4} size={B.fs * 0.9} anchor="start" color={C.hot}>
        {stack ? "last in, first out" : "first in, first out"}</Txt>
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const LinkedList = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), items = e.items, n = items.length;
  const ins = e.insert ? glide(T.k > 0 ? T.k : T.t - 60, 1.4) : 0, at = Math.max(1, Math.ceil(n / 2));
  const total = n + (e.insert ? 1 : 0), xs = spread(total, B.x0, B.x1), y = B.cy, w = Math.min(160, (B.W / total) * 0.6), h = 80;
  const pos = (k) => (k < at ? xs[k] : lerp(spread(n, B.x0, B.x1)[k], xs[k + 1], ins));
  return (
    <g>
      {items.map((it, k) => (
        <g key={k} opacity={clamp(pop(T.t - k * 6) * 2)}>
          <rect x={pos(k) - w / 2} y={y - h / 2} width={w} height={h} rx={12} fill={alpha(pal(e, 0), 0.3)} stroke={pal(e, 0)} strokeWidth={3}/>
          <Txt x={pos(k) - w * 0.12} y={y} size={fitFs(it, B.fs, w * 0.6)}>{it}</Txt>
          <line x1={pos(k) + w * 0.22} y1={y - h / 2} x2={pos(k) + w * 0.22} y2={y + h / 2} stroke={pal(e, 0)} strokeWidth={2}/>
          {k < n - 1 && !(e.insert && k === at - 1 && ins > 0.3) && <Arrow a={[pos(k) + w * 0.35, y]} b={[pos(k + 1) - w / 2 - 4, y]} draw={glide(T.t - 10 - k * 6)} color={C.text} width={4}/>}
        </g>
      ))}
      {e.insert && ins > 0 && <g>
        <rect x={xs[at] - w / 2} y={y + h * 1.2 - (h * 1.2) * clamp((ins - 0.5) * 2) - h / 2} width={w} height={h} rx={12} fill={alpha(C.hot, 0.35)} stroke={C.hot} strokeWidth={4}/>
        <Txt x={xs[at] - w * 0.12} y={y + h * 1.2 - (h * 1.2) * clamp((ins - 0.5) * 2)} size={fitFs(e.insert, B.fs, w * 0.6)}>{e.insert}</Txt>
        {ins > 0.3 && <Arrow a={[pos(at - 1) + w * 0.35, y]} b={[xs[at] - w / 2 - 4, y + h * 1.2 - (h * 1.2) * clamp((ins - 0.5) * 2)]} draw={1} color={C.hot} width={4}/>}
        {ins > 0.6 && <Arrow a={[xs[at] + w * 0.35, y + h * 1.2 - (h * 1.2) * clamp((ins - 0.5) * 2)]} b={[pos(at) - w / 2 - 4, y]} draw={clamp((ins - 0.6) * 3)} color={C.hot} width={4}/>}
      </g>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const Sorting = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), vals = e.values, n = vals.length;
  const swaps = React.useMemo(() => { const a = vals.map((v, k) => k), out = [a.slice()]; for (let i = 0; i < n; i++) for (let j = 0; j < n - 1 - i; j++) if (vals[a[j]] > vals[a[j + 1]]) { [a[j], a[j + 1]] = [a[j + 1], a[j]]; out.push(a.slice()); } return out; }, [vals, n]);
  const steps = swaps.length - 1, s = clamp((T.t - 20) / Math.max(30, end - T.at - 40)) * steps, k = Math.min(steps - 1, Math.floor(s)), u = s - k;
  const mx = Math.max(...vals), base = B.y1 - 20, bw = (B.W / n) * 0.7, xs = spread(n, B.x0, B.x1);
  const slot = (orderIdx, item) => swaps[orderIdx].indexOf(item);
  const done = s >= steps;
  return (
    <g>
      {vals.map((v, item) => {
        const x = steps > 0 ? lerp(xs[slot(Math.max(0, k), item)], xs[slot(Math.min(steps, k + 1), item)], glide(u * 20, 0.6)) : xs[item];
        const moving = steps > 0 && slot(k, item) !== slot(k + 1, item);
        const h = ((base - B.y0 - 40) * v) / mx;
        return (
          <g key={item}>
            <rect x={x - bw / 2} y={base - h} width={bw} height={h} rx={8} fill={done ? pal(e, 0) : moving ? C.hot : alpha(pal(e, 0), 0.6)} style={{filter: moving ? glowF(C.hot, 0.5) : undefined}}/>
            {e.show && <Txt x={x} y={base - h - B.fs * 0.6} size={Math.min(B.fs, bw * 0.6)}>{fmt(v)}</Txt>}
          </g>
        );
      })}
      {done && <Txt x={B.cx} y={B.y0 + B.fs * 0.4} size={B.fs} color={pal(e, 0)}>sorted</Txt>}
    </g>
  );
};

// --------------------------------------------------------------------------------------------------------------
export const BinarySearch = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), vals = e.values, n = vals.length;
  const ranges = React.useMemo(() => { let lo = 0, hi = n - 1; const out = []; while (lo <= hi) { const mid = Math.floor((lo + hi) / 2); out.push([lo, hi, mid]); if (vals[mid] === e.target) break; if (vals[mid] < e.target) lo = mid + 1; else hi = mid - 1; } return out; }, [vals, n, e.target]);
  const step = Math.min(ranges.length - 1, Math.max(0, Math.floor((T.t - 20) / 30))), [lo, hi, mid] = ranges[step];
  const cw = Math.min(110, (B.W - 20) / n), x0 = B.cx - (cw * n) / 2, y = B.cy, found = vals[mid] === e.target && T.t > 20 + step * 30 + 15;
  return (
    <g>
      {vals.map((v, k) => {
        const inR = k >= lo && k <= hi, isMid = k === mid;
        return (
          <g key={k} opacity={inR ? 1 : 0.25}>
            <rect x={x0 + k * cw + 3} y={y - cw * 0.45} width={cw - 6} height={cw * 0.9} rx={10} fill={isMid ? alpha(found ? pal(e, 0) : C.hot, 0.5) : alpha(C.panel, 0.95)}
                  stroke={isMid ? (found ? pal(e, 0) : C.hot) : C.muted} strokeWidth={isMid ? 5 : 2}/>
            <Txt x={x0 + (k + 0.5) * cw} y={y} size={Math.min(B.fs, cw * 0.4)}>{fmt(v)}</Txt>
          </g>
        );
      })}
      <path d={`M${x0 + lo * cw},${y + cw * 0.7} L${x0 + lo * cw},${y + cw * 0.85} L${x0 + (hi + 1) * cw},${y + cw * 0.85} L${x0 + (hi + 1) * cw},${y + cw * 0.7}`} fill="none" stroke={C.cool} strokeWidth={4}/>
      <Txt x={B.cx} y={y - cw * 0.9} size={B.fs} color={found ? pal(e, 0) : C.hot}>{found ? `found ${fmt(e.target)}` : `look for ${fmt(e.target)}: check the middle`}</Txt>
      <Txt x={B.cx} y={y + cw * 1.3} size={B.fs * 0.85} color={C.muted}>{`half the range left after step ${step + 1}`}</Txt>
    </g>
  );
};

export const DATA = {hashtable: HashTable, stackqueue: StackQueue, linkedlist: LinkedList, sorting: Sorting, binarysearch: BinarySearch};
