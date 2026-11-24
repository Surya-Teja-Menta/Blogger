"""Real language-model internals for the "llmreal" picture (video/src/viz/llmreal.jsx): a small open model (GPT-2, 124 million
parameters, MIT licence) reads a short sentence and we keep what it really computed: the attention weights of one head and
the probabilities of the next word. The video says it is a small model (the picture names the layer and head); a model of
billions of parameters does the same computation at a far greater scale.

It runs in the cloning environment's Python (VOICE_PYTHON: torch and transformers are already there for the voice), as a
separate process, and returns None when no Python with torch is available or anything fails, so the diagram designer just
draws the idea some other way. Results are kept per sentence."""
import json
import os
import subprocess
import sys
from typing import Dict, Optional

_CODE = r'''
import json, sys, warnings
warnings.filterwarnings("ignore")
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
text = sys.argv[1]
tok = AutoTokenizer.from_pretrained("gpt2")
model = AutoModelForCausalLM.from_pretrained("gpt2", attn_implementation="eager").eval()
ids = tok(text, return_tensors="pt")
n = ids["input_ids"].shape[1]
with torch.no_grad():
    out = model(**ids, output_attentions=True)
best = None
for layer, att in enumerate(out.attentions):                       # (1, heads, n, n)
    for head in range(att.shape[1]):
        a = att[0, head]
        if n > 3:                                                       # a head that looks further back than itself, the first word or the word just before
            score = float(sum(a[r, 1:r - 1].sum() for r in range(3, n)) / max(1, n - 3))
            if best is None or score > best[0]:
                best = (score, layer, head, a.tolist())
if best is None:
    best = (0.0, 0, 0, out.attentions[0][0, 0].tolist())
probs = torch.softmax(out.logits[0, -1], dim=-1)
top = torch.topk(probs, 5)
res = {"tokens": [tok.decode([i]) for i in ids["input_ids"][0]], "layer": best[1], "head": best[2],
       "attn": [[round(v, 3) for v in row] for row in best[3]],
       "next": [[tok.decode([int(i)]), round(float(p), 4)] for p, i in zip(top.values, top.indices)]}
print("PROBE:" + json.dumps(res))
'''
_cache: Dict[str, Optional[dict]] = {}


def probe(text: str, python: str = "", timeout: int = 600) -> Optional[dict]:
    """{"tokens", "layer", "head", "attn" (n x n), "next" ([[word, probability] x 5])} for a sentence of 3 to 12 tokens, or None."""
    text = " ".join(str(text).split())[:120]
    if text in _cache:
        return _cache[text]
    python = python or os.environ.get("VOICE_PYTHON", "") or sys.executable
    result = None
    try:
        r = subprocess.run([python, "-c", _CODE, text], capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        line = next((ln for ln in r.stdout.splitlines() if ln.startswith("PROBE:")), "")
        result = json.loads(line[6:]) if line else None
        if result and not 3 <= len(result["tokens"]) <= 14:
            result = None
    except (OSError, ValueError, subprocess.SubprocessError):
        result = None
    _cache[text] = result
    return result
