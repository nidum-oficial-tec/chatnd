# -*- coding: utf-8 -*-
"""
Etiquetas de PROCEDENCIA (Nidum). Uma definicao, dois consumidores.

POR QUE EXISTE (12/09/2026, itens #3 e #13 da Fase E):

O pipe ChatND etiqueta cada trecho recuperado antes de entregar ao modelo -
`_etiquetas_trecho`, em chatnd.py. Sao essas etiquetas que sustentam a parede
entre a rota geral e a rota documentos (D23): o modelo pode ver as duas fontes
porque cada uma chega DECLARADA. Sem etiqueta, a parede vira promessa.

O AGENTE NAO TEM ISSO. Ele recebe os trechos por `query_knowledge_files`
(tools/builtin.py), que monta {'content', 'source', ...} e devolve JSON cru. O
modelo ve o texto de um documento publico de terceiro exatamente como ve uma ata
de decisao da casa - e a unica coisa que o impede de tratar um pelo outro e
sorte.

Isto NAO e uma regra nova: e a regra que ja existe, aplicada no caminho que
ficou de fora quando o agente entrou.

DERIVA DO NOME, e nao do conteudo. O nome do arquivo carrega a pasta de origem
("... > Externo > ...") e convencoes da casa (rascunho, convergencia). Ler o
conteudo para classificar seria caro, lento e chutaria; o nome e barato, estavel
e foi escolhido por uma pessoa.

BEST-EFFORT POR CONTRATO: nome ausente ou estranho devolve lista vazia. Nunca
levanta, nunca degrada a resposta. Uma etiqueta a menos e um trecho sem rotulo;
uma excecao aqui seria uma busca sem resultado.
"""

import re
import unicodedata


def _dobrar(texto):
    """Dobra acento e caixa. MESMO criterio do `_f3_fold` do pipe.

    Reusado de proposito: os dois recebem o mesmo dado (nome de arquivo vindo do
    SharePoint) e ter dois criterios de comparacao para o mesmo dado e como ter
    dois relogios. Se este divergir do pipe, o agente e o pipe passam a etiquetar
    o MESMO documento de formas diferentes - que e pior que nenhum dos dois
    etiquetar.
    """
    s = unicodedata.normalize("NFD", str(texto or "").strip())
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


# As tres etiquetas, na ordem em que o pipe as emite. A ordem importa para o
# teste de equivalencia com o pipe - lista igual, ordem igual.
_REGRAS = (
    (("ippul", "nd-externo", " > externo"),
     "[PROCEDENCIA EXTERNA: documento publico de terceiro (ex.: lei municipal) "
     "- NAO citar como posicao ou decisao da Nidum]"),
    (("rascunho", "v31"),
     "[STATUS: RASCUNHO nao publicado - nao tratar como versao vigente]"),
    (("convergencia",),
     "[TIPO: convergencia (ata de decisao)]"),
)


def etiquetas_de_procedencia(fonte):
    """Etiquetas para um trecho, derivadas do NOME do arquivo. PURA.

    Devolve lista (possivelmente vazia). Equivalente ao `_etiquetas_trecho` do
    pipe - `teste_procedencia.py` prova a equivalencia lendo o fonte do pipe,
    para as duas nao divergirem em silencio.
    """
    f = _dobrar(fonte)
    return [rotulo for gatilhos, rotulo in _REGRAS if any(g in f for g in gatilhos)]


def custo_em_chars(fonte):
    """Quantos chars as etiquetas acrescentam a um trecho. Para MEDIR, nao adivinhar.

    Existe porque "irrelevante" e estimativa, e esta semana mostrou o que
    acontece com estimativa nao medida. O `+1` por etiqueta e a quebra de linha
    que as separa do conteudo.
    """
    ets = etiquetas_de_procedencia(fonte)
    return sum(len(e) + 1 for e in ets)


def anotar_chunk(chunk, fonte):
    """Acrescenta `procedencia` ao chunk quando ha etiqueta. Devolve o MESMO dict.

    EXISTE PARA SER TESTAVEL, e isso e a licao do D71 virando estrutura em vez de
    intencao. A alternativa era montar o campo inline no `builtin.py`, dentro de
    um laco que so roda com banco vetorial, request e usuario - e ai o unico teste
    possivel seria afirmar que o codigo CONTEM a chamada, nao que o valor sai.
    "Helper testado, fiacao nao" foi exatamente esse buraco, e a forma de nao
    repeti-lo e deixar a fiacao ser uma funcao.

    Sem etiqueta, NAO cria a chave: chunk sem procedencia e diferente de chunk com
    procedencia vazia. O primeiro diz "nome comum"; o segundo diria "olhei e nao
    achei", que e afirmacao que ninguem fez.
    """
    ets = etiquetas_de_procedencia(fonte)
    if ets:
        chunk["procedencia"] = ets
    return chunk
