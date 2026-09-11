# -*- coding: ascii -*-
"""
Baixa o fonte PUBLICADO e diffa contra o repo. Para LER a diferenca, nao medi-la.

POR QUE ESTE SCRIPT E A SIMULACAO SAO COISAS DIFERENTES - e a distincao custou uma
volta em 11/09/2026:

    o `--dry-run` do publicador responde QUANTO difere (1.148 linhas, 1a na 1431);
    este script responde O QUE difere.

Sao perguntas distintas e a segunda e a que decide. Saber que ha 1.148 linhas
diferentes nao diz se o repositorio esta ATRAS (e publicar seria regressao) ou a
FRENTE (e publicar e o conserto). Para isso e preciso LER, e para ler e preciso
trazer o publicado para o disco.

A PERGUNTA QUE ELE EXISTE PARA RESPONDER (palavras do Davi, 11/09):
    "o schema publicado do gerador pede campos que o do repositorio nao pede? a
    nomeacao publicada gera nome diferente? Se a resposta for sim em qualquer
    uma, o repositorio esta atras e publicar e regressao - e ai o caminho e
    trazer o publicado para o repositorio primeiro, nao o contrario."

O CODIGO NAO VAI PARA A TELA, VAI PARA ARQUIVO. Fonte de pipe/tool tem valve e
pode ter chave dentro; o conferidor ja se recusa a imprimir por isso. Aqui a
saida e sempre arquivo (coberto pelo .gitignore) e o terminal so recebe CONTAGEM
e o caminho. Nao commite os arquivos gerados.

USO (dentro de interface-chatnd/):
    py _nidum_manutencao/_diff_publicado.py                       # chatnd
    py _nidum_manutencao/_diff_publicado.py gerador_de_arquivos_nidum
    py _nidum_manutencao/_diff_publicado.py --todos

TOKEN: NIDUM_TOKEN do ambiente; se nao houver, NIDUM_API_KEY do .env.local.
Nunca e impresso.
"""

import difflib
import io
import json
import os
import re
import subprocess
import sys
import urllib.request

BASE = os.environ.get("NIDUM_URL", "https://chatnd.nidumbrasil.com.br").rstrip("/")

# tipo, id, caminho no repo. Os mesmos quatro do conferidor e da trava de bump.
ALVOS = {
    "chatnd": ("funcao", os.path.join("_nidum_tools", "chatnd.py")),
    "gerador_de_arquivos_nidum": ("tool", os.path.join("_nidum_tools", "gerador_de_arquivos_nidum.py")),
    "relatorio_ambientes_nidum": ("tool", os.path.join("_nidum_tools", "relatorio_ambientes_nidum.py")),
    "sharepoint_nidum": ("tool", os.path.join("_nidum_tools", "sharepoint_nidum.py")),
}


def _token():
    t = (os.environ.get("NIDUM_TOKEN") or "").strip()
    if t:
        return t
    try:
        txt = io.open(".env.local", encoding="utf-8").read()
    except Exception:
        raise SystemExit(
            "Sem credencial. Defina NIDUM_TOKEN no ambiente, ou tenha .env.local "
            "com NIDUM_API_KEY. (O token nunca e impresso nem gravado.)")
    env = dict(re.findall(r"(?m)^([A-Z0-9_]+)=(.*)$", txt))
    if "NIDUM_API_KEY" not in env:
        raise SystemExit("NIDUM_API_KEY nao esta no .env.local.")
    return env["NIDUM_API_KEY"].strip().strip('"').strip("'")


def _pegar(caminho, tok):
    req = urllib.request.Request(BASE + caminho,
                                 headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _quem(user_id, tok, _cache={}):
    """Nome de quem consta como dono do objeto publicado. Best-effort.

    O painel GUARDA autoria (`user_id`) e data (`updated_at`) - conferido nos
    modelos: FunctionModel e ToolModel tem os tres campos. Entao "quem pos isso
    em producao" e uma pergunta RESPONDIVEL, e nao precisava ter virado
    arqueologia de diff.

    Se a consulta de usuario falhar, devolve o id cru: um id opaco ainda
    identifica; inventar "desconhecido" perderia a unica pista.
    """
    if not user_id:
        return "(sem user_id)"
    if user_id not in _cache:
        try:
            d = _pegar("/api/v1/users/" + user_id, tok)
            _cache[user_id] = (d or {}).get("name") or (d or {}).get("email") or user_id
        except Exception:
            _cache[user_id] = user_id
    return _cache[user_id]


def _data(epoch):
    if not epoch:
        return "?"
    import datetime
    try:
        return datetime.datetime.utcfromtimestamp(int(epoch)).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(epoch)


def publicado(ident, tipo, tok, _cache={}):
    """O `content` no ar, mais QUEM e QUANDO. (fonte, meta, autoria).

    Tools vem do /export - /tools/id/{id} NAO traz content.
    """
    obj = None
    if tipo == "funcao":
        obj = _pegar("/api/v1/functions/id/" + ident, tok)
    else:
        if "export" not in _cache:
            _cache["export"] = _pegar("/api/v1/tools/export", tok)
        for t in (_cache["export"] or []):
            if isinstance(t, dict) and str(t.get("id") or "").strip() == ident:
                obj = t
                break
    if not isinstance(obj, dict):
        return "", {}, {}
    autoria = {
        "quem": _quem(obj.get("user_id"), tok),
        "atualizado": _data(obj.get("updated_at")),
        "criado": _data(obj.get("created_at")),
    }
    return obj.get("content") or "", obj.get("meta") or {}, autoria


def do_repo(rel, ref="origin/main"):
    p = subprocess.run(["git", "show", "%s:%s" % (ref, rel.replace(os.sep, "/"))],
                       capture_output=True)
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else ""


def _versao(t):
    m = re.search(r"(?im)^\s*version\s*:\s*(.+)$", t or "")
    return m.group(1).strip() if m else "?"


def conferir(ident, ref):
    tipo, rel = ALVOS[ident]
    tok = _token()
    pub, meta, autoria = publicado(ident, tipo, tok)
    if not pub:
        print("%-26s NAO ESTA PUBLICADO no painel." % ident)
        return
    repo = do_repo(rel, ref)
    if not repo:
        print("%-26s nao achei %s em %s." % (ident, rel, ref))
        return

    pl = pub.replace("\r\n", "\n").splitlines()
    rl = repo.replace("\r\n", "\n").splitlines()

    # QUAL LADO TEM O QUE O OUTRO NAO TEM - a leitura que responde "quem esta
    # atras". Um numero unico de "linhas diferentes" nao separa as duas direcoes,
    # e sao elas que decidem se publicar conserta ou se publicar e regressao.
    so_no_pub = so_no_repo = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, rl, pl).get_opcodes():
        if tag in ("delete", "replace"):
            so_no_repo += i2 - i1
        if tag in ("insert", "replace"):
            so_no_pub += j2 - j1

    saida_src = "_publicado_%s.py" % ident
    saida_diff = "_diff_pub_vs_main_%s.txt" % ident
    # NAO SOBRESCREVE UM RETRATO ANTERIOR - ele e PROVA, nao rascunho.
    #
    # Em 11/09 o retrato de 05/09 que estava no disco (365.233 bytes) datou a
    # divergencia: o publicado de hoje tem 373.947, e a diferenca de 8.714 bytes
    # apareceu em producao numa janela em que NINGUEM publicou pelo repo. Isso
    # transformou "1.148 linhas para revisar" em "o que entrou depois de 05/09".
    # Um `w` em cima teria apagado a unica coisa capaz de datar a mudanca.
    if os.path.isfile(saida_src):
        anterior = "_publicado_%s.ANTERIOR.py" % ident
        os.replace(saida_src, anterior)
        print("   (retrato anterior preservado em %s)" % anterior)
    io.open(saida_src, "w", encoding="utf-8", newline="").write(pub)
    diff = list(difflib.unified_diff(rl, pl, "repo:" + ref, "publicado",
                                     lineterm="", n=3))
    io.open(saida_diff, "w", encoding="utf-8").write("\n".join(diff))

    carimbo = ""
    m = re.search(r"\[origem:[^\]]{0,120}\]", (meta or {}).get("description") or "")
    if m:
        carimbo = m.group(0)

    print("%s (%s)" % (ident, tipo))
    print("   publicado : versao %-9s %d linhas" % (_versao(pub), len(pl)))
    print("   repo (%s): versao %-9s %d linhas" % (ref.split("/")[-1], _versao(repo), len(rl)))
    print("   so no PUBLICADO: %d linha(s)   |   so no REPO: %d linha(s)"
          % (so_no_pub, so_no_repo))
    print("   carimbo de origem: %s" % (carimbo or "NENHUM (publicado antes da D63, "
                                                   "ou por fora do publicador)"))
    # QUEM E QUANDO - o painel guarda, e sem isso "o repo esta atras" nao diz de
    # quem e o trabalho que esta so em producao nem quando ele entrou.
    print("   ultima gravacao : %s  por %s"
          % (autoria.get("atualizado", "?"), autoria.get("quem", "?")))
    print("   fonte publicada -> %s" % saida_src)
    print("   diff            -> %s" % saida_diff)
    print("")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ref = "origin/main"
    for a in sys.argv[1:]:
        if a.startswith("--ref="):
            ref = a.split("=", 1)[1]
    alvos = list(ALVOS) if "--todos" in sys.argv[1:] else (args or ["chatnd"])
    for a in alvos:
        if a not in ALVOS:
            raise SystemExit("Alvo desconhecido: %s. Conheco: %s"
                             % (a, ", ".join(ALVOS)))
    print("Base: %s   (nada e escrito no painel - so leitura)" % BASE)
    print("")
    for a in alvos:
        conferir(a, ref)
    print("ATENCAO: os arquivos gerados tem o FONTE (valve, e possivelmente chave).")
    print("Estao no .gitignore. Nao commite, e apague quando terminar de ler.")


if __name__ == "__main__":
    main()
