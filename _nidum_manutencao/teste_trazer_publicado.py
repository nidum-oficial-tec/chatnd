# -*- coding: ascii -*-
"""Provas OFFLINE do trazer_publicado (sem rede, sem painel, sem escrever no repo).

As duas funcoes que decidem - `farejar_segredo` e `direcoes` - sao PURAS. A parte
que escreve em disco nao e provada aqui de proposito: ela e um `write` e um
`print`, e o que pode dar errado nela e o operador nao ler o diff - o que teste
nenhum pega.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trazer_publicado import direcoes, farejar_segredo

FALHAS = []


def checa(nome, cond, extra=""):
    if cond:
        print("  ok   %s" % nome)
    else:
        print("  FALHA %s %s" % (nome, extra))
        FALHAS.append(nome)


def main():
    print("teste_trazer_publicado")

    # --- direcoes: a armadilha que motivou o script -------------------------
    base = "a\nb\nc\n"
    checa("identicos = 0 e 0", direcoes(base, base)[:2] == (0, 0))

    # Publicado e SUPERCONJUNTO: so ele tem linhas a mais -> copiar e seguro.
    so_pub, so_repo, _ = direcoes("a\nb\nc\n", "a\nb\nNOVA\nc\n")
    checa("publicado superconjunto = so_repo 0", so_repo == 0 and so_pub == 1,
          (so_pub, so_repo))

    # O CASO QUE O SCRIPT RECUSA: os dois lados andaram. Copiar por cima
    # apagaria a linha que so o repo tem.
    so_pub, so_repo, blocos = direcoes("a\nSO_DO_REPO\nc\n", "a\nSO_DO_PAINEL\nc\n")
    checa("os dois andaram = so_repo > 0", so_repo > 0 and so_pub > 0, (so_pub, so_repo))
    checa("e os blocos do repo vem junto (para reaplicar)",
          blocos and "SO_DO_REPO" in "\n".join(blocos[0][2]), blocos)

    # Fim de linha nao inventa divergencia (mesma normalizacao do conferidor).
    checa("CRLF nao vira diferenca", direcoes("a\nb\n", "a\r\nb\r\n")[:2] == (0, 0))

    # --- farejador de segredo -----------------------------------------------
    checa("chave sk- e pega",
          any("OpenAI" in o for _, _, o in farejar_segredo("K = 'sk-" + "a" * 30 + "'")))
    checa("chave sk-ant- e pega",
          bool(farejar_segredo("K = 'sk-ant-" + "b" * 30 + "'")))
    checa("JWT e pego",
          bool(farejar_segredo("t = 'eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0.abc'")))
    checa("Bearer literal e pego",
          bool(farejar_segredo('h = "Bearer ' + "c" * 30 + '"')))
    checa("api_key = valor longo e pego",
          bool(farejar_segredo('api_key = "' + "d" * 30 + '"')))

    # NAO PODE dar falso positivo no codigo normal do repo - farejador que grita
    # sempre e farejador desligado (D53).
    limpo = (
        'API_KEY: str = ""\n'
        'token = os.environ.get("NIDUM_TOKEN", "")\n'
        'headers = {"Authorization": "Bearer %s" % token}\n'
        'password = valve.password\n'
        'SENHA_PADRAO = ""\n'
    )
    achados = farejar_segredo(limpo)
    checa("valve vazia / env / interpolacao NAO sao segredo", achados == [], achados)

    # E o valor NUNCA sai inteiro no relato.
    segredo = "sk-" + "z" * 40
    rel = farejar_segredo("K='" + segredo + "'")
    checa("o relato MASCARA o valor",
          rel and segredo not in rel[0][1] and "..." in rel[0][1], rel)

    print("")
    if FALHAS:
        print("FALHOU: %d" % len(FALHAS))
        return 1
    print("TODOS OS TESTES PASSARAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
