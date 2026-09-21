# -*- coding: ascii -*-
"""
BATERIA DO DECK - LADO PIPE. O outro lado da regua de _nidum_docs/13.

POR QUE ELA E UM SCRIPT SEPARADO E NAO UM MODO DA bateria_deck.py: os dois
lados nao devolvem a mesma coisa.

    AGENTE -> a ESTRUTURA (JSON) aparece no transcrito da tool, e a contagem
              sai do log da propria tool (fonte primaria).
    PIPE   -> devolve um LINK de download de .pptx. A estrutura nunca aparece:
              ela e consumida internamente (_gerar_arquivo -> _despachar_tool) e
              o pipe NAO loga a contagem. O unico lugar onde o resultado existe
              e o ARQUIVO.

Entao aqui a medicao e outra: baixa o .pptx e le com python-pptx. Isso tem uma
consequencia que precisa estar dita, porque ela limita a comparacao:

    o que se mede no agente e a ESTRUTURA PEDIDA;
    o que se mede no pipe e o ARQUIVO ENTREGUE.

Sao quase a mesma coisa - o gerador monta um slide por item - mas nao sao
identicas: o gerador pode recusar item malformado, e a capa/encerramento podem
entrar por conta dele. A diferenca e pequena e CONHECIDA; fingir que os dois
numeros tem a mesma natureza seria pior.

O PEDIDO e o mesmo conteudo que o agente passou a tool (os 7 blocos), SEM
mandar pesquisar o acervo - comparar com pedidos diferentes mediria a
diferenca de pedido, nao a de caminho.

USO:
  py -3 bateria_deck_pipe.py --n 5
  py -3 bateria_deck_pipe.py --ler arquivo.pptx    (so le um .pptx local)
"""

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.request

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(_AQUI)

URL = os.environ.get("NIDUM_URL", "https://chatnd.nidumbrasil.com.br")
MODELO = "chatnd"          # o PIPE

PEDIDO = (
    "Monte uma apresentacao institucional da Nidum para investidores, "
    "cobrindo: o que e a Nidum, o problema que resolve, o modelo de negocio, os "
    "produtos, o estagio atual dos projetos, a governanca e o convite final."
)


def token():
    if os.environ.get("NIDUM_TOKEN"):
        return os.environ["NIDUM_TOKEN"].strip()
    for l in io.open(os.path.join(_RAIZ, ".env.local"), encoding="utf-8", errors="replace"):
        if l.strip().startswith("NIDUM_API_KEY="):
            return l.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("sem NIDUM_API_KEY")


def api(p, d=None):
    c = None if d is None else json.dumps(d).encode("utf-8")
    r = urllib.request.Request(URL + p, data=c, method="POST" if c else "GET",
                               headers={"Authorization": "Bearer " + token(),
                                        "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=1800) as x:
        return json.loads(x.read().decode("utf-8"))


def baixar(url, destino):
    r = urllib.request.Request(url, headers={"Authorization": "Bearer " + token()})
    with urllib.request.urlopen(r, timeout=600) as x:
        dados = x.read()
    io.open(destino, "wb").write(dados)
    return len(dados)


def ler_pptx(caminho):
    """Devolve (n_slides, chars_de_corpo, [blocos legiveis por slide]).

    CORPO = todo texto do slide MENOS a primeira linha (o titulo). E a mesma
    definicao usada do lado do agente (o campo `texto`), para os dois numeros
    de densidade falarem da mesma coisa.
    """
    from pptx import Presentation
    pr = Presentation(caminho)
    slides, chars = [], 0
    for s in pr.slides:
        partes = []
        for sh in s.shapes:
            if not sh.has_text_frame:
                continue
            t = (sh.text_frame.text or "").strip()
            if t:
                partes.append(t)
        titulo = partes[0] if partes else ""
        corpo = "\n".join(partes[1:]) if len(partes) > 1 else ""
        chars += len(corpo)
        slides.append({"titulo": titulo, "corpo": corpo})
    return len(slides), chars, slides


def uma_execucao(i, pasta):
    chat = api("/api/v1/chats/new", {
        "chat": {"title": "pipe deck %d" % i, "models": [MODELO], "messages": [],
                 "history": {"messages": {}, "currentId": None}}})["id"]
    corpo = json.dumps({
        "model": MODELO,
        "messages": [{"role": "user", "content": PEDIDO}],
        "stream": True,
        "chat_id": chat,
        "id": "msg-pipe-%d-%d" % (i, int(time.time())),
    }).encode("utf-8")
    req = urllib.request.Request(
        URL + "/api/chat/completions", data=corpo, method="POST",
        headers={"Authorization": "Bearer " + token(),
                 "Content-Type": "application/json",
                 "Accept": "text/event-stream"})
    t0 = time.time()
    erro = ""
    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            for _ in resp:
                pass
    except Exception as e:
        erro = str(e)
        print("  (a requisicao caiu: %s - vou ler o chat mesmo assim)" % erro)
    seg = time.time() - t0

    ch = api("/api/v1/chats/%s" % chat)
    msgs = ((ch.get("chat") or {}).get("history") or {}).get("messages") or {}
    texto = ""
    for m in reversed(list(msgs.values())):
        if m.get("role") == "assistant" and m.get("content"):
            texto = m["content"]
            break
    m = re.search(r"(https?://\S+/api/v1/files/[0-9a-f-]+/content)", texto)
    e = {"i": i, "chat_id": chat, "segundos": round(seg, 1), "erro_http": erro,
         "resposta": texto[:400], "link": m.group(1) if m else None,
         "slides": 0, "chars_corpo": 0, "arquivo": None}
    if not m:
        print("  SEM LINK na resposta - o pipe nao gerou arquivo")
        return e
    destino = os.path.join(pasta, "pipe_%d.pptx" % i)
    n = baixar(m.group(1), destino)
    e["arquivo"] = destino
    e["bytes"] = n
    e["slides"], e["chars_corpo"], blocos = ler_pptx(destino)
    io.open(os.path.join(pasta, "pipe_%d.json" % i), "w", encoding="utf-8").write(
        json.dumps(blocos, ensure_ascii=False, indent=2))
    return e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--pasta", default=_AQUI)
    ap.add_argument("--ler", default=None)
    a = ap.parse_args()

    if a.ler:
        n, chars, blocos = ler_pptx(a.ler)
        print("slides=%d  chars_corpo=%d  densidade=%d" % (n, chars, chars // max(1, n)))
        return 0

    if not os.path.isdir(a.pasta):
        os.makedirs(a.pasta)
    execucoes = []
    for i in range(1, a.n + 1):
        print("[%d/%d] chamando o PIPE..." % (i, a.n))
        try:
            e = uma_execucao(i, a.pasta)
        except Exception as ex:
            print("  ERRO: %s" % ex)
            continue
        dens = e["chars_corpo"] // max(1, e["slides"])
        print("  %.0fs | slides=%d | chars_corpo=%d | densidade=%d"
              % (e["segundos"], e["slides"], e["chars_corpo"], dens))
        execucoes.append(e)
        io.open(os.path.join(a.pasta, "pipe_execucoes.json"), "w",
                encoding="utf-8").write(json.dumps(execucoes, ensure_ascii=False, indent=2))

    ns = sorted(e["slides"] for e in execucoes if e["slides"])
    ds = sorted(e["chars_corpo"] // max(1, e["slides"]) for e in execucoes if e["slides"])
    print("")
    print("=" * 66)
    print("LADO PIPE  (n=%d  <- o DENOMINADOR)" % len(execucoes))
    print("  slides por execucao ... %s" % ns)
    print("  MEDIANA de slides ..... %d" % (ns[len(ns) // 2] if ns else 0))
    print("  densidades ............ %s" % ds)
    print("  MEDIANA de densidade .. %d chars/slide" % (ds[len(ds) // 2] if ds else 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
