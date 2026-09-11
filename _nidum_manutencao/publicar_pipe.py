# -*- coding: ascii -*-
"""
Publica (ou atualiza) o PIPE (function) ChatND na imagem VIVA, a partir do .py local.

Por que separado do publicar_tool.py: o pipe e uma FUNCTION (endpoint /api/v1/functions),
nao uma TOOL (/api/v1/tools). Mesma forma de payload (id, name, content, meta), rotas
diferentes. O id da function = nome do arquivo sem .py (o pipe -> "chatnd").

COMO USAR (no seu terminal, dentro de interface-chatnd/):
  1) variaveis de ambiente:
       $env:NIDUM_URL   = "https://chatnd.nidumbrasil.com.br"
       $env:NIDUM_TOKEN = "SEU_TOKEN_ADMIN"
  2) SIMULE primeiro (nao escreve nada, mostra o tamanho da mudanca):
       py _nidum_manutencao/publicar_pipe.py --dry-run
  3) publique:
       py _nidum_manutencao/publicar_pipe.py
     ou passe outro caminho:
       py _nidum_manutencao/publicar_pipe.py _nidum_tools/chatnd.py

O JEITO PREFERIDO NAO E ESTE: e o workflow "Publicar pipe/tools" no GitHub
Actions, que sobe o codigo direto do repositorio e carimba o sha sozinho. Rodar
daqui continua funcionando e continua sendo util (experimento nao commitado),
mas o publish deixa carimbo LOCAL - de proposito, para o conferidor ver.

Se a function ja existir, ATUALIZA (nao duplica). As VALVES salvas sao preservadas -
uma valve nova assume o default do codigo (ex.: DEBUG_TRECHOS nasce OFF). So-ASCII.

NOTA sobre encoding: le o arquivo como UTF-8 (robusto). O pipe deve ser ASCII por
convencao da casa, mas o transporte nao depende disso - se houver byte nao-ASCII, avisa
e publica assim mesmo (nao trava a publicacao por conta de convencao de fonte).
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

# A simulacao e o carimbo de origem moram no modulo irmao (ver o cabecalho dele).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _publicar_comum import carimbo_de_origem, descricao_com_carimbo, simular


def _argumentos(argv):
    """Separa a flag do caminho. --dry-run em qualquer posicao.

    Feito a mao em vez de argparse para nao mudar o jeito de chamar que ja esta
    escrito no topo do arquivo e na cabeca de quem usa: o caminho continua sendo
    um posicional solto.
    """
    seco = any(a in ("--dry-run", "--dry_run", "--simular") for a in argv)
    resto = [a for a in argv if not a.startswith("--")]
    return seco, resto

PADRAO = os.path.join("_nidum_tools", "chatnd.py")


def _http(method, url, token, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer %s" % token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, "%s: %s" % (type(e).__name__, e)


def _parece_html(txt):
    t = (txt or "").lstrip().lower()
    return t.startswith("<!doctype") or t.startswith("<html")


def _cabecalho(campo, texto):
    m = re.search(r"(?im)^\s*%s\s*:\s*(.+)$" % re.escape(campo), texto)
    return m.group(1).strip() if m else ""


def main():
    seco, posicionais = _argumentos(sys.argv[1:])
    code_path = posicionais[0] if posicionais else PADRAO
    if not os.path.isfile(code_path):
        print("ERRO: arquivo nao encontrado: %s" % code_path)
        print("Rode de dentro de interface-chatnd/ (ou passe o caminho do .py).")
        sys.exit(1)

    base = os.environ.get("NIDUM_URL", "").rstrip("/")
    token = os.environ.get("NIDUM_TOKEN", "").strip()
    if not base or not token:
        print("ERRO: defina NIDUM_URL e NIDUM_TOKEN. Veja o topo do arquivo.")
        sys.exit(1)

    print("Conferindo a URL: %s" % base)
    st0, body0 = _http("GET", "%s/api/config" % base, token)
    if _parece_html(body0) or st0 != 200:
        print("ERRO: essa URL nao respondeu como o ChatND (HTTP %d%s)." % (
            st0, ", pagina HTML" if _parece_html(body0) else ""))
        print('Ajuste: $env:NIDUM_URL = "https://chatnd.nidumbrasil.com.br"')
        sys.exit(1)
    print("URL confere.")

    with open(code_path, "r", encoding="utf-8") as fh:
        content = fh.read()
    nao_ascii = sum(1 for ch in content if ord(ch) > 127)
    if nao_ascii:
        print("AVISO: %d caractere(s) nao-ASCII no fonte (convencao pede ASCII); "
              "publicando assim mesmo." % nao_ascii)

    func_id = os.path.splitext(os.path.basename(code_path))[0].lower()
    name = _cabecalho("title", content) or func_id
    desc = _cabecalho("description", content)[:400] or name
    ver = _cabecalho("version", content) or "?"
    print("Publicando function id=%s versao=%s (%d bytes)..." % (func_id, ver, len(content)))

    if seco:
        sys.exit(simular(_http, base, token, "funcao", func_id, content, ver,
                         lambda t: _cabecalho("version", t)))

    # O CARIMBO VAI NA DESCRICAO, NUNCA NO CONTEUDO - o conferidor compara o
    # `content` com o do repo, e carimbar dentro dele faria todo publicado
    # divergir por causa do proprio carimbo.
    desc = descricao_com_carimbo(desc, carimbo_de_origem())
    form = {"id": func_id, "name": name, "content": content, "meta": {"description": desc}}
    st, body = _http("POST", "%s/api/v1/functions/create" % base, token, form)
    if st != 200:
        print("create HTTP %d -> tentando update..." % st)
        st, body = _http(
            "POST", "%s/api/v1/functions/id/%s/update" % (base, func_id), token, form
        )

    ok = False
    if st == 200 and not _parece_html(body):
        try:
            j = json.loads(body)
            if isinstance(j, dict) and j.get("id"):
                print("OK: id=%s name=%s" % (j.get("id"), j.get("name")))
                ok = True
        except Exception:
            pass
    if not ok:
        print("HTTP %d | resposta: %s" % (st, body[:400]))
        print("NAO publicou. Copie a mensagem e me mostre.")
        sys.exit(2)

    print("")
    print("PRONTO. Pipe publicado (versao %s). Confira em Admin -> Functions -> ChatND." % ver)
    print("Origem registrada: %s" % carimbo_de_origem())
    print("Lembrete: valve nova nasce no default do codigo (ex.: DEBUG_TRECHOS = OFF).")


if __name__ == "__main__":
    main()
