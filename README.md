# One Price — media & social pipeline

Public host for the finished reels of the One Price series, plus the GitHub Actions pipeline that publishes them to Instagram and runs the comment agent.

- `reels/` — finished MP4s (public links used by the publisher)
- `social/reels_manifest.json` — the queue: one entry per reel, with caption, hashtags, scheduled date; `posted_media_id` is written back after publishing
- `social/post_reel.py` — publishes the next due reel (one per run); `DRY_RUN=1` prints only
- `social/reply_agent.py` + `charter.md` — comment agent; AUTO_REPLY is off unless the repo variable `AUTO_REPLY=1`
- `social/pull_insights.py` — daily leaderboard by saves+shares per 1k plays
- `.github/workflows/` — `social-post` (daily 18:00 Dubai), `social-comments` (3×/day), `social-insights` (daily)

Secrets: `IG_ACCESS_TOKEN`, `IG_USER_ID`, optional `ANTHROPIC_API_KEY`. Variables: `IG_API_BASE` (`https://graph.instagram.com/v21.0` for an Instagram-login `IGAA…` token, `https://graph.facebook.com/v21.0` for a Facebook `EAAP…` token), `AUTO_REPLY`, `HIDE_SPAM`.
