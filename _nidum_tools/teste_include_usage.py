# -*- coding: ascii -*-
"""
Prova do pedido de consumo (include_usage) nas chamadas OpenAI-compat (08/11/2026).

POR QUE: o Opus via camada compativel da Anthropic chegava com usage = {} e o
custo do ChatND nao era mensuravel. O middleware ja le 'usage' do stream; faltava
PEDIR. O upstream so pede para o Azure.

O QUE GUARDA (leitura do codigo - o router nao sobe fora do Open WebUI):
1. `os` importado no modulo (sem ele, TODA chamada ao modelo quebraria com
   NameError, mesmo com a variavel desligada - py_compile nao pega isso);
2. desligado por padrao (NIDUM_INCLUDE_USAGE ausente = '0');
3. so em stream, e sem sobrescrever stream_options que ja venha no payload;
4. nenhum nome indefinido em generate_chat_completion.

USO: py _nidum_tools/teste_include_usage.py
"""

import ast
import importlib.util
import io
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
falhas = []


def check(nome, cond):
    print(("  OK   " if cond else "  FALHOU  ") + nome)
    if not cond:
        falhas.append(nome)


def main():
    caminho = os.path.join(RAIZ, "backend", "open_webui", "routers", "openai.py")
    src = io.open(caminho, encoding="utf-8").read()
    arv = ast.parse(src)
    importados = {a.asname or a.name.split(".")[0] for n in ast.walk(arv)
                  if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    check("os importado no modulo", "os" in importados)
    check("desligado por padrao", "os.environ.get('NIDUM_INCLUDE_USAGE', '0').strip() == '1'" in src)
    check("so em stream", "and payload.get('stream')" in src)
    check("nao sobrescreve stream_options existente", "and 'stream_options' not in payload" in src)
    check("pede include_usage", "payload['stream_options'] = {'include_usage': True}" in src)

    spec = importlib.util.spec_from_file_location("te", os.path.join(RAIZ, "_nidum_tools", "teste_estrutura.py"))
    te = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(te)
    except SystemExit:
        pass
    check("nenhum nome indefinido em generate_chat_completion",
          te.nomes_indefinidos(src, "generate_chat_completion") == set())

    print()
    if falhas:
        print("INCLUDE USAGE: %d FALHA(S)" % len(falhas))
        return 1
    print("INCLUDE USAGE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
