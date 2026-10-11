#!/usr/bin/env python3
"""Update the language section embedded in profile.svg using public GitHub repo data."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.sax.saxutils
from datetime import datetime, timezone
from pathlib import Path

OWNER = "YukiHimeno"
PROFILE_REPO = "YukiHimeno"
SVG_PATH = Path("profile.svg")
START = "<!-- LANGUAGE_STATS_START -->"
END = "<!-- LANGUAGE_STATS_END -->"
MAX_LANGUAGES = 8
COLORS = {
    "C": "#A8B9CC", "C++": "#00599C", "C#": "#512BD4",
    "CSS": "#663399", "Go": "#00ADD8", "HTML": "#E34F26",
    "Java": "#ED8B00", "JavaScript": "#F7DF1E", "Kotlin": "#7F52FF",
    "Lua": "#000080", "Objective-C": "#438EFF", "PHP": "#777BB4",
    "Python": "#3776AB", "Ruby": "#CC342D", "Rust": "#DEA584",
    "Shell": "#89E051", "Swift": "#F05138", "TypeScript": "#3178C6",
    "Vue": "#4FC08D", "Dart": "#0175C2", "Jupyter Notebook": "#DA5B0B",
    "Makefile": "#427819", "PowerShell": "#5391FE", "SCSS": "#C6538C",
    "Svelte": "#FF3E00", "Dockerfile": "#384D54", "Nix": "#7E7EFF",
}
DEFAULT_COLOR = "#8b949e"


def github_get(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "YukiHimeno-language-stats",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429) and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            raise


def get_repositories():
    repos = []
    page = 1
    while True:
        query = urllib.parse.urlencode({"type": "owner", "per_page": 100, "page": page})
        batch = github_get(f"https://api.github.com/users/{OWNER}/repos?{query}")
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def collect_language_bytes():
    totals = {}
    repos = get_repositories()
    for repo in repos:
        if repo.get("private") or repo.get("fork") or repo.get("archived") or repo.get("disabled"):
            continue
        if repo.get("full_name", "").lower() == f"{OWNER}/{PROFILE_REPO}".lower():
            continue
        if not repo.get("size", 0):
            continue
        languages_url = repo.get("languages_url")
        if not languages_url:
            continue
        try:
            languages = github_get(languages_url)
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            print(f"Warning: skipped {repo.get('full_name')}: {exc}")
            continue
        for language, byte_count in languages.items():
            totals[language] = totals.get(language, 0) + int(byte_count)
    return totals


def render_language_section(totals):
    total_bytes = sum(totals.values())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not total_bytes:
        return f'''{START}
  <g id="language-usage">
    <text x="54" y="634" class="section">LANGUAGE USAGE</text>
    <text x="54" y="674" class="body">No public repository language data found yet.</text>
    <text x="906" y="634" text-anchor="end" class="section">UPDATED {now}</text>
  </g>
  {END}'''

    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:MAX_LANGUAGES]
    # Keep the bars proportional to the largest language while percentages represent all languages.
    max_bytes = ranked[0][1]
    pieces = [
        START,
        '  <g id="language-usage">',
        '    <text x="54" y="634" class="section">LANGUAGE USAGE</text>',
        f'    <text x="906" y="634" text-anchor="end" class="section">PUBLIC REPOS · UPDATED {now}</text>',
    ]
    for index, (language, byte_count) in enumerate(ranked):
        y = 661 + index * 25
        pct = byte_count / total_bytes * 100
        label = xml.sax.saxutils.escape(language)
        color = COLORS.get(language, DEFAULT_COLOR)
        bar_width = 570 * byte_count / max_bytes if max_bytes else 0
        pieces.extend([
            f'    <text x="54" y="{y + 4}" class="tech">{label}</text>',
            f'    <rect x="190" y="{y - 9}" width="570" height="8" rx="2" fill="#21262d"/>',
            f'    <rect x="190" y="{y - 9}" width="{bar_width:.2f}" height="8" rx="2" fill="{color}"/>',
            f'    <text x="906" y="{y + 4}" text-anchor="end" class="mono">{pct:.1f}%</text>',
        ])
    pieces.extend(['  </g>', f'  {END}'])
    return "\n".join(pieces)


def main():
    svg = SVG_PATH.read_text(encoding="utf-8")
    if START not in svg or END not in svg:
        raise SystemExit("Could not find language section markers in profile.svg")
    totals = collect_language_bytes()
    section = render_language_section(totals)
    before, rest = svg.split(START, 1)
    _, after = rest.split(END, 1)
    updated = before + section + after
    # Extend the canvas to make room for the chart and footer.
    updated = updated.replace('width="960" height="690" viewBox="0 0 960 690"',
                              'width="960" height="920" viewBox="0 0 960 920"')
    updated = updated.replace('<rect x="28" y="28" width="904" height="634" rx="8"',
                              '<rect x="28" y="28" width="904" height="864" rx="8"')
    updated = updated.replace(
        '<line x1="54" y1="634" x2="906" y2="634" stroke="#30363d"/>\n  <text x="54" y="653" class="body" font-size="13">「 Nothing here. 」</text>',
        '<line x1="54" y1="875" x2="906" y2="875" stroke="#30363d"/>\n  <text x="54" y="898" class="body" font-size="13">「 Nothing here. 」</text>'
    )
    if updated != svg:
        SVG_PATH.write_text(updated, encoding="utf-8")
        print(f"Updated language chart with {len(totals)} languages across public repositories.")
    else:
        print("Language chart is already up to date.")


if __name__ == "__main__":
    main()
