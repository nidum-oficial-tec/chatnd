"""
title: Estruturar Deck (beta)
author: Nidum
version: 0.1.0
description: Produz a ESTRUTURA de um deck (ou documento) numa chamada DEDICADA ao modelo gerador, do mesmo jeito que o pipe ChatND faz na rota de arquivo. Devolve JSON pronto para o gerador_de_arquivos_nidum. Use ANTES de gerar o arquivo, sempre que o pedido for um deck/apresentacao com mais de 3 slides.
requirements:
changelog:
  0.1.0:
    - PRIMEIRA VERSAO. Move para uma tool o estagio dedicado que hoje so existe
      dentro do pipe (chatnd._gerar_arquivo -> _chamar_gerador). Desenho escrito
      ANTES do codigo em _nidum_docs/13_Desenho_estruturar_deck_beta.md.
    - O PROBLEMA QUE ELA RESOLVE, medido: o pipe faz uma chamada DEDICADA ao
      gpt-5.1 so para produzir a estrutura e entrega pronta a ferramenta; o
      agente compoe os argumentos no meio do resto do raciocinio. Pipe: 22
      slides. Agente: ~10. A diferenca e de ESTAGIO, nao de prompt.
    - O PROMPT E EXTRAIDO DO chatnd.py, nao transcrito: 6.167 chars copiados a
      mao sao 6.167 chances de divergir, e a comparacao pipe x agente so vale
      se o estagio for o MESMO.
    - RISCO CONHECIDO E NAO PROVADO ate a primeira execucao: nenhuma tool
      publicada chama generate_chat_completion. As 5 ocorrencias de
      bypass_filter=True no projeto estao TODAS no chatnd.py, que e um PIPE.
      Que uma TOOL consiga fazer o mesmo e premissa. Se falhar, falha aqui e
      cedo - e a mensagem de erro diz exatamente isso.
"""

# ASCII-only, convencao de _nidum_tools/*.py.

import json
import logging
import re

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# O PROMPT DO ESTAGIO. Extraido de chatnd.GERADOR em 21/09/2026 - se o do pipe
# mudar, este precisa ser re-extraido (o script vive no scratchpad da sessao,
# mas a regra e: NAO edite este bloco a mao, extraia de novo).
# --------------------------------------------------------------------------
GERADOR = (
    "Voce gera a ESTRUTURA de um arquivo a partir da conversa. Responda APENAS com "
    "um JSON valido, sem texto fora do JSON e sem cercas de codigo.\n"
    "REGRA ABSOLUTA: o arquivo gerado NUNCA contem secao 'Fontes', 'Fonte', "
    "'Referencias' ou 'Sources', NUNCA cita o nome de um arquivo (.txt/.pdf/.docx) e "
    "NUNCA poe referencias entre parenteses (ex.: '(MKT_Manual...txt)'). Entregue so o "
    "conteudo, como um material final. Excecao unica: se o usuario pedir as fontes.\n"
    "Formato:\n"
    "{\n"
    '  "tipo": "pptx" | "xlsx" | "docx" | "pdf" | "html",\n'
    '  "titulo": "titulo do arquivo",\n'
    '  "ecossistema": "sigla do ecossistema para a nomenclatura (ver ECOSSISTEMA abaixo)",\n'
    '  "slides": [ {"tipo":"capa|secao|conteudo|destaque|divisao|numerada|cartoes|encerramento",'
    '"titulo":"...","subtitulo":"...","texto":"...","bullets":["..."],'
    '"cor":"verde|azul|terracota|preto","itens":[{"titulo":"...","texto":"..."}],'
    '"imagem":"IMAGEM_1 (opcional)"} ],\n'
    '  "planilhas": [ {"nome":"...","cabecalhos":["..."],"linhas":[["..."]]} ],\n'
    '  "secoes": [ {"heading":"...","paragrafos":["..."],"bullets":["..."],'
    '"imagem":"IMAGEM_1 (opcional)"} ],\n'
    '  "html": "documento HTML completo (use SO quando tipo=html)"\n'
    "}\n"
    "Inclua apenas o campo de conteudo correspondente ao tipo (slides para pptx; "
    "planilhas para xlsx; secoes para docx/pdf; html para html).\n"
    "O campo \"imagem\" SO existe quando o usuario anexou imagens nesta conversa - e "
    "nesse caso as instrucoes com os marcadores disponiveis aparecem no fim deste "
    "prompt. Sem esses marcadores, NUNCA use o campo \"imagem\".\n"
    "ECOSSISTEMA (nomenclatura oficial do arquivo): escolha UMA sigla para 'ecossistema' "
    "pelo ASSUNTO do documento, NAO pela area de quem pediu. Lista fechada: FONTE "
    "(institucional/fundador), REG (regulatorio), MKT (marketing/comunicacao/marca), PROD "
    "(produto), OPS (operacoes), FIN (financeiro), JUR (juridico), ACA (academia/formacao), "
    "TEC (tecnologia), SUS (sustentabilidade), CC, CT, CE (comites). Na duvida entre duas, "
    "vale o assunto do documento. Se realmente nao souber, use \"\" (o gerador aplica um "
    "padrao) - nunca invente uma sigla fora da lista.\n"
    "IMPORTANTE: APRESENTACAO/SLIDES/DECK sempre usam o campo 'slides' (estrutura "
    "acima), nunca um HTML escrito a mao. Se o usuario quer a apresentacao em HTML, "
    "web ou navegavel, use tipo 'apresentacao' (vira um deck HTML navegavel, com "
    "passador de slides); caso contrario use tipo 'pptx'. Use tipo 'html' (campo "
    "'html', documento completo com <!DOCTYPE html> e CSS inline) APENAS para "
    "paginas, relatorios ou documentos web que NAO sejam apresentacao de slides. "
    "Para xlsx/docx/pdf, escolha conforme o pedido. Se o formato de uma apresentacao "
    "nao ficar claro, use 'pptx'. Gere conteudo completo e util.\n"
    "APRESENTACOES (pptx): VARIE os layouts para nao ficar monotono - NAO use so "
    "'conteudo'. Tipos de slide e quando usar: capa (abertura); secao (divisoria de "
    "tema, fundo colorido); conteudo (titulo + texto/bullets em fundo creme); "
    "destaque (uma frase ou conceito forte em fundo colorido cheio - defina 'cor'); "
    "divisao (titulo num bloco de cor a esquerda + texto/bullets a direita - defina "
    "'cor'); numerada (etapas/itens com numeros grandes - preencha 'itens' com "
    "{titulo,texto}); cartoes (2 a 4 cartoes coloridos lado a lado, ex.: valores ou "
    "pilares - preencha 'itens' com {titulo,texto}); encerramento (fecho). Numa "
    "apresentacao tipica, alterne os tipos (ex.: capa, conteudo, destaque, cartoes, "
    "divisao, numerada, secao, encerramento) e use 'cor' (verde|azul|terracota|preto) "
    "para diversificar os fundos coloridos entre slides vizinhos. Para pilares/"
    "valores/categorias prefira 'cartoes'; para etapas/passos prefira 'numerada'; "
    "para uma afirmacao de impacto use 'destaque'.\n"
    "CONTEUDO: baseie-se nos documentos do contexto (livros, documentos fundadores, "
    "convergencias). NAO cite nomes de arquivos, NAO escreva 'Fontes:' nem coloque "
    "referencias entre parenteses no arquivo - a menos que o usuario peca. Os arquivos "
    "iniciados por 'MKT_' (brandbook/template) sao SO identidade visual (ja aplicada "
    "pela ferramenta) - nao transforme o conteudo deles em conteudo do documento, "
    "salvo se o pedido for sobre a marca.\n"
    "JSON ROBUSTO (critico): responda com UM unico objeto JSON e NADA mais - sem "
    "prosa antes ou depois, sem cercas de codigo. O campo de conteudo do tipo "
    "escolhido NUNCA pode vir vazio: para 'pptx'/'apresentacao' o 'slides' DEVE "
    "ter ao menos 3 itens preenchidos; para docx/pdf o 'secoes'; para xlsx o "
    "'planilhas'; para html o 'html'. Escape corretamente aspas e quebras de "
    "linha dentro dos textos. Prefira BULLETS curtos a paragrafos longos - reduz "
    "erro de JSON e fica mais legivel. NAO copie blocos enormes de citacao para "
    "dentro dos slides; sintetize na sua propria voz.\n"
    "ESCOPO POR ARQUIVO: se o pedido juntar varios modulos/temas extensos, gere "
    "UM arquivo focado (o modulo ou tema principal pedido) e NAO tente espremer "
    "tudo num JSON gigante - isso quebra o arquivo. Mantenha os textos enxutos; "
    "se faltar espaco, cubra o tema principal bem feito (o usuario pode pedir os "
    "demais em seguida).\n"
    "ESTRUTURA NIDUM (triade - so quando aplicavel): se o material for sobre "
    "MOVIMENTO, RELACAO, GERACAO ou TRANSFORMACAO (ex.: como algo se realiza, "
    "se integra ou regenera), organize-o pela triade FONTE (origem e porque), "
    "FORMA (manifestacao concreta - o que e, como se estrutura) e FLUXO (o "
    "movimento - como vive e segue, sem virar 'estoque' congelado), em vez do "
    "esqueleto de treinamento corporativo (objetivos -> conteudo -> exercicios). "
    "Deixe a triade respirar (organica, sem secoes fixas obrigatorias). Para "
    "material de INVENTARIO, CATALOGO ou DEFINICAO (ex.: 'quais os ecossistemas "
    "da Nidum'), estruture de forma direta, SEM a triade."
)


def _so_json(texto):
    """Tira cercas de codigo e prosa em volta, e devolve o dict - ou None.

    Mesmo tratamento do pipe: o modelo as vezes devolve ```json ... ``` apesar
    da instrucao, e as vezes precede com uma frase.
    """
    if not isinstance(texto, str) or not texto.strip():
        return None
    t = texto.strip()
    t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
    t = re.sub(r"\s*```$", "", t).strip()
    try:
        d = json.loads(t)
        return d if isinstance(d, dict) else None
    except Exception:
        pass
    i, j = t.find("{"), t.rfind("}")
    if i >= 0 and j > i:
        try:
            d = json.loads(t[i:j + 1])
            return d if isinstance(d, dict) else None
        except Exception:
            return None
    return None


def _dados_uteis(dados):
    """True se o JSON parseou E o campo de conteudo do tipo nao esta vazio.

    Copiado de chatnd._dados_uteis: JSON valido mas com `slides: []` e o modo de
    falha real (estouro de tamanho), e ele passaria por qualquer checagem de
    sintaxe.
    """
    if not isinstance(dados, dict):
        return False
    tipo = (dados.get("tipo") or "pptx").lower()
    if tipo == "xlsx":
        return bool(dados.get("planilhas"))
    if tipo in ("docx", "pdf"):
        return bool(dados.get("secoes"))
    if tipo == "html":
        return bool((dados.get("html") or "").strip())
    if tipo == "codigo":
        return bool((dados.get("codigo") or "").strip())
    return bool(dados.get("slides"))


def _conteudo(res):
    try:
        return (res["choices"][0]["message"]["content"] or "")
    except Exception:
        return ""


def _quantos(dados):
    """Contagem content-free, para o log e para a regua."""
    if not isinstance(dados, dict):
        return 0
    for k in ("slides", "secoes", "planilhas"):
        v = dados.get(k)
        if isinstance(v, list):
            return len(v)
    return 0


class Tools:
    class Valves(BaseModel):
        GERADOR_MODEL: str = Field(
            default="gpt-5.1",
            description="Modelo do estagio dedicado. O MESMO do pipe (chatnd "
                        "GERADOR_MODEL) - comparar com modelos diferentes "
                        "mediria a diferenca de modelo, nao a de estagio.",
        )
        ATIVA: bool = Field(
            default=True,
            description="Desliga a ferramenta sem despublica-la.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def estruturar_deck(
        self,
        pedido: str,
        __request__=None,
        __user__: dict = None,
    ) -> str:
        """
        Produz a ESTRUTURA de um deck/documento numa chamada dedicada, e devolve JSON.

        Chame esta ferramenta ANTES de gerar o arquivo, sempre que o pedido for
        um deck ou apresentacao com mais de 3 slides. O JSON devolvido vai
        DIRETO para o gerador_de_arquivos_nidum: nao reescreva, nao resuma e nao
        reduza o numero de slides.

        :param pedido: O pedido do usuario, com o contexto necessario para montar o deck (tema, publico, tom, e o material que deve entrar). Quanto mais completo, melhor a estrutura.
        :return: JSON com a estrutura (titulo, tipo, slides/secoes) ou uma mensagem de erro legivel.
        """
        if not self.valves.ATIVA:
            return json.dumps({"erro": "estruturar_deck_beta esta desligada na valve."})
        if not (pedido or "").strip():
            return json.dumps({"erro": "pedido vazio."})

        # AS DUAS IMPORTACOES QUE SO EXISTEM DENTRO DO OPEN WEBUI. Ficam aqui, e
        # nao no topo, para o arquivo continuar importavel fora do servidor (e
        # para o teste offline poder carregar o modulo).
        try:
            from open_webui.utils.chat import generate_chat_completion
            from open_webui.models.users import Users
        except Exception as e:
            return json.dumps({"erro": "ambiente sem open_webui: %s" % e})

        if __request__ is None or not __user__:
            return json.dumps({
                "erro": "sem __request__/__user__ - a ferramenta nao consegue "
                        "chamar o modelo. E a PREMISSA do desenho (ver "
                        "_nidum_docs/13): que uma TOOL possa fazer o que o "
                        "PIPE faz com bypass_filter."})

        try:
            user = await Users.get_user_by_id(__user__["id"])
        except Exception as e:
            return json.dumps({"erro": "nao consegui resolver o usuario: %s" % e})

        mensagens = [{"role": "user", "content": pedido}]

        async def _chamar(sistema):
            payload = {
                "model": self.valves.GERADOR_MODEL,
                "messages": [{"role": "system", "content": sistema}] + mensagens,
                "stream": False,
            }
            res = await generate_chat_completion(
                __request__, payload, user, bypass_filter=True)
            return _so_json(_conteudo(res))

        try:
            dados = await _chamar(GERADOR)
        except Exception as e:
            # A FALHA QUE IMPORTA: se for aqui, a premissa caiu. Mensagem
            # explicita para nao ser confundida com "o modelo devolveu ruim".
            log.exception("estruturar_deck_beta: a chamada ao modelo falhou")
            return json.dumps({
                "erro": "a chamada ao modelo falhou dentro da TOOL: %s" % e,
                "significado": "se for erro de permissao/contexto, a premissa do "
                               "desenho caiu - uma tool NAO consegue chamar o "
                               "modelo como o pipe chama (bypass_filter).",
            })

        # SEGUNDA TENTATIVA, igual a do pipe: JSON invalido OU vazio (slides: []
        # por estouro de tamanho) pede reforco, nao desistencia.
        if not _dados_uteis(dados):
            log.warning("estruturar_deck_beta: estrutura vazia/invalida; reforco")
            reforco = GERADOR + (
                "\n\nATENCAO: a tentativa anterior voltou VAZIA ou invalida. "
                "Responda AGORA com UM JSON valido e COMPLETO, com o campo de "
                "conteudo (slides/secoes/planilhas/html) preenchido. Sem prosa, "
                "sem cercas. Se o conteudo for extenso, foque no tema principal "
                "e seja conciso, mas NUNCA devolva vazio.")
            try:
                dados = await _chamar(reforco)
            except Exception as e:
                return json.dumps({"erro": "reforco falhou: %s" % e})

        if not _dados_uteis(dados):
            return json.dumps({
                "erro": "o estagio nao produziu estrutura util nas duas "
                        "tentativas. Gere o deck do jeito de sempre."})

        n = _quantos(dados)
        log.info("estruturar_deck_beta: estrutura com %d item(ns), modelo=%s",
                 n, self.valves.GERADOR_MODEL)
        return json.dumps(dados, ensure_ascii=False)
