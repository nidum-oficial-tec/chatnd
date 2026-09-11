# -*- coding: ascii -*-
"""Provas OFFLINE da simulacao e do carimbo (sem rede, sem painel).

O `simular` recebe o transporte (`http`) como argumento justamente para poder
ser provado sem o ChatND no ar: aqui o http e uma funcao de mentira que devolve
o que o teste quiser. O que sobra sem prova e o POST de verdade - que e uma
linha e nao mudou neste PR.
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _publicar_comum import (carimbo_de_origem, descricao_com_carimbo,
                             publicado_atual, simular)

CAB = '"""\ntitle: X\nversion: %s\ndescription: y\n"""\n'


def fonte(versao, corpo=""):
    return (CAB % versao) + corpo


def versao_de(t):
    import re
    m = re.search(r"(?im)^\s*version\s*:\s*(.+)$", t or "")
    return m.group(1).strip() if m else ""


def http_funcao(conteudo=None, status=200):
    """Um /api/v1/functions/id/{id} de mentira."""
    def _h(metodo, url, token, payload=None):
        if status != 200:
            return status, ""
        return 200, json.dumps({"id": "chatnd", "content": conteudo})
    return _h


def http_tools(lista, status=200):
    def _h(metodo, url, token, payload=None):
        if status != 200:
            return status, ""
        return 200, json.dumps(lista)
    return _h


FALHAS = []


def checa(nome, cond, extra=""):
    if cond:
        print("  ok   %s" % nome)
    else:
        print("  FALHA %s %s" % (nome, extra))
        FALHAS.append(nome)


def rodar(*a, **k):
    """Roda `simular` capturando o que ele imprime. (rc, texto)."""
    antigo, buf = sys.stdout, io.StringIO()
    sys.stdout = buf
    try:
        rc = simular(*a, **k)
    finally:
        sys.stdout = antigo
    return rc, buf.getvalue()


def main():
    print("teste_publicar_comum")
    mesmo = fonte("1.65.0", "x = 1\n")

    # 1. Publicado identico ao local -> nao ha o que mudar.
    rc, t = rodar(http_funcao(mesmo), "http://b", "t", "funcao", "chatnd",
                  mesmo, "1.65.0", versao_de)
    checa("identico = IDENTICO, rc 0", rc == 0 and "IDENTICO" in t, t)

    # 2. Conteudo diferente -> conta as linhas e AVISA que substitui.
    rc, t = rodar(http_funcao(fonte("1.64.0", "x = 1\n")), "http://b", "t",
                  "funcao", "chatnd", fonte("1.65.0", "x = 2\ny = 3\n"),
                  "1.65.0", versao_de)
    checa("diferente = VAI MUDAR", rc == 0 and "VAI MUDAR" in t, t)
    checa("diz que SUBSTITUI", "SUBSTITUI" in t, t)

    # 3. O CASO DE 11/09: mesma versao dos dois lados, conteudo diferente.
    #    Avisa - e NAO bloqueia (o primeiro publish do conserto cai aqui).
    rc, t = rodar(http_funcao(fonte("1.65.0", "x = 1\n")), "http://b", "t",
                  "funcao", "chatnd", fonte("1.65.0", "x = 2\n"),
                  "1.65.0", versao_de)
    checa("mesma versao + conteudo diferente = AVISA", "ATENCAO" in t, t)
    checa("...e NAO bloqueia (rc 0)", rc == 0, rc)

    # 4. Nao existe no painel -> e criacao, nao divergencia.
    rc, t = rodar(http_funcao(None, status=404), "http://b", "t", "funcao",
                  "chatnd", mesmo, "1.65.0", versao_de)
    checa("404 = CRIA, rc 0", rc == 0 and "CRIA" in t, t)

    # 5. NAO CONSEGUI OLHAR nunca vira "esta igual", e tem codigo proprio.
    rc, t = rodar(http_funcao(None, status=500), "http://b", "t", "funcao",
                  "chatnd", mesmo, "1.65.0", versao_de)
    checa("HTTP 500 = nao consegui olhar, rc 4",
          rc == 4 and "NAO CONSEGUI OLHAR" in t, t)
    checa("...e NAO diz identico", "IDENTICO" not in t, t)

    # 6. Tool vem do /export (e nao de /tools/id/{id}, que nao tem content).
    rc, t = rodar(http_tools([{"id": "outra", "content": "z"},
                              {"id": "ger", "content": mesmo}]),
                  "http://b", "t", "tool", "ger", mesmo, "1.65.0", versao_de)
    checa("tool identica pelo /export", rc == 0 and "IDENTICO" in t, t)

    # 7. Tool ausente do export = publish novo.
    rc, t = rodar(http_tools([{"id": "outra", "content": "z"}]),
                  "http://b", "t", "tool", "ger", mesmo, "1.65.0", versao_de)
    checa("tool ausente = CRIA", rc == 0 and "CRIA" in t, t)

    # 8. Tool no export SEM content: nao da para comparar - e nao e "igual".
    f, motivo = publicado_atual(http_tools([{"id": "ger", "content": ""}]),
                                "http://b", "t", "tool", "ger")
    checa("export sem content = None + motivo", f is None and motivo, (f, motivo))

    # 9. Carimbo: no Actions sai o sha; fora dele sai LOCAL, dito com todas as
    #    letras (carimbo que omite a origem local seria pior que nenhum).
    for k in ("GITHUB_SHA", "GITHUB_REF_NAME", "GITHUB_RUN_ID"):
        os.environ.pop(k, None)
    checa("sem Actions = LOCAL", "LOCAL" in carimbo_de_origem())
    os.environ["GITHUB_SHA"] = "a1b2c3d4e5f6a7b8"
    os.environ["GITHUB_REF_NAME"] = "main"
    os.environ["GITHUB_RUN_ID"] = "99"
    c = carimbo_de_origem()
    checa("com Actions = sha de 12", "a1b2c3d4e5f6" in c and "LOCAL" not in c, c)

    # 10. O limite corta a DESCRICAO, nunca o carimbo - sha pela metade parece
    #     sha e nao e.
    d = descricao_com_carimbo("d" * 900, c)
    checa("cabe em 400", len(d) == 400, len(d))
    checa("o carimbo sai inteiro", d.endswith(c), d[-60:])
    for k in ("GITHUB_SHA", "GITHUB_REF_NAME", "GITHUB_RUN_ID"):
        os.environ.pop(k, None)

    print("")
    if FALHAS:
        print("FALHOU: %d" % len(FALHAS))
        return 1
    print("TODOS OS TESTES PASSARAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
