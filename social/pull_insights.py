"""Pull per-reel metrics and rank struggles/traditions. Writes insights.json + insights.md."""
import datetime as dt
import json
import os
import sys

import lib_graph as g

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "reels_manifest.json")


def main():
    g.require_env()
    manifest = {e.get("posted_media_id"): e for e in json.load(open(MANIFEST, encoding="utf-8")) if e.get("posted_media_id")}
    rows = []
    for m in g.list_media(50):
        if m.get("media_type") not in ("VIDEO", "REELS"):
            continue
        ins = g.media_insights(m["id"])
        e = manifest.get(m["id"], {})
        plays = ins.get("plays") or 0
        saves, shares = ins.get("saved") or 0, ins.get("shares") or 0
        score = (saves + shares) / plays * 1000 if plays else 0
        rows.append({"id": m["id"], "reel": e.get("id", "(manual)"), "theme": e.get("theme", ""), "traditions": e.get("traditions", ""),
                     "posted": m.get("timestamp", "")[:10], "plays": plays, "reach": ins.get("reach"), "saves": saves,
                     "shares": shares, "likes": ins.get("likes"), "comments": ins.get("comments"),
                     "avg_watch_ms": ins.get("ig_reels_avg_watch_time"), "saves_shares_per_1k": round(score, 1), "permalink": m.get("permalink")})
    rows.sort(key=lambda r: r["saves_shares_per_1k"], reverse=True)
    json.dump({"pulled": dt.datetime.utcnow().isoformat(timespec="minutes") + "Z", "rows": rows}, open(os.path.join(HERE, "insights.json"), "w"), indent=1)
    lines = [f"# One Price — reel leaderboard ({dt.datetime.utcnow():%Y-%m-%d})", "", "| rank | reel | theme | traditions | plays | saves | shares | saves+shares/1k | avg watch |", "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        w = f"{(r['avg_watch_ms'] or 0)/1000:.1f}s" if r["avg_watch_ms"] else ""
        lines.append(f"| {i} | {r['reel']} | {r['theme']} | {r['traditions']} | {r['plays']} | {r['saves']} | {r['shares']} | {r['saves_shares_per_1k']} | {w} |")
    open(os.path.join(HERE, "insights.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
