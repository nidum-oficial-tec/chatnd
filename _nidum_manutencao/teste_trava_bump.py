# -*- coding: ascii -*-
"""Provas OFFLINE da trava de bump (sem git, sem rede).

O `julgar` recebe os dois lados como TEXTO, de proposito: a decisao da trava se
prova sem repositorio, sem PR e sem Action. O que sobra para a Action e so ler o
git - e essa parte falha ruidosamente (exit 3), nao silenciosamente.
"""

import sys

from trava_bump import julgar, versao_do_texto


CAB = 'title: X\nversion: %s\ndescription: y\n"""\n'


def _fonte(versao, corpo=""):
    return '"""\n' + (CAB % versao) + corpo


def _lado(mapa):
    return lambda c: mapa.get(c)


FALHAS = []


def checa(nome, condicao, extra=""):
    if condicao:
        print("  ok   %s" % nome)
    else:
        print("  FALHA %s %s" % (nome, extra))
        FALHAS.append(nome)


def main():
    print("teste_trava_bump")

    # 1. Mudou o corpo e a versao ficou parada -> reprova. E o caso de 11/09.
    r = julgar(["a.py"],
               _lado({"a.py": _fonte("1.65.0", "x = 1\n")}),
               _lado({"a.py": _fonte("1.65.0", "x = 2\n")}))
    checa("conteudo mudou, versao parada = SEM_BUMP", r and r[0][1] == "SEM_BUMP", r)

    # 2. Mudou o corpo E a versao -> passa.
    r = julgar(["a.py"],
               _lado({"a.py": _fonte("1.65.0", "x = 1\n")}),
               _lado({"a.py": _fonte("1.66.0", "x = 2\n")}))
    checa("conteudo e versao mudaram = BUMP", r and r[0][1] == "BUMP", r)

    # 3. Conteudo identico (entrou no diff por renomeacao/modo) -> nao acusa.
    igual = _fonte("1.65.0", "x = 1\n")
    r = julgar(["a.py"], _lado({"a.py": igual}), _lado({"a.py": igual}))
    checa("conteudo identico nao gera achado", r == [], r)

    # 4. Arquivo novo passa - nao ha de que subir.
    r = julgar(["a.py"], _lado({}), _lado({"a.py": _fonte("0.1.0")}))
    checa("arquivo novo = NOVO", r and r[0][1] == "NOVO", r)

    # 5. Arquivo SEM linha de versao dos dois lados, com corpo mudado: reprova.
    #    "" == "" e verdadeiro, e e exatamente o que se quer - publicado sem
    #    etiqueta e o caso original em pior estado, nao uma isencao.
    r = julgar(["a.py"],
               _lado({"a.py": "sem cabecalho\nx = 1\n"}),
               _lado({"a.py": "sem cabecalho\nx = 2\n"}))
    checa("sem version dos dois lados = SEM_BUMP", r and r[0][1] == "SEM_BUMP", r)

    # 6. Remocao nao e assunto da trava, mas APARECE (nao passa calada).
    r = julgar(["a.py"], _lado({"a.py": _fonte("1.0.0")}), _lado({}))
    checa("removido e relatado, nao reprovado",
          r and r[0][1] == "REMOVIDO", r)

    # 7. So a linha de versao mudou -> BUMP (esquisito, inofensivo, e passa).
    r = julgar(["a.py"],
               _lado({"a.py": _fonte("1.0.0", "x = 1\n")}),
               _lado({"a.py": _fonte("1.0.1", "x = 1\n")}))
    checa("so a versao mudou = BUMP", r and r[0][1] == "BUMP", r)

    # 8. A leitura do version e a MESMA dos publicadores (com espacos, em
    #    qualquer caixa) - se divergir, a trava aprova o que o publish rotula
    #    diferente.
    checa("version com espacos", versao_do_texto("  Version :  2.8.2 \n") == "2.8.2")
    checa("sem version = string vazia", versao_do_texto("nada aqui") == "")

    print("")
    if FALHAS:
        print("FALHOU: %d" % len(FALHAS))
        return 1
    print("TODOS OS TESTES PASSARAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
