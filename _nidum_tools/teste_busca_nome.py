# -*- coding: ascii -*-
"""
Prova da busca de arquivo pelo NOME por palavras, datas e siglas (08/11/2026).

O DEFEITO, medido em producao (bateria de 12, 07/11/2026): "Quem e o gestor
do projeto Jardins segundo a reuniao do Comite de Projetos de 03/11?" -> o
agente buscou "Comite de Projetos 03-11", a busca por nome nao achou, e ele
respondeu que a reuniao NAO EXISTE. O arquivo existe:
    ...Comite de Projetos > ... > 9.  Reuniao_Acompanhamento _CP_03.11.26.md
E na pergunta vizinha ("ultima reuniao do Comite") o mesmo deck ficou SEM DATA
(ano de 2 digitos) e foi para o fim da lista: o agente respondeu 24/08.

O QUE ESTE TESTE GUARDA:
1. As datas novas do nome (aa_mm_dd, dd.mm.aa, aaaammdd) e as travas contra
   numero que nao e data (versao, secao, ano fora de 2025-2029).
2. Os dois casos reais: o deck do CP casa "Comite de Projetos 03-11" e
   "CP 03/11", e e o PRIMEIRO de "Comite de Projetos" (mais novo).
3. O que NAO pode casar: "ata" em "plataforma", "cp" em "cpf".
4. Modo parcial: uma palavra a mais nao zera a busca.
5. A copia das siglas nao diverge da Governanca (ecossistemas.json da
   esteira), quando o repo da esteira esta ao lado.
6. A ferramenta real usa o filtro e nao filtra mais no SQL.

Nomes: copiados da base de producao em 08/11/2026 (lista curta, escolhida -
a base tem documentos pessoais que nao vao para o git).

USO: py _nidum_tools/teste_busca_nome.py
"""

import importlib.util
import io
import json
import os
import sys
import types

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UTILS = os.path.join(RAIZ, "backend", "open_webui", "utils")

falhas = []


def check(nome, cond):
    print(("  OK   " if cond else "  FALHOU  ") + nome)
    if not cond:
        falhas.append(nome)


def carregar():
    """Carrega os dois modulos puros sem subir o Open WebUI: o de busca importa
    `open_webui.utils.nidum_datas_arquivo`, entao o pacote e montado aqui."""
    for pkg in ("open_webui", "open_webui.utils"):
        if pkg not in sys.modules:
            m = types.ModuleType(pkg)
            m.__path__ = []
            sys.modules[pkg] = m
    mods = {}
    for nome in ("nidum_datas_arquivo", "nidum_busca_nome"):
        spec = importlib.util.spec_from_file_location(
            "open_webui.utils." + nome, os.path.join(UTILS, nome + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["open_webui.utils." + nome] = mod
        spec.loader.exec_module(mod)
        mods[nome] = mod
    return mods["nidum_datas_arquivo"], mods["nidum_busca_nome"]


# Nomes reais (acentos em escape: este arquivo e ASCII-only, regra do repo).
CP_PASTA = (u"EGP > 3.1.4 Apresenta\u00e7\u00f5es Comit\u00ea de Projetos > "
            u"2. Reuni\u00e3o de Acompanhamento > ")
CP_0311 = CP_PASTA + u"9.  Reuni\u00e3o_Acompanhamento _CP_03.11.26.md"
CP_2710 = CP_PASTA + u"8. Reuni\u00e3o_Acompanhamento _CP_27.10.26.md"
CP_2408 = CP_PASTA + u"2. Reuni\u00e3o_Acompanhamento _CP_24.08.26.md"
ATA_2408 = (u"EGP > 3.1.4 Apresenta\u00e7\u00f5es Comit\u00ea de Projetos > "
            u"1. Atas > 3. Ata Comit\u00ea de Projetos 24-08-2026.md")
NOMES = [
    CP_2408, CP_0311, CP_2710, ATA_2408,
    u"Reuni\u00f5es > Atas > PROJ_Acompanhamento Semanal de Projetos_06-11-2026_AUTO.md",
    u"Reuni\u00f5es > Atas > CTE_Converg\u00eancia_27-06-2026.md",
    u"CVI > CVI_Converg\u00eancia_08-06-2026.md",
    u"MKT > MKT_Converg\u00eancia_11-06-2026.md",
    u"Reuni\u00f5es > Atas > GER_Converg\u00eancia_02-07-2026.md",
    u"FAN > FAN_Converg\u00eancia_29-05-2026.md",
    u"ACA > ACA_Nidum Prumo_29-07-2026.fatos.md",
    u"TEC > TEC_Plataforma Jur\u00eddico Im\u00f3veis_29-10-2026.md",
    u"BRA > BRA_CronogramaMVPISerraNegra_26_10_19_v1.md",
    u"Captacao > A-Nova-Porta-de-Entrada-da-Nidum 29.07.md",
    u"OPE > Modelo_CPF_Proprietario.md",
]


def arquivos(nomes):
    return [{"id": str(i), "filename": n, "updated_at": 0} for i, n in enumerate(nomes)]


def nomes_de(lista):
    return [a["filename"] for a in lista]


def main():
    datas, busca = carregar()
    dn = datas.data_do_nome

    print("== datas novas no nome ==")
    check("aa_mm_dd (cronograma)", str(dn("BRA_CronogramaMVPISerraNegra_26_09_15_v1.md")) == "2026-09-15")
    check("dd.mm.aa (deck do CP)", str(dn(CP_0311)) == "2026-11-03")
    check("dd-mm-aa", str(dn(u"Apresenta\u00e7\u00e3o_Interna_NIDUM_MKT 25-06-26 new.md")) == "2026-06-25")
    check("aaaammdd", str(dn("NID-LAUDO-20260811-IPA-BT19-206.md")) == "2026-08-11")
    check("dd mm aaaa com espaco", str(dn("Contrato_NIDUM_Escaneamento_3D_01 10 2026.md")) == "2026-10-01")
    check("4 digitos continua igual", str(dn("PROJ_x_04-11-2026_AUTO.md")) == "2026-11-04")
    check("versao v1.5.0 nao e data", dn("BRI_Guia_do_Usuario_v1.5.0_PT-BR.md") is None)
    check("secao 3.1.4 nao e data", dn(u"3.1.4 Apresenta\u00e7\u00f5es.md") is None)
    check("ano fora de 2025-2029 nao e data", dn("BRA_CronogramaMVPVirginia_30_09_23_v2.md") is None)

    print("== o caso real: o deck do Comite de Projetos de 03/11 ==")
    lista, modo = busca.filtrar(arquivos(NOMES), u"Comit\u00ea de Projetos 03-11")
    check("'Comite de Projetos 03-11' acha o deck (antes: nada)", CP_0311 in nomes_de(lista) and modo == "todas")
    check("... e so ele", nomes_de(lista) == [CP_0311])
    lista, modo = busca.filtrar(arquivos(NOMES), "CP 03/11")
    check("'CP 03/11' acha o deck", nomes_de(lista) == [CP_0311])
    lista, modo = busca.filtrar(arquivos(NOMES), "comite de projetos")
    ordem = nomes_de(datas.ordenar_por_data_do_nome(lista))
    check("'comite de projetos' sem acento acha os 4", len(ordem) == 4)
    check("... e o de 03/11 vem PRIMEIRO (antes: ultimo, sem data)", ordem and ordem[0] == CP_0311)
    lista, _ = busca.filtrar(arquivos(NOMES), u"reuni\u00f5es comit\u00ea de projetos novembro de 2026")
    check("'reunioes comite de projetos novembro de 2026' acha o de 03/11", nomes_de(lista) == [CP_0311])

    print("== palavras, plural, acento ==")
    lista, _ = busca.filtrar(arquivos(NOMES), u"converg\u00eancias junho 2026")
    check("'convergencias junho 2026' = as 3 de junho", sorted(nomes_de(lista)) == sorted([
        NOMES[5], NOMES[6], NOMES[7]]))
    lista, _ = busca.filtrar(arquivos(NOMES), "comite tecnico")
    check("'comite tecnico' casa CTE_ (sigla)", NOMES[5] in nomes_de(lista))
    lista, _ = busca.filtrar(arquivos(NOMES), "29/07")
    check("'29/07' casa nome com 29-07-2026 e com 29.07 sem ano", sorted(nomes_de(lista)) == sorted([NOMES[10], NOMES[13]]))
    nfd = u"Reunio\u0303es > Atas > Ata Comite\u0302 de Projetos.md"   # Unicode decomposto
    lista, _ = busca.filtrar(arquivos([nfd]), u"comit\u00ea")
    check("nome em Unicode decomposto (NFD) casa", nomes_de(lista) == [nfd])

    print("== o que NAO pode casar ==")
    check("'ata' nao casa 'plataforma'", busca.pontuar(NOMES[11], busca.montar("ata")) == 0)
    lista, _ = busca.filtrar(arquivos(NOMES), "ata")
    check("'ata' casa 'Ata Comite...'", ATA_2408 in nomes_de(lista) and NOMES[11] not in nomes_de(lista))
    lista, _ = busca.filtrar(arquivos(NOMES), "CP")
    check("'cp' nao casa 'cpf'", NOMES[14] not in nomes_de(lista))
    check("'v1.5' na consulta nao vira data",
          not [r for r in busca.montar("guia v1.5") if r["tipo"] == "data"])
    check("'03/11.' no fim da frase continua data",
          [r["data"] for r in busca.montar("reuniao de 03/11.") if r["tipo"] == "data"] == [(3, 11, None)])

    print("== parcial, vazio, consulta sem palavra ==")
    lista, modo = busca.filtrar(arquivos(NOMES), u"Comit\u00ea de Projetos 03-11 Jardins")
    check("uma palavra a mais -> modo parcial, deck ainda volta", modo == "parcial" and CP_0311 in nomes_de(lista))
    check("... com match_score", all(a.get("match_score") == "2/3" for a in lista))
    lista, modo = busca.filtrar(arquivos(NOMES), "franquia antartida")
    check("nada parecido -> vazio", modo == "vazio" and lista == [])
    lista, modo = busca.filtrar(arquivos(NOMES), "conselho junho")
    check("2 requisitos e so 1 casa -> vazio, nao 'tudo de junho'", modo == "vazio")
    pasta = u"EGP > Portf\u00f3lio de Projetos > FAZ_Cronograma_26_10_08_v9.md"
    nome = u"Reuni\u00f5es > Atas > PROJ_Acompanhamento Semanal de Portf\u00f3lio_22-09-2026.md"
    lista, _ = busca.filtrar(arquivos([pasta, nome]), u"portf\u00f3lio")
    marca = dict((a["filename"], a.get("match_in")) for a in lista)
    check("casou pelo nome -> match_in=name; so pela pasta -> folder",
          marca.get(nome) == "name" and marca.get(pasta) == "folder")
    # REGRESSAO medida em producao (08/11): com o desempate nome/pasta, "Atas"
    # punha "MUN_Ata semana passada_10-09-2026" antes das atas de 06/11.
    antiga = u"MUN > MUN_Ata semana passada_10-09-2026.md"
    recente = u"Reuni\u00f5es > Atas > PROJ_Acompanhamento Semanal de Projetos_06-11-2026_AUTO.md"
    lista, _ = busca.filtrar(arquivos([antiga, recente]), "Atas")
    ordem = nomes_de(datas.ordenar_por_data_do_nome(lista))
    check("'Atas': a de 06/11 (so na pasta) vem antes da de 10/09 (no nome)", ordem == [recente, antiga])
    corpo_src = io.open(os.path.join(RAIZ, "backend", "open_webui", "tools", "builtin.py"), encoding="utf-8").read()
    check("a ferramenta NAO reordena por nome/pasta (a ordem e so a data)",
          "f.get('match_in') == 'folder'" not in corpo_src)
    lista, modo = busca.filtrar(arquivos(NOMES), "")
    check("consulta vazia -> tudo", modo == "sem_consulta" and len(lista) == len(NOMES))
    lista, modo = busca.filtrar(arquivos(NOMES), "de")
    check("so palavra vazia -> comportamento antigo (trecho)", modo == "trecho")

    print("== siglas x Governanca (ecossistemas.json) ==")
    canon = os.path.join(os.path.dirname(RAIZ), "esteira-conhecimento", "_scripts", "ecossistemas.json")
    if not os.path.exists(canon):
        print("  (pulado: %s nao existe nesta maquina)" % canon)
    else:
        eco = json.load(io.open(canon, encoding="utf-8"))
        validos = [s for s in eco["validos"] if s != "FONTE"]
        faltam = [s for s in validos if s not in busca.SIGLAS_ECOSSISTEMAS]
        sobram = [s for s in busca.SIGLAS_ECOSSISTEMAS if s not in validos]
        check("toda sigla valida da Governanca esta na copia (faltam: %s)" % faltam, not faltam)
        check("a copia nao tem sigla fora da Governanca (sobram: %s)" % sobram, not sobram)
        divergem = [s for s in validos if s in busca.SIGLAS_ECOSSISTEMAS and not
                    busca.dobrar(eco["descricoes"][s]).startswith(busca.dobrar(busca.SIGLAS_ECOSSISTEMAS[s]))]
        check("o nome de cada sigla bate com a Governanca (divergem: %s)" % divergem, not divergem)

    print("== a ferramenta real usa o filtro ==")
    src = io.open(os.path.join(RAIZ, "backend", "open_webui", "tools", "builtin.py"), encoding="utf-8").read()
    ini = src.index("async def _nidum_arquivos_das_bases")
    fim = src.index("async def search_knowledge_files")
    check("_nidum_arquivos_das_bases nao filtra mais com ILIKE", "ilike" not in src[ini:fim])
    corpo = src[fim:src.index("\nasync def ", fim + 10)]
    check("search_knowledge_files chama filtrar()", "filtrar(candidatos, query)" in corpo)
    check("... e devolve o modo em 'match'", "'match': modo" in corpo)

    print()
    if falhas:
        print("BUSCA POR NOME: %d FALHA(S)" % len(falhas))
        return 1
    print("BUSCA POR NOME OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
