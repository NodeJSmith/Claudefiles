import json
import sys
import glob
import os
from collections import defaultdict

# $/MTok: input, output, cache_write(5m), cache_read
PRICE = {
    "opus": (5, 25, 6.25, 0.5),
    "sonnet": (3, 15, 3.75, 0.3),
    "haiku": (1, 5, 1.25, 0.1),
}


def tier(m):
    for k in PRICE:
        if k in (m or ""):
            return k
    return None


def scan(path, agg, seen):
    first = last = None
    users = 0
    for line in open(path):
        try:
            r = json.loads(line)
        except Exception:
            continue
        ts = r.get("timestamp")
        if ts:
            first = first or ts
            last = ts
        if (
            r.get("type") == "user"
            and not r.get("isMeta")
            and isinstance(r.get("message", {}).get("content"), str)
        ):
            users += 1
        m = r.get("message") or {}
        u = m.get("usage")
        mid = m.get("id")
        if r.get("type") != "assistant" or not u or not mid or mid in seen:
            continue
        seen.add(mid)
        t = tier(m.get("model"))
        if not t:
            continue
        a = agg[t]
        a[0] += u.get("input_tokens", 0)
        a[1] += u.get("output_tokens", 0)
        a[2] += u.get("cache_creation_input_tokens", 0)
        a[3] += u.get("cache_read_input_tokens", 0)
    return first, last, users


for main in sys.argv[1:]:
    agg = defaultdict(lambda: [0, 0, 0, 0])
    seen = set()
    first, last, users = scan(main, agg, seen)
    sub = defaultdict(lambda: [0, 0, 0, 0])
    subs = glob.glob(os.path.join(main[:-6], "subagents", "*.jsonl"))
    for s in subs:
        scan(s, sub, seen)
    print(
        f"== {os.path.basename(main)}  {first} -> {last}  user_msgs={users}  subagents={len(subs)}"
    )
    tot = 0
    for label, d in (("main", agg), ("subagents", sub)):
        for t, a in d.items():
            p = PRICE[t]
            cost = sum(x * y for x, y in zip(a, p)) / 1e6
            tot += cost
            print(
                f"  {label:9} {t:6} in={a[0]:>9,} out={a[1]:>9,} cw={a[2]:>11,} cr={a[3]:>12,}  ${cost:8.2f}"
            )
    print(f"  TOTAL ${tot:.2f}")
