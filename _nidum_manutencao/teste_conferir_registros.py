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
