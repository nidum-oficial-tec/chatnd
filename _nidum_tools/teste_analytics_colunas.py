# -*- coding: ascii -*-
"""
Toda chave escrita em `_ev` tem coluna no INSERT? Se nao tem, o dado nao existe.

O CASO, e ele e meu (12/09/2026): a 1.66.0 acrescentou tres contadores -
`recusa_tool`, `recusa_salva`, `recusa_final` - para responder a pergunta que o
Davi fez antes mesmo de existirem: "quantas vezes a retentativa salvou?". Sem
esse numero, "a rede cobriu um azar" e "a rede esconde um defeito que acontece
sempre" sao indistinguiveis (D68).

Os tres foram escritos em `_ev`. Nenhum foi acrescentado ao CREATE TABLE, a lista
de ALTER, nem ao INSERT - que tem lista de colunas EXPLICITA. Resultado: o pipe
escreve num dicionario que e lido chave a chave por uma lista fixa, e as tres
chaves caem no chao em silencio.

    O TESTE DA 1.66.0 PASSAVA. Ele afirmava `_ev["recusa_tool"] == 1` - ou seja,
    testava o DICIONARIO, nao a persistencia. Helper testado, fiacao nao (D71),
    cometido por mim UM DIA depois de registrar o D71.

Por isso este teste nao olha um contador: olha a REGRA. Varre o fonte atras de
toda atribuicao `_ev["x"] = ...` e exige coluna correspondente. Contador novo sem
coluna passa a ser erro de CI, e nao uma descoberta de semanas depois quando
alguem for consultar o numero e encontrar a tabela sem ele.
"""

import ast
import io
import os
import re
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
FALHAS = []


def checa(nome, cond, extra=""):
    if cond:
        print("  ok   %s" % nome)
    else:
        print("  FALHA %s %s" % (nome, extra))
        FALHAS.append(nome)


def chaves_escritas(fonte):
    """Toda chave literal atribuida em `_ev[...]`, por AST.

    AST e nao regex: `_ev["x"] = 1` aparece indentado, dentro de `if`, e as vezes
    com a chave montada. Regex pegaria as faceis e perderia as outras - e as
    outras sao justamente as que ninguem lembra de conferir.
    """
    achadas = set()
    for n in ast.walk(ast.parse(fonte)):
        alvos = []
        if isinstance(n, ast.Assign):
            alvos = n.targets
        elif isinstance(n, ast.AugAssign):
            alvos = [n.target]
        for t in alvos:
            # OS DOIS NOMES: o evento circula como `_ev` na maior parte do pipe
            # e como `ev` dentro do bloco que fecha a latencia. Varrer so um
            # produzia falso positivo - `latencia_ms` apareceu como "coluna que
            # ninguem preenche" quando ela e preenchida por `ev["latencia_ms"]`.
            # Acusacao errada num teste de higiene gasta a confianca dele.
            if (isinstance(t, ast.Subscript)
                    and isinstance(t.value, ast.Name)
                    and t.value.id in ("_ev", "ev")
                    and isinstance(t.slice, ast.Constant)
                    and isinstance(t.slice.value, str)):
                achadas.add(t.slice.value)
    return achadas


def colunas_do_insert(fonte):
    """As colunas que o INSERT realmente grava, lidas do proprio SQL."""
    m = re.search(r"INSERT INTO eventos \(([^)]*)\)", fonte, re.S)
    if not m:
        return set()
    bruto = re.sub(r'"\s*\n\s*"', "", m.group(1))
    return {c.strip() for c in bruto.split(",") if c.strip()}


# Chaves que existem no evento mas NAO sao para gravar. A lista e curta e cada
# item tem motivo - se crescer, e sinal de que o evento virou saco de coisas.
_NAO_GRAVAVEIS = {
    "t0",          # marca de tempo para calcular latencia; a latencia e que vai
}


def main():
    print("teste_analytics_colunas")
    fonte = io.open(os.path.join(_AQUI, "chatnd.py"), encoding="utf-8").read()

    escritas = chaves_escritas(fonte)
    colunas = colunas_do_insert(fonte)
    checa("achei o INSERT e suas colunas", len(colunas) > 10, len(colunas))
    checa("achei chaves escritas em _ev", len(escritas) > 10, len(escritas))

    orfas = sorted(escritas - colunas - _NAO_GRAVAVEIS)
    checa("toda chave de _ev tem coluna no INSERT", orfas == [],
          "SEM COLUNA: " + ", ".join(orfas))

    # E o contrario tambem informa: coluna que ninguem preenche e coluna morta -
    # nao quebra nada, mas mente sobre o que o evento mede.
    vazias = sorted(c for c in colunas - escritas
                    if c not in ("ts", "desfecho", "user_hash"))
    if vazias:
        print("       NOTA: colunas que nenhum `_ev[...]` preenche: %s"
              % ", ".join(vazias))

    print("")
    if FALHAS:
        print("FALHOU: %d" % len(FALHAS))
        return 1
    print("TODOS OS TESTES PASSARAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
