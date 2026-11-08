# -*- coding: ascii -*-
"""
REGUA DE BUSCA do ChatND (R3 do plano de 07/11/2026).

O QUE MEDE: se a camada de BUSCA traz o documento certo, e em que posicao.
Nao mede a resposta do modelo - mede o que ele RECEBE. Sao coisas diferentes:
"nao estava na base", "estava e nao voltou na busca" e "voltou e o modelo
ignorou" tem o mesmo sintoma para o usuario e causas opostas. Esta regua
separa as duas primeiras.

POR QUE EXISTE: ate 07/11/2026 a unica forma de descobrir uma falha de busca
era o usuario perguntar, receber a resposta errada e mandar print. O caso
"em que fase esta cada projeto" mostrou o custo: a resposta estava na base, a
busca a punha em 3o lugar com a pergunta do usuario e FORA do top 50 com a
lista de palavras que o agente escreveu. So se descobriu isso repetindo a
busca a mao.

COMO FUNCIONA:
  - Le o gabarito (gabarito_busca.json): pergunta, tipo, documentos-ouro.
  - Para cada item roda o MOTOR de busca com duas variantes:
      pergunta  = o texto do usuario;
      palavras  = a mesma pergunta como lista de palavras, como o agente faz.
  - Motor "conteudo": o endpoint de producao /api/v1/retrieval/query/collection,
    que chama o MESMO query_collection usado por query_knowledge_files
    (hibrido BM25 + vetor + reranker, com a config do painel).
  - Ranqueia por DOCUMENTO (trechos do mesmo arquivo contam uma vez) e acha a
    posicao de cada documento-ouro.
  - Agrega por tipo: acerto@5, acerto@20, MRR e cobertura (listas).

SO LEITURA. Nao altera nada em producao. A chave vem de variavel de ambiente
(NIDUM_URL, NIDUM_TOKEN) ou de --env-local (le NIDUM_API_KEY do .env.local);
nunca e impressa nem gravada.

USO:
  py _nidum_avaliacao/regua_busca.py --env-local --conferir     # o ouro existe na base?
  py _nidum_avaliacao/regua_busca.py --env-local                # roda a regua inteira
  py _nidum_avaliacao/regua_busca.py --env-local --ids F01,R02  # so alguns itens
"""

import argparse
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
GABARITO = os.path.join(AQUI, "gabarito_busca.json")
SAIDA = os.path.join(AQUI, "resultados")

# Bases que nao sao acervo (teste/descartadas). Comparacao por nome dobrado.
BASES_FORA = {"cerebro_dummy"}

TIPOS = ["fato", "recencia", "lista", "tabela_slide", "tema", "armadilha"]
VARIANTES = ["pergunta", "palavras"]


# ---------------------------------------------------------------- funcoes puras

def dobrar(texto):
    """Caixa e acento dobrados, espacos normalizados. Mesmo dado (nome de
    arquivo vindo do SharePoint) comparado sempre pelo mesmo criterio."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().casefold()


def ranking_por_documento(fontes):
    """Lista de fontes (uma por trecho, na ordem do motor) -> lista de
    documentos distintos, na ordem da 1a aparicao."""
    vistos, docs = set(), []
    for f in fontes:
        chave = dobrar(f)
        if chave and chave not in vistos:
            vistos.add(chave)
            docs.append(f)
    return docs


def posicoes_do_ouro(docs, ouro):
    """{substring_ouro: posicao 1-based do 1o documento que a contem, ou None}."""
    dobrados = [dobrar(d) for d in docs]
    out = {}
    for o in ouro:
        alvo = dobrar(o)
        out[o] = next((i + 1 for i, d in enumerate(dobrados) if alvo in d), None)
    return out


def avaliar_item(item, posicoes):
    """Metricas de um item numa variante. Armadilha nao tem metrica de busca
    (o documento nao existe; o que se avalia ali e a resposta)."""
    minimo = item.get("ouro_minimo", 1)
    if item.get("tipo") == "armadilha" or minimo == 0 or not item.get("ouro"):
        return {"aplica": False}
    achados = sorted(p for p in posicoes.values() if p is not None)
    primeira = achados[0] if achados else None
    n = len(item["ouro"])
    em20 = sum(1 for p in achados if p <= 20)
    em5 = sum(1 for p in achados if p <= 5)
    if minimo > 1:
        ok5, ok20 = em5 >= minimo, em20 >= minimo
    else:
        ok5 = primeira is not None and primeira <= 5
        ok20 = primeira is not None and primeira <= 20
    return {
        "aplica": True,
        "primeira": primeira,
        "rr": (1.0 / primeira) if primeira else 0.0,
        "acerto5": ok5,
        "acerto20": ok20,
        "cobertura20": em20 / n if n else 0.0,
    }


def agregar(resultados):
    """{(tipo, variante): {n, acerto5, acerto20, mrr, cobertura20}} + total."""
    acc = {}
    for r in resultados:
        for v in VARIANTES:
            m = r.get("metricas", {}).get(v)
            if not m or not m.get("aplica"):
                continue
            for chave in ((r["tipo"], v), ("TOTAL", v)):
                a = acc.setdefault(chave, {"n": 0, "acerto5": 0, "acerto20": 0, "rr": 0.0, "cob": 0.0})
                a["n"] += 1
                a["acerto5"] += int(m["acerto5"])
                a["acerto20"] += int(m["acerto20"])
                a["rr"] += m["rr"]
                a["cob"] += m["cobertura20"]
    out = {}
    for chave, a in acc.items():
        n = a["n"]
        out[chave] = {"n": n, "acerto5": a["acerto5"] / n, "acerto20": a["acerto20"] / n,
                      "mrr": a["rr"] / n, "cobertura20": a["cob"] / n}
    return out


def relatorio_md(agregado, resultados, meta):
    linhas = ["# Regua de busca - %s" % meta["quando"], "",
              "Motor: `%s` | k=%d | bases: %d | gabarito: %s (%d itens)" % (
                  meta["motor"], meta["k"], meta["n_bases"], meta["gabarito"], meta["n_itens"]), "",
              "Acerto@N = o documento-ouro (ou o minimo de documentos, nas listas) aparece entre os N primeiros "
              "DOCUMENTOS distintos. MRR = media de 1/posicao do 1o ouro. Cobertura@20 = fracao do ouro no top 20.", "",
              "| Tipo | Variante | n | Acerto@5 | Acerto@20 | MRR | Cobertura@20 |",
              "|---|---|---|---|---|---|---|"]
    for tipo in TIPOS + ["TOTAL"]:
        for v in VARIANTES:
            a = agregado.get((tipo, v))
            if a:
                linhas.append("| %s | %s | %d | %.0f%% | %.0f%% | %.2f | %.0f%% |" % (
                    tipo, v, a["n"], 100 * a["acerto5"], 100 * a["acerto20"], a["mrr"], 100 * a["cobertura20"]))
    linhas += ["", "## Por item", "", "| Id | Tipo | 1o ouro (pergunta) | 1o ouro (palavras) | Pergunta |", "|---|---|---|---|---|"]
    for r in resultados:
        def pos(v):
            m = r.get("metricas", {}).get(v) or {}
            if r.get("erro", {}).get(v):
                return "erro"
            if not m.get("aplica"):
                return "n/a"
            return str(m["primeira"]) if m["primeira"] else "fora"
        linhas.append("| %s | %s | %s | %s | %s |" % (r["id"], r["tipo"], pos("pergunta"), pos("palavras"),
                                                     r["pergunta"].replace("|", "/")[:90]))
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------- acesso a API

class Api:
    def __init__(self, base, token, timeout=240):
        self.base, self.token, self.timeout = base.rstrip("/"), token, timeout

    def chamar(self, caminho, corpo=None):
        req = urllib.request.Request(self.base + caminho, method="POST" if corpo is not None else "GET")
        req.add_header("Authorization", "Bearer " + self.token)
        dados = None
        if corpo is not None:
            req.add_header("Content-Type", "application/json")
            dados = json.dumps(corpo).encode("utf-8")
        with urllib.request.urlopen(req, data=dados, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def bases(self):
        r = self.chamar("/api/v1/knowledge/")
        itens = r.get("items", r) if isinstance(r, dict) else r
        return [(k["id"], k["name"]) for k in itens if dobrar(k.get("name")) not in BASES_FORA]

    def arquivos_por_nome(self, kb_id, trecho):
        # A busca por nome do Open WebUI compara bytes (ilike). Nomes vindos do
        # SharePoint as vezes estao em Unicode DECOMPOSTO (NFD: "c" + cedilha
        # separada), e a busca com o nome composto nao os acha. Por isso a
        # consulta usa so o prefixo ASCII do trecho e a comparacao final e
        # feita aqui, com dobrar(). Achado de 07/11: e defeito de esteira (R1).
        prefixo = re.split(r"[^\x00-\x7f]", trecho)[0].strip() or trecho
        r = self.chamar("/api/v1/knowledge/%s/files?query=%s&limit=50" % (kb_id, urllib.parse.quote(prefixo)))
        return [i.get("filename", "") for i in r.get("items", [])]

    def buscar_conteudo(self, ids, consulta, k):
        r = self.chamar("/api/v1/retrieval/query/collection", {"collection_names": ids, "query": consulta, "k": k})
        metas = (r.get("metadatas") or [[]])[0]
        docs = (r.get("documents") or [[]])[0]
        fontes = [(m or {}).get("source") or (m or {}).get("name") or "?" for m in metas]
        return fontes, sum(len(d or "") for d in docs)


def carregar_credenciais(env_local):
    base = os.environ.get("NIDUM_URL", "").strip()
    token = os.environ.get("NIDUM_TOKEN", "").strip()
    if env_local:
        caminho = os.path.join(RAIZ, ".env.local")
        env = dict(re.findall(r"(?m)^([A-Z0-9_]+)=(.*)$", io.open(caminho, encoding="utf-8").read()))
        token = env["NIDUM_API_KEY"].strip().strip('"').strip("'")
        base = base or "https://chatnd.nidumbrasil.com.br"
    if not base or not token:
        sys.exit("faltam NIDUM_URL/NIDUM_TOKEN (ou use --env-local)")
    return base, token


# ---------------------------------------------------------------- execucao

def conferir(api, itens, bases):
    """O ouro existe NA BASE de producao (e nao so no repositorio)?"""
    problemas = 0
    for it in itens:
        for o in it.get("ouro", []):
            achados = []
            for kb_id, kb_nome in bases:
                for nome in api.arquivos_por_nome(kb_id, o):
                    if dobrar(o) in dobrar(nome):
                        achados.append("%s: %s" % (kb_nome, nome))
            estado = "OK " if achados else "SEM"
            if not achados:
                problemas += 1
            print("%s %-5s %s -> %s" % (estado, it["id"], o, "; ".join(achados[:3]) or "nao encontrado em nenhuma base"))
    print("\n%d ouro(s) sem arquivo na base" % problemas)
    return problemas


def rodar(api, itens, bases, k):
    ids = [b[0] for b in bases]
    resultados = []
    for n, it in enumerate(itens, 1):
        r = {"id": it["id"], "tipo": it["tipo"], "pergunta": it["pergunta"], "ouro": it.get("ouro", []),
             "metricas": {}, "posicoes": {}, "top5": {}, "latencia_s": {}, "chars": {}, "erro": {}}
        for v in VARIANTES:
            consulta = it["pergunta"] if v == "pergunta" else it.get("consulta_palavras")
            if not consulta:
                continue
            t0 = time.time()
            try:
                fontes, chars = api.buscar_conteudo(ids, consulta, k)
            except Exception as e:  # um item com erro nao derruba a regua
                r["erro"][v] = str(e)[:200]
                continue
            docs = ranking_por_documento(fontes)
            pos = posicoes_do_ouro(docs, it.get("ouro", []))
            r["posicoes"][v] = pos
            r["metricas"][v] = avaliar_item(it, pos)
            r["top5"][v] = docs[:5]
            r["latencia_s"][v] = round(time.time() - t0, 1)
            r["chars"][v] = chars
        resultados.append(r)
        m = r["metricas"].get("pergunta") or {}
        print("[%d/%d] %s %-12s 1o ouro: pergunta=%s palavras=%s" % (
            n, len(itens), it["id"], it["tipo"],
            m.get("primeira") if m.get("aplica") else "n/a",
            (r["metricas"].get("palavras") or {}).get("primeira")), flush=True)
    return resultados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-local", action="store_true")
    ap.add_argument("--conferir", action="store_true", help="so confere se o ouro existe na base")
    ap.add_argument("--ids", default="", help="lista de ids separada por virgula")
    ap.add_argument("--k", type=int, default=50, help="trechos pedidos ao motor (default 50)")
    ap.add_argument("--gabarito", default=GABARITO)
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    gab = json.load(io.open(a.gabarito, encoding="utf-8"))
    itens = gab["itens"]
    if a.ids:
        quero = {x.strip() for x in a.ids.split(",")}
        itens = [i for i in itens if i["id"] in quero]

    api = Api(*carregar_credenciais(a.env_local))
    bases = api.bases()
    if a.conferir:
        return 1 if conferir(api, itens, bases) else 0

    resultados = rodar(api, itens, bases, a.k)
    agregado = agregar(resultados)
    quando = time.strftime("%Y-%m-%d_%H%M")
    meta = {"quando": quando, "motor": "conteudo (/api/v1/retrieval/query/collection)", "k": a.k,
            "n_bases": len(bases), "gabarito": gab.get("versao", "?"), "n_itens": len(itens)}
    os.makedirs(SAIDA, exist_ok=True)
    with io.open(os.path.join(SAIDA, "regua_%s.json" % quando), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "resultados": resultados,
                   "agregado": {"%s|%s" % k: v for k, v in agregado.items()}}, f, ensure_ascii=False, indent=1)
    md = relatorio_md(agregado, resultados, meta)
    with io.open(os.path.join(SAIDA, "regua_%s.md" % quando), "w", encoding="utf-8") as f:
        f.write(md)
    print("\n" + md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
