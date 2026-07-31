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
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "assets" / "languages-dark.svg"
BAR_X = 24.0
BAR_WIDTH = 312.0
COLORS = ("#D6A84B", "#5E81AC", "#A88CC8")
SLOTS = (
    {"dot_x": 28, "label_x": 39, "value_x": 28},
    {"dot_x": 137, "label_x": 148, "value_x": 137},
    {"dot_x": 274, "label_x": 285, "value_x": 274},
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

    segments: list[str] = []
    cursor = BAR_X
    for index, (_, percentage) in enumerate(percentages):
        width = BAR_WIDTH * percentage / 100
        segments.append(
            f'      <rect x="{cursor:.2f}" y="73" width="{width:.2f}" '
            f'height="12" fill="{COLORS[index]}"/>'
        )
        cursor += width

    legends: list[str] = []
    for index, (language, percentage) in enumerate(percentages):
        slot = SLOTS[index]
        safe_name = html.escape(short_label(language))
        legends.extend(
            [
                f'      <circle cx="{slot["dot_x"]}" cy="116" r="4" '
                f'fill="{COLORS[index]}"/>',
                f'      <text x="{slot["label_x"]}" y="119" '
                f'fill="#B1BAC4">{safe_name}</text>',
                f'      <text x="{slot["value_x"]}" y="140" fill="#F0F6FC" '
                f'font-size="16" font-weight="650">{percentage:.1f}%</text>',
            ]
        )

    segments_svg = "\n".join(segments)
    legends_svg = "\n".join(legends)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="180" viewBox="0 0 360 180" role="img" aria-labelledby="title desc">
  <title id="title">Most used languages</title>
  <desc id="desc">{description}</desc>
  <defs>
    <clipPath id="bar">
      <rect x="24" y="73" width="312" height="12" rx="6"/>
    </clipPath>
  </defs>

  <rect x=".5" y=".5" width="359" height="179" rx="18" fill="#161B22" stroke="#30363D"/>

  <g font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
    <text x="24" y="35" fill="#F0F6FC" font-size="16" font-weight="650">Most used languages</text>
    <text x="24" y="54" fill="#8C959F" font-size="10">Across public repositories</text>

    <g clip-path="url(#bar)">
      <rect x="24" y="73" width="312" height="12" fill="#21262D"/>
{segments_svg}
    </g>

    <g font-size="10">
{legends_svg}
    </g>
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
