// Render many stills from one bundle and one browser (far faster than one `remotion still` per frame).
// Used by blogwriter/diagram.py to look at each diagram before it goes in the video.
//   node stills.mjs jobs.json      jobs: [{"props": {...} | "path.json", "frame": 120, "out": "a.jpg",
//                                          "composition": "Long", "scale": 0.5}]
import fs from "fs";
import path from "path";
import {bundle} from "@remotion/bundler";
import {openBrowser, renderStill, selectComposition} from "@remotion/renderer";

const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const serveUrl = await bundle({entryPoint: path.resolve("src/index.jsx"), rootDir: process.cwd(),
                               publicDir: path.resolve("public")});
const browser = await openBrowser("chrome");
let failed = 0;
for (const j of jobs) {
  try {
    const given = typeof j.props === "string" ? JSON.parse(fs.readFileSync(j.props, "utf8")) : j.props;
    const inputProps = j.audit ? {...given, audit: true} : given;      // the same props for the composition and the frame
    const composition = await selectComposition({serveUrl, id: j.composition || "Long", inputProps, puppeteerInstance: browser});
    const png = j.out.toLowerCase().endsWith(".png");        // a PNG keeps a transparent frame transparent
    // "audit": the frame's own layout is measured in the page (video/src/audit.jsx) and printed as `audit <out> <json>`
    let found = null;
    await renderStill({serveUrl, composition, output: j.out, frame: j.frame, imageFormat: png ? "png" : "jpeg",
                       inputProps,
                       ...(png ? {} : {jpegQuality: 90}), scale: j.scale || 0.5, puppeteerInstance: browser,
                       timeoutInMilliseconds: 120000, ...(j.audit ? {logLevel: "verbose"} : {}),
                       onBrowserLog: j.audit ? (l) => {
                         if (String(l.text).startsWith("LAYOUT_AUDIT ")) found = String(l.text).slice(13);
                       } : undefined});
    if (j.audit) {
      for (let k = 0; k < 20 && !found; k++) await new Promise((r) => setTimeout(r, 100));     // the log can trail the picture
      console.log(`audit ${j.out} ${found || "{}"}`);
    }
    console.log(`ok ${j.out}`);
  } catch (e) {
    failed++;
    console.log(`failed ${j.out}: ${String(e.message || e).slice(0, 200)}`);
  }
}
await browser.close({silent: true});
process.exit(failed === jobs.length && jobs.length ? 1 : 0);
