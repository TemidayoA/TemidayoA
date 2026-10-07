"""Build an SVG card of public repos (not owned by the user) where the user has a merged PR.

The stars shown belong to those projects, not to the user; the card's wording says so.
Run with GITHUB_TOKEN set. Writes assets/contrib-stars.svg.
"""
import json
import logging
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

USER = os.environ.get("GH_USER", "TemidayoA")
OUT = Path(__file__).resolve().parent.parent / "assets" / "contrib-stars.svg"
MAX_ROWS = 8

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    pullRequests(first: 100, after: $after, states: MERGED) {
      pageInfo { hasNextPage endCursor }
      nodes {
        repository { nameWithOwner stargazerCount isPrivate owner { login } }
      }
    }
  }
}
"""

log = logging.getLogger("contrib_stars")


def graphql(token, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch_repos(token):
    repos, after = {}, None
    while True:
        prs = graphql(token, {"login": USER, "after": after})["user"]["pullRequests"]
        for node in prs["nodes"]:
            repo = node["repository"]
            if repo is None or repo["isPrivate"] or repo["owner"]["login"].lower() == USER.lower():
                continue
            repos[repo["nameWithOwner"]] = repo["stargazerCount"]
        if not prs["pageInfo"]["hasNextPage"]:
            break
        after = prs["pageInfo"]["endCursor"]
    return sorted(repos.items(), key=lambda kv: kv[1], reverse=True)


def fmt(n):
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def render(repos):
    total = sum(stars for _, stars in repos)
    shown = repos[:MAX_ROWS]
    row_h, top = 22, 128
    height = top + row_h * len(shown) + (row_h if len(repos) > MAX_ROWS else 0) + 14
    rows = []
    for i, (name, stars) in enumerate(shown):
        y = top + i * row_h
        rows.append(
            f'<text x="30" y="{y}" class="repo">{escape(name)}</text>'
            f'<text x="470" y="{y}" class="stars" text-anchor="end">★ {fmt(stars)}</text>'
        )
    if len(repos) > MAX_ROWS:
        rows.append(f'<text x="30" y="{top + len(shown) * row_h}" class="repo">+ {len(repos) - MAX_ROWS} more</text>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="500" height="{height}" viewBox="0 0 500 {height}">
<style>
.title {{ font: 600 22px 'Segoe UI', Ubuntu, sans-serif; fill: #0366d6; }}
.big {{ font: 700 26px 'Segoe UI', Ubuntu, sans-serif; fill: #24292e; }}
.sub {{ font: 400 13px 'Segoe UI', Ubuntu, sans-serif; fill: #586069; }}
.repo {{ font: 400 14px 'Segoe UI', Ubuntu, sans-serif; fill: #586069; }}
.stars {{ font: 600 14px 'Segoe UI', Ubuntu, sans-serif; fill: #24292e; }}
</style>
<rect x="0.5" y="0.5" width="499" height="{height - 1}" rx="4.5" fill="#ffffff" stroke="#e1e4e8"/>
<text x="30" y="40" class="title">Open-Source Contributions</text>
<text x="30" y="76" class="big">{len(repos)} projects · {fmt(total)} combined stars</text>
<text x="30" y="100" class="sub">Projects with a merged PR from @{escape(USER)}; stars are the projects' own</text>
{''.join(rows)}
</svg>
"""


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        log.error("GITHUB_TOKEN is not set")
        return 1
    repos = fetch_repos(token)
    if not repos:
        log.warning("No merged PRs to external repos found; leaving existing card untouched")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(repos), encoding="utf-8")
    log.info("Wrote %s: %d repos, %d stars", OUT, len(repos), sum(s for _, s in repos))
    return 0


if __name__ == "__main__":
    sys.exit(main())
