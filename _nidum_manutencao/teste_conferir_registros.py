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
import shutil
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

    print("\n== colecao fora do config: a comparacao e por ID ==")
    # O FALSO POSITIVO, medido em producao (10/09/2026): a primeira versao casava o
    # NOME do painel com a CHAVE do sync_config. As duas divergem DE PROPOSITO - a
    # chave e a pasta-mae do SharePoint ("1 - Fonte") e o nome e o rotulo da base
    # ("Fonte"). O relatorio acusou 'Fonte' (85 arquivos) e 'Reunioes' (78) como
    # fora do config: as duas MAIORES bases da casa, mantidas todo dia.
    #
    # Falso positivo aqui e pior que noutras classes: esta e a secao que alguem le
    # para perguntar "sobrou base velha?". Se ela acusa as duas maiores toda
    # semana, aprende-se a pular a secao - e no dia da base velha de verdade
    # ninguem esta olhando.
    contagens = {"Produtos": 209, "Fonte": 85, u"Reuni\u00f5es": 78, "Projetos": 17}
    ids_nome = {"Produtos": "id-prod", "Fonte": "id-fonte",
                u"Reuni\u00f5es": "id-reu", "Projetos": "id-proj"}
    declarados = ["id-prod", "id-fonte", "id-reu"]        # o config nao tem Projetos
    a = CR.conferir_colecoes_fora_do_config(contagens, ids_nome, declarados, [])
    check("so a base fora do config e acusada", len(a) == 1)
    check("e e a certa (Projetos)", "Projetos" in str(a))
    check("'Fonte' NAO e acusada (chave '1 - Fonte' x nome 'Fonte')",
          "Fonte" not in str(a))
    check("'Reunioes' NAO e acusada (chave '3 - Reunioes' x nome 'Reunioes')",
          u"Reuni\u00f5es" not in str(a))
    check("base fora do config e VAZIA -> silencio (espera exclusao manual)",
          CR.conferir_colecoes_fora_do_config(
              {"Projetos": 0}, {"Projetos": "id-proj"}, declarados, []) == [])
    check("pasta-mae declarada excluida continua casando por NOME",
          CR.conferir_colecoes_fora_do_config(
              {"Financas": 3}, {"Financas": "id-fin"}, declarados, ["Financas"]) == [])
    # Se o id nao chega (nome sem par no mapa), NAO se conclui que esta declarada:
    # sem id nao ha como afirmar que a esteira mantem, e o silencio seria conclusao.
    check("nome sem id conhecido -> acusa (nao presume declarada)",
          len(CR.conferir_colecoes_fora_do_config(
              {"Misteriosa": 4}, {}, declarados, [])) == 1)

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
              motivo3 is None and out3 is not None and len(out3[0]) == 3)
        check("a colecao que so existia na pagina 2 entrou na conta",
              bool(out3) and "Projetos" in out3[0])
        check("e o id dela viaja junto (a comparacao e por id)",
              bool(out3) and out3[1].get("Projetos") == "c")

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
    print("\n== PUBLICADO x REPOSITORIO (doc 14) ==")
    # A MAIOR LACUNA da varredura de cobertura: pipe e tools vao a producao por
    # API, manualmente - mergear na main NAO publica -, e nada comparava os dois
    # lados. O coracao do produto era o unico objeto que ninguem conferia.
    import tempfile as _tf
    raiz = _tf.mkdtemp()
    os.makedirs(os.path.join(raiz, "_nidum_tools"), exist_ok=True)
    alvo = os.path.join("_nidum_tools", "x.py")

    def _escrever(txt):
        with open(os.path.join(raiz, alvo), "w", encoding="utf-8") as f:
            f.write(txt)

    FONTE = '"""doc\nversion: 1.2.0\n"""\n\ndef f():\n    return 1\n'
    _escrever(FONTE)
    pub = (("funcao", "x", alvo),)

    a = CR.conferir_publicado(raiz, pub, leitor=lambda t, i: (FONTE, None))
    check("identico -> silencio", a == [])

    # Fim de linha e espaco a direita NAO sao divergencia - senao o alarme vira
    # ruido fixo, e alarme cronicamente vermelho e alarme desligado (D53).
    a = CR.conferir_publicado(
        raiz, pub,
        leitor=lambda t, i: (FONTE.replace("\n", "\r\n") + "   \n\n", None))
    check("CRLF e espaco a direita NAO viram divergencia", a == [])

    # Mas comentario divergente VIRA: e justamente o que denuncia hotfix feito
    # direto no painel.
    a = CR.conferir_publicado(
        raiz, pub, leitor=lambda t, i: (FONTE + "# hotfix no painel\n", None))
    check("linha a mais no painel -> publicado_divergente",
          len(a) == 1 and a[0]["classe"] == "publicado_divergente")
    check("e o achado diz as DUAS versoes",
          "painel version=1.2.0" in a[0]["detalhe"] and "repo version=1.2.0" in a[0]["detalhe"])
    check("e NUNCA imprime o codigo (fonte tem valve e chave dentro)",
          "def f()" not in str(a))

    a = CR.conferir_publicado(raiz, pub, leitor=lambda t, i: ("", None))
    check("nao publicada -> publicado_ausente",
          len(a) == 1 and a[0]["classe"] == "publicado_ausente")

    # O ESTADO OBRIGATORIO: nao consegui olhar NUNCA vira "igual". O
    # /api/v1/models/ passou dias dizendo "nada encontrado" por nao conseguir
    # conferir (D57).
    a = CR.conferir_publicado(raiz, pub, leitor=lambda t, i: (None, "sem credencial"))
    check("nao consegui olhar -> nao_conferido (nunca silencio)",
          len(a) == 1 and a[0]["classe"] == "nao_conferido")

    # Artefato que nao existe no repo nao e desta classe.
    a = CR.conferir_publicado(raiz, (("funcao", "y", os.path.join("_nidum_tools", "nao_existe.py")),),
                              leitor=lambda t, i: (FONTE, None))
    check("artefato ausente do repo -> nao e desta classe", a == [])

    shutil.rmtree(raiz, ignore_errors=True)

    print("\n== o formato do achado e o mesmo das classes antigas ==")
    a = CR.conferir_frac_catastrofe("0.35")[0]
    for campo in ("classe", "detalhe", "onde", "consequencia"):
        check("achado tem '%s'" % campo, campo in a)
    check("a consequencia explica o dano, nao repete o fato",
          len(a["consequencia"]) > 40)

    print("\n== QUAL LADO esta a frente (a pergunta que o tamanho nao responde) ==")
    # Saber que 1.148 linhas diferem NAO diz se o painel esta atrasado (e quanto)
    # ou se alguem editou producao pela tela - e as duas exigem acoes opostas.
    # Se o publicado casa com um commit antigo, o painel esta simplesmente ATRAS.
    import subprocess as _sp
    rel = os.path.join("_nidum_tools", "chatnd.py")
    shas = _sp.run(["git", "log", "-n", "3", "--format=%H", "--", rel],
                   capture_output=True, text=True).stdout.split()
    if len(shas) >= 3:
        antigo = _sp.run(["git", "show", "%s:_nidum_tools/chatnd.py" % shas[2]],
                         capture_output=True, text=True, encoding="utf-8").stdout
        r = CR._commit_correspondente(".", rel, CR._normalizar_fonte(antigo))
        check("conteudo de um commit antigo -> acha a ancora",
              r is not None and r[2] == 2)
        check("e devolve sha curto e data", bool(r and r[0] and r[1]))
        r2 = CR._commit_correspondente(".", rel, "conteudo que nunca existiu")
        check("conteudo que nunca existiu no repo -> None (nao inventa ancora)",
              r2 is None)
    else:
        check("(pulado: historico curto demais neste checkout)", True)

    print("\n== o tamanho da diferenca e HONESTO ==")
    # A primeira versao contava posicao a posicao (zip). Com UMA linha inserida
    # no topo, todas as seguintes ficam deslocadas e contam como diferentes: a
    # rodada em producao devolveu "5655 linhas diferentes" num arquivo de 6559.
    # Numero inflado e PIOR que numero ausente - a ausencia manda medir; o
    # inflado manda republicar tudo, com a confianca de quem tem um dado na mao.
    base = chr(10).join("l%d" % i for i in range(100))
    d, prim = CR._tamanho_da_diferenca(base, "nova" + chr(10) + base)
    check("1 linha inserida no topo -> 1 (nao 100)", d == 1)
    check("e aponta a linha 1", prim == 1)
    d, prim = CR._tamanho_da_diferenca(base, base.replace("l50", "X50"))
    check("1 linha trocada no meio -> 1", d == 1)
    check("e aponta a linha 51", prim == 51)
    d, prim = CR._tamanho_da_diferenca(base, base)
    check("identicos -> 0 e nenhuma linha", d == 0 and prim is None)

    print("\n== o relatorio NAO some com classe sem titulo ==")
    # O DEFEITO, e durou uma rodada: o laco era `for classe in _TITULOS`, entao
    # classe sem titulo entrava na CONTAGEM do cabecalho e nunca era impressa.
    # Saiu "81 divergencias em 7 classes" com SEIS secoes na tela - e as duas que
    # faltavam eram justamente as recem-escritas. E o D51 na propria ferramenta:
    # o universo do relatorio era uma lista DECLARADA.
    import io as _io
    import contextlib as _ctx
    buf = _io.StringIO()
    with _ctx.redirect_stdout(buf):
        CR.relatar([CR._achado("classe_inedita", "detalhe x", "onde", "dano y")])
    saida = buf.getvalue()
    check("classe desconhecida APARECE no relatorio", "classe_inedita" in saida)
    check("e avisa que falta titulo", "SEM TITULO" in saida)
    check("e o detalhe nao se perde", "detalhe x" in saida)
    # As duas classes do publicado agora TEM titulo - se alguem as remover do
    # mapa, o teste acima garante que elas ainda aparecem, mas feias.
    check("publicado_divergente tem titulo", "publicado_divergente" in CR._TITULOS)
    check("publicado_ausente tem titulo", "publicado_ausente" in CR._TITULOS)

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
