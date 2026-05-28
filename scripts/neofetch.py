#!/usr/bin/env python3
"""Atualiza o bloco "neofetch" do README com stats do GitHub.

Como funciona:
  1. Escolhe uma arte ASCII da pasta ascii/ (rotaciona: uma por dia, pela data UTC).
  2. Busca os numeros na API do GitHub (GraphQL).
  3. Recompoe o bloco visivel (arte em cima + stats embaixo) entre os
     marcadores <!--NEOFETCH:START--> e <!--NEOFETCH:END-->.

O script NUNCA gera nem altera a arte: ele so le os arquivos .txt de ascii/,
escolhe um e monta o bloco com os numeros. Sem dependencias externas (so a
stdlib). Sem token => roda em modo demo offline.

Variaveis de ambiente uteis:
  GH_USER       login do GitHub (default: lealgabriel1)
  GH_TOKEN      token da API; sem ele, usa dados de demonstracao
  NEOFETCH_DEMO =1 forca o modo demo
  NEOFETCH_ART  nome de um arquivo em ascii/ (ex.: dragon.txt) para fixar a arte
"""
import os
import re
import json
import textwrap
import datetime
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
ASCII_DIR = os.path.join(ROOT, "ascii")

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

GAP = 3            # espacos entre arte e stats (modo lado a lado)
MIN_STATS = 28     # largura minima legivel da coluna de stats (lado a lado)
MAX_TOTAL = 92     # largura total no lado a lado; arte mais larga que isso empilha
TARGET_WIDTH = 88  # largura p/ quebrar linhas longas de stats no modo empilhado

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
        indent = " " * len(prefix)
        width = max(wrap - len(prefix), 10)
        # Respeita quebras de linha propositais no valor (ex.: o \n da bio) e
        # so quebra automaticamente os segmentos que passam da largura.
        chunks = []
        for segment in str(value).split("\n"):
            chunks.extend(textwrap.wrap(segment, width=width) or [""])
        lines.append(prefix + chunks[0])
        for chunk in chunks[1:]:
            lines.append(indent + chunk)
    return lines


def compose(art_lines, data):
    """Lado a lado quando a arte e estreita o bastante; senao empilha (arte em
    cima, stats embaixo). A largura da arte decide o modo automaticamente."""
    art = [line.rstrip() for line in art_lines]
    art_width = max((len(l) for l in art), default=0)
    stats_w = MAX_TOTAL - art_width - GAP
    if art and stats_w >= MIN_STATS:
        return _side_by_side(art, stat_lines(data, stats_w), art_width)
    return _stacked(art, stat_lines(data, TARGET_WIDTH))


def _side_by_side(art, stats, art_width):
    rows = max(len(art), len(stats))
    out = []
    for i in range(rows):
        left = art[i] if i < len(art) else ""
        right = stats[i] if i < len(stats) else ""
        out.append((left.ljust(art_width) + " " * GAP + right).rstrip())
    return "\n".join(out)


def _stacked(art, stats):
    body = (art + [""] + list(stats)) if art else list(stats)
    return "\n".join(line.rstrip() for line in body)


def list_arts():
    if not os.path.isdir(ASCII_DIR):
        return []
    return sorted(f for f in os.listdir(ASCII_DIR) if f.lower().endswith(".txt"))


def read_art(path):
    with open(path, encoding="utf-8") as f:
        text = f.read().replace("\r\n", "\n").strip("\n")
    return text.split("\n") if text else []


def pick_art():
    """Arte do dia: rotaciona pela data UTC. Determinístico, entao pushes no
    mesmo dia nao trocam o desenho (so atualizam os numeros). Defina NEOFETCH_ART
    para fixar um arquivo especifico."""
    forced = os.environ.get("NEOFETCH_ART")
    if forced:
        path = os.path.join(ASCII_DIR, forced)
        if os.path.isfile(path):
            return read_art(path)
    arts = list_arts()
    if not arts:
        return []
    today = datetime.datetime.now(datetime.timezone.utc).date()
    index = today.toordinal() % len(arts)
    return read_art(os.path.join(ASCII_DIR, arts[index]))


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

    art = pick_art()
    if DEMO or not TOKEN:
        if not TOKEN and not DEMO:
            print("Aviso: GH_TOKEN ausente -> usando dados de demonstracao.")
        data = demo()
    else:
        data = fetch()

    data.update({k: v for k, v in OVERRIDES.items() if v})

    block = compose(art, data)
    updated = splice(readme, block)

    with open(README, "w", encoding="utf-8", newline="\n") as f:
        f.write(updated)
    print("README atualizado com sucesso.")


if __name__ == "__main__":
    main()
