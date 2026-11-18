#!/usr/bin/env python3
"""Generate the profile README's dynamic parts: stats/language/top-repo SVG cards and merged-PR activity."""
import json, os, re, subprocess, datetime as dt
from html import escape

USER = os.environ.get("GH_USER", "Rhytam23")


def gh(*args):
    out = subprocess.run(["gh", *args], capture_output=True, text=True, check=True, encoding="utf-8").stdout
    return json.loads(out)


def gql(query, **vars):
    a = ["api", "graphql", "-f", f"query={query}"]
    for k, v in vars.items():
        a += ["-f", f"{k}={v}"]
    return gh(*a)["data"]


def replace_block(text, name, body):
    pat = rf"<!--{name}:START-->.*?<!--{name}:END-->"
    new, k = re.subn(pat, lambda _: f"<!--{name}:START-->\n{body}\n<!--{name}:END-->", text, flags=re.S)
    if not k:
        raise SystemExit(f"marker {name} missing")
    return new


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


now = dt.datetime.now(dt.timezone.utc)

# ---------------------------------------------------------------- data
d = gql("""query($login:String!,$from:DateTime!,$to:DateTime!){
 user(login:$login){
  followers{totalCount}
  contributionsCollection(from:$from,to:$to){
    totalCommitContributions totalPullRequestContributions totalIssueContributions
    contributionCalendar{weeks{contributionDays{date contributionCount}}}
  }
  repositories(ownerAffiliations:OWNER,privacy:PUBLIC,isFork:false,first:100,orderBy:{field:PUSHED_AT,direction:DESC}){
    totalCount
    nodes{name stargazerCount
          languages(first:8,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}
  }
 }}""", login=USER, **{"from": iso(now - dt.timedelta(days=364)), "to": iso(now)})["user"]

repos = d["repositories"]["nodes"]
cc = d["contributionsCollection"]

# ---------------------------------------------------------------- streaks
days = [x for w in cc["contributionCalendar"]["weeks"] for x in w["contributionDays"]]
days = [x for x in days if x["date"] <= now.strftime("%Y-%m-%d")]
longest = run = 0
for x in days:
    run = run + 1 if x["contributionCount"] else 0
    longest = max(longest, run)
cur = 0
for idx in range(len(days) - 1, -1, -1):
    if days[idx]["contributionCount"]:
        cur += 1
    elif idx == len(days) - 1:
        continue  # today may not have a contribution yet
    else:
        break

# ---------------------------------------------------------------- svg helpers
FONT = "font-family='Segoe UI,Ubuntu,Helvetica,Arial,sans-serif'"
FG, MUTED = "#e6edf3", "#8b949e"
TITLE, TRACK, LINE = "#c9d1d9", "#21262d", "#30363d"

# Muted, earthy palette (no violet, no neon). Languages get a fixed colour so cards stay consistent.
PALETTE = {"TypeScript": "#4f7cac", "JavaScript": "#b8934a", "Python": "#5f9e7f", "CSS": "#6a9aa6",
           "PLpgSQL": "#8a8f98", "HTML": "#b0675f", "Swift": "#c07a52"}
FALLBACK = ["#7f8c6a", "#a8826a", "#6f8fa3", "#9a8f78", "#8a8f98"]


def lang_color(name):
    if name not in PALETTE:
        PALETTE[name] = FALLBACK[len(PALETTE) % len(FALLBACK)]
    return PALETTE[name]


def svg(w, h, body):
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}'>"
            f"<rect x='.5' y='.5' width='{w-1}' height='{h-1}' rx='8' fill='#0d1117' stroke='{LINE}'/>{body}</svg>")


def title(text):
    return f"<text x='22' y='36' fill='{TITLE}' font-size='17' font-weight='600' {FONT}>{escape(text)}</text>"


H = 220  # shared height so cards sit level

# ---------------------------------------------------------------- stats card
stats = [("Commits (1y)", cc["totalCommitContributions"], "#5f9e7f"),
         ("Pull requests", cc["totalPullRequestContributions"], "#4f7cac"),
         ("Issues", cc["totalIssueContributions"], "#c07a52"),
         ("Public repos", d["repositories"]["totalCount"], "#6a9aa6"),
         ("Stars earned", sum(r["stargazerCount"] for r in repos), "#b8934a"),
         ("Followers", d["followers"]["totalCount"], "#b0675f")]
b = title(f"{USER} - GitHub Stats")
for i, (k, v, c) in enumerate(stats):
    x, y = 22 + (i % 2) * 190, 68 + (i // 2) * 30
    b += f"<circle cx='{x+5}' cy='{y-4}' r='5' fill='{c}'/>"
    b += f"<text x='{x+18}' y='{y}' fill='{MUTED}' font-size='13' {FONT}>{k}</text>"
    b += f"<text x='{x+162}' y='{y}' fill='{c}' font-size='14' font-weight='700' text-anchor='end' {FONT}>{v}</text>"
b += f"<line x1='22' y1='158' x2='378' y2='158' stroke='{LINE}'/>"
for i, (k, v, c) in enumerate([("Current streak", cur, "#c07a52"), ("Longest streak", longest, "#5f9e7f")]):
    x = 22 + i * 190
    b += f"<text x='{x}' y='181' fill='{MUTED}' font-size='13' {FONT}>{k}</text>"
    b += (f"<text x='{x}' y='205' fill='{c}' font-size='22' font-weight='700' {FONT}>{v}"
          f"<tspan fill='{MUTED}' font-size='13' font-weight='400'> day{'s' if v != 1 else ''}</tspan></text>")
open("assets/stats.svg", "w", encoding="utf-8").write(svg(400, H, b))

# ---------------------------------------------------------------- languages card
lang, color = {}, {}
for r in repos:
    for e in r["languages"]["edges"]:
        n = e["node"]["name"]
        lang[n] = lang.get(n, 0) + e["size"]
        color[n] = lang_color(n)
top = sorted(lang.items(), key=lambda kv: -kv[1])[:6]
tot = sum(v for _, v in top) or 1
b = title("Top Languages")
for i, (n, v) in enumerate(top):
    y = 64 + i * 26
    pct = 100 * v / tot
    b += f"<text x='22' y='{y}' fill='{FG}' font-size='13' {FONT}>{escape(n)}</text>"
    b += f"<rect x='130' y='{y-10}' width='200' height='10' rx='5' fill='{TRACK}'/>"
    b += f"<rect x='130' y='{y-10}' width='{max(200*pct/100, 6):.1f}' height='10' rx='5' fill='{color[n]}'/>"
    b += f"<text x='378' y='{y}' fill='{color[n]}' font-size='13' font-weight='700' text-anchor='end' {FONT}>{pct:.1f}%</text>"
open("assets/langs.svg", "w", encoding="utf-8").write(svg(400, H, b))

# ---------------------------------------------------------------- top contributed repos card
tc = {}
meta = {}
for i in range(3):  # commit API allows max one year per query
    to = now - dt.timedelta(days=365 * i)
    data = gql("""query($login:String!,$from:DateTime!,$to:DateTime!){
     user(login:$login){contributionsCollection(from:$from,to:$to){
      commitContributionsByRepository(maxRepositories:100){
        contributions{totalCount}
        repository{nameWithOwner isPrivate primaryLanguage{name color}}}}}}""",
               login=USER, **{"from": iso(to - dt.timedelta(days=365)), "to": iso(to)})
    for c in data["user"]["contributionsCollection"]["commitContributionsByRepository"]:
        r = c["repository"]
        if r["isPrivate"]:
            continue  # never expose private repo names
        tc[r["nameWithOwner"]] = tc.get(r["nameWithOwner"], 0) + c["contributions"]["totalCount"]
        meta[r["nameWithOwner"]] = r
best = sorted(tc.items(), key=lambda kv: -kv[1])[:5]
mx = best[0][1] if best else 1
b = title("Most commits - last 3 years")
for i, (name, n) in enumerate(best):
    y = 72 + i * 36
    pl = meta[name]["primaryLanguage"] or {}
    c = "#4f7cac"  # one calm steel blue for every bar
    b += f"<circle cx='30' cy='{y-5}' r='5' fill='{c}'/>"
    b += f"<text x='46' y='{y}' fill='{FG}' font-size='15' font-weight='600' {FONT}>{escape(name)}</text>"
    b += f"<text x='290' y='{y}' fill='{MUTED}' font-size='12' {FONT}>{escape(pl.get('name', ''))}</text>"
    b += f"<rect x='390' y='{y-11}' width='300' height='12' rx='6' fill='{TRACK}'/>"
    b += f"<rect x='390' y='{y-11}' width='{max(300*n/mx, 8):.1f}' height='12' rx='6' fill='{c}'/>"
    b += f"<text x='798' y='{y}' fill='{FG}' font-size='14' font-weight='700' text-anchor='end' {FONT}>{n}"
    b += f"<tspan fill='{MUTED}' font-size='12' font-weight='400'> commits</tspan></text>"
open("assets/top-repos.svg", "w", encoding="utf-8").write(svg(820, 72 + 36 * max(len(best), 1) + 6, b))

# ---------------------------------------------------------------- merged PR activity
res = gql("""query($q:String!){search(query:$q,type:ISSUE,first:50){nodes{
  ... on PullRequest{title url mergedAt repository{isPrivate}}}}}""",
          q=f"author:{USER} is:pr is:merged sort:updated-desc")["search"]["nodes"]
prs = [p for p in res if p and p.get("mergedAt") and not p["repository"]["isPrivate"]]
prs.sort(key=lambda p: p["mergedAt"], reverse=True)
lines = []
for p in prs[:6]:
    t = p["title"].strip()
    if len(t) > 62:
        t = t[:62].rsplit(" ", 1)[0].rstrip(",:;-(") + "…"
    t = re.sub(r"([\[\]])", r"\\\1", t)
    lines.append(f"- `{p['mergedAt'][:10]}` <img src='assets/merge.svg' width='16' height='16' alt='merged'/> [{t}]({p['url']})")
activity = "\n".join(lines) or "_No merged pull requests yet._"

# ---------------------------------------------------------------- README
t = open("README.md", encoding="utf-8", newline="").read()
t = replace_block(t, "ACTIVITY", activity)
t = replace_block(t, "TOP-REPOS", '<img src="assets/top-repos.svg" alt="Top contributed repos" width="820"/>')
open("README.md", "w", encoding="utf-8", newline="").write(t)
print(activity)
print(best)
