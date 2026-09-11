# -*- coding: ascii -*-
"""
Confere se a DOCUMENTACAO e as FIXTURES descrevem o que o codigo e o repo tem.

SO-LEITURA. Nao altera nada, nao chama a API, nao precisa de credencial.

POR QUE EXISTE
==============
Em 03/09/2026 achamos QUATORZE registros descrevendo coisas revogadas ou
apagadas - valves que nao existem, ids de colecao apagada, um wrapper revogado,
e fixtures de teste usando caminhos que a reformulacao das pastas renomeou. Os
dois ultimos apareceram POR ACASO, no meio de outra tarefa.

A origem e comum e esta no D24: configuracao mora no BANCO, e renomear uma pasta
ou revogar um modelo nao deixa rastro em commit. A REGRA DA DOC resolve a
defasagem codigo -> doc, porque ali existe um PR que forca a conferencia. Nao ha
nada equivalente para painel -> doc nem para repo -> fixture.

E o custo nao e teorico: o mapa de assuntos ficou com 9 de 19 caminhos mortos
por semanas, com o DIAL_FASE3 ligado, e a etiqueta de assunto valendo zero. A
suite ficava VERDE porque as fixtures descreviam o mundo antigo.

O QUE ELE CONFERE (cinco classes, cada uma de um caso real)
==========================================================
  valve_fantasma        doc descreve valve que nao existe no codigo
  valve_nao_documentada valve existe no codigo e falta na doc
  default_divergente    doc e codigo discordam do valor default
  id_fantasma           doc cita id de colecao que nao esta no sync_config
  fixture_vencida       fixture usa caminho de pasta que nao existe no repo

O QUE ELE NAO CONFERE
=====================
Estado de PAINEL (valve efetiva, modelo ativo, colecao existente) exige
credencial e fica fora de proposito: este roda em CI, sem segredo. A parte de
painel e o `diagnostico_modelos.py`, que ja existe e pede NIDUM_URL/NIDUM_TOKEN.

USO
===
  py _nidum_manutencao/conferir_registros.py
  py _nidum_manutencao/conferir_registros.py --esteira ../esteira-conhecimento

Sai 1 quando ha achados - serve de portao em CI.
"""

import argparse
import io
import json
import os
import re
import sys
import unicodedata

_AQUI = os.path.dirname(os.path.abspath(__file__))
_PLATAFORMA = os.path.dirname(_AQUI)
_ESTEIRA_PADRAO = os.path.join(os.path.dirname(_PLATAFORMA), "esteira-conhecimento")

# Valves que a doc descreve de proposito sem existirem como Field (secoes de
# ambiente, nao de valve). Vazio hoje - existe para o dia em que houver excecao
# legitima, e para que a excecao seja ESCRITA em vez de silenciosa.
_VALVE_IGNORAR = set()


def _fold(s):
    s = unicodedata.normalize("NFD", str(s or "").strip())
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _ler(caminho):
    try:
        return io.open(caminho, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def _arquivos(raiz, sufixo, dentro=None):
    saida = []
    if not os.path.isdir(raiz):
        return saida
    for base, dirs, arqs in os.walk(raiz):
        dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]
        if dentro and dentro not in base.replace(os.sep, "/"):
            continue
        for a in arqs:
            if a.endswith(sufixo):
                saida.append(os.path.join(base, a))
    return saida


def _achado(classe, detalhe, onde, consequencia):
    return {"classe": classe, "detalhe": detalhe, "onde": onde,
            "consequencia": consequencia}


# ---------------------------------------------------------------------------
# Extracao
# ---------------------------------------------------------------------------
_RE_VALVE_CODIGO = re.compile(
    r"^\s{4,}([A-Z][A-Z0-9_]{2,}):\s*[\w\[\], |]+\s*=\s*Field\(\s*default\s*=\s*([^,)]+)",
    re.M)
# Linha de tabela de doc: | `NOME` | descricao | `default` | producao |
_RE_VALVE_DOC = re.compile(
    r"^\|\s*`([A-Z][A-Z0-9_]{2,})`\s*\|[^|]*\|\s*([^|]*?)\s*\|", re.M)
_RE_UUID8 = re.compile(r"\b([0-9a-f]{8})(?:[0-9a-f-]{0,28})\b")
_RE_CAMINHO_FIXTURE = re.compile(r'"([A-Za-zA-y][^"\n]*?/[^"\n]*?\.md)"')


def _valves_do_codigo(raiz):
    achadas = {}
    for arq in _arquivos(os.path.join(raiz, "_nidum_tools"), ".py"):
        if os.path.basename(arq).startswith("teste_"):
            continue
        for nome, bruto in _RE_VALVE_CODIGO.findall(_ler(arq)):
            achadas.setdefault(nome, _limpar_default(bruto))
    return achadas


def _limpar_default(bruto):
    v = (bruto or "").strip().strip('"').strip("'").strip()
    return v


def _valves_da_doc(raiz):
    achadas = {}
    for arq in _arquivos(os.path.join(raiz, "_nidum_docs"), ".md"):
        if "04_" not in os.path.basename(arq) and "Dicionario" not in arq:
            continue
        for nome, default in _RE_VALVE_DOC.findall(_ler(arq)):
            achadas.setdefault(nome, (_limpar_default(default.strip("`")), arq))
    return achadas


def _ids_do_config(esteira):
    ids = set()
    caminho = os.path.join(esteira, "_scripts", "sync_config.json")
    try:
        cfg = json.loads(_ler(caminho))
    except Exception:
        return ids
    def _colher(d):
        if isinstance(d, dict):
            for k, v in d.items():
                if k == "id" and isinstance(v, str):
                    ids.add(v.strip().lower()[:8])
                else:
                    _colher(v)
        elif isinstance(d, list):
            for x in d:
                _colher(x)
    _colher(cfg)
    return ids


def _pastas_do_repo(esteira):
    pastas = set()
    if not os.path.isdir(esteira):
        return pastas
    for base, dirs, _a in os.walk(esteira):
        dirs[:] = [d for d in dirs if not d.startswith((".", "_"))]
        rel = os.path.relpath(base, esteira).replace(os.sep, "/")
        if rel != ".":
            pastas.add(_fold(rel))
    return pastas


# ---------------------------------------------------------------------------
# Conferencia
# ---------------------------------------------------------------------------
FRAC_CATASTROFE_DESENHO = 0.25


def conferir_frac_catastrofe(valor):
    """O freio proporcional voltou ao valor de desenho?

    Nasce do plano de migracao do eixo: a rodada B sobe FRAC_CATASTROFE para 0,35
    porque 34 remocoes em 109 arquivos (31,2%) disparam CATASTROFE, que bloqueia
    ate confirmada. Subir e legitimo; ESQUECER DE VOLTAR nao da erro nenhum - o
    freio simplesmente deixa de proteger, e quem descobre e a proxima remocao em
    massa que passa batido.

    Acusa nos DOIS sentidos. Valor mais apertado que o desenho tambem e
    divergencia: ele bloqueia rodadas legitimas, e a reacao previsivel de quem
    apanha de um freio apertado demais e afrouxa-lo sem medir.

    Ausente nao acusa: sem variavel, vale o padrao do codigo, que ja e 0,25.
    """
    if valor is None or str(valor).strip() == "":
        return []
    try:
        atual = float(str(valor).strip().replace(",", "."))
    except (TypeError, ValueError):
        return [_achado(
            "frac_catastrofe",
            "FRAC_CATASTROFE ilegivel: %r" % valor,
            "variavel de repositorio da esteira",
            "valor que nao e numero faz o freio cair no padrao sem ninguem saber "
            "qual protecao esta valendo.")]
    if abs(atual - FRAC_CATASTROFE_DESENHO) < 1e-9:
        return []
    return [_achado(
        "frac_catastrofe",
        "FRAC_CATASTROFE = %s (o desenho e %s)" % (atual, FRAC_CATASTROFE_DESENHO),
        "variavel de repositorio da esteira",
        "acima do desenho, o freio de catastrofe deixa passar remocao em massa que "
        "deveria barrar; abaixo, bloqueia rodada legitima e ensina a afrouxa-lo. "
        "Se foi a migracao que subiu, o passo 8 do plano manda restaurar.")]


def conferir_bases_vazias(contagens, devem_ficar_vazias):
    """Existe base para uma pasta-mae DECLARADA como excluida, e com conteudo?

    O DEFEITO QUE ESTA FUNCAO JA TEVE, e que e a licao mais cara do conferidor:
    a primeira versao procurava os nomes das pastas excluidas dentro das contagens
    das colecoes CONFIGURADAS. Pasta excluida nao tem colecao configurada - por
    construcao. A intersecao era sempre vazia, a comparacao era sempre zero contra
    zero, e o resultado era VERDE PERMANENTE SEM COBERTURA NENHUMA.

    Nao havia como notar lendo: o codigo esta certo, o teste passa (com fixtures
    que colocam o nome nos dois lados), e o relatorio diz "nada encontrado". So
    rodar contra dado real DESCONFIANDO DO VERDE pega - foi assim que apareceu.

    Agora as contagens trazem TODAS as colecoes do painel, inclusive as criadas
    fora do config, que sao exatamente o caso que a classe deveria pegar. A
    comparacao e por nome normalizado, para uma base "Financas" e outra
    "Finan\u00e7as" nao escaparem por acento.
    """
    achados = []
    por_nome = {_fold(k).lower(): (k, v) for k, v in (contagens or {}).items()}
    for pasta in devem_ficar_vazias:
        chave = _fold(pasta).lower()
        if chave not in por_nome:
            continue                       # nao existe base para ela: o esperado
        nome_real, n = por_nome[chave]
        if not n:
            continue                       # existe e esta vazia: aceitavel
        achados.append(_achado(
            "base_indevida",
            "base %r tem %d arquivo(s) e a pasta-mae dela esta DECLARADA como "
            "excluida" % (nome_real, n),
            "painel do ChatND",
            "arquivo ali e recuperavel por qualquer usuario numa busca, sem que "
            "nada acuse - e a declaracao de exclusao passa a ser mentira"))
    return achados


def conferir_colecoes_fora_do_config(contagens, ids_por_nome, ids_declarados,
                                     excluidas):
    """Colecao existe no painel e NAO esta declarada em lugar nenhum?

    A COMPARACAO E POR ID, e a primeira versao errou isso. Ela casava o NOME do
    painel com a CHAVE do sync_config, e as duas divergem de proposito: a chave
    e a pasta-mae do SharePoint ("1 - Fonte", "3 - Reunioes") e o nome e o rotulo
    da base ("Fonte", "Reunioes"). Resultado medido em 10/09: acusou 'Fonte' (85
    arquivos) e 'Reunioes' (78) como fora do config - as duas MAIORES bases da
    casa, as duas mantidas pela esteira todo dia.

    E o campo 'nome' do config nao salvaria: ele carrega anotacao editorial
    ("Fonte (reaproveitada: era nd-fonte; os 83 sao os mesmos)"), que nunca vai
    bater com o rotulo do painel.

    Falso positivo aqui e pior que em outras classes. Esta e a classe que existe
    para ser lida quando alguem pergunta "sobrou alguma base velha?" - se ela
    acusa as duas maiores toda semana, aprende-se a pular a secao, e no dia em
    que uma base velha de verdade aparecer ninguem vai estar olhando. Id nao
    tem sinonimo: ou a esteira mantem aquela base, ou nao mantem.

    O BURACO QUE ESTA CLASSE FECHA, medido em 10/09/2026: a colecao 'Projetos'
    (a antiga nd-projetos, 17 arquivos) sobreviveu ao passo 9 da migracao e
    continuou VIVA no painel - acessivel ao agente, aparecendo na listagem de
    bases, competindo na busca.

    E NENHUM RELATORIO A VIA. O de orfaos compara o sync_config com o repo, e ela
    nao esta no config; a classe base_indevida compara as pastas-mae DECLARADAS
    como excluidas, e ela nao e uma delas. Ficava exatamente no vao entre os dois:
    invisivel para quem confere e visivel para quem pergunta.

    E o D37 numa forma nova: nao e comparacao que da zero contra zero, e
    comparacao que NUNCA ACONTECE. Um objeto que nao esta em nenhuma das duas
    listas nao e conferido por nenhuma das duas conferencias.

    Colecao VAZIA fora do config nao acusa: e o estado de quem foi esvaziada e
    espera exclusao manual, que e passo legitimo da migracao.
    """
    mantidos = {str(x).strip() for x in (ids_declarados or []) if x}
    # As pastas-mae DECLARADAS como excluidas continuam casando por NOME: elas nao
    # tem id no config (nao ha base declarada para elas), e uma base com esse nome
    # e assunto de conferir_bases_vazias, nao desta classe.
    por_nome = {_fold(x).lower() for x in (excluidas or [])}
    achados = []
    for nome, n in sorted((contagens or {}).items()):
        if str((ids_por_nome or {}).get(nome) or "").strip() in mantidos:
            continue
        if _fold(nome).lower() in por_nome:
            continue
        if not n:
            continue
        achados.append(_achado(
            "colecao_fora_do_config",
            "a colecao %r existe no painel com %d arquivo(s) e nao esta no "
            "sync_config nem entre as pastas-mae excluidas" % (nome, n),
            "painel x sync_config",
            "a esteira nao a mantem e nenhum relatorio a confere, mas o agente a "
            "ve e busca nela - o conteudo dela envelhece sem que nada acuse"))
    return achados

# ---------------------------------------------------------------------------
# PUBLICADO x REPOSITORIO  (desenho em _nidum_docs/14_Conferencia_do_Publicado.md)
# ---------------------------------------------------------------------------
# O pipe e as tools vao para producao POR API, MANUALMENTE. Mergear na main NAO
# publica. Logo o que esta no ar pode ser qualquer versao - e ate hoje NADA
# comparava o painel com o repositorio.
#
# A varredura de cobertura (doc 11) apontou isto como a maior lacuna: o coracao
# do produto era o unico objeto que ninguem conferia. E a Fase E torna a lacuna
# critica em vez de apenas indesejavel - durante o corte vao coexistir DUAS
# implementacoes do mesmo produto.
#
# NAO BLOQUEIA. Divergencia entre painel e repo e estado NORMAL entre o merge e
# o publish. O que nao e normal e ela durar sem ninguem saber.

_PUBLICADOS = (
    # (tipo, id no painel, caminho no repo)
    ("funcao", "chatnd", os.path.join("_nidum_tools", "chatnd.py")),
    ("tool", "gerador_de_arquivos_nidum",
     os.path.join("_nidum_tools", "gerador_de_arquivos_nidum.py")),
    ("tool", "relatorio_ambientes_nidum",
     os.path.join("_nidum_tools", "relatorio_ambientes_nidum.py")),
    ("tool", "sharepoint_nidum",
     os.path.join("_nidum_tools", "sharepoint_nidum.py")),
)

_RE_VERSAO = re.compile(r"^\s*version:\s*([0-9]+(?:\.[0-9]+)*)", re.M)


def _normalizar_fonte(texto):
    """Normaliza o SUFICIENTE, e nao mais que isso.

    NORMALIZA: \r\n -> \n, espaco a direita de cada linha, linhas vazias no fim.
    NAO NORMALIZA: indentacao, ordem, comentarios, espacos internos.

    A fronteira nao e arbitraria. Comparar bytes crus produziria divergencia
    falsa toda vez (fim de linha, espaco sobrando) e o alarme viraria ruido fixo
    - que e como um alarme morre (D53). Normalizar demais esconderia mudanca
    real: em Python a indentacao E semantica, e comentario divergente e
    justamente o que denuncia um hotfix feito direto no painel.
    """
    t = (texto or "").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(l.rstrip() for l in t.split("\n")).rstrip("\n")


def _versao_de(fonte):
    m = _RE_VERSAO.search(fonte or "")
    return m.group(1) if m else ""


def _publicado_do_painel(tipo, ident, _cache={}):
    """(fonte, motivo). fonte=None significa NAO CONSEGUI OLHAR - nunca 'igual'.

    O ENDPOINT DAS TOOLS NAO E O QUE PARECE, e este e o achado que justificou
    desenhar antes de codar:

        funcoes:  GET /api/v1/functions/id/{id}  -> FunctionModel, TEM `content`
        tools:    GET /api/v1/tools/id/{id}      -> ToolAccessResponse, SEM content
                  GET /api/v1/tools/export       -> list[ToolModel], TEM `content`

    Dois objetos que parecem irmaos, com formas diferentes. Descobrir isso no
    meio da implementacao custaria uma tarde.
    """
    base = os.environ.get("OPENWEBUI_BASE_URL")
    chave = os.environ.get("OPENWEBUI_API_KEY")
    if not base or not chave:
        return None, "faltam OPENWEBUI_BASE_URL/OPENWEBUI_API_KEY neste ambiente"
    import urllib.request

    def _pegar(caminho):
        req = urllib.request.Request(base.rstrip("/") + caminho,
                                     headers={"Authorization": "Bearer " + chave})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())

    if tipo == "funcao":
        try:
            d = _pegar("/api/v1/functions/id/" + ident)
        except Exception as e:
            return None, ("a base nao respondeu a /api/v1/functions/id/%s (%s)"
                          % (ident, str(e)[:60]))
        if not isinstance(d, dict):
            return None, "/api/v1/functions/id/%s nao devolveu objeto" % ident
        if not d.get("content"):
            return None, "a funcao %r existe no painel mas veio sem `content`" % ident
        return d["content"], None

    # TOOLS: uma chamada so para todas, guardada em cache - o /export devolve a
    # lista inteira, e pedir de novo por tool seria pagar N vezes pela mesma
    # resposta.
    if "tools" not in _cache:
        try:
            _cache["tools"] = _pegar("/api/v1/tools/export")
        except Exception as e:
            _cache["tools"] = e
    d = _cache["tools"]
    if isinstance(d, Exception):
        return None, "a base nao respondeu a /api/v1/tools/export (%s)" % str(d)[:60]
    if not isinstance(d, list):
        return None, "/api/v1/tools/export nao devolveu lista (veio %s)" % type(d).__name__
    for t in d:
        if isinstance(t, dict) and str(t.get("id") or "").strip() == ident:
            if not t.get("content"):
                return None, "a tool %r esta no export mas veio sem `content`" % ident
            return t["content"], None
    return "", None                      # nao publicada: string vazia, nao None


_RE_CARIMBO = re.compile(r"\[origem:[^\]]{0,120}\]")


def _carimbo_do_painel(tipo, ident, _cache={}):
    """O carimbo `[origem: ...]` que o publish deixou no `meta.description`.

    DESDE A D63 todo publish carimba de onde veio: sha/ref/run quando sai do
    Actions, "LOCAL" quando sai da maquina de alguem. Ler isso responde de
    imediato a pergunta que o `_commit_correspondente` responde caro (varrendo
    500 commits) - e responde tambem o caso em que ele NAO responde: um publish
    de branch, ou de codigo que nunca virou commit.

    A AUSENCIA TAMBEM INFORMA, e por isso "" nao e tratado como nada: sem
    carimbo, o publish e anterior a D63 ou veio por fora do publicador.

    POR QUE NAO APROVEITA O `_publicado_do_painel`: aquele devolve (fonte,
    motivo) e e INJETAVEL nos testes (`leitor=`). Mudar o contrato dele para
    carregar mais um campo quebraria a injecao onde ela ja prova seis casos.
    Uma leitura a mais custa uma chamada; mudar um contrato provado custa mais.
    """
    base = os.environ.get("OPENWEBUI_BASE_URL")
    chave = os.environ.get("OPENWEBUI_API_KEY")
    if not base or not chave:
        return None
    import urllib.request

    def _pegar(caminho):
        req = urllib.request.Request(base.rstrip("/") + caminho,
                                     headers={"Authorization": "Bearer " + chave})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())

    if tipo == "funcao":
        d = _pegar("/api/v1/functions/id/" + ident)
        itens = [d] if isinstance(d, dict) else []
    else:
        if "export" not in _cache:
            _cache["export"] = _pegar("/api/v1/tools/export")
        itens = [t for t in (_cache["export"] or [])
                 if isinstance(t, dict) and str(t.get("id") or "").strip() == ident]
    for it in itens:
        desc = ((it.get("meta") or {}).get("description") or "")
        m = _RE_CARIMBO.search(desc)
        return m.group(0) if m else ""
    return None


def _commit_correspondente(plataforma, rel, publicado_norm, limite=500):
    """Qual commit do repo tem EXATAMENTE o conteudo que esta publicado?

    RESPONDE A PERGUNTA QUE O TAMANHO DA DIFERENCA NAO RESPONDE: "qual lado esta
    a frente?". Saber que 1.148 linhas diferem nao diz se o painel esta atrasado
    (e quanto) ou se alguem editou producao pela tela - e as duas exigem acoes
    opostas.

    Se o publicado casa com um commit antigo, o painel esta simplesmente ATRAS, e
    a distancia e contavel. Se nao casa com NENHUM, o conteudo publicado nunca
    existiu no repositorio - e ai a conversa e outra.

    A JANELA E O HISTORICO INTEIRO (500 commits), e nao uma amostra. Com 40 a
    resposta "nao corresponde a nenhum commit" ficava ambigua - podia significar
    "editaram producao" ou "e mais antigo que a janela", e as duas levam a acoes
    opostas. Uma busca que nao cobre tudo devolve uma conclusao que nao vale.

    Devolve (sha_curto, data, quantos_commits_atras), "SEM_HISTORICO", ou None.
    Nao imprime codigo em nenhum caso.
    """
    import subprocess
    def _git(*a):
        return subprocess.run(["git"] + list(a), cwd=plataforma, capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout
    # CLONE RASO NAO E "NAO ENCONTREI" - e "nao tenho onde procurar".
    #
    # `actions/checkout@v4` traz UM commit por padrao (fetch-depth: 1). Com isso
    # o laco abaixo nao acha ancora nenhuma e a conclusao sai como "o conteudo
    # publicado nao corresponde a nenhum commit" - que se le como "alguem editou
    # producao pela tela". Foi o que este achado disse na primeira rodada, e era
    # artefato do ambiente, nao fato do painel.
    #
    # E o mesmo defeito que o conferidor inteiro existe para pegar, cometido
    # dentro dele: uma resposta DEFINITIVA construida sobre uma fonte que nao
    # estava la. Aqui ela vira um estado proprio.
    saida = _git("log", "-n", str(limite), "--format=%H|%h|%ad", "--date=short",
                 "--", rel)
    linhas_log = [l for l in (saida or "").strip().split(chr(10)) if l.strip()]
    # O CRITERIO E QUANTOS COMMITS HA PARA PROCURAR, e nao a flag de clone raso.
    # Um clone raso pode ter dezenas de commits (o enxerto so corta o fundo), e
    # nesse caso a busca funciona. O que impede de responder e ter UM commit -
    # o que `actions/checkout@v4` traz por padrao.
    if len(linhas_log) < 2:
        return "SEM_HISTORICO"
    for n, linha in enumerate(linhas_log):
        if not linha.strip():
            continue
        partes = linha.split("|")
        if len(partes) < 3:
            continue
        sha, curto, data = partes[0], partes[1], partes[2]
        conteudo = _git("show", "%s:%s" % (sha, rel.replace(os.sep, "/")))
        if not conteudo:
            continue
        if _normalizar_fonte(conteudo) == publicado_norm:
            return (curto, data, n)
    return None


def _tamanho_da_diferenca(a, b):
    """(linhas realmente diferentes, numero da 1a divergencia). PURA.

    POR QUE NAO E UM `zip` POSICAO A POSICAO - e a primeira versao desta funcao
    era exatamente isso. Com UMA linha inserida no topo, todas as seguintes ficam
    deslocadas e contam como diferentes. A primeira rodada em producao devolveu
    "5655 linhas diferentes" num arquivo de 6559, e "2686" num de 2711 - numeros
    que mandam republicar tudo quando a verdade pode ser uma linha.

    NUMERO INFLADO E PIOR QUE NUMERO AUSENTE: a ausencia manda medir; o inflado
    manda agir errado, e com a confianca de quem tem um dado na mao. E o
    conteudo que parece conteudo (D54) na forma de metrica.

    `difflib` alinha os blocos iguais antes de contar, entao o numero passa a ser
    o que uma pessoa chamaria de diferenca. E a 1a linha divergente diz se a
    mudanca esta no cabecalho (version, docstring) ou no corpo.
    """
    import difflib
    la, lb = a.split(chr(10)), b.split(chr(10))
    dif, primeira = 0, None
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, la, lb).get_opcodes():
        if tag == "equal":
            continue
        dif += max(i2 - i1, j2 - j1)
        if primeira is None:
            primeira = min(i1, j1) + 1
    return dif, primeira


def conferir_config_producao():
    """Configuracao que o codigo EXIGE e producao nao tem. Classe `config_ausente`.

    POR QUE ISTO E CLASSE DE CONFERIDOR E NAO `log.warning` (D67, ponto 4):

    O `WEBUI_URL` estava vazio em producao. O gerador avisava disso a cada
    chamada, com a mensagem certa, dizendo a consequencia certa:

        "WEBUI_URL vazia -> o link sai RELATIVO. Se o anexo nativo nao chegar,
         o modelo transcreve o caminho e pode gerar 404."

    O aviso saiu por UMA SEMANA. A DETECCAO NUNCA FALHOU - o que nao existia era
    um leitor. `log.warning` em caminho de requisicao nao tem destinatario: vai
    para um log que so se abre quando ja ha problema, e ai o aviso e ruido no
    meio do incidente, nao prevencao dele.

    E o motivo de ter ficado invisivel e o pior da historia: a MITIGACAO
    funcionava. O anexo nativo torna o link desnecessario quando chega, entao
    ninguem sentia falta - e a configuracao ruim sobreviveu justamente porque a
    rede de seguranca segurava. Mitigacao que funciona bem o bastante REMOVE o
    incentivo de consertar a causa.

    Aqui o achado cai num relatorio que ja tem dono, ja roda semanalmente e ja e
    lido. Nao e "mais um relatorio" - e tirar um sinal sem leitor e por no que
    ja existe.

    SONDA SEM ADMIN, de proposito: o `/opensearch.xml` e publico e interpola o
    `WEBUI_URL` direto no XML (main.py). Se o template vier sem esquema, a
    configuracao esta vazia. Uma sonda que precisa de menos privilegio quebra
    menos vezes por motivo errado.
    """
    base = os.environ.get("OPENWEBUI_BASE_URL")
    if not base:
        return None, "falta OPENWEBUI_BASE_URL neste ambiente"
    import urllib.request
    try:
        req = urllib.request.Request(base.rstrip("/") + "/opensearch.xml")
        with urllib.request.urlopen(req, timeout=30) as r:
            xml = r.read().decode("utf-8", "replace")
    except Exception as e:
        return None, "a base nao respondeu a /opensearch.xml (%s)" % str(e)[:60]

    achados = []
    m = re.search(r'template="([^"]*)"', xml)
    alvo = m.group(1) if m else ""
    if not alvo.lower().startswith("http"):
        achados.append(_achado(
            "config_ausente",
            "WEBUI_URL esta VAZIA em producao (o /opensearch.xml monta %r, sem "
            "host). Consequencia medida: o link do gerador sai RELATIVO e, no "
            "laco agentico, o modelo o reescreve, perde a barra inicial e o "
            "navegador resolve contra /c/<chat_id> -> 404."
            % (alvo[:40] or "(vazio)"),
            "Admin -> Configuracoes -> Geral -> WebUI URL",
            "configuracao persistente: variavel de ambiente NAO pega (D62); "
            "tem de ser o painel"))
    print("  config de producao: %d ausente(s)" % len(achados))
    return achados, None


def conferir_publicado(plataforma, publicados=None, leitor=None, carimbeiro=None):
    """Painel x repo, para cada artefato publicado por API.

    TRES COMPARACOES EM ORDEM, e a ordem importa porque a primeira que diverge
    ja responde: existe -> versao -> corpo.

    A versao sozinha nao basta (alguem publica sem subir o numero) e o corpo
    sozinho tambem nao (dizer "divergente" sem dizer de QUANTAS versoes nao
    ajuda a decidir).

    NAO IMPRIME O CODIGO em nenhum achado: e fonte com valve e chave dentro.
    """
    ler = leitor or _publicado_do_painel
    carimbeiro = carimbeiro or _carimbo_do_painel
    achados = []
    conferidos = identicos = 0
    for tipo, ident, rel in (publicados or _PUBLICADOS):
        caminho = os.path.join(plataforma, rel)
        no_repo = _ler(caminho)
        if not no_repo:
            continue                     # artefato que nao existe no repo: nao e desta classe
        fonte, motivo = ler(tipo, ident)
        if fonte is None:
            # NAO CONSEGUI OLHAR. Este estado e obrigatorio e nao e detalhe: uma
            # classe que nao pode conferir e diz "nada encontrado" e a forma mais
            # silenciosa de um conferidor mentir - o /api/v1/models/ passou dias
            # assim (D57).
            achados.append(_achado(
                "nao_conferido",
                "publicado_divergente NAO foi conferida para %s %r: %s"
                % (tipo, ident, motivo),
                "ambiente de execucao",
                "classe nao conferida contada como 'nada encontrado' e a forma "
                "mais silenciosa de um conferidor mentir"))
            continue
        if fonte == "":
            achados.append(_achado(
                "publicado_ausente",
                "%s %r existe no repo e NAO esta publicada no painel" % (tipo, ident),
                rel,
                "codigo que ninguem publicou nao roda - e quem le o repo supoe "
                "que roda"))
            continue
        conferidos += 1
        a, b = _normalizar_fonte(fonte), _normalizar_fonte(no_repo)
        if a == b:
            identicos += 1
            continue
        v_painel, v_repo = _versao_de(fonte), _versao_de(no_repo)
        dif, primeira = _tamanho_da_diferenca(a, b)
        # QUAL LADO ESTA A FRENTE - a pergunta que o tamanho nao responde.
        ancora = _seguro(_commit_correspondente, plataforma, rel, a)
        if ancora == "SEM_HISTORICO":
            onde = ("NAO DA PARA DIZER qual lado esta a frente: o checkout tem UM "
                    "commit e nao ha historico para comparar - use fetch-depth: 0")
        elif ancora:
            onde = ("o painel e o commit %s de %s, %d commit(s) atras do repo"
                    % (ancora[0], ancora[1], ancora[2]))
        else:
            onde = ("o conteudo publicado NAO corresponde a nenhum commit recente "
                    "do repo - foi editado fora do repositorio, ou e mais antigo "
                    "que a janela conferida")
        # O CARIMBO DO PUBLISH (D63) responde de graca o que a ancora responde
        # caro - e responde tambem onde ela nao alcanca (publish de branch, ou de
        # codigo que nunca virou commit). Ausencia tambem informa.
        carimbo = _seguro(carimbeiro, tipo, ident)
        if carimbo:
            onde = "%s. Carimbo do publish: %s" % (onde, carimbo)
        elif carimbo == "":
            onde = ("%s. SEM carimbo de origem: publicado antes da D63, ou por "
                    "fora do publicador." % onde)
        achados.append(_achado(
            "publicado_divergente",
            "%s %r: painel version=%s x repo version=%s "
            "(%d linha(s) realmente diferentes; 1a divergencia na linha %s). %s"
            % (tipo, ident, v_painel or "?", v_repo or "?", dif,
               primeira if primeira is not None else "?", onde),
            rel,
            "o que roda nao e o que esta escrito; todo diagnostico do produto "
            "parte da suposicao contraria"))
    # CONTA EM VOZ ALTA o que conferiu, mesmo quando esta tudo igual.
    #
    # POR QUE: a primeira rodada desta classe voltou SILENCIOSA, e silencio tem
    # dois significados incompativeis - "conferi os quatro e batem" e "nao rodei".
    # Sem esta linha, distinguir os dois exigiria ler o codigo; foi exatamente o
    # que custou dias no /api/v1/models/ e o que o D37 descreve. Alarme que so
    # fala quando ha problema nao prova que olhou.
    print("  publicado x repo: %d conferido(s), %d identico(s)"
          % (conferidos, identicos))
    return achados


def codigo_de_saida(achados):
    """2 = achou (RESULTADO), 0 = limpo, 1 fica reservado para FALHA do script.

    Mesma convencao do orfaos_indice.py, e pela mesma razao: relatorio que fica
    vermelho ao cumprir a funcao treina todo mundo a ignorar o vermelho (D30).
    """
    return 2 if achados else 0

def _ids_declarados(esteira):
    """Os IDS de 'colecoes' do sync_config - le da esteira, nao de copia.

    IDS e nao chaves: a chave e a pasta-mae ("1 - Fonte") e o painel mostra o
    rotulo ("Fonte"). Comparar os dois acusava as duas maiores bases da casa como
    "fora do config" - ver conferir_colecoes_fora_do_config.
    """
    try:
        cfg = json.loads(_ler(os.path.join(esteira or "", "_scripts",
                                           "sync_config.json")))
    except Exception:
        return []
    saida = []
    for info in (cfg.get("colecoes") or {}).values():
        cid = str(((info or {}).get("id") or "")).strip()
        if cid and not cid.startswith("PREENCHER"):
            saida.append(cid)
    return saida


def _bases_que_ficam_vazias(esteira):
    """Pastas-mae DECLARADAS como excluidas: nenhuma delas deveria ter base com
    conteudo. Le do sync_config, e nao de uma lista propria - duas copias de uma
    declaracao divergem, e a que envelhece e sempre a do conferidor."""
    caminho = os.path.join(esteira or "", "_scripts", "sync_config.json")
    try:
        cfg = json.loads(_ler(caminho))
    except Exception:
        return []
    return list((cfg.get("pastas_mae_excluidas") or {}).keys())


def _contagens_do_painel(esteira):
    """{nome da base: n arquivos} do painel, ou None sem credencial/em erro.

    None e diferente de {}: vazio significa "conferi e nao ha nada"; None
    significa "nao consegui conferir". O relatorio trata os dois de forma
    diferente, e e essa a diferenca que impede um conferidor de mentir calado.

    O ENDPOINT CERTO E /knowledge/{id}/files, E ISSO NAO E DETALHE. A primeira
    versao usava /knowledge/{id} e lia `data.file_ids` - o LEGADO, que o file/add
    nao atualiza. Ela devolveria ZERO para toda base com arquivos vinculados, e
    zero e exatamente o valor que esta classe considera "certo": a conferencia
    passaria sempre, sem conferir nada. O comentario de sincronizar.listar_colecao
    ja avisava disso; eu nao li antes de escrever.

    PAGINA, porque o endpoint pagina (default 30) - sem isso, base grande contaria
    30 e a conta so estaria errada nas bases que mais importam.
    """
    base = os.environ.get("OPENWEBUI_BASE_URL")
    chave = os.environ.get("OPENWEBUI_API_KEY")
    if not base or not chave:
        return None, "faltam OPENWEBUI_BASE_URL/OPENWEBUI_API_KEY neste ambiente"
    # O MOTIVO VERDADEIRO, e nao o primeiro plausivel. A versao anterior dizia
    # "faltam as credenciais" em QUALQUER falha - inclusive quando elas estavam
    # presentes e o que faltava era o sync_config da esteira. Mandar quem le
    # conferir a credencial certa por um motivo errado custa a mesma hora que
    # custaria nao ter mensagem nenhuma, e ainda gasta a confianca na proxima.
    try:
        cfg = json.loads(_ler(os.path.join(esteira or "", "_scripts",
                                           "sync_config.json")))
        colecoes = cfg.get("colecoes") or {}
    except Exception:
        return None, ("credenciais presentes, mas falta o sync_config da esteira "
                      "(os ids das bases moram la)")
    if not colecoes:
        return None, "o sync_config da esteira nao declara nenhuma colecao"

    import urllib.request
    base = base.rstrip("/")

    def _pegar(caminho):
        req = urllib.request.Request(
            base + caminho, headers={"Authorization": "Bearer " + chave})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())

    # TODAS as colecoes do painel, e nao so as declaradas no config. Contar so as
    # configuradas era o que tornava a classe cega: base criada fora do config -
    # justamente o caso que ela deveria pegar - nao aparecia na conta.
    #
    # E ESTA CHAMADA NAO PODE FALHAR CALADA. A versao anterior fazia
    # `except Exception: catalogo = None` e seguia: sem catalogo, `colecoes` fica
    # so com as declaradas, e conferir_colecoes_fora_do_config filtra fora tudo
    # que e declarado - a intersecao fica VAZIA POR CONSTRUCAO e a classe devolve
    # zero. Zero de "conferi e nao ha nada" e zero de "nao consegui olhar" sao a
    # mesma saida, e o relatorio nao tem como distinguir.
    #
    # Isso e o D37 pela terceira vez, agora DENTRO da classe escrita para consertar
    # o D37. Vale registrar sem suavizar: o defeito nao e distracao, e a forma
    # natural de um `except` largo - ele transforma "falhei" em "nada encontrado",
    # que e a mentira mais silenciosa que um conferidor sabe contar.
    #
    # A prova de que importa esta no mesmo relatorio: _modelos_do_painel FALHA ALTO
    # ("modelo_renomeado NAO foi conferida: a base nao respondeu a /api/v1/models/")
    # e por isso a gente SABE que ela nao foi conferida. Duas chamadas irmas, a
    # mesma falha possivel, e so uma delas avisava.
    # O ENDPOINT DEVOLVE {items, total} E PAGINA, e a pagina NAO e negociavel: o
    # /api/v1/knowledge/ so aceita `page`, com o tamanho fixo em PAGE_ITEM_COUNT.
    # E a mesma armadilha do list_knowledge_bases (PR #66): ler a primeira pagina e
    # chamar de catalogo funciona ate o dia em que existirem mais bases que uma
    # pagina - e nesse dia a base que faltar e justamente a que ninguem confere.
    # Por isso o laco usa `total` como criterio de parada, e nao "veio menos que
    # pedi": so `total` sabe quantas existem.
    conhecidas = {}
    total_declarado, pagina = None, 1
    while True:
        try:
            d = _pegar("/api/v1/knowledge/?page=%d" % pagina)
        except Exception as e:
            return None, ("a base nao respondeu a /api/v1/knowledge/ (%s) - sem o "
                          "catalogo do painel a classe colecao_fora_do_config nao "
                          "tem o que conferir, e devolveria zero sem olhar" % e)
        if isinstance(d, list):          # formato antigo: lista crua
            itens, total_declarado = d, len(d)
        elif isinstance(d, dict) and isinstance(d.get("items"), list):
            itens = d["items"]
            if total_declarado is None:
                total_declarado = d.get("total")
        else:
            return None, ("/api/v1/knowledge/ nao devolveu {items,total} nem lista "
                          "(veio %s) - sem o catalogo do painel a classe "
                          "colecao_fora_do_config devolveria zero sem olhar"
                          % type(d).__name__)
        antes = len(conhecidas)
        for k in itens:
            if isinstance(k, dict) and k.get("id"):
                conhecidas[str(k["id"]).strip()] = (k.get("name") or "").strip()
        # Para quando a pagina nao acrescenta NADA de novo - cobre tanto o fim da
        # lista quanto um endpoint que ignora `page` e devolve sempre a primeira.
        # Nos dois casos quem decide se o resultado presta e a conferencia de
        # `total` logo abaixo, e nao este laco.
        if not itens or len(conhecidas) == antes:
            break
        if not isinstance(total_declarado, int) or len(conhecidas) >= total_declarado:
            break
        pagina += 1
        if pagina > 200:                 # cinto, caso as duas guardas acima falhem
            return None, ("/api/v1/knowledge/ nao termina de paginar (200 paginas) "
                          "- catalogo incompleto, nao da para concluir nada")
    if isinstance(total_declarado, int) and len(conhecidas) < total_declarado:
        return None, ("o painel declara %d colecoes e a paginacao entregou %d - "
                      "catalogo INCOMPLETO, e concluir 'nada fora do config' sobre "
                      "um catalogo incompleto e exatamente a mentira que esta "
                      "classe existe para evitar" % (total_declarado, len(conhecidas)))
    for cid, nome in conhecidas.items():
        colecoes.setdefault(nome or cid, {"id": cid})

    out, ids_por_nome = {}, {}
    for nome, info in colecoes.items():
        cid = ((info or {}).get("id") or "").strip()
        if not cid or cid.startswith("PREENCHER"):
            continue
        total, pagina = 0, 1
        try:
            while True:
                d = _pegar("/api/v1/knowledge/%s/files?limit=1000&page=%d"
                           % (cid, pagina))
                itens = d if isinstance(d, list) else (
                    (d or {}).get("files") or (d or {}).get("items") or [])
                if not itens:
                    break
                total += len(itens)
                if len(itens) < 1000:
                    break
                pagina += 1
        except Exception:
            return None, ("a base nao respondeu para a colecao %r - credencial "
                          "sem leitura nela, ou a colecao nao existe mais" % nome)
        out[nome] = total
        ids_por_nome[nome] = cid
    # (contagens por nome, id de cada nome). O id viaja junto porque a comparacao
    # de "esta no config?" e por ID - nome do painel e chave do config divergem de
    # proposito. Ver conferir_colecoes_fora_do_config.
    return (out, ids_por_nome), None


_RE_ID_MODELO = re.compile(r"`(nidum-[a-z0-9-]+)`")


def _modelos_do_painel():
    """{id do modelo: nome de exibicao} do painel, ou (None, motivo).

    O ENDPOINT CERTO E /api/v1/models/list, E A BARRA FINAL ERA O DEFEITO.

    `modelo_renomeado` era a unica classe NAO CONFERIDA do relatorio ha dias, com
    a mensagem "a base nao respondeu a /api/v1/models/ (Expecting value: line 1
    column 1 (char 0))" - corpo vazio ou nao-JSON. A causa esta escrita no proprio
    codigo do backend, em `routers/models.py`:

        @router.get("/list", ...)  # do NOT use "/" as path, conflicts with main.py

    O router NAO define "/" de proposito, porque `main.py` registra
    `@app.get("/api/v1/models")` (sem barra) como compatibilidade com a API da
    OpenAI. Pedir COM barra nao casa rota nenhuma no router e cai no
    redirecionamento de barra do FastAPI - que responde sem corpo JSON. O
    conferidor lia esse vazio e, corretamente, dizia que nao conseguiu conferir.

    NAO ERA FALHA DE CREDENCIAL NEM DE REDE: era um caractere no caminho, com o
    aviso escrito na linha de cima do endpoint, do outro lado do repositorio.

    E PAGINA, como /api/v1/knowledge/: devolve {items, total}. Mesma licao do
    PR #66 e do catalogo de colecoes - ler a primeira pagina e chamar de
    inventario funciona ate existirem mais modelos que uma pagina, e nesse dia o
    que faltar e justamente o que ninguem confere. O laco para por `total`.
    """
    base = os.environ.get("OPENWEBUI_BASE_URL")
    chave = os.environ.get("OPENWEBUI_API_KEY")
    if not base or not chave:
        return None, "faltam OPENWEBUI_BASE_URL/OPENWEBUI_API_KEY neste ambiente"
    import urllib.request

    def _pegar(caminho):
        req = urllib.request.Request(base.rstrip("/") + caminho,
                                     headers={"Authorization": "Bearer " + chave})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())

    out, total, pagina = {}, None, 1
    while True:
        try:
            d = _pegar("/api/v1/models/list?page=%d" % pagina)
        except Exception as e:
            return None, ("a base nao respondeu a /api/v1/models/list (%s)"
                          % str(e)[:70])
        if isinstance(d, list):                   # formato antigo: lista crua
            itens, total = d, len(d)
        elif isinstance(d, dict) and isinstance(d.get("items"), list):
            itens = d["items"]
            if total is None:
                total = d.get("total")
        else:
            return None, ("/api/v1/models/list nao devolveu {items,total} nem "
                          "lista (veio %s)" % type(d).__name__)
        antes = len(out)
        for m in itens:
            if isinstance(m, dict) and m.get("id"):
                out[str(m["id"]).strip()] = (m.get("name") or "").strip()
        if not itens or len(out) == antes:
            break
        if not isinstance(total, int) or len(out) >= total:
            break
        pagina += 1
        if pagina > 200:
            return None, "/api/v1/models/list nao termina de paginar (200 paginas)"
    if isinstance(total, int) and len(out) < total:
        return None, ("o painel declara %d modelos e a paginacao entregou %d - "
                      "inventario INCOMPLETO" % (total, len(out)))
    return out, None


def conferir_modelos_renomeados(citados, do_painel):
    """Id de modelo citado na doc x NOME DE EXIBICAO atual no painel.

    A DIVERGENCIA QUE ENGANOU TRES PESSOAS (D39): `nidum-10---dia-a-dia` foi
    RENOMEADO para "Nidum 1.0 - Geral", e o id ficou. Tres leituras diferentes
    concluiram "modelo revogado" a partir do nome fossilizado no id, e o caso
    entrou em tres listas de pendencia com tres opcoes de conserto - quando a
    resposta era abrir uma tela.

    NAO E UM ERRO A CORRIGIR, e por isso a mensagem nao pede conserto: o id esta
    certo, o nome esta certo, e o que falta e a LIGACAO entre os dois estar
    escrita onde alguem le. Acusar so quando o id ainda existe no painel - id
    ausente e outra classe (modelo de fato revogado).
    """
    achados = []
    for cid in sorted(citados):
        nome = (do_painel or {}).get(cid)
        if nome is None:
            continue                      # nao existe: outra classe
        if not nome:
            continue
        cauda = cid.split("---")[-1].replace("-", " ").strip().lower()
        if cauda and cauda in _fold(nome).lower():
            continue                      # o nome ainda contem o que o id promete
        achados.append(_achado(
            "modelo_renomeado",
            "a doc cita o id %r, cujo nome de exibicao hoje e %r" % (cid, nome),
            "doc x painel",
            "o id fossiliza o nome ANTIGO, e quem le o id conclui que o modelo "
            "foi revogado. Nao ha erro a corrigir - falta a ligacao escrita "
            "entre o id e o nome atual (D39)"))
    return achados

def _seguro(fn, *a, **kw):
    """Executa a coleta e devolve None se ela quebrar, em vez de derrubar tudo.

    MEDIDO em 05/09: um AttributeError dentro da coleta do painel fez o conferidor
    inteiro sair com rc=1 e PERDER as outras cinco classes - que estavam prontas e
    corretas. Conferidor e ferramenta de leitura: a falha de uma fonte tem de virar
    "esta classe nao foi conferida", nunca "nao ha relatorio".
    """
    try:
        return fn(*a, **kw)
    except Exception:
        return None


def conferir(plataforma=None, esteira=None):
    plataforma = plataforma or _PLATAFORMA
    esteira = esteira or _ESTEIRA_PADRAO
    achados = []

    codigo = _valves_do_codigo(plataforma)
    doc = _valves_da_doc(plataforma)

    # A - doc descreve valve que nao existe
    for nome, (_default, arq) in sorted(doc.items()):
        if nome in _VALVE_IGNORAR or nome in codigo:
            continue
        achados.append(_achado(
            "valve_fantasma",
            "a doc descreve a valve %s, que nao existe no codigo" % nome,
            os.path.relpath(arq, plataforma),
            "quem le a doc procura no painel uma valve que nao esta la; e quem "
            "mexe no codigo nao encontra o que a doc promete"))

    # B - valve existe e nao esta documentada
    for nome in sorted(codigo):
        if nome in _VALVE_IGNORAR or nome in doc:
            continue
        achados.append(_achado(
            "valve_nao_documentada",
            "a valve %s existe no codigo e nao esta no dicionario" % nome,
            "_nidum_tools/",
            "valve sem doc so e descoberta lendo o codigo - e o valor efetivo "
            "dela mora no banco (D24)"))

    # C - default divergente
    for nome, (default_doc, arq) in sorted(doc.items()):
        if nome not in codigo or not default_doc:
            continue
        d_doc = _fold(default_doc).strip(". ")
        d_cod = _fold(codigo[nome]).strip(". ")
        if d_doc.startswith("`"):
            d_doc = d_doc.strip("`")
        if d_doc and d_cod and d_doc != d_cod and not d_doc.endswith("..."):
            achados.append(_achado(
                "default_divergente",
                "%s: a doc diz default %r, o codigo diz %r"
                % (nome, default_doc, codigo[nome]),
                os.path.relpath(arq, plataforma),
                "a doc contradiz o codigo sobre um valor - e o efetivo esta no "
                "banco, entao os dois podem estar errados ao mesmo tempo"))

    # D - id de colecao citado na doc e ausente do config da esteira
    ids_config = _ids_do_config(esteira)
    if ids_config:
        for arq in _arquivos(os.path.join(plataforma, "_nidum_docs"), ".md"):
            nome_arq = os.path.basename(arq)
            # 07_Diario e registro HISTORICO por desenho - id velho la e correto
            if nome_arq.startswith("07_"):
                continue
            texto = _ler(arq)
            linhas_do_id = {}
            for linha in texto.split(chr(10)):
                for c in _RE_UUID8.findall(linha):
                    linhas_do_id.setdefault(c, linha)
            for curto in sorted(set(_RE_UUID8.findall(texto))):
                if curto in ids_config:
                    continue
                ctx = _fold(linhas_do_id.get(curto, "")).lower()
                # DOIS FALSOS POSITIVOS que o proprio conserto dos registros
                # vencidos criou, e que so aparecem rodando:
                #
                # (a) SHA DE COMMIT. O regex casa qualquer 8 hex, e a correcao do
                #     documento-inteiro passou a citar o commit 'e7232ec2' como
                #     PROVA da data. Acusar a prova de ser id morto e o conferidor
                #     brigando com a disciplina que ele mesmo deveria premiar.
                if "commit" in ctx:
                    continue
                # (b) ID CITADO JUSTAMENTE COMO MORTO. O 04 e o 08 dizem que
                #     'f2c8a48c' e 'a85d8a8f' foram APAGADAS - a doc esta certa, e
                #     e essa a informacao util. Sinalizar aqui treinaria a apagar a
                #     mencao, que e o oposto do que se quer: um id morto explicado
                #     e documentacao; um id morto silencioso e a armadilha.
                if any(m in ctx for m in ("apagad", "mort", "aposentad",
                                          "removid", "revogad", "extint",
                                          "nao existe mais")):
                    continue
                achados.append(_achado(
                    "id_fantasma",
                    "a doc cita o id de colecao %s..., que nao esta no "
                    "sync_config da esteira" % curto,
                    os.path.relpath(arq, plataforma),
                    "id de colecao muda e some; doc que cita id morto manda o "
                    "leitor para uma colecao que nao existe"))

    # Sem o repo da esteira, DUAS classes nao rodam. Declarar isso e a mesma regra
    # que vale para a base_indevida, e ela nao pode valer so para metade: o aviso
    # que existia era um print no comeco, e print rola para fora da tela enquanto o
    # relatorio final - o que alguem le - dizia "nada encontrado" nas duas.
    if not (esteira and os.path.isdir(os.path.join(esteira, "_scripts"))):
        for classe in ("id_fantasma", "fixture_vencida"):
            achados.append(_achado(
                "nao_conferido",
                "%s NAO foi conferida: o repositorio da esteira nao esta "
                "disponivel neste ambiente" % classe,
                "ambiente de execucao",
                "classe nao conferida contada como 'nada encontrado' e a forma "
                "mais silenciosa de um conferidor mentir"))

    # H - id de modelo citado na doc x nome de exibicao atual no painel (D39).
    citados = set()
    for arq in _arquivos(os.path.join(plataforma, "_nidum_docs"), ".md"):
        citados |= set(_RE_ID_MODELO.findall(_ler(arq)))
    if citados:
        modelos, motivo_m = _seguro(_modelos_do_painel) or (None, "erro na coleta")
        if modelos is None:
            achados.append(_achado(
                "nao_conferido",
                "modelo_renomeado NAO foi conferida: %s" % motivo_m,
                "ambiente de execucao",
                "classe nao conferida contada como 'nada encontrado' e a forma "
                "mais silenciosa de um conferidor mentir"))
        else:
            achados.extend(conferir_modelos_renomeados(citados, modelos))

    # F - FRAC_CATASTROFE fora do valor de desenho (variavel de repo da esteira).
    # Le do ambiente: na Action vem de vars.FRAC_CATASTROFE; na mao, de quem exportar.
    # Ausente NAO acusa - sem variavel vale o padrao do workflow, que ja e 0,25.
    achados.extend(conferir_frac_catastrofe(os.environ.get("FRAC_CATASTROFE")))
    # D67 ponto 4: configuracao ausente entra AQUI, e nao num log que ninguem le.
    _cfg, _motivo = _seguro(conferir_config_producao) or (None, "a coleta explodiu")
    if _cfg is None:
        achados.append(_achado(
            "nao_conferido",
            "config_ausente NAO foi conferida: %s" % (_motivo or "?"),
            "ambiente de execucao",
            "classe nao conferida contada como limpa e a forma mais silenciosa "
            "de um conferidor mentir"))
    else:
        achados.extend(_cfg)

    # G - base que deveria estar vazia e nao esta. Precisa das contagens do painel,
    # que so existem com credencial; sem ela, a classe fica de fora E ISSO E DITO no
    # relatorio, em vez de passar por "nada encontrado".
    dados, motivo = _seguro(_contagens_do_painel, esteira) or (None, "erro inesperado na coleta")
    if dados is None:
        achados.append(_achado(
            "nao_conferido",
            "base_indevida NAO foi conferida: %s" % motivo,
            "ambiente de execucao",
            "classe nao conferida contada como 'nada encontrado' e a forma mais "
            "silenciosa de um conferidor mentir"))
    else:
        contagens, ids_por_nome = dados
        achados.extend(conferir_bases_vazias(contagens, _bases_que_ficam_vazias(esteira)))
        achados.extend(conferir_colecoes_fora_do_config(
            contagens, ids_por_nome, _ids_declarados(esteira),
            _bases_que_ficam_vazias(esteira)))

    # I - o que esta PUBLICADO x o que esta no repo (doc 14). Pipe e tools vao por
    # API, manualmente: mergear na main nao publica, e ate hoje nada comparava os
    # dois lados. Nao bloqueia - divergencia e estado normal entre merge e publish.
    pub = _seguro(conferir_publicado, plataforma)
    if pub is None:
        # `_seguro` devolve None quando a coleta QUEBRA. Escrever
        # `_seguro(...) or []` seria transformar "explodiu" em "nada encontrado" -
        # o defeito que este arquivo inteiro existe para pegar, cometido na
        # chamada da classe mais nova. Todos os outros chamadores tratam o None
        # explicitamente; este nao tratava, e por isso a primeira rodada em CI
        # voltou silenciosa em vez de dizer o que houve.
        achados.append(_achado(
            "nao_conferido",
            "publicado_divergente NAO foi conferida: a coleta quebrou",
            "ambiente de execucao",
            "classe nao conferida contada como 'nada encontrado' e a forma mais "
            "silenciosa de um conferidor mentir"))
    else:
        achados.extend(pub)

    # E - fixture com caminho de pasta inexistente
    pastas = _pastas_do_repo(esteira)
    if pastas:
        for raiz in (os.path.join(plataforma, "_nidum_tools"),
                     os.path.join(esteira, "_scripts")):
            for arq in _arquivos(raiz, ".py"):
                if not os.path.basename(arq).startswith("teste_"):
                    continue
                for caminho in set(_RE_CAMINHO_FIXTURE.findall(_ler(arq))):
                    pasta = "/".join(caminho.split("/")[:-1])
                    if not pasta:
                        continue
                    pf = _fold(pasta)
                    if pf in pastas or any(p.startswith(pf + "/") for p in pastas):
                        continue
                    # SO CONTA FIXTURE QUE UM DIA FOI REAL. A primeira versao
                    # acusava 21 caminhos, e quase todos eram sinteticos de
                    # proposito: "x/y.md", "K/X.md", "QUALQUER/x.md", e ate a
                    # linha de documentacao "sigla valida -> <SIGLA>/<stem>.md".
                    # Fixture sintetica NAO envelhece - ela nunca descreveu o
                    # mundo, entao nao pode divergir dele.
                    #
                    # O criterio: o PRIMEIRO segmento tem de existir hoje no repo.
                    # Ai o achado significa "a pasta-mae continua ali e o caminho
                    # abaixo dela mudou", que e exatamente o caso do mapa de
                    # assuntos - 9 de 19 caminhos mortos por renomeacao interna.
                    #
                    # PONTO CEGO ASSUMIDO: fixture cuja pasta-mae INTEIRA sumiu
                    # (as de "ACERVOS/", da epoca do roteamento antigo) passa
                    # batida. E deliberado - separar essas das sinteticas exigiria
                    # historia do git, e um alarme que dispara 21 vezes com 2
                    # verdadeiros e desligado na primeira semana. Prefiro pegar
                    # menos e ser lido.
                    topo = pf.split("/")[0]
                    if topo not in {x.split("/")[0] for x in pastas}:
                        continue
                    achados.append(_achado(
                        "fixture_vencida",
                        "a fixture usa o caminho %r, cuja pasta nao existe no "
                        "repo" % caminho,
                        os.path.basename(arq),
                        "a suite fica VERDE testando uma forma que a producao "
                        "nao produz - confianca falsa, e foi assim que o mapa "
                        "de assuntos ficou morto por semanas"))
    return achados


_TITULOS = {
    "config_ausente": "CONFIGURACAO QUE PRODUCAO NAO TEM",
    "valve_fantasma": "Valves que a doc descreve e o codigo nao tem",
    "valve_nao_documentada": "Valves do codigo que a doc nao descreve",
    "default_divergente": "Defaults em que a doc e o codigo discordam",
    "id_fantasma": "Ids de colecao citados na doc e ausentes do config",
    "nao_conferido": ("CLASSES QUE NAO FORAM CONFERIDAS - leia antes de concluir "
                       "que esta tudo bem"),
    "colecao_fora_do_config": ("Colecoes no painel que a esteira NAO mantem "
                               "(fora do config e fora das excluidas)"),
    "modelo_renomeado": ("Ids de modelo cujo NOME DE EXIBICAO mudou "
                         "(nao e erro: falta a ligacao escrita)"),
    "fixture_vencida": ("Fixtures apontando para pasta que nao existe "
                        "(LISTA PARA REVISAO: parte pode ser sintetica)"),
    "frac_catastrofe": "FRAC_CATASTROFE fora do valor de desenho (0,25)",
    "base_indevida": ("Base com conteudo que NAO devia receber arquivo "
                      "(pasta-mae declarada como excluida)"),
    "publicado_divergente": ("O que esta PUBLICADO diverge do repositorio "
                             "(pipe e tools vao por API, nao por deploy)"),
    "publicado_ausente": "Existe no repo e NAO esta publicado no painel",
}


def relatar(achados):
    if not achados:
        print("CONFERIR REGISTROS: nada divergente. Doc, codigo, config e "
              "fixtures descrevem a mesma realidade.")
        return 0
    por_classe = {}
    for a in achados:
        por_classe.setdefault(a["classe"], []).append(a)
    print("CONFERIR REGISTROS: %d divergencia(s) em %d classe(s)."
          % (len(achados), len(por_classe)))
    print("Nenhuma quebra nada agora - e esse o problema: elas so aparecem "
          "quando alguem tropeca.\n")
    # ITERA O QUE EXISTE, e nao a lista de titulos.
    #
    # O DEFEITO (11/09/2026), e ele durou uma rodada: o laco era
    # `for classe in _TITULOS`. Classe sem titulo entrava na CONTAGEM do
    # cabecalho e nunca era IMPRESSA. Foi o que aconteceu com as duas classes
    # novas do publicado: "81 divergencias em 7 classes" com seis secoes na
    # tela - e as duas que faltavam eram justamente as recem-escritas.
    #
    # E o D51 na propria ferramenta: o universo do relatorio era uma LISTA
    # DECLARADA, entao tudo que nasce fora dela e invisivel POR CONSTRUCAO. A
    # ordem dos titulos continua mandando na apresentacao; o que mudou e que
    # classe sem titulo aparece assim mesmo, com o nome cru e um aviso - porque
    # achado que nao cabe numa gaveta conhecida e o que mais precisa ser visto.
    conhecidas = [c for c in _TITULOS if c in por_classe]
    novas = [c for c in sorted(por_classe) if c not in _TITULOS]
    for classe in conhecidas + novas:
        itens = por_classe.get(classe)
        if not itens:
            continue
        titulo = _TITULOS.get(classe)
        if titulo is None:
            titulo = "%s (classe SEM TITULO - acrescente em _TITULOS)" % classe
        print("== %s (%d) ==" % (titulo, len(itens)))
        print("   consequencia: %s" % itens[0]["consequencia"])
        for a in itens:
            print("   - [%s] %s" % (a["onde"], a["detalhe"]))
        print("")
    return 1


def nota_markdown(achados):
    """O relatorio no formato de Nota da plataforma.

    GRAVA EM ARQUIVO, nao publica. Publicar exigiria credencial de escrita, e um
    conferidor que escreve na plataforma deixa de ser conferidor: verificacao que
    altera estado nao e verificacao (D28). Quem importa a Nota e o Davi.

    A Nota abre pelo que MUDOU desde a ultima leitura - contagem por classe -
    porque a lista inteira e longa demais para ser lida toda vez, e uma lista que
    nao se le nao protege ninguem.
    """
    import collections
    por_classe = collections.Counter(a["classe"] for a in achados)
    L = ["# Conferencia de registros", ""]
    if not achados:
        L += ["Nenhuma divergencia entre a documentacao, as fixtures e o que o "
              "codigo e o repositorio tem.", ""]
        return chr(10).join(L)
    L += ["| classe | achados |", "|---|---:|"]
    for classe, n in por_classe.most_common():
        L.append("| `%s` | %d |" % (classe, n))
    L.append("")
    for classe, _n in por_classe.most_common():
        L += ["## %s" % _TITULOS.get(classe, classe), ""]
        primeiro = True
        for a in achados:
            if a["classe"] != classe:
                continue
            if primeiro:
                L += ["> %s" % a["consequencia"], ""]
                primeiro = False
            L.append("- **%s** - %s" % (a["onde"], a["detalhe"]))
        L.append("")
    return chr(10).join(L)

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Confere doc/fixtures contra codigo e repo (so-leitura).")
    ap.add_argument("--plataforma", default=_PLATAFORMA)
    ap.add_argument("--esteira", default=_ESTEIRA_PADRAO)
    ap.add_argument("--nota", default="",
                    help="grava o relatorio em Markdown, no formato de Nota da "
                         "plataforma (nao publica: a importacao e manual)")
    args = ap.parse_args(argv)
    if not os.path.isdir(args.esteira):
        print("AVISO: repo da esteira nao encontrado em %r - as classes "
              "'id_fantasma' e 'fixture_vencida' ficam de fora." % args.esteira)
    achados = conferir(args.plataforma, args.esteira)
    relatar(achados)
    if args.nota:
        io.open(args.nota, "w", encoding="utf-8", newline=chr(10)).write(
            nota_markdown(achados))
        print("Nota gravada em %s (importar na plataforma e acao do Davi)." % args.nota)
    # 2 = ACHOU (resultado, nao falha). Ver codigo_de_saida.
    return codigo_de_saida(achados)


if __name__ == "__main__":
    sys.exit(main())
