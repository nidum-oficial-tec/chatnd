# -*- coding: utf-8 -*-
"""Roda as 12 perguntas da bateria contra o AGENTE `chatnd` (ponta a ponta).
Mesmo jeito de chamar da bateria_orcamento (D88): stream, chat_id real, id,
function_calling native. Sem pasta e sem '#': o caminho de um usuario comum.
Grava, por pergunta: resposta, consultas que o agente mandou, n de chamadas,
latencia. So leitura alem dos chats criados (titulo 'medicao regua <id>')."""
import html, io, json, os, re, sys, time, urllib.request

RAIZ = r"C:\Users\daviv\Dev\1-nidum\chatnd\interface-chatnd"
URL = "https://chatnd.nidumbrasil.com.br"
MODELO = "chatnd"
IDS = "L01,L02,L04,R01,R03,R06,T01,T02,F02,F09,E03,A03".split(",")
SAIDA = sys.argv[1]


def token():
    for l in io.open(os.path.join(RAIZ, ".env.local"), encoding="utf-8"):
        if l.strip().startswith("NIDUM_API_KEY="):
            return l.split("=", 1)[1].strip().strip('"').strip("'")


TOK = token()


def api(c, d=None):
    req = urllib.request.Request(URL + c, data=None if d is None else json.dumps(d).encode(),
                                 method="POST" if d is not None else "GET",
                                 headers={"Authorization": "Bearer " + TOK, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))


def um(item):
    t0 = time.time()
    chat = api("/api/v1/chats/new", {"chat": {"title": "medicao regua %s" % item["id"], "models": [MODELO],
                                              "messages": [], "history": {"messages": {}, "currentId": None}}})
    cid, mid = chat["id"], "msg-regua-%s-%d" % (item["id"], int(time.time()))
    corpo = json.dumps({"model": MODELO, "messages": [{"role": "user", "content": item["pergunta"]}],
                        "stream": True, "chat_id": cid, "id": mid,
                        "params": {"function_calling": "native"}}).encode()
    req = urllib.request.Request(URL + "/api/chat/completions", data=corpo, method="POST",
                                 headers={"Authorization": "Bearer " + TOK, "Content-Type": "application/json",
                                          "Accept": "text/event-stream"})
    partes, n_tc = [], 0
    with urllib.request.urlopen(req, timeout=1800) as r:
        for b in r:
            l = b.decode("utf-8", "replace").strip()
            if not l.startswith("data:"):
                continue
            d = l[5:].strip()
            if d == "[DONE]":
                break
            try:
                ev = json.loads(d)
            except Exception:
                continue
            for ch in ev.get("choices") or []:
                dd = ch.get("delta") or {}
                if dd.get("content"):
                    partes.append(dd["content"])
                if dd.get("tool_calls"):
                    n_tc += len(dd["tool_calls"])
    seg = round(time.time() - t0, 1)
    texto = ""
    for _ in range(10):  # a persistencia pode atrasar uns segundos
        ch = api("/api/v1/chats/%s" % cid)
        msgs = ((ch.get("chat") or {}).get("history") or {}).get("messages") or {}
        m = msgs.get(mid) or next((x for x in msgs.values() if x.get("role") == "assistant"), {})
        texto = m.get("content") or ""
        if texto and m.get("done", True):
            break
        time.sleep(3)
    texto = texto or "".join(partes)
    # chamadas de ferramenta ficam no conteudo como <details type="tool_calls" name=.. arguments=..>
    chamadas = []
    for tag in re.findall(r'<details type="tool_calls"[^>]*>', texto):
        nome = re.search(r'name="([^"]*)"', tag)
        args = re.search(r'arguments="([^"]*)"', tag)
        chamadas.append({"ferramenta": nome.group(1) if nome else "?",
                         "args": html.unescape(args.group(1)) if args else ""})
    final = re.sub(r"<details.*?</details>", "", texto, flags=re.S).strip()
    return {"id": item["id"], "tipo": item["tipo"], "pergunta": item["pergunta"],
            "resposta_esperada": item.get("resposta_esperada"), "ouro": item.get("ouro"),
            "chat_id": cid, "latencia_s": seg, "n_tool_calls_sse": n_tc,
            "chamadas": chamadas, "resposta": final}


gab = json.load(io.open(os.path.join(RAIZ, "_nidum_avaliacao", "gabarito_busca.json"), encoding="utf-8"))
itens = [i for i in gab["itens"] if i["id"] in IDS]
out = []
for n, it in enumerate(itens, 1):
    try:
        r = um(it)
    except Exception as e:
        r = {"id": it["id"], "erro": str(e)[:300]}
    out.append(r)
    print("[%d/%d] %s %ss chamadas=%s" % (n, len(itens), it["id"], r.get("latencia_s"), len(r.get("chamadas", []))), flush=True)
    io.open(SAIDA, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
    time.sleep(2)
print("ok")
