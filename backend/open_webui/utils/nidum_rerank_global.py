# -*- coding: ascii -*-
"""
Reranker UMA VEZ sobre os candidatos de todas as bases (Nidum, 08/11/2026).

POR QUE EXISTE - medido em producao em 08/11/2026, mesma pergunta, 13 bases:

    hibrida, k=5   (~130 pares no reranker)    17,8 s
    hibrida, k=48  (~1.250 pares no reranker)  67,9 s

O upstream roda o reranker DENTRO de cada base: BM25 (k) + vetor (k) -> ate
2k candidatos por base -> cross-encoder em TODOS. Com 13 bases e k=48 sao
~1.250 pares por busca, ~22 pares/s no CPU do container. O custo fixo (ler
as bases, montar o BM25, consultar o vetor) fica em ~18 s; o resto, ~50 s,
e reranker. Foi tambem o reranker em 13 bases ao mesmo tempo que estourou o
teto de threads e derrubava o servidor (D94).

O QUE MUDA: em cada base roda so a busca hibrida (BM25 + vetor, RRF), SEM
reranker. Os candidatos das bases sao intercalados POR POSICAO (o 1o de cada
base, depois o 2o de cada base...) ate `profundidade` por base, sem repetir
trecho. O reranker roda UMA vez nesse conjunto (~13 x 12 = ~156 pares).

POR QUE INTERCALAR POR POSICAO e nao por nota: a nota do RRF de cada base so
vale dentro da base (e posicao, nao relevancia). Intercalar da a toda base a
mesma chance de por os seus melhores na mesa; quem decide entre eles e o
reranker, que e o unico que compara pergunta e trecho de verdade.

O QUE PODE PIORAR: um trecho que a busca hibrida punha abaixo da posicao
`profundidade` na sua base nao chega mais ao reranker. Antes, ate ~96 por
base chegavam. Por isso a profundidade e variavel de ambiente
(NIDUM_RERANK_PROFUNDIDADE; 0 = comportamento antigo, sem mudar codigo) e a
mudanca so vale com a regua antes e depois.

Funcoes PURAS aqui (testaveis offline); a fiacao fica em retrieval/utils.py.
"""

import hashlib
import os

PADRAO = 12


def profundidade():
    """NIDUM_RERANK_PROFUNDIDADE: candidatos por base. 0 ou invalido-negativo =
    desligado (o upstream roda). Ausente = PADRAO."""
    bruto = os.environ.get('NIDUM_RERANK_PROFUNDIDADE')
    if bruto is None or str(bruto).strip() == '':
        return PADRAO
    try:
        return max(int(bruto), 0)
    except (ValueError, TypeError):
        return PADRAO


def _chave(doc, chave_hash):
    meta = getattr(doc, 'metadata', None) or {}
    h = meta.get(chave_hash) if chave_hash else None
    if h:
        return h
    texto = getattr(doc, 'page_content', '') or ''
    return hashlib.sha256(texto.encode('utf-8', 'replace')).hexdigest()


def intercalar(listas, prof, chave_hash=None):
    """listas: uma lista de documentos POR BASE, cada uma ja na ordem da busca
    hibrida daquela base. Devolve uma lista unica: posicao 1 de todas as bases,
    depois posicao 2..., ate `prof` por base, sem repetir trecho (o mesmo
    trecho em duas bases entra uma vez, na primeira em que aparece)."""
    if prof <= 0:
        return []
    vistos, saida = set(), []
    for pos in range(prof):
        for lista in listas or []:
            if pos < len(lista or []):
                doc = lista[pos]
                k = _chave(doc, chave_hash)
                if k not in vistos:
                    vistos.add(k)
                    saida.append(doc)
    return saida


def cortar(pares, k):
    """pares (nota, doc) do reranker -> os k melhores, nota DESC."""
    return sorted(pares, key=lambda p: p[0], reverse=True)[: max(int(k or 0), 0)]
