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


def conferir_colecoes_fora_do_config(contagens, declaradas, excluidas):
    """Colecao existe no painel e NAO esta declarada em lugar nenhum?

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
    conhecidas = {_fold(x).lower() for x in (declaradas or [])}
    conhecidas |= {_fold(x).lower() for x in (excluidas or [])}
    achados = []
    for nome, n in sorted((contagens or {}).items()):
        if _fold(nome).lower() in conhecidas:
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

def codigo_de_saida(achados):
    """2 = achou (RESULTADO), 0 = limpo, 1 fica reservado para FALHA do script.

    Mesma convencao do orfaos_indice.py, e pela mesma razao: relatorio que fica
    vermelho ao cumprir a funcao treina todo mundo a ignorar o vermelho (D30).
    """
    return 2 if achados else 0

def _bases_declaradas(esteira):
    """As chaves de 'colecoes' do sync_config - le da esteira, nao de copia."""
    try:
        cfg = json.loads(_ler(os.path.join(esteira or "", "_scripts",
                                           "sync_config.json")))
    except Exception:
        return []
    return list((cfg.get("colecoes") or {}).keys())


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
    try:
        catalogo = _pegar("/api/v1/knowledge/")
    except Exception as e:
        return None, ("a base nao respondeu a /api/v1/knowledge/ (%s) - sem o "
                      "catalogo do painel a classe colecao_fora_do_config nao tem "
                      "o que conferir, e devolveria zero sem olhar" % e)
    if not isinstance(catalogo, list):
        return None, ("/api/v1/knowledge/ nao devolveu uma lista (veio %s) - sem o "
                      "catalogo do painel a classe colecao_fora_do_config devolveria "
                      "zero sem olhar" % type(catalogo).__name__)
    conhecidas = {}
    for k in catalogo:
        if isinstance(k, dict) and k.get("id"):
            conhecidas[str(k["id"]).strip()] = (k.get("name") or "").strip()
    for cid, nome in conhecidas.items():
        colecoes.setdefault(nome or cid, {"id": cid})

    out = {}
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
    return out, None


_RE_ID_MODELO = re.compile(r"`(nidum-[a-z0-9-]+)`")


def _modelos_do_painel():
    """{id do modelo: nome de exibicao} do painel, ou None sem credencial."""
    base = os.environ.get("OPENWEBUI_BASE_URL")
    chave = os.environ.get("OPENWEBUI_API_KEY")
    if not base or not chave:
        return None, "faltam OPENWEBUI_BASE_URL/OPENWEBUI_API_KEY neste ambiente"
    import urllib.request
    req = urllib.request.Request(base.rstrip("/") + "/api/v1/models/",
                                 headers={"Authorization": "Bearer " + chave})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            dados = json.loads(r.read().decode())
    except Exception as e:
        return None, "a base nao respondeu a /api/v1/models/ (%s)" % str(e)[:60]
    out = {}
    for m in (dados or []):
        if isinstance(m, dict) and m.get("id"):
            out[str(m["id"]).strip()] = (m.get("name") or "").strip()
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

    # G - base que deveria estar vazia e nao esta. Precisa das contagens do painel,
    # que so existem com credencial; sem ela, a classe fica de fora E ISSO E DITO no
    # relatorio, em vez de passar por "nada encontrado".
    contagens, motivo = _seguro(_contagens_do_painel, esteira) or (None, "erro inesperado na coleta")
    if contagens is None:
        achados.append(_achado(
            "nao_conferido",
            "base_indevida NAO foi conferida: %s" % motivo,
            "ambiente de execucao",
            "classe nao conferida contada como 'nada encontrado' e a forma mais "
            "silenciosa de um conferidor mentir"))
    else:
        achados.extend(conferir_bases_vazias(contagens, _bases_que_ficam_vazias(esteira)))
        achados.extend(conferir_colecoes_fora_do_config(
            contagens, _bases_declaradas(esteira), _bases_que_ficam_vazias(esteira)))

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
    for classe in _TITULOS:
        itens = por_classe.get(classe)
        if not itens:
            continue
        print("== %s (%d) ==" % (_TITULOS[classe], len(itens)))
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
