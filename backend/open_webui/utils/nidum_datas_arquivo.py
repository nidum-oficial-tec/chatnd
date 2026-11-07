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

# dd-mm-aaaa (convencao da esteira) e aaaa-mm-dd. Separador -, _ ou .
# Os limites (?<!\d) / (?!\d) impedem casar pedaco de um numero maior.
_DMA = re.compile(r'(?<!\d)(\d{1,2})[-_.](\d{1,2})[-_.](\d{4})(?!\d)')
_AMD = re.compile(r'(?<!\d)(\d{4})[-_.](\d{1,2})[-_.](\d{1,2})(?!\d)')


def _valida(ano, mes, dia):
    try:
        return date(int(ano), int(mes), int(dia))
    except (ValueError, TypeError):
        return None


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
    if not achados:
        return None
    achados.sort(key=lambda par: par[0])
    return achados[-1][1]


def ordenar_por_data_do_nome(arquivos):
    """Ordena dicts {'filename', 'updated_at', ...}: data do nome DESC, sem data
    no fim, empate por updated_at DESC. Acrescenta 'date' (aaaa-mm-dd) em cada
    um que tiver data. Devolve uma lista NOVA; nao mexe na de entrada.
    """
    saida = []
    for a in arquivos or []:
        item = dict(a)
        d = data_do_nome(item.get('filename'))
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
