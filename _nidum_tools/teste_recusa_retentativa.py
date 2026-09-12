# -*- coding: ascii -*-
"""
A recusa da TOOL passa a ter retentativa - e o teste prova a FIACAO, nao so os
helpers.

O CASO, medido em 12/09/2026: das 5 execucoes do baseline de deck, UMA voltou
como texto de diagnostico em vez de arquivo:

    DIAGNOSTICO gerar_pptx: o slide 16 (tipo 'destaque') chegou sem nenhum campo
    de corpo, e sairia mudo no arquivo.

A recusa esta CERTA - e a validacao impedindo o slide mudo, e a mensagem foi
desenhada para ENSINAR o modelo. O buraco era nao haver quem aprendesse: o pipe
retentava quando o JSON vinha invalido ou vazio, mas ali o JSON estava bom e quem
recusou foi a tool, DEPOIS. A licao chegava ao usuario em vez de voltar ao modelo.

O QUE ESTE TESTE PROVA, e a ordem importa:
  1. os helpers reconhecem a recusa e montam a instrucao;
  2. a FIACAO - `_gerar_arquivo` retenta, e a segunda saida e a que volta;
  3. a recusa que sobra CHEGA INTEIRA ao usuario (condicao do Davi: a retentativa
     nao pode esconder o problema);
  4. os contadores existem - sem eles nao da para distinguir "a rede cobriu um
     azar" de "a rede esconde um defeito que acontece sempre".
"""

import asyncio
import os
import sys
from unittest.mock import MagicMock

for _m in [
    "open_webui",
    "open_webui.models", "open_webui.models.knowledge", "open_webui.models.users",
    "open_webui.retrieval", "open_webui.retrieval.utils",
    "open_webui.routers", "open_webui.routers.images",
    "open_webui.utils", "open_webui.utils.chat", "open_webui.utils.plugin",
]:
    sys.modules[_m] = MagicMock()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chatnd as C  # noqa: E402

RECUSA = ("DIAGNOSTICO gerar_pptx: o slide 16 (tipo 'destaque') chegou sem nenhum "
          "campo de corpo, e sairia mudo no arquivo. Esse tipo exige 'texto', "
          "'bullets' ou 'itens'. As chaves que chegaram foram: titulo, tipo. "
          "Reenvie o slide com o corpo preenchido.")
SUCESSO = "Arquivo gerado com sucesso. Link para download: [x](http://a/b/content)"

FALHAS = []


def checa(nome, cond, extra=""):
    if cond:
        print("  ok   %s" % nome)
    else:
        print("  FALHA %s %s" % (nome, extra))
        FALHAS.append(nome)


def _pipe_falso(saidas_da_tool, dados_por_chamada):
    """Um Pipe com o minimo trocado: o gerador e o despacho da tool.

    O MIOLO RODA DE VERDADE - a deteccao da recusa, a decisao de retentar, a
    troca dos dados e o que volta ao usuario. E esse miolo que o D71 manda
    provar: nao a funcao isolada, e sim o valor que o chamador recebe.
    """
    p = C.Pipe.__new__(C.Pipe)
    p.valves = MagicMock()
    chamadas = {"gerador": 0, "tool": 0}

    async def _chamar_gerador(request, user, messages, sistema, _ev=None):
        i = chamadas["gerador"]
        chamadas["gerador"] += 1
        chamadas.setdefault("sistemas", []).append(sistema)
        return dados_por_chamada[min(i, len(dados_por_chamada) - 1)]

    async def _despachar(tool, tipo, titulo, dados, __user__, eco, imagens, fc=""):
        i = chamadas["tool"]
        chamadas["tool"] += 1
        return saidas_da_tool[min(i, len(saidas_da_tool) - 1)]

    async def _get_tool():
        return MagicMock()

    p._chamar_gerador = _chamar_gerador
    p._despachar_tool = _despachar
    p._get_tool = _get_tool
    # `_dados_uteis` e staticmethod: acessar pela CLASSE ja devolve a funcao
    # pura. Fazer __get__ a transformaria em metodo ligado esperando self.
    p._dados_uteis = C.Pipe._dados_uteis
    p._oferta_multiplos = staticmethod(lambda m: "")
    return p, chamadas


DADOS = {"tipo": "pptx", "titulo": "T", "slides": [{"titulo": "a", "texto": "b"}]}


def _rodar(p, ev=None):
    # asyncio.run, e nao get_event_loop: a partir do 3.12 nao ha loop implicito
    # no MainThread, e get_event_loop levanta em vez de criar um.
    return asyncio.run(
        p._gerar_arquivo(MagicMock(), MagicMock(), [{"role": "user", "content": "x"}],
                         {"id": "u1"}, _ev=ev if ev is not None else {}))


def main():
    print("teste_recusa_retentativa")

    # 1. HELPERS
    checa("reconhece a recusa da tool", C._eh_recusa(RECUSA))
    checa("nao confunde sucesso com recusa", not C._eh_recusa(SUCESSO))
    checa("recusa com espaco a esquerda tambem", C._eh_recusa("   " + RECUSA))
    checa("vazio nao e recusa", not C._eh_recusa("") and not C._eh_recusa(None))
    instr = C._instrucao_recusa(RECUSA)
    checa("a instrucao leva o diagnostico INTEIRO (nao resumo)",
          "slide 16" in instr and "titulo, tipo" in instr, instr[:70])

    # 2. A FIACAO: recusa -> retentativa -> sucesso
    p, ch = _pipe_falso([RECUSA, SUCESSO], [DADOS, DADOS])
    saida = _rodar(p)
    checa("retentou o gerador (2 chamadas)", ch["gerador"] == 2, ch["gerador"])
    checa("despachou a tool 2 vezes", ch["tool"] == 2, ch["tool"])
    checa("o usuario recebe o SUCESSO, nao a recusa", saida == SUCESSO, saida[:60])
    checa("a 2a chamada ao gerador levou o diagnostico junto",
          "RECUSADA" in ch["sistemas"][1] and "slide 16" in ch["sistemas"][1])

    # 3. A RECUSA QUE SOBRA CHEGA INTEIRA - condicao do Davi.
    p, ch = _pipe_falso([RECUSA, RECUSA], [DADOS, DADOS])
    saida = _rodar(p)
    checa("duas recusas -> o usuario recebe o DIAGNOSTICO", C._eh_recusa(saida), saida[:60])
    checa("e ele vem inteiro, com o que faltava", "slide 16" in saida and
          "Reenvie o slide" in saida, saida[:60])
    checa("NAO foi trocado por 'nao consegui'", "nao consegui" not in saida.lower())

    # 4. SEM RECUSA, nada muda - a rede nao pode custar nada no caminho normal.
    p, ch = _pipe_falso([SUCESSO], [DADOS])
    saida = _rodar(p)
    checa("sucesso de primeira: UMA chamada ao gerador", ch["gerador"] == 1, ch["gerador"])
    checa("sucesso de primeira: UM despacho", ch["tool"] == 1, ch["tool"])
    checa("e a saida e a da tool", saida == SUCESSO)

    # 5. OS CONTADORES. Sem eles, "a rede cobriu um azar" e "a rede esconde um
    #    defeito que acontece sempre" sao indistinguiveis (D68).
    p, _ = _pipe_falso([RECUSA, SUCESSO], [DADOS, DADOS])
    ev = {}
    _rodar(p, ev)
    checa("conta a recusa", ev.get("recusa_tool") == 1, ev)
    checa("conta a SALVACAO (e o numero que denuncia rede virando muleta)",
          ev.get("recusa_salva") == 1, ev)
    checa("nao marca recusa_final quando salvou", "recusa_final" not in ev, ev)

    p, _ = _pipe_falso([RECUSA, RECUSA], [DADOS, DADOS])
    ev = {}
    _rodar(p, ev)
    checa("conta a recusa FINAL quando as duas falham",
          ev.get("recusa_final") == 1 and "recusa_salva" not in ev, ev)

    print("")
    if FALHAS:
        print("FALHOU: %d" % len(FALHAS))
        return 1
    print("TODOS OS TESTES PASSARAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
