#!/usr/bin/env bash
# Commit the story history and the video queue back to the repo. Many jobs run in parallel and all touch the same
# files, so instead of merging, each try starts from the latest main and re-applies this job's own change:
# the new lines of output/history.jsonl, then $APPLY (a command, e.g. marking a queued topic done).
# env: MSG (commit message), APPLY (optional command), BRANCH (default main)
set -uo pipefail
BRANCH="${BRANCH:-main}"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
new_history="$(git diff -U0 -- output/history.jsonl | grep '^+[^+]' | cut -c2- || true)"

for try in 1 2 3 4 5 6; do
  git fetch -q origin "$BRANCH" && git reset -q --hard "origin/$BRANCH" || { sleep 5; continue; }
  [ -z "$new_history" ] || printf '%s\n' "$new_history" >> output/history.jsonl
  if [ -n "${APPLY:-}" ]; then eval "$APPLY" || exit 1; fi
  git add output/history.jsonl queue 2>/dev/null
  if git diff --cached --quiet; then echo "nothing to save"; exit 0; fi
  git commit -qm "$MSG"
  if git push -q origin "HEAD:$BRANCH"; then echo "saved: $MSG"; exit 0; fi
  echo "push raced another job (try $try); retrying"
  sleep $((RANDOM % 15 + 5))
done
echo "could not save after 6 tries"
exit 1
