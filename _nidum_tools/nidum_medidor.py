# -*- coding: ascii -*-
"""
title: Nidum Medidor
author: Nidum
version: 0.1.0
description: Manda ao razao `ia_uso` (Supabase de producao) quantos tokens cada resposta gastou, por pessoa e por modelo. Nao muda a resposta, nao entra no caminho dela, e some sozinho sem IA_USO_TOKEN.
required_open_webui_version: 0.5.0
"""

# =============================================================================
# POR QUE ESTE ARQUIVO EXISTE
# A Nidum tem SETE frentes que gastam API de IA, em repositorios e nuvens
# diferentes. Ate 19-09-2026 cada uma contava (ou nao contava) do seu jeito e
# nenhuma somava com a outra - cinco contabilidades paralelas, medidas. Agora
# existe UM razao, a tabela `ia_uso` no Supabase de producao, e toda frente
# manda a contagem para la.
#
# POR QUE UM FILTER, E NAO UMA MUDANCA NO PIPE
# O pipe `chatnd` tem mais de 6.000 linhas, changelog proprio e vida ativa. Um
# Filter le a resposta DEPOIS de pronta, num metodo de 20 linhas, e nao disputa
# uma unica linha com quem mantem o pipe. Se um dia o pipe mudar de forma, o
# medidor quebra sozinho e visivelmente - nao leva o roteador junto.
#
# POR QUE NAO FICA NO CAMINHO DA RESPOSTA
# O `outlet` roda depois de a resposta estar montada, e o envio vai numa thread
# cujo resultado ninguem espera. Se o coletor cair, cai o REGISTRO - nao a
# conversa. E por isso que este desenho nao precisa de plano de contorno,
# diferente de um gateway, que fica no meio de toda chamada.
#
# ATENCAO - O QUE PRECISA SER CONFERIDO NUMA INSTANCIA VIVA
# Medido no codigo em 19-09: o laco de SSE captura `usage`
# (utils/middleware.py:4129-4133), `normalize_usage` PRESERVA o dicionario
# original (utils/response.py:45 - entao os campos de cache sobrevivem) e o
# valor e anexado a mensagem. O que NAO pude medir sem instancia rodando:
#   1. se `outlet` recebe esse `usage` no ultimo item de body["messages"];
#   2. se o upstream OpenAI-shaped esta mandando `stream_options`
#      {"include_usage": true} - SEM ISSO A CONTAGEM VEM ZERADA EM STREAMING.
#      `stream_options` so aparece nas listas de parametros PERMITIDOS
#      (routers/openai.py:787 e :984); nao achei quem o DEFINA.
# A valve DEBUG=True escreve no log o que chegou, e responde as duas de uma vez.
#
# SEGREDO: IA_USO_TOKEN (variavel de ambiente do servico, no Railway). Ele nao
# da acesso a provedor nenhum: no pior caso alguem grava linha falsa de custo -
# polui o relatorio, nao a fatura.
# =============================================================================

import json
import logging
import os
import threading
import urllib.request

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


def _num(v):
    try:
        n = int(v or 0)
        return n if n > 0 else 0
    except (TypeError, ValueError):
        return 0


def _de_usage(u):
    """Os QUATRO contadores - e nao dois.

    ATENCAO: `input_tokens` (ou `prompt_tokens`, no vocabulario OpenAI) e SO O
    RESTO NAO-CACHEADO. O tamanho real do prompt e a soma dos tres de entrada.
    Ler so o primeiro faria o contador anunciar uma queda de gasto no dia em que
    o cache de prompt fosse ligado - arruinando a prova da economia.
    """
    u = u or {}
    entrada = u.get("input_tokens")
    if entrada is None:
        entrada = u.get("prompt_tokens")
    saida = u.get("output_tokens")
    if saida is None:
        saida = u.get("completion_tokens")
    det = u.get("prompt_tokens_details") or {}
    return {
        "tokens_in": _num(entrada),
        "tokens_out": _num(saida),
        "tokens_cache_w": _num(u.get("cache_creation_input_tokens")),
        # OpenAI chama de `cached_tokens`, dentro de prompt_tokens_details
        "tokens_cache_r": _num(u.get("cache_read_input_tokens") or det.get("cached_tokens")),
    }


class Filter:
    class Valves(BaseModel):
        URL: str = Field(
            default=os.environ.get("IA_USO_URL", ""),
            description="Endereco do coletor (Edge Function ia-uso, na producao).",
        )
        TOKEN: str = Field(
            default=os.environ.get("IA_USO_TOKEN", ""),
            description="Cracha de ingestao desta frente. Vazio = o medidor nao registra nada.",
        )
        APP: str = Field(default="chatnd", description="Nome da frente no razao.")
        FERRAMENTA: str = Field(default="conversa", description="Nome declarado em ia_apps.")
        DEBUG: bool = Field(
            default=False,
            description="Escreve no log o usage que chegou. Ligue uma vez para conferir se a contagem chega - e desligue.",
        )

    def __init__(self):
        self.valves = self.Valves()

    # -- envio: melhor-esforco, nunca levanta, nunca atrasa ------------------
    def _enviar(self, linha):
        try:
            req = urllib.request.Request(
                self.valves.URL,
                data=json.dumps(linha).encode("utf-8"),
                method="POST",
                headers={
                    "content-type": "application/json",
                    "authorization": "Bearer " + self.valves.TOKEN,
                },
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                if r.status >= 300:
                    log.debug("nidum_medidor: coletor respondeu %s", r.status)
        except Exception as e:  # noqa: BLE001 - auditoria e melhor-esforco
            log.debug("nidum_medidor: nao registrou (%s)", e)

    async def outlet(self, body: dict, __user__: dict = None, **kwargs) -> dict:
        # A resposta ja esta pronta aqui. Aconteca o que acontecer abaixo, ela
        # sai inteira: o `try` cobre o metodo todo e devolve `body` intocado.
        try:
            msgs = (body or {}).get("messages") or []
            ultima = msgs[-1] if msgs else {}
            uso = ultima.get("usage") or (body or {}).get("usage") or {}
            if self.valves.DEBUG:
                log.info("nidum_medidor: usage recebido = %s", json.dumps(uso)[:400])

            # Sem cracha nao ha o que fazer - e nao e erro: e o intervalo entre
            # publicar o filtro e por o segredo. Degrada limpo.
            if not self.valves.URL or not self.valves.TOKEN:
                return body

            cont = _de_usage(uso)
            # ATENCAO: nada a contar nao vira linha de zero. Uma enxurrada de
            # linhas zeradas faria o relatorio parecer barato justamente quando
            # a contagem parou de chegar - o silencio tem de ser visivel como
            # silencio, nao como economia.
            if not any(cont.values()):
                if self.valves.DEBUG:
                    log.info("nidum_medidor: sem contagem nesta resposta - nada gravado")
                return body

            linha = dict(cont)
            linha.update({
                "ferramenta": self.valves.FERRAMENTA,
                "acao": "pergunta",
                # O e-mail sai da SESSAO do Open WebUI, nao do corpo.
                "email": (__user__ or {}).get("email"),
                "modelo": (body or {}).get("model") or ultima.get("model"),
                "fornecedor": "openai" if str((body or {}).get("model") or "").startswith(("gpt", "o1", "o3", "o4")) else "anthropic",
                "ref_tipo": "conversa",
                "ref_id": (body or {}).get("chat_id") or (body or {}).get("id"),
            })
            threading.Thread(target=self._enviar, args=(linha,), daemon=True).start()
        except Exception as e:  # noqa: BLE001
            log.debug("nidum_medidor: outlet falhou sem afetar a resposta (%s)", e)
        return body
