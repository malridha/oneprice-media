"""Comment agent for One Price. Charter-bound (see charter.md).

Reads new comments on recent media, sorts each into AUTO / REVIEW / HUMAN, drafts replies,
and only posts AUTO replies when AUTO_REPLY=1. Everything is logged to comments_log.json
and summarised in comments_digest.md for the human.

Classification + drafting use the Anthropic API when ANTHROPIC_API_KEY is set (recommended);
otherwise a conservative keyword classifier runs and nothing is auto-replied.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request

import lib_graph as g

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "comments_log.json")
DIGEST = os.path.join(HERE, "comments_digest.md")
CHARTER = open(os.path.join(HERE, "charter.md"), encoding="utf-8").read()
AUTO_REPLY = os.environ.get("AUTO_REPLY", "0") == "1"
HIDE_SPAM = os.environ.get("HIDE_SPAM", "0") == "1"
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5-5")
MAX_MEDIA = int(os.environ.get("MAX_MEDIA", "12"))

HUMAN_PAT = re.compile(r"(kill myself|suicid|self.harm|want to die|end my life|انتحار|أقتل نفسي|اموت|kafir|كافر|رافض|ناصبي|shia dogs|sunni dogs|terrorist|http[s]?://|www\.)", re.I)
REVIEW_PAT = re.compile(r"(wrong|misrepresent|incorrect|actually|not true|hadith|quran says|bible says|gita says|sheikh|imam|pastor|scholar|source\?|citation|خطأ|غلط|مصدر|حديث|الآية)", re.I)


def load_log():
    try:
        with open(LOG, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_log(d):
    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")


def classify_rules(text):
    if HUMAN_PAT.search(text):
        return "HUMAN", ""
    if REVIEW_PAT.search(text):
        return "REVIEW", ""
    return "AUTO", ""


def classify_llm(comment, caption):
    prompt = (
        f"{CHARTER}\n\n---\nReel caption:\n{caption}\n\nComment by @{comment['username']}:\n{comment['text']}\n\n"
        "Return JSON only: {\"bin\": \"AUTO\"|\"REVIEW\"|\"HUMAN\", \"reply\": \"<reply in the commenter's language, or empty for HUMAN>\", \"note\": \"<one line for the human>\"}"
    )
    body = json.dumps({"model": MODEL, "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "content-type": "application/json", "x-api-key": API_KEY, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.loads(r.read().decode())
    txt = "".join(b.get("text", "") for b in out.get("content", []))
    m = re.search(r"\{.*\}", txt, re.S)
    d = json.loads(m.group(0)) if m else {"bin": "REVIEW", "reply": "", "note": "unparsed"}
    if d.get("bin") not in ("AUTO", "REVIEW", "HUMAN"):
        d["bin"] = "REVIEW"
    # hard safety net: rules can only make it stricter
    rb, _ = classify_rules(comment["text"])
    order = {"AUTO": 0, "REVIEW": 1, "HUMAN": 2}
    if order[rb] > order[d["bin"]]:
        d["bin"], d["note"] = rb, (d.get("note", "") + " [rule override]").strip()
    if d["bin"] == "HUMAN":
        d["reply"] = ""
    return d["bin"], d.get("reply", ""), d.get("note", "")


def main():
    g.require_env()
    me = g.me()
    my_name = me.get("username", "")
    log = load_log()
    new = []
    for m in g.list_media(MAX_MEDIA):
        caption = (m.get("caption") or "")[:800]
        for c in g.list_comments(m["id"]):
            if c.get("username") == my_name or c["id"] in log:
                continue
            replied_already = any(r.get("username") == my_name for r in (c.get("replies") or {}).get("data", []))
            if replied_already:
                log[c["id"]] = {"bin": "SKIP", "reason": "already replied"}
                continue
            if API_KEY:
                try:
                    b, reply, note = classify_llm(c, caption)
                except Exception as e:  # never let the LLM path break the run
                    b, reply, note = classify_rules(c["text"])[0], "", f"llm error: {e}"
            else:
                b, reply, note = classify_rules(c["text"])
                reply = ""
            posted = False
            if b == "AUTO" and reply and AUTO_REPLY:
                try:
                    g.reply_to_comment(c["id"], reply)
                    posted = True
                except Exception as e:
                    note = f"reply failed: {e}"
            if b == "HUMAN" and HIDE_SPAM and re.search(r"http[s]?://|www\.", c["text"], re.I):
                try:
                    g.hide_comment(c["id"])
                    note = (note + " [spam hidden]").strip()
                except Exception:
                    pass
            rec = {"media": m["id"], "permalink": m.get("permalink"), "username": c.get("username"),
                   "text": c.get("text"), "bin": b, "reply": reply, "posted": posted, "note": note,
                   "seen": dt.datetime.utcnow().isoformat(timespec="minutes") + "Z"}
            log[c["id"]] = rec
            new.append((c["id"], rec))
    save_log(log)
    # digest for the human
    lines = [f"# Comment digest — {dt.datetime.utcnow():%Y-%m-%d %H:%M} UTC", ""]
    for b in ("HUMAN", "REVIEW", "AUTO"):
        items = [(i, r) for i, r in new if r["bin"] == b]
        lines.append(f"## {b} ({len(items)})")
        for i, r in items:
            lines.append(f"- @{r['username']}: {r['text']!r}")
            if r["reply"]:
                lines.append(f"  - {'POSTED' if r['posted'] else 'draft'}: {r['reply']!r}")
            if r["note"]:
                lines.append(f"  - note: {r['note']}")
            lines.append(f"  - {r['permalink']}  (comment {i})")
        lines.append("")
    open(DIGEST, "w", encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines))
    print(f"new comments: {len(new)} | auto-reply {'ON' if AUTO_REPLY else 'OFF'} | llm {'on' if API_KEY else 'off'}")


if __name__ == "__main__":
    sys.exit(main())
