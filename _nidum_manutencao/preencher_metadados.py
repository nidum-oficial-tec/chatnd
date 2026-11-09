# -*- coding: ascii -*-
"""
PREENCHE meta['nidum'] (data_documento, tipo_doc, projeto) nos arquivos que JA
estao na base do ChatND - etapa C, 08/11/2026.

POR QUE: a busca por nome passou a ler esse metadado (PR #133). Os arquivos
novos o recebem da esteira; os ~1.400 que ja estao na base precisam de um
preenchimento. Isto NAO reindexa nada: usa POST /api/v1/files/{id}/nidum-meta,
que grava so meta['nidum'] - sem re-embutir, sem tocar updated_at.

DE ONDE VEM O METADADO: a mesma derivacao da esteira
(chatnd-conhecimento/_scripts/metadados_documento.py, lida de origin/main), a
partir do cabecalho do .md no repo da esteira (origem, pasta, tipo) e do texto.
O arquivo da base e casado com o .md pelo nome: a esteira grava o nome como o
caminho no repo com '/' -> ' > ' (sincronizar.py).

SEGURO POR PADRAO: sem --aplicar, so mostra o plano (quantos, por tipo,
quantos sem par no repo). Uso:
  py _nidum_manutencao/preencher_metadados.py            # simula
  py _nidum_manutencao/preencher_metadados.py --aplicar  # grava
"""

import collections
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
ESTEIRA = os.path.join(os.path.dirname(RAIZ), "esteira-conhecimento")
URL = os.environ.get("NIDUM_URL", "https://chatnd.nidumbrasil.com.br")


def token():
    for l in io.open(os.path.join(RAIZ, ".env.local"), encoding="utf-8"):
        if l.strip().startswith("NIDUM_API_KEY="):
            return l.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("sem NIDUM_API_KEY")


TOK = token()


def api(caminho, corpo=None):
    req = urllib.request.Request(URL + caminho, method="POST" if corpo is not None else "GET",
                                 data=None if corpo is None else json.dumps(corpo).encode("utf-8"),
                                 headers={"Authorization": "Bearer " + TOK, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def git_show(caminho):
    r = subprocess.run(["git", "-C", ESTEIRA, "-c", "core.quotepath=false", "show", "origin/main:" + caminho],
                       capture_output=True)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def carregar_derivacao():
    src = git_show("_scripts/metadados_documento.py")
    if not src:
        raise SystemExit("nao achei _scripts/metadados_documento.py em origin/main da esteira (git fetch?)")
    tmp = os.path.join(tempfile.gettempdir(), "metadados_documento_esteira.py")
    io.open(tmp, "w", encoding="utf-8").write(src)
    spec = importlib.util.spec_from_file_location("metadados_documento", tmp)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    aplicar = "--aplicar" in sys.argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    M = carregar_derivacao()
    repo = set(subprocess.run(["git", "-C", ESTEIRA, "-c", "core.quotepath=false", "ls-tree", "-r", "--name-only",
                               "-z", "origin/main"], capture_output=True).stdout.decode("utf-8").split("\0"))
    vistos, plano, sem_par = set(), [], []
    bases = api("/api/v1/knowledge/")
    bases = bases.get("items", bases) if isinstance(bases, dict) else bases
    for kb in bases:
        page = 1
        while True:
            it = api("/api/v1/knowledge/%s/files?limit=100&page=%d" % (kb["id"], page)).get("items", [])
            for f in it:
                if f["id"] in vistos:
                    continue
                vistos.add(f["id"])
                nome = f.get("filename", "")
                caminho = nome.replace(" > ", "/")
                if caminho not in repo:
                    sem_par.append(nome)
                    continue
                txt = git_show(caminho) or ""
                cab = re.search(r"<!--(.*?)-->", txt[:1500], re.S)
                c = cab.group(1) if cab else ""
                orig = (re.search(r"origem:\s*([^|]*)", c) or [None, ""])[1].strip()
                pasta = (re.search(r"pasta:\s*([^|]*)", c) or [None, ""])[1].strip()
                te = (re.search(r"tipo:\s*([a-z_]+)", c) or [None, None])[1]
                ext = orig.rsplit(".", 1)[-1] if "." in orig.rsplit("/", 1)[-1] else ""
                nome_orig = orig.rsplit("/", 1)[-1] if orig else caminho.rsplit("/", 1)[-1]
                md = M.derivar(nome_orig, pasta, txt[cab.end():] if cab else txt, ext, te)
                md = {k: v for k, v in md.items() if v}
                plano.append((f["id"], nome, md))
            if len(it) < 100:
                break
            page += 1

    tipos = collections.Counter(m.get("tipo_doc") for _, _, m in plano)
    print("arquivos na base: %d | com par no repo: %d | sem par: %d" % (len(vistos), len(plano), len(sem_par)))
    print("por tipo:", dict(tipos.most_common()))
    print("com data_documento: %d | com projeto: %d" % (sum(1 for _, _, m in plano if m.get("data_documento")),
                                                         sum(1 for _, _, m in plano if m.get("projeto"))))
    for n in sem_par[:8]:
        print("  sem par:", n)
    if not aplicar:
        print("\nSIMULACAO: nada foi gravado. Rode com --aplicar.")
        return 0
    ok = erro = 0
    t0 = time.time()
    for fid, nome, md in plano:
        try:
            api("/api/v1/files/%s/nidum-meta" % fid, {"nidum": md})
            ok += 1
        except Exception as e:
            erro += 1
            if erro <= 5:
                print("  erro em %s: %s" % (nome, e))
    print("\nGRAVADO: %d ok, %d erro, %.0f s" % (ok, erro, time.time() - t0))
    return 1 if erro else 0


if __name__ == "__main__":
    sys.exit(main())
