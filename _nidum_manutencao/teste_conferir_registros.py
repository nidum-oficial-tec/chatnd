# -*- coding: ascii -*-
"""
Prova do `conferir_registros` - escrita ANTES das duas classes novas.

CADA CASO AQUI E UM REGISTRO VENCIDO REAL, nao um exemplo inventado. E a
diferenca importa: um teste com fixture inventada prova que o codigo faz o que o
codigo faz. Estes provam que ele pega o que JA PASSOU despercebido - por semanas,
com a suite verde.

OS SEIS CASOS, e o dano que cada um causou:

  valve_fantasma        doc descrevia valve que nao existe. Alguem procura o
                        interruptor no painel e nao acha; conclui que a doc esta
                        certa e o painel, quebrado.
  modelo_revogado       modelo citado na doc que foi revogado/renomeado. O caso
                        do A.2: cinco correcoes de uma vez.
  id_fantasma           id de colecao apagada ainda citado. BASE_CONHECIMENTO_ID
                        apontou para duas colecoes apagadas, e so a valve do
                        painel salvava.
  fixture_vencida       fixture com caminho que a reformulacao renomeou. Custou
                        NOVE de dezenove caminhos do mapa_assuntos mortos, por
                        semanas, com o DIAL_FASE3 ligado e a etiqueta de assunto
                        valendo zero. A suite ficava VERDE.
  frac_catastrofe       FRAC_CATASTROFE fora de 0,25. Nasce do plano de migracao:
                        a rodada B sobe para 0,35 e PRECISA voltar. Um freio
                        afrouxado que ninguem restaurou nao da erro nenhum - ele
                        so deixa de proteger, e a proxima remocao em massa passa.
  base_indevida         base com contagem != 0 que nao devia receber arquivo.
                        Pasta-mae declarada como excluida cujo destino recebeu
                        conteudo assim mesmo: e o unico sintoma observavel de um
                        roteamento errado.

USO: py _nidum_manutencao/teste_conferir_registros.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conferir_registros as CR  # noqa: E402

falhas = []


def check(nome, cond):
    print(("  OK   " if cond else "  FALHOU  ") + nome)
    if not cond:
        falhas.append(nome)


def classes(achados):
    return sorted({a["classe"] for a in achados})


def main():
    print("== FRAC_CATASTROFE: o freio que a migracao afrouxa e alguem esquece ==")
    check("0.25 (o valor de desenho) -> nada a relatar",
          CR.conferir_frac_catastrofe("0.25") == [])
    check("0,25 com virgula tambem passa",
          CR.conferir_frac_catastrofe("0,25") == [])
    check("ausente -> nada (o padrao do codigo e 0.25)",
          CR.conferir_frac_catastrofe(None) == [])
    a = CR.conferir_frac_catastrofe("0.35")
    check("0.35 (o valor da rodada B) -> ACUSA", len(a) == 1)
    check("o achado diz o valor encontrado", "0.35" in str(a))
    check("e diz o valor esperado", "0.25" in str(a))
    check("0.10 (mais apertado que o desenho) tambem acusa",
          len(CR.conferir_frac_catastrofe("0.10")) == 1)
    check("lixo nao quebra o conferidor",
          isinstance(CR.conferir_frac_catastrofe("abacaxi"), list))

    print("")
    print("== base que nao devia receber arquivo ==")
    # O CASO QUE A VERSAO ANTIGA NAO PEGAVA, e que nenhum teste pegaria enquanto
    # as fixtures colocassem o mesmo nome nos dois lados: as contagens vinham SO
    # das colecoes configuradas, e pasta excluida nao tem colecao configurada. A
    # intersecao era vazia por construcao - zero contra zero, verde permanente.
    # Estas fixtures imitam o mundo real: as contagens trazem TODAS as colecoes do
    # painel, inclusive uma criada fora do config.
    do_painel = {"Produtos": 141, "Financas": 3, "Tecnologia": 107}
    excluidas = ["0 - Comece por aqui", "4 - Pastas de Trabalho", "Financas"]
    a = CR.conferir_bases_vazias(do_painel, excluidas)
    check("base criada FORA do config, com conteudo -> ACUSA", len(a) == 1)
    check("o achado NOMEIA a base", "Financas" in str(a))
    check("e diz quantos", "3" in str(a))
    check("excluida SEM base nenhuma -> silencio (o esperado)",
          CR.conferir_bases_vazias({"Produtos": 141}, excluidas) == [])
    check("excluida com base VAZIA -> silencio (aceitavel)",
          CR.conferir_bases_vazias({"Financas": 0}, excluidas) == [])
    check("base legitima com conteudo -> silencio",
          CR.conferir_bases_vazias({"Produtos": 141}, ["Financas"]) == [])
    # Acento: "Financas" no config e "Financas" com cedilha no painel sao a mesma
    # pasta, e escapar por acento seria a mesma cegueira por outra porta.
    check("acento nao faz a base escapar",
          len(CR.conferir_bases_vazias({u"Finan\u00e7as": 3}, ["Financas"])) == 1)

    print("\n== o catalogo do painel NAO pode falhar calado ==")
    # O DEFEITO, achado rodando o proprio conferidor em 10/09/2026: a coleta do
    # catalogo fazia `except Exception: catalogo = None` e seguia. Sem catalogo,
    # so as colecoes DECLARADAS entram na conta - e colecao_fora_do_config filtra
    # fora justamente as declaradas. A intersecao fica vazia POR CONSTRUCAO e a
    # classe devolve ZERO, indistinguivel de "conferi e esta limpo".
    #
    # E o D37 pela terceira vez, agora dentro da classe escrita para consertar o
    # D37. Nao e distracao: e o que um `except` largo FAZ - transforma "falhei" em
    # "nada encontrado". Por isso a prova mora aqui e nao numa leitura.
    import json as _json
    import tempfile
    import urllib.request as _u

    tmp = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmp, "_scripts"), exist_ok=True)
    with open(os.path.join(tmp, "_scripts", "sync_config.json"), "w") as f:
        _json.dump({"colecoes": {"Produtos": {"id": "abc"}}}, f)
    os.environ["OPENWEBUI_BASE_URL"] = "http://exemplo.invalido"
    os.environ["OPENWEBUI_API_KEY"] = "x"
    original = _u.urlopen
    try:
        _u.urlopen = lambda *a, **k: (_ for _ in ()).throw(OSError("recusou"))
        out, motivo = CR._contagens_do_painel(tmp)
        check("catalogo indisponivel -> None (nao {} nem zero)", out is None)
        check("e o motivo aponta o endpoint que falhou",
              bool(motivo) and "/api/v1/knowledge/" in motivo)

        class _Resp(object):
            def __init__(self, corpo):
                self._c = corpo

            def read(self):
                return self._c

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        # A OUTRA FORMA da mesma falha: responde 200 com um dict que nao traz
        # 'items'. Sem esta metade, um endpoint que devolvesse {} passaria e a
        # classe ficaria cega de novo.
        _u.urlopen = lambda *a, **k: _Resp(b'{"detail":"nao autorizado"}')
        out2, motivo2 = CR._contagens_do_painel(tmp)
        check("catalogo sem 'items' -> None", out2 is None)
        check("e o motivo diz o que veio no lugar",
              bool(motivo2) and "dict" in motivo2)

        # PAGINACAO: o endpoint devolve {items,total} e so aceita `page`. Se a
        # conferencia lesse a primeira pagina e parasse, a colecao fora do config
        # que estivesse na pagina 2 nunca seria vista - e o relatorio diria
        # "limpo". E o defeito do PR #66 (count=10 num universo de doze) na porta
        # do lado. O painel abaixo tem 3 colecoes em 2 paginas.
        paginas = {
            1: b'{"items":[{"id":"a","name":"Produtos"},'
               b'{"id":"b","name":"Fonte"}],"total":3}',
            2: b'{"items":[{"id":"c","name":"Projetos"}],"total":3}',
        }

        def _por_pagina(req, *a, **k):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            n = 2 if "page=2" in url else 1
            return _Resp(paginas[n])

        _u.urlopen = _por_pagina
        out3, motivo3 = CR._contagens_do_painel(tmp)
        check("paginou ate o total (nao parou na pagina 1)",
              motivo3 is None and out3 is not None and len(out3) == 3)
        check("a colecao que so existia na pagina 2 entrou na conta",
              bool(out3) and "Projetos" in out3)

        # E se a paginacao NAO entregar o que o painel declara, e falha - nao
        # "achei menos". Concluir 'nada fora do config' sobre catalogo incompleto
        # e a propria mentira que a classe existe para evitar.
        _u.urlopen = lambda *a, **k: _Resp(
            b'{"items":[{"id":"a","name":"Produtos"}],"total":9}')
        out4, motivo4 = CR._contagens_do_painel(tmp)
        check("catalogo incompleto (1 de 9) -> None, nao conclusao",
              out4 is None and bool(motivo4) and "INCOMPLETO" in motivo4)
    finally:
        _u.urlopen = original
        os.environ.pop("OPENWEBUI_BASE_URL", None)
        os.environ.pop("OPENWEBUI_API_KEY", None)

    print("\n== o formato do achado e o mesmo das classes antigas ==")
    a = CR.conferir_frac_catastrofe("0.35")[0]
    for campo in ("classe", "detalhe", "onde", "consequencia"):
        check("achado tem '%s'" % campo, campo in a)
    check("a consequencia explica o dano, nao repete o fato",
          len(a["consequencia"]) > 40)

    print("\n== job VERDE ao encontrar (mesma regra do relatorio de orfaos) ==")
    check("achou -> codigo 2 (resultado, nao falha)",
          CR.codigo_de_saida([{"classe": "x"}]) == 2)
    check("nada -> codigo 0", CR.codigo_de_saida([]) == 0)
    check("1 fica reservado para o script quebrar",
          CR.codigo_de_saida([]) != 1 and CR.codigo_de_saida([{"classe": "x"}]) != 1)

    print("")
    if falhas:
        print("CONFERIR REGISTROS: %d FALHA(S)" % len(falhas))
        return 1
    print("CONFERIR REGISTROS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
