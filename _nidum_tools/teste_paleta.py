# -*- coding: utf-8 -*-
"""
Prova da PALETA: os seis nomes oficiais do brandbook sao canonicos, e os antigos
continuam funcionando como alias.

POR QUE ALIAS, E NAO TROCA SECA: estes CSS ja sairam dentro de arquivos que estao
no SharePoint e em caixas de e-mail. Um .html gerado em agosto continua abrindo
com --creme. Quebrar isso seria estragar entrega passada para arrumar nome.

O QUE O TESTE GUARDA, e que a leitura nao pega:

1. **Os dois blocos precisam ser iguais.** A paleta aparece duas vezes - no CSS
   do documento e no do deck - e sao copias POR DESENHO: CSS embutido em arquivo
   entregue nao pode depender de import. Copia que so uma metade recebe conserto
   e a forma mais comum de divergencia silenciosa nesta casa.

2. **Alias tem de APONTAR, nao repetir o hex.** Se alguem "consertar" um alias
   escrevendo o hex de novo, o alias deixa de seguir o oficial e a proxima
   mudanca de cor sai pela metade - com a cor certa em metade do arquivo.

USO: python _nidum_tools/teste_paleta.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
CAMINHO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "gerador_de_arquivos_nidum.py")

# Brand Book v2 (novembro de 2026): o branco entrou na paleta (e a BASE) e o azul
# prumo e o acento de nidum prumo. As outras seis nao mudaram de hex.
OFICIAIS = {"branco": "#FFFFFF", "areia": "#E5E0D5", "pedra": "#9D9890",
            "terracota": "#9A4A2E", "ceu": "#4F7187", "musgo": "#515E52",
            "escuro": "#1F1E1B", "prumo": "#174E78"}
ALIASES = {"creme": "areia", "cinza": "pedra", "azul": "ceu",
           "verde": "musgo", "preto": "escuro", "cremealt": "areia"}

falhas = []


def check(nome, cond):
    print(("  OK   " if cond else "  FALHOU  ") + nome)
    if not cond:
        falhas.append(nome)


def main():
    with open(CAMINHO, encoding="utf-8") as f:
        fonte = f.read()

    print("== os seis nomes oficiais, com o hex do brandbook ==")
    for nome, hexa in sorted(OFICIAIS.items()):
        n = fonte.count("--%s:%s" % (nome, hexa))
        check("--%-10s %s  (nos 2 blocos)" % (nome, hexa), n == 2)

    print("\n== os antigos APONTAM para o oficial, nao repetem o hex ==")
    for alias, oficial in sorted(ALIASES.items()):
        n = fonte.count("--%s:var(--%s)" % (alias, oficial))
        check("--%-9s -> var(--%s)" % (alias, oficial), n == 2)
        # o alias nao pode ter hex proprio em lugar nenhum
        solto = re.findall(r"--%s:#[0-9A-Fa-f]{6}" % alias, fonte)
        check("--%-9s sem hex proprio" % alias, not solto)

    print("\n== nenhum nome oficial ficou sem definicao ==")
    usados = set(re.findall(r"var\(--([a-z]+)\)", fonte))
    # --acento e definida POR PECA (a cor do produto), fora do bloco fixo.
    definidos = set(OFICIAIS) | set(ALIASES) | {"acento"}
    orfaos = sorted(u for u in usados if u not in definidos)
    check("nenhuma var(--x) sem definicao: %s" % (orfaos or "nenhuma"), not orfaos)

    print("\n== os dois blocos de paleta sao iguais ==")
    blocos = re.findall(r"--branco:#FFFFFF.*?--cremealt:var\(--areia\)", fonte, re.S)
    normal = [re.sub(r"[\s\"]+", "", b) for b in blocos]
    check("dois blocos encontrados", len(normal) == 2)
    check("e identicos entre si", len(set(normal)) == 1)

    print("")
    if falhas:
        print("PALETA: %d FALHA(S)" % len(falhas))
        return 1
    print("PALETA OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
