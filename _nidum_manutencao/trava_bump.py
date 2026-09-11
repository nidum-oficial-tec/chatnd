# -*- coding: ascii -*-
"""
TRAVA A: quem muda um arquivo PUBLICADO tem que mexer no `version:`.

POR QUE EXISTE (11/09/2026, o achado que a motivou):
  O conferidor comparou o que esta PUBLICADO no painel com o que esta no repo:

    chatnd                    painel 1.65.0 x repo 1.65.0 -> 1148 linhas diferentes
    gerador_de_arquivos_nidum painel  2.8.2 x repo  2.8.2 ->  543 linhas diferentes

  MESMO NUMERO DE VERSAO, CONTEUDO DIFERENTE. E isso e pior que uma versao
  defasada: uma versao defasada se ve e se conta ("o painel esta 3 atras"). Duas
  coisas diferentes com o mesmo rotulo nao se veem - o numero AFIRMA que sao
  iguais, e quem le acredita nele em vez de conferir.

  Aqui o pipe e as tools sao publicados POR API, MANUALMENTE: mergear na main NAO
  publica (ver a REGRA DA DOC no CLAUDE.md). Entao o numero de versao e o UNICO
  fio que liga "o que esta no ar" a "o que esta no repo". Se ele para de se mexer,
  o fio arrebenta em silencio.

O QUE ESTA TRAVA FAZ - e o que ela NAO faz:
  FAZ: recusa um PR que altere um dos arquivos publicados sem mudar o `version:`.
  NAO FAZ: nao garante que o publicado corresponda ao repo. Ela cuida do ROTULO,
  nao do CONTEUDO. Quem confere o conteudo e o conferidor de registros (a classe
  `publicado_divergente`), que ja existe e foi quem achou o problema.

  Dito de outro jeito, e para nao vender o que ela nao entrega: esta trava sozinha
  nao teria impedido a divergencia de 11/09 - ela DOCUMENTA a mudanca. O que fecha
  o buraco e publicar pelo repositorio (e nao da maquina de alguem) somado ao
  conferidor. A trava e a parte barata e util de um conserto maior.

SEM ESCAPE, DE PROPOSITO: nao ha marcador de "desta vez nao precisa". Trava com
  porta dos fundos vira porta dos fundos. Se um caso legitimo aparecer - mover o
  arquivo, corrigir uma virgula do docstring - o custo de obedecer e UMA LINHA
  (subir o patch). Versao que anda sem comportamento novo nao machuca ninguem;
  comportamento novo com versao parada foi o que custou a investigacao de 11/09.

USO:
  python _nidum_manutencao/trava_bump.py --base origin/main
  (sem --base, compara com o merge-base de origin/main)
"""

import argparse
import os
import re
import subprocess
import sys

# Os arquivos que sobem por API e cujo numero de versao e a unica etiqueta do que
# esta no ar. Quem acrescentar um publicado novo acrescenta aqui - e a lista e a
# mesma do `_PUBLICADOS` do conferir_registros.py DE PROPOSITO (as duas frentes
# falam dos mesmos quatro arquivos; divergir seria uma delas mentir).
PUBLICADOS = (
    os.path.join("_nidum_tools", "chatnd.py"),
    os.path.join("_nidum_tools", "gerador_de_arquivos_nidum.py"),
    os.path.join("_nidum_tools", "relatorio_ambientes_nidum.py"),
    os.path.join("_nidum_tools", "sharepoint_nidum.py"),
)


def versao_do_texto(texto):
    """O `version:` do cabecalho. Mesma leitura que os publicadores fazem.

    Devolve "" quando nao ha linha de versao - e "" != "" e falso, entao um
    arquivo sem versao nenhuma NAO passa por engano: cai no veredito de falta
    de bump, que e o comportamento certo (arquivo publicado sem etiqueta e o
    caso original, so que pior).
    """
    m = re.search(r"(?im)^\s*version\s*:\s*(.+)$", texto or "")
    return m.group(1).strip() if m else ""


def julgar(arquivos, ler_base, ler_topo):
    """Decide, sem tocar em git nem em disco - por isso da para testar offline.

    `arquivos` sao os caminhos alterados no PR que estao entre os PUBLICADOS.
    `ler_base(caminho)` e `ler_topo(caminho)` devolvem o texto de cada lado (ou
    None quando o arquivo nao existe daquele lado).

    Devolve lista de (caminho, veredito, detalhe). Veredito "BUMP" passa;
    "SEM_BUMP" reprova; "NOVO" passa (arquivo que nasce nao tem de que subir).
    """
    fora = []
    for caminho in arquivos:
        antes = ler_base(caminho)
        depois = ler_topo(caminho)
        if antes is None:
            fora.append((caminho, "NOVO", "arquivo novo (versao %s)"
                         % (versao_do_texto(depois) or "AUSENTE")))
            continue
        if depois is None:
            # Apagado no PR. Nao e assunto desta trava (e a regra de nunca
            # deletar cuida disso) - mas contar como aprovado calado seria a
            # trava mentindo sobre o que conferiu.
            fora.append((caminho, "REMOVIDO", "sumiu no PR - fora do escopo da trava"))
            continue
        if antes == depois:
            continue  # constou no diff (renomeacao, modo) mas o conteudo e o mesmo
        v_antes = versao_do_texto(antes)
        v_depois = versao_do_texto(depois)
        if v_antes == v_depois:
            fora.append((caminho, "SEM_BUMP",
                         "conteudo mudou e version continua %s"
                         % (v_antes or "AUSENTE")))
        else:
            fora.append((caminho, "BUMP", "%s -> %s"
                         % (v_antes or "AUSENTE", v_depois or "AUSENTE")))
    return fora


def _git(*args):
    p = subprocess.run(["git"] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout


def _mostrar(rev, caminho):
    rc, saida = _git("show", "%s:%s" % (rev, caminho.replace(os.sep, "/")))
    return saida if rc == 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main",
                    help="ref de comparacao (padrao: origin/main)")
    ap.add_argument("--topo", default="HEAD")
    args = ap.parse_args()

    rc, saida = _git("merge-base", args.base, args.topo)
    base = saida.strip() if rc == 0 and saida.strip() else args.base
    if rc != 0:
        # Sem merge-base o diff compararia arvores sem ancestral comum e acusaria
        # o repo inteiro. Melhor parar dizendo o que faltou do que reprovar um PR
        # por falta de historico (foi o que o clone raso fez com a ancora).
        print("ERRO: nao achei merge-base entre %s e %s. O checkout trouxe o "
              "historico? (fetch-depth: 0)" % (args.base, args.topo))
        sys.exit(3)

    rc, saida = _git("diff", "--name-only", base, args.topo)
    if rc != 0:
        print("ERRO: git diff falhou entre %s e %s." % (base, args.topo))
        sys.exit(3)
    mudados = [l.strip().replace("/", os.sep) for l in saida.splitlines() if l.strip()]
    alvos = [c for c in mudados if c in PUBLICADOS]

    print("Trava de bump: comparando %s..%s" % (base[:12], args.topo))
    if not alvos:
        print("Nenhum arquivo publicado foi tocado neste PR - nada a travar.")
        return 0

    achados = julgar(alvos,
                     lambda c: _mostrar(base, c),
                     lambda c: _mostrar(args.topo, c))
    reprovados = [a for a in achados if a[1] == "SEM_BUMP"]
    for caminho, veredito, detalhe in achados:
        print("  %-10s %s  (%s)" % (veredito, caminho, detalhe))

    if reprovados:
        print("")
        print("REPROVADO: %d arquivo(s) publicado(s) mudaram sem subir o version."
              % len(reprovados))
        print("")
        print("O numero de versao e o unico fio que liga o que esta NO AR ao que")
        print("esta no repo - aqui o publish e por API e o merge nao publica. Em")
        print("11/09/2026 dois arquivos tinham o MESMO numero do painel e 1.148 e")
        print("543 linhas diferentes; descobrir isso custou uma investigacao.")
        print("")
        print("Conserto: suba o `version:` no docstring do arquivo (e registre a")
        print("linha no changelog, conforme o CLAUDE.md).")
        for caminho, _, detalhe in reprovados:
            print("::error file=%s::version parado (%s) com conteudo alterado"
                  % (caminho.replace(os.sep, "/"), detalhe))
        return 1

    print("")
    print("OK: todo arquivo publicado alterado neste PR subiu de versao.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
