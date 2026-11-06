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
    const inputProps = typeof j.props === "string" ? JSON.parse(fs.readFileSync(j.props, "utf8")) : j.props;
    const composition = await selectComposition({serveUrl, id: j.composition || "Long", inputProps, puppeteerInstance: browser});
    await renderStill({serveUrl, composition, output: j.out, frame: j.frame, inputProps, imageFormat: "jpeg",
                       jpegQuality: 90, scale: j.scale || 0.5, puppeteerInstance: browser, timeoutInMilliseconds: 120000});
    console.log(`ok ${j.out}`);
  } catch (e) {
    failed++;
    console.log(`failed ${j.out}: ${String(e.message || e).slice(0, 200)}`);
  }
}
await browser.close({silent: true});
process.exit(failed === jobs.length && jobs.length ? 1 : 0);
