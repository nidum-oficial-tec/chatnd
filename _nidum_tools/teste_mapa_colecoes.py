# -*- coding: utf-8 -*-
"""
Prova de que a MAPA_COLECOES invalida NAO passa em silencio (pendencia 5, 17/09/2026).

O QUE ACONTECEU, e e a razao deste arquivo existir: em 17/09 um id foi colado na valve
sem a chave. O JSON ficou invalido, `_parse_mapa_colecoes` devolveu {} SEM excecao e SEM
log, o pipe caiu no BASE_CONHECIMENTO_ID - e ele apontava para duas colecoes ja apagadas
(404). Resultado: a rota `documentos` respondeu SEM ACERVO NENHUM, com aparencia de
normalidade, ate alguem ler a valve de volta pela API.

Tres propriedades que, isoladas, seriam toleraveis:
  1. o parser falha em silencio;
  2. o fallback esta morto;
  3. nada compara a valve com o sync_config da esteira.
Este teste ataca a (1) - a unica que e codigo nosso e a que faz as outras duas serem fatais.

O CONTRATO PROVADO AQUI:
  - VAZIO   -> {} e SILENCIO. A valve nasce vazia; desligada de proposito nao e defeito.
  - INVALIDO-> {} e LOG DE ERRO. Alguem quis configurar e errou.
  - O comportamento NAO muda nos dois casos (devolve {}): a resposta nunca degrada por
    causa de observabilidade. O que muda e o rastro.

D-72: escrito com o defeito reintroduzido de proposito (o `except` devolvendo {} calado) -
ficou VERMELHO em 4 casos antes de o conserto voltar.

USO: python _nidum_tools/teste_mapa_colecoes.py
"""

import io
import logging
import os
import re
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
falhas = []


def check(nome, cond):
    print((u"  OK   " if cond else u"  FALHOU  ") + nome)
    if not cond:
        falhas.append(nome)


def carregar():
    """Importa so as funcoes do modulo, sem subir o Open WebUI.

    O chatnd.py depende do runtime do OWUI no topo; aqui interessam duas funcoes puras,
    entao elas sao extraidas do fonte e executadas num namespace proprio. Le o ARQUIVO
    REAL - se alguem mudar a funcao, este teste ve a mudanca (D-002).
    """
    src = io.open(os.path.join(_DIR, "chatnd.py"), encoding="utf-8").read()
    ns = {"json": __import__("json"), "log": logging.getLogger("teste_mapa")}
    for nome in ("_parse_mapa_colecoes", "_amostra_json_invalido"):
        m = re.search(r"^def %s\(.*?(?=^def |\Z)" % nome, src, re.S | re.M)
        assert m, "funcao %s nao encontrada em chatnd.py" % nome
        exec(compile(m.group(0), "chatnd.py", "exec"), ns)
    return ns["_parse_mapa_colecoes"], ns["_amostra_json_invalido"], ns["log"]


class Captura(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.registros = []

    def emit(self, r):
        self.registros.append((r.levelname, r.getMessage()))

    def por_nivel(self, nivel):
        return [m for n, m in self.registros if n == nivel]


def main():
    parse, amostra, log = carregar()
    cap = Captura()
    log.addHandler(cap)
    log.setLevel(logging.DEBUG)
    log.propagate = False

    VALIDA = ('{"projetos": "accc1ac9-1cb3-42c6-b7ea-b9e92753ecc4", '
              '"fonte": "03e63260-3a5f-49f0-9e22-85dd68bbec11"}')
    # o caso REAL de 17/09: id colado sem a chave, depois da virgula
    REAL = ('{\n "Plataformas Regionais": "b1c81a6b-04f0-4b01-bc2e-6ef4e57e966e", '
            '"accc1ac9-1cb3-42c6-b7ea-b9e92753ecc4"\n}')

    print(u"== 1) valida: devolve o mapa e NAO polui o log ==")
    del cap.registros[:]
    r = parse(VALIDA)
    check(u"2 colecoes lidas", len(r) == 2)
    check(u"chave normalizada para minuscula", "projetos" in r and "fonte" in r)
    check(u"nenhum ERROR para valve valida", not cap.por_nivel("ERROR"))

    print(u"\n== 2) VAZIA: silencio, porque desligada de proposito NAO e defeito ==")
    for vazio in ("", "   ", None):
        del cap.registros[:]
        r = parse(vazio)
        check(u"%-8r -> {} e sem log" % (vazio,), r == {} and not cap.registros)

    print(u"\n== 3) INVALIDA: devolve {} E GRITA (a pendencia 5) ==")
    del cap.registros[:]
    r = parse(REAL)
    erros = cap.por_nivel("ERROR")
    check(u"o caso real de 17/09 -> {}", r == {})
    check(u"registrou ERROR", len(erros) == 1)
    check(u"o log diz que a valve foi IGNORADA", any("IGNORADA" in e for e in erros))
    check(u"o log avisa do BASE_CONHECIMENTO_ID", any("BASE_CONHECIMENTO_ID" in e for e in erros))
    check(u"o log avisa que pode responder SEM ACERVO", any("SEM ACERVO" in e for e in erros))
    check(u"o log mostra ONDE esta o erro (marcador >>><<<)", any(">>><<<" in e for e in erros))

    print(u"\n== 4) outras formas de invalido tambem gritam ==")
    for rotulo, valor in ((u"lista em vez de objeto", '["a","b"]'),
                          (u"string JSON", '"so um texto"'),
                          (u"truncado", '{"fonte": "03e6'),
                          (u"objeto vazio", '{}')):
        del cap.registros[:]
        r = parse(valor)
        check(u"%-22s -> {} + ERROR" % rotulo, r == {} and bool(cap.por_nivel("ERROR")))

    print(u"\n== 5) entrada malformada NAO derruba o mapa inteiro, mas aparece ==")
    del cap.registros[:]
    r = parse('{"fonte": "03e63260", "quebrada": 123, "outra": null}')
    check(u"o que e valido sobrevive", r == {"fonte": "03e63260"})
    check(u"as descartadas viram WARNING", len(cap.por_nivel("WARNING")) == 1)
    check(u"o WARNING conta quantas", any("2 entrada" in w for w in cap.por_nivel("WARNING")))

    print(u"\n== 6) a amostra do erro e content-free e aponta a posicao ==")
    a = amostra(REAL)
    check(u"traz o marcador de posicao", ">>><<<" in a)
    check(u"nao vaza o JSON inteiro", len(a) < 200)
    check(u"json valido -> '(sem erro)'", amostra(VALIDA) == "(sem erro)")

    print(u"")
    if falhas:
        print(u"MAPA_COLECOES: %d FALHA(S)" % len(falhas))
        return 1
    print(u"MAPA_COLECOES OK - valve invalida nao passa mais em silencio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
