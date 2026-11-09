# -*- coding: utf-8 -*-
"""
Data da reuniao/documento lida do NOME do arquivo (Nidum).

POR QUE EXISTE (07/11/2026):

Perguntaram ao agente "quais as reunioes mais recentes?" e ele respondeu com
atas de 01/10, 29/10 e 10/09 - com a base cheia de atas de 03 a 06/11. A base
estava certa; a BUSCA e que nao sabia o que e "recente".

`search_knowledge_files` (tools/builtin.py) ordenava por `File.updated_at`, que
e a hora em que o arquivo ENTROU NA BASE, e nao a data da reuniao. Depois de um
resync, todos os arquivos tem o mesmo updated_at (minutos de diferenca) e a
ordem "mais novo primeiro" vira sorteio. Some-se o corte em 5 resultados e o
agente via cinco atas aleatorias entre centenas - e as chamava, honestamente,
de "as mais recentes". Resposta honesta e errada, de novo.

A data VERDADEIRA ja estava no nome: a esteira grava `..._04-11-2026_AUTO.md`.
Ninguem lia.

DERIVA DO NOME, como a procedencia (nidum_procedencia.py): barato, estavel e
escolhido por uma pessoa (ou pela convencao da esteira).

BEST-EFFORT POR CONTRATO: nome sem data, ou data impossivel (31-02-2026),
devolve None - nunca levanta. Arquivo sem data vai para o FIM da lista, depois
de todos os datados; entre eles vale o updated_at, como antes.
"""

import re
from datetime import date

# dd-mm-aaaa (convencao da esteira) e aaaa-mm-dd. Separador -, _, . ou espaco
# (o espaco so com ano de 4 digitos: "Escaneamento_3D_01 10 2026").
# Os limites (?<!\d) / (?!\d) impedem casar pedaco de um numero maior.
_DMA = re.compile(r'(?<!\d)(\d{1,2})[-_. ](\d{1,2})[-_. ](\d{4})(?!\d)')
_AMD = re.compile(r'(?<!\d)(\d{4})[-_.](\d{1,2})[-_.](\d{1,2})(?!\d)')

# NIDUM (08/11/2026) - ANO DE DOIS DIGITOS e data compacta.
#
# O DEFEITO, medido em producao: o deck "Reuniao_Acompanhamento _CP_03.11.26"
# (Comite de Projetos de 03/11) ficava SEM DATA - so se lia ano de 4 digitos -
# e ia para o FIM da lista. O agente viu primeiro a ata de 24/08 e respondeu
# que ela era "a ultima reuniao do Comite". Dos 1.407 nomes da base em 08/11,
# 888 nao tinham data lida; os formatos que faltavam, por frequencia:
#   aa_mm_dd   45  (cronogramas: BRA_CronogramaMVPISerraNegra_26_09_15_v1)
#   dd.mm.aa   21  (Governanca_GP_04.08.26_V1, ..._CP_03.11.26)
#   dd-mm-aa    1  (Apresentacao_Interna_NIDUM_MKT 25-06-26)
#   aaaammdd    2  (NID-LAUDO-20260811-...)
#
# A AMBIGUIDADE e real ("24.10.25" pode ser 24/10/2025 ou 25/10/2024), e se
# resolve pela CONVENCAO DA CASA, medida nos nomes: com "_" o ano vem primeiro
# (aa_mm_dd), com "." ou "-" vem por ultimo (dd.mm.aa). Se a leitura preferida
# nao for uma data valida, tenta a outra.
#
# A TRAVA contra numero que nao e data (versao "v1.5.0", secao "3.1.4", codigo
# "30_09_02"): ano de dois digitos so vale entre 2025 e 2029 (a base e de 2026).
# Fora disso, nao e data - e nome sem data vai para o fim, como antes. Errar
# para "sem data" e o lado seguro; errar para uma data falsa poe o arquivo no
# lugar errado. Medido: com 2020 como piso, "BRA_CronogramaMVPVirginia_30_09_23_v2"
# virava 30/09/2023 - o unico erro em 82 nomes. Com 2025, fica sem data.
_DOIS = re.compile(r'(?<![\dvV.])(\d{1,2})([-_.])(\d{1,2})\2(\d{2})(?![\d])')
_COMPACTA = re.compile(r'(?<!\d)(202\d)(\d{2})(\d{2})(?!\d)')
_ANO_MIN, _ANO_MAX = 2025, 2029


def _valida(ano, mes, dia):
    try:
        return date(int(ano), int(mes), int(dia))
    except (ValueError, TypeError):
        return None


def _plausivel(d):
    return d if d and _ANO_MIN <= d.year <= _ANO_MAX else None


def _dois_digitos(a, sep, b, c):
    """a<sep>b<sep>c com c de dois digitos. Devolve date ou None."""
    dma = _plausivel(_valida(2000 + int(c), b, a))   # dd.mm.aa
    amd = _plausivel(_valida(2000 + int(a), b, c))   # aa_mm_dd
    if sep == '_':
        return amd or dma
    return dma or amd


def data_do_nome(nome):
    """Devolve a data (datetime.date) contida no nome do arquivo, ou None.

    Havendo mais de uma, vale a ULTIMA: o nome carrega o caminho da pasta
    ("Reunioes > Atas > ..."), e a data do documento fica no fim, junto do
    nome proprio.
    """
    if not nome or not isinstance(nome, str):
        return None
    achados = []
    for m in _DMA.finditer(nome):
        d = _valida(m.group(3), m.group(2), m.group(1))
        if d:
            achados.append((m.start(), d))
    for m in _AMD.finditer(nome):
        d = _valida(m.group(1), m.group(2), m.group(3))
        if d:
            achados.append((m.start(), d))
    for m in _DOIS.finditer(nome):
        d = _dois_digitos(m.group(1), m.group(2), m.group(3), m.group(4))
        if d:
            achados.append((m.start(), d))
    for m in _COMPACTA.finditer(nome):
        d = _plausivel(_valida(m.group(1), m.group(2), m.group(3)))
        if d:
            achados.append((m.start(), d))
    if not achados:
        return None
    achados.sort(key=lambda par: par[0])
    return achados[-1][1]


def _data_do_metadado(item):
    """NIDUM (08/11/2026, etapa C): data_documento que a esteira derivou (do nome
    ou do conteudo, so com regras medidas como confiaveis) e gravou em
    meta['nidum']. Usada SO quando o nome nao tem data."""
    try:
        v = ((item or {}).get('nidum') or {}).get('data_documento')
        return date.fromisoformat(v) if v else None
    except (ValueError, TypeError, AttributeError):
        return None


def ordenar_por_data_do_nome(arquivos):
    """Ordena dicts {'filename', 'updated_at', ...}: data do nome DESC, sem data
    no fim, empate por updated_at DESC. Acrescenta 'date' (aaaa-mm-dd) em cada
    um que tiver data. Devolve uma lista NOVA; nao mexe na de entrada.
    """
    saida = []
    for a in arquivos or []:
        item = dict(a)
        d = data_do_nome(item.get('filename')) or _data_do_metadado(item)
        if d:
            item['date'] = d.isoformat()
        saida.append((d, item))

    def chave(par):
        d, item = par
        upd = item.get('updated_at') or 0
        try:
            upd = -float(upd)
        except (ValueError, TypeError):
            upd = 0
        # sem data -> grupo 1 (fim); com data -> grupo 0, mais nova primeiro
        if d is None:
            return (1, 0, upd)
        return (0, -d.toordinal(), upd)

    saida.sort(key=chave)
    return [item for _, item in saida]
