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

O CASO CONHECIDO EM QUE O TETO PROPORCIONAL NAO ALCANCA (21/09/2026):

  "leia tudo e me de X por secao" - pedido claramente multi-entrega que o
  agente NAO decompoe em create_tasks. Medido: o turno c1 da bateria ("leia o
  NIDUM_DOCUMENTO_CONSTITUICAO por inteiro e me faca um resumo executivo de
  cada secao, sem pular nenhuma") nao criou plano nenhum, e foi o UNICO dos
  seis a estourar o teto - 105.512 chars, 104.768 deles numa unica chamada de
  view_knowledge_file.

  Com o teto proporcional ele teria n=1 e 50.000 chars: o desenho nao o cobre.
  Quem cobre e a PAGINACAO (ver _pagina), e e por isso que as duas coisas
  andam juntas - n cuida da complexidade declarada, a paginacao cuida do
  documento que nao cabe numa leitura so.

  DENOMINADOR, para nao superinterpretar: 6 turnos, 2 pedidos multi-entrega,
  1 sem plano. "1 de 2" NAO e uma taxa - e uma anedota com dois pontos. Dizer
  se o perfil e frequente exigiria uma bateria so disso (~20 pedidos
  multi-entrega), que NAO foi feita. O que esta provado e que o perfil existe
  e que e o que mais consome. Se ele reaparecer no uso, ja tem nome.

DUAS FASES NO MESMO CODIGO:
  seco (padrao) - CONTA e registra, nao corta. E a medicao ANTES.
  ligado        - corta com aviso. E a medicao DEPOIS.
A regua tem dois numeros e o segundo e o que importa: a cauda acima do teto
some (objetivo) E A MEDIANA NAO SE MOVE (prova de que o teto nao virou mordaca).
Se a mediana cair, o orcamento passou de protecao a censura - mesma logica do
"todo acervo dispara" na prova de gatilho.
"""

import json
import logging
import os

log = logging.getLogger(__name__)

# TETO PROPORCIONAL AS PARTES DO PEDIDO (decisao do Davi, 21/09/2026).
#
# O PROBLEMA COM UM TETO UNICO: ele serve a pergunta simples e corta justamente
# a tarefa complexa - que e o caso para o qual o agente existe. Classificar o
# pedido por tipo traria de volta o problema do roteador do pipe (o
# classificador erra, e o erro e invisivel). O `create_tasks` resolve os dois:
# e a decomposicao que o PROPRIO agente ja faz, olhando o pedido.
#
#     teto = min(CHARS_POR_PARTE * min(n, MAX_PARTES), TETO_ABSOLUTO)
#     n = tarefas criadas por create_tasks NESTE TURNO; sem plano, n = 1.
#
# ORDEM, medida em 21/09: no unico turno que planejou, o create_tasks foi a
# SEGUNDA chamada, com 958 chars consumidos - o teto fica conhecido antes de o
# material chegar. E create_tasks SUBSTITUI a lista inteira
# (Chats.update_chat_tasks_by_id), entao replanejar no meio do turno reajusta o
# teto; o que ja entrou continua dentro.
#
# ATENCAO - POR QUE `n` VEM DO RESULTADO DA TOOL E NUNCA DO BANCO:
#   as tarefas sao guardadas POR CHAT (__chat_id__); o orcamento vive POR TURNO
#   (request.state). Lendo do banco, um "e o resto?" no mesmo chat herdaria o
#   plano de 7 tarefas do turno anterior e ganharia 350.000 chars para uma
#   pergunta de uma linha. Contar do resultado que passa por `orcar` DENTRO do
#   turno fecha isso POR CONSTRUCAO - nao por disciplina de quem mantem. E o
#   tipo de defeito que passaria em todo teste unitario, porque so aparece na
#   segunda mensagem de uma conversa.
#
# OS NUMEROS NAO FORAM MEDIDOS, e quem ajustar isto depois precisa saber:
#   - 45.000 (o teto anterior) era o MAX_CHARS_PROJETO do pipe, copiado de
#     proposito para os dois serem comparaveis. O do pipe tem JUSTIFICATIVA DE
#     DESENHO ("o material do projeto e um canal a MAIS, nunca o dono do
#     orcamento"), nao experimento.
#   - 50.000 por parte e 6 partes sao PALPITE DECLARADO (Davi, 21/09). O limite
#     que morde nao e a janela do modelo: 300.000 chars ~ 81.000 tokens cabem
#     folgado. E a QUALIDADE - material demais dilui o relevante muito antes de
#     a janela encher, que e o mesmo diagnostico do piso de k (D-001).
#   Ou seja: o multiplicador repousa sobre um numero herdado. Medir o ponto em
#   que mais material piora a resposta e outra bateria, nao esta.
AGENTE_CHARS_POR_PARTE = int(os.environ.get("AGENTE_CHARS_POR_PARTE", "50000") or 0)
AGENTE_MAX_PARTES = int(os.environ.get("AGENTE_MAX_PARTES", "6") or 0)
AGENTE_TETO_ABSOLUTO = int(os.environ.get("AGENTE_TETO_ABSOLUTO", "300000") or 0)

# Teto FIXO, quando quiser desligar a proporcionalidade (0 = proporcional).
# Serve a comparacao entre fases: medir com tetos diferentes mediria a
# diferenca de teto, nao a de comportamento.
AGENTE_MAX_CHARS_TURNO = int(os.environ.get("AGENTE_MAX_CHARS_TURNO", "0") or 0)

# FASE 1 por padrao. Ligar o corte e decisao de operacao, tomada DEPOIS de olhar
# a distribuicao - e nao junto com o deploy que a instrumenta. Foi o D58 que
# ensinou a desconfiar de default que decide sozinho; aqui o default nao decide,
# ele mede.
AGENTE_ORCAMENTO_ATIVO = (os.environ.get("AGENTE_ORCAMENTO_ATIVO", "false")
                          .lower() == "true")

_ATRIBUTO = "_nidum_orcamento_turno"
_ATRIBUTO_N = "_nidum_orcamento_partes"


def _partes(request):
    # Quantas partes o pedido tem NESTE turno. Sem plano, 1.
    return max(1, getattr(request, "state", None) and
               getattr(request.state, _ATRIBUTO_N, 1) or 1)


def _teto(request):
    if AGENTE_MAX_CHARS_TURNO > 0:
        return AGENTE_MAX_CHARS_TURNO
    n = min(_partes(request), AGENTE_MAX_PARTES or 1)
    return min(AGENTE_CHARS_POR_PARTE * n, AGENTE_TETO_ABSOLUTO or (AGENTE_CHARS_POR_PARTE * n))


def _registra_plano(request, tool_result, nome_da_tool):
    """Se a tool foi `create_tasks`, guarda n = numero de tarefas DO TURNO.

    O resultado do create_tasks e {"tasks": [...], "summary": {...}} - o proprio
    dado que ja passa por aqui. Nada de banco: ver a nota das constantes.
    """
    if nome_da_tool != "create_tasks" or not isinstance(tool_result, str):
        return
    try:
        d = json.loads(tool_result)
        n = len(d.get("tasks") or [])
        if n > 0:
            setattr(request.state, _ATRIBUTO_N, n)
            log.info("nidum_orcamento: plano com %d parte(s) -> teto do turno %d",
                     n, _teto(request))
    except Exception:
        pass


def _aviso(omitidos, teto, trechos=None, de=None):
    """O aviso que o modelo LE. Diz o numero de TRECHOS quando o resultado era
    uma lista - "3 de 8 trechos" e acionavel de um jeito que "412 caracteres"
    nao e: o modelo sabe que ha itens inteiros faltando, nao um texto cortado.
    """
    quanto = "%d caractere(s) omitidos" % omitidos
    if trechos is not None and de:
        quanto = "%d de %d trecho(s) descartados (%d caractere(s))" % (
            trechos, de, omitidos)
        if trechos < de:
            quanto += "; os que ficaram sao os PRIMEIROS da lista"
    return (
        "\n\n[ORCAMENTO DO TURNO: %s. O limite de %d "
        "caracteres de material por turno foi atingido. NAO repita esta busca - "
        "ela devolveria o mesmo. Se precisar de mais, faca UMA busca mais "
        "especifica, ou responda com o que ja tem e diga ao usuario que o "
        "material foi truncado.]" % (quanto, teto)
    )


def _aviso_pagina(omitidos, teto, proximo, total):
    """Aviso de LEITURA DE DOCUMENTO: diz ONDE parou e como continuar.

    Diferente do aviso de busca, que manda NAO repetir: aqui repetir e
    exatamente o certo, desde que com o offset novo. Sem isto o modelo recebe
    "foi truncado" e nao tem como saber que existe um jeito de pedir o resto -
    e o caso medido em 21/09 (c1: 104.768 de 105.512 chars numa unica chamada
    de view_knowledge_file) morria ai.
    """
    return (
        "\n\n[ORCAMENTO DO TURNO: o documento continua. Foram entregues os "
        "caracteres ate %d de %d; %d caractere(s) nao couberam no limite de %d "
        "por turno. PARA CONTINUAR, chame a MESMA ferramenta com "
        "offset=%d - e o resto do MESMO arquivo, nao uma busca nova. Se o "
        "orcamento do turno ja estiver esgotado, responda com o que tem e diga "
        "ao usuario ate onde leu.]" % (proximo, total, omitidos, teto, proximo)
    )


def _pagina(dado, sobra, teto, tamanho):
    """Documento truncado pelo orcamento -> pagina, em vez de fatia crua.

    O `view_knowledge_file` JA E PAGINADO: aceita offset/max_chars e devolve
    truncated/total_chars/returned_chars/offset/next_offset. O corte reusa esse
    contrato em vez de inventar outro - encurta o `content`, MANTEM o envelope
    (id, filename, metadados) e RECALCULA next_offset, para o modelo poder
    pedir a continuacao exata.

    Nota de fidelidade: quando a chamada usou line_numbers=True, o `content`
    traz prefixos de linha e o proprio upstream conta o offset sobre o texto
    JA prefixado (builtin.py: returned_chars = len(sliced) depois da
    prefixacao). Seguimos a MESMA convencao de proposito - divergir aqui daria
    dois significados de offset no mesmo contrato.
    """
    conteudo = dado.get("content")
    if not isinstance(conteudo, str) or not conteudo:
        return None
    inicio = int(dado.get("offset") or 0)
    total = int(dado.get("total_chars") or (inicio + len(conteudo)))

    # Quanto do envelope custa, sem o conteudo? O que sobrar e para o texto.
    molde = dict(dado)
    molde["content"] = ""
    molde["truncated"] = True
    molde["offset"] = inicio
    molde["total_chars"] = total
    molde["returned_chars"] = 0
    molde["next_offset"] = inicio
    custo = len(json.dumps(molde, indent=2, ensure_ascii=False))
    espaco = sobra - custo
    if espaco <= 0:
        return None   # nem o envelope cabe: cai no aviso seco

    pedaco = conteudo[:espaco]
    quebra = pedaco.rfind("\n")
    if quebra > espaco // 2:
        pedaco = pedaco[:quebra]
    if not pedaco:
        return None

    novo = dict(dado)
    novo["content"] = pedaco
    novo["truncated"] = True
    novo["offset"] = inicio
    novo["total_chars"] = total
    novo["returned_chars"] = len(pedaco)
    novo["next_offset"] = inicio + len(pedaco)
    texto = json.dumps(novo, indent=2, ensure_ascii=False)
    return texto + _aviso_pagina(tamanho - len(texto), teto,
                                 novo["next_offset"], total)


def _lista_de(dado):
    """Se o resultado for uma lista - direta ou embrulhada num dict de uma
    chave so - devolve (lista, embrulhar). Senao, (None, None).

    O embrulho existe porque `process_tool_result` faz
    `{"results": tool_result}` antes de serializar toda lista (middleware.py),
    entao o formato que chega aqui e quase sempre o dict de uma chave.
    """
    if isinstance(dado, list):
        return dado, (lambda itens: itens)
    if isinstance(dado, dict):
        chaves = [k for k, v in dado.items() if isinstance(v, list)]
        if len(chaves) == 1:
            k = chaves[0]
            return dado[k], (lambda itens, _k=k, _d=dado: dict(_d, **{_k: itens}))
    return None, None


def _corta(tool_result, sobra, teto, tamanho):
    """Corta PRESERVANDO A ESTRUTURA. Devolve o texto ja com o aviso.

    POR QUE NAO E MAIS `tool_result[:sobra]` (medido em 21/09/2026): quando o
    orcamento ve o resultado, ele JA E UMA STRING JSON - `process_tool_result`
    faz `json.dumps(..., indent=2)` antes de chamar daqui. Cortar por caractere
    parte o JSON no meio de uma chave ou de uma string:

        json.loads(cortado) -> Unterminated string starting at line 15

    O modelo recebia dado sintaticamente quebrado MAIS um aviso em prosa. Isso
    nao e "corte pouco inteligente", e entregar lixo.

    DUAS ESTRATEGIAS, e a primeira e a que torna o corte SELETIVO de graca:

      LISTA  -> descarta ELEMENTOS INTEIROS da cauda ate caber, e re-serializa.
                `query_knowledge_files` devolve os trechos ORDENADOS por
                similaridade (`query_collection` -> distances, depois
                `chunks[:count]`), entao a cauda e o MENOS relevante: descartar
                do fim ja e descartar o menos relevante. De graca, sem rankear
                nada aqui.
      TEXTO  -> corta na ultima QUEBRA DE LINHA que cabe, nunca no meio de uma
                palavra. Vale para leitura de documento (`view_knowledge_file`),
                que NAO vem ordenada por relevancia: ali o corte continua sendo
                "guarda o comeco", e isso e arbitrario em relacao a pergunta.
                A paginacao e que resolve esse caso - nao o corte.
    """
    try:
        dado = json.loads(tool_result)
    except Exception:
        dado = None

    if isinstance(dado, dict) and "content" in dado:
        # LEITURA DE DOCUMENTO: pagina em vez de cortar. E o caso que nenhum
        # teto por turno alcanca - o c1 estourou com UMA chamada de 104.768
        # chars -, entao o corte precisa deixar o modelo continuar.
        paginado = _pagina(dado, sobra, teto, tamanho)
        if paginado is not None:
            return paginado

    if dado is not None:
        itens, embrulhar = _lista_de(dado)
        if itens is not None and len(itens) > 1:
            total = len(itens)
            # Maior prefixo que cabe. Linear e barato: as listas tem poucas
            # dezenas de itens, e medir o serializado e o unico jeito honesto -
            # o indent e as virgulas contam.
            cabe = 0
            for k in range(total, 0, -1):
                if len(json.dumps(embrulhar(itens[:k]), indent=2,
                                  ensure_ascii=False)) <= sobra:
                    cabe = k
                    break
            if cabe:
                texto = json.dumps(embrulhar(itens[:cabe]), indent=2,
                                   ensure_ascii=False)
                return texto + _aviso(tamanho - len(texto), teto,
                                      total - cabe, total)
            # Nem um item cabe: o aviso sozinho, dizendo de quantos.
            return _aviso(tamanho, teto, total, total).strip()

    # TEXTO: fronteira de linha. Se nao houver quebra na janela, cai no corte
    # por caractere - melhor cortar do que devolver vazio.
    pedaco = tool_result[:sobra]
    quebra = pedaco.rfind("\n")
    if quebra > sobra // 2:
        pedaco = pedaco[:quebra]
    return pedaco + _aviso(tamanho - len(pedaco), teto)


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
        _registra_plano(request, tool_result, nome_da_tool)
        teto = _teto(request)
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
        return _corta(tool_result, sobra, teto, tamanho)
    except Exception:
        # Best-effort, como todo o resto do pipe: a resposta nunca degrada por
        # causa de contabilidade.
        log.exception("nidum_orcamento: falhou; o resultado segue intacto")
        return tool_result


def consumido(request):
    """Quanto o turno ja consumiu. Para teste e para quem quiser relatar."""
    return getattr(request.state, _ATRIBUTO, 0)
