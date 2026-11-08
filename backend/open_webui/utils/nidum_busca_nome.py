# -*- coding: ascii -*-
"""
Busca de arquivo PELO NOME, por palavras, datas e siglas (Nidum).

POR QUE EXISTE (08/11/2026):

Na bateria de 12 perguntas (Fase 0 do plano de 07/11), as duas respostas
erradas do agente vieram do MESMO arquivo:

    EGP > 3.1.4 Apresentacoes Comite de Projetos > 2. Reuniao de
    Acompanhamento > 9.  Reuniao_Acompanhamento _CP_03.11.26.md

Pergunta: "Quem e o gestor do projeto Jardins segundo a reuniao do Comite de
Projetos de 03/11?". O agente buscou por nome "Comite de Projetos 03-11", nao
achou nada e respondeu que a reuniao NAO EXISTE. Existe.

A busca do upstream era `File.filename ILIKE '%<consulta>%'`: a consulta
INTEIRA tinha de aparecer, igual, dentro do nome. Tres coisas a derrubavam:

  1. palavras fora de ordem ou separadas: "Comite de Projetos 03-11" nao e um
     pedaco de "...Comite de Projetos > ... _CP_03.11.26";
  2. a data em outro formato: o usuario escreve 03/11, o nome diz 03.11.26;
  3. acento e caixa: o banco compara bytes; "Comite" nao casa "Comite" com
     acento, e nomes do SharePoint as vezes vem em Unicode decomposto.

O QUE ESTE MODULO FAZ: a consulta vira uma lista de REQUISITOS, e cada
requisito tem alternativas.

  - palavra: casa se algum termo do nome COMECA com ela (sem acento, sem caixa,
    plural reduzido: "reunioes" casa "reuniao", "ata" NAO casa "plataforma");
  - data: "03/11", "03-11-2026", "03.11.26", "2026-11-03" ou "novembro de 2026"
    casam a data lida do nome (nidum_datas_arquivo.py) ou os numeros no nome;
  - sigla: "Comite de Projetos" tambem casa "CP" no nome, e "CP" na consulta
    tambem casa "Comite de Projetos" - nos dois sentidos.

E BEST-EFFORT POR CONTRATO: nada aqui levanta excecao para quem chama.

O QUE NAO FAZ: nao le conteudo (isso e da busca por conteudo) e nao inventa
sinonimo fora da tabela de siglas. Sigla nova entra na tabela, com o nome que
aparece nos arquivos - nao por deducao.
"""

import re
import unicodedata

from open_webui.utils.nidum_datas_arquivo import data_do_nome

# ---------------------------------------------------------------- siglas
#
# DUAS FONTES, e o teste guarda a primeira contra drift:
#  (a) ECOSSISTEMAS: copia das `descricoes` de
#      chatnd-conhecimento/_scripts/ecossistemas.json (Governanca de Dados v2),
#      a fonte unica da esteira. teste_busca_nome.py compara as duas quando o
#      repo da esteira estiver ao lado e FALHA se divergirem.
#  (b) GESTAO DE PROJETOS: siglas que aparecem nos NOMES dos arquivos do EGP e
#      nao estao na Governanca. Cada uma foi conferida num nome real (08/11).
SIGLAS_ECOSSISTEMAS = {
    'REG': 'Regulacao',
    'MKT': 'Marketing',
    'PROD': 'Produtos',
    'BRA': 'Nidum Brasil',
    'CVI': 'Comunidades Vivas',
    'FAN': 'Fazenda Ancora',
    'MUN': 'Nidum Mundo',
    'OPE': 'Operacoes',
    'FIN': 'Financeiro',
    'JUR': 'Juridico',
    'ACA': 'Academia',
    'TEC': 'Plataforma Tecnologica',
    'SUS': 'Sustentabilidade',
    'CC': 'Conselho Curador',
    'CT': 'Comite Tecnico',
    'CE': 'Comite Executivo',
}
SIGLAS_GESTAO = {
    'CP': 'Comite de Projetos',          # Reuniao_Acompanhamento _CP_03.11.26
    'CTE': 'Comite Tecnico',             # CTE_Convergencia_27-06-2026
    'EGP': 'Escritorio de Gestao de Projetos',  # pasta EGP
    'GP': 'Gestao de Projetos',          # Governanca_GP_04.08.26_V1
    'TAP': 'Termo de Abertura do Projeto',  # TAP do Implantacao Nidum Mundo
}

STOPWORDS = {
    'a', 'o', 'as', 'os', 'e', 'de', 'da', 'do', 'das', 'dos', 'em', 'na', 'no',
    'nas', 'nos', 'para', 'por', 'com', 'um', 'uma', 'ao', 'aos', 'pela', 'pelo',
    'que', 'qual', 'quais', 'sobre', 'the', 'of', 'and',
}

MESES = {
    'janeiro': 1, 'fevereiro': 2, 'marco': 3, 'abril': 4, 'maio': 5, 'junho': 6,
    'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10, 'novembro': 11,
    'dezembro': 12,
}


def dobrar(texto, separar_juntas=False):
    """Sem acento, minusculo, tudo que nao e letra/numero vira espaco.

    separar_juntas=True tambem separa palavras GRUDADAS por maiuscula
    ("CronogramaMVPISerraNegra" -> "cronograma mvpi serra negra"). NIDUM
    (08/11/2026): medido no conjunto cego de cruzamento - "Serra Negra" nao
    achava BRA_CronogramaMVPISerraNegra_26_10_19_v1 e o agente respondeu que o
    cronograma nao existia. O nome e comparado nas DUAS formas (grudada e
    separada), para "chatnd" continuar casando "ChatND"."""
    if not texto:
        return ''
    t = unicodedata.normalize('NFKD', str(texto))
    t = ''.join(c for c in t if not unicodedata.combining(c))
    if separar_juntas:
        t = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', t)          # SerraNegra -> Serra Negra
        t = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', t)     # MVPISerra -> MVPI Serra
    return re.sub(r'[^0-9a-z]+', ' ', t.casefold()).strip()


def radical(palavra):
    """Plural reduzido, so o suficiente para casar por inicio de termo."""
    p = palavra
    if len(p) > 4 and p.endswith('oes'):
        return p[:-3]            # reunioes -> reuni (casa reuniao)
    if len(p) > 4 and p.endswith(('aes', 'ais')):
        return p[:-2]            # capitaes -> capita
    # NIDUM (08/11/2026): singular em -ao tambem vira o radical do plural em
    # -oes. Medido em producao: o agente buscou "ata reuniao"; "reuniao" nao e
    # o inicio de "Reunioes" (a pasta das atas), entao as atas de 06/11 em
    # "Reunioes > Atas" ficaram de fora e ele deu 14/10 como a mais recente.
    if len(p) > 5 and p.endswith('ao'):
        return p[:-2]            # reuniao -> reuni (casa reuniao e reunioes)
    if len(p) > 3 and p.endswith('s') and not p.endswith('ss'):
        return p[:-1]            # projetos -> projeto, atas -> ata
    return p


def _palavras(texto):
    return [radical(w) for w in dobrar(texto).split() if w not in STOPWORDS]


def _tabela_siglas():
    tab = {}
    for fonte in (SIGLAS_ECOSSISTEMAS, SIGLAS_GESTAO):
        for sigla, nome in fonte.items():
            tab[sigla.lower()] = _palavras(nome)
    return tab


_SIGLAS = _tabela_siglas()

# ---------------------------------------------------------------- datas da consulta

# (?<![\dvV.]): "v1.5" e "3.1.4" sao versao/secao, nao data.
_D_DMA = re.compile(r'(?<![\dvV.])(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2}|\d{4}))?(?!\d)(?![.]\d)')
_D_AMD = re.compile(r'(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)')


def _ano(txt):
    if not txt:
        return None
    a = int(txt)
    return a + 2000 if a < 100 else a


def _extrair_datas(texto):
    """Devolve (datas, texto_sem_datas). Cada data = (dia|None, mes, ano|None)."""
    datas = []
    resto = texto or ''

    def tira(m, d):
        datas.append(d)
        return ' '

    resto = _D_AMD.sub(lambda m: tira(m, (int(m.group(3)), int(m.group(2)), int(m.group(1)))), resto)

    def dma(m):
        dia, mes = int(m.group(1)), int(m.group(2))
        if not (1 <= dia <= 31 and 1 <= mes <= 12):
            return m.group(0)    # "3.1" de versao, "15/40": nao e data
        return tira(m, (dia, mes, _ano(m.group(3))))

    resto = _D_DMA.sub(dma, resto)

    # "novembro de 2026", "agosto 2026", "agosto"
    dob = dobrar(resto)
    for mes_nome, mes in MESES.items():
        m = re.search(r'\b%s\b(?:\s+(?:de\s+)?(\d{4}))?' % mes_nome, dob)
        if m:
            datas.append((None, mes, int(m.group(1)) if m.group(1) else None))
            dob = dob[:m.start()] + ' ' + dob[m.end():]
    return datas, dob


# ---------------------------------------------------------------- a consulta


def montar(consulta):
    """Consulta -> lista de requisitos. Cada requisito e um dict:
    {'tipo': 'palavras', 'alternativas': [[termo, ...], ...]} ou
    {'tipo': 'data', 'data': (dia, mes, ano)}.
    Um requisito vale se QUALQUER alternativa vale (todos os termos dela)."""
    datas, resto = _extrair_datas(consulta or '')
    termos = [radical(w) for w in resto.split() if w not in STOPWORDS]
    reqs = []

    # sigla por extenso na consulta ("comite de projetos") -> tambem a sigla.
    # Agrupado por extenso: "comite tecnico" e CT E CTE, as duas alternativas.
    por_extenso = {}
    for sigla, nome in _SIGLAS.items():
        por_extenso.setdefault(tuple(nome), []).append(sigla)
    usados = set()
    # Nome de UMA palavra so vale para os ecossistemas da Governanca ("Academia"
    # -> ACA, "Marketing" -> MKT). NIDUM (08/11/2026): medido no conjunto cego
    # de cruzamento - "Academia setembro 2026" achou 3 de 8 atas, so as que tem
    # "Academia" escrito no nome; as outras sao "ACA_...".
    eco = {s.lower() for s in SIGLAS_ECOSSISTEMAS}
    for nome, siglas in sorted(por_extenso.items(), key=lambda kv: -len(kv[0])):
        vale = len(nome) >= 2 or (len(nome) == 1 and any(s in eco for s in siglas))
        if vale and all(t in termos for t in nome) and not (set(nome) & usados):
            alternativas = [list(nome)] + [[s] for s in sorted(siglas)]
            reqs.append({'tipo': 'palavras', 'alternativas': alternativas})
            usados.update(nome)

    for t in termos:
        if t in usados:
            continue
        if t in _SIGLAS and len(_SIGLAS[t]) >= 1:
            # sigla na consulta ("cp") -> tambem por extenso
            reqs.append({'tipo': 'palavras', 'alternativas': [[t], list(_SIGLAS[t])]})
        else:
            reqs.append({'tipo': 'palavras', 'alternativas': [[t]]})
        usados.add(t)

    for d in datas:
        reqs.append({'tipo': 'data', 'data': d})
    return reqs


def _termo_casa(termo, nome_dobrado):
    # sigla curta (ate 3 letras): termo INTEIRO, senao "cp" casaria "cpf".
    if termo in _SIGLAS and len(termo) <= 3:
        return re.search(r'(?<![0-9a-z])%s(?![0-9a-z])' % re.escape(termo), nome_dobrado) is not None
    return re.search(r'(?<![0-9a-z])%s' % re.escape(termo), nome_dobrado) is not None


def _data_casa(d, nome, nome_dobrado):
    dia, mes, ano = d
    lida = data_do_nome(nome)
    if lida and lida.month == mes and (dia is None or lida.day == dia) and (ano is None or lida.year == ano):
        return True
    if dia is None:
        return False
    # nome com dia e mes mas sem ano ("..._29.07.md"): os dois numeros juntos
    for dd in {str(dia), '%02d' % dia}:
        for mm in {str(mes), '%02d' % mes}:
            if re.search(r'(?<![0-9])%s %s(?![0-9])' % (dd, mm), nome_dobrado):
                return True
    return False


def pontuar(nome, reqs):
    """Quantos requisitos o nome atende (0..len(reqs))."""
    if not reqs:
        return 0
    nd = dobrar(nome)
    nd_sep = dobrar(nome, separar_juntas=True)
    n = 0
    for r in reqs:
        try:
            if r['tipo'] == 'data':
                ok = _data_casa(r['data'], nome, nd)
            else:
                ok = any(all(_termo_casa(t, nd) or _termo_casa(t, nd_sep) for t in alt)
                         for alt in r['alternativas'])
        except Exception:
            ok = False
        n += 1 if ok else 0
    return n


def filtrar(arquivos, consulta):
    """Filtra dicts {'filename', ...} pela consulta.

    Devolve (lista, modo):
      modo 'todas'   - cada arquivo atende TODOS os requisitos (o caso normal);
      modo 'parcial' - ninguem atendeu todos; voltam os que atendem MAIS (pelo
                       menos metade), com 'match_score' em cada um. Existe para
                       o agente nao concluir "nao existe" quando so uma palavra
                       nao bateu - foi exatamente o erro de 07/11;
      modo 'vazio'   - nada casou nem pela metade;
      modo 'sem_consulta' - consulta vazia: tudo volta;
      modo 'trecho'  - a consulta so tem palavras vazias ("de"): vale o
                       comportamento antigo, o texto como pedaco do nome.
    A ordem final (data do nome) e de quem chama; aqui so se filtra.
    """
    if not (consulta or '').strip():
        return list(arquivos or []), 'sem_consulta'
    reqs = montar(consulta)
    if not reqs:
        alvo = dobrar(consulta)
        return [a for a in arquivos or [] if alvo in dobrar(a.get('filename', ''))], 'trecho'
    total = len(reqs)
    pontos = [(pontuar(a.get('filename', ''), reqs), a) for a in arquivos or []]
    todas = []
    for p, a in pontos:
        if p == total:
            item = dict(a)
            # 'name' = casou so com o nome do arquivo; 'folder' = precisou da
            # pasta. Medido em 08/11: "portfolio" casava 35 nomes e os 3
            # primeiros eram cronogramas de uma PASTA "Portfolio".
            item['match_in'] = 'name' if pontuar(_proprio(a.get('filename', '')), reqs) == total else 'folder'
            todas.append(item)
    if todas:
        return todas, 'todas'
    # PARCIAL so quando falta UM requisito de tres ou mais: e o caso do deck do
    # CP ("Comite de Projetos 03-11 Jardins": a pessoa e o projeto nao estao no
    # nome). Com dois requisitos, "metade" e uma palavra so - medido em 08/11,
    # "conselho agosto" devolvia 143 arquivos de agosto. Ruido nao ajuda.
    melhor = max([p for p, _ in pontos] or [0])
    if total < 3 or melhor < total - 1:
        return [], 'vazio'
    parcial = []
    for p, a in pontos:
        if p == melhor:
            item = dict(a)
            item['match_score'] = '%d/%d' % (p, total)
            parcial.append(item)
    return parcial, 'parcial'


def _proprio(nome):
    """So o nome do arquivo, sem o caminho de pastas ("A > B > arquivo.md")."""
    return (nome or '').split(' > ')[-1]
