// A layout audit for the preview renderer (video/stills.mjs): after a frame has drawn, measure every visible piece of
// text and every visible box as the browser really laid it out, and report the ones that run into each other. The
// pipeline (blogwriter/layout.py) renders each shot at a few moments with `audit: true` and repairs what is reported,
// so a title on top of a question, two boxes sharing a corner or a label across another label never reaches a viewer.
// Nothing here draws anything; it only logs one line "LAYOUT_AUDIT {json}" that the renderer picks up.
import React, {useEffect, useState} from "react";
import {continueRender, delayRender, useCurrentFrame} from "remotion";

const SEE = 0.35;               // pieces fainter than this (ghost words, fading parts) are not part of the picture yet
const TEXT_MIN = 0.33;          // share of the smaller text box that has to be covered (the boxes are trimmed to the ink, see ink())
const BOX_MIN = 0.12;           // the same for two boxes that are neither nested nor apart
const EDGE = [0.18, 0.82];      // a text with this share of its area inside a box crosses the box's edge

const seen = (el) => {
  let o = 1;
  for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
    const cs = getComputedStyle(e);
    if (cs.display === "none" || cs.visibility === "hidden") return 0;
    o *= parseFloat(cs.opacity || "1");
    if (e.dataset && e.dataset.audit === "skip") return 0;
  }
  return o;
};
// a text's line box is taller than its letters (big numbers and headlines most of all): measure the ink, not the padding
const ink = (r) => {
  const t = r.height * 0.06;
  return {left: r.left, right: r.right, top: r.top + t, bottom: r.bottom - t, width: r.width, height: r.height - 2 * t};
};
const area = (r) => Math.max(0, r.width) * Math.max(0, r.height);
const cut = (a, b) => {
  const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
  const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
  return w > 0 && h > 0 ? {w, h, a: w * h} : null;
};
const alphaOf = (c) => {
  const m = /rgba?\(([^)]+)\)/.exec(c || "");
  if (!m) return 0;
  const p = m[1].split(",").map((x) => parseFloat(x));
  return p.length > 3 ? p[3] : 1;
};
const word = (s) => String(s || "").replace(/\s+/g, " ").trim().slice(0, 28);

export const measure = (root = document.body) => {
  const texts = [], boxes = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const katex = new Set();
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const p = n.parentElement;
    if (!p || !n.nodeValue.trim() || /^(SCRIPT|STYLE|NOSCRIPT)$/.test(p.tagName)) continue;
    const k = p.closest(".katex") || p.closest("[data-caption]");
    if (k) {                // a formula or a caption line is one piece: its own glyphs (and the lit word) overlap by design
      if (!katex.has(k)) {
        katex.add(k);
        const o = seen(k), r = k.getBoundingClientRect();
        if (o >= SEE && r.width > 4 && r.height > 4) texts.push({el: k, r, t: k.matches(".katex") ? "formula" : "caption: " + word(k.textContent)});
      }
      continue;
    }
    const o = seen(p);
    if (o < SEE || alphaOf(getComputedStyle(p).color) < 0.1) continue;      // outlined ghost words are not drawn text
    const range = document.createRange();
    range.selectNodeContents(n);
    const r = range.getBoundingClientRect();
    if (r.width > 4 && r.height > 4) texts.push({el: p, r: ink(r), t: word(n.nodeValue)});
  }
  for (const el of root.querySelectorAll("*")) {
    if (el.closest(".katex") || el.closest("[data-caption]")) continue;
    const tag = el.tagName.toLowerCase();
    let ok = false;
    if (tag === "rect") {
      const cs = getComputedStyle(el);
      ok = (cs.fill !== "none" && alphaOf(cs.fill) > 0.05) || (cs.stroke !== "none" && parseFloat(cs.strokeWidth) > 1.5);
    } else if (el instanceof HTMLElement) {
      const cs = getComputedStyle(el);
      const border = parseFloat(cs.borderTopWidth) >= 1.5 && alphaOf(cs.borderTopColor) > 0.2 && cs.borderTopStyle !== "none";
      const round = parseFloat(cs.borderTopLeftRadius) >= 0.4 * Math.min(el.offsetWidth, el.offsetHeight);
      // a box is a container of something: bare bars, specks and glows (decoration) and round rings or pills are not
      ok = (border || alphaOf(cs.backgroundColor) >= 0.25) && !round && (el.textContent.trim() !== "" || !!el.querySelector("svg"));
    }
    if (!ok) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 48 || r.height < 26 || r.width > 1500 || r.height > 800) continue;
    if (seen(el) < SEE + 0.15) continue;
    const label = word(el.textContent) || tag;
    boxes.push({el, r, t: label});
  }
  const out = [];
  const box = (r) => [r.left, r.top, r.width, r.height].map(Math.round);
  const add = (kind, a, b, extra = {}) => out.push({kind, a: a.t, b: b.t, at: [box(a.r), box(b.r)], ...extra});
  for (let i = 0; i < texts.length; i++) {
    for (let j = i + 1; j < texts.length; j++) {
      const a = texts[i], b = texts[j];
      if (a.el === b.el && a.t === b.t) continue;
      const c = cut(a.r, b.r);
      if (!c || c.w < 8 || c.h < 8) continue;
      if (c.a / Math.min(area(a.r), area(b.r)) >= TEXT_MIN) add("text-on-text", a, b, {share: +(c.a / Math.min(area(a.r), area(b.r))).toFixed(2)});
    }
  }
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
      const c = cut(a.r, b.r);
      if (!c || c.w < 8 || c.h < 8) continue;
      const share = c.a / Math.min(area(a.r), area(b.r));
      if (share >= BOX_MIN && share < 0.88) add("box-on-box", a, b, {share: +share.toFixed(2)});
    }
  }
  for (const t of texts) {
    for (const b of boxes) {
      const c = cut(t.r, b.r);
      if (!c || c.w < 6 || c.h < 6) continue;
      const share = c.a / area(t.r);
      if (share >= EDGE[0] && share <= EDGE[1] && !b.el.contains(t.el)) add("text-over-box-edge", t, b, {share: +share.toFixed(2)});
    }
  }
  const seenPair = new Set();
  return out.filter((o) => {
    const key = `${o.kind}|${o.a}|${o.b}`;
    if (seenPair.has(key)) return false;
    seenPair.add(key);
    return true;
  }).slice(0, 12);
};

export const LayoutAudit = () => {
  const frame = useCurrentFrame();
  const [handle] = useState(() => delayRender("layout audit"));
  useEffect(() => {
    const t = setTimeout(() => {
      try {
        console.log("LAYOUT_AUDIT " + JSON.stringify({frame, found: measure()}));
      } catch (e) {
        console.log("LAYOUT_AUDIT " + JSON.stringify({frame, error: String(e && e.message || e).slice(0, 120)}));
      } finally {
        continueRender(handle);
      }
    }, 250);
    return () => clearTimeout(t);
  }, []);
  return null;
};
