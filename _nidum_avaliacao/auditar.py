# -*- coding: ascii -*-
"""
AUDITOR de outra familia de modelo para as respostas do ChatND (08/11/2026).

POR QUE EXISTE: o ChatND responde com Claude (preset `chatnd` -> claude-opus).
Um juiz da mesma familia tende a gostar do proprio estilo. Este auditor usa o
GPT (modelo-base `gpt-5.1` do proprio Open WebUI: mesma chave das baterias,
nenhum segredo novo) e da a nota com as MESMAS categorias do juiz Claude, para
as duas notas serem comparaveis. Onde os dois discordam, decide uma pessoa.

ENTRADA:
  --perguntas  {"itens": [{"id", "pergunta", "resposta_esperada", ...}]}
  --respostas  saida do bateria_agente.py (lista com "id" e "resposta")
  --fontes     pasta com os textos-fonte; o item aponta o arquivo em "doc"
               (perguntas cegas) ou "grupo" (perguntas cruzadas)
  --saida      json de notas

USO:
  py _nidum_avaliacao/auditar.py --perguntas P.json --respostas R.json --fontes DIR --saida N.json
  py _nidum_avaliacao/auditar.py ... --comparar notas_do_outro_juiz.json
"""

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://chatnd.nidumbrasil.com.br"
MODELO = os.environ.get("AUDITOR_MODELO", "gpt-5.1")
NOTAS = ["certo", "parcial", "errado", "nao_achou_honesto", "inventou"]
MAX_FONTE = 40000

INSTRUCAO = (
    "Voce e um auditor imparcial de um assistente de chat interno de uma empresa (Nidum). "
    "Avalie a RESPOSTA DO ASSISTENTE contra a FONTE (os documentos sao a verdade; a resposta "
    "esperada e um guia). Seja estrito e literal; nao de credito a respostas vagas.\n"
    "CRITERIO DA EMPRESA (Davi, 08/11/2026): o TITULO de uma reuniao/documento pode contar como certo "
    "numa listagem simples; quando a pergunta pede detalhes (andamento, decisoes, conteudo, explicacao), a "
    "resposta precisa refletir o CONTEUDO do documento, nao so o titulo. Pedido de MATERIAL: certo = aponta o "
    "arquivo certo (versao/data quando pedido). Pedido para GERAR algo: certo = produziu arquivo/link com "
    "conteudo fiel a fonte; sem arquivo, no maximo parcial.\n"
    "Notas possiveis:\n"
    "- certo: responde corretamente; o fato central bate com a fonte. Para listas: todos os itens "
    "obrigatorios presentes, nada inventado. Para 'versao mais recente': nomeia a versao/data mais nova.\n"
    "- parcial: direcao certa mas incompleto, impreciso, lista faltando itens, ou um de dois fatos faltando.\n"
    "- errado: fato central errado, responde outra coisa, ou diz que nao existe quando existe.\n"
    "- nao_achou_honesto: diz que nao encontrou, sem inventar.\n"
    "- inventou: apresenta como reais fatos/itens que nao estao na fonte NEM nos documentos que o assistente abriu.\n"
    "Detalhes ADICIONAIS que nao contradizem a fonte e que voce nao consegue verificar NAO rebaixam a nota "
    "(o assistente consulta a base inteira); rebaixe so se o adicional CONTRADIZ a fonte ou se falta algo pedido.\n"
    "Responda SO com um JSON numa linha: "
    "{\"nota\": \"<uma das notas>\", \"cobertura\": \"k/n ou vazio\", \"justificativa\": \"uma frase\"}"
)


def token():
    for l in io.open(os.path.join(RAIZ, ".env.local"), encoding="utf-8"):
        if l.strip().startswith("NIDUM_API_KEY="):
            return l.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("sem NIDUM_API_KEY no .env.local")


def chamar(tok, mensagens):
    corpo = json.dumps({"model": MODELO, "messages": mensagens, "stream": False}).encode("utf-8")
    req = urllib.request.Request(URL + "/api/chat/completions", data=corpo, method="POST",
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read().decode("utf-8"))
    return (d.get("choices") or [{}])[0].get("message", {}).get("content") or "", d.get("usage") or {}


def lidos_pelo_assistente(tok, resposta, limite=12000):
    """Texto dos arquivos que o assistente ABRIU (view/grep com file_id).

    POR QUE (medido em 08/11): o juiz GPT marcou como "inventados" detalhes
    da C11 que estavam certos - o documento sorteado era um INDICE que cita a
    nota, e o ChatND abriu a nota de verdade. Julgar so contra a fonte sorteada
    pune quem achou um documento melhor. Com o que ele leu ao lado, detalhe vindo
    de outro documento real deixa de parecer invencao."""
    ids = []
    for c in resposta.get("chamadas") or []:
        for fid in re.findall(r'"file_id":\s*"([0-9a-f-]{36})"', c.get("args") or ""):
            if fid not in ids:
                ids.append(fid)
    partes = []
    for fid in ids[:4]:
        try:
            req = urllib.request.Request(URL + "/api/v1/files/%s/data/content" % fid,
                                         headers={"Authorization": "Bearer " + tok})
            with urllib.request.urlopen(req, timeout=60) as r:
                txt = (json.loads(r.read().decode("utf-8")) or {}).get("content", "")
            partes.append("--- arquivo lido pelo assistente (%s) ---\n%s" % (fid, txt[:limite]))
        except Exception:
            continue
    return "\n\n".join(partes)


def extrair_json(texto):
    m = re.search(r"\{.*\}", texto or "", re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except ValueError:
        return None
    return j if j.get("nota") in NOTAS else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perguntas", required=True)
    ap.add_argument("--respostas", required=True)
    ap.add_argument("--fontes", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--comparar", default=None, help="notas de outro juiz ({'itens':[{'id','nota'}]})")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    perg = {i["id"]: i for i in json.load(io.open(a.perguntas, encoding="utf-8"))["itens"]}
    resp = {r["id"]: r for r in json.load(io.open(a.respostas, encoding="utf-8")) if "resposta" in r}
    tok = token()
    saida = []
    for pid in sorted(resp):
        p = perg.get(pid)
        if not p:
            continue
        nome_fonte = p.get("doc") or p.get("grupo") or ""
        caminho = os.path.join(a.fontes, nome_fonte)
        fonte = io.open(caminho, encoding="utf-8").read()[:MAX_FONTE] if os.path.exists(caminho) else "(fonte indisponivel)"
        extra = ""
        if p.get("evidencia"):
            extra += "\nTRECHO DE EVIDENCIA: " + p["evidencia"]
        if p.get("ouro"):
            extra += "\nITENS/DOCUMENTOS OBRIGATORIOS: " + "; ".join(p["ouro"])
        if p.get("como_conferir"):
            extra += "\nCOMO CONFERIR: " + p["como_conferir"]
        lidos = lidos_pelo_assistente(tok, resp[pid])
        msg = ("PERGUNTA: %s\n\nRESPOSTA ESPERADA: %s%s\n\nFONTE:\n%s\n\n"
               "DOCUMENTOS QUE O ASSISTENTE ABRIU (tambem sao verdade; um detalhe que esta aqui nao e invencao):\n%s"
               "\n\nRESPOSTA DO ASSISTENTE:\n%s"
               % (p["pergunta"], p.get("resposta_esperada", ""), extra, fonte, lidos or "(nenhum)",
                  resp[pid]["resposta"]))
        t0 = time.time()
        nota, uso = None, {}
        for _ in range(2):
            try:
                txt, uso = chamar(tok, [{"role": "system", "content": INSTRUCAO}, {"role": "user", "content": msg}])
                nota = extrair_json(txt)
            except Exception as e:
                txt = "ERRO %s" % e
            if nota:
                break
        item = {"id": pid, "nota": (nota or {}).get("nota", "sem_nota"),
                "cobertura": (nota or {}).get("cobertura", ""),
                "justificativa": (nota or {}).get("justificativa", txt[:200]),
                "segundos": round(time.time() - t0, 1), "uso": uso}
        saida.append(item)
        print("%s %-18s %s" % (pid, item["nota"], item["justificativa"][:110]), flush=True)

    tot = {n: sum(1 for i in saida if i["nota"] == n) for n in NOTAS + ["sem_nota"]}
    res = {"auditor": MODELO, "itens": saida, "totais": tot}
    if a.comparar:
        outro = {i["id"]: i["nota"] for i in json.load(io.open(a.comparar, encoding="utf-8"))["itens"]}
        pares = [(i["id"], i["nota"], outro.get(i["id"])) for i in saida if outro.get(i["id"])]
        iguais = [p for p in pares if p[1] == p[2]]
        res["comparacao"] = {"concordam": len(iguais), "total": len(pares),
                             "divergem": [{"id": x, "este": y, "outro": z} for x, y, z in pares if y != z]}
        print("\nconcordam %d de %d; divergem: %s" % (len(iguais), len(pares), res["comparacao"]["divergem"]))
    print("totais:", tot)
    json.dump(res, io.open(a.saida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
