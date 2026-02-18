"""
Admin dashboard — aiohttp + HTMX.
Access: GET /stats?token=SECRET
"""

import csv
import io
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

/* responsive */
@media (max-width: 700px) {
  .detail-grid { grid-template-columns: 1fr; }
  .grid { grid-template-columns: 1fr; }
  .nav { gap: 2px; }
  .nav a { padding: 5px 10px; font-size: .82em; }
  .chat-bubble { max-width: 90%; }
  .user-list-item .preview { max-width: 200px; }
}
"""


def _shell_html(token: str, active_tab: str = "overview") -> str:
    """Full HTML shell with nav. Content loaded by HTMX."""
    tabs = [
        ("overview", "Overview"),
        ("users", "Users"),
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
        try:
            users = await user_repo.get_all_users_full()
        except Exception as e:
            logger.error(f"Overview query failed: {e}")
            return web.Response(text=f'<div class="card">DB error: {_esc(str(e))}</div>',
                                content_type="text/html")

        total = len(users)
        onboarded = sum(1 for u in users if u.get("onboarding_completed"))
        in_progress = total - onboarded
        onboarded_pct = round(onboarded / total * 100) if total else 0

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_ago = today_start - timedelta(days=7)

        new_today = new_yesterday = new_week = 0
        # intent distribution
        intent_counts: dict[str, int] = {}
        # city distribution
        city_counts: dict[str, int] = {}
        # profile completeness
        has_photo = has_bio = has_profession = 0
        # referral funnel
        referrers: dict[str, dict] = {}

        for u in users:
            dt = _parse_dt(u.get("created_at"))
            if dt:
                if dt >= today_start:
                    new_today += 1
                if yesterday_start <= dt < today_start:
                    new_yesterday += 1
                if dt >= week_ago:
                    new_week += 1

            # intents
            for intent in (u.get("connection_intents") or []):
                intent_counts[intent] = intent_counts.get(intent, 0) + 1

            # city
            city = u.get("city_current")
            if city:
                city_counts[city] = city_counts.get(city, 0) + 1

            # completeness
            if u.get("photo_url"):
                has_photo += 1
            if u.get("bio"):
                has_bio += 1
            if u.get("profession"):
                has_profession += 1

            # referrals
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
        if match_repo:
            try:
                from infrastructure.database.supabase_client import supabase, run_sync
                @run_sync
                def _get_match_stats():
                    resp = supabase.table("matches").select("id, compatibility_score").execute()
                    return resp.data or []
                all_matches = await _get_match_stats()
                match_total = len(all_matches)
                if match_total:
                    match_avg_score = round(sum(m["compatibility_score"] for m in all_matches) / match_total, 2)

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

        # Profile completeness
        photo_pct = round(has_photo / total * 100) if total else 0
        bio_pct = round(has_bio / total * 100) if total else 0
        prof_pct = round(has_profession / total * 100) if total else 0

        html = f"""
<div hx-get="/stats/overview?token={stats_token}" hx-trigger="every 30s" hx-target="#content">

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
    <h3>Profile Completeness</h3>
    <div class="row"><span>Has photo</span><span>{has_photo} ({photo_pct}%)</span></div>
    <div class="row"><span>Has bio</span><span>{has_bio} ({bio_pct}%)</span></div>
    <div class="row"><span>Has profession</span><span>{has_profession} ({prof_pct}%)</span></div>
  </div>
</div>

<div class="card">
  <h3>Intent Distribution</h3>
  {intent_html if intent_html else '<span class="muted">No intent data</span>'}
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
        q = request.query.get("q", "").strip()
        try:
            if q:
                users = await user_repo.search_users(q)
            else:
                users = await user_repo.get_all_users_full()
        except Exception as e:
            logger.error(f"Users query failed: {e}")
            return web.Response(text=f'<div class="card">DB error: {_esc(str(e))}</div>',
                                content_type="text/html")

        rows = ""
        for u in users:
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

        html = f"""
<div class="search-bar">
  <span class="search-icon">&#128269;</span>
  <input type="search" name="q" placeholder="Search by name or username..."
         value="{_esc(q)}"
         hx-get="/stats/users?token={stats_token}"
         hx-trigger="keyup changed delay:300ms"
         hx-target="#content"
         hx-include="this">
</div>
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
  <span class="muted">{len(users)} users</span>
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

        try:
            from infrastructure.database.supabase_client import supabase, run_sync

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

            # Get all events for dropdown
            @run_sync
            def _get_events():
                resp = supabase.table("events").select("id, name, code").execute()
                return resp.data or []
            events = await _get_events()

            # Build user lookup
            user_ids = set()
            for m in matches:
                user_ids.add(m.get("user_a_id"))
                user_ids.add(m.get("user_b_id"))

            @run_sync
            def _get_user_names():
                if not user_ids:
                    return []
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

        # Event options
        ev_options = '<option value="">All events</option>'
        for ev in events:
            sel = " selected" if ev["id"] == event_filter else ""
            ev_options += f'<option value="{ev["id"]}"{sel}>{_esc(ev.get("name") or ev.get("code"))}</option>'

        status_options = '<option value="">All</option>'
        for s in ["pending", "accepted", "declined"]:
            sel = " selected" if s == status_filter else ""
            status_options += f'<option value="{s}"{sel}>{s.title()}</option>'

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

        html = f"""
<form class="card" style="display:flex;gap:12px;flex-wrap:wrap;align-items:end"
      hx-get="/stats/matches?token={stats_token}" hx-target="#content">
  <div><label class="muted" style="font-size:.8em">Event</label><br>
    <select name="event" style="width:200px">{ev_options}</select></div>
  <div><label class="muted" style="font-size:.8em">Min Score</label><br>
    <input type="text" name="min_score" value="{_esc(min_score)}" placeholder="0.0" style="width:80px"></div>
  <div><label class="muted" style="font-size:.8em">Status</label><br>
    <select name="status" style="width:120px">{status_options}</select></div>
  <button class="btn btn-sm btn-blue" type="submit">Filter</button>
</form>
<span class="muted">{len(matches)} matches (max 200)</span>
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

        try:
            active_users = await conv_log_repo.get_active_users(limit=80, hours=168)
        except Exception as e:
            logger.error(f"Conversations query failed: {e}")
            return web.Response(
                text=f'<div class="card">DB error: {_esc(str(e))}</div>',
                content_type="text/html",
            )

        # Build a user-info lookup from the users table
        tg_ids = [u["telegram_user_id"] for u in active_users]
        user_map: dict[int, dict] = {}
        if tg_ids:
            try:
                from infrastructure.database.supabase_client import supabase, run_sync

                @run_sync
                def _get_user_info():
                    resp = (
                        supabase.table("users")
                        .select("platform_user_id, display_name, first_name, username")
                        .eq("platform", "telegram")
                        .execute()
                    )
                    return resp.data or []

                for u in await _get_user_info():
                    pid = u.get("platform_user_id")
                    if pid:
                        user_map[int(pid)] = u
            except Exception:
                pass

        rows = ""
        for au in active_users:
            tgid = au["telegram_user_id"]
            info = user_map.get(tgid, {})
            name = info.get("display_name") or info.get("first_name") or str(tgid)
            uname = info.get("username") or ""
            count = au.get("message_count", "")
            last = _fmt_dt(au.get("last_active"))

            # Apply search filter
            if q and q.lower() not in f"{name} {uname} {tgid}".lower():
                continue

            rows += (
                f'<div class="user-list-item" '
                f'hx-get="/stats/conversation/{tgid}?token={stats_token}" '
                f'hx-target="#content">'
                f'<div><div class="name">{_esc(name)}'
                f'{(" (@" + _esc(uname) + ")") if uname else ""}</div>'
                f'<div class="preview">{count} messages</div></div>'
                f'<div class="time">{last}</div>'
                f'</div>'
            )

        html = f"""
<div class="search-bar">
  <span class="search-icon">&#128269;</span>
  <input type="search" name="q" placeholder="Search by name, username, or TG ID..."
         value="{_esc(q)}"
         hx-get="/stats/conversations?token={stats_token}"
         hx-trigger="keyup changed delay:300ms"
         hx-target="#content"
         hx-include="this">
</div>
<div class="card" style="padding:0">
{rows if rows else '<div class="muted" style="padding:20px;text-align:center">No conversations yet</div>'}
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
        total_pages = (total + per_page - 1) // per_page if total else 1
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
                  document.querySelectorAll('.nav a')[4].classList.add('active')">
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
    app.router.add_get("/stats/events", handle_events)
    app.router.add_get("/stats/event/{id}", handle_event_detail)
    app.router.add_get("/stats/matches", handle_matches)
    app.router.add_get("/stats/match/{id}", handle_match_detail)
    app.router.add_get("/stats/conversations", handle_conversations)
    app.router.add_get("/stats/conversation/{tgid}", handle_user_conversation)
    app.router.add_get("/stats/broadcast", handle_broadcast_form)
    app.router.add_post("/stats/broadcast", handle_broadcast_send)
    app.router.add_get("/stats/export/users", handle_export_users)
    return app
