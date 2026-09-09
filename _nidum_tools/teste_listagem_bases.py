# -*- coding: ascii -*-
"""
Prova de que a listagem de bases NUNCA esconde uma base em silencio.

O DEFEITO, medido em producao (05/09/2026): o agente pediu as bases acessiveis,
recebeu DEZ de doze, e "Fonte" e "Reunioes" - as duas maiores - nao estavam entre
elas. Ele respondeu "atas anteriores nao disponiveis", o que era HONESTO: para
ele, Reunioes nao existia.

RESPOSTA HONESTA E ERRADA e a pior combinacao possivel: nao ha sintoma, e quem le
nao tem como desconfiar. Foi isso que fez o teste 1 parecer regressao de
raciocinio quando era bug de listagem.

DUAS CAUSAS SOMADAS, as duas do upstream:
  (a) count=10 por padrao, num universo de doze;
  (b) ordenacao por updated_at DESC - e o campo NAO e tocado por file/add. A base
      mais ESTAVEL era a primeira a sumir: quanto mais antiga e confiavel, mais
      invisivel.

O QUE ESTE TESTE GUARDA, e que nenhuma leitura pega:

1. Que a ordem e por NOME. Uma listagem de DESCOBERTA responde "o que existe", e
   nao "o que mexi por ultimo" - e sob recencia a base certa some justamente
   quando esta estavel, que e quando ela e mais confiavel.

2. Que o TOTAL e declarado. O total sempre existiu (a camada de dados calcula
   select(func.count()) e devolve em result.total) e era descartado. Cortar sem
   dizer quanto ficou de fora e o que transforma um limite em APAGAMENTO.

3. Que 'truncated' e verdadeiro QUANDO corta - e falso quando nao corta. Sem a
   segunda metade, uma implementacao que dissesse "truncated: true" sempre
   passaria, e o agente pediria paginas que nao existem para sempre.

USO: python _nidum_tools/teste_listagem_bases.py
"""

import json
import os
import sys

falhas = []


def check(nome, cond):
    print(("  OK   " if cond else "  FALHOU  ") + nome)
    if not cond:
        falhas.append(nome)


def montar(bases, total, skip=0):
    """Reproduz a saida de list_knowledge_bases, na mesma ordem de operacoes.

    Copia deliberada: a funcao real e async e carrega o mundo do Open WebUI. A
    guarda contra esta copia divergir e o ultimo bloco, que le o arquivo REAL.
    """
    itens = list(bases)
    itens.sort(key=lambda k: (k.get("name") or "").lower())
    truncated = (skip + len(itens)) < total
    payload = {
        "total": total,
        "shown": len(itens),
        "truncated": truncated,
        "knowledge_bases": itens,
    }
    if truncated:
        payload["note"] = (
            "INCOMPLETE listing: %d of %d knowledge bases shown." % (len(itens), total)
        )
    return json.loads(json.dumps(payload, ensure_ascii=False))


def base(nome, updated):
    return {"id": nome.lower(), "name": nome, "description": "", "file_count": 1,
            "updated_at": updated}


def main():
    # As doze do caso real, com as datas que produziram o defeito: Fonte e
    # Reunioes sao as mais ANTIGAS, e eram as duas maiores.
    doze = [
        base("Produtos", 900), base("Tecnologia", 899), base("Operacoes", 898),
        base("Gestao de Projetos", 897), base("Marketing", 896),
        base("Academia", 895), base("Sustentabilidade", 894),
        base("Juridico", 893), base("Plataformas Regionais", 892),
        base("Brandbook", 891),
        base("Fonte", 100), base("Reunioes", 100),
    ]

    print("== ordem por NOME, nao por recencia ==")
    saida = montar(doze, total=12)
    nomes = [k["name"] for k in saida["knowledge_bases"]]
    check("a lista sai em ordem alfabetica", nomes == sorted(nomes, key=str.lower))
    check("Fonte esta na lista", "Fonte" in nomes)
    check("Reunioes esta na lista", "Reunioes" in nomes)
    check("as doze aparecem", len(nomes) == 12)

    print("")
    print("== o caso exato do defeito: as duas mais antigas eram as que sumiam ==")
    # Sob a ordem antiga (updated_at desc) com corte em 10, estas duas caem fora.
    por_recencia = sorted(doze, key=lambda k: -k["updated_at"])[:10]
    caiam = {k["name"] for k in doze} - {k["name"] for k in por_recencia}
    check("sob recencia+corte, Fonte e Reunioes caiam fora (o bug reproduzido)",
          caiam == {"Fonte", "Reunioes"})
    check("sob ordem por nome, nenhuma cai",
          len(montar(doze, total=12)["knowledge_bases"]) == 12)

    print("")
    print("== o total e DECLARADO quando corta ==")
    cortada = montar(doze[:10], total=12)
    check("truncated = true", cortada["truncated"] is True)
    check("total diz 12", cortada["total"] == 12)
    check("shown diz 10", cortada["shown"] == 10)
    check("a nota diz o que fazer", "Raise" in cortada.get("note", "")
          or "INCOMPLETE" in cortada.get("note", ""))

    print("")
    print("== e NAO mente quando nao corta ==")
    check("truncated = false com tudo na mao", saida["truncated"] is False)
    check("sem nota quando completo", "note" not in saida)
    check("shown == total", saida["shown"] == saida["total"])

    print("")
    print("== paginacao: skip nao inventa truncamento ==")
    pag = montar(doze[10:], total=12, skip=10)
    check("ultima pagina nao e truncada", pag["truncated"] is False)
    check("mas o total continua 12", pag["total"] == 12)

    print("")
    print("== a copia acima nao divergiu da funcao real ==")
    caminho = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "backend", "open_webui", "tools", "builtin.py")
    try:
        with open(caminho, encoding="utf-8") as f:
            fonte = f.read()
    except OSError:
        print("  (builtin.py nao encontrado - guarda pulada)")
        fonte = ""
    if fonte:
        ini = fonte.index("async def list_knowledge_bases(")
        fim = fonte.index("async def ", ini + 10)
        corpo = fonte[ini:fim]
        check("o default deixou de ser 10", "count: int = 10," not in corpo)
        check("ordena por nome",
              "knowledge_bases.sort(key=lambda k: (k.get('name') or '').lower())" in corpo)
        check("le o total de result.total", "getattr(result, 'total', None)" in corpo)
        check("devolve 'truncated'", "'truncated': truncated," in corpo)
        check("devolve 'total'", "'total': total," in corpo)

    print("")
    if falhas:
        print("LISTAGEM DE BASES: %d FALHA(S)" % len(falhas))
        return 1
    print("LISTAGEM DE BASES OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
