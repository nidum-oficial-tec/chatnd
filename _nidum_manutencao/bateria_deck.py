# -*- coding: ascii -*-
"""
BATERIA DO DECK - mede a estrutura que o agente produz, com e sem a tool.

O QUE SE MEDE, e a regua esta em _nidum_docs/13_Desenho_estruturar_deck_beta.md:

    mediana de slides     >= 80% do pipe (baseline 22) -> 18
    densidade             dentro de +-25% da do pipe (chars de corpo por slide)
    slides mudos          ZERO, para os tipos de _TIPOS_EXIGEM_CORPO

POR QUE CINCO EXECUCOES E NAO TRES: a variancia medida em 21/09 no mesmo
prompt, mesma pasta, foi de 57x (532 x 30.237 chars). Tres execucoes so
bastariam se a diferenca ENTRE os lados fosse muito maior que a variacao
DENTRO de cada lado, e 57x torna essa suposicao insustentavel ate prova em
contrario. Se as cinco vierem apertadas, o proximo par pode usar menos - com
o numero registrado.

CADA EXECUCAO E UMA CHAMADA PAGA, e das caras: o estagio dedicado usa gpt-5.1.

USO:
  py -3 bateria_deck.py --n 1              (uma execucao, para provar a fiacao)
  py -3 bateria_deck.py --n 5              (a bateria)
  py -3 bateria_deck.py --regua saida.json (so le, nao chama)
"""

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(_AQUI)

URL = os.environ.get("NIDUM_URL", "https://chatnd.nidumbrasil.com.br")
MODELO = os.environ.get("BATERIA_MODELO", "chatnd-agente-beta")
SERVICO = os.environ.get("RAILWAY_SERVICO", "ChatND")

# Baseline do pipe, medido antes desta bateria (ver o desenho).
PIPE_SLIDES = 22

# As tools que o turno recebe. Ver a nota em uma_execucao.
TOOL_IDS = ["estruturar_deck_beta", "gerador_de_arquivos_nidum"]

# _TIPOS_EXIGEM_CORPO do gerador_de_arquivos_nidum.py:1117. Slide desses tipos
# sem corpo e MUDO - falha, nao variacao.
TIPOS_EXIGEM_CORPO = ("conteudo", "destaque", "divisao", "numerada", "cartoes")

# Os aliases de corpo que o gerador aceita (o campo canonico e "texto").
CAMPOS_CORPO = ("texto", "corpo", "conteudo", "itens", "bullets", "cartoes")

# O PEDIDO INTEIRO estourou o gateway: 300,2s -> HTTP 502, chat com mensagem
# de 0 chars. O limite e de 5 MINUTOS na borda, e o tempo vai quase todo na
# varredura do acervo que o agente faz antes de estruturar.
#
# PARTIR O PEDIDO (decisao do Davi: tentar isto ANTES de mudar de caminho). A
# regua so precisa da ESTRUTURA - contagem de slides, densidade e slides mudos
# saem dela, nao do arquivo montado. Entao o turno 1 pede SO a estrutura, e a
# geracao do arquivo (que nao e medida) fica de fora. Menos busca, menos tempo,
# e o que se mede continua sendo o mesmo.
PEDIDO_PARTIDO = (
    # O NOME QUE O MODELO VE E O DO METODO (estruturar_deck), nao o id da tool
    # (estruturar_deck_beta) - o OWUI expoe a funcao, nao o pacote. Pedir pelo id
    # faz o modelo responder "essa ferramenta nao existe" e OFERECER a certa,
    # o que parece falha de publicacao e e so o nome errado no pedido.
    "Use a ferramenta estruturar_deck AGORA, de uma vez, para montar a "
    "estrutura de uma apresentacao institucional da Nidum para investidores, "
    "cobrindo: o que e a Nidum, o problema que resolve, o modelo de negocio, os "
    "produtos, o estagio atual dos projetos, a governanca e o convite final. "
    "NAO pesquise no acervo antes - passe o pedido direto para a ferramenta, que "
    "ela cuida do conteudo. Depois me diga apenas quantos slides ela devolveu. "
    "NAO gere o arquivo."
)

PEDIDO_INTEIRO = (
    "Monte uma apresentacao institucional da Nidum para investidores. "
    "Cubra: o que e a Nidum, o problema que ela resolve, o modelo de negocio, "
    "os produtos, o estagio atual dos projetos, a governanca e o convite final. "
    "Use o material do acervo. Quero um deck completo, com profundidade em cada "
    "tema - nao um resumo."
)


def token():
    if os.environ.get("NIDUM_TOKEN"):
        return os.environ["NIDUM_TOKEN"].strip()
    caminho = os.path.join(_RAIZ, ".env.local")
    for linha in io.open(caminho, encoding="utf-8", errors="replace"):
        if linha.strip().startswith("NIDUM_API_KEY="):
            return linha.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("sem NIDUM_API_KEY em %s" % caminho)


def api(caminho, dados=None):
    corpo = None if dados is None else json.dumps(dados).encode("utf-8")
    req = urllib.request.Request(
        URL.rstrip("/") + caminho, data=corpo,
        method="POST" if corpo else "GET",
        headers={"Authorization": "Bearer " + token(),
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read().decode("utf-8"))


def log_do_railway(n=600):
    """Le o log. Caminho absoluto e cwd do diretorio LINKADO - ver a nota
    equivalente em bateria_orcamento.py; os dois defeitos de Windows sao os
    mesmos e ja custaram uma medicao."""
    exe = shutil.which("railway") or shutil.which("railway.cmd") or "railway"
    try:
        # encoding/errors EXPLICITOS: sem eles o Python usa cp1252 no Windows e
        # o log do Railway (que tem acento e emoji) levanta UnicodeDecodeError
        # DENTRO da thread de leitura - erro que aparece como ruido e nao
        # derruba o processo, mas devolve log vazio.
        o = subprocess.run([exe, "logs", "--service", SERVICO, "--lines", str(n)],
                           capture_output=True, text=True, timeout=180, cwd=_RAIZ,
                           encoding="utf-8", errors="replace")
        if o.returncode != 0 and o.stderr:
            print("  (railway rc=%s: %s)" % (o.returncode, o.stderr.strip()[:160]))
        return (o.stdout or "").splitlines()
    except Exception as e:
        print("  (railway falhou: %s)" % e)
        return []


def novo_chat(titulo):
    return api("/api/v1/chats/new", {
        "chat": {"title": titulo, "models": [MODELO], "messages": [],
                 "history": {"messages": {}, "currentId": None}},
    })["id"]


def resposta_do_chat(chat_id):
    """O conteudo persistido, SEM o transcrito das tool calls.

    A `content` do chat inclui blocos <details type="tool_calls"> com a saida
    crua embutida - medido em 21/09: uma resposta de 235 chars aparecia como
    159.239. Tirar os blocos e o que separa a resposta do envelope.
    """
    try:
        ch = api("/api/v1/chats/%s" % chat_id)
        msgs = ((ch.get("chat") or {}).get("history") or {}).get("messages") or {}
        bruto = ""
        for m in reversed(list(msgs.values())):
            if m.get("role") == "assistant" and m.get("content"):
                bruto = m["content"]
                break
        prosa = re.sub(r"<details.*?</details>", "", bruto, flags=re.S).strip()
        return bruto, prosa
    except Exception as e:
        print("  (nao consegui ler o chat: %s)" % e)
        return "", ""


def _slides_do_bruto(bruto):
    """Acha a estrutura devolvida pela tool dentro do transcrito.

    A saida da estruturar_deck_beta aparece no bloco <details> da tool; e o
    unico lugar onde a estrutura COMPLETA existe (o gerador consome e devolve
    um link). Procura o maior JSON com 'slides'.
    """
    # O TRANSCRITO VEM HTML-ESCAPADO. O conteudo do chat guarda a saida da tool
    # dentro de <details ...>, com &quot; no lugar das aspas e mais uma camada de
    # escape do JSON: `\&quot;slides\&quot;`. Procurar por `"slides"` com aspas
    # de verdade nao acha NADA - e o resultado sai 0 slides com a tool tendo
    # funcionado, que e o pior formato de erro possivel (numero plausivel,
    # fenomeno ausente). Desescapa antes de procurar.
    bruto = (bruto.replace("&quot;", '"').replace("&amp;", "&")
             .replace("&lt;", "<").replace("&gt;", ">").replace('\\"', '"'))
    melhor = None
    for m in re.finditer(r'\{[^{}]*"slides"\s*:\s*\[', bruto):
        i = m.start()
        # varre ate fechar as chaves
        nivel, j, dentro, esc = 0, i, False, False
        while j < len(bruto):
            c = bruto[j]
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                dentro = not dentro
            elif not dentro:
                if c == "{":
                    nivel += 1
                elif c == "}":
                    nivel -= 1
                    if nivel == 0:
                        break
            j += 1
        trecho = bruto[i:j + 1]
        try:
            d = json.loads(trecho.replace("\\n", "\n").replace('\\"', '"'))
        except Exception:
            try:
                d = json.loads(trecho)
            except Exception:
                continue
        if isinstance(d, dict) and isinstance(d.get("slides"), list):
            if melhor is None or len(d["slides"]) > len(melhor["slides"]):
                melhor = d
    return melhor


def _corpo_de(slide):
    for k in CAMPOS_CORPO:
        v = slide.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, list) and v:
            return " ".join(str(x) for x in v)
    return ""


def avaliar(estrutura):
    """Devolve (n_slides, densidade, mudos) - a regua, sem julgamento."""
    if not estrutura:
        return 0, 0, []
    slides = estrutura.get("slides") or []
    corpos = [_corpo_de(s) for s in slides]
    chars = sum(len(c) for c in corpos)
    mudos = [i + 1 for i, s in enumerate(slides)
             if (s.get("tipo") or "conteudo").lower() in TIPOS_EXIGEM_CORPO
             and not corpos[i]]
    dens = (chars // len(slides)) if slides else 0
    return len(slides), dens, mudos


def uma_execucao(i, pedido=None):
    pedido = pedido or PEDIDO_PARTIDO
    chat_id = novo_chat("deck beta %d" % i)
    corpo = json.dumps({
        "model": MODELO,
        "messages": [{"role": "user", "content": pedido}],
        "stream": True,
        "chat_id": chat_id,
        "id": "msg-deck-%d-%d" % (i, int(time.time())),
        "params": {"function_calling": "native"},
        # TERCEIRA PORTA DA API, medida em 21/09 - e a familia das outras duas
        # (stream:false e chat_id/id). O `toolIds` do PRESET e aplicado pela
        # INTERFACE, nao pelo backend:
        #     Chat.svelte:347   if (model?.info?.meta?.toolIds) {
        #     Chat.svelte:2449  tool_ids: toolIds.length > 0 ? toolIds : undefined
        #     middleware:2671   tool_ids = form_data.pop("tool_ids", None)
        # Quem chama pela API e manda so o `model` NAO recebe tool de usuario
        # nenhuma - nem as que estao anexadas ao preset. O sintoma e educado e
        # enganoso: o agente responde "nao tenho acesso a nenhuma ferramenta
        # chamada X" e LISTA as builtin, o que parece problema de publicacao ou
        # de permissao. Nao e: e o corpo da requisicao.
        "tool_ids": TOOL_IDS,
    }).encode("utf-8")
    req = urllib.request.Request(
        URL.rstrip("/") + "/api/chat/completions", data=corpo, method="POST",
        headers={"Authorization": "Bearer " + token(),
                 "Content-Type": "application/json",
                 "Accept": "text/event-stream"})
    t0 = time.time()
    # 502 NAO E CRASH DA INSTANCIA, e corte do gateway numa requisicao longa
    # (medido em 21/09: a instancia seguia em 200 nas outras rotas e o log nao
    # tinha traceback). O turno pode ter progredido no servidor mesmo assim,
    # entao a resposta e lida do CHAT de qualquer jeito - e o que estiver la
    # vale. Sem isto, um 502 descartava uma chamada paga que talvez tenha
    # produzido a estrutura inteira.
    erro = ""
    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            for _ in resp:
                pass
    except Exception as e:
        erro = str(e)
        print("  (a requisicao caiu: %s - vou ler o chat mesmo assim)" % erro)
    seg = time.time() - t0
    bruto, prosa = resposta_do_chat(chat_id)
    est = _slides_do_bruto(bruto)
    n, dens, mudos = avaliar(est)
    return {
        "i": i, "chat_id": chat_id, "segundos": round(seg, 1), "erro_http": erro,
        "chars_bruto": len(bruto), "chars_prosa": len(prosa),
        "slides": n, "densidade": dens, "mudos": mudos,
        # NAO basta procurar o nome no texto: ele aparece no ECO do pedido e
        # deu FALSO POSITIVO em 21/09 (usou_tool=True com zero chamadas). O
        # marcador de uma chamada de verdade e o bloco <details name="...">.
        # O atributo `name=` traz o METODO (estruturar_deck), nao o id da tool.
        "usou_tool": 'name="estruturar_deck"' in bruto,
        "estrutura": est,
    }


def regua(execucoes):
    ns = sorted(e["slides"] for e in execucoes if e["slides"])
    ds = sorted(e["densidade"] for e in execucoes if e["slides"])
    med = ns[len(ns) // 2] if ns else 0
    med_d = ds[len(ds) // 2] if ds else 0
    alvo = int(PIPE_SLIDES * 0.8 + 0.999)
    mudos = sum(len(e["mudos"]) for e in execucoes)
    print("")
    print("=" * 66)
    print("A REGUA  (n=%d execucoes  <- o DENOMINADOR)" % len(execucoes))
    print("  slides por execucao ... %s" % ns)
    print("  MEDIANA ............... %d   (alvo: >= %d, 80%% dos %d do pipe)"
          % (med, alvo, PIPE_SLIDES))
    print("  densidade mediana ..... %d chars/slide" % med_d)
    print("  slides MUDOS .......... %d   (alvo: 0)" % mudos)
    print("  usaram a tool ......... %d de %d"
          % (sum(1 for e in execucoes if e["usou_tool"]), len(execucoes)))
    multi = [e for e in execucoes if (e.get("chamadas_tool") or 0) > 1]
    if multi:
        print("  chamaram a tool 2x+ ... %d de %d  (execucoes %s)"
              % (len(multi), len(execucoes), [e["i"] for e in multi]))
    div = [e for e in execucoes
           if e.get("slides_log") is not None
           and e.get("slides_extraido") != e.get("slides_log")]
    if div:
        print("  parser divergiu ....... %d de %d  (valeu o log)"
              % (len(div), len(execucoes)))
    print("")
    print("  [%s] mediana >= %d" % ("OK " if med >= alvo else "NAO", alvo))
    print("  [%s] zero slides mudos" % ("OK " if mudos == 0 else "NAO"))
    print("")
    print("  NOTA: a densidade so vira veredito com a do pipe ao lado - ela e")
    print("        relativa (+-25%), e o baseline de densidade ainda NAO foi")
    print("        medido. O de slides (22) foi.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--saida", default=None)
    ap.add_argument("--regua", default=None)
    ap.add_argument("--inteiro", action="store_true",
                    help="o pedido completo (estourou o gateway em 21/09)")
    a = ap.parse_args()

    if a.regua:
        return regua(json.load(io.open(a.regua, encoding="utf-8")))

    saida = a.saida or os.path.join(_AQUI, "deck_execucoes.json")
    antes = set(log_do_railway())
    execucoes = []
    for i in range(1, a.n + 1):
        print("[%d/%d] chamando o agente..." % (i, a.n))
        try:
            e = uma_execucao(i, PEDIDO_INTEIRO if a.inteiro else PEDIDO_PARTIDO)
        except Exception as ex:
            print("  ERRO: %s" % ex)
            continue
        novas = [l for l in log_do_railway() if l not in antes]
        antes.update(novas)
        e["log_tool"] = [l for l in novas if "estruturar_deck_beta" in l]

        # O LOG DA TOOL E A FONTE PRIMARIA DA CONTAGEM (decisao do Davi, 21/09).
        # O transcrito do chat vem HTML-escapado e com uma segunda camada de
        # escape do JSON; o parser acertou 3 de 5 e devolveu ZERO nas outras
        # duas - com a tool tendo funcionado nas cinco. Zero que significa "nao
        # consegui extrair" e o pior formato de erro possivel, e ja custou uma
        # medicao hoje. A tool, por outro lado, REGISTRA o que produziu:
        #     estruturar_deck_beta: estrutura com 30 item(ns), modelo=gpt-5.1
        # Esse numero nao passa por escape nenhum. O extraido fica AO LADO, como
        # conferencia - quando os dois divergem, quem manda e o log, e a
        # divergencia aparece em vez de sumir.
        registrados = [int(x) for x in
                       re.findall(r"estrutura com (\d+) item", " ".join(e["log_tool"]))]
        e["slides_log"] = max(registrados) if registrados else None
        e["slides_extraido"] = e["slides"]
        e["chamadas_tool"] = len(registrados)
        if e["slides_log"] is not None:
            if e["slides_extraido"] != e["slides_log"]:
                print("     (divergencia: extraido=%s, log=%s -> vale o LOG)"
                      % (e["slides_extraido"], e["slides_log"]))
            e["slides"] = e["slides_log"]
        print("  %.0fs | slides=%d | densidade=%d | mudos=%d | usou a tool: %s"
              % (e["segundos"], e["slides"], e["densidade"], len(e["mudos"]),
                 e["usou_tool"]))
        for l in e["log_tool"][:3]:
            print("     log: %s" % l.strip()[-120:])
        execucoes.append(e)
        io.open(saida, "w", encoding="utf-8").write(
            json.dumps(execucoes, ensure_ascii=False, indent=2))
    print("")
    print("gravado: %s" % saida)
    if execucoes:
        regua(execucoes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
