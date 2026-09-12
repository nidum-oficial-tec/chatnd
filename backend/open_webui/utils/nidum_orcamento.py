# -*- coding: utf-8 -*-
"""
ORCAMENTO DE CONTEXTO POR TURNO, para o laco agentico.

POR QUE EXISTE (Fase E #13, 12/09/2026) - e os numeros sao medidos, nao estimados:

O pipe ChatND tem orcamento para o canal da pasta ha tempos: `MAX_CHARS_PROJETO`,
45.000 chars. Ele monta o bloco UMA VEZ - recupera, monta, corta, entrega. E um
orcamento de MONTAGEM.

O agente nao monta nada: ele ACUMULA, chamada a chamada, ao longo do turno. E a
diferenca nao e de grau.

    chunk medio na base ........... 1.718 chars   (CHUNK_SIZE=2200, overlap 300)
    query_knowledge_files(count=5)  8.590 chars por chamada
    view_file, padrao ............ 10.000 chars
    view_file, HARD CAP ......... 100.000 chars
    teto de rodadas do laco ........... 12

    por turno, so com busca ...... ~103.000
    por turno, com view_file .... ate 1.200.000
    orcamento do pipe ............... 45.000

O agente pode puxar ATE 26 VEZES o que o pipe puxa num turno. E um documento no
p90 do acervo (48.156 chars) estoura o teto do pipe SOZINHO, num arquivo so.

POR ISSO O TETO E POR TURNO, E NAO POR CHAMADA: teto por chamada nao limita nada,
porque o modelo chama de novo. E por isso ele conta TODA tool de conteudo - com
ENABLE_KB_EXEC=False o agente recebe seis, e um teto so na busca seria contornado
pelo `view_file` sem ninguem perceber.

CORTA COM AVISO, NAO RECUSA (decisao do Davi, e o argumento e o que decide): o
modelo LE o aviso e pode buscar melhor. Recusar no meio de um laco o deixa sem
saida - ele nao tem como pedir de novo o que foi negado sem motivo legivel.

DUAS FASES NO MESMO CODIGO:
  seco (padrao) - CONTA e registra, nao corta. E a medicao ANTES.
  ligado        - corta com aviso. E a medicao DEPOIS.
A regua tem dois numeros e o segundo e o que importa: a cauda acima do teto
some (objetivo) E A MEDIANA NAO SE MOVE (prova de que o teto nao virou mordaca).
Se a mediana cair, o orcamento passou de protecao a censura - mesma logica do
"todo acervo dispara" na prova de gatilho.
"""

import logging
import os

log = logging.getLogger(__name__)

# Teto por TURNO. O default espelha o MAX_CHARS_PROJETO do pipe (45.000) por uma
# razao: o corte compara os dois, e comparar com orcamentos diferentes mediria a
# diferenca de orcamento, nao a de comportamento.
AGENTE_MAX_CHARS_TURNO = int(os.environ.get("AGENTE_MAX_CHARS_TURNO", "45000") or 0)

# FASE 1 por padrao. Ligar o corte e decisao de operacao, tomada DEPOIS de olhar
# a distribuicao - e nao junto com o deploy que a instrumenta. Foi o D58 que
# ensinou a desconfiar de default que decide sozinho; aqui o default nao decide,
# ele mede.
AGENTE_ORCAMENTO_ATIVO = (os.environ.get("AGENTE_ORCAMENTO_ATIVO", "false")
                          .lower() == "true")

_ATRIBUTO = "_nidum_orcamento_turno"


def _aviso(omitidos, teto):
    return (
        "\n\n[ORCAMENTO DO TURNO: %d caractere(s) omitidos. O limite de %d "
        "caracteres de material por turno foi atingido. NAO repita esta busca - "
        "ela devolveria o mesmo. Se precisar de mais, faca UMA busca mais "
        "especifica, ou responda com o que ja tem e diga ao usuario que o "
        "material foi truncado.]" % (omitidos, teto)
    )


def orcar(request, tool_result, nome_da_tool=""):
    """Contabiliza o resultado no turno e, se ativo, corta com aviso.

    Devolve o `tool_result` (igual, ou cortado). NUNCA levanta: orcamento que
    derruba a resposta e pior que orcamento nenhum.

    O ESTADO VIVE EM `request.state`, que e exatamente o escopo de um turno -
    nasce e morre com a requisicao. Nao precisa de reset explicito, e nao ha
    como um turno herdar o consumo de outro.
    """
    try:
        if not isinstance(tool_result, str) or not tool_result:
            return tool_result
        teto = AGENTE_MAX_CHARS_TURNO
        if teto <= 0:
            return tool_result

        usado = getattr(request.state, _ATRIBUTO, 0)
        tamanho = len(tool_result)
        sobra = teto - usado

        if tamanho <= sobra:
            setattr(request.state, _ATRIBUTO, usado + tamanho)
            log.info("nidum_orcamento: %s +%d chars (turno: %d/%d)",
                     nome_da_tool or "?", tamanho, usado + tamanho, teto)
            return tool_result

        # ESTOUROU. Em seco, so registra - e o numero da fase 1.
        setattr(request.state, _ATRIBUTO, usado + tamanho)
        log.warning("nidum_orcamento: %s ESTOUROU o turno (%d/%d, +%d) modo=%s",
                    nome_da_tool or "?", usado + tamanho, teto, tamanho,
                    "ATIVO" if AGENTE_ORCAMENTO_ATIVO else "seco")
        if not AGENTE_ORCAMENTO_ATIVO:
            return tool_result

        if sobra <= 0:
            # Nada cabe. Devolve SO o aviso - o modelo precisa saber por que
            # veio vazio, senao ele conclui que a base nao tem nada e diz isso
            # ao usuario, que e pior que dizer "foi truncado".
            return _aviso(tamanho, teto).strip()
        return tool_result[:sobra] + _aviso(tamanho - sobra, teto)
    except Exception:
        # Best-effort, como todo o resto do pipe: a resposta nunca degrada por
        # causa de contabilidade.
        log.exception("nidum_orcamento: falhou; o resultado segue intacto")
        return tool_result


def consumido(request):
    """Quanto o turno ja consumiu. Para teste e para quem quiser relatar."""
    return getattr(request.state, _ATRIBUTO, 0)
