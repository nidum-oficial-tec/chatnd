# -*- coding: ascii -*-
"""
Orcamento de contexto por turno: prova o acumulado, o corte, o aviso e a FIACAO.

OS NUMEROS QUE MOTIVARAM (medidos em producao, 12/09/2026):
  chunk medio 1.718 | query_knowledge_files(count=5) = 8.590/chamada
  view_file padrao 10.000 | view_file HARD CAP 100.000 | 12 rodadas de laco
  -> ate 1.200.000 chars por turno, contra os 45.000 do pipe. 26x.

O que este teste prova, em ordem:
  1. acumula ENTRE chamadas (teto por chamada nao limitaria nada);
  2. em modo SECO conta e NAO corta - e a medicao da fase 1;
  3. ativo, corta e o aviso DIZ quanto foi omitido e o que fazer;
  4. estouro total devolve o aviso, nao vazio - vazio faz o modelo concluir
     que a base nao tem nada, o que e pior que dizer que truncou;
  5. o estado vive no request e NAO vaza entre turnos;
  6. FIACAO: o `middleware.process_tool_result` chama o orcamento no ponto
     unico por onde os dois caminhos de execucao passam.
"""

import json
import importlib.util
import io
import os
import re
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(_AQUI)
_MOD = os.path.join(_RAIZ, "backend", "open_webui", "utils", "nidum_orcamento.py")

# Carrega por CAMINHO: `import open_webui...` puxa o __init__ do pacote, que
# importa typer e so existe no container.
_spec = importlib.util.spec_from_file_location("nidum_orcamento", _MOD)
_O = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_O)

FALHAS = []


def checa(nome, cond, extra=""):
    if cond:
        print("  ok   %s" % nome)
    else:
        print("  FALHA %s %s" % (nome, extra))
        FALHAS.append(nome)


class _Estado(object):
    pass


_MARCA = chr(10) + chr(10) + "[ORCAMENTO"


class _Req(object):
    """Um request de mentira: o orcamento so precisa de `.state`."""

    def __init__(self):
        self.state = _Estado()


def _conf(teto, ativo):
    _O.AGENTE_MAX_CHARS_TURNO = teto
    _O.AGENTE_ORCAMENTO_ATIVO = ativo


def main():
    print("teste_orcamento_turno")

    # 1. ACUMULA ENTRE CHAMADAS. E o ponto do desenho: teto por chamada nao
    #    limita nada, porque o modelo chama de novo.
    _conf(10000, True)
    r = _Req()
    _O.orcar(r, "a" * 4000, "query_knowledge_files")
    _O.orcar(r, "b" * 4000, "query_knowledge_files")
    checa("soma entre chamadas do mesmo turno", _O.consumido(r) == 8000,
          _O.consumido(r))
    terceiro = _O.orcar(r, "c" * 4000, "view_file")
    checa("a 3a chamada e CORTADA (8000+4000 > 10000)", len(terceiro) < 4000 + 400,
          len(terceiro))
    checa("e o corte respeita a sobra exata (2000 chars de conteudo)",
          terceiro.startswith("c" * 2000) and not terceiro.startswith("c" * 2001))

    # 2. MODO SECO: conta e NAO corta. E a fase 1.
    _conf(1000, False)
    r = _Req()
    saida = _O.orcar(r, "x" * 5000, "view_file")
    checa("seco NAO corta", saida == "x" * 5000, len(saida))
    checa("mas CONTA (o numero da fase 1 existe)", _O.consumido(r) == 5000,
          _O.consumido(r))

    # 3. O AVISO diz quanto foi omitido e o que fazer.
    _conf(1000, True)
    r = _Req()
    saida = _O.orcar(r, "y" * 3000, "grep_knowledge_files")
    checa("o aviso diz o numero de chars omitidos", "2000 caractere(s)" in saida,
          saida[-160:])
    checa("e manda NAO repetir a busca", "NAO repita esta busca" in saida)
    checa("e oferece saida (buscar mais especifico ou responder)",
          "mais especifica" in saida and "truncado" in saida)

    # 4. ESTOURO TOTAL devolve o AVISO, nao vazio.
    _conf(1000, True)
    r = _Req()
    _O.orcar(r, "z" * 1000, "view_file")          # consome o teto inteiro
    saida = _O.orcar(r, "w" * 500, "view_file")
    checa("sem sobra, devolve o AVISO (nunca string vazia)",
          saida.strip() != "" and "ORCAMENTO DO TURNO" in saida, repr(saida[:60]))

    # 5. O ESTADO NAO VAZA ENTRE TURNOS - request novo, contador zerado.
    r2 = _Req()
    checa("turno novo comeca em zero", _O.consumido(r2) == 0)

    # 6. NAO DEGRADA: teto 0 desliga, tipo estranho passa, excecao nao levanta.
    _conf(0, True)
    r = _Req()
    checa("teto 0 desliga o canal", _O.orcar(r, "q" * 9999, "x") == "q" * 9999)
    _conf(10, True)
    checa("resultado nao-string passa intacto", _O.orcar(_Req(), {"a": 1}, "x") == {"a": 1})
    # Silencia SO neste caso: o log.exception esta certo (nunca falhar calado,
    # D68) e deve continuar barulhento em producao - mas aqui ele imprime um
    # traceback que se le como falha do teste. Calar em producao seria o defeito;
    # calar na prova do defeito, nao.
    import logging
    _lg = logging.getLogger("nidum_orcamento")
    _antes = _lg.level
    _lg.setLevel(logging.CRITICAL)
    try:
        checa("request sem .state nao levanta", _O.orcar(object(), "abc", "x") == "abc")
    finally:
        _lg.setLevel(_antes)

    # 7. FIACAO - o valor que o chamador de verdade recebe (D71). Sem isto, o
    #    teste provaria uma funcao que ninguem chama.
    mw = io.open(os.path.join(_RAIZ, "backend", "open_webui", "utils",
                              "middleware.py"), encoding="utf-8").read()
    checa("middleware IMPORTA o orcamento",
          "from open_webui.utils.nidum_orcamento import orcar" in mw)
    checa("e CHAMA no ponto unico, antes do return de process_tool_result",
          re.search(r"tool_result = orcar\(request, tool_result, tool_function_name\)\s*\n\s*return tool_result, tool_result_files, tool_result_embeds", mw) is not None)

    # ================================================== CORTE ESTRUTURAL (21/09)
    print("")
    print("corte estrutural: o que o modelo recebe continua sendo dado valido")
    _conf(400, True)
    chunks = [{"content": "trecho %d, e a lista vem por relevancia" % i}
              for i in range(8)]
    bruto = json.dumps({"results": chunks}, indent=2, ensure_ascii=False)
    saida = _O.orcar(_Req(), bruto, "query_knowledge_files")
    corpo = saida.split(_MARCA)[0]
    try:
        d = json.loads(corpo)
        valido = True
    except Exception:
        d, valido = None, False
    checa("lista cortada continua JSON VALIDO", valido)
    checa("descarta ELEMENTOS inteiros, nao caracteres",
          valido and 0 < len(d["results"]) < 8)
    checa("os que ficam sao os PRIMEIROS (= os mais relevantes)",
          valido and d["results"][0]["content"].startswith("trecho 0,"))
    checa("o aviso conta TRECHOS, nao so chars", "trecho(s) descartados" in saida)

    _conf(300, True)
    doc = chr(10).join("linha %02d com conteudo" % i for i in range(40))
    saida = _O.orcar(_Req(), doc, "view_file")
    corpo = saida.split(_MARCA)[0]
    checa("texto sem estrutura corta em FRONTEIRA DE LINHA",
          corpo.endswith("conteudo"))

    # ================================================== PAGINACAO (21/09)
    print("")
    print("paginacao: o documento que nao cabe continua, em vez de morrer cortado")
    _conf(3000, True)
    texto = chr(10).join("Secao %02d. %s" % (i, "corpo " * 20) for i in range(40))
    payload = json.dumps({"id": "f1", "filename": "X.md", "content": texto,
                          "total_chars": len(texto), "offset": 0,
                          "returned_chars": len(texto)}, ensure_ascii=False)
    saida = _O.orcar(_Req(), payload, "view_knowledge_file")
    corpo = saida.split(_MARCA)[0]
    try:
        d = json.loads(corpo)
        valido = True
    except Exception:
        d, valido = None, False
    checa("o envelope sobrevive (JSON valido)", valido)
    checa("id e filename preservados",
          valido and d.get("id") == "f1" and d.get("filename") == "X.md")
    checa("truncated=True e total_chars intacto",
          valido and d.get("truncated") is True and d["total_chars"] == len(texto))
    checa("next_offset aponta para a continuacao EXATA",
          valido and texto[d["next_offset"]:][:30] == texto[len(d["content"]):][:30])
    checa("o aviso ensina a continuar (offset=)", "offset=" in saida)
    checa("e NAO manda parar de buscar", "NAO repita esta busca" not in saida)

    # ============================================ TETO PROPORCIONAL (21/09)
    print("")
    print("teto proporcional: n vem do create_tasks DO TURNO, nunca do banco")
    _O.AGENTE_MAX_CHARS_TURNO = 0        # 0 = proporcional
    r = _Req()
    checa("sem plano -> 1 parte (50.000)", _O._teto(r) == 50000)
    plano = json.dumps({"tasks": [{"id": str(i), "content": "p%d" % i}
                                  for i in range(5)]})
    _O.orcar(r, plano, "create_tasks")
    checa("5 tarefas -> 250.000, no MESMO turno", _O._teto(r) == 250000)
    checa("TURNO NOVO nao herda o plano (a armadilha do chat)",
          _O._teto(_Req()) == 50000)
    r9 = _Req()
    setattr(r9.state, "_nidum_orcamento_partes", 9)
    checa("teto absoluto trava em 300.000", _O._teto(r9) == 300000)
    _O.AGENTE_MAX_CHARS_TURNO = 45000
    r5 = _Req()
    setattr(r5.state, "_nidum_orcamento_partes", 5)
    checa("teto FIXO desliga a proporcionalidade (comparar fases)",
          _O._teto(r5) == 45000)
    _O.AGENTE_MAX_CHARS_TURNO = 0

    print("")
    if FALHAS:
        print("FALHOU: %d" % len(FALHAS))
        return 1
    print("TODOS OS TESTES PASSARAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
