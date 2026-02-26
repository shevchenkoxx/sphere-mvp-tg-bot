"""
Admin dashboard — aiohttp + HTMX.
Access: GET /stats?token=SECRET
"""

import csv
import io
import json
import logging
from datetime import datetime, timedelta, timezone
from aiohttp import web

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CSS + shared HTML helpers
# ---------------------------------------------------------------------------

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #0d1117; color: #e6edf3; }
a { color: #58a6ff; text-decoration: none; }
a:hover { text-decoration: underline; }

/* layout */
.shell { display: flex; flex-direction: column; min-height: 100vh; }
.nav { display: flex; gap: 4px; padding: 12px 16px; background: #161b22;
       border-bottom: 1px solid #30363d; flex-wrap: wrap; align-items: center; }
.nav-title { font-weight: 700; font-size: 1.1em; margin-right: 16px; color: #58a6ff; }
.nav a { padding: 6px 14px; border-radius: 6px; font-size: .9em; color: #8b949e;
         cursor: pointer; transition: all .15s; }
.nav a:hover { background: #21262d; color: #e6edf3; text-decoration: none; }
.nav a.active { background: #1f6feb; color: #fff; }
#content { padding: 16px; max-width: 1100px; width: 100%; margin: 0 auto; }
#toast { position: fixed; top: 16px; right: 16px; z-index: 999; }
.toast-msg { background: #238636; color: #fff; padding: 10px 18px; border-radius: 8px;
             margin-bottom: 8px; font-size: .9em; animation: fadeout 3s forwards; }
.toast-msg.error { background: #da3633; }
@keyframes fadeout { 0%,70%{opacity:1} 100%{opacity:0;display:none} }

/* cards & tables */
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 16px; margin-bottom: 14px; }
.card h3 { font-size: 1em; color: #8b949e; margin-bottom: 10px; font-weight: 500; }
.big { font-size: 2.2em; font-weight: 700; color: #58a6ff; }
.row { display: flex; justify-content: space-between; margin: 4px 0; }
.label { color: #8b949e; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
table { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: .88em; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid #21262d; }
th { color: #8b949e; font-weight: 500; position: sticky; top: 0; background: #161b22; }
tr:hover { background: #1c2128; }
tr.clickable { cursor: pointer; }
.muted { color: #8b949e; font-size: .85em; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: .78em;
         font-weight: 600; }
.badge-green { background: #238636; color: #fff; }
.badge-yellow { background: #9e6a03; color: #fff; }
.badge-red { background: #da3633; color: #fff; }
.badge-blue { background: #1f6feb; color: #fff; }

/* forms & buttons */
input[type=text], input[type=search], textarea, select {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3; border-radius: 6px;
  padding: 8px 12px; width: 100%; font-size: .9em; }
input:focus, textarea:focus, select:focus { outline: none; border-color: #58a6ff; }
textarea { resize: vertical; min-height: 80px; font-family: inherit; }
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 16px;
       border-radius: 6px; border: 1px solid #30363d; background: #21262d;
       color: #e6edf3; cursor: pointer; font-size: .88em; transition: all .15s; }
.btn:hover { background: #30363d; }
.btn-primary { background: #238636; border-color: #238636; }
.btn-primary:hover { background: #2ea043; }
.btn-danger { background: #da3633; border-color: #da3633; }
.btn-danger:hover { background: #f85149; }
.btn-blue { background: #1f6feb; border-color: #1f6feb; }
.btn-blue:hover { background: #388bfd; }
.btn-sm { padding: 4px 10px; font-size: .82em; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }

/* detail panel */
.detail { background: #1c2128; border: 1px solid #30363d; border-radius: 8px;
          padding: 16px; margin: 8px 0; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 24px; }
.detail-grid .field { margin-bottom: 6px; }
.detail-grid .field-label { color: #8b949e; font-size: .8em; }
.detail-grid .field-value { font-size: .92em; word-break: break-word; }

/* inline edit form */
.edit-form { margin-top: 12px; }
.edit-form .form-row { display: flex; gap: 8px; margin-bottom: 8px; align-items: center; }
.edit-form .form-row label { min-width: 120px; color: #8b949e; font-size: .85em; }
.edit-form .form-row input { flex: 1; }

/* search */
.search-bar { margin-bottom: 14px; position: relative; }
.search-bar input { padding-left: 36px; }
.search-icon { position: absolute; left: 12px; top: 50%; transform: translateY(-50%);
               color: #8b949e; font-size: .9em; pointer-events: none; }

/* expandable */
.expand-row td { padding: 0; }
.expand-row .detail { margin: 0; border-radius: 0; border-left: 3px solid #1f6feb; }

/* chat bubbles */
.chat-container { display: flex; flex-direction: column; gap: 6px; padding: 12px; max-height: 70vh;
                  overflow-y: auto; }
.chat-bubble { max-width: 75%; padding: 8px 12px; border-radius: 12px; font-size: .88em;
               word-break: break-word; line-height: 1.4; position: relative; }
.chat-bubble .meta { font-size: .72em; color: #8b949e; margin-top: 3px; }
.chat-bubble.incoming { align-self: flex-start; background: #1f6feb; color: #fff;
                        border-bottom-left-radius: 4px; }
.chat-bubble.incoming .meta { color: rgba(255,255,255,.6); }
.chat-bubble.outgoing { align-self: flex-end; background: #238636; color: #fff;
                        border-bottom-right-radius: 4px; }
.chat-bubble.outgoing .meta { color: rgba(255,255,255,.6); }
.chat-bubble.callback { align-self: flex-start; background: #30363d; color: #e6edf3;
                        border-bottom-left-radius: 4px; font-size: .82em; }
.chat-date-sep { text-align: center; color: #8b949e; font-size: .78em; margin: 8px 0; }
.chat-header { display: flex; justify-content: space-between; align-items: center;
               padding: 10px 16px; border-bottom: 1px solid #30363d; }
.user-list-item { display: flex; justify-content: space-between; align-items: center;
                  padding: 10px 14px; border-bottom: 1px solid #21262d; cursor: pointer;
                  transition: background .15s; }
.user-list-item:hover { background: #1c2128; }
.user-list-item .name { font-weight: 500; }
.user-list-item .preview { color: #8b949e; font-size: .82em; overflow: hidden;
                           text-overflow: ellipsis; white-space: nowrap; max-width: 400px; }
.user-list-item .time { color: #8b949e; font-size: .78em; white-space: nowrap; }

/* filter bar */
.filter-bar { display: flex; gap: 6px; margin-bottom: 14px; flex-wrap: wrap; align-items: center; }
.filter-group { display: flex; flex-direction: column; gap: 3px; }
.filter-group label { font-size: .78em; color: #8b949e; }
.filter-group select, .filter-group input { font-size: .85em; }

/* funnel */
.funnel-container { display: flex; flex-direction: column; gap: 6px; }
.funnel-step { display: flex; align-items: center; gap: 10px; }
.funnel-bar { background: linear-gradient(90deg, #1f6feb, #58a6ff); color: #fff; padding: 6px 12px;
              border-radius: 4px; font-size: .85em; font-weight: 600; min-width: 40px;
              transition: width .3s; white-space: nowrap; }
.funnel-label { color: #8b949e; font-size: .82em; white-space: nowrap; }

/* heatmap */
.heatmap { display: grid; grid-template-columns: 50px repeat(24, 1fr); gap: 2px; font-size: .72em; }
.heatmap-cell { aspect-ratio: 1; border-radius: 3px; display: flex; align-items: center;
                justify-content: center; color: #8b949e; font-size: .7em; }
.heatmap-label { display: flex; align-items: center; color: #8b949e; font-size: .78em; }
.heatmap-header { display: flex; align-items: center; justify-content: center; color: #8b949e; }

/* chart container */
.chart-container { position: relative; margin: 8px 0; }

/* responsive */
@media (max-width: 700px) {
  .detail-grid { grid-template-columns: 1fr; }
  .grid { grid-template-columns: 1fr; }
  .nav { gap: 2px; }
  .nav a { padding: 5px 10px; font-size: .82em; }
  .chat-bubble { max-width: 90%; }
  .user-list-item .preview { max-width: 200px; }
  .heatmap { grid-template-columns: 40px repeat(24, 1fr); font-size: .6em; }
  .filter-bar { gap: 4px; }
}
"""


def _shell_html(token: str, active_tab: str = "overview") -> str:
    """Full HTML shell with nav. Content loaded by HTMX."""
    tabs = [
        ("overview", "Overview"),
        ("users", "Users"),
        ("onboarding", "Onboarding"),
        ("communities", "Communities"),
        ("events", "Events"),
        ("matches", "Matches"),
        ("conversations", "Conversations"),
        ("broadcast", "Broadcast"),
    ]
    nav_links = ""
    for tid, label in tabs:
        cls = ' class="active"' if tid == active_tab else ""
        nav_links += (
            f'<a{cls} hx-get="/stats/{tid}?token={token}" '
            f'hx-target="#content" hx-push-url="false" '
            f'onclick="document.querySelectorAll(\'.nav a\').forEach(a=>a.classList.remove(\'active\'));'
            f'this.classList.add(\'active\')">{label}</a>\n'
        )
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sphere Admin</title>
<style>{CSS}</style>
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<script>
// Destroy all Chart.js instances before HTMX swap to prevent canvas reuse errors
document.addEventListener('htmx:beforeSwap', function() {{
  Object.keys(Chart.instances || {{}}).forEach(function(k) {{
    try {{ Chart.instances[k].destroy(); }} catch(e) {{}}
  }});
}});
</script>
</head><body>
<div class="shell">
<div class="nav">
  <span class="nav-title">Sphere Admin</span>
  {nav_links}
</div>
<div id="toast"></div>
<div id="content"
     hx-get="/stats/overview?token={token}"
     hx-trigger="load"
     hx-target="#content">
  <p class="muted" style="padding:40px;text-align:center">Loading...</p>
</div>
</div>
</body></html>"""


def _esc(val) -> str:
    """HTML-escape a value."""
    if val is None:
        return ""
    return str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _trunc(val, length=60) -> str:
    s = _esc(str(val)) if val else ""
    return s[:length] + "..." if len(s) > length else s


def _parse_dt(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def _fmt_dt(raw) -> str:
    dt = _parse_dt(raw)
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def _list_to_str(val) -> str:
    if not val:
        return ""
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val)


def _parse_range(request):
    """Parse date range from query param. Returns (key, cutoff_datetime_or_None)."""
    key = request.query.get("range", "all")
    now = datetime.now(timezone.utc)
    if key == "today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif key == "7d":
        cutoff = now - timedelta(days=7)
    elif key == "30d":
        cutoff = now - timedelta(days=30)
    else:
        key = "all"
        cutoff = None
    return key, cutoff


def _date_range_picker_html(token: str, tab: str, active: str = "all", extra_params: str = "") -> str:
    """Render 4 date range buttons with HTMX."""
    buttons = []
    for key, label in [("today", "Today"), ("7d", "7d"), ("30d", "30d"), ("all", "All")]:
        cls = "btn btn-sm btn-blue" if key == active else "btn btn-sm"
        buttons.append(
            f'<a class="{cls}" hx-get="/stats/{tab}?token={token}&range={key}{extra_params}" '
            f'hx-target="#content">{label}</a>'
        )
    return f'<div class="filter-bar">{"".join(buttons)}</div>'


def _chart_html(chart_id: str, chart_type: str, labels: list, datasets: list, height: int = 250) -> str:
    """Render a Chart.js canvas with inline init script."""
    options = {
        "responsive": True,
        "maintainAspectRatio": False,
        "plugins": {"legend": {"labels": {"color": "#8b949e"}}},
    }
    if chart_type not in ("doughnut", "pie"):
        options["scales"] = {
            "x": {"ticks": {"color": "#8b949e"}, "grid": {"color": "#21262d"}},
            "y": {"ticks": {"color": "#8b949e"}, "grid": {"color": "#21262d"}, "beginAtZero": True},
        }
    config = {"type": chart_type, "data": {"labels": labels, "datasets": datasets}, "options": options}
    config_json = json.dumps(config)
    return (
        f'<div class="chart-container" style="height:{height}px"><canvas id="{chart_id}"></canvas></div>'
        f'<script>(function(){{'
        f'var c=document.getElementById("{chart_id}");'
        f'if(!c)return;'
        f'new Chart(c.getContext("2d"),{config_json});'
        f'}})()</script>'
    )


def _funnel_html(steps) -> str:
    """Render a horizontal funnel. steps = [(label, value), ...]"""
    if not steps:
        return '<span class="muted">No data</span>'
    max_val = max(s[1] for s in steps) if steps else 1
    html = '<div class="funnel-container">'
    for i, (label, value) in enumerate(steps):
        pct = round(value / max_val * 100) if max_val else 0
        drop = ""
        if i > 0 and steps[0][1] > 0:
            drop = f" ({round(value / steps[0][1] * 100)}%)"
        html += (
            f'<div class="funnel-step">'
            f'<div class="funnel-bar" style="width:{max(pct, 8)}%">{value}{drop}</div>'
            f'<div class="funnel-label">{_esc(label)}</div>'
            f'</div>'
        )
    html += '</div>'
    return html


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def create_stats_app(user_repo, stats_token: str, bot=None, user_service=None,
                     match_repo=None, event_repo=None, conv_log_repo=None) -> web.Application:
    """Create aiohttp app with admin dashboard routes."""

    def _check_token(request: web.Request) -> bool:
        return request.query.get("token", "") == stats_token

    # === SHELL ===
    async def handle_shell(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)
        return web.Response(text=_shell_html(stats_token), content_type="text/html")

    # === OVERVIEW TAB ===
    async def handle_overview(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)

        range_key, cutoff = _parse_range(request)

        try:
            users = await user_repo.get_all_users_full()
        except Exception as e:
            logger.error(f"Overview query failed: {e}")
            return web.Response(text=f'<div class="card">DB error: {_esc(str(e))}</div>',
                                content_type="text/html")

        # Filter users by date range
        filtered_users = users
        if cutoff:
            filtered_users = [u for u in users if _parse_dt(u.get("created_at")) and _parse_dt(u.get("created_at")) >= cutoff]

        total = len(users)
        filtered_total = len(filtered_users)
        onboarded = sum(1 for u in users if u.get("onboarding_completed"))
        in_progress = total - onboarded
        onboarded_pct = round(onboarded / total * 100) if total else 0

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_ago = today_start - timedelta(days=7)

        new_today = new_yesterday = new_week = 0
        intent_counts: dict[str, int] = {}
        city_counts: dict[str, int] = {}
        has_photo = has_bio = has_profession = has_interests = has_goals = 0
        referrers: dict[str, dict] = {}

        # Daily signups for chart (last 30 days)
        daily_signups: dict[str, int] = {}
        for i in range(30):
            d = (today_start - timedelta(days=29 - i)).strftime("%m/%d")
            daily_signups[d] = 0

        for u in users:
            dt = _parse_dt(u.get("created_at"))
            if dt:
                if dt >= today_start:
                    new_today += 1
                if yesterday_start <= dt < today_start:
                    new_yesterday += 1
                if dt >= week_ago:
                    new_week += 1
                # Daily chart
                day_key = dt.strftime("%m/%d")
                if day_key in daily_signups:
                    daily_signups[day_key] += 1

            for intent in (u.get("connection_intents") or []):
                intent_counts[intent] = intent_counts.get(intent, 0) + 1

            city = u.get("city_current")
            if city:
                city_counts[city] = city_counts.get(city, 0) + 1

            if u.get("photo_url"):
                has_photo += 1
            if u.get("bio"):
                has_bio += 1
            if u.get("profession"):
                has_profession += 1
            if u.get("interests"):
                has_interests += 1
            if u.get("goals"):
                has_goals += 1

            ref = u.get("referred_by")
            if ref:
                referrers.setdefault(ref, {"total": 0, "onboarded": 0})
                referrers[ref]["total"] += 1
                if u.get("onboarding_completed"):
                    referrers[ref]["onboarded"] += 1

        # Match stats
        match_total = 0
        match_avg_score = 0
        feedback_good = feedback_bad = 0
        users_with_matches = 0
        if match_repo:
            try:
                from infrastructure.database.supabase_client import supabase, run_sync
                @run_sync
                def _get_match_stats():
                    resp = supabase.table("matches").select("id, compatibility_score, user_a_id, user_b_id").execute()
                    return resp.data or []
                all_matches = await _get_match_stats()
                match_total = len(all_matches)
                if match_total:
                    scores = [m["compatibility_score"] for m in all_matches if m.get("compatibility_score")]
                    match_avg_score = round(sum(scores) / len(scores), 2) if scores else 0
                    matched_ids = set()
                    for m in all_matches:
                        matched_ids.add(m.get("user_a_id"))
                        matched_ids.add(m.get("user_b_id"))
                    users_with_matches = len(matched_ids)

                @run_sync
                def _get_feedback_stats():
                    resp = supabase.table("match_feedback").select("feedback_type").execute()
                    return resp.data or []
                all_fb = await _get_feedback_stats()
                for fb in all_fb:
                    if fb.get("feedback_type") == "good":
                        feedback_good += 1
                    else:
                        feedback_bad += 1
            except Exception as e:
                logger.warning(f"Match stats failed: {e}")

        # Active users (7d) — users who sent a message in the last 7 days
        active_7d = 0
        if conv_log_repo:
            try:
                active_list = await conv_log_repo.get_active_users(limit=9999, hours=168)
                active_7d = len(active_list)
            except Exception:
                pass

        # Conversion funnel
        funnel_steps = [
            ("Total users", total),
            ("Onboarded", onboarded),
            ("Got matches", users_with_matches),
            ("Active (7d)", active_7d),
        ]

        # Daily signups chart
        signup_labels = list(daily_signups.keys())
        signup_data = list(daily_signups.values())
        signup_chart = _chart_html(
            "signupChart", "line", signup_labels,
            [{"label": "New users", "data": signup_data,
              "borderColor": "#58a6ff", "backgroundColor": "rgba(88,166,255,0.1)",
              "fill": True, "tension": 0.3}],
            height=200,
        )

        # Profile completeness — depth distribution
        depth_buckets = {"0-25%": 0, "25-50%": 0, "50-75%": 0, "75-100%": 0}
        profile_fields = ["bio", "interests", "goals", "looking_for", "can_help_with",
                          "photo_url", "profession", "city_current", "connection_intents", "skills"]
        for u in users:
            filled = sum(1 for f in profile_fields if u.get(f))
            pct = filled / len(profile_fields) * 100
            if pct < 25:
                depth_buckets["0-25%"] += 1
            elif pct < 50:
                depth_buckets["25-50%"] += 1
            elif pct < 75:
                depth_buckets["50-75%"] += 1
            else:
                depth_buckets["75-100%"] += 1

        avg_completeness = 0
        if total:
            total_filled = sum(
                sum(1 for f in profile_fields if u.get(f)) for u in users
            )
            avg_completeness = round(total_filled / (total * len(profile_fields)) * 100)

        depth_chart = _chart_html(
            "depthChart", "doughnut",
            list(depth_buckets.keys()),
            [{"data": list(depth_buckets.values()),
              "backgroundColor": ["#da3633", "#9e6a03", "#1f6feb", "#238636"]}],
            height=200,
        )

        # Build referral rows
        ref_rows = ""
        for ref_id, data in sorted(referrers.items(), key=lambda x: x[1]["total"], reverse=True):
            pct = round(data["onboarded"] / data["total"] * 100) if data["total"] else 0
            ref_rows += (
                f'<tr><td>ref_{_esc(ref_id)}</td>'
                f'<td>{data["total"]}</td>'
                f'<td>{data["onboarded"]} ({pct}%)</td></tr>'
            )
        organic_total = total - sum(r["total"] for r in referrers.values())
        organic_onboarded = onboarded - sum(r["onboarded"] for r in referrers.values())
        ref_rows += f'<tr><td>Organic</td><td>{organic_total}</td><td>{organic_onboarded}</td></tr>'

        # Intent distribution
        intent_html = ""
        for intent, cnt in sorted(intent_counts.items(), key=lambda x: -x[1]):
            intent_html += f'<div class="row"><span>{_esc(intent)}</span><span>{cnt}</span></div>'

        # Top cities
        city_html = ""
        for city, cnt in sorted(city_counts.items(), key=lambda x: -x[1])[:10]:
            city_html += f'<div class="row"><span>{_esc(city)}</span><span>{cnt}</span></div>'

        # Profile completeness bars
        photo_pct = round(has_photo / total * 100) if total else 0
        bio_pct = round(has_bio / total * 100) if total else 0
        prof_pct = round(has_profession / total * 100) if total else 0

        range_picker = _date_range_picker_html(stats_token, "overview", range_key)

        html = f"""
<div hx-get="/stats/overview?token={stats_token}&range={range_key}" hx-trigger="every 30s" hx-target="#content">

{range_picker}

<div class="grid">
  <div class="card">
    <div class="big">{total}</div>
    <div class="label">Total Users</div>
    <div class="row"><span>Onboarded</span><span>{onboarded} ({onboarded_pct}%)</span></div>
    <div class="row"><span>In progress</span><span>{in_progress}</span></div>
  </div>
  <div class="card">
    <h3>New Users</h3>
    <div class="row"><span>Today</span><span>{new_today}</span></div>
    <div class="row"><span>Yesterday</span><span>{new_yesterday}</span></div>
    <div class="row"><span>Last 7 days</span><span>{new_week}</span></div>
  </div>
  <div class="card">
    <h3>Matches</h3>
    <div class="row"><span>Total</span><span>{match_total}</span></div>
    <div class="row"><span>Avg score</span><span>{match_avg_score}</span></div>
    <div class="row"><span>Feedback</span><span>{feedback_good} good / {feedback_bad} bad</span></div>
  </div>
  <div class="card">
    <h3>Profile Quality</h3>
    <div class="row"><span>Avg completeness</span><span>{avg_completeness}%</span></div>
    <div class="row"><span>Has photo</span><span>{has_photo} ({photo_pct}%)</span></div>
    <div class="row"><span>Has bio</span><span>{has_bio} ({bio_pct}%)</span></div>
  </div>
</div>

<div class="card">
  <h3>Daily Signups (30 days)</h3>
  {signup_chart}
</div>

<div class="card">
  <h3>Conversion Funnel</h3>
  {_funnel_html(funnel_steps)}
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
  <div class="card">
    <h3>Profile Depth Distribution</h3>
    {depth_chart}
  </div>
  <div class="card">
    <h3>Intent Distribution</h3>
    {intent_html if intent_html else '<span class="muted">No intent data</span>'}
  </div>
</div>

<div class="card">
  <h3>Top Cities</h3>
  {city_html if city_html else '<span class="muted">No city data</span>'}
</div>

<div class="card">
  <h3>Referral Funnel</h3>
  <table>
    <tr><th>Source</th><th>Joined</th><th>Onboarded</th></tr>
    {ref_rows}
  </table>
</div>

<p class="muted" style="margin-top:12px">Auto-refreshes every 30s &middot; {now.strftime('%Y-%m-%d %H:%M UTC')}</p>
</div>"""
        return web.Response(text=html, content_type="text/html")

    # === USERS TAB ===
    async def handle_users(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)

        # Parse all filters
        q = request.query.get("q", "").strip()
        city_filter = request.query.get("city", "").strip()
        intent_filter = request.query.get("intent", "").strip()
        onb_filter = request.query.get("onb", "").strip()
        photo_filter = request.query.get("photo", "").strip()
        range_key, cutoff = _parse_range(request)

        try:
            if q:
                users = await user_repo.search_users(q)
            else:
                users = await user_repo.get_all_users_full()
        except Exception as e:
            logger.error(f"Users query failed: {e}")
            return web.Response(text=f'<div class="card">DB error: {_esc(str(e))}</div>',
                                content_type="text/html")

        # Collect unique cities and intents for dropdowns (before filtering)
        all_cities: dict[str, int] = {}
        all_intents: dict[str, int] = {}
        for u in users:
            c = u.get("city_current")
            if c:
                all_cities[c] = all_cities.get(c, 0) + 1
            for intent in (u.get("connection_intents") or []):
                all_intents[intent] = all_intents.get(intent, 0) + 1

        # Apply filters
        filtered = users
        if city_filter:
            filtered = [u for u in filtered if u.get("city_current") == city_filter]
        if intent_filter:
            filtered = [u for u in filtered if intent_filter in (u.get("connection_intents") or [])]
        if onb_filter == "yes":
            filtered = [u for u in filtered if u.get("onboarding_completed")]
        elif onb_filter == "no":
            filtered = [u for u in filtered if not u.get("onboarding_completed")]
        if photo_filter == "yes":
            filtered = [u for u in filtered if u.get("photo_url")]
        elif photo_filter == "no":
            filtered = [u for u in filtered if not u.get("photo_url")]
        if cutoff:
            filtered = [u for u in filtered if _parse_dt(u.get("created_at")) and _parse_dt(u.get("created_at")) >= cutoff]

        # Build filter params for HTMX
        def _filter_params():
            parts = []
            if q:
                parts.append(f"q={_esc(q)}")
            if city_filter:
                parts.append(f"city={_esc(city_filter)}")
            if intent_filter:
                parts.append(f"intent={_esc(intent_filter)}")
            if onb_filter:
                parts.append(f"onb={_esc(onb_filter)}")
            if photo_filter:
                parts.append(f"photo={_esc(photo_filter)}")
            parts.append(f"range={range_key}")
            return "&".join(parts)

        params = _filter_params()

        # City dropdown
        city_options = '<option value="">All cities</option>'
        for c, cnt in sorted(all_cities.items(), key=lambda x: -x[1]):
            sel = " selected" if c == city_filter else ""
            city_options += f'<option value="{_esc(c)}"{sel}>{_esc(c)} ({cnt})</option>'

        # Intent dropdown
        intent_options = '<option value="">All intents</option>'
        for intent, cnt in sorted(all_intents.items(), key=lambda x: -x[1]):
            sel = " selected" if intent == intent_filter else ""
            intent_options += f'<option value="{_esc(intent)}"{sel}>{_esc(intent)} ({cnt})</option>'

        # Onboarding dropdown
        onb_options = '<option value="">All</option>'
        for val, label in [("yes", "Completed"), ("no", "In progress")]:
            sel = " selected" if val == onb_filter else ""
            onb_options += f'<option value="{val}"{sel}>{label}</option>'

        # Photo dropdown
        photo_options = '<option value="">All</option>'
        for val, label in [("yes", "Yes"), ("no", "No")]:
            sel = " selected" if val == photo_filter else ""
            photo_options += f'<option value="{val}"{sel}>{label}</option>'

        rows = ""
        for u in filtered:
            uid = u.get("id", "")
            active_badge = ('<span class="badge badge-green">Active</span>'
                            if u.get("is_active", True)
                            else '<span class="badge badge-red">Inactive</span>')
            onb_badge = ('<span class="badge badge-green">Yes</span>'
                         if u.get("onboarding_completed")
                         else '<span class="badge badge-yellow">No</span>')
            intents = _list_to_str(u.get("connection_intents"))
            rows += (
                f'<tr class="clickable" hx-get="/stats/user/{uid}?token={stats_token}" '
                f'hx-target="#detail-{uid}" hx-swap="innerHTML">'
                f'<td>{_esc(u.get("display_name") or u.get("first_name") or "—")}</td>'
                f'<td>{_esc(u.get("username") or "")}</td>'
                f'<td>{_esc(u.get("city_current") or "")}</td>'
                f'<td>{_esc(u.get("profession") or "")}</td>'
                f'<td>{_trunc(intents, 30)}</td>'
                f'<td>{onb_badge}</td>'
                f'<td>{active_badge}</td>'
                f'<td class="muted">{_fmt_dt(u.get("created_at"))}</td>'
                f'</tr>'
                f'<tr class="expand-row"><td colspan="8" id="detail-{uid}"></td></tr>'
            )

        # Date range picker
        range_buttons = ""
        for key, label in [("today", "Today"), ("7d", "7d"), ("30d", "30d"), ("all", "All")]:
            cls = "btn btn-sm btn-blue" if key == range_key else "btn btn-sm"
            range_buttons += f'<a class="{cls}" onclick="document.getElementById(\'user-range\').value=\'{key}\';document.getElementById(\'user-filter-form\').dispatchEvent(new Event(\'submit\',{{bubbles:true}}))">{label}</a> '

        html = f"""
<form id="user-filter-form" class="card" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end"
      hx-get="/stats/users?token={stats_token}" hx-target="#content" hx-trigger="submit, change from:select">
  <div class="filter-group">
    <label>Search</label>
    <input type="search" name="q" placeholder="Name or username..." value="{_esc(q)}" style="width:180px"
           hx-get="/stats/users?token={stats_token}" hx-trigger="keyup changed delay:400ms"
           hx-target="#content" hx-include="closest form">
  </div>
  <div class="filter-group">
    <label>City</label>
    <select name="city" style="width:150px">{city_options}</select>
  </div>
  <div class="filter-group">
    <label>Intent</label>
    <select name="intent" style="width:130px">{intent_options}</select>
  </div>
  <div class="filter-group">
    <label>Onboarded</label>
    <select name="onb" style="width:110px">{onb_options}</select>
  </div>
  <div class="filter-group">
    <label>Photo</label>
    <select name="photo" style="width:90px">{photo_options}</select>
  </div>
  <input type="hidden" name="range" id="user-range" value="{range_key}">
  <div class="filter-group">
    <label>Period</label>
    <div style="display:flex;gap:4px">{range_buttons}</div>
  </div>
</form>
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
  <span class="muted">{len(filtered)} users{f' (filtered from {len(users)})' if len(filtered) != len(users) else ''}</span>
  <a href="/stats/export/users?token={stats_token}" class="btn btn-sm">Export CSV</a>
</div>
<div class="card" style="overflow-x:auto">
<table>
<tr>
  <th>Name</th><th>@username</th><th>City</th><th>Profession</th>
  <th>Intents</th><th>Onboarded</th><th>Active</th><th>Created</th>
</tr>
{rows}
</table>
</div>"""
        return web.Response(text=html, content_type="text/html")

    # === USER DETAIL ===
    async def handle_user_detail(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)
        uid = request.match_info["id"]
        try:
            u = await user_repo.get_user_dict(uid)
        except Exception as e:
            return web.Response(text=f'<div class="detail">Error: {_esc(str(e))}</div>',
                                content_type="text/html")
        if not u:
            return web.Response(text='<div class="detail">User not found</div>',
                                content_type="text/html")

        fields = [
            ("Bio", "bio"), ("Interests", "interests"), ("Goals", "goals"),
            ("Looking for", "looking_for"), ("Can help with", "can_help_with"),
            ("Skills", "skills"), ("Profession", "profession"), ("Company", "company"),
            ("Experience", "experience_level"), ("Language", "language"),
            ("Gender", "gender"), ("Partner values", "partner_values"),
            ("Intents", "connection_intents"), ("Personality", "personality_vibe"),
            ("Referred by", "referred_by"), ("Referral count", "referral_count"),
            ("Photo", "photo_url"),
        ]
        detail_fields = ""
        for label, key in fields:
            val = u.get(key)
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val) if val else ""
            if key == "photo_url" and val:
                val = "Has photo"
            elif key == "photo_url":
                val = "No photo"
            detail_fields += (
                f'<div class="field"><div class="field-label">{label}</div>'
                f'<div class="field-value">{_esc(str(val)) if val else "—"}</div></div>'
            )

        # AI summary (expandable)
        ai_summary = u.get("ai_summary") or ""
        summary_html = ""
        if ai_summary:
            short = _trunc(ai_summary, 150)
            summary_html = f"""
<div class="field" style="grid-column:1/-1;margin-top:8px">
  <div class="field-label">AI Summary</div>
  <div class="field-value muted">{_esc(ai_summary)}</div>
</div>"""

        is_active = u.get("is_active", True)
        toggle_label = "Deactivate" if is_active else "Activate"
        toggle_class = "btn-danger btn-sm" if is_active else "btn-primary btn-sm"
        platform_uid = _esc(u.get("platform_user_id", ""))

        html = f"""<div class="detail">
<div class="detail-grid">
{detail_fields}
{summary_html}
</div>

<div class="actions">
  <button class="btn btn-sm btn-blue"
          onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
    Edit</button>
  <div style="display:none;width:100%">
    <form class="edit-form" hx-post="/stats/user/{uid}/edit?token={stats_token}"
          hx-target="#toast" hx-swap="innerHTML">
      <div class="form-row"><label>Name</label>
        <input type="text" name="display_name" value="{_esc(u.get('display_name') or '')}"></div>
      <div class="form-row"><label>Bio</label>
        <input type="text" name="bio" value="{_esc(u.get('bio') or '')}"></div>
      <div class="form-row"><label>City</label>
        <input type="text" name="city_current" value="{_esc(u.get('city_current') or '')}"></div>
      <div class="form-row"><label>Profession</label>
        <input type="text" name="profession" value="{_esc(u.get('profession') or '')}"></div>
      <div class="form-row"><label>Interests</label>
        <input type="text" name="interests" value="{_esc(_list_to_str(u.get('interests')))}"></div>
      <div class="form-row"><label>Goals</label>
        <input type="text" name="goals" value="{_esc(_list_to_str(u.get('goals')))}"></div>
      <div class="form-row"><label>Looking for</label>
        <input type="text" name="looking_for" value="{_esc(u.get('looking_for') or '')}"></div>
      <div class="form-row"><label>Can help with</label>
        <input type="text" name="can_help_with" value="{_esc(u.get('can_help_with') or '')}"></div>
      <div class="form-row"><label>Intents</label>
        <input type="text" name="connection_intents" value="{_esc(_list_to_str(u.get('connection_intents')))}"></div>
      <button class="btn btn-primary btn-sm" type="submit">Save</button>
    </form>
  </div>
</div>

<div class="actions" style="margin-top:8px">
  <button class="btn btn-sm btn-blue"
          onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'flex':'none'">
    Send DM</button>
  <div style="display:none;gap:8px;align-items:center;width:100%">
    <form style="display:flex;gap:8px;width:100%"
          hx-post="/stats/user/{uid}/dm?token={stats_token}"
          hx-target="#toast" hx-swap="innerHTML">
      <input type="text" name="text" placeholder="Message text..." style="flex:1">
      <button class="btn btn-primary btn-sm" type="submit">Send</button>
    </form>
  </div>
</div>

<div class="actions" style="margin-top:8px">
  <button class="btn {toggle_class}"
          hx-post="/stats/user/{uid}/toggle?token={stats_token}"
          hx-target="#detail-{uid}" hx-swap="innerHTML">
    {toggle_label}</button>
  <button class="btn btn-danger btn-sm"
          hx-post="/stats/user/{uid}/reset?token={stats_token}"
          hx-target="#toast" hx-swap="innerHTML"
          hx-confirm="Reset this user's entire profile? This cannot be undone.">
    Reset Profile</button>
</div>

<div class="muted" style="margin-top:10px">
  ID: {_esc(uid)} &middot; TG: {platform_uid} &middot;
  Created: {_fmt_dt(u.get('created_at'))} &middot; Updated: {_fmt_dt(u.get('updated_at'))}
</div>
</div>"""
        return web.Response(text=html, content_type="text/html")

    # === USER EDIT ===
    async def handle_user_edit(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)
        uid = request.match_info["id"]
        data = await request.post()

        u = await user_repo.get_user_dict(uid)
        if not u:
            return web.Response(text='<div class="toast-msg error">User not found</div>',
                                content_type="text/html")

        update_fields = {}
        for field in ["display_name", "bio", "city_current", "profession", "looking_for", "can_help_with"]:
            val = data.get(field)
            if val is not None:
                update_fields[field] = val.strip() if val.strip() else None

        for field in ["interests", "goals", "connection_intents"]:
            val = data.get(field)
            if val is not None:
                update_fields[field] = [v.strip() for v in val.split(",") if v.strip()] if val.strip() else []

        if not update_fields:
            return web.Response(text='<div class="toast-msg error">No changes</div>',
                                content_type="text/html")

        try:
            from infrastructure.database.supabase_client import supabase, run_sync
            @run_sync
            def _update():
                supabase.table("users").update(update_fields).eq("id", uid).execute()
            await _update()
        except Exception as e:
            logger.error(f"User edit failed: {e}")
            return web.Response(text=f'<div class="toast-msg error">Error: {_esc(str(e))}</div>',
                                content_type="text/html")

        return web.Response(text='<div class="toast-msg">User updated</div>',
                            content_type="text/html")

    # === USER RESET ===
    async def handle_user_reset(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)
        uid = request.match_info["id"]
        u = await user_repo.get_user_dict(uid)
        if not u:
            return web.Response(text='<div class="toast-msg error">User not found</div>',
                                content_type="text/html")

        platform_uid = u.get("platform_user_id")
        if not platform_uid or not user_service:
            return web.Response(text='<div class="toast-msg error">Cannot reset</div>',
                                content_type="text/html")
        try:
            from core.domain.models import MessagePlatform
            await user_service.reset_user(MessagePlatform.TELEGRAM, str(platform_uid))
        except Exception as e:
            logger.error(f"User reset failed: {e}")
            return web.Response(text=f'<div class="toast-msg error">Error: {_esc(str(e))}</div>',
                                content_type="text/html")

        return web.Response(text='<div class="toast-msg">Profile reset</div>',
                            content_type="text/html")

    # === USER DM ===
    async def handle_user_dm(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)
        uid = request.match_info["id"]
        data = await request.post()
        text = (data.get("text") or "").strip()
        if not text:
            return web.Response(text='<div class="toast-msg error">Empty message</div>',
                                content_type="text/html")

        u = await user_repo.get_user_dict(uid)
        if not u or not bot:
            return web.Response(text='<div class="toast-msg error">Cannot send</div>',
                                content_type="text/html")

        platform_uid = u.get("platform_user_id")
        try:
            await bot.send_message(int(platform_uid), text)
        except Exception as e:
            logger.error(f"DM failed: {e}")
            return web.Response(text=f'<div class="toast-msg error">Failed: {_esc(str(e))}</div>',
                                content_type="text/html")

        return web.Response(text='<div class="toast-msg">Message sent</div>',
                            content_type="text/html")

    # === USER TOGGLE ===
    async def handle_user_toggle(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)
        uid = request.match_info["id"]
        u = await user_repo.get_user_dict(uid)
        if not u:
            return web.Response(text='<div class="detail">User not found</div>',
                                content_type="text/html")

        new_active = not u.get("is_active", True)
        try:
            from infrastructure.database.supabase_client import supabase, run_sync
            @run_sync
            def _toggle():
                supabase.table("users").update({"is_active": new_active}).eq("id", uid).execute()
            await _toggle()
        except Exception as e:
            logger.error(f"Toggle failed: {e}")
            return web.Response(text=f'<div class="detail">Error: {_esc(str(e))}</div>',
                                content_type="text/html")

        # Re-render the detail panel
        return await handle_user_detail(request)

    # === EVENTS TAB ===
    async def handle_events(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)

        try:
            from infrastructure.database.supabase_client import supabase, run_sync
            @run_sync
            def _get_events():
                resp = supabase.table("events").select("*").order("created_at", desc=True).execute()
                return resp.data or []
            events = await _get_events()

            @run_sync
            def _get_participants():
                resp = supabase.table("event_participants").select("event_id, user_id").execute()
                return resp.data or []
            participants = await _get_participants()

            @run_sync
            def _get_matches():
                resp = supabase.table("matches").select("id, event_id, compatibility_score").execute()
                return resp.data or []
            matches = await _get_matches()
        except Exception as e:
            logger.error(f"Events query failed: {e}")
            return web.Response(text=f'<div class="card">DB error: {_esc(str(e))}</div>',
                                content_type="text/html")

        # Count participants and matches per event
        part_counts: dict[str, int] = {}
        for p in participants:
            eid = p.get("event_id")
            part_counts[eid] = part_counts.get(eid, 0) + 1

        match_counts: dict[str, int] = {}
        for m in matches:
            eid = m.get("event_id")
            if eid:
                match_counts[eid] = match_counts.get(eid, 0) + 1

        rows = ""
        for ev in events:
            eid = ev.get("id", "")
            active_badge = ('<span class="badge badge-green">Active</span>'
                            if ev.get("is_active", True)
                            else '<span class="badge badge-red">Inactive</span>')
            p_count = part_counts.get(eid, 0)
            m_count = match_counts.get(eid, 0)
            rows += (
                f'<tr class="clickable" hx-get="/stats/event/{eid}?token={stats_token}" '
                f'hx-target="#ev-detail-{eid}" hx-swap="innerHTML">'
                f'<td>{_esc(ev.get("name") or "—")}</td>'
                f'<td><code>{_esc(ev.get("code") or "")}</code></td>'
                f'<td>{p_count}</td>'
                f'<td>{m_count}</td>'
                f'<td>{active_badge}</td>'
                f'<td class="muted">{_fmt_dt(ev.get("created_at"))}</td>'
                f'</tr>'
                f'<tr class="expand-row"><td colspan="6" id="ev-detail-{eid}"></td></tr>'
            )

        html = f"""
<div class="card" style="overflow-x:auto">
<table>
<tr><th>Name</th><th>Code</th><th>Participants</th><th>Matches</th><th>Active</th><th>Created</th></tr>
{rows if rows else '<tr><td colspan="6" class="muted">No events</td></tr>'}
</table>
</div>"""
        return web.Response(text=html, content_type="text/html")

    # === EVENT DETAIL ===
    async def handle_event_detail(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)
        eid = request.match_info["id"]

        try:
            from infrastructure.database.supabase_client import supabase, run_sync
            @run_sync
            def _get_event():
                resp = supabase.table("events").select("*").eq("id", eid).execute()
                return resp.data[0] if resp.data else None
            ev = await _get_event()

            if not ev:
                return web.Response(text='<div class="detail">Event not found</div>',
                                    content_type="text/html")

            @run_sync
            def _get_parts():
                resp = supabase.table("event_participants").select("*, users(*)").eq("event_id", eid).execute()
                return resp.data or []
            parts = await _get_parts()

            @run_sync
            def _get_ev_matches():
                resp = supabase.table("matches").select("*, match_feedback(*)").eq("event_id", eid).order("compatibility_score", desc=True).execute()
                return resp.data or []
            ev_matches = await _get_ev_matches()
        except Exception as e:
            return web.Response(text=f'<div class="detail">Error: {_esc(str(e))}</div>',
                                content_type="text/html")

        # Participant list
        part_rows = ""
        for p in parts:
            u = p.get("users") or {}
            part_rows += (
                f'<tr><td>{_esc(u.get("display_name") or u.get("first_name") or "—")}</td>'
                f'<td>{_esc(u.get("username") or "")}</td>'
                f'<td>{_esc(u.get("city_current") or "")}</td></tr>'
            )

        # Match stats
        total_m = len(ev_matches)
        avg_score = round(sum(m["compatibility_score"] for m in ev_matches) / total_m, 2) if total_m else 0
        pending = sum(1 for m in ev_matches if m.get("status") == "pending")
        accepted = sum(1 for m in ev_matches if m.get("status") == "accepted")
        fb_list = []
        for m in ev_matches:
            for fb in (m.get("match_feedback") or []):
                fb_list.append(fb.get("feedback_type"))
        fb_good = fb_list.count("good")
        fb_bad = fb_list.count("bad")

        html = f"""<div class="detail">
<div class="detail-grid">
  <div class="field"><div class="field-label">Name</div><div class="field-value">{_esc(ev.get('name'))}</div></div>
  <div class="field"><div class="field-label">Code</div><div class="field-value"><code>{_esc(ev.get('code'))}</code></div></div>
  <div class="field"><div class="field-label">Location</div><div class="field-value">{_esc(ev.get('location') or '—')}</div></div>
  <div class="field"><div class="field-label">Date</div><div class="field-value">{_fmt_dt(ev.get('event_date'))}</div></div>
</div>

<h3 style="margin-top:14px;color:#8b949e">Participants ({len(parts)})</h3>
<table>
<tr><th>Name</th><th>Username</th><th>City</th></tr>
{part_rows if part_rows else '<tr><td colspan="3" class="muted">No participants</td></tr>'}
</table>

<h3 style="margin-top:14px;color:#8b949e">Match Stats</h3>
<div class="row"><span>Total matches</span><span>{total_m}</span></div>
<div class="row"><span>Avg score</span><span>{avg_score}</span></div>
<div class="row"><span>Pending / Accepted</span><span>{pending} / {accepted}</span></div>
<div class="row"><span>Feedback</span><span>{fb_good} good / {fb_bad} bad</span></div>
</div>"""
        return web.Response(text=html, content_type="text/html")

    # === MATCHES TAB ===
    async def handle_matches(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)

        # Filters
        event_filter = request.query.get("event", "")
        min_score = request.query.get("min_score", "")
        status_filter = request.query.get("status", "")
        range_key, cutoff = _parse_range(request)

        try:
            from infrastructure.database.supabase_client import supabase, run_sync

            # Get ALL matches for analytics (unfiltered)
            @run_sync
            def _get_all_matches():
                resp = supabase.table("matches").select("id, compatibility_score, status, user_a_id, user_b_id, created_at").order("created_at", desc=True).execute()
                return resp.data or []
            all_matches_raw = await _get_all_matches()

            # Apply date cutoff to analytics
            analytics_matches = all_matches_raw
            if cutoff:
                analytics_matches = [m for m in all_matches_raw
                                     if _parse_dt(m.get("created_at")) and _parse_dt(m.get("created_at")) >= cutoff]

            # Filtered matches for the table
            @run_sync
            def _get_matches():
                q = supabase.table("matches").select("*").order("created_at", desc=True).limit(200)
                if event_filter:
                    q = q.eq("event_id", event_filter)
                if min_score:
                    try:
                        q = q.gte("compatibility_score", float(min_score))
                    except ValueError:
                        pass
                if status_filter:
                    q = q.eq("status", status_filter)
                resp = q.execute()
                return resp.data or []
            matches = await _get_matches()
            if cutoff:
                matches = [m for m in matches
                           if _parse_dt(m.get("created_at")) and _parse_dt(m.get("created_at")) >= cutoff]

            # Get all events for dropdown
            @run_sync
            def _get_events():
                resp = supabase.table("events").select("id, name, code").execute()
                return resp.data or []
            events = await _get_events()

            # Feedback
            @run_sync
            def _get_feedback():
                resp = supabase.table("match_feedback").select("match_id, feedback_type").execute()
                return resp.data or []
            all_feedback = await _get_feedback()

            # Build user lookup
            @run_sync
            def _get_user_names():
                resp = supabase.table("users").select("id, display_name, first_name, username").execute()
                return resp.data or []
            all_users = await _get_user_names()
            user_map = {u["id"]: u for u in all_users}
        except Exception as e:
            logger.error(f"Matches query failed: {e}")
            return web.Response(text=f'<div class="card">DB error: {_esc(str(e))}</div>',
                                content_type="text/html")

        def _user_name(uid):
            u = user_map.get(uid, {})
            return u.get("display_name") or u.get("first_name") or u.get("username") or "?"

        # --- Analytics ---
        a_total = len(analytics_matches)
        a_pending = sum(1 for m in analytics_matches if m.get("status") == "pending")
        a_accepted = sum(1 for m in analytics_matches if m.get("status") == "accepted")
        a_declined = sum(1 for m in analytics_matches if m.get("status") == "declined")
        a_scores = [m["compatibility_score"] for m in analytics_matches if m.get("compatibility_score")]
        a_avg_score = round(sum(a_scores) / len(a_scores), 2) if a_scores else 0

        # Feedback for analytics period
        analytics_match_ids = {m["id"] for m in analytics_matches}
        fb_good = sum(1 for f in all_feedback if f.get("match_id") in analytics_match_ids and f.get("feedback_type") == "good")
        fb_bad = sum(1 for f in all_feedback if f.get("match_id") in analytics_match_ids and f.get("feedback_type") == "bad")
        fb_ratio = f"{round(fb_good / (fb_good + fb_bad) * 100)}%" if (fb_good + fb_bad) > 0 else "—"

        # Score distribution histogram (5 buckets)
        score_buckets = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
        for s in a_scores:
            if s < 0.2:
                score_buckets["0.0-0.2"] += 1
            elif s < 0.4:
                score_buckets["0.2-0.4"] += 1
            elif s < 0.6:
                score_buckets["0.4-0.6"] += 1
            elif s < 0.8:
                score_buckets["0.6-0.8"] += 1
            else:
                score_buckets["0.8-1.0"] += 1

        score_chart = _chart_html(
            "scoreDistChart", "bar",
            list(score_buckets.keys()),
            [{"label": "Matches", "data": list(score_buckets.values()),
              "backgroundColor": ["#da3633", "#9e6a03", "#1f6feb", "#238636", "#2ea043"]}],
            height=200,
        )

        # Matches over time (daily, last 30 days)
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily_matches: dict[str, int] = {}
        for i in range(30):
            d = (today_start - timedelta(days=29 - i)).strftime("%m/%d")
            daily_matches[d] = 0
        for m in all_matches_raw:
            dt = _parse_dt(m.get("created_at"))
            if dt:
                dk = dt.strftime("%m/%d")
                if dk in daily_matches:
                    daily_matches[dk] += 1

        matches_time_chart = _chart_html(
            "matchesTimeChart", "line",
            list(daily_matches.keys()),
            [{"label": "Matches", "data": list(daily_matches.values()),
              "borderColor": "#238636", "backgroundColor": "rgba(35,134,54,0.1)",
              "fill": True, "tension": 0.3}],
            height=200,
        )

        # Top matched users (top 10)
        user_match_counts: dict[str, int] = {}
        for m in analytics_matches:
            for uid in [m.get("user_a_id"), m.get("user_b_id")]:
                if uid:
                    user_match_counts[uid] = user_match_counts.get(uid, 0) + 1
        top_matched = sorted(user_match_counts.items(), key=lambda x: -x[1])[:10]
        top_rows = ""
        for uid, cnt in top_matched:
            top_rows += f'<tr><td>{_esc(_user_name(uid))}</td><td>{cnt}</td></tr>'

        # --- Filters ---
        ev_options = '<option value="">All events</option>'
        for ev in events:
            sel = " selected" if ev["id"] == event_filter else ""
            ev_options += f'<option value="{ev["id"]}"{sel}>{_esc(ev.get("name") or ev.get("code"))}</option>'

        status_options = '<option value="">All</option>'
        for s in ["pending", "accepted", "declined"]:
            sel = " selected" if s == status_filter else ""
            status_options += f'<option value="{s}"{sel}>{s.title()}</option>'

        # Table rows
        rows = ""
        for m in matches:
            mid = m.get("id", "")
            score = m.get("compatibility_score", 0)
            score_color = "badge-green" if score >= 0.6 else ("badge-yellow" if score >= 0.4 else "badge-red")
            rows += (
                f'<tr class="clickable" hx-get="/stats/match/{mid}?token={stats_token}" '
                f'hx-target="#match-detail-{mid}" hx-swap="innerHTML">'
                f'<td>{_esc(_user_name(m.get("user_a_id")))}</td>'
                f'<td>{_esc(_user_name(m.get("user_b_id")))}</td>'
                f'<td><span class="badge {score_color}">{score}</span></td>'
                f'<td>{_esc(m.get("match_type") or "")}</td>'
                f'<td>{_esc(m.get("status") or "pending")}</td>'
                f'<td class="muted">{_fmt_dt(m.get("created_at"))}</td>'
                f'</tr>'
                f'<tr class="expand-row"><td colspan="6" id="match-detail-{mid}"></td></tr>'
            )

        range_picker = _date_range_picker_html(stats_token, "matches", range_key)

        html = f"""
{range_picker}

<div class="grid">
  <div class="card">
    <div class="big">{a_total}</div>
    <div class="label">Total Matches</div>
  </div>
  <div class="card">
    <h3>Status</h3>
    <div class="row"><span>Pending</span><span>{a_pending}</span></div>
    <div class="row"><span>Accepted</span><span>{a_accepted}</span></div>
    <div class="row"><span>Declined</span><span>{a_declined}</span></div>
  </div>
  <div class="card">
    <h3>Quality</h3>
    <div class="row"><span>Avg score</span><span>{a_avg_score}</span></div>
    <div class="row"><span>Feedback</span><span>{fb_good} / {fb_bad}</span></div>
    <div class="row"><span>Positive rate</span><span>{fb_ratio}</span></div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
  <div class="card">
    <h3>Score Distribution</h3>
    {score_chart}
  </div>
  <div class="card">
    <h3>Matches Over Time (30d)</h3>
    {matches_time_chart}
  </div>
</div>

<div class="card">
  <h3>Top Matched Users</h3>
  <table>
    <tr><th>User</th><th>Matches</th></tr>
    {top_rows if top_rows else '<tr><td colspan="2" class="muted">No data</td></tr>'}
  </table>
</div>

<form class="card" style="display:flex;gap:12px;flex-wrap:wrap;align-items:end"
      hx-get="/stats/matches?token={stats_token}" hx-target="#content">
  <input type="hidden" name="range" value="{range_key}">
  <div><label class="muted" style="font-size:.8em">Event</label><br>
    <select name="event" style="width:200px">{ev_options}</select></div>
  <div><label class="muted" style="font-size:.8em">Min Score</label><br>
    <input type="text" name="min_score" value="{_esc(min_score)}" placeholder="0.0" style="width:80px"></div>
  <div><label class="muted" style="font-size:.8em">Status</label><br>
    <select name="status" style="width:120px">{status_options}</select></div>
  <button class="btn btn-sm btn-blue" type="submit">Filter</button>
</form>
<span class="muted">{len(matches)} matches</span>
<div class="card" style="overflow-x:auto;margin-top:8px">
<table>
<tr><th>User A</th><th>User B</th><th>Score</th><th>Type</th><th>Status</th><th>Created</th></tr>
{rows if rows else '<tr><td colspan="6" class="muted">No matches</td></tr>'}
</table>
</div>"""
        return web.Response(text=html, content_type="text/html")

    # === MATCH DETAIL ===
    async def handle_match_detail(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)
        mid = request.match_info["id"]
        try:
            from infrastructure.database.supabase_client import supabase, run_sync
            @run_sync
            def _get_match():
                resp = supabase.table("matches").select("*").eq("id", mid).execute()
                return resp.data[0] if resp.data else None
            m = await _get_match()
        except Exception as e:
            return web.Response(text=f'<div class="detail">Error: {_esc(str(e))}</div>',
                                content_type="text/html")
        if not m:
            return web.Response(text='<div class="detail">Match not found</div>',
                                content_type="text/html")

        html = f"""<div class="detail">
<div class="detail-grid">
  <div class="field"><div class="field-label">Score</div><div class="field-value">{m.get('compatibility_score')}</div></div>
  <div class="field"><div class="field-label">Type</div><div class="field-value">{_esc(m.get('match_type'))}</div></div>
  <div class="field"><div class="field-label">Status</div><div class="field-value">{_esc(m.get('status'))}</div></div>
  <div class="field"><div class="field-label">City</div><div class="field-value">{_esc(m.get('city') or '—')}</div></div>
</div>
<div style="margin-top:10px">
  <div class="field-label">AI Explanation</div>
  <div class="field-value muted" style="white-space:pre-wrap">{_esc(m.get('ai_explanation') or '—')}</div>
</div>
<div style="margin-top:8px">
  <div class="field-label">Icebreaker</div>
  <div class="field-value" style="font-style:italic">{_esc(m.get('icebreaker') or '—')}</div>
</div>
</div>"""
        return web.Response(text=html, content_type="text/html")

    # === BROADCAST TAB ===
    async def handle_broadcast_form(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)

        # Get events for dropdown
        try:
            from infrastructure.database.supabase_client import supabase, run_sync
            @run_sync
            def _get_events():
                resp = supabase.table("events").select("id, name, code").eq("is_active", True).execute()
                return resp.data or []
            events = await _get_events()
        except Exception:
            events = []

        ev_options = ""
        for ev in events:
            ev_options += f'<option value="{ev["id"]}">{_esc(ev.get("name") or ev.get("code"))}</option>'

        html = f"""
<div class="card">
  <h3>Broadcast Message</h3>
  <form hx-post="/stats/broadcast?token={stats_token}" hx-target="#broadcast-result" hx-swap="innerHTML">
    <div style="margin-bottom:12px">
      <label class="muted" style="font-size:.85em">Audience</label><br>
      <label style="margin-right:16px"><input type="radio" name="audience" value="all" checked> All users</label>
      <label style="margin-right:16px"><input type="radio" name="audience" value="onboarded"> Onboarded only</label>
      <label><input type="radio" name="audience" value="event"> Event participants</label>
    </div>
    <div style="margin-bottom:12px">
      <label class="muted" style="font-size:.85em">Event (if audience = event)</label><br>
      <select name="event_id" style="width:300px">
        <option value="">Select event...</option>
        {ev_options}
      </select>
    </div>
    <div style="margin-bottom:12px">
      <label class="muted" style="font-size:.85em">Message (HTML supported)</label><br>
      <textarea name="text" rows="5" placeholder="Your broadcast message..."></textarea>
    </div>
    <button class="btn btn-primary" type="submit"
            hx-confirm="Send this broadcast? This cannot be undone.">
      Send Broadcast</button>
  </form>
</div>
<div id="broadcast-result"></div>"""
        return web.Response(text=html, content_type="text/html")

    # === BROADCAST SEND ===
    async def handle_broadcast_send(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)
        if not bot:
            return web.Response(text='<div class="card toast-msg error">Bot not available</div>',
                                content_type="text/html")

        data = await request.post()
        text = (data.get("text") or "").strip()
        audience = data.get("audience", "all")
        event_id = data.get("event_id", "").strip()

        if not text:
            return web.Response(text='<div class="card toast-msg error">Message is empty</div>',
                                content_type="text/html")

        try:
            from infrastructure.database.supabase_client import supabase, run_sync

            if audience == "event" and event_id:
                @run_sync
                def _get_event_users():
                    resp = supabase.table("event_participants").select("user_id, users(platform_user_id)").eq("event_id", event_id).execute()
                    return resp.data or []
                parts = await _get_event_users()
                platform_ids = [str(p["users"]["platform_user_id"]) for p in parts
                                if p.get("users") and p["users"].get("platform_user_id")]
            elif audience == "onboarded":
                @run_sync
                def _get_onboarded():
                    resp = supabase.table("users").select("platform_user_id").eq("onboarding_completed", True).eq("platform", "telegram").execute()
                    return resp.data or []
                rows = await _get_onboarded()
                platform_ids = [str(r["platform_user_id"]) for r in rows if r.get("platform_user_id")]
            else:
                platform_ids = await user_repo.get_all_platform_ids()

        except Exception as e:
            logger.error(f"Broadcast query failed: {e}")
            return web.Response(text=f'<div class="card toast-msg error">Query error: {_esc(str(e))}</div>',
                                content_type="text/html")

        sent = 0
        failed = 0
        for pid in platform_ids:
            try:
                await bot.send_message(int(pid), text)
                sent += 1
            except Exception as e:
                logger.warning(f"Broadcast to {pid} failed: {e}")
                failed += 1

        html = f"""<div class="card" style="margin-top:12px">
<div class="big" style="font-size:1.4em">{sent}</div>
<div class="label">Messages sent</div>
<div class="row"><span>Failed</span><span>{failed}</span></div>
<div class="row"><span>Total target</span><span>{len(platform_ids)}</span></div>
</div>"""
        return web.Response(text=html, content_type="text/html")

    # === CONVERSATIONS TAB ===
    async def handle_conversations(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)

        if not conv_log_repo:
            return web.Response(
                text='<div class="card muted">Conversation logging not configured</div>',
                content_type="text/html",
            )

        q = request.query.get("q", "").strip()
        search_mode = request.query.get("search_mode", "name")  # "name" or "messages"
        range_key, cutoff = _parse_range(request)

        # Message content search
        if search_mode == "messages" and q:
            try:
                search_results = await conv_log_repo.search_conversations(q, limit=100)
            except Exception as e:
                logger.error(f"Message search failed: {e}")
                search_results = []

            # Build user lookup for search results
            sr_tg_ids = list(set(r["telegram_user_id"] for r in search_results))
            sr_user_map: dict[int, dict] = {}
            if sr_tg_ids:
                try:
                    from infrastructure.database.supabase_client import supabase, run_sync
                    @run_sync
                    def _get_sr_users():
                        resp = supabase.table("users").select("platform_user_id, display_name, first_name, username").eq("platform", "telegram").in_("platform_user_id", [str(t) for t in sr_tg_ids]).execute()
                        return resp.data or []
                    for u in await _get_sr_users():
                        pid = u.get("platform_user_id")
                        if pid:
                            sr_user_map[int(pid)] = u
                except Exception:
                    pass

            sr_rows = ""
            for r in search_results:
                tgid = r["telegram_user_id"]
                info = sr_user_map.get(tgid, {})
                name = info.get("display_name") or info.get("first_name") or str(tgid)
                content = _trunc(r.get("content", ""), 120)
                dt = _fmt_dt(r.get("created_at"))
                sr_rows += (
                    f'<div class="user-list-item" '
                    f'hx-get="/stats/conversation/{tgid}?token={stats_token}" hx-target="#content">'
                    f'<div><div class="name">{_esc(name)}</div>'
                    f'<div class="preview">{content}</div></div>'
                    f'<div class="time">{dt}</div></div>'
                )

            search_toggle = (
                f'<div class="filter-bar" style="margin-top:10px">'
                f'<a class="btn btn-sm" hx-get="/stats/conversations?token={stats_token}&search_mode=name" hx-target="#content">Search by name</a>'
                f'<a class="btn btn-sm btn-blue">Search messages</a></div>'
            )

            html = f"""
{search_toggle}
<div class="search-bar">
  <span class="search-icon">&#128269;</span>
  <input type="search" name="q" placeholder="Search message content..."
         value="{_esc(q)}"
         hx-get="/stats/conversations?token={stats_token}&search_mode=messages"
         hx-trigger="keyup changed delay:400ms"
         hx-target="#content" hx-include="this">
</div>
<span class="muted">{len(search_results)} results</span>
<div class="card" style="padding:0;margin-top:8px">
{sr_rows if sr_rows else '<div class="muted" style="padding:20px;text-align:center">No messages matching "' + _esc(q) + '"</div>'}
</div>"""
            return web.Response(text=html, content_type="text/html")

        # Normal conversations view
        try:
            active_users = await conv_log_repo.get_active_users(limit=80, hours=168)
        except Exception as e:
            logger.error(f"Conversations query failed: {e}")
            return web.Response(
                text=f'<div class="card">DB error: {_esc(str(e))}</div>',
                content_type="text/html",
            )

        # Get message stats for analytics
        msg_stats = []
        if conv_log_repo:
            try:
                msg_stats = await conv_log_repo.get_message_stats(cutoff, limit=10000)
            except Exception as e:
                logger.warning(f"Message stats failed: {e}")

        # Analytics calculations
        total_msgs = len(msg_stats)
        msgs_in = sum(1 for m in msg_stats if m.get("direction") == "in")
        msgs_out = total_msgs - msgs_in
        unique_users = len(set(m.get("telegram_user_id") for m in msg_stats))
        avg_per_user = round(total_msgs / unique_users, 1) if unique_users else 0

        # Message type distribution
        type_counts: dict[str, int] = {}
        for m in msg_stats:
            mt = m.get("message_type", "text")
            type_counts[mt] = type_counts.get(mt, 0) + 1

        type_chart = ""
        if type_counts:
            type_labels = list(type_counts.keys())
            type_data = list(type_counts.values())
            type_colors = ["#1f6feb", "#238636", "#9e6a03", "#da3633", "#8b949e", "#58a6ff"]
            type_chart = _chart_html(
                "msgTypeChart", "doughnut", type_labels,
                [{"data": type_data, "backgroundColor": type_colors[:len(type_labels)]}],
                height=200,
            )

        # Activity heatmap (7 days x 24 hours)
        heatmap_data: dict[tuple[int, int], int] = {}
        for m in msg_stats:
            dt = _parse_dt(m.get("created_at"))
            if dt:
                heatmap_data[(dt.weekday(), dt.hour)] = heatmap_data.get((dt.weekday(), dt.hour), 0) + 1

        max_heat = max(heatmap_data.values()) if heatmap_data else 1
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        heatmap_html = '<div class="heatmap">'
        # Header row
        heatmap_html += '<div class="heatmap-label"></div>'
        for h in range(24):
            heatmap_html += f'<div class="heatmap-header">{h}</div>'
        # Data rows
        for d in range(7):
            heatmap_html += f'<div class="heatmap-label">{day_names[d]}</div>'
            for h in range(24):
                val = heatmap_data.get((d, h), 0)
                intensity = round(val / max_heat * 0.9, 2) if max_heat else 0
                bg = f"rgba(31,111,235,{intensity})" if val > 0 else "#161b22"
                heatmap_html += f'<div class="heatmap-cell" style="background:{bg}" title="{day_names[d]} {h}:00 — {val} msgs">{val if val else ""}</div>'
        heatmap_html += '</div>'

        # Build user-info lookup
        tg_ids = [u["telegram_user_id"] for u in active_users]
        user_map: dict[int, dict] = {}
        if tg_ids:
            try:
                from infrastructure.database.supabase_client import supabase, run_sync

                tg_id_strs = [str(t) for t in tg_ids]

                @run_sync
                def _get_user_info():
                    resp = (
                        supabase.table("users")
                        .select("platform_user_id, display_name, first_name, username")
                        .eq("platform", "telegram")
                        .in_("platform_user_id", tg_id_strs)
                        .execute()
                    )
                    return resp.data or []

                for u in await _get_user_info():
                    pid = u.get("platform_user_id")
                    if pid:
                        user_map[int(pid)] = u
            except Exception:
                pass

        user_rows = ""
        for au in active_users:
            tgid = au["telegram_user_id"]
            info = user_map.get(tgid, {})
            name = info.get("display_name") or info.get("first_name") or str(tgid)
            uname = info.get("username") or ""
            count = au.get("message_count", "")
            last = _fmt_dt(au.get("last_active"))

            if q and q.lower() not in f"{name} {uname} {tgid}".lower():
                continue

            user_rows += (
                f'<div class="user-list-item" '
                f'hx-get="/stats/conversation/{tgid}?token={stats_token}" '
                f'hx-target="#content">'
                f'<div><div class="name">{_esc(name)}'
                f'{(" (@" + _esc(uname) + ")") if uname else ""}</div>'
                f'<div class="preview">{count} messages</div></div>'
                f'<div class="time">{last}</div>'
                f'</div>'
            )

        range_picker = _date_range_picker_html(stats_token, "conversations", range_key)
        search_toggle = (
            f'<div class="filter-bar" style="margin-top:10px">'
            f'<a class="btn btn-sm btn-blue">Search by name</a>'
            f'<a class="btn btn-sm" hx-get="/stats/conversations?token={stats_token}&search_mode=messages" hx-target="#content">Search messages</a></div>'
        )

        html = f"""
{range_picker}

<div class="grid">
  <div class="card">
    <div class="big">{total_msgs}</div>
    <div class="label">Total Messages</div>
    <div class="row"><span>In</span><span>{msgs_in}</span></div>
    <div class="row"><span>Out</span><span>{msgs_out}</span></div>
  </div>
  <div class="card">
    <h3>Users</h3>
    <div class="row"><span>Unique users</span><span>{unique_users}</span></div>
    <div class="row"><span>Avg per user</span><span>{avg_per_user}</span></div>
  </div>
  <div class="card">
    <h3>Message Types</h3>
    {type_chart if type_chart else '<span class="muted">No data</span>'}
  </div>
</div>

<div class="card">
  <h3>Activity Heatmap (by day/hour)</h3>
  {heatmap_html}
</div>

{search_toggle}
<div class="search-bar">
  <span class="search-icon">&#128269;</span>
  <input type="search" name="q" placeholder="Search by name, username, or TG ID..."
         value="{_esc(q)}"
         hx-get="/stats/conversations?token={stats_token}&range={range_key}"
         hx-trigger="keyup changed delay:300ms"
         hx-target="#content"
         hx-include="this">
</div>
<div class="card" style="padding:0">
{user_rows if user_rows else ('<div class="muted" style="padding:20px;text-align:center">No results for "' + _esc(q) + '"</div>' if q else '<div class="muted" style="padding:20px;text-align:center">No conversations yet</div>')}
</div>"""
        return web.Response(text=html, content_type="text/html")

    # === SINGLE USER CONVERSATION ===
    async def handle_user_conversation(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)

        if not conv_log_repo:
            return web.Response(
                text='<div class="card muted">Not configured</div>',
                content_type="text/html",
            )

        tgid = int(request.match_info["tgid"])
        page = int(request.query.get("page", "0"))
        per_page = 150

        # Fetch messages
        try:
            messages = await conv_log_repo.get_user_conversation(
                tgid, limit=per_page, offset=page * per_page
            )
            total = await conv_log_repo.get_message_count(tgid)
        except Exception as e:
            logger.error(f"Conversation fetch failed: {e}")
            return web.Response(
                text=f'<div class="card">Error: {_esc(str(e))}</div>',
                content_type="text/html",
            )

        # User info
        user_name = str(tgid)
        try:
            from infrastructure.database.supabase_client import supabase, run_sync

            @run_sync
            def _get_name():
                resp = (
                    supabase.table("users")
                    .select("display_name, first_name, username")
                    .eq("platform_user_id", str(tgid))
                    .execute()
                )
                return resp.data[0] if resp.data else None

            info = await _get_name()
            if info:
                user_name = info.get("display_name") or info.get("first_name") or str(tgid)
                uname = info.get("username")
                if uname:
                    user_name += f" (@{uname})"
        except Exception:
            pass

        # Build chat bubbles
        bubbles = ""
        last_date = ""
        for msg in messages:
            dt = _parse_dt(msg.get("created_at"))
            if dt:
                date_str = dt.strftime("%Y-%m-%d")
                if date_str != last_date:
                    bubbles += f'<div class="chat-date-sep">{date_str}</div>'
                    last_date = date_str
                time_str = dt.strftime("%H:%M:%S")
            else:
                time_str = ""

            direction = msg.get("direction", "in")
            msg_type = msg.get("message_type", "text")
            content = msg.get("content") or ""
            callback_data = msg.get("callback_data")
            api_method = msg.get("api_method")
            fsm_state = msg.get("fsm_state")
            has_media = msg.get("has_media", False)

            if direction == "in" and msg_type == "callback":
                bubbles += (
                    f'<div class="chat-bubble callback">'
                    f'[button] {_esc(callback_data or "?")}'
                    f'<div class="meta">{time_str}'
                    f'{(" | state: " + _esc(fsm_state)) if fsm_state else ""}</div>'
                    f'</div>'
                )
            elif direction == "in":
                type_badge = ""
                if msg_type != "text":
                    type_badge = f'<span class="badge badge-blue" style="font-size:.7em;margin-right:4px">{_esc(msg_type)}</span>'
                bubbles += (
                    f'<div class="chat-bubble incoming">'
                    f'{type_badge}{_esc(content)}'
                    f'<div class="meta">{time_str}'
                    f'{(" | state: " + _esc(fsm_state)) if fsm_state else ""}</div>'
                    f'</div>'
                )
            else:  # out
                method_hint = ""
                if api_method and api_method != "SendMessage":
                    method_hint = f'<span class="badge badge-green" style="font-size:.7em;margin-right:4px">{_esc(api_method)}</span>'
                bubbles += (
                    f'<div class="chat-bubble outgoing">'
                    f'{method_hint}{_esc(content)}'
                    f'{"[media]" if has_media and not content else ""}'
                    f'<div class="meta">{time_str}</div>'
                    f'</div>'
                )

        # Pagination
        total_pages = max(1, (total + per_page - 1) // per_page) if total else 0
        pagination = ""
        if total_pages > 1:
            parts = []
            if page > 0:
                parts.append(
                    f'<a class="btn btn-sm" hx-get="/stats/conversation/{tgid}?token={stats_token}&page={page - 1}" '
                    f'hx-target="#content">Newer</a>'
                )
            parts.append(f'<span class="muted">Page {page + 1}/{total_pages} ({total} msgs)</span>')
            if page < total_pages - 1:
                parts.append(
                    f'<a class="btn btn-sm" hx-get="/stats/conversation/{tgid}?token={stats_token}&page={page + 1}" '
                    f'hx-target="#content">Older</a>'
                )
            pagination = '<div style="display:flex;gap:8px;align-items:center;justify-content:center;margin-top:10px">' + "".join(parts) + "</div>"

        html = f"""
<div class="card" style="padding:0">
  <div class="chat-header">
    <div>
      <a class="btn btn-sm" hx-get="/stats/conversations?token={stats_token}" hx-target="#content"
         onclick="document.querySelectorAll('.nav a').forEach(a=>a.classList.remove('active'));
                  document.querySelectorAll('.nav a')[5].classList.add('active')">
        Back</a>
      <strong style="margin-left:8px">{_esc(user_name)}</strong>
      <span class="muted" style="margin-left:8px">TG: {tgid}</span>
    </div>
    <span class="muted">{total} messages</span>
  </div>
  <div class="chat-container">
    {bubbles if bubbles else '<div class="muted" style="padding:20px;text-align:center">No messages</div>'}
  </div>
  {pagination}
</div>"""
        return web.Response(text=html, content_type="text/html")

    # === ONBOARDING TAB ===
    async def handle_onboarding(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)

        range_key, cutoff = _parse_range(request)

        try:
            users = await user_repo.get_all_users_full()
        except Exception as e:
            logger.error(f"Onboarding query failed: {e}")
            return web.Response(text=f'<div class="card">DB error: {_esc(str(e))}</div>',
                                content_type="text/html")

        if cutoff:
            users = [u for u in users if _parse_dt(u.get("created_at")) and _parse_dt(u.get("created_at")) >= cutoff]

        total = len(users)
        onboarded = sum(1 for u in users if u.get("onboarding_completed"))
        not_onboarded = total - onboarded

        # FSM state funnel from conversation logs
        fsm_state_counts: dict[str, int] = {}
        fsm_logs: list[dict] = []
        if conv_log_repo:
            try:
                fsm_logs = await conv_log_repo.get_fsm_state_logs(limit=10000)
                if cutoff:
                    fsm_logs = [l for l in fsm_logs if _parse_dt(l.get("created_at")) and _parse_dt(l.get("created_at")) >= cutoff]

                # Count distinct users per FSM state
                state_users: dict[str, set] = {}
                for log in fsm_logs:
                    state = log.get("fsm_state")
                    uid = log.get("telegram_user_id")
                    if state and uid:
                        state_users.setdefault(state, set()).add(uid)
                fsm_state_counts = {s: len(uids) for s, uids in state_users.items()}
            except Exception as e:
                logger.warning(f"FSM state query failed: {e}")

        # Build FSM funnel — ordered by common onboarding flow
        onboarding_states_order = [
            "IntentOnboarding:choosing_intents",
            "IntentOnboarding:choosing_mode",
            "AgentOnboarding:chatting",
            "AgentOnboarding:confirming",
            "IntentOnboarding:choosing_city",
            "IntentOnboarding:requesting_photo",
            "IntentOnboarding:confirming_profile",
        ]
        # Also include any states not in the predefined order
        all_states = list(fsm_state_counts.keys())
        ordered_states = [s for s in onboarding_states_order if s in fsm_state_counts]
        remaining_states = [s for s in all_states if s not in ordered_states]
        ordered_states.extend(sorted(remaining_states))

        fsm_funnel_steps = [(s.split(":")[-1] if ":" in s else s, fsm_state_counts[s])
                            for s in ordered_states if fsm_state_counts.get(s, 0) > 0]

        # Onboarding mode distribution — infer from FSM states
        mode_counts = {"agent": 0, "voice": 0, "quick": 0, "social": 0}
        if conv_log_repo:
            try:
                # Count users per mode based on FSM state prefixes
                mode_state_map = {
                    "AgentOnboarding": "agent",
                    "VoiceOnboarding": "voice",
                    "QuickOnboarding": "quick",
                    "SocialOnboarding": "social",
                }
                mode_users: dict[str, set] = {}
                for log in fsm_logs:
                    state = log.get("fsm_state") or ""
                    uid = log.get("telegram_user_id")
                    prefix = state.split(":")[0] if ":" in state else state
                    mode = mode_state_map.get(prefix)
                    if mode and uid:
                        mode_users.setdefault(mode, set()).add(uid)
                mode_counts = {m: len(mode_users.get(m, set())) for m in mode_counts}
            except Exception:
                pass

        mode_labels = [k for k, v in mode_counts.items() if v > 0]
        mode_data = [v for v in mode_counts.values() if v > 0]
        mode_chart = ""
        if mode_labels:
            mode_chart = _chart_html(
                "modeChart", "doughnut", mode_labels,
                [{"data": mode_data,
                  "backgroundColor": ["#1f6feb", "#238636", "#9e6a03", "#da3633"]}],
                height=220,
            )

        # Avg onboarding duration
        avg_duration = "—"
        if conv_log_repo and onboarded > 0:
            try:
                # Estimate: time from first log to last log before onboarding_completed
                durations = []
                for u in users:
                    if not u.get("onboarding_completed"):
                        continue
                    created = _parse_dt(u.get("created_at"))
                    updated = _parse_dt(u.get("updated_at"))
                    if created and updated and updated > created:
                        dur = (updated - created).total_seconds()
                        if dur < 86400:  # Ignore > 24h as likely not a single session
                            durations.append(dur)
                if durations:
                    avg_secs = sum(durations) / len(durations)
                    if avg_secs < 60:
                        avg_duration = f"{round(avg_secs)}s"
                    elif avg_secs < 3600:
                        avg_duration = f"{round(avg_secs / 60)}m"
                    else:
                        avg_duration = f"{round(avg_secs / 3600, 1)}h"
            except Exception:
                pass

        # Profile completeness histogram
        profile_fields = ["bio", "interests", "goals", "looking_for", "can_help_with",
                          "photo_url", "profession", "city_current", "connection_intents", "skills"]
        completeness_buckets = {"0-20%": 0, "20-40%": 0, "40-60%": 0, "60-80%": 0, "80-100%": 0}
        for u in users:
            filled = sum(1 for f in profile_fields if u.get(f))
            pct = filled / len(profile_fields) * 100
            if pct < 20:
                completeness_buckets["0-20%"] += 1
            elif pct < 40:
                completeness_buckets["20-40%"] += 1
            elif pct < 60:
                completeness_buckets["40-60%"] += 1
            elif pct < 80:
                completeness_buckets["60-80%"] += 1
            else:
                completeness_buckets["80-100%"] += 1

        completeness_chart = _chart_html(
            "completenessChart", "bar",
            list(completeness_buckets.keys()),
            [{"label": "Users", "data": list(completeness_buckets.values()),
              "backgroundColor": "#1f6feb"}],
            height=200,
        )

        range_picker = _date_range_picker_html(stats_token, "onboarding", range_key)
        onb_pct = round(onboarded / total * 100) if total else 0

        html = f"""
{range_picker}

<div class="grid">
  <div class="card">
    <div class="big">{onboarded}<span style="font-size:.4em;color:#8b949e"> / {total}</span></div>
    <div class="label">Onboarded ({onb_pct}%)</div>
    <div class="row"><span>In progress</span><span>{not_onboarded}</span></div>
  </div>
  <div class="card">
    <h3>Avg Duration</h3>
    <div class="big" style="font-size:1.8em">{avg_duration}</div>
    <div class="label">signup to complete</div>
  </div>
  <div class="card">
    <h3>Onboarding Mode</h3>
    {mode_chart if mode_chart else '<span class="muted">No mode data</span>'}
  </div>
</div>

<div class="card">
  <h3>FSM State Funnel (where users drop off)</h3>
  {_funnel_html(fsm_funnel_steps) if fsm_funnel_steps else '<span class="muted">No FSM state data — enable conversation logging</span>'}
</div>

<div class="card">
  <h3>Profile Completeness Distribution</h3>
  {completeness_chart}
</div>"""
        return web.Response(text=html, content_type="text/html")

    # === CSV EXPORT ===
    async def handle_export_users(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)
        try:
            users = await user_repo.get_all_users_full()
        except Exception as e:
            return web.Response(text=f"Export failed: {e}", status=500)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["name", "username", "city", "profession", "intents", "bio", "onboarded", "created_at"])
        for u in users:
            writer.writerow([
                u.get("display_name") or u.get("first_name") or "",
                u.get("username") or "",
                u.get("city_current") or "",
                u.get("profession") or "",
                _list_to_str(u.get("connection_intents")),
                (u.get("bio") or "")[:200],
                "yes" if u.get("onboarding_completed") else "no",
                u.get("created_at") or "",
            ])

        return web.Response(
            text=output.getvalue(),
            content_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=sphere_users.csv"},
        )

    # === COMMUNITIES TAB ===
    async def handle_communities(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)

        try:
            from infrastructure.database.supabase_client import supabase, run_sync

            @run_sync
            def _get_communities():
                resp = supabase.table("communities").select("*").order("created_at", desc=True).execute()
                return resp.data or []

            @run_sync
            def _get_member_counts():
                resp = supabase.table("community_members").select("community_id").execute()
                return resp.data or []

            @run_sync
            def _get_match_counts():
                resp = supabase.table("matches").select("id, community_id").not_.is_("community_id", "null").execute()
                return resp.data or []

            communities = await _get_communities()
            members_raw = await _get_member_counts()
            matches_raw = await _get_match_counts()
        except Exception as e:
            logger.error(f"Communities query failed: {e}")
            return web.Response(text=f'<div class="card">DB error: {_esc(str(e))}</div>',
                                content_type="text/html")

        # Count members per community
        member_counts: dict[str, int] = {}
        for m in members_raw:
            cid = m.get("community_id")
            member_counts[cid] = member_counts.get(cid, 0) + 1

        match_counts: dict[str, int] = {}
        for m in matches_raw:
            cid = m.get("community_id")
            if cid:
                match_counts[cid] = match_counts.get(cid, 0) + 1

        rows = ""
        for c in communities:
            cid = c.get("id", "")
            active_badge = ('<span class="badge badge-green">Active</span>'
                            if c.get("is_active", True)
                            else '<span class="badge badge-red">Inactive</span>')
            m_count = member_counts.get(cid, 0)
            mtch_count = match_counts.get(cid, 0)
            settings = c.get("settings") or {}
            reminder = "On" if settings.get("reminder_enabled", True) else "Off"
            rows += (
                f'<tr class="clickable" hx-get="/stats/community/{cid}?token={stats_token}" '
                f'hx-target="#comm-detail-{cid}" hx-swap="innerHTML">'
                f'<td>{_esc(c.get("name") or "—")}</td>'
                f'<td><code>{_esc(str(c.get("telegram_group_id") or ""))}</code></td>'
                f'<td>{m_count}</td>'
                f'<td>{mtch_count}</td>'
                f'<td>{reminder}</td>'
                f'<td>{active_badge}</td>'
                f'<td class="muted">{_fmt_dt(c.get("created_at"))}</td>'
                f'</tr>'
                f'<tr class="expand-row"><td colspan="7" id="comm-detail-{cid}"></td></tr>'
            )

        total = len(communities)
        active = sum(1 for c in communities if c.get("is_active", True))
        total_members = sum(member_counts.values())

        html = f"""
<div class="grid">
  <div class="card"><h3>Communities</h3><div class="big">{total}</div><span class="muted">{active} active</span></div>
  <div class="card"><h3>Total Members</h3><div class="big">{total_members}</div></div>
  <div class="card"><h3>Community Matches</h3><div class="big">{sum(match_counts.values())}</div></div>
</div>
<div class="card" style="overflow-x:auto">
<table>
<tr><th>Name</th><th>Group ID</th><th>Members</th><th>Matches</th><th>Reminders</th><th>Status</th><th>Created</th></tr>
{rows if rows else '<tr><td colspan="7" class="muted">No communities yet</td></tr>'}
</table>
</div>"""
        return web.Response(text=html, content_type="text/html")

    async def handle_community_detail(request: web.Request) -> web.Response:
        if not _check_token(request):
            return web.Response(text="Unauthorized", status=401)

        cid = request.match_info["id"]
        try:
            from infrastructure.database.supabase_client import supabase, run_sync

            @run_sync
            def _get_community():
                resp = supabase.table("communities").select("*").eq("id", cid).execute()
                return resp.data[0] if resp.data else None

            @run_sync
            def _get_members():
                resp = supabase.table("community_members").select("*, users(id, display_name, username, onboarding_completed, created_at)")\
                    .eq("community_id", cid).order("joined_at", desc=True).execute()
                return resp.data or []

            @run_sync
            def _get_matches():
                resp = supabase.table("matches").select("id, compatibility_score, created_at, user_a_id, user_b_id")\
                    .eq("community_id", cid).order("created_at", desc=True).execute()
                return resp.data or []

            @run_sync
            def _get_game_sessions():
                resp = supabase.table("game_sessions").select("id, game_type, status, created_at")\
                    .eq("community_id", cid).order("created_at", desc=True).limit(100).execute()
                return resp.data or []

            @run_sync
            def _get_game_responses(session_ids):
                if not session_ids:
                    return []
                resp = supabase.table("game_responses").select("game_session_id, user_id")\
                    .in_("game_session_id", session_ids).execute()
                return resp.data or []

            @run_sync
            def _get_observations():
                cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
                resp = supabase.table("message_observations").select("topics, sentiment, user_id, created_at")\
                    .eq("community_id", cid).gte("created_at", cutoff).execute()
                return resp.data or []

            community = await _get_community()
            members = await _get_members()
            matches = await _get_matches()
            game_sessions = await _get_game_sessions()
            session_ids = [g["id"] for g in game_sessions]
            game_responses = await _get_game_responses(session_ids)
            observations = await _get_observations()
        except Exception as e:
            logger.error(f"Community detail query failed: {e}")
            return web.Response(text=f'<div class="detail">DB error: {_esc(str(e))}</div>',
                                content_type="text/html")

        if not community:
            return web.Response(text='<div class="detail muted">Community not found</div>',
                                content_type="text/html")

        settings = community.get("settings") or {}
        total_members = len(members)
        onboarded = sum(1 for m in members if m.get("is_onboarded"))
        admins = sum(1 for m in members if m.get("role") == "admin")

        # ---- Source attribution breakdown ----
        source_counts: dict = {}
        for m in members:
            src = m.get("joined_via") or "unknown"
            source_counts[src] = source_counts.get(src, 0) + 1

        source_bars = ""
        source_colors = {"deep_link": "#1f6feb", "auto_detected": "#238636", "referral": "#a371f7",
                         "tg_admin_sync": "#f0883e", "post_onboarding": "#58a6ff", "unknown": "#484f58"}
        for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
            pct = round(count / total_members * 100) if total_members else 0
            color = source_colors.get(src, "#484f58")
            source_bars += (
                f'<div class="funnel-step">'
                f'<div class="funnel-bar" style="width:{max(pct, 8)}%;background:{color}">{count}</div>'
                f'<span class="funnel-label">{_esc(src)} ({pct}%)</span>'
                f'</div>'
            )

        # ---- Onboarding funnel ----
        matched_user_ids = set()
        for m in matches:
            matched_user_ids.add(m.get("user_a_id"))
            matched_user_ids.add(m.get("user_b_id"))
        member_user_ids = {m.get("user_id") for m in members}
        matched_in_community = len(matched_user_ids & member_user_ids)

        funnel_steps = [
            ("Joined group", total_members, "#58a6ff"),
            ("Onboarded", onboarded, "#1f6feb"),
            ("Got matched", matched_in_community, "#238636"),
        ]
        funnel_html = ""
        for label, count, color in funnel_steps:
            pct = round(count / total_members * 100) if total_members else 0
            funnel_html += (
                f'<div class="funnel-step">'
                f'<div class="funnel-bar" style="width:{max(pct, 8)}%;background:{color}">{count}</div>'
                f'<span class="funnel-label">{label} ({pct}%)</span>'
                f'</div>'
            )

        # ---- Member growth (last 14 days) ----
        now = datetime.now(timezone.utc)
        day_counts = {}
        for i in range(13, -1, -1):
            day = (now - timedelta(days=i)).strftime("%m/%d")
            day_counts[day] = 0

        for m in members:
            dt = _parse_dt(m.get("joined_at"))
            if dt:
                day_key = dt.strftime("%m/%d")
                if day_key in day_counts:
                    day_counts[day_key] += 1

        growth_labels = json.dumps(list(day_counts.keys()))
        growth_data = json.dumps(list(day_counts.values()))
        chart_id = f"growth_{cid[:8]}"

        # ---- Game engagement ----
        total_games = len(game_sessions)
        game_type_counts: dict = {}
        for g in game_sessions:
            gt = g.get("game_type", "unknown")
            game_type_counts[gt] = game_type_counts.get(gt, 0) + 1

        # Participation: unique users who responded
        unique_participants = set()
        responses_per_session: dict = {}
        for r in game_responses:
            unique_participants.add(r.get("user_id"))
            sid = r.get("game_session_id")
            responses_per_session[sid] = responses_per_session.get(sid, 0) + 1

        avg_participation = (round(sum(responses_per_session.values()) / len(responses_per_session), 1)
                             if responses_per_session else 0)
        most_popular_game = max(game_type_counts, key=game_type_counts.get) if game_type_counts else "—"

        game_rows = ""
        for gt, cnt in sorted(game_type_counts.items(), key=lambda x: -x[1]):
            game_rows += f'<tr><td>{_esc(gt)}</td><td>{cnt}</td></tr>'

        # ---- Matching stats ----
        match_count = len(matches)
        avg_score = (round(sum(m.get("compatibility_score", 0) or 0 for m in matches) / match_count, 2)
                     if match_count else 0)

        # ---- Observation topics (last 30 days) ----
        topic_counts: dict = {}
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        obs_user_ids = set()
        for obs in observations:
            for t in (obs.get("topics") or []):
                topic_counts[t] = topic_counts.get(t, 0) + 1
            s = obs.get("sentiment", "neutral")
            sentiment_counts[s] = sentiment_counts.get(s, 0) + 1
            obs_user_ids.add(obs.get("user_id"))

        top_topics = sorted(topic_counts.items(), key=lambda x: -x[1])[:10]
        topic_tags = " ".join(
            f'<span class="badge badge-blue" style="margin:2px">#{_esc(t)} ({c})</span>'
            for t, c in top_topics
        ) if top_topics else '<span class="muted">No topics yet</span>'

        obs_total = len(observations)
        obs_pos = sentiment_counts["positive"]
        obs_neg = sentiment_counts["negative"]
        obs_neu = sentiment_counts["neutral"]

        # ---- Member rows ----
        member_rows = ""
        for m in members[:50]:
            user = m.get("users") or {}
            role_badge = '<span class="badge badge-blue">Admin</span>' if m.get("role") == "admin" else ""
            onboard_badge = ('<span class="badge badge-green">Onboarded</span>'
                             if m.get("is_onboarded") else
                             '<span class="badge badge-yellow">Pending</span>')
            member_rows += (
                f'<tr>'
                f'<td>{_esc(user.get("display_name") or user.get("username") or "—")}</td>'
                f'<td>{role_badge}</td>'
                f'<td>{onboard_badge}</td>'
                f'<td class="muted">{_esc(m.get("joined_via") or "—")}</td>'
                f'<td class="muted">{_fmt_dt(m.get("joined_at"))}</td>'
                f'</tr>'
            )

        # Settings display
        games = settings.get("games_enabled", [])
        games_str = ", ".join(games) if games else "all (default)"

        html = f"""
<div class="detail">
  <h3 style="margin-bottom:12px;font-size:1.1em;color:#e6edf3">{_esc(community.get("name") or "Community")}</h3>

  <!-- Summary cards -->
  <div class="grid" style="margin-bottom:14px">
    <div class="card"><h3>Members</h3><div class="big">{total_members}</div><span class="muted">{onboarded} onboarded, {admins} admins</span></div>
    <div class="card"><h3>Matches</h3><div class="big">{match_count}</div><span class="muted">avg score: {avg_score}</span></div>
    <div class="card"><h3>Games Played</h3><div class="big">{total_games}</div><span class="muted">{len(unique_participants)} participants, ~{avg_participation}/game</span></div>
    <div class="card"><h3>Messages Analyzed</h3><div class="big">{obs_total}</div><span class="muted">{len(obs_user_ids)} active users (30d)</span></div>
  </div>

  <!-- Growth chart + Funnel side by side -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px">
    <div class="card">
      <h3>Member Growth (14 days)</h3>
      <div class="chart-container" style="height:160px">
        <canvas id="{chart_id}"></canvas>
      </div>
      <script>
        (function() {{
          var ctx = document.getElementById('{chart_id}');
          if (ctx) new Chart(ctx, {{
            type: 'bar',
            data: {{
              labels: {growth_labels},
              datasets: [{{ data: {growth_data}, backgroundColor: '#1f6feb', borderRadius: 3 }}]
            }},
            options: {{
              responsive: true, maintainAspectRatio: false,
              plugins: {{ legend: {{ display: false }} }},
              scales: {{
                x: {{ ticks: {{ color: '#8b949e', font: {{ size: 10 }} }}, grid: {{ display: false }} }},
                y: {{ ticks: {{ color: '#8b949e', stepSize: 1 }}, grid: {{ color: '#21262d' }},
                     beginAtZero: true }}
              }}
            }}
          }});
        }})();
      </script>
    </div>
    <div class="card">
      <h3>Onboarding Funnel</h3>
      <div class="funnel-container" style="margin-top:8px">{funnel_html}</div>
      <h3 style="margin-top:14px">Source Attribution</h3>
      <div class="funnel-container" style="margin-top:8px">{source_bars if source_bars else '<span class="muted">No data</span>'}</div>
    </div>
  </div>

  <!-- Game engagement + Topics -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px">
    <div class="card">
      <h3>Game Engagement</h3>
      {f'<table><tr><th>Game Type</th><th>Played</th></tr>{game_rows}</table>' if game_rows else '<span class="muted">No games yet</span>'}
      <div style="margin-top:8px"><span class="muted">Most popular: <b>{_esc(most_popular_game)}</b></span></div>
    </div>
    <div class="card">
      <h3>Community Topics (30d)</h3>
      <div style="margin:8px 0;line-height:1.8">{topic_tags}</div>
      <div style="margin-top:10px">
        <span class="badge badge-green">+{obs_pos}</span>
        <span class="badge" style="background:#484f58;color:#e6edf3">{obs_neu} neutral</span>
        <span class="badge badge-red">-{obs_neg}</span>
      </div>
    </div>
  </div>

  <!-- Settings -->
  <div class="card" style="margin-bottom:14px">
    <h3>Settings</h3>
    <div class="detail-grid">
      <div class="field"><div class="field-label">Group ID</div><div class="field-value"><code>{community.get("telegram_group_id")}</code></div></div>
      <div class="field"><div class="field-label">Status</div><div class="field-value">{"Active" if community.get("is_active") else "Inactive"}</div></div>
      <div class="field"><div class="field-label">Reminders</div><div class="field-value">{"Enabled" if settings.get("reminder_enabled", True) else "Disabled"} (every {settings.get("reminder_hours", 48)}h)</div></div>
      <div class="field"><div class="field-label">Games</div><div class="field-value">{_esc(games_str)}</div></div>
      <div class="field"><div class="field-label">Cross-community</div><div class="field-value">{"Yes" if settings.get("cross_community_matching", True) else "No"} (max {settings.get("max_free_cross_matches", 1)} free)</div></div>
      <div class="field"><div class="field-label">Created</div><div class="field-value">{_fmt_dt(community.get("created_at"))}</div></div>
    </div>
  </div>

  <!-- Members table -->
  <div class="card">
    <h3>Members ({total_members})</h3>
    <table>
    <tr><th>Name</th><th>Role</th><th>Status</th><th>Joined via</th><th>Joined</th></tr>
    {member_rows if member_rows else '<tr><td colspan="5" class="muted">No members</td></tr>'}
    </table>
    {f'<div class="muted" style="margin-top:8px">Showing first 50 of {total_members}</div>' if total_members > 50 else ''}
  </div>
</div>"""
        return web.Response(text=html, content_type="text/html")

    # === ROUTES ===
    app = web.Application()
    app.router.add_get("/stats", handle_shell)
    app.router.add_get("/stats/overview", handle_overview)
    app.router.add_get("/stats/users", handle_users)
    app.router.add_get("/stats/user/{id}", handle_user_detail)
    app.router.add_post("/stats/user/{id}/edit", handle_user_edit)
    app.router.add_post("/stats/user/{id}/reset", handle_user_reset)
    app.router.add_post("/stats/user/{id}/dm", handle_user_dm)
    app.router.add_post("/stats/user/{id}/toggle", handle_user_toggle)
    app.router.add_get("/stats/onboarding", handle_onboarding)
    app.router.add_get("/stats/events", handle_events)
    app.router.add_get("/stats/event/{id}", handle_event_detail)
    app.router.add_get("/stats/matches", handle_matches)
    app.router.add_get("/stats/match/{id}", handle_match_detail)
    app.router.add_get("/stats/conversations", handle_conversations)
    app.router.add_get("/stats/conversation/{tgid}", handle_user_conversation)
    app.router.add_get("/stats/broadcast", handle_broadcast_form)
    app.router.add_post("/stats/broadcast", handle_broadcast_send)
    app.router.add_get("/stats/export/users", handle_export_users)
    app.router.add_get("/stats/communities", handle_communities)
    app.router.add_get("/stats/community/{id}", handle_community_detail)
    return app
