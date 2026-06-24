#!/usr/bin/env python3
"""Atualiza o bloco "neofetch" do README com stats do GitHub.

Como funciona:
  1. Le a arte ASCII fixa de scripts/art.txt (uma so, sem rotacao).
  2. Busca os numeros na API do GitHub (GraphQL).
  3. Injeta os campos nas linhas reservadas da arte, alinhados a esquerda e
     preenchidos ate a coluna onde o desenho comeca (sem deformar o desenho).
  4. Recompoe o bloco visivel entre <!--NEOFETCH:START--> e <!--NEOFETCH:END-->.

O script NUNCA altera a arte: ele so injeta os numeros nas posicoes reservadas.
Sem dependencias externas (so a stdlib). Sem token => roda em modo demo offline.

Variaveis de ambiente uteis:
  GH_USER       login do GitHub (default: lealgabriel1)
  GH_TOKEN      token da API; sem ele, usa dados de demonstracao
  NEOFETCH_DEMO =1 forca o modo demo
"""
import os
import re
import json
import datetime
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "art.txt")

USER = os.environ.get("GH_USER", "lealgabriel1")
TOKEN = os.environ.get("GH_TOKEN", "")
DEMO = os.environ.get("NEOFETCH_DEMO") == "1"

# Layout fixo: (indice da linha na arte, campo). A linha do "username" vira o
# cabecalho "{username}@github" centralizado; as demais viram "Label: valor".
# Os indices correspondem as linhas reservadas (vazias a esquerda) de art.txt.
LAYOUT = [
    (13, "username"),       # cabecalho centralizado
    (14, "location"),
    (15, "company"),
    (16, "bytes_of_code"),
    (17, "total_commits"),
    (18, "total_prs"),
    (19, "created_at"),
    (20, "email"),
]

LABELS = {
    "location": "Location",
    "company": "Company",
    "email": "Email",
    "bytes_of_code": "Bytes of Code",
    "created_at": "Created At",
    "total_commits": "Total Commits",
    "total_prs": "Total PRs",
}

MIN_GAP = 2  # espacos minimos entre o texto injetado e o desenho

# --- Sobrescrever campos (opcional) ---
# Deixe comentado para usar o dado real do seu GitHub. Os campos numericos
# continuam atualizando sozinhos.
OVERRIDES = {
    "location": "Sao Paulo, BR",
    "company": "MEDTH",
    "email": "glealleone@gmail.com",
}

GQL_USER = """
query($login: String!) {
  user(login: $login) {
    login name location company email
    createdAt
    pullRequests { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size }
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
    total_bytes = sum(
        edge["size"] for repo in repos for edge in repo["languages"]["edges"]
    )
    created = user["createdAt"][:10]
    return {
        "username": user["login"],
        "location": user.get("location"),
        "company": user.get("company"),
        "email": user.get("email"),
        "bytes_of_code": total_bytes,
        "created_at": created,
        "total_commits": total_commits(int(created[:4])),
        "total_prs": user["pullRequests"]["totalCount"],
    }


def demo():
    return {
        "username": "lealgabriel1",
        "location": "Brasil",
        "company": "None",
        "email": "None",
        "bytes_of_code": 31196,
        "created_at": "2023-04-11",
        "total_commits": 412,
        "total_prs": 17,
    }


def read_art():
    with open(ART, encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n").rstrip("\n").split("\n")


def inject(art_lines, data):
    """Escreve cada campo na sua linha reservada, preenchendo ate a coluna onde
    o desenho comeca. O desenho (a direita) nunca se move."""
    out = list(art_lines)
    for idx, key in LAYOUT:
        line = out[idx]
        draw_col = len(line) - len(line.lstrip(" "))  # col 0-based do desenho
        if key == "username":
            # cabecalho alinhado com o inicio da primeira linha do desenho
            text = f"{data['username']}@github"
            indent = len(art_lines[0]) - len(art_lines[0].lstrip(" "))
            left = min(indent, max(draw_col - MIN_GAP - len(text), 0))
            text = " " * left + text
        else:
            value = data.get(key)
            if value in (None, ""):
                value = "None"
            text = f"{LABELS[key]}: {value}"
        limit = draw_col - MIN_GAP
        if len(text) > limit:
            text = text[:limit]
        out[idx] = text.ljust(draw_col) + line[draw_col:]
    return out


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

    if DEMO or not TOKEN:
        if not TOKEN and not DEMO:
            print("Aviso: GH_TOKEN ausente -> usando dados de demonstracao.")
        data = demo()
    else:
        data = fetch()

    data.update({k: v for k, v in OVERRIDES.items() if v})

    block = "\n".join(inject(read_art(), data))
    updated = splice(readme, block)

    with open(README, "w", encoding="utf-8", newline="\n") as f:
        f.write(updated)
    print("README atualizado com sucesso.")


if __name__ == "__main__":
    main()
