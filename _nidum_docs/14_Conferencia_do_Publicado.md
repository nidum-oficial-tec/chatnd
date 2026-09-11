# 14 — Conferência do que está publicado × o repositório

> **Desenho, 11/09/2026.** Pedido do Davi depois da varredura de cobertura (`11`), que
> apontou esta como a maior lacuna: **o coração do produto é o único objeto que ninguém
> confere.** Nada implementado ainda.

---

## O problema, em uma frase

`chatnd.py` e `gerador_de_arquivos_nidum.py` vão para produção **por API, manualmente**.
Mergear na `main` **não publica**. Logo o que está no ar pode ser qualquer versão — e
**nada compara o painel com o repositório**.

A REGRA DA DOC existe porque esse descompasso é real e já apodreceu a documentação uma
vez. Mas ela pede **disciplina humana**; não há conferência. E a Fase E torna isso
crítico, não apenas desejável: durante o corte vão **coexistir duas implementações do
mesmo produto**, e é exatamente quando *"qual versão está no ar?"* deixa de ser
curiosidade e vira a pergunta central.

---

## O que ela compara

Para cada artefato publicado por API, três coisas — e a ordem importa, porque a primeira
que diverge já responde:

| # | compara | responde |
|---|---|---|
| 1 | **existe no painel?** | publicado ou nunca publicado |
| 2 | **`version:` do docstring** painel × repo | quantas versões de atraso |
| 3 | **corpo inteiro**, normalizado | idêntico, ou divergente com o tamanho da diferença |

A versão sozinha não basta — alguém pode publicar sem subir o número. O corpo sozinho
também não: dizer "divergente" sem dizer **de quantas versões** não ajuda a decidir.

---

## De onde sai o que está publicado

Este é o detalhe que custa um dia se descoberto na hora de escrever o código, então fica
registrado:

```
FUNÇÕES (o pipe):  GET /api/v1/functions/id/{id}   -> FunctionModel, TEM `content`
TOOLS:             GET /api/v1/tools/id/{id}       -> ToolAccessResponse, NÃO tem `content`
                   GET /api/v1/tools/export        -> list[ToolModel], TEM `content`
```

**As tools não expõem o código no endpoint por id.** O caminho é o `/export`, filtrando
pelo id — e isso é uma diferença de forma entre dois objetos que parecem irmãos.

---

## Normalização, e onde ela não pode ir longe demais

Comparar bytes crus produziria divergência falsa toda vez (fim de linha, espaço no
final). Comparar demais esconderia mudança real.

**Normalizar:** `\r\n` → `\n`, espaços à direita de cada linha, linhas em branco no fim.
**Não normalizar:** indentação, ordem, comentários, espaços internos. Em Python
indentação **é** semântica, e comentário divergente é justamente o tipo de coisa que
denuncia um hotfix feito no painel.

---

## O que ela relata

Quatro estados, e **os quatro são distintos**:

- **idêntico** — silêncio.
- **divergente** — versão de cada lado, e quantas linhas diferem. **Sem imprimir o
  código**: é fonte com valve e chave dentro.
- **não publicado** — existe no repo, não no painel.
- **não conferido** — não deu para olhar. Credencial ausente, endpoint mudou, resposta
  inesperada.

O quarto estado é obrigatório e não é detalhe. A lição de 10/09 é que **uma classe que
não pôde conferir e diz "nada encontrado" é a forma mais silenciosa de um conferidor
mentir** — e o `/api/v1/models/` passou dias assim.

---

## Onde roda

Dentro do `conferir_registros.py`, como classe nova (`publicado_divergente`), no
workflow `conferir_registros.yml` — que **já tem as credenciais** e já sabe declarar
classe não conferida. Nada de workflow novo.

**Não bloqueia nada.** Relata, como as outras. Divergência entre painel e repo é um
estado **normal e esperado** entre o merge e o publish — o que não é normal é ela durar
sem ninguém saber.

---

## O que este desenho NÃO resolve

**Não diz qual lado está certo.** Painel à frente do repo pode ser hotfix legítimo não
commitado — ou alguém editando produção direto. A conferência mostra a diferença; a
leitura é humana.

**Não cobre valves.** O `conferir_registros` já tem três classes para isso, e valve muda
sem mudar código — é outro eixo.

**Não versiona o publicado.** Se a pergunta for *"o que estava no ar em 03/09?"*, isto
não responde. Responder exigiria guardar o conteúdo a cada publish, que é uma decisão
maior e não está tomada.

---

## Por que vale mais que parece

O custo é uma classe num script que já existe. O que ela compra é a única resposta que
hoje **ninguém tem**: se o que roda é o que está escrito. Todo diagnóstico do produto
parte dessa suposição — inclusive os três testes do agente, inclusive a linha de base de
20 origens (D59).

**Uma régua medida contra uma versão desconhecida é uma régua contaminada, e isso vale
para o código tanto quanto para o acervo.**

---

## Como se publica agora (11/09/2026)

O desenho deste documento nasceu para **medir** a divergência. Medida, ela expôs a
causa — e a causa não se conserta medindo melhor.

**O publish saiu da máquina de alguém.** O workflow `Publicar pipe/tools (manual)`
sobe o código direto do repositório:

- **gatilho só manual** (`workflow_dispatch`), **sem publish automático a cada merge**;
- **simulação ligada por padrão** — só publica de verdade quem desmarcar a caixinha;
- **um alvo por rodada**, sem opção *todos* — **o raio de alcance de um engano vale
  mais que dois cliques**: publicar os quatro de uma vez triplica o que uma rodada
  errada atinge, e economiza dois cliques numa operação que acontece poucas vezes
  por semana. Troca ruim;
- **carimbo de origem** no `meta.description`: sha, ref e run quando sai do Actions;
  `LOCAL, sem sha` quando sai da máquina de alguém.

**O carimbo não vai no `content`, e isto não é detalhe:** esta conferência compara o
`content` publicado com o do repo. Carimbar dentro do código faria **todo** publicado
divergir por causa do próprio carimbo, e a conferência passaria a acusar sempre — que é
como um alarme morre (D53). O `meta.description` é o único campo gravável que fica
**fora** da coisa comparada.

**O que a simulação diz antes de escrever:** versão dos dois lados, quantas linhas
realmente diferem, em qual linha começa a divergência, e o aviso explícito de que o
publish **substitui** o painel. Quando não consegue ler o publicado, ela diz isso — com
código de saída próprio (4) — em vez de calar e deixar entender "está igual".

**Uma coisa que a simulação avisa e não bloqueia:** painel e repo dizendo a **mesma
versão** com conteúdo diferente. Foi exatamente assim que a divergência de 11/09 ficou
invisível. Não bloqueia porque a primeira publicação do conserto cai justamente nesse
caso (1.65.0 × 1.65.0, 1.148 linhas) — travar ali impediria a rodada que vem consertar.
Travar o bump é trabalho do PR, onde o conserto custa uma linha (trava A). Ver
**D64**, que guarda o caso concreto — uma trava desenhada a partir de um incidente
precisa ser testada contra o **conserto** do incidente, não só contra o incidente.

Ver **D63**.

---

## Carimbo

**Última verificação: 2026-09-11.** A conferência (`conferir_publicado` no
`conferir_registros.py`) está **implementada e rodando** no workflow semanal — foi ela
que achou as 1.148 e as 543 linhas. O publish pelo Actions está implementado e
**nunca foi executado**: a primeira rodada, inclusive a simulação, é do Davi.
