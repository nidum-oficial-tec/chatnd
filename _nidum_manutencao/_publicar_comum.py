# -*- coding: ascii -*-
"""
O que `publicar_pipe.py` e `publicar_tool.py` passaram a compartilhar: a
SIMULACAO (--dry-run) e o CARIMBO DE ORIGEM.

POR QUE ESTE ARQUIVO EXISTE (11/09/2026): o publish daqui e por API e MANUAL -
mergear na main nao publica. O conferidor achou `chatnd` 1.65.0 no painel e
1.65.0 no repo com 1.148 linhas realmente diferentes, e o conteudo publicado nao
correspondia a NENHUM commit que ja existiu. Ou seja: o que roda nao era
rastreavel ao repositorio.

Duas coisas consertam isso, e as duas moram aqui:

  1. SIMULAR ANTES. Ate hoje os dois publicadores so tinham um modo: publicar.
     Quem rodava o comando descobria o tamanho da mudanca DEPOIS, em producao.
  2. CARIMBAR A ORIGEM. Todo publish deixa dito de onde veio - sha do commit
     quando sai do Actions, e "LOCAL" quando sai da maquina de alguem.

ONDE O CARIMBO VAI, e por que nao vai no lugar obvio: vai no `meta.description`,
e NAO no `content`. O conferidor compara o `content` publicado com o do repo; se
o publish carimbasse dentro do codigo, TODO arquivo publicado divergiria do repo
por causa do proprio carimbo, e o conferidor passaria a acusar sempre. O
`meta.description` e o unico campo gravavel que fica FORA da coisa comparada.
Preco: a descricao no painel Admin ganha um sufixo tecnico. E admin-only, e vale.

A REGRA DE COMPARACAO NAO E REDEFINIDA AQUI. `normalizar_fonte` e
`tamanho_da_diferenca` sao IMPORTADAS do conferir_registros.py - se a simulacao e
o conferidor discordassem sobre o que e "diferente", um dos dois estaria mentindo,
e nao daria para saber qual. O import e TARDIO (dentro da funcao) de proposito: o
caminho que PUBLICA nao carrega o conferidor, entao um defeito la nao derruba a
publicacao. Se o import falhar, a simulacao diz que NAO CONSEGUIU OLHAR - nunca
"esta igual".
"""

import datetime
import json
import os
import sys


def carimbo_de_origem():
    """De onde veio este publish. String curta, para o `meta.description`.

    No Actions sai o sha - de graca, e sem depender de ninguem lembrar de anotar.
    Na maquina de alguem sai LOCAL, dito com todas as letras: um publish local
    nao tem como provar de que codigo saiu, e o carimbo que omite isso seria pior
    que carimbo nenhum (dois publishes indistinguiveis, um rastreavel e outro
    nao).
    """
    sha = (os.environ.get("GITHUB_SHA") or "").strip()
    if sha:
        return "[origem: repo %s ref %s run %s]" % (
            sha[:12],
            os.environ.get("GITHUB_REF_NAME") or "?",
            os.environ.get("GITHUB_RUN_ID") or "?")
    hoje = datetime.date.today().isoformat()
    return "[origem: LOCAL em %s - sem sha, nao rastreavel ao repo]" % hoje


def descricao_com_carimbo(desc, carimbo, limite=400):
    """Encaixa os dois dentro do limite, cortando a DESCRICAO e nunca o carimbo.

    A descricao cortada continua servindo (e um resumo); um carimbo cortado vira
    um sha pela metade, que parece um sha e nao e - e conteudo que parece
    conteudo e o defeito que este projeto ja pagou.
    """
    carimbo = (carimbo or "").strip()
    desc = (desc or "").strip()
    if not carimbo:
        return desc[:limite]
    sobra = limite - len(carimbo) - 1
    if sobra <= 0:
        return carimbo[:limite]
    return (desc[:sobra] + " " + carimbo).strip()


def publicado_atual(http, base, token, tipo, ident):
    """O `content` que esta NO AR. (fonte, motivo).

    fonte=None significa NAO CONSEGUI OLHAR - nunca "igual". fonte="" significa
    que a coisa ainda nao existe no painel (publish novo, e nao divergencia).

    O ENDPOINT DAS TOOLS NAO E O QUE PARECE - a mesma armadilha documentada no
    conferidor:
        funcoes: GET /api/v1/functions/id/{id} -> TEM `content`
        tools:   GET /api/v1/tools/id/{id}     -> NAO TEM
                 GET /api/v1/tools/export      -> TEM
    """
    if tipo == "funcao":
        st, corpo = http("GET", "%s/api/v1/functions/id/%s" % (base, ident), token)
        if st == 404:
            return "", None
        if st != 200:
            return None, "HTTP %d em /api/v1/functions/id/%s" % (st, ident)
        try:
            d = json.loads(corpo)
        except Exception:
            return None, "/api/v1/functions/id/%s nao devolveu JSON" % ident
        if not isinstance(d, dict):
            return None, "/api/v1/functions/id/%s nao devolveu objeto" % ident
        if not d.get("content"):
            return None, "a funcao %r existe no painel mas veio sem `content`" % ident
        return d["content"], None

    st, corpo = http("GET", "%s/api/v1/tools/export" % base, token)
    if st != 200:
        return None, "HTTP %d em /api/v1/tools/export" % st
    try:
        d = json.loads(corpo)
    except Exception:
        return None, "/api/v1/tools/export nao devolveu JSON"
    if not isinstance(d, list):
        return None, "/api/v1/tools/export nao devolveu lista (veio %s)" % type(d).__name__
    for t in d:
        if isinstance(t, dict) and str(t.get("id") or "").strip() == ident:
            if not t.get("content"):
                return None, "a tool %r esta no export mas veio sem `content`" % ident
            return t["content"], None
    return "", None


def _comparar(publicado, local):
    """(identico, linhas_diferentes, primeira_linha) ou None se nao deu para medir.

    Import TARDIO do conferidor - ver o cabecalho. Se ele nao carregar, devolve
    None, e quem chama e obrigado a dizer "nao consegui olhar".
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from conferir_registros import _normalizar_fonte, _tamanho_da_diferenca
    except Exception:
        return None
    a, b = _normalizar_fonte(publicado), _normalizar_fonte(local)
    if a == b:
        return (True, 0, None)
    dif, primeira = _tamanho_da_diferenca(a, b)
    return (False, dif, primeira)


def simular(http, base, token, tipo, ident, conteudo_local, versao_local, versao_de):
    """Imprime o que ACONTECERIA. Devolve o codigo de saida do processo.

    0 = simulou e da para publicar (ou nao ha o que mudar). 4 = simulou mas NAO
    consegui olhar o publicado - e um resultado proprio, e nao um sucesso: quem
    le precisa saber que a comparacao nao aconteceu, em vez de receber silencio e
    entender "esta tudo bem".
    """
    print("")
    print("=== SIMULACAO (--dry-run): NADA sera escrito no painel ===")
    fonte, motivo = publicado_atual(http, base, token, tipo, ident)

    if fonte is None:
        print("NAO CONSEGUI OLHAR o que esta publicado: %s" % motivo)
        print("Sem isso nao da para dizer o tamanho da mudanca. NAO e 'esta igual'.")
        return 4

    if fonte == "":
        print("%s %r ainda NAO existe no painel - este publish CRIA." % (tipo, ident))
        print("Local: versao %s, %d bytes." % (versao_local or "?", len(conteudo_local)))
        return 0

    v_painel = versao_de(fonte)
    medida = _comparar(fonte, conteudo_local)
    print("painel: versao %s (%d bytes)" % (v_painel or "?", len(fonte)))
    print("local : versao %s (%d bytes)" % (versao_local or "?", len(conteudo_local)))

    if medida is None:
        print("NAO CONSEGUI MEDIR a diferenca (o conferidor nao carregou).")
        print("O publish real funcionaria; a simulacao e que ficou cega.")
        return 4

    identico, dif, primeira = medida
    if identico:
        print("")
        print("IDENTICO. Publicar nao mudaria nada.")
        return 0

    print("")
    print("VAI MUDAR: %d linha(s) realmente diferentes (1a divergencia na linha %s)."
          % (dif, primeira if primeira is not None else "?"))
    if v_painel and versao_local and v_painel == versao_local:
        # NAO BLOQUEIA - AVISA. O primeiro publish depois de 11/09 cai
        # exatamente aqui (1.65.0 x 1.65.0 com 1.148 linhas): uma trava neste
        # ponto impediria justamente a rodada que vem consertar o problema.
        # Travar o bump e trabalho do PR (a trava A), onde o conserto e barato.
        print("")
        print("ATENCAO: o painel e o local dizem a MESMA versao (%s) e o conteudo"
              % v_painel)
        print("DIFERE. Foi assim que a divergencia de 11/09 ficou invisivel - o")
        print("numero afirmava que eram iguais. Confira se o version devia subir.")
    print("")
    print("ESTE PUBLISH SUBSTITUI o conteudo do painel pelo do repo. Se houver em")
    print("producao algo que nao esta no repositorio, ele se perde. Leia a")
    print("diferenca antes de rodar sem --dry-run.")
    return 0
