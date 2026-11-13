// The Upload buttons in the video email point here. One click starts the "Upload to YouTube" job on GitHub, which
// holds the YouTube sign-in (GitHub Secrets) and does the upload; nothing YouTube-related lives in this Worker.
//
//   GET  /upload?what=video|short|both&run=<run folder>&key=<per-video key>
//        checks the link, then posts itself (JavaScript) so the click needs nothing more. A mail scanner that only
//        fetches the link never runs that script, so it cannot start an upload.
//   POST /upload   (same fields) checks the link again and starts the GitHub job.
//
// The key: each video's delivery writes a random key to videos/<run>/upload_key.txt in the private bucket, and only
// the email carries it. When storage removes the video (it keeps the 4 newest), the key goes too and the button
// says so. Markers in uploads/<run>/ stop a second click from uploading twice: <item>.json is written by the upload
// job when an item is on YouTube, requested-<item>.json here when a job was started (the job removes it at the end).
//
// Bindings (wrangler.toml): BUCKET (R2), REPO, WORKFLOW, BRANCH. Secret: GH_TOKEN, a fine-grained GitHub token for
// this one repository with "Actions: read and write" and nothing else.

const RUN = /^\d{8}_\d{6}_[A-Za-z0-9_\-]{1,140}$/;
const WHAT = { video: ["video"], short: ["short"], both: ["video", "short"] };
const BUSY_MS = 2 * 60 * 60 * 1000;      // a started job counts as running for 2 hours (an upload takes minutes)

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/upload") return page(404, "Nothing here", "<p>This address only takes the Upload buttons of the Adyora video email.</p>");
    if (request.method !== "GET" && request.method !== "POST") return page(405, "Not allowed", "");
    const form = request.method === "POST" ? await request.formData() : url.searchParams;
    const what = String(form.get("what") || ""), run = String(form.get("run") || ""), key = String(form.get("key") || "");
    if (!WHAT[what] || !RUN.test(run) || !/^[A-Za-z0-9_\-]{20,100}$/.test(key))
      return page(400, "This link is broken", "<p>Use the Upload button in the video email.</p>");

    const stored = await env.BUCKET.get(`videos/${run}/upload_key.txt`);
    if (!stored)
      return page(410, "This video is no longer stored", "<p>Storage keeps the 4 newest videos, so this one can no longer be uploaded from here.</p>");
    if (!(await same(key, (await stored.text()).trim())))
      return page(403, "This link is not valid", "<p>Use the Upload button in the video email.</p>");

    const items = WHAT[what], done = {}, busy = [];
    for (const item of items) {
      const mark = await readJson(env, `uploads/${run}/${item}.json`);
      if (mark && mark.url) { done[item] = mark; continue; }
      const req = await readJson(env, `uploads/${run}/requested-${item}.json`);
      if (req && Date.now() - Number(req.at || 0) < BUSY_MS) busy.push(item);
    }
    const todo = items.filter((i) => !done[i] && !busy.includes(i));
    const name = (i) => (i === "video" ? "The video" : "The Short");
    const doneHtml = Object.entries(done).map(([i, m]) =>
      `<p>${name(i)} is already on YouTube: <a href="${esc(m.url)}">${esc(m.title || m.url)}</a>.</p>`).join("");
    const busyHtml = busy.map((i) => `<p>${name(i)} is already being uploaded. The email with its YouTube link is on its way.</p>`).join("");

    if (!todo.length) return page(200, "Nothing new to upload", doneHtml + busyHtml);

    if (request.method === "GET") {        // the click itself: post straight on, no second button for a person
      const fields = { what, run, key };
      const hidden = Object.entries(fields).map(([k, v]) => `<input type="hidden" name="${k}" value="${esc(v)}">`).join("");
      return page(200, "Starting the upload…",
        `<form id="go" method="post" action="/upload">${hidden}<noscript><button type="submit">Upload now</button></noscript></form>` +
        `<script>document.getElementById("go").submit()</script>`);
    }

    const send = todo.length === 2 ? "both" : todo[0];
    const r = await fetch(`https://api.github.com/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`, {
      method: "POST",
      headers: { Authorization: `Bearer ${env.GH_TOKEN}`, Accept: "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "adyora-upload-button", "Content-Type": "application/json" },
      body: JSON.stringify({ ref: env.BRANCH || "main", inputs: { what: send, run } }),
    });
    if (r.status !== 204 && r.status !== 200)
      return page(502, "GitHub did not start the upload",
        `<p>GitHub answered ${r.status}. Nothing was uploaded; try the button again in a minute.</p>` +
        (r.status === 401 || r.status === 403 || r.status === 404 ? "<p>The GitHub token of this button may have expired: make a new one and update GH_TOKEN.</p>" : ""));
    for (const item of todo)
      await env.BUCKET.put(`uploads/${run}/requested-${item}.json`, JSON.stringify({ at: Date.now() }),
        { httpMetadata: { contentType: "application/json" } });
    const what2 = send === "both" ? "The video and the Short are" : `${name(send)} is`;
    return page(200, "Upload started",
      `<p>${what2} being uploaded by GitHub now. You will get an email with the YouTube link in a few minutes.</p>` +
      doneHtml + busyHtml +
      `<p class="m"><a href="https://github.com/${esc(env.REPO)}/actions/workflows/${esc(env.WORKFLOW)}">Watch the job on GitHub</a></p>`);
  },
};

async function readJson(env, key) {
  const o = await env.BUCKET.get(key);
  if (!o) return null;
  try { return JSON.parse(await o.text()); } catch { return null; }
}

async function same(a, b) {                 // compares in constant time
  const enc = new TextEncoder();
  const [x, y] = await Promise.all([a, b].map((s) => crypto.subtle.digest("SHA-256", enc.encode(s))));
  return crypto.subtle.timingSafeEqual(x, y);
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function page(status, title, body) {
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>${esc(title)} · Adyora</title><style>
body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#f6f8fa;color:#1f2328;margin:0;padding:48px 16px}
main{max-width:520px;margin:0 auto;background:#fff;border:1px solid #d1d9e0;border-radius:8px;padding:24px 28px}
.k{color:#59636e;font-size:12px;letter-spacing:.06em;text-transform:uppercase}h1{font-size:22px;margin:4px 0 12px}
a{color:#c4302b;font-weight:600}.m{color:#59636e;font-size:13px}button{background:#c4302b;color:#fff;border:0;border-radius:6px;padding:10px 18px;font-weight:600;font-size:15px}
</style></head><body><main><div class="k">Adyora · upload</div><h1>${esc(title)}</h1>${body}</main></body></html>`;
  return new Response(html, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex" } });
}
