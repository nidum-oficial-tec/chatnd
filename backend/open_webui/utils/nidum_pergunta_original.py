# -*- coding: ascii -*-
"""
A PERGUNTA DO USUARIO entra na busca por conteudo junto com a reescrita do
agente (etapa A do plano de 07/11; Nidum, 08/11/2026).

POR QUE EXISTE: o agente nao manda a pergunta do usuario para
query_knowledge_files - manda uma reescrita dele, quase sempre uma lista de
palavras. Evidencia:
  - Estudos revisados por pares (citados em TEC_EstudoReferenciasRAGChatND):
    substituir a pergunta pela reescrita piorou a busca (Wang et al. 2024,
    EMNLP); a reescrita JUNTO com a original melhorou (Query2doc, EMNLP 2023).
  - Caso de 07/11 no ChatND: "em que fase esta cada projeto" - com a pergunta
    do usuario, as atas certas vinham em 3o e 6o; com a lista de palavras do
    agente, fora do top 50.
  - Regua de 08/11 (11 perguntas): cada forma acerta perguntas diferentes;
    pegando a melhor das duas por item, acerto@20 iria de 45-55% para ~64%.

O QUE FAZ: devolve as consultas a mandar ao motor: a do agente e, quando
diferente dela, a ultima pergunta do usuario. O motor
(query_collection_with_hybrid_search) ja aceita varias consultas e junta os
resultados pela nota do reranker.

QUANDO NAO ACRESCENTA: pergunta vazia; igual a consulta do agente (sem acento,
sem caixa); longa demais (texto colado, > MAX_CHARS - vira ruido e custo); ou
NIDUM_PERGUNTA_ORIGINAL=0 (desliga sem mudar codigo).

Funcoes PURAS (testaveis offline). BEST-EFFORT: nunca levanta.
"""

import os
import re
import unicodedata

MAX_CHARS = 500


def _dobrar(texto):
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c)).casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-z]+", " ", t)).strip()


def ligado():
    return str(os.environ.get("NIDUM_PERGUNTA_ORIGINAL", "1")).strip() != "0"


def ultima_pergunta(messages):
    """Texto da ultima mensagem do usuario (str ou lista de partes)."""
    try:
        for m in reversed(messages or []):
            if (m or {}).get("role") != "user":
                continue
            c = m.get("content")
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                return " ".join(p.get("text", "") for p in c
                                if isinstance(p, dict) and p.get("type") == "text")
            return ""
    except Exception:
        return ""
    return ""


def consultas_da_busca(query, messages):
    """[query] ou [query, pergunta_do_usuario]."""
    try:
        consultas = [query]
        if not ligado():
            return consultas
        p = (ultima_pergunta(messages) or "").strip()
        if not p or len(p) > MAX_CHARS:
            return consultas
        if _dobrar(p) == _dobrar(query):
            return consultas
        return consultas + [p]
    except Exception:
        return [query]
