#!/usr/bin/env python3
"""Atualiza o bloco "neofetch" do README com stats do GitHub.

Como funciona:
  1. Le a arte ASCII de dentro do comentario <!--ART:START ... ART:END--> no README.
  2. Busca os numeros na API do GitHub (GraphQL).
  3. Recompoe o bloco visivel (arte a esquerda + stats a direita) entre os
     marcadores <!--NEOFETCH:START--> e <!--NEOFETCH:END-->.

O script NUNCA gera nem altera a arte: ele so le, alinha e atualiza os numeros.
Sem dependencias externas (so a stdlib). Sem token => roda em modo demo offline.
"""
import os
import re
import json
import textwrap
import datetime
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")

USER = os.environ.get("GH_USER", "lealgabriel1")
TOKEN = os.environ.get("GH_TOKEN", "")
DEMO = os.environ.get("NEOFETCH_DEMO") == "1"

# Campos exibidos, nesta ordem. Comente uma linha para esconder o campo.
ENABLED = [
    "username",
    "bio",
    "location",
    "company",
    "email",
    #"hireable",
    "followers",
    "following",
    "public_repos",
    "public_gists",
    "total_stars",
    "bytes_of_code",
    "created_at",
    "updated_at",
    "languages",
    "total_commits",
    "total_issues",
    "total_prs",
]

# --- Sobrescrever campos (opcional) ---
# Deixe comentado para usar o dado real do seu GitHub.
# Descomente e preencha para exibir um valor customizado (ex.: uma bio diferente
# da do seu perfil). Os campos numericos continuam atualizando sozinhos.
OVERRIDES = {
    "bio": "Construindo soluções reais e criando problemas novos no processo.\nPipelines com LLMs e sidequests corporativas.",
    "location": "Sao Paulo, BR",
    "company": "MEDTH",
    "email": "glealleone@gmail.com",
    # "languages": "Python, Rust, Go",
}

LABELS = {
    "username": "Username",
    "bio": "Bio",
    "location": "Location",
    "company": "Company",
    "email": "Email",
    "hireable": "Hireable",
    "followers": "Followers",
    "following": "Following",
    "public_repos": "Public Repos",
    "public_gists": "Public Gists",
    "total_stars": "Total Stars",
    "bytes_of_code": "Bytes of Code",
    "created_at": "Created At",
    "updated_at": "Updated At",
    "languages": "Main Languages",
    "total_commits": "Total Commits",
    "total_issues": "Total Issues",
    "total_prs": "Total PRs",
}

GAP = 3            # espacos entre a arte e os stats
TARGET_WIDTH = 88  # largura total alvo do bloco (evita scroll horizontal no desktop)
MIN_STATS = 24     # largura minima da coluna de stats (piso de legibilidade)

GQL_USER = """
query($login: String!) {
  user(login: $login) {
    login name bio location company email isHireable
    createdAt updatedAt
    followers { totalCount }
    following { totalCount }
    gists { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

GQL_COMMITS = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
    }
  }
}
"""


def gql(query, variables):
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": USER,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if data.get("errors"):
        raise SystemExit("Erro GraphQL: " + json.dumps(data["errors"]))
    return data["data"]


def total_commits(created_year):
    """Soma os commits de cada ano (contributionsCollection cobre 1 ano por vez)."""
    total = 0
    this_year = datetime.datetime.utcnow().year
    for year in range(created_year, this_year + 1):
        data = gql(GQL_COMMITS, {
            "login": USER,
            "from": f"{year}-01-01T00:00:00Z",
            "to": f"{year}-12-31T23:59:59Z",
        })
        total += data["user"]["contributionsCollection"]["totalCommitContributions"]
    return total


def fetch():
    user = gql(GQL_USER, {"login": USER})["user"]
    repos = user["repositories"]["nodes"]
    stars = sum(r["stargazerCount"] for r in repos)

    langs = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            langs[name] = langs.get(name, 0) + edge["size"]
    total_bytes = sum(langs.values())
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:4]

    created = user["createdAt"][:10]
    return {
        "username": user["login"],
        "bio": user.get("bio"),
        "location": user.get("location"),
        "company": user.get("company"),
        "email": user.get("email"),
        "hireable": "Yes" if user.get("isHireable") else "No",
        "followers": user["followers"]["totalCount"],
        "following": user["following"]["totalCount"],
        "public_repos": user["repositories"]["totalCount"],
        "public_gists": user["gists"]["totalCount"],
        "total_stars": stars,
        "bytes_of_code": total_bytes,
        "created_at": created,
        "updated_at": user["updatedAt"][:10],
        "languages": ", ".join(name for name, _ in top) or "N/A",
        "total_commits": total_commits(int(created[:4])),
        "total_issues": user["issues"]["totalCount"],
        "total_prs": user["pullRequests"]["totalCount"],
    }


def demo():
    return {
        "username": "lealgabriel1",
        "bio": "Estudante de ciencia da computacao apaixonado por Linux.",
        "location": "Brasil",
        "company": "None",
        "email": "None",
        "hireable": "No",
        "followers": 12,
        "following": 8,
        "public_repos": 9,
        "public_gists": 0,
        "total_stars": 23,
        "bytes_of_code": 31196,
        "created_at": "2023-04-11",
        "updated_at": datetime.date.today().isoformat(),
        "languages": "Python, JavaScript, C",
        "total_commits": 412,
        "total_issues": 5,
        "total_prs": 17,
    }


def stat_lines(data, wrap):
    header = f"{data['username']}@github"
    lines = [header, "-" * len(header)]
    for key in ENABLED:
        value = data.get(key)
        if value in (None, ""):
            value = "None"
        prefix = f"{LABELS[key]}: "
        text = f"{prefix}{value}"
        if len(text) <= wrap:
            lines.append(text)
            continue
        chunks = textwrap.wrap(str(value), width=max(wrap - len(prefix), 10)) or [str(value)]
        lines.append(prefix + chunks[0])
        for chunk in chunks[1:]:
            lines.append(" " * len(prefix) + chunk)
    return lines


def compose(art_lines, stats):
    art_width = max((len(l) for l in art_lines), default=0)
    rows = max(len(art_lines), len(stats))
    out = []
    for i in range(rows):
        art = art_lines[i] if i < len(art_lines) else ""
        stat = stats[i] if i < len(stats) else ""
        out.append((art.ljust(art_width) + " " * GAP + stat).rstrip())
    return "\n".join(out)


def extract_art(readme):
    match = re.search(r"<!--ART:START\n(.*?)\nART:END-->", readme, re.DOTALL)
    return match.group(1).split("\n") if match else []


def splice(readme, block):
    fenced = "<!--NEOFETCH:START-->\n```text\n" + block + "\n```\n<!--NEOFETCH:END-->"
    return re.sub(
        r"<!--NEOFETCH:START-->.*?<!--NEOFETCH:END-->",
        lambda _m: fenced,
        readme,
        flags=re.DOTALL,
    )


def main():
    with open(README, encoding="utf-8") as f:
        readme = f.read()

    art = extract_art(readme)
    if DEMO or not TOKEN:
        if not TOKEN and not DEMO:
            print("Aviso: GH_TOKEN ausente -> usando dados de demonstracao.")
        data = demo()
    else:
        data = fetch()

    data.update({k: v for k, v in OVERRIDES.items() if v})

    art_width = max((len(l) for l in art), default=0)
    wrap = max(TARGET_WIDTH - art_width - GAP, MIN_STATS)
    block = compose(art, stat_lines(data, wrap))
    updated = splice(readme, block)

    with open(README, "w", encoding="utf-8", newline="\n") as f:
        f.write(updated)
    print("README atualizado com sucesso.")


if __name__ == "__main__":
    main()
