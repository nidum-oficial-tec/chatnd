# -*- coding: utf-8 -*-
"""
RASTRO DE BUSCA (R3, peca 3 - plano de 07/11/2026).

POR QUE EXISTE: quando uma resposta do ChatND sai errada, ha tres causas
possiveis com o MESMO sintoma: (1) o documento nao estava na base, (2) estava
e a busca nao trouxe, (3) a busca trouxe e o modelo ignorou. Ate 07/11/2026
nada registrava o que a busca devolveu - para separar (2) de (3) no caso "em
que fase esta cada projeto" foi preciso baixar a conversa e repetir a busca a
mao. Este modulo grava, por CHAMADA de ferramenta de busca, o que entrou e o
que saiu.

CONTENT-FREE, como a contagem (nidum_contagem.py): nunca grava texto. Grava:
    ferramenta, escopo ('selecionado' com # ou 'todas'), ids das bases,
    tamanho da consulta, se a consulta e IGUAL a pergunta do usuario,
    ids dos documentos devolvidos EM ORDEM (sem duplicata), n de trechos,
    caracteres entregues ao modelo, latencia.
Ids de arquivo nao sao conteudo: identificam o documento sem expor o texto,
e sao o que permite cruzar com a regua (_nidum_avaliacao/).

`consulta_igual_pergunta` mede a falha no 1 de 07/11 em producao: quanto o
agente troca a pergunta do usuario por uma reescrita propria. A comparacao e
feita aqui, em memoria, e so o booleano e gravado.

MESMO BANCO da contagem (`chatnd_analytics.db` em DATA_DIR), tabela propria
`buscas`, para o historico de uso continuar num lugar so.

BEST-EFFORT POR CONTRATO: nunca levanta, nunca atrasa a busca de forma
perceptivel (um INSERT local com timeout de 1 s). Rastro perdido e rastro
perdido; busca quebrada por causa de rastro seria trocar o produto pela metrica.
"""

import logging
import os
import re
import time
import unicodedata

log = logging.getLogger(__name__)

MAX_IDS = 20  # suficiente para acerto@20, que e o que a regua mede


def _dobrar(texto):
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().casefold()


def ultima_pergunta(messages):
    """Texto da ultima mensagem do usuario (str ou lista de partes). '' se nao houver."""
    for m in reversed(messages or []):
        if (m or {}).get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            return " ".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text")
        return ""
    return ""


def ids_em_ordem(file_ids, limite=MAX_IDS):
    """Ids distintos na ordem da primeira aparicao, ate `limite`."""
    vistos, out = set(), []
    for f in file_ids or []:
        if f and f not in vistos:
            vistos.add(f)
            out.append(f)
            if len(out) >= limite:
                break
    return out


def montar_linha(user_id, ferramenta, escopo, bases, consulta, pergunta, file_ids, n_trechos, chars, t0):
    from open_webui.utils.nidum_contagem import _hash_usuario

    ids = ids_em_ordem(file_ids)
    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "user_hash": _hash_usuario(user_id),
        "ferramenta": ferramenta,
        "escopo": escopo,
        "bases": ",".join(sorted(bases or [])),
        "consulta_chars": len(consulta or ""),
        # None quando nao ha pergunta para comparar (ex.: chamada fora de chat)
        "consulta_igual_pergunta": (None if not pergunta else int(_dobrar(consulta) == _dobrar(pergunta))),
        "docs": ",".join(ids),
        "n_docs": len(ids),
        "n_trechos": n_trechos,
        "chars": chars,
        "latencia_ms": int((time.time() - t0) * 1000) if t0 else None,
    }


def _escrever(db_path, linha):
    import sqlite3

    con = sqlite3.connect(db_path, timeout=1.0)
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS buscas ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, user_hash TEXT, ferramenta TEXT, "
            "escopo TEXT, bases TEXT, consulta_chars INTEGER, consulta_igual_pergunta INTEGER, "
            "docs TEXT, n_docs INTEGER, n_trechos INTEGER, chars INTEGER, latencia_ms INTEGER)"
        )
        cols = list(linha.keys())
        con.execute(
            "INSERT INTO buscas (%s) VALUES (%s)" % (", ".join(cols), ", ".join("?" for _ in cols)),
            [linha[c] for c in cols],
        )
        con.commit()
    finally:
        con.close()


def registrar(user_id, ferramenta, escopo, bases, consulta, messages, file_ids, n_trechos, chars, t0):
    """Grava UMA linha por chamada de busca. NUNCA levanta."""
    try:
        from open_webui.env import DATA_DIR

        linha = montar_linha(user_id, ferramenta, escopo, bases, consulta, ultima_pergunta(messages),
                             file_ids, n_trechos, chars, t0)
        _escrever(os.path.join(str(DATA_DIR), "chatnd_analytics.db"), linha)
        log.info("nidum_rastro: %s escopo=%s docs=%d igual_pergunta=%s %sms",
                 ferramenta, escopo, linha["n_docs"], linha["consulta_igual_pergunta"], linha["latencia_ms"])
    except Exception:
        log.exception("nidum_rastro: falhou; a busca segue intacta")
