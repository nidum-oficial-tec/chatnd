# -*- coding: ascii -*-
"""
Prova offline das contas da regua de busca (regua_busca.py).

Uma regua com conta errada e pior que nenhuma: da numero com cara de prova.
Este teste guarda as tres contas que decidem o veredito:
  1. o ranking e por DOCUMENTO (trechos repetidos do mesmo arquivo contam uma vez);
  2. o ouro casa sem caixa e sem acento ("Reunioes" == "Reunioes" com til);
  3. lista exige o MINIMO de documentos, e armadilha fica fora da media.

USO: py _nidum_avaliacao/teste_regua_busca.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regua_busca as rb  # noqa: E402

falhas = []


def check(nome, cond):
    print(("  OK   " if cond else "  FALHOU  ") + nome)
    if not cond:
        falhas.append(nome)


def main():
    print("== ranking por documento ==")
    fontes = ["A.md", "A.md", "B.md", "a.md", "C.md"]
    check("trechos do mesmo arquivo contam uma vez", rb.ranking_por_documento(fontes) == ["A.md", "B.md", "C.md"])

    print("\n== ouro casa sem caixa e sem acento ==")
    docs = ["Reuni" + chr(0xF5) + "es > Atas > PROJ_Acompanhamento Semanal de Portf" + chr(0xF3) + "lio_22-09-2026.md", "X.md"]
    pos = rb.posicoes_do_ouro(docs, ["portfolio_22-09-2026", "inexistente"])
    check("acha com acento dobrado", pos["portfolio_22-09-2026"] == 1)
    check("ausente vira None", pos["inexistente"] is None)

    print("\n== metricas ==")
    fato = {"tipo": "fato", "ouro": ["x"], "ouro_minimo": 1}
    m = rb.avaliar_item(fato, {"x": 3})
    check("fato em 3o: acerto@5 e @20", m["acerto5"] and m["acerto20"] and abs(m["rr"] - 1 / 3) < 1e-9)
    m = rb.avaliar_item(fato, {"x": 12})
    check("fato em 12o: falha @5, acerta @20", (not m["acerto5"]) and m["acerto20"])
    m = rb.avaliar_item(fato, {"x": None})
    check("fato fora: rr 0", m["rr"] == 0.0 and not m["acerto20"])

    lista = {"tipo": "lista", "ouro": ["a", "b", "c"], "ouro_minimo": 2}
    m = rb.avaliar_item(lista, {"a": 2, "b": None, "c": 30})
    check("lista com 1 de 2 minimos no top 20 NAO acerta", not m["acerto20"])
    m = rb.avaliar_item(lista, {"a": 2, "b": 18, "c": None})
    check("lista com 2 no top 20 acerta @20 mas nao @5", m["acerto20"] and not m["acerto5"])
    check("cobertura@20 = 2/3", abs(m["cobertura20"] - 2 / 3) < 1e-9)

    arm = {"tipo": "armadilha", "ouro": [], "ouro_minimo": 0}
    check("armadilha fora da metrica de busca", rb.avaliar_item(arm, {}) == {"aplica": False})

    print("\n== agregado ==")
    res = [
        {"tipo": "fato", "metricas": {"pergunta": rb.avaliar_item(fato, {"x": 1}),
                                      "palavras": rb.avaliar_item(fato, {"x": None})}},
        {"tipo": "fato", "metricas": {"pergunta": rb.avaliar_item(fato, {"x": 10})}},
        {"tipo": "armadilha", "metricas": {"pergunta": {"aplica": False}}},
    ]
    ag = rb.agregar(res)
    check("fato/pergunta n=2, acerto@5 50%", ag[("fato", "pergunta")]["n"] == 2 and ag[("fato", "pergunta")]["acerto5"] == 0.5)
    check("MRR (1 + 0,1)/2", abs(ag[("fato", "pergunta")]["mrr"] - 0.55) < 1e-9)
    check("variante ausente nao conta", ag[("fato", "palavras")]["n"] == 1)
    check("armadilha nao entra no TOTAL", ag[("TOTAL", "pergunta")]["n"] == 2)

    print("")
    if falhas:
        print("REGUA DE BUSCA: %d FALHA(S)" % len(falhas))
        return 1
    print("REGUA DE BUSCA OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
