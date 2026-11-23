"""Generate the profile language card from public GitHub repositories."""

from __future__ import annotations

import html
import json
import os
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_ROOT = "https://api.github.com"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "assets" / "languages-console.svg"
BAR_X = 174
BAR_WIDTH = 94
LANGUAGE_MARKERS = (
    ("#BE935F", "M0 0h10v10H0Z"),
    ("#7D9FBE", "M4 0h2v2h2v2h2v2H8v2H6v2H4V8H2V6H0V4h2V2h2Z"),
    ("#CDCDD2", "M0 0h10v10H0ZM2 2v6h6V2Z"),
)


def github_get(path: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "L111M1-profile-language-card",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(f"{API_ROOT}{path}", headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API returned {error.code}: {detail}") from error


def public_repositories(owner: str) -> list[dict[str, object]]:
    repositories: list[dict[str, object]] = []
    page = 1
    while True:
        batch = github_get(
            f"/users/{owner}/repos?type=owner&sort=updated&per_page=100&page={page}"
        )
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected repositories response from GitHub")
        repositories.extend(
            repository
            for repository in batch
            if not repository.get("fork") and not repository.get("archived")
        )
        if len(batch) < 100:
            return repositories
        page += 1


def collect_languages(owner: str) -> Counter[str]:
    totals: Counter[str] = Counter()
    for repository in public_repositories(owner):
        name = repository.get("name")
        if not isinstance(name, str):
            continue
        languages = github_get(f"/repos/{owner}/{name}/languages")
        if not isinstance(languages, dict):
            continue
        for language, size in languages.items():
            if isinstance(language, str) and isinstance(size, int):
                totals[language] += size
    return totals


def short_label(language: str) -> str:
    return language if len(language) <= 12 else f"{language[:11]}…"


def generate_svg(totals: Counter[str]) -> str:
    if not totals:
        raise RuntimeError("No language data found in public repositories")

    grand_total = sum(totals.values())
    top_three = totals.most_common(3)
    percentages = [(language, size / grand_total * 100) for language, size in top_three]
    description = ", ".join(
        f"{html.escape(language)} {percentage:.1f}%"
        for language, percentage in percentages
    )

    rows: list[str] = []
    for index, (language, percentage) in enumerate(percentages):
        color, marker_path = LANGUAGE_MARKERS[index]
        safe_name = html.escape(short_label(language))
        y = 62 + 30 * index
        width = BAR_WIDTH * percentage / 100
        rows.append(
            f'''    <g transform="translate(0 {y})">
      <path d="{marker_path}" transform="translate(17 -5)" fill="{color}" fill-rule="evenodd"/>
      <text x="38" y="5" fill="#DADDE4" font-size="14">{safe_name}</text>
      <rect x="{BAR_X}" y="-2" width="{BAR_WIDTH}" height="4" fill="#2A3040"/>
      <rect x="{BAR_X}" y="-2" width="{width:.2f}" height="4" fill="{color}"/>
      <text x="342" y="5" fill="#EFF0F3" font-size="15" font-weight="700" text-anchor="end">{percentage:.1f}%</text>
    </g>'''
        )

    rows_svg = "\n".join(rows)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="144" viewBox="0 0 360 144" role="img" aria-labelledby="title desc">
  <title id="title">Most used languages</title>
  <desc id="desc">Across public repositories: {description}</desc>
  <rect x=".5" y=".5" width="359" height="143" rx="5" fill="#11141C" stroke="#343B4B"/>
  <path d="M6 1h348a5 5 0 0 1 5 5v37H1V6a5 5 0 0 1 5-5Z" fill="#171B26"/>
  <path d="M1 43.5h358M17 77.5h326M17 107.5h326" stroke="#2A3040"/>

  <g font-family="'Courier New',monospace">
    <text x="17" y="28" fill="#EFF0F3" font-size="16" font-weight="700">Most used languages</text>
    <text x="342" y="28" fill="#A6AEBE" font-size="12" text-anchor="end">Share</text>

{rows_svg}
  </g>
</svg>
"""


def main() -> None:
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "L111M1")
    svg = generate_svg(collect_languages(owner))
    OUTPUT_PATH.write_text(svg, encoding="utf-8", newline="\n")
    print(f"Updated {OUTPUT_PATH} for {owner}")


if __name__ == "__main__":
    main()
