"""Render an SVG of the most used languages across the owner's (non-fork) repositories.

Usage: GH_TOKEN=... python scripts/languages.py <login> <output.svg>
Private repositories are included when the token can read them.
"""

import json
import math
import os
import sys
import urllib.request
from collections import Counter
from html import escape

QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes {
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

TOP_N = 6
IGNORED = {"Just", "Makefile", "Dockerfile", "Shell", "Batchfile"}


def fetch(login, token):
    sizes, colors, cursor, repo_count = Counter(), {}, None, 0
    while True:
        body = json.dumps({"query": QUERY, "variables": {"login": login, "cursor": cursor}}).encode()
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=body,
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
        if "errors" in data:
            sys.exit(f"GraphQL error: {data['errors']}")
        repos = data["data"]["user"]["repositories"]
        repo_count += len(repos["nodes"])
        for repo in repos["nodes"]:
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                if name in IGNORED:
                    continue
                sizes[name] += edge["size"]
                colors[name] = edge["node"]["color"] or "#8b949e"
        if not repos["pageInfo"]["hasNextPage"]:
            return sizes, colors, repo_count
        cursor = repos["pageInfo"]["endCursor"]


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def render(sizes, colors, repo_count):
    total = sum(sizes.values())
    top = sizes.most_common(TOP_N)
    other = total - sum(size for _, size in top)
    if other:
        top.append(("Other", other))
        colors["Other"] = "#8b949e"

    width = 480
    height = max(200, 92 + len(top) * 26)
    cx, cy, r, stroke = 100, height / 2 + 12, 58, 16
    circ = 2 * math.pi * r
    gap = 2 if len(top) > 1 else 0

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>"
        ":root{--bg:#ffffff;--border:#d0d7de;--title:#0969da;--text:#1f2328;--muted:#656d76;--track:#eaeef2}"
        "@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--border:#30363d;--title:#58a6ff;--text:#e6edf3;--muted:#8b949e;--track:#21262d}}"
        "text{font-family:'Segoe UI',Ubuntu,Helvetica,sans-serif}"
        ".t{font-size:16px;font-weight:600;fill:var(--title)}"
        ".s{font-size:11px;fill:var(--muted)}"
        ".n{font-size:13px;fill:var(--text)}"
        ".p{font-size:12px;fill:var(--muted);font-variant-numeric:tabular-nums}"
        ".big{font-size:22px;font-weight:700;fill:var(--text)}"
        ".seg{fill:none;animation:draw 1.2s cubic-bezier(.4,0,.2,1) both}"
        "@keyframes draw{from{stroke-dasharray:0 1000}}"
        ".row{opacity:0;animation:fade .5s ease-out forwards}"
        "@keyframes fade{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:none}}"
        ".bar{transform-box:fill-box;transform-origin:left;animation:grow .9s cubic-bezier(.4,0,.2,1) both}"
        "@keyframes grow{from{transform:scaleX(0)}}"
        "</style>",
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="var(--bg)" stroke="var(--border)"/>',
        '<text x="24" y="36" class="t">Most used languages</text>',
        f'<text x="24" y="54" class="s">{len(sizes)} languages · {repo_count} repositories · {human_size(total)} of code</text>',
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="var(--track)" stroke-width="{stroke}"/>',
    ]

    offset = 0.0
    for i, (name, size) in enumerate(top):
        length = circ * size / total
        visible = max(length - gap, 0.8)
        parts.append(
            f'<circle class="seg" cx="{cx}" cy="{cy}" r="{r}" stroke="{colors[name]}" stroke-width="{stroke}" '
            f'stroke-dasharray="{visible:.2f} {circ:.2f}" stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 {cx} {cy})" style="animation-delay:{i * 0.12:.2f}s"/>'
        )
        offset += length

    lead_name, lead_size = top[0]
    parts.append(f'<text x="{cx}" y="{cy + 2}" text-anchor="middle" class="big">{100 * lead_size / total:.0f}%</text>')
    parts.append(f'<text x="{cx}" y="{cy + 20}" text-anchor="middle" class="s">{escape(lead_name)}</text>')

    lx, bar_x, bar_w, px = 196, 300, 110, width - 24
    for i, (name, size) in enumerate(top):
        y = 92 + i * 26
        share = size / total
        parts.append(f'<g class="row" style="animation-delay:{0.3 + i * 0.1:.2f}s">')
        parts.append(f'<circle cx="{lx + 5}" cy="{y - 4}" r="5" fill="{colors[name]}"/>')
        parts.append(f'<text x="{lx + 16}" y="{y}" class="n">{escape(name)}</text>')
        parts.append(f'<rect x="{bar_x}" y="{y - 7}" width="{bar_w}" height="6" rx="3" fill="var(--track)"/>')
        parts.append(
            f'<rect class="bar" x="{bar_x}" y="{y - 7}" width="{max(bar_w * share, 6):.2f}" height="6" rx="3" '
            f'fill="{colors[name]}" style="animation-delay:{0.4 + i * 0.1:.2f}s"/>'
        )
        parts.append(f'<text x="{px}" y="{y}" text-anchor="end" class="p">{100 * share:.1f}%</text>')
        parts.append("</g>")

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main():
    login, out = sys.argv[1], sys.argv[2]
    sizes, colors, repo_count = fetch(login, os.environ["GH_TOKEN"])
    with open(out, "w") as f:
        f.write(render(sizes, colors, repo_count))


if __name__ == "__main__":
    main()
