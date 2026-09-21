# -*- coding: ascii -*-
"""
Prova do MEDIDOR - e o que impede o falso negativo de voltar.

O DEFEITO QUE ESTE TESTE FIXA (achado em 21/09/2026, antes de gastar chamada de
producao): o contador soma o tamanho PEDIDO tambem quando corta, entao com o
corte LIGADO o log continua escrevendo "(100000/45000)". Lido como entregue,
a cauda NUNCA zera e o veredito diria "o corte nao esta ativo" com ele ativo.

Os casos 4 e 5 sao esse par: MESMO log, modo=seco e modo=ATIVO. Em seco a cauda
existe; em ATIVO ela desaparece - lendo o entregue, que e o que entrou no
contexto. Se alguem "simplificar" a reconstrucao, os dois casos caem juntos.
"""

import importlib.util
import io
import os
import sys
import tempfile

_AQUI = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "medir_orcamento", os.path.join(_AQUI, "medir_orcamento.py"))
_M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_M)

FALHAS = []


def checa(nome, cond, extra=""):
    if cond:
        print("  ok   %s" % nome)
    else:
        print("  FALHA %s %s" % (nome, extra))
        FALHAS.append(nome)


def soma(tool, tamanho, acum, teto=45000):
    return ("2026-09-21 12:00:00.000 | INFO | nidum_orcamento: %s +%d chars "
            "(turno: %d/%d)\n" % (tool, tamanho, acum, teto))


def estouro(tool, acum, tamanho, modo, teto=45000):
    return ("2026-09-21 12:00:00.000 | WARNING | nidum_orcamento: %s ESTOUROU o "
            "turno (%d/%d, +%d) modo=%s\n" % (tool, acum, teto, tamanho, modo))


def ler_texto(texto):
    fd, cam = tempfile.mkstemp(suffix=".log")
    os.close(fd)
    with io.open(cam, "w", encoding="utf-8") as fh:
        fh.write(texto)
    try:
        return _M.ler(cam)
    finally:
        os.remove(cam)


def main():
    print("teste_medir_orcamento")

    # 1. SOMA simples: entregue == pedido, um turno so.
    t, teto, modos, por_tool = ler_texto(
        soma("query_knowledge_files", 8590, 8590)
        + soma("query_knowledge_files", 8590, 17180))
    checa("um turno", len(t) == 1, len(t))
    checa("teto lido do log", teto == 45000, teto)
    checa("entregue = pedido quando nada corta",
          t[0].entregue == 17180 and t[0].pedido == 17180,
          (t[0].entregue, t[0].pedido))

    # 2. QUEDA DO ACUMULADO separa turnos (o caminho do despejo cru).
    t, _, _, _ = ler_texto(
        soma("query_knowledge_files", 8590, 8590)
        + soma("view_file", 10000, 18590)
        + soma("query_knowledge_files", 8590, 8590))
    checa("a queda do acumulado abre turno novo", len(t) == 2, len(t))
    checa("e os dois totais estao certos",
          [x.entregue for x in t] == [18590, 8590], [x.entregue for x in t])

    # 3. MARCADOR separa turnos sem heuristica - inclusive quando o acumulado
    #    SOBE entre turnos, que e o caso em que a queda nao ajuda.
    t, _, _, _ = ler_texto(
        "#turno controle-1\n"
        + soma("query_knowledge_files", 8590, 8590)
        + "#turno controle-2\n"
        + soma("query_knowledge_files", 9000, 9000)
        + soma("view_file", 10000, 19000))
    checa("o marcador separa", len(t) == 2, len(t))
    checa("e carrega o rotulo",
          [x.rotulo for x in t] == ["controle-1", "controle-2"],
          [x.rotulo for x in t])
    checa("com marcador, acumulado que SOBE nao funde os turnos",
          [x.entregue for x in t] == [8590, 19000], [x.entregue for x in t])

    # 4. SECO: a cauda EXISTE. E o numero da fase 1.
    log_cauda = (soma("query_knowledge_files", 8590, 8590)
                 + estouro("view_file", 108590, 100000, "seco"))
    t, teto, modos, _ = ler_texto(log_cauda)
    checa("seco: entregue = pedido (nada foi cortado)",
          t[0].entregue == 108590, t[0].entregue)
    checa("seco: o turno esta ACIMA do teto", t[0].entregue > teto, t[0].entregue)
    checa("seco: nenhuma chamada cortada", t[0].cortes == 0, t[0].cortes)

    # 5. ATIVO, MESMOS NUMEROS NO LOG: a cauda DESAPARECE no entregue.
    #    8590 entregues + (45000-8590)=36410 do view_file = 45000 exatos.
    t, teto, modos, _ = ler_texto(
        soma("query_knowledge_files", 8590, 8590)
        + estouro("view_file", 108590, 100000, "ATIVO"))
    checa("ATIVO: o entregue para no teto", t[0].entregue == 45000, t[0].entregue)
    checa("ATIVO: e a DEMANDA continua visivel", t[0].pedido == 108590, t[0].pedido)
    checa("ATIVO: a chamada cortada e contada", t[0].cortes == 1, t[0].cortes)
    checa("ATIVO: o modo aparece na leitura", "ATIVO" in modos, modos)

    # 6. ATIVO com o turno JA estourado: a chamada seguinte entrega ZERO.
    #    (sobra <= 0 -> so o aviso; o aviso nao e material do acervo)
    t, _, _, _ = ler_texto(
        estouro("view_file", 100000, 100000, "ATIVO")
        + estouro("view_file", 150000, 50000, "ATIVO"))
    checa("ATIVO: depois de estourar, a chamada seguinte entrega 0",
          t[0].entregue == 45000, t[0].entregue)

    # 7. O que o log NAO tem nao se inventa.
    t, teto, modos, por_tool = ler_texto("linha qualquer sem orcamento\n")
    checa("log sem linha do orcamento devolve zero turno", t == [], t)
    checa("e a regua diz isso em vez de imprimir numero",
          _M.regua("vazio.log", t, 45000) is None)

    # 8. Contagem por tool - e o que mostra QUEM puxa o material.
    _, _, _, por_tool = ler_texto(
        soma("query_knowledge_files", 100, 100)
        + soma("query_knowledge_files", 100, 200)
        + estouro("view_file", 100200, 100000, "seco"))
    checa("conta chamadas por tool",
          por_tool == {"query_knowledge_files": 2, "view_file": 1}, por_tool)

    print("")
    if FALHAS:
        print("FALHOU: %d" % len(FALHAS))
        return 1
    print("TODOS OS TESTES PASSARAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
