# -*- coding: ascii -*-
"""
BATERIA do orcamento por turno - chama o agente pela API, DENTRO de uma pasta,
e devolve a regua. Substitui o roteiro manual de 19/09 (16 prompts na tela).

POR QUE DENTRO DE UMA PASTA, e isto foi medido no codigo, nao suposto:
`get_builtin_tools` (utils/tools.py) monta ferramentas DIFERENTES conforme haja
ou nao conhecimento anexado. Sem pasta e sem knowledge no preset, o agente
recebe as tools de NAVEGAR bases. Com a pasta, recebe as SEIS de dentro do
escopo - e e ai que entra o `view_file`, cujo teto por chamada e 100.000 chars.
Ou seja: a cauda que este orcamento existe para cortar so aparece no caminho da
PASTA. Medir fora dela mediria outra coisa e acharia menos.

COMO OS TURNOS SAO SEPARADOS: um por vez, sequencial, e o log de cada um e
recolhido logo depois e escrito atras de um marcador `#turno <id>`. O medidor le
o marcador e nao precisa da heuristica da "queda do acumulado" - que erra quando
duas pessoas conversam ao mesmo tempo. Cada linha entra uma vez so (dedup por
timestamp + texto), entao refazer a coleta nao duplica turno.

CADA TURNO E UMA CHAMADA PAGA. Por isso a bateria e um SUBCONJUNTO declarado
(bateria_orcamento_prompts.json) e nao os 16 prompts: a mediana precisa de
turnos que ficam abaixo do teto, a cauda precisa de turnos que estouram por
caminhos diferentes, e mais turnos do que isso compram precisao que a decisao
nao usa.

  py -3 bateria_orcamento.py --fase seco   --saida antes.log
  py -3 bateria_orcamento.py --fase ligado --saida depois.log --blocos c,a
  py -3 bateria_orcamento.py --regua antes.log depois.log      (so le, nao chama)

O `--fase` NAO configura nada - ele so CONFERE o que o log disser e serve de
rotulo. Ligar o corte e mexer em `AGENTE_ORCAMENTO_ATIVO` no Railway, que e
passo de operacao, de proposito (ver nidum_orcamento.py).
"""

import argparse
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(_AQUI)

URL = os.environ.get("NIDUM_URL", "https://chatnd.nidumbrasil.com.br")
MODELO = os.environ.get("BATERIA_MODELO", "chatnd-agente-beta")
SERVICO = os.environ.get("RAILWAY_SERVICO", "ChatND")
PASTA_NOME = "TEC_MedicaoOrcamento"

# As colecoes REAIS que uma pasta de projeto carrega. Ids conferidos na
# instancia em 21/09/2026; nome ao lado para quem for ler depois.
COLECOES = [
    ("accc1ac9-1cb3-42c6-b7ea-b9e92753ecc4", "Projetos"),
    ("e59de55f-4dd0-49ed-bc63-1727505009f2", "Gestao de Projetos"),
    ("0676a412-ff3d-488e-a576-e56afc621b31", "Operacoes"),
    ("03e63260-3a5f-49f0-9e22-85dd68bbec11", "Fonte"),
]

_spec = importlib.util.spec_from_file_location(
    "medir_orcamento", os.path.join(_AQUI, "medir_orcamento.py"))
_MED = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_MED)


# ---------------------------------------------------------------- credencial

def token():
    """Le o NIDUM_API_KEY do .env.local - o mesmo caminho do publicar_pipe."""
    if os.environ.get("NIDUM_TOKEN"):
        return os.environ["NIDUM_TOKEN"].strip()
    caminho = os.path.join(_RAIZ, ".env.local")
    with io.open(caminho, encoding="utf-8") as fh:
        for linha in fh:
            if linha.strip().startswith("NIDUM_API_KEY="):
                return linha.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("sem NIDUM_API_KEY em %s" % caminho)


def api(caminho, dados=None, metodo=None, timeout=1200):
    corpo = None if dados is None else json.dumps(dados).encode("utf-8")
    req = urllib.request.Request(
        URL.rstrip("/") + caminho, data=corpo,
        method=metodo or ("POST" if corpo else "GET"),
        headers={"Authorization": "Bearer " + token(),
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------- a pasta

def pasta_da_medicao(criar=True):
    """Devolve o id da pasta de medicao, criando-a se preciso.

    A pasta e do USUARIO DA CHAVE: `get_folder_by_id_and_user_id` exige dono, e
    por isso nao se pode medir dentro da pasta de outra pessoa. O que importa
    para a medicao e o CONTEUDO - as colecoes sao as de producao, as mesmas que
    uma pasta de projeto carrega.
    """
    for f in api("/api/v1/folders/"):
        if f.get("name") == PASTA_NOME:
            return f["id"]
    if not criar:
        raise SystemExit("pasta '%s' nao existe (use --criar-pasta)" % PASTA_NOME)
    novo = api("/api/v1/folders/", {
        "name": PASTA_NOME,
        "data": {
            "system_prompt": (
                "Voce apoia a equipe da Nidum neste projeto. Consulte o material "
                "do projeto antes de responder e cite o que encontrou."),
            "files": [{"type": "collection", "id": cid, "name": nome}
                      for cid, nome in COLECOES],
        },
    })
    print("pasta criada: %s (%s) com %d colecoes"
          % (novo["id"], PASTA_NOME, len(COLECOES)))
    return novo["id"]


# ---------------------------------------------------------------- o log

def linhas_do_log(n=800):
    """Le do Railway SO as linhas do orcamento. Cai para o log cru se o filtro
    nao devolver nada - filtro que muda de sintaxe nao pode calar a medicao."""
    # DOIS DEFEITOS DE WINDOWS, medidos em 21/09/2026, e o segundo e silencioso:
    #
    #  1. o CLI instalado por npm e "railway.CMD" - subprocess.run(["railway",...])
    #     levanta WinError 2 ("arquivo nao encontrado"). Resolve-se com shutil.which.
    #  2. `railway logs` le o projeto LINKADO DO DIRETORIO ATUAL. O link mora em
    #     interface-chatnd/, e esta bateria roda de _nidum_manutencao/ - de la o CLI
    #     devolve rc=1 e "No linked project found" no STDERR, com stdout VAZIO.
    #
    # O modo de falha do (2) era o perigoso: stdout vazio vira "0 linhas de
    # orcamento", que se le como "nenhum turno estourou" - a conclusao oposta da
    # verdadeira. Por isso o stderr agora APARECE: saida vazia sem explicacao foi
    # o que fez a primeira sonda mentir.
    exe = shutil.which("railway") or shutil.which("railway.cmd") or "railway"
    base = [exe, "logs", "--service", SERVICO, "--lines", str(n)]
    def _roda(args):
        o = subprocess.run(args, capture_output=True, text=True, timeout=180,
                           cwd=_RAIZ)   # <- o diretorio LINKADO, nao o da bateria
        if o.returncode != 0 and o.stderr:
            print("  (railway rc=%s: %s)" % (o.returncode, o.stderr.strip()[:160]))
        return o.stdout
    try:
        saida = _roda(base + ["--filter", "nidum_orcamento"])
    except Exception as e:
        print("  (railway logs falhou: %s)" % e)
        saida = ""
    linhas = [l for l in saida.splitlines() if "nidum_orcamento" in l]
    if not linhas:
        try:
            saida = _roda(base)
        except Exception as e:
            print("  (railway logs cru falhou: %s)" % e)
            return []
        linhas = [l for l in saida.splitlines() if "nidum_orcamento" in l]
    return linhas


# ---------------------------------------------------------------- os turnos

def um_turno(p, folder_id):
    """Roda UM prompt e devolve (texto, segundos). Turno = requisicao.

    STREAM=TRUE, E NAO E PREFERENCIA - E A UNICA FORMA DE HAVER O QUE MEDIR.
    Medido no codigo em 21/09/2026:

        non_streaming_chat_response_handler (middleware.py:3482-3628)
            -> ZERO ocorrencias de "tool". Nao executa ferramenta.
        streaming_chat_response_handler     (middleware.py:3629-5330)
            -> 128 ocorrencias. O laco agentico vive aqui.

    Com `stream: false` o modelo ate EMITE a intencao ("Vou consultar as bases
    de conhecimento...") e a resposta termina ali: ninguem executa a chamada.
    Seis turnos assim devolveram 0 linhas de orcamento - que se le como "nenhum
    turno estoura", quando o certo era "nenhuma ferramenta rodou". Mesmo modo de
    falha do railway sem link: saida limpa, fenomeno ausente, conclusao invertida.
    """
    t0 = time.time()
    corpo = json.dumps({
        "model": MODELO,
        "messages": [{"role": "user", "content": p["texto"]}],
        "stream": True,
        "folder_id": folder_id,
        # Sem 'native' nao ha laco de ferramenta - e sem laco nao ha o que orcar.
        "params": {"function_calling": "native"},
    }).encode("utf-8")
    req = urllib.request.Request(
        URL.rstrip("/") + "/api/chat/completions", data=corpo, method="POST",
        headers={"Authorization": "Bearer " + token(),
                 "Content-Type": "application/json",
                 "Accept": "text/event-stream"})
    partes, ferramentas = [], 0
    with urllib.request.urlopen(req, timeout=1800) as resp:
        for bruta in resp:
            linha = bruta.decode("utf-8", "replace").strip()
            if not linha.startswith("data:"):
                continue
            dado = linha[5:].strip()
            if dado == "[DONE]":
                break
            try:
                ev = json.loads(dado)
            except Exception:
                continue
            for ch in (ev.get("choices") or []):
                d = ch.get("delta") or {}
                if d.get("content"):
                    partes.append(d["content"])
                if d.get("tool_calls"):
                    ferramentas += len(d["tool_calls"])
    return "".join(partes), time.time() - t0, ferramentas


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--fase", choices=["seco", "ligado"], default="seco")
    ap.add_argument("--saida", default=None)
    ap.add_argument("--blocos", default="controle,medio,cauda")
    ap.add_argument("--so", default=None, help="ids separados por virgula (ex.: c1,c2)")
    ap.add_argument("--pasta", default=None)
    ap.add_argument("--criar-pasta", action="store_true")
    ap.add_argument("--regua", nargs="*", default=None)
    args = ap.parse_args()

    if args.regua is not None:
        if not args.regua:
            raise SystemExit("--regua precisa de 1 ou 2 arquivos de log")
        return _regua(args.regua)

    with io.open(os.path.join(_AQUI, "bateria_orcamento_prompts.json"),
                 encoding="utf-8") as fh:
        prompts = json.load(fh)["prompts"]
    blocos = [b.strip() for b in args.blocos.split(",") if b.strip()]
    if args.so:
        ids = [i.strip() for i in args.so.split(",")]
        prompts = [p for p in prompts if p["id"] in ids]
    else:
        prompts = [p for p in prompts if p["bloco"] in blocos]
    if not prompts:
        raise SystemExit("nenhum prompt selecionado")

    saida = args.saida or ("%s.log" % args.fase)
    folder_id = args.pasta or pasta_da_medicao(criar=True)
    # As respostas ficam AO LADO do log, e nao no repositorio: sao artefato de
    # medicao, e o `--saida` e que diz onde a medicao mora.
    dir_resp = os.path.join(os.path.dirname(os.path.abspath(saida)), "respostas")
    if not os.path.isdir(dir_resp):
        os.makedirs(dir_resp)

    print("bateria_orcamento: fase=%s modelo=%s pasta=%s" % (args.fase, MODELO, folder_id))
    print("turnos: %s" % ", ".join(p["id"] for p in prompts))
    print("")

    # O que JA estava no log antes de comecar nao e desta bateria.
    vistas = set(linhas_do_log())
    print("linhas de orcamento ja no log antes de comecar: %d" % len(vistas))

    with io.open(saida, "w", encoding="utf-8") as fh:
        fh.write("# bateria_orcamento fase=%s modelo=%s pasta=%s em %s\n"
                 % (args.fase, MODELO, folder_id,
                    time.strftime("%Y-%m-%d %H:%M:%S")))

    for p in prompts:
        print("[%s/%s] %s" % (p["id"], p["bloco"], p["texto"][:70]))
        try:
            texto, seg, ferr = um_turno(p, folder_id)
        except Exception as e:
            print("  ERRO na chamada: %s" % e)
            texto, seg, ferr = "ERRO: %s" % e, 0, 0
        print("  %.1fs, resposta com %d chars, %d tool call(s)%s"
              % (seg, len(texto), ferr,
                 "   <- SEM FERRAMENTA: nao ha o que orcar" if not ferr else ""))
        with io.open(os.path.join(dir_resp, "%s_%s.md" % (args.fase, p["id"])),
                     "w", encoding="utf-8") as fh:
            fh.write("# %s (%s) - fase %s\n\n%s\n\n---\n\n%s\n"
                     % (p["id"], p["bloco"], args.fase, p["texto"], texto))

        # O log demora a aparecer no Railway; duas tentativas curtas bastam.
        novas = []
        for _ in range(6):
            time.sleep(5)
            novas = [l for l in linhas_do_log() if l not in vistas]
            if novas:
                break
        vistas.update(novas)
        with io.open(saida, "a", encoding="utf-8") as fh:
            fh.write("#turno %s-%s\n" % (p["id"], p["bloco"]))
            for l in novas:
                fh.write(l + "\n")
        print("  linhas de orcamento deste turno: %d%s"
              % (len(novas), "" if novas else "   <- NENHUMA (sem tool call?)"))
        print("")

    print("=" * 70)
    return _regua([saida])


def _regua(caminhos):
    sys.argv = [sys.argv[0]] + list(caminhos)
    return _MED.main()


if __name__ == "__main__":
    sys.exit(main())
