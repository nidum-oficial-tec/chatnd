# -*- coding: ascii -*-
"""
Prova do reranker UMA VEZ sobre os candidatos de todas as bases (08/11/2026).

MEDIDO EM PRODUCAO (13 bases, mesma pergunta): k=5 -> 17,8 s; k=48 -> 67,9 s.
O custo e o reranker rodando em ~96 candidatos POR BASE (~1.250 por busca).

O QUE ESTE TESTE GUARDA:
1. intercalar(): posicao 1 de todas as bases antes da posicao 2; no maximo
   `prof` por base; trecho repetido entra uma vez; base vazia nao quebra.
2. profundidade(): ausente = 12; "0" = desligado; lixo = 12.
3. A fiacao em retrieval/utils.py: o caminho novo e tentado ANTES do upstream,
   cai no upstream se der erro, e o so_candidatos devolve a busca hibrida sem
   reranker. (Leitura do codigo - o retrieval nao sobe fora do Open WebUI.)

USO: py _nidum_tools/teste_rerank_global.py
"""

import importlib.util
import io
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
falhas = []


def check(nome, cond):
    print(("  OK   " if cond else "  FALHOU  ") + nome)
    if not cond:
        falhas.append(nome)


class Doc(object):
    def __init__(self, texto, hash_=None):
        self.page_content = texto
        self.metadata = {"_chunk_hash": hash_} if hash_ else {}

    def __repr__(self):
        return self.page_content


def carregar():
    caminho = os.path.join(RAIZ, "backend", "open_webui", "utils", "nidum_rerank_global.py")
    spec = importlib.util.spec_from_file_location("nidum_rerank_global", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    g = carregar()
    a = [Doc("a1", "h-a1"), Doc("a2", "h-a2"), Doc("a3", "h-a3")]
    b = [Doc("b1", "h-b1"), Doc("b2", "h-b2")]
    c = []
    d = [Doc("d1", "h-a1"), Doc("d2", "h-d2")]   # d1 e o MESMO trecho que a1

    print("== intercalar ==")
    out = [x.page_content for x in g.intercalar([a, b, c], 2, "_chunk_hash")]
    check("posicao 1 de todas antes da posicao 2: a1 b1 a2 b2", out == ["a1", "b1", "a2", "b2"])
    out = [x.page_content for x in g.intercalar([a, b], 1, "_chunk_hash")]
    check("profundidade 1 = so o primeiro de cada base", out == ["a1", "b1"])
    out = [x.page_content for x in g.intercalar([a, d], 2, "_chunk_hash")]
    check("trecho repetido em duas bases entra uma vez", out == ["a1", "a2", "d2"])
    out = [x.page_content for x in g.intercalar([a, b], 10, "_chunk_hash")]
    check("profundidade maior que a lista: pega tudo, sem erro", sorted(out) == ["a1", "a2", "a3", "b1", "b2"])
    check("profundidade 0 = nada", g.intercalar([a, b], 0, "_chunk_hash") == [])
    check("sem listas = nada", g.intercalar([], 5, "_chunk_hash") == [])
    sem_hash = [Doc("igual"), Doc("igual")]
    check("sem hash: deduplica pelo texto", len(g.intercalar([sem_hash], 5, "_chunk_hash")) == 1)
    treze = [[Doc("b%d-%d" % (i, j), "h%d-%d" % (i, j)) for j in range(96)] for i in range(13)]
    check("13 bases x 96 candidatos, profundidade 12 -> 156 (era ~1.250)", len(g.intercalar(treze, 12, "_chunk_hash")) == 156)

    print("== lotes paralelos ==")
    pool = list(range(156))
    partes = g.fatiar(pool, 6)
    check("156 em 6 lotes de 26", [len(p) for p in partes] == [26] * 6)
    check("rodizio: nada se perde nem repete", sorted(x for p in partes for x in p) == pool)
    check("menos itens que lotes: so lotes cheios", g.fatiar([1, 2], 6) == [[1], [2]])
    check("1 lote = tudo junto", g.fatiar(pool, 1) == [pool])
    antigo_l = os.environ.pop("NIDUM_RERANK_LOTES", None)
    try:
        check("NIDUM_RERANK_LOTES ausente -> 6", g.lotes() == 6)
        os.environ["NIDUM_RERANK_LOTES"] = "0"
        check("'0' -> 1 (minimo)", g.lotes() == 1)
    finally:
        os.environ.pop("NIDUM_RERANK_LOTES", None)
        if antigo_l is not None:
            os.environ["NIDUM_RERANK_LOTES"] = antigo_l
    d1, d2, d3 = Doc("x"), Doc("y"), Doc("z")
    d1.metadata["score"], d2.metadata["score"] = 0.2, 0.9
    check("nota: maior primeiro, sem nota no fim",
          [d.page_content for d in sorted([d1, d3, d2], key=g.nota, reverse=True)] == ["y", "x", "z"])

    print("== cortar ==")
    check("cortar: k melhores por nota", [p[1] for p in g.cortar([(0.1, "x"), (0.9, "y"), (0.5, "z")], 2)] == ["y", "z"])

    print("== profundidade (variavel de ambiente) ==")
    antigo = os.environ.pop("NIDUM_RERANK_PROFUNDIDADE", None)
    try:
        check("ausente -> 12", g.profundidade() == 12)
        os.environ["NIDUM_RERANK_PROFUNDIDADE"] = "0"
        check("'0' -> desligado", g.profundidade() == 0)
        os.environ["NIDUM_RERANK_PROFUNDIDADE"] = "20"
        check("'20' -> 20", g.profundidade() == 20)
        os.environ["NIDUM_RERANK_PROFUNDIDADE"] = "lixo"
        check("lixo -> 12 (padrao)", g.profundidade() == 12)
    finally:
        os.environ.pop("NIDUM_RERANK_PROFUNDIDADE", None)
        if antigo is not None:
            os.environ["NIDUM_RERANK_PROFUNDIDADE"] = antigo

    print("== fiacao em retrieval/utils.py ==")
    src = io.open(os.path.join(RAIZ, "backend", "open_webui", "retrieval", "utils.py"), encoding="utf-8").read()
    ini = src.index("async def query_collection_with_hybrid_search(")
    corpo = src[ini:src.index("\ndef generate_openai_batch_embeddings", ini)]
    i_novo = corpo.find("_nidum_hibrida_rerank_global(")
    i_velho = corpo.find("async def process_query(")
    check("o caminho novo e tentado ANTES do upstream", 0 < i_novo < i_velho)
    check("... dentro de try, com queda para o upstream",
          "except Exception as e:" in corpo[i_novo:i_velho] and "usando o caminho por base" in corpo[i_novo:i_velho])
    check("... so quando a profundidade > 0", "if _prof > 0:" in corpo[:i_velho])
    qd = src[src.index("async def query_doc_with_hybrid_search("):src.index("def merge_get_results")]
    check("so_candidatos devolve a busca hibrida ANTES do reranker",
          qd.find("if so_candidatos:") < qd.find("compressor = RerankCompressor("))
    check("so_candidatos=False e o padrao (o upstream nao muda)", "so_candidatos: bool = False" in qd)
    glob = src[src.index("async def _nidum_hibrida_rerank_global("):ini]
    check("o global reranqueia o pool intercalado, em lotes paralelos",
          glob.count("RerankCompressor(") == 1 and "intercalar(listas, prof, CHUNK_HASH_KEY)" in glob
          and "fatiar(pool, n_lotes)" in glob and "asyncio.gather(*(_reranquear(l)" in glob)
    check("... junta os lotes pela nota e corta em k_reranker",
          "sorted((d for p in partes for d in p), key=nota, reverse=True)[:k_reranker]" in glob)
    check("... e registra no log quantos candidatos e quanto tempo", "nidum_rerank_global: %d bases" in glob)

    print()
    if falhas:
        print("RERANK GLOBAL: %d FALHA(S)" % len(falhas))
        return 1
    print("RERANK GLOBAL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
