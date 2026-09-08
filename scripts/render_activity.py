from __future__ import annotations

import argparse
import collections
import datetime as dt
import html
import json
import math
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

GITHUB_GRAPHQL = "https://api.github.com/graphql"
MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

THEMES = {
    "light": {
        "background": "#F5EAD8",
        "panel": "#EBDDC5",
        "empty": "#E4D8C6",
        "text": "#201E1D",
        "muted": "#645F56",
        "border": "#D4C5AC",
        "github": "#56633F",
        "gitlab": "#C67139",
        "levels": ("#E4D8C6", "#D9E9BE", "#AFCB86", "#768B54", "#3D472B"),
    },
    "dark": {
        "background": "#201E1D",
        "panel": "#2C2926",
        "empty": "#39342F",
        "text": "#F5EAD8",
        "muted": "#C1B6A6",
        "border": "#514A42",
        "github": "#AFCB86",
        "gitlab": "#E58A50",
        "levels": ("#39342F", "#34402A", "#566B3D", "#789653", "#AFCB86"),
    },
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def graphql(token: str, query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    request = urllib.request.Request(
        GITHUB_GRAPHQL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "invcxze-profile-activity",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.URLError:
        gh = shutil.which("gh")
        if not gh:
            raise
        environment = os.environ.copy()
        environment["GH_TOKEN"] = token
        result = subprocess.run(
            [gh, "api", "graphql", "--input", "-"],
            input=json.dumps({"query": query, "variables": variables}),
            text=True,
            capture_output=True,
            env=environment,
            check=False
        )
        if result.returncode:
            raise RuntimeError("GitHub CLI GraphQL request failed") from None
        payload = json.loads(result.stdout)
    if payload.get("errors"):
        message = payload["errors"][0].get("message", "unknown GraphQL error")
        raise RuntimeError(f"GitHub GraphQL error: {message}")
    return payload["data"]


def github_days(
    login: str, token: str, years: list[int], today: dt.date
) -> dict[str, int]:
    query = """
      query($login:String!,$from:DateTime!,$to:DateTime!){
        user(login:$login){contributionsCollection(from:$from,to:$to){
          contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}
        }}
      }
    """
    result: dict[str, int] = {}
    for year in years:
        end = min(today, dt.date(year, 12, 31))
        if end < dt.date(year, 1, 1):
            continue
        data = graphql(
            token,
            query,
            {
                "login": login,
                "from": f"{year}-01-01T00:00:00Z",
                "to": f"{end.isoformat()}T23:59:59Z",
            },
        )
        user = data.get("user")
        if not user:
            raise RuntimeError(f"GitHub user not found: {login}")
        calendar = user["contributionsCollection"]["contributionCalendar"]
        observed = {
            day["date"]: int(day["contributionCount"])
            for week in calendar["weeks"]
            for day in week["contributionDays"]
            if day["date"].startswith(f"{year}-") and day["date"] <= end.isoformat()
        }
        if sum(observed.values()) != int(calendar["totalContributions"]):
            raise RuntimeError(f"Incomplete GitHub calendar for {year}")
        result.update(observed)
    return result


def gitlab_days(snapshot: dict) -> dict[str, int]:
    days = {
        date: sum(int(value) for value in counts.values())
        for date, counts in snapshot["days"].items()
    }
    if sum(days.values()) != int(snapshot["event_count"]):
        raise RuntimeError("GitLab snapshot total does not match its daily data")
    return days


def combined_days(
    github: dict[str, int], gitlab: dict[str, int]
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for date in sorted(set(github) | set(gitlab)):
        result[date] = {"github": github.get(date, 0), "gitlab": gitlab.get(date, 0)}
    return result


def total(row: dict[str, int]) -> int:
    return row["github"] + row["gitlab"]


def longest_streak(
    days: dict[str, dict[str, int]], start: dt.date | None = None
) -> int:
    active = [
        dt.date.fromisoformat(date)
        for date, row in days.items()
        if total(row) and (start is None or date >= start.isoformat())
    ]
    best = run = 0
    previous = None
    for day in active:
        run = run + 1 if previous and day == previous + dt.timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    return best


def svg_text(
    x: int,
    y: int,
    value: str,
    *,
    size: int,
    color: str,
    weight: int = 400,
    anchor: str = "start",
    family: str = "Arial, Helvetica, sans-serif",
) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-family="{family}" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{html.escape(value)}</text>'
    )


def svg_start(
    width: int, height: int, theme: dict[str, str], title: str, description: str
) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{html.escape(title)}</title>',
        f'<desc id="desc">{html.escape(description)}</desc>',
        f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="18" fill="{theme["background"]}" stroke="{theme["border"]}" stroke-width="2"/>',
    ]


def level_for(value: int, nonzero: list[int]) -> int:
    if value == 0:
        return 0
    maximum = max(nonzero, default=1)
    return min(4, max(1, math.ceil(4 * math.log1p(value) / math.log1p(maximum))))


def render_lifetime(
    days: dict[str, dict[str, int]], years: list[int], theme: dict[str, str]
) -> str:
    width, height = 1000, 150 + 48 * len(years)
    all_total = sum(total(row) for row in days.values())
    active_days = sum(1 for row in days.values() if total(row))
    parts = svg_start(
        width,
        height,
        theme,
        "Combined contribution history",
        "GitHub contributions combined with an archived GitLab activity snapshot, grouped by week and year.",
    )
    parts += [
        svg_text(
            34,
            46,
            "Combined activity history",
            size=25,
            color=theme["text"],
            weight=700,
        ),
        svg_text(
            34,
            74,
            "GitHub contributions + archived GitLab activity",
            size=14,
            color=theme["muted"],
        ),
        svg_text(
            966,
            46,
            f"{all_total:,} RECORDED",
            size=14,
            color=theme["muted"],
            weight=700,
            anchor="end",
        ),
        svg_text(
            966,
            70,
            f"{active_days} ACTIVE DAYS",
            size=12,
            color=theme["muted"],
            anchor="end",
        ),
    ]
    grid_x, cell, gap = 92, 13, 2
    for index, year in enumerate(years):
        y = 108 + index * 48
        first = dt.date(year, 1, 1)
        last = dt.date(year, 12, 31)
        week_values = collections.defaultdict(int)
        cursor = first
        while cursor <= last:
            week = ((cursor - first).days + (first.weekday() + 1) % 7) // 7
            week_values[week] += total(
                days.get(cursor.isoformat(), {"github": 0, "gitlab": 0})
            )
            cursor += dt.timedelta(days=1)
        nonzero = [value for value in week_values.values() if value]
        year_total = sum(week_values.values())
        parts.append(
            svg_text(
                34, y + 12, str(year), size=14, color=theme["muted"], family="monospace"
            )
        )
        for week in range(53):
            value = week_values[week]
            color = theme["levels"][level_for(value, nonzero)]
            x = grid_x + week * (cell + gap)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{color}"><title>{year}, week {week + 1}: {value} recorded activities</title></rect>'
            )
        parts.append(
            svg_text(
                966,
                y + 12,
                f"{year_total:,}",
                size=14,
                color=theme["text"],
                weight=700,
                anchor="end",
                family="monospace",
            )
        )
    legend_y = height - 26
    parts.append(svg_text(34, legend_y + 10, "Less", size=12, color=theme["muted"]))
    for level, color in enumerate(theme["levels"]):
        parts.append(
            f'<rect x="{75 + level * 19}" y="{legend_y}" width="13" height="13" rx="3" fill="{color}"/>'
        )
    parts.append(svg_text(173, legend_y + 10, "More", size=12, color=theme["muted"]))
    parts.append(
        svg_text(
            966,
            legend_y + 10,
            "Platform units differ; totals are observed events, not unique commits.",
            size=11,
            color=theme["muted"],
            anchor="end",
        )
    )
    parts.append("</svg>")
    return "".join(parts)


def month_sequence(start: dt.date, end: dt.date) -> list[dt.date]:
    cursor = start.replace(day=1)
    months = []
    while cursor <= end:
        months.append(cursor)
        cursor = dt.date(
            cursor.year + (cursor.month == 12),
            1 if cursor.month == 12 else cursor.month + 1,
            1,
        )
    return months


def render_recent(
    days: dict[str, dict[str, int]],
    today: dt.date,
    gitlab_last: dt.date,
    theme: dict[str, str],
) -> str:
    # Keep the last archived GitLab year visible instead of letting a rolling
    # window silently remove it after New Year's Day.
    start = dt.date(gitlab_last.year, 1, 1)
    recent = {
        date: row
        for date, row in days.items()
        if start.isoformat() <= date <= today.isoformat()
    }
    recorded = sum(total(row) for row in recent.values())
    active_days = sum(1 for row in recent.values() if total(row))
    streak = longest_streak(recent, start)
    github_total = sum(row["github"] for row in recent.values())
    gitlab_total = sum(row["gitlab"] for row in recent.values())
    width, height = 1000, 500
    parts = svg_start(
        width,
        height,
        theme,
        f"Activity since {start.year}",
        "Monthly GitHub contributions and archived GitLab activity since the final archived GitLab year began.",
    )
    parts += [
        svg_text(
            34,
            46,
            f"Activity since {start.year}",
            size=25,
            color=theme["text"],
            weight=700,
        ),
        svg_text(
            34,
            74,
            f"{MONTHS[start.month - 1]} {start.year} – {MONTHS[today.month - 1]} {today.year}",
            size=14,
            color=theme["muted"],
        ),
    ]
    tiles = (
        ("RECORDED ACTIVITY", f"{recorded:,}"),
        ("ACTIVE DAYS", str(active_days)),
        ("LONGEST STREAK", f"{streak} days"),
    )
    for index, (label, value) in enumerate(tiles):
        x = 34 + index * 316
        parts.append(
            f'<rect x="{x}" y="98" width="298" height="105" rx="14" fill="{theme["panel"]}"/>'
        )
        parts.append(
            svg_text(x + 20, 128, label, size=12, color=theme["muted"], weight=700)
        )
        parts.append(
            svg_text(
                x + 20,
                176,
                value,
                size=34,
                color=theme["text"],
                weight=700,
                family="Georgia, serif",
            )
        )
    parts += [
        svg_text(
            34, 242, "MONTHLY ACTIVITY", size=12, color=theme["muted"], weight=700
        ),
        f'<circle cx="175" cy="238" r="6" fill="{theme["github"]}"/>',
        svg_text(188, 242, f"GitHub {github_total:,}", size=12, color=theme["muted"]),
        f'<circle cx="286" cy="238" r="6" fill="{theme["gitlab"]}"/>',
        svg_text(299, 242, f"GitLab {gitlab_total:,}", size=12, color=theme["muted"]),
    ]
    months = month_sequence(start, today)
    buckets = []
    for month in months:
        prefix = f"{month.year}-{month.month:02d}"
        gh = sum(
            row["github"] for date, row in recent.items() if date.startswith(prefix)
        )
        gl = sum(
            row["gitlab"] for date, row in recent.items() if date.startswith(prefix)
        )
        buckets.append((month, gh, gl))
    maximum = max((gh + gl for _, gh, gl in buckets), default=1)
    chart_x, chart_y, chart_w, chart_h = 45, 272, 910, 150
    parts.append(
        f'<line x1="{chart_x}" y1="{chart_y + chart_h}" x2="{chart_x + chart_w}" y2="{chart_y + chart_h}" stroke="{theme["border"]}"/>'
    )
    slot = chart_w / max(len(buckets), 1)
    bar_width = min(24, slot * 0.58)
    for index, (month, gh, gl) in enumerate(buckets):
        value = gh + gl
        bar_height = (
            0
            if value == 0
            else max(4, chart_h * math.log1p(value) / math.log1p(maximum))
        )
        gh_height = 0 if value == 0 else bar_height * gh / value
        gl_height = bar_height - gh_height
        x = chart_x + slot * index + (slot - bar_width) / 2
        base = chart_y + chart_h
        if gl_height:
            parts.append(
                f'<rect x="{x:.1f}" y="{base - gl_height:.1f}" width="{bar_width:.1f}" height="{gl_height:.1f}" rx="3" fill="{theme["gitlab"]}"><title>{MONTHS[month.month - 1]} {month.year}: GitLab {gl}, GitHub {gh}</title></rect>'
            )
        if gh_height:
            parts.append(
                f'<rect x="{x:.1f}" y="{base - bar_height:.1f}" width="{bar_width:.1f}" height="{gh_height:.1f}" rx="3" fill="{theme["github"]}"><title>{MONTHS[month.month - 1]} {month.year}: GitHub {gh}, GitLab {gl}</title></rect>'
            )
        if index % 2 == 0 or index == len(buckets) - 1:
            parts.append(
                svg_text(
                    int(x + bar_width / 2),
                    449,
                    MONTHS[month.month - 1],
                    size=10,
                    color=theme["muted"],
                    anchor="middle",
                )
            )
        if month.month == 1:
            parts.append(
                svg_text(
                    int(x + bar_width / 2),
                    467,
                    str(month.year),
                    size=10,
                    color=theme["muted"],
                    weight=700,
                    anchor="middle",
                )
            )
    parts.append(
        svg_text(
            34,
            487,
            f"GitLab snapshot ends {MONTHS[gitlab_last.month - 1]} {gitlab_last.day}, {gitlab_last.year}; GitHub refreshes daily.",
            size=11,
            color=theme["muted"],
        )
    )
    parts.append(
        svg_text(
            966,
            487,
            "Bar height uses a logarithmic scale.",
            size=11,
            color=theme["muted"],
            anchor="end",
        )
    )
    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-login", required=True)
    parser.add_argument("--gitlab-snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--today", type=dt.date.fromisoformat)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    today = args.today or dt.datetime.now(dt.timezone.utc).date()
    snapshot = load_json(args.gitlab_snapshot)
    gl_days = gitlab_days(snapshot)
    first_year = min(int(date[:4]) for date in gl_days)
    years = list(range(first_year, today.year + 1))
    gh_days = github_days(args.github_login, token, years, today)
    days = combined_days(gh_days, gl_days)
    gitlab_last = dt.datetime.fromisoformat(
        snapshot["last_event"].replace("Z", "+00:00")
    ).date()

    args.output.mkdir(parents=True, exist_ok=True)
    for theme_name, theme in THEMES.items():
        (args.output / f"lifetime.{theme_name}.svg").write_text(
            render_lifetime(days, years, theme), encoding="utf-8"
        )
        (args.output / f"contributions.{theme_name}.svg").write_text(
            render_recent(days, today, gitlab_last, theme), encoding="utf-8"
        )
    summary = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "github_login": args.github_login,
        "gitlab_login": snapshot["login"],
        "github": sum(gh_days.values()),
        "gitlab": sum(gl_days.values()),
        "combined": sum(total(row) for row in days.values()),
        "active_days": sum(1 for row in days.values() if total(row)),
        "longest_streak": longest_streak(days),
        "gitlab_last_event": snapshot["last_event"],
    }
    (args.output / "activity-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
