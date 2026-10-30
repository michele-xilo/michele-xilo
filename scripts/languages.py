"""Render an SVG of the most used languages across the owner's (non-fork) repositories.

Usage: GH_TOKEN=... python scripts/languages.py <login> <output.svg>
Private repositories are included when the token can read them.
"""

import json
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
    sizes, colors, cursor = Counter(), {}, None
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
        for repo in repos["nodes"]:
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                if name in IGNORED:
                    continue
                sizes[name] += edge["size"]
                colors[name] = edge["node"]["color"] or "#8b949e"
        if not repos["pageInfo"]["hasNextPage"]:
            return sizes, colors
        cursor = repos["pageInfo"]["endCursor"]


def render(sizes, colors):
    total = sum(sizes.values())
    top = sizes.most_common(TOP_N)
    other = total - sum(size for _, size in top)
    if other:
        top.append(("Other", other))
        colors["Other"] = "#8b949e"

    width, pad, bar_y, bar_h = 400, 20, 50, 10
    bar_w = width - 2 * pad
    rows = (len(top) + 1) // 2
    height = bar_y + bar_h + 20 + rows * 24 + 10

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>"
        ".t{font:600 16px 'Segoe UI',Ubuntu,sans-serif;fill:#58a6ff}"
        ".l{font:400 12px 'Segoe UI',Ubuntu,sans-serif;fill:#8b949e}"
        "</style>",
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="6" fill="#0d1117" stroke="#30363d"/>',
        f'<text x="{pad}" y="32" class="t">Most used languages</text>',
        f'<clipPath id="c"><rect x="{pad}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="5"/></clipPath>',
        '<g clip-path="url(#c)">',
    ]
    x = pad
    for name, size in top:
        w = bar_w * size / total
        parts.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{w + 0.5:.2f}" height="{bar_h}" fill="{colors[name]}"/>')
        x += w
    parts.append("</g>")

    for i, (name, size) in enumerate(top):
        cx = pad + (i % 2) * (bar_w / 2)
        cy = bar_y + bar_h + 28 + (i // 2) * 24
        parts.append(f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{colors[name]}"/>')
        parts.append(f'<text x="{cx + 16}" y="{cy}" class="l">{escape(name)} {100 * size / total:.1f}%</text>')

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main():
    login, out = sys.argv[1], sys.argv[2]
    sizes, colors = fetch(login, os.environ["GH_TOKEN"])
    with open(out, "w") as f:
        f.write(render(sizes, colors))


if __name__ == "__main__":
    main()
