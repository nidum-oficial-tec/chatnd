# ChatND / Plataforma Nidum — instrucoes do projeto

Fork do Open WebUI 0.9.6 com o "motor invisivel" ChatND (pipe roteador) e a tool
de geracao de arquivos. Codigo Nidum vive em `_nidum_tools/`, docs em
`_nidum_docs/`, scripts de manutencao em `_nidum_manutencao/`.

## Mapa do repositorio (scripts principais)

Versoes vivem no docstring do arquivo e no PAINEL (pipe/tool sao publicados por API,
nao por deploy) - nao repito numero aqui para nao apodrecer. O que ESTA no ar se le no
painel; ver a REGRA DA DOC.

- `_nidum_tools/chatnd.py` - o PIPE roteador "ChatND" (classe `Pipe`). Coracao da
  esteira: classifica o pedido, roteia para 4 rotas (geral / documentos / arquivo /
  imagem), faz RAG na documentos, chama a tool na arquivo, gera imagem na imagem.
- `_nidum_tools/gerador_de_arquivos_nidum.py` - a TOOL de geracao de arquivos
  (pptx/docx/xlsx/pdf/html/codigo). Anexada ao wrapper da rota geral.
- `_nidum_tools/relatorio_ambientes_nidum.py`, `sharepoint_nidum.py` - tools do
  "Identificador De Ambientes" (frente separada do roteador).
- `_nidum_tools/teste_*.py` - banco de provas OFFLINE do pipe/tool (rodam sem subir o
  OWUI). `teste_estrutura.py` = helpers AST (ex.: `nomes_indefinidos`). Ha suites de
  travas, datas, anexo, imagens, codigo, analytics, voz, token.
- `_nidum_manutencao/` - scripts de publicacao/manutencao (ex.: `publicar_tool.py`).
- `_nidum_docs/` - doc viva (03 arquitetura, 04 dicionario, 07 diario, 08 decisoes...).
- `backend/`, `editorial/`, `Dockerfile` - o fork OWUI; vai por git push -> Railway.

## Decisoes firmadas da esteira (e o que foi DESCARTADO)

FIRMADO (nao reabrir sem motivo novo):
- 4 rotas: geral / documentos / arquivo / imagem. Mudar as CATEGORIAS do roteador
  afeta o "Chico" (motor de outro colaborador que usa o `chatnd` como base model).
- RAG so na documentos; web so na geral. Documentos e geral NUNCA se cruzam (governanca:
  "isto e da Nidum?" decide qual, e so uma toca cada fonte).
- Modelos: geral/documentos = Claude Sonnet (via camada OpenAI-compat da Anthropic);
  classificador = gpt-5-mini (OpenAI); gerador = gpt-5.1 (OpenAI); embeddings =
  text-embedding-3-small (OpenAI). Uma chave por provedor, comingled com o Chico.
- Rota de CONVERSA retorna um StreamingResponse (`_resposta_ou_aviso` ->
  `_stream_resiliente`); o pipe NAO remonta o texto final, repassa o stream. Rotas
  arquivo/imagem retornam string.
- Prioridade absoluta do pipe (o changelog institucionaliza): STREAM INTOCADO,
  best-effort, a resposta NUNCA degrada por observabilidade ou feature nova.
- Analytics content-free (SQLite, best-effort, admin-only). Medicao de token (2a)
  mergeada; trim do acervo so DEPOIS do mapa medido.

DESCARTADO (com o motivo - nao repetir a tentativa):
- gpt-5-mini na rota geral: inventava consultoria (SPE x SCP) com confianca; geral e
  Sonnet, medido.
- Tool-calling para features novas: QUEBRA nos modelos Claude (camada OpenAI-compat:
  `'str' object has no attribute 'get'`); o pipe nem declara `__tools__`.
- Catch-all do classificador ("geral = tudo que nao e Nidum"): decisao por eliminacao
  sobre um vocabulario que o modelo nao conhece; lista fechada e mais honesta.
- Cache de prompt Anthropic: bloqueado por infra (OWUI fala OpenAI-compat, `cache_control`
  vira no-op); exige proxy (LiteLLM) ou backend. Frente futura, nao "botao".
- nidum-voz / OpenAI STT para voz-entrada: Whisper local basta (transcreveu pt 0.997).
- `ENABLE_WEB_SEARCH=True`: reabriria o caminho pre-pipe que contamina pergunta
  institucional com a web. Fica False DE PROPOSITO; o pipe busca pela camada de baixo.

## Documentacao continua (obrigatorio)

Este projeto mantem documentacao viva em `_nidum_docs/`:
- `_nidum_docs/Documentacao_ChatND_Nidum.html` — doc tecnica do pipe ChatND e da
  tool gerador_de_arquivos_nidum (diagnostico, mudancas por versao, infra).
- `_nidum_docs/07_Diario_e_Status.md` — status geral vivo do projeto.
- `_nidum_docs/00_LEIA-ME.md` ... `09_Dominio_Nidum.md` — o pacote estruturante.

### REGRA DA DOC (a mais importante desta secao)

**Doc que descreve PRODUCAO mergeia junto com o DEPLOY - nunca antes.**

POR QUE ISTO E REGRA E NAO CONSELHO: e a CAUSA RAIZ do apodrecimento dos _nidum_docs/.
Em 16/07/2026 o 03_Arquitetura_e_Motor.md errava TODOS os fatos estruturais - apontava
para um arquivo inexistente (chatnd_router.py), uma versao 18 numeros atras (1.10.0 vs
1.28.0), uma colecao aposentada e um modo de RAG desligado havia semanas. Ele nao nasceu
errado: APODRECEU, e ninguem notou porque nada obrigava a conferir.

A PROVA de que e estrutural e nao falta de disciplina: a doc 03 foi REESCRITA DO ZERO em
16/07 para consertar exatamente isso - e APODRECEU ANTES DE MERGEAR. Descrevia 6 rotas; a
fatia 1 fez 4, no mesmo dia. Uma doc escrita para consertar apodrecimento apodreceu em
horas.

A CAUSA - e ela estava ESCRITA AQUI, como obrigacao. A regra anterior dizia, literalmente:

    "Atualize Documentacao_ChatND_Nidum.html na MESMA sessao da alteracao."

O defeito: "alteracao" NAO e "deploy". Aqui pipe/tools vao por API, MANUALMENTE - mergear
na main NAO publica. Entao a doc atualizada "na mesma sessao da alteracao" fica CERTA
sobre algo que ainda NAO EXISTE e ERRADA sobre o que esta no ar. Ela documentava o commit;
o leitor precisa do que ESTA RODANDO.

    O PROBLEMA NAO ERA NINGUEM SEGUIR A REGRA. ERA SEGUI-LA.

Isso importa para quem for mexer aqui: nao adianta pedir "mais disciplina com as docs". A
disciplina existia e a regra era obrigatoria - e o resultado foi uma doc que errava TODOS
os fatos estruturais. Instrucao errada nao se corrige com esforco; corrige-se trocando a
instrucao.

NA PRATICA:
  - Doc de PRODUCAO (03_Arquitetura, 04_Dicionario, Documentacao_ChatND_Nidum.html):
    o PR mergeia QUANDO O PUBLISH ACONTECE, nao quando o codigo entra na main.
  - Se precisar mergear antes: aviso no TOPO dizendo QUAL versao ela descreve e que pode
    nao estar publicada. O aviso SAI no publish.
  - Carimbo "Ultima verificacao: <data>" no topo. Nao impede o apodrecimento - deixa ele
    VISIVEL, que e o que a doc antiga nao tinha.
  - Doc de DECISAO (07_Diario, 08_Decisoes): mergeia quando a decisao e tomada. Decisao
    nao espera deploy - ela E o registro de que se decidiu.
  - NA DUVIDA, pergunte: "isto fica FALSO se o publish nao acontecer?" Se sim, e doc de
    producao: espera o deploy.

---

Sempre que alterar o pipe ChatND, a tool gerador_de_arquivos_nidum, ou qualquer
configuracao de infraestrutura (env vars, storage, banco):

1. Atualize `Documentacao_ChatND_Nidum.html` na mesma sessao da alteracao - MAS
   respeitando a REGRA DA DOC acima: ela descreve producao, entao o MERGE espera o
   publish (ou leva o aviso no topo).
2. Registre na secao "Historico de alteracoes": data, componente, versao, O QUE
   mudou, POR QUE mudou e COMO VALIDAR (um teste concreto).
3. Se a mudanca criar/alterar valves ou variaveis de ambiente, atualize tambem as
   secoes 3, 4 ou 5 conforme o caso.
4. Linguagem objetiva e didatica, em portugues. Sem jargao desnecessario: o
   leitor pode nao ser tecnico.
5. NUNCA apague o historico - acrescente a nova linha no TOPO da tabela.
6. Ao subir a versao de um arquivo, atualize o numero de versao no docstring do
   arquivo E na secao 1 desta documentacao.
7. Atualize tambem `_nidum_docs/07_Diario_e_Status.md` a cada sessao relevante
   (acrescentando, nunca apagando o historico).

## REGRA DO REBASE: padrao que funcionou tres vezes e o que voce para de checar

**Ao resolver conflito de rebase: leia o RESULTADO, nao so o diff. E nunca aplique "como
das outras vezes" sem conferir se vale desta vez.**

POR QUE (quase publicado em 17/07/2026):

Nos rebases das fatias A, B e C, o conflito era sempre no mesmo lugar - o `version:` e o
changelog - e a resolucao era sempre a mesma: manter os dois blocos, mais novo no topo,
e remover um cabecalho "  1.3X.0:" ORFAO que sobrava (ele ficava ANTES do marcador de
conflito, entao entrava nas linhas de cima).

Tres vezes seguidas o mesmo padrao. Na quarta, o cabecalho NAO era orfao - era o dono do
bloco dos TERMOS CANONICOS (1.34.0), que tinha acabado de ser publicado e provado.
Removi por reflexo. Resultado: o conteudo da 1.34.0 ficou sob o rotulo 1.35.0, e a 1.34.0
SUMIU do changelog.

    PY_COMPILE PASSAVA. OS TESTES PASSAVAM. O CHANGELOG MENTIA.

    TESTE NAO PEGA DOCUMENTACAO.

Nada na suite ia denunciar. O que pegou foi IMPRIMIR os cabecalhos e LER - um comando de
tres segundos. Se tivesse mergeado, o changelog atribuiria o conserto da Q12 a versao
errada, e a 1.34.0 - a unica que consertou de verdade - nao existiria no registro.

O QUE FAZER:
  - Depois de resolver, IMPRIMA o resultado e leia. Nao confie no "sem conflitos".
  - Para changelog/doc, confira BLOCO A BLOCO por CONTEUDO: cada versao tem o texto que
    e dela? (`grep` do marcador de cada bloco resolve.)
  - Se voce se pegar pensando "e igual as outras vezes", esse e o momento de conferir -
    nao de acelerar. O padrao que funcionou tres vezes e o que voce para de olhar.

## REGRA DO CLASSIFICADOR: teoria sobre prompt e HIPOTESE, nao diagnostico

**Ao mexer no prompt do CLASSIFICADOR para consertar um roteamento errado: voce esta
formulando uma HIPOTESE. Trate como hipotese - teste antes de dizer que consertou, e
antes de escrever "conserta X" em changelog.**

POR QUE ISTO E REGRA (aprendido errando tres vezes, 16-17/07/2026):

Explicar o comportamento de um LLM com uma teoria sobre o TEXTO do prompt e sedutor: a
teoria e sempre elegante, sempre plausivel, e voce nunca consegue perguntar ao modelo se
ela esta certa. O placar real deste projeto:

  1. "a expansao de datas envenena o reranker"        -> REFUTADA por teste
  2. "o catch-all do 'geral' quebrou a Q12"           -> REFUTADA por teste
  3. "a poluicao vem do historico (3 mensagens)"      -> confirmada, e por OUTRO
                                                         mecanismo, nao pelo que eu previa

Duas de tres teorias sobre prompt/recuperacao, refutadas. E a #2 foi escrita como REGRA
neste arquivo, com caso concreto e tudo, ANTES de ser testada - e o changelog da 1.33.0
dizia "CONSERTA A REGRESSAO DA Q12". Nao consertava.

COMO A #2 MORREU - o metodo que vale mais que a regra: Davi pediu os dois prompts LADO A
LADO (1.26.0, quando funcionava; 1.33.0, quando falhava). A comparacao mostrou que o
'diaadia' da 1.26.0 JA CONTINHA "conversa geral" e "organizacao de ideias". Se a pergunta
casasse com isso, teria ido para 'diaadia' na 1.26.0 tambem. NAO FOI. A teoria do "ficar
sem caixa" nunca explicou nada - a caixa existia desde sempre.

A CAUSA REAL, e ela e simples: o gpt-5-mini NAO SABE que "fazer da casa um ninho" e frase
do Documento Fundador. Para ele e metafora comum em portugues.

    NENHUMA REDACAO DE PROMPT CONSERTA DESCONHECIMENTO. SO INFORMACAO CONSERTA.

Por isso a solucao nao foi redigir melhor: foi DAR A INFORMACAO (valve TERMOS_CANONICOS,
1.34.0) - no prompt, para o juiz aprender, e numa TRAVA deterministica, para funcionar
quando ele erra mesmo assim.

O QUE FAZER NA PRATICA, quando o roteamento errar:
  - Primeiro o LOG: 'classificador=<saida>' diz se o juiz DECIDIU, se o parse nao casou
    (o laco nao tem else - fica o valor inicial, calado) ou se houve excecao. Sao tres
    bugs diferentes com o mesmo sintoma.
  - Depois pergunte: "o modelo SABE o que precisa saber para acertar?" Se a resposta for
    nao, redigir melhor nao vai ajudar - falta informacao, nao clareza.
  - So entao teorize sobre o texto. E rode a pergunta ANTES e DEPOIS. Sem o depois, voce
    nao consertou: voce escreveu.
  - E NAO escreva "conserta X" em changelog antes de ter o depois. Changelog errado nao e
    imprecisao - e pista falsa para o proximo, que vai procurar o bug em outro lugar.

SOBRE O CATCH-ALL, o que sobrou: nao ha prova de que ele causa o problema, mas ha razao
para nao usar. "geral: TUDO que NAO e sobre a Nidum" faz o juiz decidir por eliminacao,
com base no que ELE reconhece como sendo da Nidum - e ele nao conhece o vocabulario da
casa. LISTA FECHADA e mais honesta: descreve o que a categoria E. Isso e higiene, nao
conserto - a 1.33.0 fez, e nao mudou nada.

## Regras invioaveis do codigo

- `_nidum_tools/*.py` (pipe e tool): APENAS ASCII (sem bullets unicode, travessoes
  ou emojis). Validar com `python -m py_compile`.
- **Nunca revelar qual LLM/provedor esta por tras - NO TEXTO DAS RESPOSTAS.** O
  ChatND nao diz "eu sou o Claude" quando perguntam, nao cita o provedor, e nao
  deixa o nome do modelo aparecer em nenhuma saida que o usuario le: resposta,
  arquivo gerado, mensagem de erro, log mostrado na tela.
  **O escopo E O TEXTO, e nao o payload das APIs internas.** `/api/models` devolve
  `info.base_model_id` e `owned_by` para qualquer usuario autenticado, e isso
  vale HOJE, com os wrappers - conferido em producao em 11/09/2026 pelo devtools.
  **Foi examinado e decidido que NAO e problema** (D61): vaza o MODELO, nunca a
  chave, e todo mundo com conta e de dentro.
  **Por que o escopo esta escrito, e nao subentendido:** a frase antiga cobria
  duas coisas diferentes - a experiencia do produto e a superficie tecnica - e,
  lida ao pe da letra, transformava um fato conhecido em violacao permanente.
  Regra que nao diz onde comeca e onde termina vira alarme falso ou licenca,
  conforme quem le.
- Nunca expor chaves/segredos no chat, log ou commit.
- Pipe/tool sao publicados via API do Open WebUI (`/api/v1/functions/id/chatnd/update`
  e `/api/v1/tools/id/gerador_de_arquivos_nidum/update`), nao por deploy de repo.
  Ao atualizar SO a tool, republicar tambem o pipe (reseta o cache da tool).
- Backend (editorial, branding, Dockerfile) vai por git push -> Railway (downtime).
