# -*- coding: ascii -*-
"""
Prova da etapa C na busca: data, tipo e projeto do metadado da esteira
(meta['nidum']) entram na busca por nome (08/11/2026).

O QUE GUARDA:
1. "cronograma" acha arquivo que a esteira classificou como cronograma, mesmo
   sem a palavra no nome; "RJ-001" acha os documentos do projeto.
2. A data do metadado ordena e casa datas SO quando o nome nao tem data; com
   data no nome, vale a do nome.
3. Sem metadado, nada muda.
4. O endpoint /nidum-meta grava so meta['nidum'] e NAO toca updated_at; e admin.
5. A busca traz File.meta do banco.

USO: py _nidum_tools/teste_metadado_busca.py
"""

import importlib.util
import io
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
    for pkg in ("open_webui", "open_webui.utils"):
        if pkg not in sys.modules:
            m = types.ModuleType(pkg)
            m.__path__ = []
            sys.modules[pkg] = m
    mods = {}
    for nome in ("nidum_datas_arquivo", "nidum_busca_nome"):
        spec = importlib.util.spec_from_file_location("open_webui.utils." + nome, os.path.join(UTILS, nome + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["open_webui.utils." + nome] = mod
        spec.loader.exec_module(mod)
        mods[nome] = mod
    return mods["nidum_datas_arquivo"], mods["nidum_busca_nome"]


def main():
    D, B = carregar()
    planilha = {"id": "1", "filename": "Projetos > Retrofits > RJ-001 Ipanema > Planilha Mestre.md", "updated_at": 5,
                "nidum": {"tipo_doc": "cronograma", "data_documento": "2026-10-30", "projeto": "RJ-001"}}
    antigo = {"id": "2", "filename": "BRA > BRA_CronogramaMVPISerraNegra_26_09_15_v1.md", "updated_at": 9,
              "nidum": {"tipo_doc": "cronograma", "data_documento": "2026-09-15"}}
    nome_com_data = {"id": "3", "filename": "X_Relatorio_01-08-2026.md", "updated_at": 1,
                     "nidum": {"tipo_doc": "documento", "data_documento": "2026-11-05"}}
    sem_meta = {"id": "4", "filename": "Manual da Marca.md", "updated_at": 1}

    print("== tipo e projeto contam como palavra ==")
    lista, _ = B.filtrar([planilha, sem_meta], "cronograma Ipanema")
    check("'cronograma Ipanema' acha a planilha classificada como cronograma", [a["id"] for a in lista] == ["1"])
    lista, _ = B.filtrar([planilha, antigo], "RJ-001")
    check("'RJ-001' acha pelo projeto do metadado", [a["id"] for a in lista] == ["1"])
    lista, _ = B.filtrar([sem_meta], "manual marca")
    check("sem metadado: nada muda", [a["id"] for a in lista] == ["4"])

    print("== data do metadado ==")
    ordem = [a["id"] for a in D.ordenar_por_data_do_nome([antigo, planilha, sem_meta])]
    check("planilha sem data no nome ordena pela data do metadado (30/10 antes de 15/09)", ordem == ["1", "2", "4"])
    item = D.ordenar_por_data_do_nome([nome_com_data])[0]
    check("com data no nome, vale a do nome (01/08), nao a do metadado", item.get("date") == "2026-08-01")
    lista, _ = B.filtrar([planilha, antigo], "cronograma outubro 2026")
    check("'cronograma outubro 2026' casa a data do metadado", [a["id"] for a in lista] == ["1"])
    lista, _ = B.filtrar([nome_com_data], "novembro 2026")
    check("data do metadado NAO passa na frente da data do nome", lista == [])

    print("== endpoint e consulta ==")
    f = io.open(os.path.join(RAIZ, "backend", "open_webui", "routers", "files.py"), encoding="utf-8").read()
    ini = f.index("async def set_nidum_meta_by_id(")
    corpo = f[ini:f.index("# Delete File By Id", ini)]
    check("endpoint e admin", "user=Depends(get_admin_user)" in corpo)
    check("grava so meta['nidum']", "meta['nidum'] = form_data.nidum" in corpo)
    check("nao toca updated_at", "updated_at" not in corpo.split('"""')[-1])
    b = io.open(os.path.join(RAIZ, "backend", "open_webui", "tools", "builtin.py"), encoding="utf-8").read()
    check("busca traz File.meta", "KnowledgeFile.knowledge_id, File.meta)" in b)

    print()
    if falhas:
        print("METADADO NA BUSCA: %d FALHA(S)" % len(falhas))
        return 1
    print("METADADO NA BUSCA OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
