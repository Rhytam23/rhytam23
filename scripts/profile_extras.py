#!/usr/bin/env python3
"""Generate featured projects, recent activity, and self-hosted stats SVGs for the profile README."""
import json, os, re, subprocess, datetime as dt
from html import escape

USER = os.environ.get("GH_USER", "Rhytam23")


def gh(*args):
    return json.loads(subprocess.run(["gh", *args], capture_output=True, text=True, check=True, encoding="utf-8").stdout)


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


# ---------- data ----------
now = dt.datetime.now(dt.timezone.utc)
frm = (now - dt.timedelta(days=364)).strftime("%Y-%m-%dT%H:%M:%SZ")
to = now.strftime("%Y-%m-%dT%H:%M:%SZ")

d = gql("""query($login:String!,$from:DateTime!,$to:DateTime!){
 user(login:$login){
  followers{totalCount}
  contributionsCollection(from:$from,to:$to){
    totalCommitContributions totalPullRequestContributions totalIssueContributions
    contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}
  }
  repositories(ownerAffiliations:OWNER,privacy:PUBLIC,isFork:false,first:100,orderBy:{field:PUSHED_AT,direction:DESC}){
    totalCount
    nodes{name url description stargazerCount pushedAt primaryLanguage{name}
          languages(first:8,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}
  }
 }}""", login=USER, **{"from": frm, "to": to})["user"]

repos = [r for r in d["repositories"]["nodes"] if r["name"].lower() != USER.lower()]
cc = d["contributionsCollection"]

# ---------- featured projects ----------
rows = ["| Project | About | Language | Stars |", "|---|---|---|---:|"]
for r in repos[:6]:
    desc = (r["description"] or "-").replace("|", "\\|")
    lang = (r["primaryLanguage"] or {}).get("name", "-")
    rows.append(f"| [{r['name']}]({r['url']}) | {desc} | {lang} | {r['stargazerCount']} |")
featured = "\n".join(rows)

# ---------- recent activity ----------
ev = gh("api", f"users/{USER}/events/public?per_page=100")
items = []
for e in ev:
    repo = e["repo"]["name"]
    link = f"https://github.com/{repo}"
    day = e["created_at"][:10]
    t, p = e["type"], e["payload"]
    if t == "PushEvent" and p.get("commits"):
        msg = p["commits"][-1]["message"].splitlines()[0][:70]
        items.append(f"- `{day}` \U0001F528 Pushed to [{repo}]({link}) - {msg}")
    elif t == "PullRequestEvent" and p.get("action") in ("opened", "closed"):
        pr = p["pull_request"]
        verb = "Merged" if pr.get("merged") else p["action"].capitalize()
        items.append(f"- `{day}` \U0001F500 {verb} PR [{repo}#{pr['number']}](https://github.com/{repo}/pull/{pr['number']})")
    elif t == "IssuesEvent" and p.get("action") == "opened":
        i = p["issue"]
        items.append(f"- `{day}` \U0001F41B Opened issue [{repo}#{i['number']}](https://github.com/{repo}/issues/{i['number']})")
    elif t == "CreateEvent" and p.get("ref_type") == "repository":
        items.append(f"- `{day}` ✨ Created [{repo}]({link})")
seen, act = set(), []
for i in items:
    if i not in seen:
        seen.add(i)
        act.append(i)
activity = "\n".join(act[:6]) or "_No recent public activity._"

# ---------- streaks ----------
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

# ---------- svg helpers ----------
BG, FG, MUTED, ACC = "#0d1117", "#e6edf3", "#8b949e", "#58a6ff"
FONT = "font-family='Segoe UI,Ubuntu,Helvetica,Arial,sans-serif'"


def svg(w, h, body):
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}'>"
            f"<rect x='.5' y='.5' width='{w-1}' height='{h-1}' rx='8' fill='{BG}' stroke='#30363d'/>{body}</svg>")


stats = [("Commits (1y)", cc["totalCommitContributions"]), ("Pull requests", cc["totalPullRequestContributions"]),
         ("Issues", cc["totalIssueContributions"]), ("Public repos", d["repositories"]["totalCount"]),
         ("Stars earned", sum(r["stargazerCount"] for r in repos)), ("Followers", d["followers"]["totalCount"])]
b = f"<text x='20' y='32' fill='{ACC}' font-size='18' font-weight='600' {FONT}>{escape(USER)} - GitHub Stats</text>"
for i, (k, v) in enumerate(stats):
    x, y = 20 + (i % 2) * 190, 64 + (i // 2) * 30
    b += f"<text x='{x}' y='{y}' fill='{MUTED}' font-size='13' {FONT}>{k}</text>"
    b += f"<text x='{x+160}' y='{y}' fill='{FG}' font-size='13' font-weight='600' text-anchor='end' {FONT}>{v}</text>"
b += "<line x1='20' y1='150' x2='380' y2='150' stroke='#30363d'/>"
for i, (k, v) in enumerate([("Current streak", f"{cur} days"), ("Longest streak", f"{longest} days")]):
    x = 20 + i * 190
    b += f"<text x='{x}' y='176' fill='{MUTED}' font-size='13' {FONT}>{k}</text>"
    b += f"<text x='{x}' y='198' fill='{FG}' font-size='16' font-weight='600' {FONT}>{v}</text>"
open("assets/stats.svg", "w", encoding="utf-8").write(svg(400, 215, b))

lang, color = {}, {}
for r in repos:
    for e in r["languages"]["edges"]:
        n = e["node"]["name"]
        lang[n] = lang.get(n, 0) + e["size"]
        color[n] = e["node"]["color"] or "#8b949e"
top = sorted(lang.items(), key=lambda kv: -kv[1])[:6]
tot = sum(v for _, v in top) or 1
b = f"<text x='20' y='32' fill='{ACC}' font-size='18' font-weight='600' {FONT}>Top Languages</text>"
x = 20.0
b += "<clipPath id='c'><rect x='20' y='46' width='360' height='10' rx='5'/></clipPath><g clip-path='url(#c)'>"
for n, v in top:
    w = 360 * v / tot
    b += f"<rect x='{x:.1f}' y='46' width='{w:.1f}' height='10' fill='{color[n]}'/>"
    x += w
b += "</g>"
for i, (n, v) in enumerate(top):
    cx, cy = 20 + (i % 2) * 190, 82 + (i // 2) * 26
    b += f"<circle cx='{cx+5}' cy='{cy-4}' r='5' fill='{color[n]}'/>"
    b += (f"<text x='{cx+16}' y='{cy}' fill='{FG}' font-size='13' {FONT}>{escape(n)} "
          f"<tspan fill='{MUTED}'>{100*v/tot:.1f}%</tspan></text>")
open("assets/langs.svg", "w", encoding="utf-8").write(svg(400, 170, b))

# ---------- write README ----------
t = open("README.md", encoding="utf-8", newline="").read()
t = replace_block(t, "FEATURED", featured)
t = replace_block(t, "ACTIVITY", activity)
open("README.md", "w", encoding="utf-8", newline="").write(t)
print(featured, "\n", activity, "\n", stats, cur, longest, top)
