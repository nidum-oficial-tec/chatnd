# -*- coding: ascii -*-
"""Avaliacoes dos USUARIOS (polegar) -> perguntas de teste (09/11/2026).

POR QUE: as baterias usam perguntas que NOS escrevemos. O polegar para baixo e
a unica pergunta real que um usuario disse que saiu ruim. Este script junta cada
avaliacao com a pergunta e a resposta avaliadas (lidas do chat) e grava no
formato das baterias ({"itens": [...]}), para rodar com bateria_agente.py.

So leitura (admin). Nao grava nome nem e-mail de quem avaliou: so as 8 primeiras
letras do id, para agrupar.

USO:
  py _nidum_avaliacao/avaliacoes_usuarios.py <saida.json> [--desde 2026-11-01] [--so-negativas]
"""
import argparse
import datetime
import io
import json
import os
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://chatnd.nidumbrasil.com.br"


def token():
    for l in io.open(os.path.join(RAIZ, ".env.local"), encoding="utf-8"):
        if l.strip().startswith("NIDUM_API_KEY="):
            return l.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("sem NIDUM_API_KEY no .env.local")


def api(tok, caminho):
    req = urllib.request.Request(URL + caminho, headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def pergunta_e_resposta(tok, chat_id, message_id):
    """A resposta avaliada e a pergunta do usuario logo antes dela."""
    try:
        chat = (api(tok, "/api/v1/chats/%s" % chat_id) or {}).get("chat") or {}
    except Exception:
        return "", ""
    msgs = (chat.get("history") or {}).get("messages") or {}
    m = msgs.get(message_id) or {}
    pai = msgs.get(m.get("parentId") or "") or {}
    return pai.get("content") or "", m.get("content") or ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("saida")
    ap.add_argument("--desde", default="")
    ap.add_argument("--so-negativas", action="store_true")
    a = ap.parse_args()
    tok = token()
    todas = api(tok, "/api/v1/evaluations/feedbacks/all/export") or []
    itens = []
    for f in sorted(todas, key=lambda x: x.get("created_at") or 0):
        d = f.get("data") or {}
        meta = f.get("meta") or {}
        dia = datetime.datetime.fromtimestamp(f.get("created_at") or 0, datetime.timezone.utc).strftime("%Y-%m-%d")
        if a.desde and dia < a.desde:
            continue
        if a.so_negativas and d.get("rating") != -1:
            continue
        perg, resp = pergunta_e_resposta(tok, meta.get("chat_id"), meta.get("message_id"))
        itens.append({
            "id": "U%02d" % (len(itens) + 1), "tipo": "usuario", "dia": dia,
            "nota_usuario": d.get("rating"), "motivo": d.get("reason") or "",
            "comentario": d.get("comment") or "", "modelo": d.get("model_id"),
            "quem": (f.get("user_id") or "")[:8], "pergunta": perg,
            "resposta_avaliada": resp[:4000],
            "usavel": bool(perg.strip()),
        })
    json.dump({"fonte": "avaliacoes dos usuarios", "itens": itens},
              io.open(a.saida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    neg = sum(1 for i in itens if i["nota_usuario"] == -1)
    print("%d avaliacoes (%d negativas); %d com pergunta recuperada -> %s"
          % (len(itens), neg, sum(1 for i in itens if i["usavel"]), a.saida))


if __name__ == "__main__":
    main()
