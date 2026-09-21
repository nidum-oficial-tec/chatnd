# -*- coding: utf-8 -*-
"""
CONTAGEM DE USO DO AGENTE - a divida do D81, paga junto com o corte.

POR QUE AGORA E NAO DEPOIS (decisao do Davi, 21/09/2026): quando o agente
substituir o pipe, ele JA precisa contar. O pipe tem serie historica na tabela
`eventos`; o agente nao gravava nada. Sem isto, o dia do corte compararia um
lado medido com outro lembrado - e isso nao e comparacao.

O MINIMO ACORDADO, e so ele:
    quantas PESSOAS usaram        -> user_hash distintos
    quantas PERGUNTAS             -> uma linha por turno
    quantas VAZIAS / ERRO / TRUNCADAS
    latencia                      -> de brinde, ja que o relogio esta aqui

MESMA TABELA, e de proposito: `chatnd_analytics.db` em DATA_DIR, tabela
`eventos`. O pipe escreve nela desde a 1.52.0 e o agente passa a escrever na
mesma, para o historico continuar num lugar so. A coluna nova e `origem`.

    origem = 'agente'  -> escrito por aqui
    origem IS NULL     -> escrito pelo PIPE

O pipe NAO foi alterado: ele e publicado por API e mexer nele para acrescentar
uma constante seria risco sem retorno. As linhas antigas e as dele continuam
com `origem` nula, e a leitura trata NULL como 'pipe'. Isso tambem preserva o
historico anterior ao corte, que nao teria como saber de uma coluna que ainda
nao existia.

================================ O D90 MORA AQUI ================================

    "Confere-se o ARTEFATO, nunca a frase que o descreve."

Toda coluna abaixo vem do que o agente FEZ, nunca do que ele disse que fez:

    vazio     -> o texto de saida esta vazio. Nao "ele disse que nao achou".
    ferramentas -> contadas nos itens `function_call` do output, nao no relato.
    truncado  -> ver a heuristica abaixo; tambem observada.

Isto nao e zelo: em 21/09 o agente anunciou ter gerado "todos os 30 slides,
exatamente como especificado" e o arquivo tinha 32. O relato dele sobre a
propria acao nao e evidencia da acao.

=============================== TRUNCADO, A HEURISTICA ==========================

D85: um turno que termina SEM RESPOSTA e pior que qualquer resposta incompleta
que declare a lacuna. O caso medido: o agente chamou `view_knowledge_file` 10
vezes, leu 132.204 de 258.361 chars e devolveu 235 caracteres prometendo
continuar. Gastou o turno lendo e nao respondeu.

A assinatura OBSERVAVEL disso e: MUITA ferramenta, POUCO texto. Entao:

    truncado := ferramentas >= MIN_FERRAMENTAS  E  len(texto) < MAX_CHARS

CONTENT-FREE, como todo o resto: conta ferramentas e caracteres, nunca le o que
foi escrito. E e HEURISTICA, nao medida - um resumo legitimamente curto depois
de muita busca cai aqui como falso positivo. O numero foi escolhido para ser
ajustado com dado real depois do corte, nao para estar certo na primeira
tentativa; por isso os dois limiares sao constantes nomeadas e nao numeros
soltos no meio do `if`.
"""

import logging
import os
import time

log = logging.getLogger(__name__)

# A assinatura do D85. Ajustar com dado real, nao por intuicao.
MIN_FERRAMENTAS = 3
MAX_CHARS_TRUNCADO = 400

_ATRIBUTO_T0 = "_nidum_contagem_t0"


def marcar_inicio(request):
    """Guarda o relogio do turno. Best-effort: sem isto, latencia fica nula."""
    try:
        setattr(request.state, _ATRIBUTO_T0, time.time())
    except Exception:
        pass


def _hash_usuario(user_id):
    """Hash estavel e content-free do id, com sal do ambiente.

    Mesmo formato do pipe (_analytics_user_hash): 12 hex. Sem o sal, o hash
    ainda serve para CONTAR pessoas distintas - que e o minimo acordado - mas
    nao resiste a quem tenha a lista de ids. Com sal, resiste.
    """
    import hashlib
    sal = os.getenv("ANALYTICS_USER_SALT", "")
    if not user_id:
        return ""
    return hashlib.sha256((sal + str(user_id)).encode("utf-8")).hexdigest()[:12]


def _texto_do_output(output):
    """Todo o texto de saida, sem os itens de ferramenta.

    Os itens sao dicts com `type`; os de texto trazem `content` ou `text`. Um
    item de `function_call` NAO e resposta ao usuario e nao entra na contagem
    de caracteres - senao um turno que so chamou ferramentas pareceria ter
    respondido.
    """
    if not isinstance(output, list):
        return ""
    partes = []
    for it in output:
        if not isinstance(it, dict):
            continue
        # A GUARDA, e ela e a unica coisa que separa "o agente respondeu" de
        # "o agente leu coisas". Um `function_call_output` carrega o resultado
        # da ferramenta em `output: [{"type": "input_text", "text": ...}]`
        # (middleware:4777) - texto de verdade, as vezes dezenas de milhares de
        # caracteres. Sem esta linha, um turno que so chamou ferramentas e nao
        # respondeu contaria como resposta longa, e o desfecho `vazio` e a
        # heuristica do D85 nunca disparariam. E exatamente o turno c1 de
        # 21/09: 10 ferramentas, 235 chars de resposta - que apareceria como
        # 140.000 chars de "resposta".
        if (it.get("type") or "") in ("function_call", "function_call_output"):
            continue
        for chave in ("content", "text", "output"):
            v = it.get(chave)
            if isinstance(v, str):
                partes.append(v)
            elif isinstance(v, list):
                for sub in v:
                    if isinstance(sub, dict) and isinstance(sub.get("text"), str):
                        partes.append(sub["text"])
                    elif isinstance(sub, str):
                        partes.append(sub)
    return "".join(partes)


def _ferramentas_do_output(output):
    if not isinstance(output, list):
        return 0
    return sum(1 for it in output
               if isinstance(it, dict) and (it.get("type") or "") == "function_call")


def _desfecho(texto, ferramentas, erro):
    if erro:
        return "erro"
    if not (texto or "").strip():
        return "vazio"
    if ferramentas >= MIN_FERRAMENTAS and len(texto.strip()) < MAX_CHARS_TRUNCADO:
        return "truncado"
    return "ok"


def _escrever(db_path, linha):
    """INSERT best-effort. Cria a tabela e a coluna `origem` se faltarem.

    O ALTER e idempotente pelo mesmo padrao do pipe: se a coluna ja existe, o
    sqlite levanta e o erro e engolido. Banco que ja tem as linhas do pipe
    ganha a coluna sem migracao manual.
    """
    import sqlite3
    con = sqlite3.connect(db_path, timeout=1.0)
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS eventos ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, user_hash TEXT, rota TEXT, "
            "classificador TEXT, trava TEXT, anexo TEXT, anexo_fonte TEXT, "
            "anexo_faixa TEXT, formato_saida TEXT, desfecho TEXT, recusa_cat TEXT, "
            "erro_cat TEXT, latencia_ms INTEGER)"
        )
        for col in ("origem TEXT", "ferramentas INTEGER", "chars_saida INTEGER"):
            try:
                con.execute("ALTER TABLE eventos ADD COLUMN %s" % col)
            except Exception:
                pass
        con.execute(
            "INSERT INTO eventos (ts, user_hash, rota, desfecho, erro_cat, "
            "latencia_ms, origem, ferramentas, chars_saida) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (linha["ts"], linha["user_hash"], linha["rota"], linha["desfecho"],
             linha["erro_cat"], linha["latencia_ms"], linha["origem"],
             linha["ferramentas"], linha["chars_saida"]),
        )
        con.commit()
    finally:
        con.close()


def contar(request, metadata, output, erro=None):
    """Grava UMA linha por turno do agente. NUNCA levanta.

    Best-effort, como todo o resto do pipe: a resposta jamais degrada por causa
    de contabilidade. Se o disco estiver cheio ou o banco travado, a contagem
    se perde e o turno segue - o contrario seria trocar o produto pela metrica.
    """
    try:
        from open_webui.env import DATA_DIR

        texto = _texto_do_output(output)
        ferramentas = _ferramentas_do_output(output)
        t0 = getattr(getattr(request, "state", None), _ATRIBUTO_T0, None)
        linha = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "user_hash": _hash_usuario((metadata or {}).get("user_id")),
            "rota": (metadata or {}).get("model_id") or "",
            "desfecho": _desfecho(texto, ferramentas, erro),
            "erro_cat": (type(erro).__name__ if erro else None),
            "latencia_ms": int((time.time() - t0) * 1000) if t0 else None,
            "origem": "agente",
            "ferramentas": ferramentas,
            "chars_saida": len(texto),
        }
        _escrever(os.path.join(str(DATA_DIR), "chatnd_analytics.db"), linha)
        log.info("nidum_contagem: %s rota=%s ferramentas=%d chars=%d %sms",
                 linha["desfecho"], linha["rota"], ferramentas, len(texto),
                 linha["latencia_ms"])
    except Exception:
        log.exception("nidum_contagem: falhou; o turno segue intacto")
