"""Render the public-facing README.md (the product) + a CSV tracker.

Plain, professional, human voice. No decorative emojis. Sections are exactly the
configured cycles, in order. Roles are sorted by their PUBLISHED date (newest on
top), and that date is frozen per role so the page behaves like a ladder.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from . import config, filters, paths, priority, radar


def _engine_metrics() -> str:
    """One-line observability summary from the last run, if available."""
    try:
        with open(paths.STATS_PATH, encoding="utf-8") as f:
            stats = json.load(f)
    except (OSError, ValueError):
        return ""
    sources = len(stats.get("companies_by_source", {}))
    line = (
        f"_Engine (last run): {stats.get('companies_total', 0):,} companies across "
        f"{sources} ATS platforms · {int(stats.get('fetch_success_rate', 0) * 100)}% "
        f"fetch success · completed in {stats.get('duration_seconds', 0)}s"
    )
    latency = stats.get("detection_latency") or {}
    if latency.get("median_minutes") is not None and latency.get("sample_size", 0) >= 5:
        line += f" · median detection latency {latency['median_minutes']:.0f} min"
    coverage = stats.get("posted_date_coverage")
    if coverage:
        line += f" · real posted dates on {int(coverage * 100)}% of open roles"
    return line + "._"


def _now_str() -> str:
    return datetime.now(UTC).strftime("%b %d, %Y at %H:%M UTC")


def _md_cell(text: str) -> str:
    return (text or "—").replace("|", "/").replace("\n", " ").strip() or "—"


def _short_location(loc: str, limit: int = 40) -> str:
    loc = _md_cell(loc)
    if len(loc) <= limit:
        return loc
    parts = [p.strip() for p in loc.replace(";", ",").split(",") if p.strip()]
    if len(parts) > 1:
        return f"{parts[0]} +{len(parts) - 1} more"
    return loc[: limit - 1].rstrip() + "…"


def _date_str(record: dict) -> str:
    """The published date string we sort/display by (frozen per role)."""
    # Display only a REAL published date (no first_seen fallback) — undated -> dash.
    return record.get("posted_at") or ""


def _sort_key(record: dict):
    # Dated roles first (newest), undated sink to the bottom; first_seen breaks
    # ties so undated roles still have a stable, newest-first order.
    return ((record.get("posted_at") or "")[:10], (record.get("first_seen_at") or "")[:19])


def _pretty_date(record: dict) -> str:
    iso = _date_str(record)
    if not iso:
        return "—"
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        return iso[:10]


def _is_new(record: dict, hours: int = 48) -> bool:
    seen = (record.get("first_seen_at") or "")[:19]
    if not seen:
        return False
    try:
        seen_dt = datetime.strptime(seen, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return False
    return datetime.now(UTC) - seen_dt <= timedelta(hours=hours)


def _row(record: dict) -> str:
    company = _md_cell(record.get("company"))
    title = _md_cell(record.get("title"))
    if record.get("season_inferred"):
        title += " ~"
    if _is_new(record):
        title = f"{title} 🆕"
    location = _short_location(record.get("location"))
    category = _md_cell(record.get("category"))

    specs = []
    if record.get("stipend"):
        specs.append(record.get("stipend"))
    elif record.get("salary"):
        specs.append(record.get("salary"))
    if record.get("experience"):
        specs.append(record.get("experience"))
    if record.get("degree"):
        specs.append(record.get("degree"))
    if record.get("batch"):
        specs.append(record.get("batch"))
    specs_str = "<br>".join(specs) if specs else "—"

    posted = _pretty_date(record)
    url = record.get("url") or ""
    apply = f"[Apply]({url})" if url else "—"
    return f"| {company} | {title} | {category} | {specs_str} | {location} | {posted} | {apply} |"


def _region_label(cfg: dict) -> str:
    if not config.restrict_region(cfg):
        return "Worldwide"
    parts = []
    if config.want_india(cfg):
        parts.append("India")
    if config.want_remote(cfg):
        parts.append("Verified Remote")
    if config.want_us(cfg):
        parts.append("United States")
    if config.want_canada(cfg):
        parts.append("Canada")
    return " & ".join(parts) if parts else "India & Verified Remote"



def _company_count() -> int:
    try:
        with open(paths.COMPANIES_PATH, encoding="utf-8") as f:
            return len(json.load(f))
    except (OSError, ValueError):
        return 0


def _raw_feed_url() -> str:
    """The feed served straight from the repo (no Pages dependency)."""
    return f"https://raw.githubusercontent.com/{config.repo_slug()}/main/docs/feed.xml"


def _email_subscribe_url() -> str:
    """One-click feed-to-email signup, prefilled with our feed."""
    return f"https://feedrabbit.com/subscriptions/new?url={quote(_raw_feed_url(), safe='')}"


def _header(cfg: dict, total_open: int, companies: int, new_week: int) -> list[str]:
    batches = config.target_batches(cfg)
    batch_phrase = " & ".join(batches)
    pages = config.pages_base()

    repo = config.repo_slug()
    stats_url = quote(f"{pages}/api/stats.json", safe="")
    return [
        "# Indian Fresher & New-Grad Jobs",
        "",
        f"[![CI](https://github.com/{repo}/actions/workflows/ci.yml/badge.svg)]"
        f"(https://github.com/{repo}/actions/workflows/ci.yml) "
        f"![Open roles](https://img.shields.io/badge/dynamic/json?label=open%20roles"
        f"&query=open_total&url={stats_url}&color=2f81f7) "
        "![Updates](https://img.shields.io/badge/updates-every%204h-3fb950) "
        f"[![RSS](https://img.shields.io/badge/RSS-subscribe-e67e22)]({pages}/feed.xml)",
        "",
        "A self-updating engine that tracks **full-time fresher & new-grad tech jobs** "
        f"for the **{batch_phrase} batch** across India — so you don't have to. "
        "Instead of refreshing Naukri, LinkedIn, and a dozen career pages by hand, "
        "it reads company hiring feeds directly and keeps one live list, newest roles "
        "on top, refreshed automatically throughout the day.",
        "",
        f"**{total_open} open roles · {new_week} new this week · {companies:,} companies "
        f"tracked · updated {_now_str()}**",
        "",
        "**⭐ Star this repo ⭐** to save it and get notified when new roles land.",
        "",
        f"**Live:** [dashboard]({pages}/) · [RSS feed]({pages}/feed.xml) "
        f"(instant alerts in any RSS app) · [JSON API]({pages}/api/jobs.json)",
        "",
        f"**🔔 New roles in your inbox:** [subscribe by email]({pages}/#subscribe) "
        "- one email a day, only when new jobs actually appeared, "
        f"one-click unsubscribe. (Prefer RSS-to-email? [Feedrabbit works too]"
        f"({_email_subscribe_url()}).)",
        "---",
        "",
    ]




def _about_section(cfg: dict) -> list[str]:
    region = _region_label(cfg)
    batches = config.target_batches(cfg)
    batch_phrase = " and ".join(batches)
    pages = config.pages_base()

    return [
        "## What this is",
        "",
        "This is an engine, not a hand-kept list. It polls company career feeds several "
        "times a day, detects fresher / new-grad openings using a 4-tier signal detector "
        "(batch year → title band → experience range → eligibility signals), removes "
        "duplicates, and rebuilds this page automatically. Every link comes straight "
        "from the source — no stale copy-paste lists.",
        "",
        "## What makes this different",
        "",
        "- **🎓 Fresher-specific detection** — finds roles by what companies actually "
        "write: `2026 batch`, `Graduate Engineer Trainee`, `0-1 years`, `no active "
        "backlogs`, `CGPA ≥ 7.0`, `PPO`, `TCS NQT` — not just title keywords.",
        "- **Real posted dates on every role** — pulled from each ATS directly, so "
        "newest-first actually means newest.",
        "- **Skill tags + pay, extracted** — every posting's text is scanned for the "
        "stack it wants (Python, Java, C++, SQL, ...) and the CTC / stipend it states — "
        f"searchable on the [dashboard]({pages}/), included in the CSV and API.",
        f"- **Alerts your way** — [email digests]({pages}/#subscribe), "
        f"[RSS]({pages}/feed.xml), or Discord — plus a [live dashboard]({pages}/) "
        "with search and custom filters.",
        "- **Covers the full India fresher ecosystem** — Naukri (fresher filter), "
        "Unstop (off-campus drives), Internshala, direct ATS (Greenhouse, Workday, "
        "Lever…), and custom scrapers for Flipkart, Swiggy, Razorpay, and more.",
        "- **An engine, not a spreadsheet** — polled every 4 hours across all "
        "platforms with full source in this repo.",
        "",
        "## Scope",
        "",
        "- **Roles:** Full-time entry-level / fresher — Software Engineering, "
        "Data Science & ML, and closely related tech roles",
        f"- **Batch:** {batch_phrase} passouts (freshers & final-year)",
        f"- **Region:** {region}",
        "- **What we detect:** Graduate Engineer Trainee, Associate SWE/SDE, "
        "Junior Developer, System Engineer (TCS/Infosys band), Programmer Analyst "
        "Trainee (Cognizant), off-campus drives, and any role stating `2026 batch` "
        "/ `2027 passout` / `0-1 years` in the JD",
        "",
        "## About",
        "",
        "I built this engine because finding fresher jobs in India is painful — "
        "Naukri floods you with spam, LinkedIn shows you senior roles, and "
        "off-campus drives close before you even hear about them. This engine "
        "watches everything automatically and surfaces only what's relevant for "
        "the 2026/2027 batch. Apply early — freshers who apply in the first 48 "
        "hours have a significantly higher callback rate.",
        "",
        "## How to use",
        "",
        "- Roles are grouped by batch year — **newest posting on top, oldest at the bottom.**",
        "- The **Posted** column is the date the company published the role.",
        "- **Flags:** 🆕 = spotted in the last 48 hours — apply immediately.",
        "- The **Pay & Specs** column shows CTC / stipend + experience range + degree.",
        "- Track your applications with [`data/jobs.csv`](data/jobs.csv) "
        "(opens in Excel / Google Sheets).",
        "- Missing a company? Adding one takes a single line — see "
        "[CONTRIBUTING.md](CONTRIBUTING.md).",
        "",
        "---",
        "",
    ]




def _footer() -> list[str]:
    return [
        "---",
        "",
        "## Hiring timeline",
        "",
        "Fresher job postings per week, from each role's real published date — "
        "redrawn automatically on every run. When this line takes off, "
        "campus season and off-campus drives are in full swing:",
        "",
        "<picture>",
        '  <source media="(prefers-color-scheme: dark)" srcset="docs/trends-dark.svg">',
        '  <img alt="Fresher jobs posted per week, drawn from real published dates" '
        'src="docs/trends-light.svg">',
        "</picture>",
        "",
        "## How it stays current",
        "",
        "A Python engine reads public company hiring feeds directly, keeps the "
        "roles that match the fresher/new-grad scope above, de-duplicates across "
        "sources, records each role's published date once (so it never shifts), "
        "and regenerates this page through GitHub Actions every 4 hours. "
        "It polls every company concurrently (async) with retry/backoff and "
        "per-host rate limits. The full source is in this repo.",
        "",
        _engine_metrics(),
        "",
        "## Platforms Monitored",
        "",
        "The engine currently extracts live data from the following platforms:",
        "- **Direct ATS (Applicant Tracking Systems):** Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Workday, Breezy, Recruitee, Rippling, Eightfold, Oracle",
        "- **Direct Enterprise APIs:** Amazon (India Jobs)",
        "",
        "## Contributing",
        "",
        "Adding a company takes one line, see [CONTRIBUTING.md](CONTRIBUTING.md). "
        "Suggestions and pull requests are welcome.",
        "",
        "## Note on dates",
        "",
        "The **Posted** column shows when a role was published, newest at the top. "
        "Dates are pulled straight from each job portal. Portals that don't expose "
        "a date show a dash (—). Know the real date for a dashed role? Open a PR.",
        "",
        "Roles can close at any time — always confirm on the company's own site "
        "before applying.",
        "",
    ]




def _select(rows: list[dict], limit, per_company) -> list[dict]:
    """Pick which rows to show, then order them newest-first for display.

    1) cap each company to `per_company` (variety, newest kept),
    2) if still over `limit`, keep the most sought-after companies first,
    3) display newest on top.
    """
    rows = sorted(rows, key=_sort_key, reverse=True)
    if per_company:
        seen: dict[str, int] = {}
        capped = []
        for r in rows:
            c = (r.get("company") or "").strip().lower()
            if seen.get(c, 0) >= per_company:
                continue
            seen[c] = seen.get(c, 0) + 1
            capped.append(r)
        rows = capped
    if limit and len(rows) > limit:
        rows = sorted(rows, key=lambda r: priority.rank(r.get("company")))[:limit]
    return sorted(rows, key=lambda r: _date_str(r)[:10], reverse=True)


def _region_of(record: dict) -> str:
    loc = record.get("location") or ""
    if filters.is_india(loc) or (filters.is_remote_or_hybrid(loc) and not filters.is_foreign(loc)):
        return "Primary"
    return "International"


def _new_this_week(open_jobs: list[dict]) -> int:
    cutoff = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    return sum(1 for r in open_jobs if (r.get("first_seen_at") or "") >= cutoff)


def _radar_section(store_data: dict, cycle: str, cap: int = 30) -> list[str]:
    """The Drop Radar: which companies haven't posted yet, and when to expect
    them — from the engine's own observed dates + hand-verified opening windows.

    The README teaser leads with the FORECAST (waiting, soonest first) — that's
    the radar's unique value; "open now" rows just echo the list above — then
    shows a few recent drops as proof the forecast is real. The dashboard keeps
    the full, searchable list."""
    rows = radar.rows(store_data, cycle)
    if not rows:
        return []
    waiting = [r for r in rows if r["status"] == "waiting"]
    opened = [r for r in rows if r["status"] == "open"]
    dropped = [r for r in rows if r["status"] == "dropped"]
    # Forecast first (what to watch for), then a handful of recent drops as proof.
    ordered = waiting + opened[:8] + dropped[:4]

    pages = config.pages_base()
    verified = sum(1 for r in rows if r.get("source") == "engine")
    lines = [
        '<a id="drop-radar"></a>',
        "",
        f"## 📅 Drop Radar — when companies usually post for {cycle} batch",

        "",
        "Stop refreshing career pages. Every date here is **real or verified** — "
        "no third-party list. 🎯 = the engine **saw the drop itself** from the "
        "company's own careers API; the rest are hand-checked typical opening "
        "windows for marquee names. ✅ = already live in the list above.",
        "",
        '> **Heads up:** companies trend *earlier* every cycle, and "~Aug" is a '
        'month, not a day. Treat "expected" as when to **start watching**, and '
        '"rolling" companies as worth checking year-round.',
        "",
        "| Company | Typical opening | Expected this cycle | Status |",
        "|---|---|---|---|",
    ]
    for r in ordered[:cap]:
        if r["status"] == "open":
            status = f"✅ [open now]({r['url']})" if r["url"] else "✅ open now"
        elif r["status"] == "dropped":
            status = "🗓️ dropped"
        else:
            status = "⏳ waiting"
        mark = "🎯 " if r.get("source") == "engine" else ""
        lines.append(
            f"| {mark}{_md_cell(r['company'])} | {radar.pretty_last(r)} | "
            f"{radar.pretty_expected(r)} | {status} |"
        )
    verified_note = (
        f"**{verified}** dated from our own live observations 🎯 (this grows every cycle). "
        if verified
        else ""
    )
    lines.extend(
        [
            "",
            f"_{len(rows)} companies on the [full radar]({pages}/#radar). {verified_note}"
            '"~Aug" = hand-verified typical month, not a promise of the day; '
            '"rolling" = posts year-round; "waiting" = not seen in our tracked '
            "feeds yet, not a guarantee it isn't out somewhere else._",
            "",
        ]
    )
    return lines


def _closed_section(
    store_data: dict, cycles: list[str], days: int = 14, cap: int = 40
) -> list[str]:
    """Roles that recently closed, kept visible (collapsed) so nobody wastes an
    application on a listing that just died. Only tracked cycles appear here —
    an off-cycle tombstone (text-verified "Summer 2026") was never on the list,
    so it has no business in its obituary either."""
    cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    closed = [
        r
        for r in store_data.values()
        if not r.get("is_open")
        and (r.get("closed_at") or "") >= cutoff
        and r.get("season") in cycles
    ]
    if not closed:
        return []
    closed.sort(key=lambda r: r.get("closed_at") or "", reverse=True)
    closed = closed[:cap]
    lines = [
        "<details>",
        f"<summary><strong>Recently closed</strong> — {len(closed)} roles taken down "
        f"in the last {days} days</summary>",
        "",
        "| Company | Role | Cycle | Closed |",
        "|---|---|---|---|",
    ]
    for r in closed:
        closed_on = (r.get("closed_at") or "")[:10]
        lines.append(
            f"| {_md_cell(r.get('company'))} | {_md_cell(r.get('title'))} "
            f"| {_md_cell(r.get('season'))} | {closed_on} |"
        )
    lines.extend(["", "</details>", ""])
    return lines


def generate(store_data: dict) -> dict:
    cfg = config.load_config()
    batches = config.target_batches(cfg)
    per_company = config.max_per_company(cfg)

    open_jobs = [r for r in store_data.values() if r.get("is_open")]
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in open_jobs:
        groups.setdefault((_region_of(r), r.get("season", "")), []).append(r)

    # Build section labels: known batches first, then any "new_grad" catch-all
    all_seasons = list(batches)
    if any(r.get("season") == "new_grad" for r in open_jobs):
        all_seasons.append("new_grad")

    _BATCH_LABELS = {
        "2026": "2026 Batch — Freshers (Passed Out)",
        "2027": "2027 Batch — Final Year (Passing Out)",
        "new_grad": "New Grad — Entry Level (All Batches)",
    }

    sections: list[tuple[str, list[dict]]] = []
    displayed: list[dict] = []
    regions = ["Primary"]
    if config.include_international(cfg):
        regions.append("International")
    for region in regions:
        for season in all_seasons:
            rows = _select(
                groups.get((region, season)) or [],
                config.section_limit(cfg, season),
                per_company,
            )
            if rows:
                label = _BATCH_LABELS.get(season, season)
                heading = label if region == "Primary" else f"{label} (International)"
                sections.append((heading, rows))
                displayed.extend(rows)

    lines = _header(cfg, len(displayed), _company_count(), _new_this_week(open_jobs))
    for heading, rows in sections:
        lines.append(f"## {heading}  ({len(rows)} open)")
        lines.append("")
        lines.append("| Company | Role | Category | Pay & Specs | Location | Posted | Apply |")
        lines.append("|---|---|---|---|---|---|---|")
        lines.extend(_row(r) for r in rows)
        lines.append("")

    if not displayed:
        lines.append(
            "_No matching roles right now — the list fills as companies post fresher "
            "openings. ⭐ Star and check back._"
        )
        lines.append("")

    lines.extend(_about_section(cfg))
    lines.extend(_radar_section(store_data, batches[0]))
    lines.extend(_closed_section(store_data, all_seasons))
    lines.extend(_footer())

    with open(paths.README_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    _write_csv(displayed)

    return {"open": len(displayed), "companies": _company_count()}




def _write_csv(open_jobs: list[dict]) -> None:
    fields = [
        "company",
        "title",
        "batch",
        "category",
        "location",
        "salary",
        "stipend",
        "experience",
        "degree",
        "skills",
        "posted_at",
        "first_seen_at",
        "url",
    ]
    csv_path = paths.CSV_PATH
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in open_jobs:
            row = {k: r.get(k, "") for k in fields}
            # 'season' holds the batch label in the store — map it to 'batch'
            if not row["batch"] and r.get("season"):
                row["batch"] = r.get("season")
            row["skills"] = "; ".join(r.get("skills") or [])
            writer.writerow(row)

