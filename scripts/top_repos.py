#!/usr/bin/env python3
"""Rewrite the TOP-REPOS block in README.md with the user's most-committed public repos."""
import json, os, re, subprocess, sys, datetime as dt

USER = os.environ.get("GH_USER", "Rhytam23")
LIMIT = 5
YEARS = 3

QUERY = """
query($login:String!,$from:DateTime!,$to:DateTime!){
  user(login:$login){
    contributionsCollection(from:$from,to:$to){
      commitContributionsByRepository(maxRepositories:100){
        contributions{totalCount}
        repository{nameWithOwner url isPrivate isFork description stargazerCount
                   primaryLanguage{name}}
      }
    }
  }
}"""

def gql(frm, to):
    out = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY}", "-F", f"login={USER}",
         "-f", f"from={frm}", "-f", f"to={to}"],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)["data"]["user"]["contributionsCollection"]["commitContributionsByRepository"]

now = dt.datetime.now(dt.timezone.utc)
totals, meta = {}, {}
for i in range(YEARS):  # API allows max 1 year per query
    to = now - dt.timedelta(days=365 * i)
    frm = to - dt.timedelta(days=365)
    for c in gql(frm.strftime("%Y-%m-%dT%H:%M:%SZ"), to.strftime("%Y-%m-%dT%H:%M:%SZ")):
        r = c["repository"]
        if r["isPrivate"]:
            continue  # never expose private repo names
        totals[r["nameWithOwner"]] = totals.get(r["nameWithOwner"], 0) + c["contributions"]["totalCount"]
        meta[r["nameWithOwner"]] = r

top = sorted(totals.items(), key=lambda kv: -kv[1])[:LIMIT]
lines = ["| Repo | Commits | Language | ⭐ |", "|---|---:|---|---:|"]
for name, n in top:
    r = meta[name]
    lang = (r["primaryLanguage"] or {}).get("name", "—")
    lines.append(f"| [{name}]({r['url']}) | {n} | {lang} | {r['stargazerCount']} |")
block = "<!--TOP-REPOS:START-->\n" + "\n".join(lines) + "\n<!--TOP-REPOS:END-->"

path = "README.md"
text = open(path, encoding="utf-8").read()
new, k = re.subn(r"<!--TOP-REPOS:START-->.*?<!--TOP-REPOS:END-->", lambda _: block, text, flags=re.S)
if k == 0:
    sys.exit("markers not found in README.md")
open(path, "w", encoding="utf-8", newline="").write(new)
print(block)
