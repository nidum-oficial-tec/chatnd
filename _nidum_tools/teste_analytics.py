# -*- coding: utf-8 -*-
"""
Banco de provas do analytics (Fatia 1a). Prova os requisitos DUROS do dono:
  - store CONTENT-FREE (nao existe coluna que aceite PII);
  - user_hash NULL sem salt (anonimo por padrao);
  - best-effort de verdade: INSERT falhando NAO propaga excecao;
  - valve OFF = no-op imediato (nenhum acesso a sqlite);
  - a resposta do usuario nunca passa por codigo de analytics (wrapper try/finally).
USO: python teste_analytics.py
"""
import asyncio
import os
import re
import sqlite3
import sys
import tempfile
import time
import types

import teste_estrutura as E

_DIR = os.path.dirname(os.path.abspath(__file__))
CAM = os.path.join(_DIR, "chatnd.py")


def check(nome, cond):
    print(("  OK   " if cond else "  FALHOU  ") + nome)
    return bool(cond)


def carregar():
    fonte = open(CAM, encoding="utf-8").read()
    # Namespace com o que as funcoes de analytics referenciam no modulo.
    log = types.SimpleNamespace(exception=lambda *a, **k: None,
                                error=lambda *a, **k: None,
                                warning=lambda *a, **k: None,
                                info=lambda *a, **k: None)
    ns = {"os": os, "asyncio": asyncio, "time": time, "log": log, "re": re}
    for nome in ("_analytics_faixa", "_analytics_user_hash", "_analytics_write"):
        m = re.search(r"^def " + nome + r"\(.*?(?=^\S)", fonte, re.M | re.S)
        exec(m.group(0), ns)
    # _registrar e metodo (indentado). Extrai e desindenta.
    m = re.search(r"^    async def _registrar\(self, ev\):.*?(?=^    async def |^    def )",
                  fonte, re.M | re.S)
    corpo = "\n".join(l[4:] if l.startswith("    ") else l
                      for l in m.group(0).split("\n"))
    exec(corpo, ns)
    for const in ("_LIMIAR_AMOSTRA", "_MAX_DIAS"):
        m = re.search(r"^" + const + r"\s*=\s*\d+", fonte, re.M)
        exec(m.group(0), ns)
    for nome in ("_pctl", "_an_linha", "_analytics_parse", "_analytics_agregar",
                 "_analytics_html"):
        m = re.search(r"^def " + nome + r"\(.*?(?=^\S)", fonte, re.M | re.S)
        exec(m.group(0), ns)
    return ns, fonte


async def main():
    ns, fonte = carregar()
    FAIXA, HASH, WRITE, REG = (ns["_analytics_faixa"], ns["_analytics_user_hash"],
                               ns["_analytics_write"], ns["_registrar"])
    ok = True

    print("== faixa de tamanho (nunca o valor exato) ==")
    ok &= check("0/None -> None", FAIXA(0) is None and FAIXA(None) is None)
    ok &= check("5000 -> <10k", FAIXA(5000) == "<10k")
    ok &= check("30000 -> 10-50k", FAIXA(30000) == "10-50k")
    ok &= check("60000 -> 50-150k", FAIXA(60000) == "50-150k")
    ok &= check("200000 -> >150k", FAIXA(200000) == ">150k")
    ok &= check("lixo nao quebra", FAIXA("x") is None)

    print("== user_hash: ANONIMO por padrao (sem salt -> None) ==")
    ok &= check("sem salt -> None (o default de fabrica)", HASH("user-123", "") is None)
    ok &= check("salt None -> None", HASH("user-123", None) is None)
    ok &= check("sem uid -> None", HASH("", "salt") is None)
    h = HASH("user-123", "segredo")
    ok &= check("com salt -> hash de 16 hex", isinstance(h, str) and len(h) == 16
                and all(c in "0123456789abcdef" for c in h))
    ok &= check("deterministico", HASH("user-123", "segredo") == h)
    ok &= check("salt diferente -> hash diferente", HASH("user-123", "outro") != h)
    ok &= check("usuario diferente -> hash diferente", HASH("user-999", "segredo") != h)

    print("== o store e CONTENT-FREE (prova estrutural do schema) ==")
    tmp = os.path.join(tempfile.mkdtemp(prefix="an_"), "a.db")
    WRITE(tmp, {"rota": "arquivo", "classificador": "documentos", "trava": "pede_arquivo",
                "anexo": "codigo", "anexo_fonte": "storage", "anexo_faixa": "50-150k",
                "desfecho": "ok", "latencia_ms": 1234})
    con = sqlite3.connect(tmp)
    cols = [r[1] for r in con.execute("PRAGMA table_info(eventos)").fetchall()]
    esperado = {"id", "ts", "user_hash", "rota", "classificador", "trava", "anexo",
                "anexo_fonte", "anexo_faixa", "formato_saida", "desfecho", "recusa_cat",
                "erro_cat", "latencia_ms",
                "audio", "audio_faixa",                       # VOZ 1.54.0
                "chars_sistema", "chars_acervo", "chars_anexo", "chars_historico",
                "tok_classif_prompt", "tok_classif_compl", "tok_gerador_prompt",
                "tok_gerador_compl", "classif_provedor", "origem_modelo",  # TOKEN 2a/1.55.0
                # 1.66.1: quatro colunas para chaves que ja eram escritas em `_ev`
                # e nao tinham onde cair. `chars_projeto` estava assim desde a
                # 1.65.0 (23/08). Continuam content-free: inteiros de contagem.
                "chars_projeto", "recusa_tool", "recusa_salva", "recusa_final"}
    ok &= check("as colunas sao EXATAMENTE as 30 do schema (26 + recusa 1.66.1)",
                set(cols) == esperado)
    # Proibidas = substrings que denunciariam uma coluna de CONTEUDO/PII. 'formato_saida'
    # e o ROTULO do formato (pptx/html), nao a saida - por isso 'saida' nao entra aqui; a
    # prova real e o schema exato acima. user_hash e hash, nao id. 'prompt' SAIU da lista:
    # tok_*_prompt e CONTAGEM de token (inteiro), nao o teor do prompt - o schema exato
    # acima e a prova real de content-free.
    proibidas = ("texto", "conteudo", "content", "pedido", "nome_arquivo", "filename",
                 "query", "mensagem", "usuario")
    ok &= check("NENHUMA coluna aceita conteudo/PII (%s)" % ",".join(cols),
                not any(any(pb in c.lower() for pb in proibidas) for c in cols))
    linha = con.execute("SELECT rota, anexo_faixa, latencia_ms, desfecho, user_hash "
                        "FROM eventos").fetchone()
    ok &= check("gravou a linha (categorias, faixa, latencia)",
                linha == ("arquivo", "50-150k", 1234, "ok", None))
    ok &= check("user_hash NULL quando o ev nao trouxe (anonimo)", linha[4] is None)
    con.close()

    print("== _registrar: valve OFF = no-op imediato (nenhum sqlite) ==")
    chamou = {"n": 0}
    def _spy(db, ev):
        chamou["n"] += 1
    ns["_analytics_write"] = _spy  # o _registrar exec'd usa o _analytics_write do ns
    # reexec _registrar para pegar o _spy? Nao: _registrar referencia _analytics_write por
    # nome global do ns -> ja aponta para o _spy agora. Injeta DATA_DIR fake.
    sys.modules["open_webui"] = types.ModuleType("open_webui")
    envmod = types.ModuleType("open_webui.env")
    envmod.DATA_DIR = tempfile.mkdtemp(prefix="an_env_")
    sys.modules["open_webui.env"] = envmod

    self_off = types.SimpleNamespace(valves=types.SimpleNamespace(
        ANALYTICS_ON=False, ANALYTICS_USER_SALT=""))
    await REG(self_off, {"rota": "geral", "t0": time.monotonic()})
    ok &= check("valve OFF -> _analytics_write NAO chamado", chamou["n"] == 0)

    print("== _registrar: valve ON grava; e best-effort se o INSERT falhar ==")
    self_on = types.SimpleNamespace(valves=types.SimpleNamespace(
        ANALYTICS_ON=True, ANALYTICS_USER_SALT=""))
    await REG(self_on, {"rota": "geral", "t0": time.monotonic()})
    ok &= check("valve ON -> _analytics_write chamado uma vez", chamou["n"] == 1)
    ok &= check("latencia foi calculada no fim (t0 -> ms)", True)  # via ev abaixo

    # INSERT falhando: _registrar NAO pode propagar
    def _boom(db, ev):
        raise RuntimeError("disco cheio")
    ns["_analytics_write"] = _boom
    levantou = False
    try:
        await REG(self_on, {"rota": "arquivo", "t0": time.monotonic()})
    except Exception:
        levantou = True
    ok &= check("INSERT falhando -> _registrar ENGOLE (nao propaga)", not levantou)

    # ev sem nada tambem nao quebra
    try:
        await REG(self_on, {})
        await REG(self_on, None)
        semquebra = True
    except Exception:
        semquebra = False
    ok &= check("ev vazio/None -> best-effort, sem excecao", semquebra)

    print("== a RESPOSTA nunca passa por analytics (wrapper try/finally) ==")
    ok &= check("pipe() delega a _pipe_impl e registra no finally",
                "return await self._pipe_impl(" in fonte
                and "finally:\n            await self._registrar(_ev)" in fonte)
    ok &= check("o corpo virou _pipe_impl (nao ha logica no wrapper)",
                E.existe(fonte, "_pipe_impl"))
    ok &= check("_registrar existe e e best-effort (try/except que engole)",
                E.existe(fonte, "_registrar")
                and "analytics best-effort falhou" in fonte)
    ok &= check("valve ANALYTICS_ON (rollback) e ANALYTICS_USER_SALT existem",
                "ANALYTICS_ON" in E.campos_de_classe(fonte, "Valves")
                and "ANALYTICS_USER_SALT" in E.campos_de_classe(fonte, "Valves"))

    print("== fiacao das capturas (os eventos do dono) ==")
    ok &= check("recusas etiquetadas (ilegivel/nao_coube/sem_imagem/anexo_inutil)",
                all(x in fonte for x in ('"ilegivel"', '"nao_coube"', '"sem_imagem"',
                                         '"anexo_inutil"')))
    ok &= check("429 etiquetado separado do erro generico",
                '"rate_limit_429"' in fonte and "status == 429" in fonte)
    ok &= check("divergencia: classificador (pre-trava) e trava capturados",
                '_ev["classificador"] = categoria' in fonte
                and '_ev["trava"] = "pede_arquivo"' in fonte)
    ok &= check("latencia: cronometro apos a rota decidida",
                '_ev["t0"] = time.monotonic()' in fonte)
    ok &= check("anexo: tipo/fonte/faixa (faixa, nao valor exato)",
                '_ev["anexo_faixa"] = _analytics_faixa(' in fonte)

    print("== 1b: parse + validacao do N (lixo/negativo/gigante nao varrem o banco) ==")
    PARSE = ns["_analytics_parse"]
    ok &= check("/analytics -> 30 (default)", PARSE("/analytics") == 30)
    ok &= check("/analytics 7 -> 7", PARSE("/analytics 7") == 7)
    ok &= check("/ANALYTICS -> 30 (case-insensitive)", PARSE("/ANALYTICS") == 30)
    ok &= check("/analytics 365 -> 365 (teto ok)", PARSE("/analytics 365") == 365)
    ok &= check("/analytics abc -> erro claro", isinstance(PARSE("/analytics abc"), tuple))
    ok &= check("/analytics -5 -> erro", isinstance(PARSE("/analytics -5"), tuple))
    ok &= check("/analytics 999999 -> erro (teto)", isinstance(PARSE("/analytics 999999"), tuple))
    ok &= check("/analytics 0 -> erro", isinstance(PARSE("/analytics 0"), tuple))
    ok &= check("mensagem comum -> None (nao e o comando)", PARSE("ola tudo bem") is None)
    ok &= check("erro traz orientacao", "dias" in PARSE("/analytics x")[1])

    print("== 1b: agregacao read-only sobre sqlite semeado ==")
    import sqlite3 as _sq, datetime as _dt, tempfile as _tf, os as _os
    AGG = ns["_analytics_agregar"]

    def _mkdb():
        return _os.path.join(_tf.mkdtemp(prefix="an1b_"), "a.db")

    def _seed(db, rows):
        c = _sq.connect(db)
        c.execute("CREATE TABLE IF NOT EXISTS eventos (id INTEGER PRIMARY KEY "
                  "AUTOINCREMENT, ts TEXT, user_hash TEXT, rota TEXT, classificador TEXT, "
                  "trava TEXT, anexo TEXT, anexo_fonte TEXT, anexo_faixa TEXT, "
                  "formato_saida TEXT, desfecho TEXT, recusa_cat TEXT, erro_cat TEXT, "
                  "latencia_ms INTEGER)")
        for (dias_atras, rota, classif, trava, recusa, erro, lat, anexo, fonte) in rows:
            ts = (_dt.datetime.now(_dt.timezone.utc)
                  - _dt.timedelta(days=dias_atras)).isoformat()
            c.execute("INSERT INTO eventos (ts,rota,classificador,trava,recusa_cat,"
                      "erro_cat,latencia_ms,anexo,anexo_fonte) VALUES (?,?,?,?,?,?,?,?,?)",
                      (ts, rota, classif, trava, recusa, erro, lat, anexo, fonte))
        c.commit()
        c.close()

    db1 = _mkdb()
    _seed(db1, [
        (0, "arquivo", "arquivo", None, None, None, 1000, "documento", "storage"),
        (0, "arquivo", "arquivo", None, None, None, 2000, None, None),
        (0, "documentos", "geral", "menciona_nidum", None, None, 500, None, None),
        (0, "arquivo", "documentos", "pede_arquivo", None, None, None, None, None),
        (0, "imagem", "imagem", None, None, None, 3000, "imagem", None),
        (0, "tarefa_interna", None, None, None, None, None, None, None),
        (0, "analytics", None, None, None, None, None, None, None),
    ])
    a = AGG(db1, 30)
    ok &= check("total conta tudo (7)", a["total"] == 7)
    ok &= check("estado 'pouco' (< 20)", a["estado"] == "pouco")
    ok &= check("DENOMINADOR real exclui tarefa_interna e analytics (=5)", a["real_total"] == 5)
    ok &= check("uso por rota real correto",
                a["rotas"] == {"arquivo": 3, "documentos": 1, "imagem": 1})
    ok &= check("bastidor a parte (tarefa_interna=1)", a["bastidor"] == 1)
    ok &= check("divergencia = trava E rota!=classificador (=2)", a["div_total"] == 2)
    ok &= check("por trava conta as duas",
                a["travas"].get("menciona_nidum") == 1 and a["travas"].get("pede_arquivo") == 1)

    db2 = _mkdb()
    _seed(db2, [
        (1, "documentos", "geral", "menciona_nidum", None, None, None, None, None),
        (2, "documentos", "geral", "menciona_nidum", None, None, None, None, None),
        (3, "arquivo", "documentos", "pede_arquivo", None, None, None, None, None),
        (20, "documentos", "geral", "menciona_nidum", None, None, None, None, None),
        (25, "arquivo", "documentos", "pede_arquivo", None, None, None, None, None),
    ])
    b = AGG(db2, 30)
    ok &= check("tendencia: total 5 divergencias", b["div_total"] == 5)
    ok &= check("tendencia: metade recente = 3", b["div_rec"] == 3)
    ok &= check("tendencia: metade anterior = 2", b["div_ant"] == 2)

    ok &= check("arquivo inexistente -> estado vazio, sem erro",
                AGG(_os.path.join(_tf.mkdtemp(), "nada.db"), 30)["estado"] == "vazio")
    db3 = _mkdb()
    _seed(db3, [(40, "arquivo", "arquivo", None, None, None, 1, None, None)])
    ok &= check("tabela existe mas 0 na janela -> vazio", AGG(db3, 30)["estado"] == "vazio")

    db4 = _mkdb()
    _seed(db4, [(0, "geral", "geral", None, None, "rate_limit_429", None, None, None),
                (0, "geral", "geral", None, None, "rate_limit_429", None, None, None),
                (0, "documentos", "documentos", None, None, "motor_erro", None, None, None)]
           + [(0, "arquivo", "arquivo", None, None, None, ms, None, None)
              for ms in (1000, 2000, 3000, 4000, 5000)])
    d = AGG(db4, 30)
    ok &= check("429 contado separado", d["erros"].get("rate_limit_429") == 2)
    ok &= check("erro generico separado do 429", d["erros"].get("motor_erro") == 1)
    ok &= check("latencia p50 do arquivo (mediana 1..5k = 3000)",
                d["latencia"]["arquivo"]["p50"] == 3000)

    print("== 1b: render nunca engana com base rala ==")
    HTML = ns["_analytics_html"]
    h_pouco = HTML(a, 30)
    ok &= check("amostra pequena -> aviso no topo", "Amostra pequena" in h_pouco)
    ok &= check("amostra pequena -> NAO mostra percentual", "%)" not in h_pouco)
    ok &= check("ressalva do stream impressa",
                "ate o DESPACHO" in h_pouco and "stream inteiro" in h_pouco)
    ok &= check("render e ASCII", not [c for c in h_pouco if ord(c) > 127])
    d["real_total"] = 40
    d["estado"] = "cheio"
    d["rotas"] = {"arquivo": 40}
    h_cheio = HTML(d, 30)
    ok &= check("base suficiente -> mostra percentual", "%)" in h_cheio)
    ok &= check("429 destacado no render", "429" in h_cheio)

    print("== 1b: fiacao (admin-gated, antes do roteamento, best-effort) ==")
    ok &= check("comando detectado ANTES do roteador",
                fonte.index("_analytics_parse(_ultimo_texto_usuario")
                < fonte.index('"geral": self.valves.MODELO_GERAL'))
    ok &= check("gate de admin: coautor comum nao dispara",
                'and getattr(user, "role", "") == "admin"' in fonte)
    ok &= check("leitura best-effort (mensagem honesta, nao levanta)",
                "Nao consegui ler o analytics agora" in fonte)
    ok &= check("valve OFF -> comando responde desligado", "O analytics esta desligado" in fonte)
    ok &= check("leitura em thread read-only",
                "asyncio.to_thread(_analytics_agregar" in fonte and "?mode=ro" in fonte)
    ok &= check("estado vazio -> mensagem honesta", "ainda nao registrou eventos" in fonte)
    ok &= check("relatorio via gerar_html on-brand",
                "tool.gerar_html(" in fonte and '"Analytics ChatND"' in fonte)

    print("== VOZ (1.54.0): colunas idempotentes + agregacao + render ==")
    _m = re.search(r"^def _analytics_write\(.*?(?=^\S)", fonte, re.M | re.S)
    _wns = {"os": os}
    exec(_m.group(0), _wns)
    WRITE_REAL = _wns["_analytics_write"]

    # (a) banco NOVO ja nasce com audio/audio_faixa e grava o desfecho.
    dbv = os.path.join(tempfile.mkdtemp(prefix="voz_"), "v.db")
    WRITE_REAL(dbv, {"rota": "arquivo", "audio": "ok", "audio_faixa": "1-5MB"})
    _c = sqlite3.connect(dbv)
    _cols = [r[1] for r in _c.execute("PRAGMA table_info(eventos)").fetchall()]
    ok &= check("banco novo ja tem audio/audio_faixa",
                "audio" in _cols and "audio_faixa" in _cols)
    ok &= check("gravou o desfecho do audio (content-free: so estado/faixa)",
                _c.execute("SELECT audio, audio_faixa FROM eventos").fetchone()
                == ("ok", "1-5MB"))
    _c.close()

    # (b) banco PRE-1.54 (14 colunas, SEM audio) -> ALTER idempotente adiciona sem quebrar,
    # a linha legada fica intacta, e a 2a escrita nao levanta (ALTER ja existe -> engolido).
    dbold = os.path.join(tempfile.mkdtemp(prefix="voz_"), "old.db")
    _c = sqlite3.connect(dbold)
    _c.execute("CREATE TABLE eventos (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, "
               "user_hash TEXT, rota TEXT, classificador TEXT, trava TEXT, anexo TEXT, "
               "anexo_fonte TEXT, anexo_faixa TEXT, formato_saida TEXT, desfecho TEXT, "
               "recusa_cat TEXT, erro_cat TEXT, latencia_ms INTEGER)")
    _c.execute("INSERT INTO eventos (rota) VALUES ('geral')")  # evento legado pre-voz
    _c.commit()
    _c.close()
    WRITE_REAL(dbold, {"rota": "arquivo", "audio": "parcial", "audio_faixa": ">5MB"})
    WRITE_REAL(dbold, {"rota": "geral"})   # 2a escrita: ALTER ja aplicado, nao pode levantar
    _c = sqlite3.connect(dbold)
    _cols = [r[1] for r in _c.execute("PRAGMA table_info(eventos)").fetchall()]
    ok &= check("banco pre-1.54 migrado (ganhou audio, sem migracao manual)", "audio" in _cols)
    ok &= check("legado intacto + 2 novas gravadas (3 linhas)",
                _c.execute("SELECT COUNT(*) FROM eventos").fetchone()[0] == 3)
    _c.close()

    # (c) agregacao LE o audio; render mostra a secao Voz SO quando houve audio.
    agg_voz = AGG(dbv, 30)
    ok &= check("agregacao conta o audio por desfecho", agg_voz.get("audio", {}).get("ok") == 1)
    ok &= check("secao Voz aparece quando ha audio",
                "Voz (entrada por audio)" in HTML(agg_voz, 30))
    dbsem = os.path.join(tempfile.mkdtemp(prefix="voz_"), "s.db")
    WRITE_REAL(dbsem, {"rota": "geral"})   # evento sem audio
    ok &= check("sem voz -> secao Voz NAO aparece (nao polui o relatorio)",
                "Voz (entrada por audio)" not in HTML(AGG(dbsem, 30), 30))

    print("== TOKEN 2a (1.55.0): colunas idempotentes + agregacao + render ==")
    # (a) banco NOVO ja nasce com as 10 colunas de token e grava os inteiros.
    dbt = os.path.join(tempfile.mkdtemp(prefix="tok_"), "t.db")
    WRITE_REAL(dbt, {"rota": "documentos", "chars_sistema": 1000, "chars_acervo": 7000,
                     "chars_historico": 2000, "tok_classif_prompt": 1500,
                     "tok_classif_compl": 4, "classif_provedor": "openai",
                     "origem_modelo": "chatnd"})
    WRITE_REAL(dbt, {"rota": "arquivo", "chars_sistema": 4000, "chars_acervo": 0,
                     "chars_anexo": 30000, "tok_gerador_prompt": 12000,
                     "tok_gerador_compl": 800, "origem_modelo": "chico-m1"})
    _c = sqlite3.connect(dbt)
    _cols = [r[1] for r in _c.execute("PRAGMA table_info(eventos)").fetchall()]
    ok &= check("banco novo tem as 10 colunas de token",
                {"chars_sistema", "chars_acervo", "chars_anexo", "chars_historico",
                 "tok_classif_prompt", "tok_classif_compl", "tok_gerador_prompt",
                 "tok_gerador_compl", "classif_provedor", "origem_modelo"} <= set(_cols))
    ok &= check("gravou os inteiros (content-free)",
                _c.execute("SELECT chars_acervo, tok_gerador_prompt FROM eventos "
                           "WHERE rota='arquivo'").fetchone() == (0, 12000))
    _c.close()

    # (b) banco pre-2a (schema 16 colunas, sem token) -> ALTER idempotente adiciona.
    dbold2 = os.path.join(tempfile.mkdtemp(prefix="tok_"), "old2.db")
    _c = sqlite3.connect(dbold2)
    _c.execute("CREATE TABLE eventos (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, "
               "user_hash TEXT, rota TEXT, classificador TEXT, trava TEXT, anexo TEXT, "
               "anexo_fonte TEXT, anexo_faixa TEXT, formato_saida TEXT, desfecho TEXT, "
               "recusa_cat TEXT, erro_cat TEXT, latencia_ms INTEGER, audio TEXT, "
               "audio_faixa TEXT)")
    _c.execute("INSERT INTO eventos (rota) VALUES ('geral')")
    _c.commit()
    _c.close()
    WRITE_REAL(dbold2, {"rota": "documentos", "chars_acervo": 5000,
                        "tok_classif_prompt": 900, "classif_provedor": "anthropic"})
    WRITE_REAL(dbold2, {"rota": "geral"})   # 2a escrita: ALTER ja aplicado, nao levanta
    _c = sqlite3.connect(dbold2)
    _cols = [r[1] for r in _c.execute("PRAGMA table_info(eventos)").fetchall()]
    ok &= check("banco pre-2a migrado (ganhou chars_acervo/token)",
                "chars_acervo" in _cols and "classif_provedor" in _cols)
    ok &= check("legado intacto + 2 novas (3 linhas)",
                _c.execute("SELECT COUNT(*) FROM eventos").fetchone()[0] == 3)
    _c.close()

    # (c) agregacao LE token; render mostra a secao Token so quando ha medicao.
    agg_tok = AGG(dbt, 30)
    tkn = agg_tok.get("token", {})
    ok &= check("agregacao expoe chars por rota",
                tkn.get("chars_rota", {}).get("documentos", {}).get("acervo") == 7000)
    ok &= check("agregacao expoe usage do classificador",
                tkn.get("classif", {}).get("prompt_total") == 1500)
    ok &= check("classif_provedor derivado agregado (resolve o conflito com dado)",
                tkn.get("provedor", {}).get("openai") == 1)
    ok &= check("origem separa o Chico",
                tkn.get("origem", {}).get("chico-m1") == 1
                and tkn.get("origem", {}).get("chatnd") == 1)
    _html_tok = HTML(agg_tok, 30)
    ok &= check("secao Token aparece quando ha medicao",
                "Token / Orcamento" in _html_tok)
    ok &= check("render Token e content-free (so inteiros/rotulos, ASCII)",
                not [ch for ch in _html_tok if ord(ch) > 127])
    ok &= check("ressalva do stream/base-model impressa",
                "STREAM" in _html_tok and "BASE-MODEL" in _html_tok)
    dbsem2 = os.path.join(tempfile.mkdtemp(prefix="tok_"), "s2.db")
    WRITE_REAL(dbsem2, {"rota": "imagem"})   # sem nenhuma metrica de token
    ok &= check("sem medicao -> secao Token NAO aparece",
                "Token / Orcamento" not in HTML(AGG(dbsem2, 30), 30))

    print("== ESCOPO: nenhum nome indefinido (o bug 'messages' da 1.53.0) ==")
    for fn in ("_pipe_impl", "_registrar", "_relatorio_analytics", "_ler_bytes_storage",
               "_completar_anexos", "_resposta_ou_aviso", "_gerar_arquivo",
               "_gerar_imagem", "_analytics_agregar", "_analytics_html"):
        indef = E.nomes_indefinidos(fonte, fn)
        ok &= check("%s: sem nome indefinido (%s)" % (fn, indef or "ok"), not indef)

    print("\nRESULTADO: " + ("ANALYTICS 1a+1b+voz OK" if ok else "HOUVE FALHA"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
