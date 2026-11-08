# -*- coding: ascii -*-
"""
Prova offline do RASTRO DE BUSCA (backend/open_webui/utils/nidum_rastro.py).

O que este teste guarda, e que nenhuma leitura pega:
  1. CONTENT-FREE: a linha gravada nao contem o texto da consulta nem da
     pergunta - so tamanho e um booleano. Um rastro que vazasse texto
     violaria a regra de analytics sem conteudo.
  2. consulta_igual_pergunta compara sem caixa/acento e e None sem pergunta.
  3. ids distintos, em ordem, com teto.
  4. NUNCA levanta: banco inacessivel nao derruba a busca.
  5. as duas ferramentas chamam registrar() antes de devolver.

USO: py _nidum_tools/teste_rastro.py
"""

import os
import sqlite3
import sys
import tempfile
import time
import types

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(RAIZ, "backend")
sys.path.insert(0, BACKEND)

# Isola o modulo dos imports pesados do Open WebUI: so precisa de
# nidum_contagem._hash_usuario e de env.DATA_DIR.
TMP = tempfile.mkdtemp()
pkg = types.ModuleType("open_webui")
pkg.__path__ = [os.path.join(BACKEND, "open_webui")]
sys.modules["open_webui"] = pkg
env = types.ModuleType("open_webui.env")
env.DATA_DIR = TMP
sys.modules["open_webui.env"] = env

from open_webui.utils import nidum_rastro as nr  # noqa: E402

falhas = []


def check(nome, cond):
    print(("  OK   " if cond else "  FALHOU  ") + nome)
    if not cond:
        falhas.append(nome)


def main():
    print("== ultima pergunta ==")
    msgs = [{"role": "user", "content": "primeira"}, {"role": "assistant", "content": "x"},
            {"role": "user", "content": [{"type": "text", "text": "Em que fase"}, {"type": "image_url"}]}]
    check("pega a ultima do usuario, partes de texto", nr.ultima_pergunta(msgs) == "Em que fase")
    check("sem mensagens -> ''", nr.ultima_pergunta(None) == "")

    print("\n== ids em ordem ==")
    check("distintos, ordem da 1a aparicao", nr.ids_em_ordem(["a", "b", "a", None, "c"]) == ["a", "b", "c"])
    check("teto", len(nr.ids_em_ordem([str(i) for i in range(50)])) == nr.MAX_IDS)

    print("\n== linha content-free ==")
    segredo_c = "status do projeto fase planejamento execucao"
    segredo_p = "Em qual fase est" + chr(0xE1) + " cada projeto da Nidum?"
    linha = nr.montar_linha("u1", "query_knowledge_files", "selecionado", ["kb2", "kb1"], segredo_c,
                            segredo_p, ["f1", "f2", "f1"], 3, 1234, time.time())
    texto_linha = repr(linha)
    check("nao contem a consulta", segredo_c not in texto_linha)
    check("nao contem a pergunta", "cada projeto" not in texto_linha)
    check("guarda o tamanho da consulta", linha["consulta_chars"] == len(segredo_c))
    check("consulta diferente da pergunta -> 0", linha["consulta_igual_pergunta"] == 0)
    check("docs distintos em ordem", linha["docs"] == "f1,f2" and linha["n_docs"] == 2)
    check("bases ordenadas", linha["bases"] == "kb1,kb2")
    check("user_hash nao e o id cru", linha["user_hash"] != "u1")

    igual = nr.montar_linha("u1", "q", "todas", [], "EM QUAL fase esta cada projeto da nidum?", segredo_p,
                            [], 0, 0, None)
    check("igual sem caixa/acento -> 1", igual["consulta_igual_pergunta"] == 1)
    sem = nr.montar_linha("u1", "q", "todas", [], "x", "", [], 0, 0, None)
    check("sem pergunta -> None", sem["consulta_igual_pergunta"] is None)

    print("\n== grava e nunca levanta ==")
    nr.registrar("u1", "query_knowledge_files", "todas", ["kb1"], "abc", msgs, ["f1"], 1, 10, time.time())
    con = sqlite3.connect(os.path.join(TMP, "chatnd_analytics.db"))
    n = con.execute("SELECT count(*) FROM buscas").fetchone()[0]
    con.close()
    check("uma linha gravada", n == 1)
    env.DATA_DIR = os.path.join(TMP, "nao", "existe")
    try:
        nr.registrar("u1", "q", "todas", [], "abc", msgs, [], 0, 0, None)
        ok = True
    except Exception:
        ok = False
    check("banco inacessivel nao levanta", ok)

    print("\n== as ferramentas chamam o rastro ==")
    with open(os.path.join(BACKEND, "open_webui", "tools", "builtin.py"), encoding="utf-8") as f:
        fonte = f.read()
    for nome in ("query_knowledge_files", "search_knowledge_files"):
        ini = fonte.index("async def %s(" % nome)
        fim = fonte.index("\nasync def ", ini + 10)
        corpo = fonte[ini:fim]
        check("%s recebe __messages__" % nome, "__messages__: Optional[list] = None" in corpo)
        check("%s chama registrar antes de devolver" % nome,
              "registrar(" in corpo and corpo.index("registrar(") < corpo.rindex("return json.dumps("))

    print("")
    if falhas:
        print("RASTRO: %d FALHA(S)" % len(falhas))
        return 1
    print("RASTRO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
