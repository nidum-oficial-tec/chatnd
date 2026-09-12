# -*- coding: ascii -*-
"""
Etiquetas de procedencia: equivalencia com o pipe, e o CUSTO medido.

Tres coisas sao provadas aqui, e a segunda e a que evita o defeito futuro:

  1. As etiquetas certas saem para os nomes certos, e nada sai para nome comum.
  2. A funcao do BACKEND e a do PIPE concordam - lendo o fonte do pipe do disco,
     nao uma copia. Duas definicoes da mesma regra em repositorios que publicam
     por caminhos diferentes e o D66 esperando acontecer: o agente e o pipe
     etiquetariam o MESMO documento de formas diferentes, que e pior que nenhum
     dos dois etiquetar.
  3. O CUSTO em chars, medido e impresso. "Irrelevante" era estimativa minha;
     esta semana mostrou o que acontece com estimativa nao medida.
"""

import ast
import io
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(_AQUI)

# CARREGA POR CAMINHO, e nao por `import open_webui.utils...`: o __init__ do
# pacote importa `typer`, que so existe dentro do container. O modulo em si
# depende de `re` e `unicodedata` e nada mais - e essa independencia e de
# proposito, porque uma regra de etiquetagem que so roda em producao nao se
# prova antes de ir para producao.
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "nidum_procedencia",
    os.path.join(_RAIZ, "backend", "open_webui", "utils", "nidum_procedencia.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
etiquetas_de_procedencia = _mod.etiquetas_de_procedencia
custo_em_chars = _mod.custo_em_chars
anotar_chunk = _mod.anotar_chunk

FALHAS = []


def checa(nome, cond, extra=""):
    if cond:
        print("  ok   %s" % nome)
    else:
        print("  FALHA %s %s" % (nome, extra))
        FALHAS.append(nome)


def _etiquetas_do_pipe():
    """Extrai `_etiquetas_trecho` do fonte do pipe e devolve a funcao viva.

    LE DO DISCO de proposito. Copiar a logica para ca criaria uma TERCEIRA
    definicao, e o teste passaria a provar que duas copias minhas concordam -
    que nao e a pergunta.
    """
    fonte = io.open(os.path.join(_RAIZ, "_nidum_tools", "chatnd.py"),
                    encoding="utf-8").read()
    arv = ast.parse(fonte)
    alvo = {}
    for n in arv.body:
        if isinstance(n, ast.FunctionDef) and n.name in ("_etiquetas_trecho", "_f3_fold"):
            alvo[n.name] = n
    if len(alvo) != 2:
        return None
    mod = ast.Module(body=[alvo["_f3_fold"], alvo["_etiquetas_trecho"]], type_ignores=[])
    # UM dicionario para globals E locals: funcao definida por exec resolve nome
    # nos GLOBALS, entao com dois dicionarios o `_etiquetas_trecho` nao enxerga o
    # `_f3_fold` que acabou de ser definido ao lado dele.
    amb = {"re": __import__("re"), "unicodedata": __import__("unicodedata")}
    exec(compile(mod, "<pipe>", "exec"), amb, amb)
    return amb.get("_etiquetas_trecho")


# Nomes reais do acervo, e os tres gatilhos. O ultimo e o caso que mais importa:
# nome comum NAO pode gerar etiqueta - etiqueta em tudo e etiqueta em nada.
_CASOS = [
    ("Juridico > Externo > Lei Municipal 1234.md", 1, "procedencia externa"),
    ("TEC > ippul_relatorio.md", 1, "ippul"),
    ("OPE > nd-externo_parecer.md", 1, "nd-externo"),
    ("ACA > ACA_Rascunho_Politica_v2.md", 1, "rascunho"),
    ("REU > Convergencia_Comite_19-08-2026.md", 1, "convergencia"),
    # Acentos por ESCAPE: o arquivo e ASCII (convencao do _nidum_manutencao)
    # e o caso precisa do nome acentuado para provar a dobra.
    ("REU > Converg\u00eancia_Comit\u00ea_19-08-2026.md", 1,
     "convergencia COM acento"),
    ("PROD > PROD_Manual_do_Produto.md", 0, "nome comum"),
    ("ACA > ACA_Demandas_Academia_Agosto_2026.md", 0, "nome comum 2"),
    ("", 0, "nome vazio"),
    (None, 0, "nome None"),
]


def main():
    print("teste_procedencia")

    # 1. As etiquetas certas, e nada em nome comum.
    for nome, quantas, rotulo in _CASOS:
        ets = etiquetas_de_procedencia(nome)
        checa("%-22s -> %d etiqueta(s)" % (rotulo, quantas), len(ets) == quantas, ets)

    checa("externo diz para NAO citar como posicao da Nidum",
          "NAO citar como posicao" in
          etiquetas_de_procedencia("x > Externo > lei.md")[0])

    # 2. EQUIVALENCIA COM O PIPE.
    do_pipe = _etiquetas_do_pipe()
    if do_pipe is None:
        checa("consegui ler _etiquetas_trecho do pipe", False,
              "nao achei a funcao - a comparacao NAO aconteceu")
    else:
        divergem = []
        for nome, _q, rotulo in _CASOS:
            a, b = etiquetas_de_procedencia(nome), do_pipe(nome)
            if a != b:
                divergem.append((rotulo, a, b))
        checa("backend e pipe concordam nos %d casos" % len(_CASOS),
              divergem == [], divergem[:2])

    # 3. O CUSTO, medido.
    print("")
    print("  CUSTO EM CONTEXTO (medido, nao estimado):")
    com = [c for c in _CASOS if c[1] > 0]
    mais_caro = max(custo_em_chars(n) for n, _q, _r in com)
    print("    etiqueta mais cara            : %d chars" % mais_caro)
    print("    trecho tipico do acervo       : ~1.000 chars")
    print("    5 resultados, TODOS etiquetados: +%d chars (%.1f%% sobre 5.000)"
          % (5 * mais_caro, 100.0 * 5 * mais_caro / 5000.0))
    print("    5 resultados, nenhum etiquetado: +0 chars")
    checa("nenhuma etiqueta passa de 200 chars", mais_caro <= 200, mais_caro)
    checa("nome comum custa ZERO (o caso mais frequente)",
          custo_em_chars("PROD > PROD_Manual_do_Produto.md") == 0)

    # 4. A FIACAO - o valor que o chamador recebe, nao a funcao isolada (D71).
    #    `anotar_chunk` e exatamente o que o `builtin.py` chama no laco dos
    #    resultados; provar aqui e provar o que sai para o agente.
    print("")
    base = {"content": "texto do trecho", "source": "x", "file_id": "f1"}
    c = anotar_chunk(dict(base), "Juridico > Externo > Lei 1234.md")
    checa("chunk etiquetado GANHA o campo procedencia", "procedencia" in c, c)
    checa("e o conteudo do trecho fica INTOCADO",
          c["content"] == base["content"] and c["source"] == base["source"], c)

    c2 = anotar_chunk(dict(base), "PROD > PROD_Manual.md")
    checa("chunk de nome comum NAO ganha a chave (ausente != vazia)",
          "procedencia" not in c2, c2)

    # E o `builtin.py` chama mesmo? Sem isto o teste provaria uma funcao que
    # ninguem usa - que e o D71 pela segunda vez.
    bt = io.open(os.path.join(_RAIZ, "backend", "open_webui", "tools",
                              "builtin.py"), encoding="utf-8").read()
    checa("builtin.py IMPORTA anotar_chunk",
          "from open_webui.utils.nidum_procedencia import anotar_chunk" in bt)
    checa("builtin.py CHAMA anotar_chunk no laco dos resultados",
          "anotar_chunk(chunk_info, fonte)" in bt)

    print("")
    if FALHAS:
        print("FALHOU: %d" % len(FALHAS))
        return 1
    print("TODOS OS TESTES PASSARAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
