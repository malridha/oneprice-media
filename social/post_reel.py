"""Publish the next due reel from reels_manifest.json. One reel per run.

Picks the first entry where posted_media_id is null, scheduled <= today (Asia/Dubai), and video_url is set.
Posts it, drops `hashtags` as the first comment, writes posted_media_id back.
DRY_RUN=1 prints what it would do and changes nothing.
"""
import datetime as dt
import json
import os
import sys
import zoneinfo

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "reels_manifest.json")
DRY = os.environ.get("DRY_RUN", "0") == "1"
TZ = zoneinfo.ZoneInfo("Asia/Dubai")


def load():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def save(entries):
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)
        f.write("\n")


def next_due(entries, today):
    for e in entries:
        if e.get("posted_media_id"):
            continue
        if not e.get("video_url"):
            continue
        if e.get("scheduled") and e["scheduled"] > today:
            continue
        return e
    return None


def main():
    entries = load()
    today = dt.datetime.now(TZ).date().isoformat()
    e = next_due(entries, today)
    if not e:
        print(f"nothing due on {today}; {sum(1 for x in entries if not x.get('posted_media_id'))} pending")
        return
    print(f"Next due: {e['id']} (scheduled {e.get('scheduled')}, today {today})")
    print("--- caption ---\n" + e["caption"] + "\n--- hashtags ---\n" + e.get("hashtags", "") + "\n---")
    print("video:", e["video_url"])
    if DRY:
        print("DRY_RUN=1: nothing posted")
        return
    import lib_graph as g
    g.require_env()
    who = g.me()
    print("posting as", who.get("username"), who.get("id"))
    media_id = g.publish_reel(e["video_url"], e["caption"])
    print("published media id:", media_id)
    if e.get("hashtags"):
        g.add_comment(media_id, e["hashtags"])
        print("hashtags posted as first comment")
    e["posted_media_id"] = media_id
    e["posted_at"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    save(entries)
    print("manifest updated")


if __name__ == "__main__":
    sys.exit(main())
