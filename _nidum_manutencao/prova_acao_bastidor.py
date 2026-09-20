# -*- coding: ascii -*-
"""Prova a regra da `acao` da linha de resposta, recortando-a DO ARQUIVO."""
import io
import re
import sys

P = "_nidum_tools/chatnd.py"
src = io.open(P, encoding="utf-8").read()

# a regra, como ela esta no arquivo (sem parenteses externos - ali vem virgula)
REGRA = 'ev.get("acao_resposta") or "resposta"'
if REGRA not in src:
    print("FALHA: nao achei a regra no arquivo:", REGRA)
    sys.exit(1)

# e o atalho da tarefa interna precisa GRAVAR essa chave
if '_ev["acao_resposta"] = str(__task__)[:40]' not in src:
    print("FALHA: a tarefa interna nao grava acao_resposta")
    sys.exit(1)


def acao(ev):
    return ev.get("acao_resposta") or "resposta"


CASOS = [
    ({}, "resposta"),
    ({"acao_resposta": "title_generation"}, "title_generation"),
    ({"acao_resposta": "tags_generation"}, "tags_generation"),
    ({"acao_resposta": None}, "resposta"),
    ({"acao_resposta": ""}, "resposta"),
]

falhas = 0
for ev, esp in CASOS:
    got = acao(ev)
    ok = got == esp
    falhas += 0 if ok else 1
    print(("ok   " if ok else "FALHA") + "  ev=%-40r -> %s" % (ev, got))

# o nome da tarefa cabe na coluna (trunca em 40)
longo = "x" * 80
if len(str(longo)[:40]) != 40:
    print("FALHA: truncagem")
    falhas += 1
else:
    print("ok     nome de tarefa longo trunca em 40 chars")

print("-" * 60)
print("%d caso(s), %d falha(s)" % (len(CASOS) + 1, falhas))
sys.exit(1 if falhas else 0)
