# -*- coding: ascii -*-
"""
Prova da CONTAGEM DE USO do agente (D81, paga em 21/09/2026).

O que este teste prova, em ordem:
  1. o texto de saida IGNORA os itens de ferramenta - senao um turno que so
     chamou tools pareceria ter respondido;
  2. as ferramentas sao contadas nos itens `function_call`, nao no relato (D90);
  3. os quatro desfechos: ok / vazio / erro / truncado;
  4. a heuristica do D85 (muita ferramenta, pouco texto) e os seus limites -
     inclusive o falso positivo conhecido;
  5. o banco: cria a tabela, acrescenta `origem` de forma idempotente, e
     NULL continua significando 'pipe';
  6. contar() NUNCA levanta - contabilidade nao derruba resposta;
  7. FIACAO: o middleware importa e chama nos dois pontos.

USO: py -3 teste_contagem.py
"""

import importlib.util
import io
import os
import sqlite3
import sys
import tempfile

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(_AQUI)
_MOD = os.path.join(_RAIZ, "backend", "open_webui", "utils", "nidum_contagem.py")

_spec = importlib.util.spec_from_file_location("nidum_contagem", _MOD)
_C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_C)

FALHAS = []


def checa(nome, cond, extra=""):
    print(("  ok   " if cond else "  FALHA ") + nome + (("  " + extra) if not cond else ""))
    if not cond:
        FALHAS.append(nome)


def texto(t):
    return {"type": "message", "content": t}


def tool(nome="x", resultado="conteudo devolvido pela ferramenta " * 40):
    """Um item de ferramenta COMO O MIDDLEWARE O MONTA (linha 4777).

    O `function_call_output` carrega o resultado em
    `output: [{"type": "input_text", "text": ...}]` - texto de verdade, e
    muito dele. A primeira versao deste fixture nao tinha esse campo, e por
    isso o teste NAO ficava vermelho quando a guarda era removida: ele
    descrevia o conserto em vez de prova-lo (D72). Fixture errada, nao
    assercao errada - e o conserto foi na fixture.
    """
    return [
        {"type": "function_call", "call_id": nome, "name": nome, "arguments": "{}"},
        {"type": "function_call_output", "call_id": nome,
         "output": [{"type": "input_text", "text": resultado}]},
    ]


def outs(*chamadas):
    """Achata os pares (chamada + resultado) num output, como o turno real."""
    plano = []
    for c in chamadas:
        plano.extend(c if isinstance(c, list) else [c])
    return plano


def main():
    print("teste_contagem")

    # 1. ---------------------------------------------------------------- texto
    print("")
    print("1. o texto de saida ignora os itens de FERRAMENTA")
    out = outs(tool("query"), texto("Resposta ao usuario."), tool("view"))
    checa("so o texto de mensagem entra", _C._texto_do_output(out) == "Resposta ao usuario.")
    checa("turno SO de ferramenta tem texto vazio",
          _C._texto_do_output(outs(tool(), tool(), tool())) == "")
    checa("output invalido nao levanta", _C._texto_do_output(None) == "")
    checa("texto em lista de blocos tambem e lido",
          _C._texto_do_output([{"type": "message",
                                "content": [{"text": "a"}, {"text": "b"}]}]) == "ab")

    # 2. ------------------------------------------------------------ ferramentas
    print("")
    print("2. as ferramentas sao CONTADAS no output, nao no relato (D90)")
    checa("3 function_call -> 3", _C._ferramentas_do_output(outs(tool(), tool(), tool())) == 3)
    checa("texto dizendo 'chamei 10 ferramentas' -> 0",
          _C._ferramentas_do_output([texto("Chamei 10 ferramentas.")]) == 0)

    # 3. --------------------------------------------------------------- desfecho
    print("")
    print("3. os quatro desfechos")
    checa("resposta normal -> ok", _C._desfecho("x" * 800, 1, None) == "ok")
    checa("texto vazio -> vazio", _C._desfecho("   ", 2, None) == "vazio")
    checa("erro vence tudo", _C._desfecho("x" * 800, 1, ValueError("x")) == "erro")
    checa("erro vence ate texto vazio", _C._desfecho("", 0, ValueError("x")) == "erro")

    # 4. ------------------------------------------------------- a heuristica D85
    print("")
    print("4. D85: muita ferramenta, pouco texto -> truncado")
    # o caso REAL: 10 view_knowledge_file, resposta de 235 chars
    real = outs(*([tool("view_knowledge_file") for _ in range(10)]
                  + [texto("x" * 235)]))
    checa("o caso c1 de 21/09 (10 tools, 235 chars) -> truncado",
          _C._desfecho(_C._texto_do_output(real), _C._ferramentas_do_output(real), None)
          == "truncado")
    checa("MUITA ferramenta + MUITO texto -> ok",
          _C._desfecho("x" * 5000, 10, None) == "ok")
    checa("POUCA ferramenta + pouco texto -> ok (resposta curta e legitima)",
          _C._desfecho("Sao 60 coautores.", 1, None) == "ok")
    checa("no limiar de ferramentas (>=%d)" % _C.MIN_FERRAMENTAS,
          _C._desfecho("x" * 10, _C.MIN_FERRAMENTAS, None) == "truncado"
          and _C._desfecho("x" * 10, _C.MIN_FERRAMENTAS - 1, None) == "ok")
    # O FALSO POSITIVO CONHECIDO, provado de proposito: um resumo curto e
    # legitimo depois de muita busca cai aqui. Esta no docstring do modulo como
    # limite declarado - o teste existe para que ninguem o descubra como surpresa.
    checa("FALSO POSITIVO declarado: resumo curto apos muita busca",
          _C._desfecho("Nao ha nada no acervo sobre isso.", 6, None) == "truncado")

    # 5. ------------------------------------------------------------------ banco
    print("")
    print("5. o banco: tabela, coluna `origem` idempotente, e NULL = pipe")
    tmp = os.path.join(tempfile.mkdtemp(), "t.db")
    # simula um banco que JA existe com linhas do pipe, sem a coluna nova
    con = sqlite3.connect(tmp)
    con.execute("CREATE TABLE eventos (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, "
                "user_hash TEXT, rota TEXT, classificador TEXT, trava TEXT, anexo TEXT, "
                "anexo_fonte TEXT, anexo_faixa TEXT, formato_saida TEXT, desfecho TEXT, "
                "recusa_cat TEXT, erro_cat TEXT, latencia_ms INTEGER)")
    con.execute("INSERT INTO eventos (ts, user_hash, rota, desfecho) "
                "VALUES ('2026-09-20T10:00:00','abc','documentos','ok')")
    con.commit(); con.close()

    linha = {"ts": "2026-09-21T12:00:00", "user_hash": "def", "rota": "chatnd-agente-beta",
             "desfecho": "ok", "erro_cat": None, "latencia_ms": 1234,
             "origem": "agente", "ferramentas": 2, "chars_saida": 900}
    _C._escrever(tmp, linha)
    _C._escrever(tmp, dict(linha, desfecho="truncado"))   # 2a vez: ALTER ja existe

    con = sqlite3.connect(tmp)
    cols = [r[1] for r in con.execute("PRAGMA table_info(eventos)")]
    checa("a coluna `origem` foi criada", "origem" in cols)
    checa("e as outras duas tambem", "ferramentas" in cols and "chars_saida" in cols)
    n_ag = con.execute("SELECT COUNT(*) FROM eventos WHERE origem='agente'").fetchone()[0]
    n_pipe = con.execute("SELECT COUNT(*) FROM eventos WHERE origem IS NULL").fetchone()[0]
    checa("2 linhas do agente", n_ag == 2, "(%d)" % n_ag)
    checa("a linha ANTIGA do pipe sobreviveu, com origem NULL", n_pipe == 1, "(%d)" % n_pipe)
    checa("escrever duas vezes NAO duplica a coluna",
          len([c for c in cols if c == "origem"]) == 1)
    con.close()

    # 6. ------------------------------------------------------------ nunca levanta
    print("")
    print("6. contar() nunca levanta - contabilidade nao derruba resposta")

    class _R:
        pass

    r = _R(); r.state = _R()
    try:
        _C.contar(r, None, None)          # metadata None, output None
        _C.contar(None, {}, [texto("x")])  # request None
        _C.contar(r, {"user_id": "u"}, "nao e lista")
        ok = True
    except Exception as e:
        ok = False
        print("     levantou: %s" % e)
    checa("tres chamadas degeneradas, nenhuma excecao", ok)

    # 7. ----------------------------------------------------------------- fiacao
    print("")
    print("7. FIACAO: o middleware importa e chama nos DOIS pontos")
    mw = io.open(os.path.join(_RAIZ, "backend", "open_webui", "utils", "middleware.py"),
                 encoding="utf-8").read()
    checa("importa contar e marcar_inicio",
          "from open_webui.utils.nidum_contagem import contar, marcar_inicio" in mw)
    checa("marca o inicio do turno", "marcar_inicio(request)" in mw)
    checa("conta no fim do turno", "contar(request, metadata, output)" in mw)
    i_conta = mw.find("contar(request, metadata, output)")
    i_outlet = mw.find("await outlet_filter_handler(ctx)", i_conta - 2000 if i_conta > 0 else 0)
    checa("conta ANTES dos filtros de saida (senao mede o filtro, nao o agente)",
          0 < i_conta < i_outlet)

    print("")
    if FALHAS:
        print("CONTAGEM: %d FALHA(S)" % len(FALHAS))
        return 1
    print("TODOS OS TESTES PASSARAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
