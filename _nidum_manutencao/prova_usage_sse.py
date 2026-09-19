# -*- coding: ascii -*-
"""
Prova de `_usage_de_sse` e `_modelo_de_resposta` (chatnd.py, 1.67.2).

RECORTA as duas funcoes DO ARQUIVO e roda casos - nao ha copia aqui, entao a
prova nao envelhece separada do codigo (a licao do duble que divergiu em 16-09).
O pipe importa open_webui no topo e nao pode ser importado fora do container;
por isso o recorte, e por isso as duas sao funcoes PURAS de modulo.

Como rodar:  py _nidum_manutencao/prova_usage_sse.py
"""
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.join(AQUI, "..", "_nidum_tools", "chatnd.py")


def _recortar(fonte, nome):
    m = re.search(r"^def %s\(.*?(?=^def |^class |\Z)" % re.escape(nome), fonte, re.S | re.M)
    if not m:
        raise SystemExit("nao achei def %s em chatnd.py" % nome)
    return m.group(0)


with open(PIPE, "r", encoding="utf-8") as f:
    fonte = f.read()

ns = {"json": json}
exec(_recortar(fonte, "_usage_de_sse"), ns)
exec(_recortar(fonte, "_modelo_de_resposta"), ns)
usage_de_sse = ns["_usage_de_sse"]
modelo_de_resposta = ns["_modelo_de_resposta"]


def sse(*objs):
    return "".join("data: " + (o if isinstance(o, str) else json.dumps(o)) + "\n\n" for o in objs)


CASOS = [
    # (nome, entrada, esperado)
    ("chunk final da OpenAI (choices vazio, usage, model snapshot)",
     sse({"choices": [], "model": "gpt-5.1-2026-08-07",
          "usage": {"prompt_tokens": 51200, "completion_tokens": 830}}),
     (51200, 830, "gpt-5.1-2026-08-07")),
    ("chunks de texto sem usage -> nada",
     sse({"choices": [{"delta": {"content": "Ola"}}]}, {"choices": [{"delta": {"content": "!"}}]}),
     (None, None, None)),
    ("texto + usage no MESMO blob -> pega o usage",
     sse({"choices": [{"delta": {"content": "fim"}}]},
         {"choices": [], "model": "gpt-5-mini-2026-08-07", "usage": {"prompt_tokens": 10, "completion_tokens": 2}}, "[DONE]"),
     (10, 2, "gpt-5-mini-2026-08-07")),
    ("vocabulario Anthropic (input_/output_)",
     sse({"model": "claude-sonnet-5", "usage": {"input_tokens": 7, "output_tokens": 3}}),
     (7, 3, "claude-sonnet-5")),
    ("usage aninhado em response (Responses API convertida)",
     sse({"response": {"usage": {"input_tokens": 4, "output_tokens": 1}}, "model": "gpt-5.1"}),
     (4, 1, "gpt-5.1")),
    ("usage repetido em varios chunks -> o ULTIMO vence",
     sse({"usage": {"prompt_tokens": 1, "completion_tokens": 1}},
         {"usage": {"prompt_tokens": 9, "completion_tokens": 8}}),
     (9, 8, None)),
    ("usage com lixo (strings nao numericas) -> ignorado",
     sse({"usage": {"prompt_tokens": "x", "completion_tokens": None}}),
     (None, None, None)),
    ("JSON quebrado no meio nao derruba",
     "data: {isto nao e json\n\n" + sse({"usage": {"prompt_tokens": 5, "completion_tokens": 6}}),
     (5, 6, None)),
    ("usage zerado (0/0) CONTA como visto - e o motor dizendo zero",
     sse({"usage": {"prompt_tokens": 0, "completion_tokens": 0}}),
     (0, 0, None)),
    ("[DONE] sozinho", "data: [DONE]\n\n", (None, None, None)),
    ("vazio / None", None, (None, None, None)),
]

CASOS_MODELO = [
    ("dict com model", {"model": "gpt-5-mini-2026-08-07", "usage": {}}, "gpt-5-mini-2026-08-07"),
    ("dict sem model", {"usage": {}}, None),
    ("objeto com .body JSON", type("R", (), {"body": json.dumps({"model": "gpt-5.1"}).encode()})(), "gpt-5.1"),
    ("objeto com .body invalido", type("R", (), {"body": b"nao json"})(), None),
    ("None", None, None),
]

falhas = 0
for nome, entrada, esperado in CASOS:
    got = usage_de_sse(entrada)
    ok = got == esperado
    falhas += 0 if ok else 1
    print(("ok   " if ok else "FALHA") + "  " + nome + ("" if ok else "  -> %r (esperado %r)" % (got, esperado)))
for nome, entrada, esperado in CASOS_MODELO:
    got = modelo_de_resposta(entrada)
    ok = got == esperado
    falhas += 0 if ok else 1
    print(("ok   " if ok else "FALHA") + "  modelo: " + nome + ("" if ok else "  -> %r (esperado %r)" % (got, esperado)))

print("-" * 60)
print("%d caso(s), %d falha(s)" % (len(CASOS) + len(CASOS_MODELO), falhas))
sys.exit(1 if falhas else 0)
