"""Gera os cards de estatísticas e o gráfico de atividade do perfil.

Roda dentro do GitHub Actions usando o GITHUB_TOKEN, então não depende
de nenhum site de terceiros. Para testar localmente: passe um JSON com
a resposta da API como primeiro argumento.
"""

import datetime as dt
import json
import os
import sys
import urllib.request
from collections import defaultdict
from xml.sax.saxutils import escape

USUARIO = os.environ.get("GITHUB_USER", "RuanTrindade")
SAIDA = os.environ.get("OUT_DIR", "dist")

FUNDO = "#0d0d12"
BORDA = "#8000FF"
TITULO = "#A855F7"
TEXTO = "#E5E5E5"
SUAVE = "#9CA3AF"
LINHA = "#A855F7"
AREA = "#7E22CE"

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def buscar_dados():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            return json.load(f)["data"]["user"]
    token = os.environ["GITHUB_TOKEN"]
    corpo = json.dumps({"query": QUERY, "variables": {"login": USUARIO}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=corpo,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resposta = json.load(resp)
    if "errors" in resposta:
        raise SystemExit(f"Erro da API do GitHub: {resposta['errors']}")
    return resposta["data"]["user"]


def dias_de_contribuicao(user):
    semanas = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    dias = [d for s in semanas for d in s["contributionDays"]]
    hoje = dt.date.today().isoformat()
    return [d for d in dias if d["date"] <= hoje]


def sequencias(dias):
    atual = maior = corrida = 0
    for d in dias:
        corrida = corrida + 1 if d["contributionCount"] > 0 else 0
        maior = max(maior, corrida)
    # A sequência atual não quebra só porque hoje ainda não teve contribuição.
    lista = list(dias)
    if lista and lista[-1]["contributionCount"] == 0:
        lista = lista[:-1]
    for d in reversed(lista):
        if d["contributionCount"] == 0:
            break
        atual += 1
    return atual, maior


def moldura(largura, altura, titulo, conteudo):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" viewBox="0 0 {largura} {altura}" role="img" aria-label="{escape(titulo)}">
<style>
  text {{ font-family: 'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif; }}
  .titulo {{ font-size: 18px; font-weight: 700; fill: {TITULO}; }}
  .rotulo {{ font-size: 13px; fill: {SUAVE}; }}
  .valor {{ font-size: 15px; font-weight: 700; fill: {TEXTO}; }}
  .grande {{ font-size: 28px; font-weight: 800; fill: {TEXTO}; }}
  .eixo {{ font-size: 11px; fill: {SUAVE}; }}
  .surgir {{ opacity: 0; animation: surgir .6s ease-out forwards; }}
  @keyframes surgir {{ to {{ opacity: 1; }} }}
  .linha {{ stroke-dasharray: 4000; stroke-dashoffset: 4000; animation: desenhar 2s ease-out forwards; }}
  @keyframes desenhar {{ to {{ stroke-dashoffset: 0; }} }}
  .barra {{ transform-box: fill-box; transform-origin: left; transform: scaleX(0); animation: crescer 1s ease-out forwards; }}
  @keyframes crescer {{ to {{ transform: scaleX(1); }} }}
</style>
<rect x="0.5" y="0.5" width="{largura - 1}" height="{altura - 1}" rx="12" fill="{FUNDO}" stroke="{BORDA}"/>
<text x="24" y="36" class="titulo">{escape(titulo)}</text>
{conteudo}
</svg>
"""


def card_estatisticas(user, dias):
    cc = user["contributionsCollection"]
    repos = user["repositories"]
    estrelas = sum(r["stargazerCount"] for r in repos["nodes"])
    atual, maior = sequencias(dias)
    itens = [
        ("🔥", "Contribuições no último ano", cc["contributionCalendar"]["totalContributions"]),
        ("📝", "Commits no último ano", cc["totalCommitContributions"]),
        ("🔀", "Pull requests", cc["totalPullRequestContributions"]),
        ("📦", "Repositórios públicos", repos["totalCount"]),
        ("⭐", "Estrelas recebidas", estrelas),
        ("👥", "Seguidores", user["followers"]["totalCount"]),
    ]
    partes = []
    for i, (icone, rotulo, valor) in enumerate(itens):
        y = 74 + i * 28
        partes.append(
            f'<g class="surgir" style="animation-delay:{i * 0.12:.2f}s">'
            f'<text x="24" y="{y}" class="rotulo">{icone}  {escape(rotulo)}</text>'
            f'<text x="300" y="{y}" class="valor" text-anchor="end">{valor}</text></g>'
        )
    # Bloco da sequência à direita
    partes.append(
        f'<line x1="330" y1="58" x2="330" y2="226" stroke="{BORDA}" stroke-opacity=".4"/>'
        f'<g class="surgir" style="animation-delay:.8s">'
        f'<text x="420" y="104" class="grande" text-anchor="middle">{atual}</text>'
        f'<text x="420" y="126" class="rotulo" text-anchor="middle">{"dia seguido" if atual == 1 else "dias seguidos"}</text>'
        f'<text x="420" y="176" class="grande" text-anchor="middle">{maior}</text>'
        f'<text x="420" y="198" class="rotulo" text-anchor="middle">maior sequência</text></g>'
    )
    return moldura(510, 245, "Estatísticas do Ruan", "\n".join(partes))


def card_linguagens(user):
    tamanhos = defaultdict(int)
    cores = {}
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            nome = e["node"]["name"]
            tamanhos[nome] += e["size"]
            cores[nome] = e["node"]["color"] or "#888888"
    total = sum(tamanhos.values()) or 1
    top = sorted(tamanhos.items(), key=lambda kv: kv[1], reverse=True)[:6]
    partes = []
    largura_barra = 230
    for i, (nome, tam) in enumerate(top):
        pct = tam / total * 100
        y = 66 + i * 29
        w = max(largura_barra * pct / 100, 3)
        partes.append(
            f'<g class="surgir" style="animation-delay:{i * 0.12:.2f}s">'
            f'<text x="24" y="{y + 11}" class="rotulo">{escape(nome)}</text>'
            f'<rect x="120" y="{y}" width="{largura_barra}" height="12" rx="6" fill="#ffffff" fill-opacity=".08"/>'
            f'<rect class="barra" style="animation-delay:{i * 0.12:.2f}s" x="120" y="{y}" width="{w:.1f}" height="12" rx="6" fill="{cores[nome]}"/>'
            f'<text x="414" y="{y + 11}" class="valor" text-anchor="end">{pct:.1f}%</text></g>'
        )
    if not top:
        partes.append('<text x="24" y="80" class="rotulo">Ainda sem dados de linguagens.</text>')
    return moldura(440, 245, "Linguagens mais usadas", "\n".join(partes))


def grafico_atividade(dias, quantidade=31):
    ultimos = dias[-quantidade:]
    largura, altura = 900, 300
    esq, dir_, topo, base = 50, 24, 60, 50
    w = largura - esq - dir_
    h = altura - topo - base
    maximo = max([d["contributionCount"] for d in ultimos] + [1])
    # Escala do eixo Y em números redondos
    passo = max(1, -(-maximo // 4))
    teto = passo * 4

    def ponto(i, valor):
        x = esq + (w * i / max(len(ultimos) - 1, 1))
        y = topo + h - (h * valor / teto)
        return x, y

    pts = [ponto(i, d["contributionCount"]) for i, d in enumerate(ultimos)]
    linha = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{esq},{topo + h} " + linha + f" {pts[-1][0]:.1f},{topo + h}"

    partes = []
    for k in range(5):
        valor = passo * k
        y = topo + h - (h * valor / teto)
        partes.append(
            f'<line x1="{esq}" y1="{y:.1f}" x2="{largura - dir_}" y2="{y:.1f}" stroke="#ffffff" stroke-opacity=".07"/>'
            f'<text x="{esq - 10}" y="{y + 4:.1f}" class="eixo" text-anchor="end">{valor}</text>'
        )
    for i, d in enumerate(ultimos):
        if i % 5 == 0 or i == len(ultimos) - 1:
            x, _ = ponto(i, 0)
            data = dt.date.fromisoformat(d["date"]).strftime("%d/%m")
            partes.append(f'<text x="{x:.1f}" y="{topo + h + 22}" class="eixo" text-anchor="middle">{data}</text>')
    partes.append(
        f'<defs><linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{AREA}" stop-opacity=".55"/>'
        f'<stop offset="1" stop-color="{AREA}" stop-opacity="0"/></linearGradient></defs>'
        f'<polygon class="surgir" style="animation-delay:.6s" points="{area}" fill="url(#grad)"/>'
        f'<polyline class="linha" points="{linha}" fill="none" stroke="{LINHA}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>'
    )
    for i, (x, y) in enumerate(pts):
        partes.append(
            f'<circle class="surgir" style="animation-delay:{0.6 + i * 0.04:.2f}s" cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#ffffff" stroke="{LINHA}" stroke-width="2">'
            f'<title>{ultimos[i]["date"]}: {ultimos[i]["contributionCount"]} contribuições</title></circle>'
        )
    total = sum(d["contributionCount"] for d in ultimos)
    partes.append(f'<text x="{largura - dir_}" y="36" class="rotulo" text-anchor="end">{total} contribuições nos últimos {len(ultimos)} dias</text>')
    return moldura(largura, altura, "Atividade recente", "\n".join(partes))


def main():
    user = buscar_dados()
    dias = dias_de_contribuicao(user)
    os.makedirs(SAIDA, exist_ok=True)
    arquivos = {
        "stats.svg": card_estatisticas(user, dias),
        "linguagens.svg": card_linguagens(user),
        "atividade.svg": grafico_atividade(dias),
    }
    for nome, svg in arquivos.items():
        with open(os.path.join(SAIDA, nome), "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"gerado {nome}")


if __name__ == "__main__":
    main()
