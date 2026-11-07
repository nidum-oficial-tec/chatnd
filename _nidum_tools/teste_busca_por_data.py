# -*- coding: ascii -*-
"""
Prova de que a busca de arquivos ordena pela DATA DO NOME, e nao pelo upload.

O DEFEITO, medido em producao (07/11/2026): "quais as datas das reunioes mais
recentes?" -> o agente respondeu 01/10, 29/10 e 10/09 (nessa ordem), com a base
cheia de atas de 03 a 06/11.

DUAS CAUSAS SOMADAS, as duas do upstream (mesma familia da listagem de bases,
teste_listagem_bases.py):
  (a) ordem por File.updated_at - hora em que o arquivo ENTROU na base. Depois
      de um resync, e praticamente igual para todos: a ordem vira sorteio;
  (b) corte em 5, calado. O agente via cinco atas ao acaso e as chamava,
      honestamente, de "as mais recentes".

O QUE ESTE TESTE GUARDA:
1. Que a data sai do NOME (dd-mm-aaaa), inclusive com o caminho da pasta na
   frente, e que data impossivel nao vira data.
2. Que a ordem e data DESC, sem-data no fim, empate por updated_at.
3. Que o caso real sai certo mesmo com updated_at INVERTIDO (o pior caso).
4. Que a funcao real usa isso, ordena ANTES de paginar e declara o total.

USO: py _nidum_tools/teste_busca_por_data.py
"""

import importlib.util
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

falhas = []


def check(nome, cond):
    print(("  OK   " if cond else "  FALHOU  ") + nome)
    if not cond:
        falhas.append(nome)


def carregar():
    # Modulo puro: carrega pelo caminho, sem subir o Open WebUI.
    caminho = os.path.join(RAIZ, "backend", "open_webui", "utils",
                           "nidum_datas_arquivo.py")
    spec = importlib.util.spec_from_file_location("nidum_datas_arquivo", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    m = carregar()
    dn = m.data_do_nome

    print("== a data sai do nome ==")
    d = dn("Reunioes > Atas > PROJ_Estruturacao EGP Fase 2_04-11-2026_AUTO.md")
    check("dd-mm-aaaa com caminho na frente", d is not None and d.isoformat() == "2026-11-04")
    check("aaaa-mm-dd tambem", dn("ata_2026-11-06.md").isoformat() == "2026-11-06")
    check("dia/mes de um digito", dn("x_4-1-2026_AUTO.md").isoformat() == "2026-01-04")
    check("sem data -> None", dn("Brandbook > Manual da Marca.md") is None)
    check("data impossivel -> None", dn("x_31-02-2026.md") is None)
    check("nome vazio/None nao levanta", dn("") is None and dn(None) is None)
    check("numero longo nao vira data", dn("x_104-11-20261.md") is None)
    check("duas datas: vale a ultima",
          dn("Pasta 01-01-2020 > ata_05-11-2026.md").isoformat() == "2026-11-05")

    print("")
    print("== o caso real, com updated_at no PIOR caso (invertido) ==")
    # updated_at mais NOVO para as atas mais VELHAS: sob a ordem antiga, as de
    # outubro/setembro vinham primeiro - o que o agente respondeu.
    arquivos = [
        {"filename": "TEC > TEC_Vistos e Escritorios Juridicos_01-10-2026_AUTO.md", "updated_at": 900},
        {"filename": "TEC > TEC_Plataforma Juridico Imoveis_29-10-2026_AUTO.md", "updated_at": 899},
        {"filename": "TEC > TEC_Plataforma Due Diligence Juridico_10-09-2026_AUTO.md", "updated_at": 898},
        {"filename": "Reunioes > Atas > PROJ_Acompanhamento Semanal de Projetos_06-11-2026_AUTO.md", "updated_at": 100},
        {"filename": "PROD > PROD_Modelagem e Orcamento MVP Ipanema_03-11-2026_AUTO.md", "updated_at": 101},
        {"filename": "Reunioes > Atas > PROJ_Estruturacao EGP Fase 2_04-11-2026_AUTO.md", "updated_at": 102},
        {"filename": "Brandbook > Manual.md", "updated_at": 999},
    ]
    saida = m.ordenar_por_data_do_nome(arquivos)
    datas = [a.get("date") for a in saida]
    check("mais nova primeiro: 06/11", datas[0] == "2026-11-06")
    check("ordem completa por data DESC",
          datas[:6] == ["2026-11-06", "2026-11-04", "2026-11-03",
                        "2026-10-29", "2026-10-01", "2026-09-10"])
    check("29/10 vem ANTES de 01/10 (o erro do modelo)",
          datas.index("2026-10-29") < datas.index("2026-10-01"))
    check("sem data vai para o FIM, mesmo com o updated_at mais novo",
          saida[-1]["filename"] == "Brandbook > Manual.md" and "date" not in saida[-1])
    check("nao muta a lista de entrada", "date" not in arquivos[0])

    print("")
    print("== empate de data: vale o updated_at mais novo ==")
    emp = m.ordenar_por_data_do_nome([
        {"filename": "a_05-11-2026.md", "updated_at": 1},
        {"filename": "b_05-11-2026.md", "updated_at": 2},
    ])
    check("b (updated_at 2) antes de a", emp[0]["filename"] == "b_05-11-2026.md")
    check("updated_at ausente nao levanta",
          len(m.ordenar_por_data_do_nome([{"filename": "x.md"}, {"filename": "y_01-01-2026.md", "updated_at": None}])) == 2)

    print("")
    print("== a funcao real usa isso ==")
    caminho = os.path.join(RAIZ, "backend", "open_webui", "tools", "builtin.py")
    try:
        with open(caminho, encoding="utf-8") as f:
            fonte = f.read()
    except OSError:
        print("  (builtin.py nao encontrado - guarda pulada)")
        fonte = ""
    if fonte:
        ini = fonte.index("async def search_knowledge_files(")
        fim = fonte.index("\nasync def ", ini + 10)
        corpo = fonte[ini:fim]
        check("chama ordenar_por_data_do_nome", "ordenar_por_data_do_nome(all_files)" in corpo)
        i_ord = corpo.index("ordenar_por_data_do_nome(all_files)")
        i_pag = corpo.index("ordenados[skip : skip + count]")
        check("ordena ANTES de paginar", i_ord < i_pag)
        check("o default deixou de ser 5", "count: int = 5," not in corpo)
        check("devolve 'total'", "'total': total," in corpo)
        check("devolve 'truncated'", "'truncated': truncated," in corpo)
        check("query vazia e permitida (lista tudo)", "query: str = ''" in corpo)
        check("o docstring avisa que updated_at nao e recencia", "does NOT tell" in corpo)
        check("count/skip em texto nao quebram o fatiamento", "skip = max(int(skip or 0), 0)" in corpo
              and "count = max(int(count or 20), 1)" in corpo)
        leve = fonte[fonte.index("async def _nidum_arquivos_das_bases("):ini]
        check("a consulta leve nao carrega File.data", "File.data" not in leve.split('"""')[2])

        print("")
        print("== list_knowledge concorda com a busca sobre o que e recente ==")
        ini2 = fonte.index("async def list_knowledge(")
        fim2 = fonte.index("\nasync def ", ini2 + 10)
        corpo2 = fonte[ini2:fim2]
        check("list_knowledge ordena pela data do nome antes de paginar",
              corpo2.index("ordenar_por_data_do_nome(") < corpo2.index("ordenados[skip : skip + count]"))

    print("")
    if falhas:
        print("BUSCA POR DATA: %d FALHA(S)" % len(falhas))
        return 1
    print("BUSCA POR DATA OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
