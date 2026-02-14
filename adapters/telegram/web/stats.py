"""
Stats web dashboard — lightweight aiohttp app served alongside the bot.
Access: GET /stats?token=SECRET
"""

import logging
from datetime import datetime, timedelta, timezone
from aiohttp import web

logger = logging.getLogger(__name__)


def create_stats_app(user_repo, stats_token: str) -> web.Application:
    """Create aiohttp app with a single /stats route."""

    async def handle_stats(request: web.Request) -> web.Response:
        token = request.query.get("token", "")
        if token != stats_token:
            return web.Response(text="Unauthorized", status=401)

        try:
            users = await user_repo.get_all_users_summary()
        except Exception as e:
            logger.error(f"Stats query failed: {e}")
            return web.Response(text="DB error", status=500)

        total = len(users)
        onboarded = sum(1 for u in users if u.get("onboarding_completed"))
        in_progress = total - onboarded

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_ago = today_start - timedelta(days=7)

        new_today = 0
        new_yesterday = 0
        new_week = 0
        for u in users:
            created = u.get("created_at", "")
            if not created:
                continue
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except Exception:
                continue
            if dt >= today_start:
                new_today += 1
            if yesterday_start <= dt < today_start:
                new_yesterday += 1
            if dt >= week_ago:
                new_week += 1

        # Referral funnel
        referrers: dict = {}
        for u in users:
            ref = u.get("referred_by")
            if ref:
                if ref not in referrers:
                    referrers[ref] = {"total": 0, "onboarded": 0}
                referrers[ref]["total"] += 1
                if u.get("onboarding_completed"):
                    referrers[ref]["onboarded"] += 1

        organic_total = total - sum(r["total"] for r in referrers.values())
        organic_onboarded = onboarded - sum(r["onboarded"] for r in referrers.values())

        ref_rows = ""
        for ref_id, data in sorted(referrers.items(), key=lambda x: x[1]["total"], reverse=True):
            pct = round(data["onboarded"] / data["total"] * 100) if data["total"] else 0
            ref_rows += (
                f'<tr><td>ref_{ref_id}</td>'
                f'<td>{data["total"]}</td>'
                f'<td>{data["onboarded"]} ({pct}%)</td></tr>\n'
            )
        ref_rows += (
            f'<tr><td>Organic</td>'
            f'<td>{organic_total}</td>'
            f'<td>{organic_onboarded}</td></tr>\n'
        )

        onboarded_pct = round(onboarded / total * 100) if total else 0
        in_progress_pct = 100 - onboarded_pct

        html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>Sphere Stats</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 16px; background: #0d1117; color: #e6edf3; }}
  h1 {{ font-size: 1.4em; border-bottom: 1px solid #30363d; padding-bottom: 8px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 12px; }}
  .big {{ font-size: 2em; font-weight: bold; color: #58a6ff; }}
  .row {{ display: flex; justify-content: space-between; margin: 4px 0; }}
  .label {{ color: #8b949e; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid #21262d; }}
  th {{ color: #8b949e; font-weight: normal; }}
  .muted {{ color: #8b949e; font-size: 0.85em; }}
</style>
</head><body>
<h1>Sphere Growth Dashboard</h1>

<div class="card">
  <div class="big">{total}</div>
  <div class="label">Total Users</div>
  <div class="row"><span>Onboarded</span><span>{onboarded} ({onboarded_pct}%)</span></div>
  <div class="row"><span>In progress</span><span>{in_progress} ({in_progress_pct}%)</span></div>
</div>

<div class="card">
  <div class="label">New Users</div>
  <div class="row"><span>Today</span><span>{new_today}</span></div>
  <div class="row"><span>Yesterday</span><span>{new_yesterday}</span></div>
  <div class="row"><span>Last 7 days</span><span>{new_week}</span></div>
</div>

<div class="card">
  <div class="label">Referral Funnel</div>
  <table>
    <tr><th>Source</th><th>Joined</th><th>Onboarded</th></tr>
    {ref_rows}
  </table>
</div>

<p class="muted">Auto-refreshes every 30s &middot; {now.strftime('%Y-%m-%d %H:%M UTC')}</p>
</body></html>"""

        return web.Response(text=html, content_type="text/html")

    app = web.Application()
    app.router.add_get("/stats", handle_stats)
    return app
