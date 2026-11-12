# -*- coding: utf-8 -*-
"""
Prova do BRAND BOOK V2 (novembro de 2026) no gerador de arquivos.

O QUE O TESTE GUARDA - as regras do v2 que mudam o arquivo gerado, conferidas no
ARQUIVO (bytes que saem), nao no codigo-fonte:

1. Fundo BRANCO. Areia so em secao suave (code/pre), nunca no body ou no slide.
2. Sem bloco de cor chapada: nenhum slide de PPTX com fundo colorido, nenhuma forma
   retangular cheia de cor, nenhum cabecalho de tabela pintado (HTML/XLSX/PDF).
3. Sem sombra e sem transparencia das cores (rgba/box-shadow) no CSS da marca.
4. Slogan v2 "Do imovel que existe ao ninho." no lugar de "fazer da casa um ninho."
5. UMA cor de acento por peca, escolhida pelo produto; logo na cor do produto.
6. Titulos em iBrand com espacamento FECHADO (HTML, PPTX e DOCX).
7. Botoes em minusculas com verbo.

Monta os arquivos chamando os metodos privados com o upload trocado por um duble,
igual as outras suites (sem subir o Open WebUI).

USO: python _nidum_tools/teste_marca_v2.py
"""

import asyncio
import io
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gerador_de_arquivos_nidum as G  # noqa: E402

falhas = []
CAPTURA = {}


def check(nome, cond):
    print(("  OK   " if cond else "  FALHOU  ") + nome)
    if not cond:
        falhas.append(nome)


async def _falso_salvar(data, nome, ct, uid):
    CAPTURA["ultimo"] = data
    return "[ok](/x)"


G._salvar_e_linkar = _falso_salvar

# Fora do container nao ha o pacote open_webui: aponta a pasta de marca (logos e
# fontes) para a copia do repo, para a logo e a fonte entrarem no arquivo testado.
_BRAND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "backend", "open_webui", "static", "brand")
if os.path.isdir(_BRAND):
    G._brand_dir = lambda: _BRAND

# ASCII-only: o "o" com acento entra por chr(0xF3).
SLOGAN_V2 = "Do im" + chr(0xF3) + "vel que existe ao ninho."

SLIDES = [
    {"tipo": "capa", "titulo": "Teste v2", "subtitulo": "marca"},
    {"tipo": "secao", "titulo": "Secao", "subtitulo": "parte 1", "cor": "verde"},
    {"tipo": "conteudo", "titulo": "Conteudo", "texto": "corpo", "bullets": ["a", "b"]},
    {"tipo": "destaque", "titulo": "Frase", "texto": "apoio", "cor": "terracota"},
    {"tipo": "divisao", "titulo": "Div", "texto": "direita", "cor": "azul"},
    {"tipo": "numerada", "titulo": "Passos",
     "itens": [{"titulo": "um", "texto": "x"}, {"titulo": "dois", "texto": "y"}]},
    {"tipo": "cartoes", "titulo": "Pilares",
     "itens": [{"titulo": "p1", "texto": "t1"}, {"titulo": "p2", "texto": "t2"}]},
    {"tipo": "encerramento"},
]
SECOES = [{"heading": "Parte", "paragrafos": ["texto"], "bullets": ["item"],
           "tabela": [["col a", "col b"], ["1", "2"]]}]
SLOGAN_V1 = "fazer da casa um ninho"


def _streams_pdf(pdf):
    # Junta o conteudo de todos os streams do PDF, decodificando ASCII85 + Flate
    # (o padrao do reportlab). Stream que nao decodifica e ignorado.
    import base64
    import zlib
    out = b""
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        raw = m.group(1).strip()
        if raw.endswith(b"~>"):
            raw = raw[:-2]
        try:
            out += zlib.decompress(base64.a85decode(raw))
        except Exception:
            pass
    return out


def rodar(coro):
    CAPTURA.pop("ultimo", None)
    asyncio.run(coro)
    return CAPTURA.get("ultimo", b"")


def main():
    T = G.Tools()

    print("== acento por produto ==")
    check("sem produto -> terracota + logo escuro",
          G._acento_da_peca("")[1:] == ("9A4A2E", "escuro"))
    check("'Casas Vivas' -> musgo + logo musgo",
          G._acento_da_peca("Casas Vivas")[1:] == ("515E52", "verde"))
    check("'nidum mundo' -> ceu", G._acento_da_peca("nidum mundo")[1] == "4F7187")
    check("'Prumo' -> azul prumo 174E78", G._acento_da_peca("Prumo")[1] == "174E78")
    check("produto desconhecido nao derruba (cai no padrao)",
          G._acento_da_peca("xyz")[0] == "padrao")
    check("slogan v2 com acento", G.NIDUM_SLOGAN == SLOGAN_V2)

    print("\n== HTML (gerar_html) ==")
    html = rodar(T.gerar_html("t", "<h1>Oi</h1><p>x</p>", produto="nidum mundo"))
    h = html.decode("utf-8")
    m_body = re.search(r"body\{background:#([0-9A-Fa-f]{6})", h)
    check("body branco", bool(m_body) and m_body.group(1).upper() == "FFFFFF")
    marca_css = h[h.find("/*NIDUM_BRAND*/"):h.find("</style>", h.find("/*NIDUM_BRAND*/"))]
    marca_css = re.sub(r"@font-face\{[^}]*\}", "", marca_css)
    check("CSS da marca sem rgba()", "rgba(" not in marca_css)
    check("CSS da marca sem sombra", "box-shadow:0" not in marca_css)
    check("th sem fundo chapado", not re.search(r"th\{[^}]*background", marca_css))
    check("h1 com espacamento fechado -.022em", "letter-spacing:-.022em" in marca_css)
    check("acento = ceu (nidum mundo)", "--acento:#4F7187" in h)
    check("slogan v2 no rodape", "Do im&oacute;vel que existe ao ninho." in h)
    check("sem o slogan v1", SLOGAN_V1 not in h.lower())
    check("botoes em minusculas", ">editar</button>" in h and ">salvar html</button>" in h)

    print("\n== deck HTML (gerar_apresentacao_html) ==")
    deck = rodar(T.gerar_apresentacao_html("d", SLIDES, produto="casas vivas")).decode("utf-8")
    m_sl = re.search(r"\.slide\{[^}]*background:#([0-9A-Fa-f]{6})", deck)
    check("slide branco", bool(m_sl) and m_sl.group(1).upper() == "FFFFFF")
    check("nenhum slide com background inline (bloco de cor)",
          "class='slide" not in deck or "style='background" not in deck)
    check("acento = musgo (casas vivas)", "--acento:#515E52" in deck)
    check("encerramento sem titulo usa o slogan v2",
          SLOGAN_V2 in deck)
    deck_css = re.sub(r"@font-face\{[^}]*\}", "", deck)
    check("deck sem rgba()/blur", "rgba(" not in deck_css and "blur(" not in deck_css)

    print("\n== PPTX ==")
    pptx = rodar(T.gerar_pptx("p", SLIDES, produto="nidum prumo"))
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    prs = Presentation(io.BytesIO(pptx))
    fundos = set()
    blocos = 0
    for sl in prs.slides:
        f = sl.background.fill
        try:
            fundos.add(str(f.fore_color.rgb))
        except Exception:
            fundos.add("?")
        for shp in sl.shapes:
            if shp.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
                # So o PONTO (oval pequeno) pode ser cheio de cor.
                if shp.width > 300000 and shp.fill.type == 1:
                    blocos += 1
    check("todos os slides com fundo branco: %s" % sorted(fundos), fundos == {"FFFFFF"})
    check("nenhuma forma grande cheia de cor (bloco/cartao)", blocos == 0)
    xml = b"".join(zipfile.ZipFile(io.BytesIO(pptx)).read(n)
                   for n in zipfile.ZipFile(io.BytesIO(pptx)).namelist()
                   if n.startswith("ppt/slides/slide"))
    check("titulos com spc negativo (iBrand fechada)", b'spc="-' in xml)
    check("acento azul prumo presente", b"174E78" in xml)
    check("encerramento usa o slogan v2",
          SLOGAN_V2.encode("utf-8") in xml)
    check("sem cor de bloco v1 (musgo/ceu) num slide prumo",
          b"515E52" not in xml and b"4F7187" not in xml)

    print("\n== DOCX ==")
    docx = rodar(T.gerar_docx("d", SECOES, produto=""))
    z = zipfile.ZipFile(io.BytesIO(docx))
    styles = z.read("word/styles.xml").decode("utf-8")
    footer = "".join(z.read(n).decode("utf-8") for n in z.namelist()
                     if n.startswith("word/footer"))
    m_title = re.search(r'w:styleId="Title".*?</w:style>', styles, re.S)
    t = m_title.group(0) if m_title else ""
    check("Title condensado (w:spacing negativo)", re.search(r'w:spacing w:val="-\d+"', t))
    check("Title sem a borda azul do modelo padrao", "w:pBdr" not in t)
    check("Title escuro", 'w:val="1F1E1B"' in t)
    rpr = re.search(r"<w:rPr>.*?</w:rPr>", t, re.S)
    ordem_ok = True
    if rpr:
        r = rpr.group(0)
        if "<w:sz " in r and "w:spacing" in r:
            ordem_ok = r.find("w:spacing") < r.find("<w:sz ")
    check("w:spacing antes de w:sz (ordem do schema do Word)", ordem_ok)
    check("rodape com o slogan v2", SLOGAN_V2 in footer)

    print("\n== XLSX ==")
    xlsx = rodar(T.gerar_xlsx("x", [{"nome": "aba", "cabecalhos": ["a", "b"],
                                     "linhas": [["1", "2"], ["3", "4"]]}],
                              produto="casas vivas"))
    from openpyxl import load_workbook
    ws = load_workbook(io.BytesIO(xlsx)).active
    fills = {ws.cell(row=rr, column=1).fill.fgColor.rgb for rr in range(2, 5)
             if ws.cell(row=rr, column=1).fill.fill_type}
    check("nenhuma celula pintada (sem cabecalho chapado, sem zebra)", not fills)
    check("aba na cor do produto (musgo)", str(ws.sheet_properties.tabColor.rgb).endswith("515E52"))

    print("\n== PDF ==")
    pdf = rodar(T.gerar_pdf("p", SECOES))
    check("PDF gerado", pdf.startswith(b"%PDF"))
    # O fundo areia antigo era um retangulo cheio do tamanho da pagina na cor E5E0D5
    # (".898039 .878431 .835294 rg"). O reportlab grava os streams em ASCII85 +
    # Flate: procurar no PDF cru NUNCA acharia nada (conferido: a checagem crua
    # passava ate na versao 2.8.2, que pinta areia). Por isso decodifica antes.
    conteudo = _streams_pdf(pdf)
    check("streams do PDF decodificados", len(conteudo) > 0)
    check("sem fundo areia pintado", b".898039 .878431 .835294 rg" not in conteudo)
    check("sem musgo nos titulos (v1)", b".317647 .368627 .321569 rg" not in conteudo)

    print("")
    if falhas:
        print("MARCA V2: %d FALHA(S)" % len(falhas))
        return 1
    print("MARCA V2 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
