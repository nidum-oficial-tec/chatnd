# -*- coding: ascii -*-
"""
Prova da etapa A: a pergunta do usuario entra na busca por conteudo JUNTO com a
consulta que o agente escreveu (08/11/2026).

O QUE GUARDA:
1. consultas_da_busca(): acrescenta a pergunta quando ela difere da consulta;
   nao acrescenta se vazia, igual (sem acento/caixa), longa demais ou desligada.
2. ultima_pergunta(): pega a ULTIMA mensagem do usuario, texto ou partes.
3. Fiacao: query_knowledge_files manda as duas consultas ao motor; o motor
   roda as consultas em paralelo e divide os lotes entre elas.

USO: py _nidum_tools/teste_pergunta_original.py
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


def carregar():
    caminho = os.path.join(RAIZ, "backend", "open_webui", "utils", "nidum_pergunta_original.py")
    spec = importlib.util.spec_from_file_location("nidum_pergunta_original", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    p = carregar()
    msgs = [{"role": "user", "content": "oi"}, {"role": "assistant", "content": "ola"},
            {"role": "user", "content": u"Em que fase est\u00e1 cada projeto da Nidum?"}]

    print("== consultas_da_busca ==")
    antigo = os.environ.pop("NIDUM_PERGUNTA_ORIGINAL", None)
    try:
        c = p.consultas_da_busca("fase projeto iniciacao planejamento", msgs)
        check("acrescenta a pergunta do usuario depois da consulta do agente",
              c == ["fase projeto iniciacao planejamento", u"Em que fase est\u00e1 cada projeto da Nidum?"])
        c = p.consultas_da_busca(u"em que fase esta cada projeto da nidum", msgs)
        check("igual sem acento/caixa/pontuacao -> uma so", len(c) == 1)
        check("sem mensagens -> uma so", p.consultas_da_busca("x", []) == ["x"])
        longa = [{"role": "user", "content": "a" * 600}]
        check("pergunta longa demais (texto colado) -> uma so", p.consultas_da_busca("x", longa) == ["x"])
        check("mensagens invalidas nao levantam", p.consultas_da_busca("x", [None, 5]) == ["x"])
        os.environ["NIDUM_PERGUNTA_ORIGINAL"] = "0"
        check("NIDUM_PERGUNTA_ORIGINAL=0 desliga", p.consultas_da_busca("x", msgs) == ["x"])
    finally:
        os.environ.pop("NIDUM_PERGUNTA_ORIGINAL", None)
        if antigo is not None:
            os.environ["NIDUM_PERGUNTA_ORIGINAL"] = antigo

    print("== ultima_pergunta ==")
    partes = [{"role": "user", "content": [{"type": "text", "text": "qual"}, {"type": "image_url"},
                                            {"type": "text", "text": "o prazo?"}]}]
    check("partes de texto juntadas", p.ultima_pergunta(partes) == "qual o prazo?")
    check("pega a ULTIMA do usuario", p.ultima_pergunta(msgs).startswith("Em que fase"))

    print("== fiacao ==")
    b = io.open(os.path.join(RAIZ, "backend", "open_webui", "tools", "builtin.py"), encoding="utf-8").read()
    ini = b.index("async def query_knowledge_files(")
    corpo = b[ini:b.index("\nasync def ", ini + 10)]
    check("query_knowledge_files manda consultas_da_busca(query, __messages__)",
          "queries=consultas_da_busca(query, __messages__)" in corpo)
    u = io.open(os.path.join(RAIZ, "backend", "open_webui", "retrieval", "utils.py"), encoding="utf-8").read()
    g = u[u.index("async def _nidum_hibrida_rerank_global("):u.index("async def query_collection_with_hybrid_search(")]
    check("motor roda as consultas em paralelo", "asyncio.gather(*(_uma_consulta(q) for q in queries))" in g)
    check("... e divide os lotes entre elas", "_nidum_lotes() // max(1, len(queries))" in g)

    print()
    if falhas:
        print("PERGUNTA ORIGINAL: %d FALHA(S)" % len(falhas))
        return 1
    print("PERGUNTA ORIGINAL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
