# -*- coding: ascii -*-
"""
TRAZ o publicado para o repositorio - o caminho INVERSO do publish.

POR QUE EXISTE (11/09/2026): a simulacao mediu e a direcao ficou clara - o painel
tem 373.947 bytes e o repo 366.012. O publicado e MAIOR. **Publicar apagaria
codigo que so existe em producao.** O conserto nao e publicar: e trazer o que
roda para o repositorio, revisar, e so entao o repo volta a ser a fonte da
verdade.

    ESTE SCRIPT NAO ESCREVE NO PAINEL. Ele so le de la e escreve em disco.

A ARMADILHA QUE ELE SE RECUSA A CAIR - e e a razao de ser um script e nao um `cp`:

    "o publicado esta a frente" NAO e a mesma coisa que
    "o publicado contem tudo que o repo tem".

Os dois lados podem ter andado. O repo mexeu 14 linhas depois do bump da 1.65.0;
se alguma dessas linhas NAO estiver no publicado, copiar por cima a apaga - e o
erro seria simetrico ao que estamos consertando, cometido na outra direcao, e por
cima de um trabalho que ninguem lembraria de procurar.

Por isso a copia so acontece quando o publicado e SUPERCONJUNTO do repo
(`so_no_repo == 0`). Quando nao e, o script RECUSA e lista as linhas que existem
so no repo, para serem reaplicadas por cima depois. Recusar com a lista na mao e
mais util que copiar e torcer.

A CONFERENCIA DE SEGREDO E OBRIGATORIA E NAO E OPCIONAL: o `content` publicado e
codigo-fonte com DEFAULTS de valve dentro. Um default pode ter recebido uma chave
digitada a mao no painel, e commitar isso vaza para o historico do git - onde nao
sai mais. O script procura os padroes conhecidos e PARA se achar; achar nada nao
e prova de que nao ha, entao a revisao humana do PR continua sendo a trava real.

USO:
    py _nidum_manutencao/_diff_publicado.py chatnd       # baixa
    py _nidum_manutencao/trazer_publicado.py chatnd      # confere e traz
    (-> git diff, revisar, commitar em branch, abrir PR)
"""

import difflib
import io
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _diff_publicado import ALVOS  # a mesma lista dos quatro, nao uma copia


# Padroes de segredo. A lista e curta de proposito: cada item aqui e uma forma
# que JA apareceu em codigo de verdade. Lista longa de regex vira ruido e some
# no meio das excecoes.
_SEGREDOS = (
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "chave estilo OpenAI (sk-...)"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "chave Anthropic (sk-ant-...)"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{20,}"), "token Bearer literal"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\."), "JWT literal"),
    (re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*[\"'][^\"'\s]{16,}[\"']"),
     "atribuicao de segredo com valor longo"),
)


def farejar_segredo(texto):
    """(linha, trecho_mascarado, o_que_e) para cada suspeita. NUNCA devolve o valor."""
    achados = []
    for n, linha in enumerate(texto.split("\n"), start=1):
        for rx, o_que in _SEGREDOS:
            m = rx.search(linha)
            if m:
                bruto = m.group(0)
                mascara = bruto[:6] + "..." + bruto[-2:] if len(bruto) > 12 else "..."
                achados.append((n, mascara, o_que))
                break
    return achados


def direcoes(repo, pub):
    """(so_no_pub, so_no_repo, blocos_so_no_repo). Mesma normalizacao do conferidor."""
    rl = repo.replace("\r\n", "\n").split("\n")
    pl = pub.replace("\r\n", "\n").split("\n")
    so_pub = so_repo = 0
    blocos = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, rl, pl).get_opcodes():
        if tag in ("delete", "replace"):
            so_repo += i2 - i1
            blocos.append((i1 + 1, i2, rl[i1:i2]))
        if tag in ("insert", "replace"):
            so_pub += j2 - j1
    return so_pub, so_repo, blocos


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    forcar = "--aceito-perder-o-repo" in sys.argv[1:]
    if not args:
        raise SystemExit("USO: py _nidum_manutencao/trazer_publicado.py <alvo>\n"
                         "Alvos: " + ", ".join(ALVOS))
    ident = args[0]
    if ident not in ALVOS:
        raise SystemExit("Alvo desconhecido: %s. Conheco: %s" % (ident, ", ".join(ALVOS)))
    _tipo, rel = ALVOS[ident]

    baixado = "_publicado_%s.py" % ident
    if not os.path.isfile(baixado):
        raise SystemExit(
            "Nao achei %s.\nRode antes:  py _nidum_manutencao/_diff_publicado.py %s"
            % (baixado, ident))

    pub = io.open(baixado, encoding="utf-8").read()
    if not os.path.isfile(rel):
        raise SystemExit("Nao achei %s no repositorio." % rel)
    repo = io.open(rel, encoding="utf-8").read()

    print("Alvo: %s" % ident)
    print("  publicado (em disco): %s  %d bytes" % (baixado, len(pub)))
    print("  repo                : %s  %d bytes" % (rel, len(repo)))
    print("")

    # 1. SEGREDO - antes de qualquer coisa. Um `git add` depois disto e
    #    irreversivel na pratica: sai do working tree, nao do historico.
    suspeitas = farejar_segredo(pub)
    if suspeitas:
        print("PAREI: o conteudo publicado tem %d trecho(s) com CARA DE SEGREDO."
              % len(suspeitas))
        for n, mascara, o_que in suspeitas[:10]:
            print("   linha %-5d %-40s %s" % (n, o_que, mascara))
        print("")
        print("Commitar isso poe o segredo no HISTORICO do git, de onde nao sai.")
        print("Confira no painel, troque por valve vazia, e so entao traga.")
        return 2
    print("  farejador de segredo: nada encontrado (nao e prova - revise o PR).")

    # 2. DIRECAO - a armadilha do cabecalho.
    so_pub, so_repo, blocos = direcoes(repo, pub)
    print("  so no PUBLICADO: %d linha(s)   |   so no REPO: %d linha(s)"
          % (so_pub, so_repo))
    print("")

    if so_repo and not forcar:
        print("RECUSEI COPIAR: ha %d linha(s) que existem SO NO REPO." % so_repo)
        print("Copiar por cima as apagaria - o mesmo erro que estamos consertando,")
        print("na direcao oposta. Os blocos (por linha do arquivo no repo):")
        for ini, fim, linhas in blocos[:12]:
            print("   linhas %d-%d:" % (ini, fim))
            for l in linhas[:3]:
                print("      %s" % l[:100])
            if len(linhas) > 3:
                print("      ... (+%d linha(s))" % (len(linhas) - 3))
        if len(blocos) > 12:
            print("   ... (+%d bloco(s))" % (len(blocos) - 12))
        print("")
        print("CAMINHO: traga o publicado, depois REAPLIQUE estes blocos por cima,")
        print("um a um, conferindo se cada um ainda faz sentido. Quando tiver")
        print("decidido bloco a bloco, repita com --aceito-perder-o-repo.")
        return 3

    if not so_pub and not so_repo:
        print("IDENTICOS. Nada a trazer.")
        return 0

    # 3. A COPIA. Escreve em disco e para - quem commita e voce, olhando o diff.
    io.open(rel, "w", encoding="utf-8", newline="\n").write(pub)
    print("ESCRITO: %s agora tem o conteudo PUBLICADO." % rel)
    print("")
    nao_ascii = sum(1 for c in pub if ord(c) > 127)
    if nao_ascii:
        print("AVISO: %d caractere(s) nao-ASCII - a regra da casa pede ASCII em"
              % nao_ascii)
        print("       _nidum_tools/*.py. Confira antes de commitar.")
    p = subprocess.run(["python", "-m", "py_compile", rel], capture_output=True)
    print("  py_compile: %s" % ("OK" if p.returncode == 0 else "FALHOU - NAO COMMITE"))
    print("")
    print("AGORA, e NAO antes:")
    print("  git diff -- %s          # leia. E codigo que ninguem revisou." % rel)
    print("  git checkout -b traz/%s" % ident)
    print("  git add %s && git commit" % rel)
    print("")
    print("O PR e a revisao. Este script nao commita nada de proposito: trazer")
    print("codigo de producao para o repo e exatamente o momento de ter um humano")
    print("lendo, e nao um passo a mais de automacao.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
