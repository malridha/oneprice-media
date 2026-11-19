"""Minimal Instagram Graph API client, stdlib only.

Works with either token family — set IG_API_BASE to match the token:
  * Instagram-login token (starts IGAA…)  -> https://graph.instagram.com/v21.0   (default here)
  * Facebook token        (starts EAAP…)  -> https://graph.facebook.com/v21.0
A mismatch gives `code 190 Cannot parse access token`.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH_VERSION = "v21.0"
BASE = os.environ.get("IG_API_BASE", f"https://graph.instagram.com/{GRAPH_VERSION}").rstrip("/")
TOKEN = (os.environ.get("IG_ACCESS_TOKEN") or "").strip()
IG_USER_ID = (os.environ.get("IG_USER_ID") or "").strip()


class GraphError(RuntimeError):
    pass


def _call(method, path, params=None, data=None):
    params = dict(params or {})
    params["access_token"] = TOKEN
    url = f"{BASE}/{path.lstrip('/')}"
    body = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        merged = dict(params)
        merged.update(data or {})
        body = urllib.parse.urlencode(merged).encode()
    req = urllib.request.Request(url, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
        except Exception:
            err = {"error": {"message": str(e)}}
        raise GraphError(json.dumps(err.get("error", err)))


def get(path, **params):
    return _call("GET", path, params)


def post(path, **data):
    return _call("POST", path, data=data)


def require_env():
    missing = [k for k, v in {"IG_ACCESS_TOKEN": TOKEN, "IG_USER_ID": IG_USER_ID}.items() if not v]
    if missing:
        sys.exit(f"missing env: {', '.join(missing)}")


def me():
    return get("me", fields="id,username,account_type")


def publish_reel(video_url, caption, share_to_feed=True, poll_seconds=15, max_wait=600):
    """Create a REELS container from a public video URL, wait for processing, publish. Returns media id."""
    c = post(f"{IG_USER_ID}/media", media_type="REELS", video_url=video_url,
             caption=caption, share_to_feed="true" if share_to_feed else "false")
    cid = c["id"]
    waited = 0
    while waited < max_wait:
        s = get(cid, fields="status_code,status")
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise GraphError(f"container {cid} failed: {s}")
        time.sleep(poll_seconds)
        waited += poll_seconds
    else:
        raise GraphError(f"container {cid} not ready after {max_wait}s")
    pub = post(f"{IG_USER_ID}/media_publish", creation_id=cid)
    return pub["id"]


def add_comment(media_id, message):
    return post(f"{media_id}/comments", message=message)


def reply_to_comment(comment_id, message):
    return post(f"{comment_id}/replies", message=message)


def hide_comment(comment_id, hide=True):
    return post(comment_id, hide="true" if hide else "false")


def list_media(limit=25):
    return get(f"{IG_USER_ID}/media", fields="id,caption,timestamp,permalink,media_type", limit=limit).get("data", [])


def list_comments(media_id, limit=50):
    return get(f"{media_id}/comments",
               fields="id,text,username,timestamp,replies{id,text,username,timestamp}",
               limit=limit).get("data", [])


def media_insights(media_id):
    # Reels metrics; some fields are unavailable on older media types
    try:
        d = get(f"{media_id}/insights", metric="plays,reach,saved,shares,likes,comments,total_interactions,ig_reels_avg_watch_time")
    except GraphError as e:
        return {"error": str(e)}
    return {x["name"]: (x.get("values", [{}])[0].get("value") if x.get("values") else x.get("total_value", {}).get("value")) for x in d.get("data", [])}
