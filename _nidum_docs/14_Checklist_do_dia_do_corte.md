# Checklist do dia do corte — o agente substitui o pipe

> **21/09/2026 — ENSAIADO.** Adiado três vezes por ser "se sobrar tempo"; passou
> a ter lugar fixo na fila por decisão do Davi, exatamente por isso. Os itens 1 e
> 2 (conversa aberta e reversão) foram **executados em produção** em 21/09, com
> autorização, e os números abaixo são medidos.
>
> **Contexto que simplificou tudo:** ninguém está usando o ChatND hoje. Sem
> conversas abertas não há o que escoar, e o corte pelo `is_active` — o mais
> barato, um comando — basta.
>
> **O corte não tem passo intermediário:** o agente substitui o pipe para todo mundo de uma vez.
> Então o corte **é** o primeiro teste com uso real, e o checklist existe para que o primeiro dia
> não seja também o primeiro diagnóstico.

---

## O estado de hoje, medido

`/api/models` (o que o seletor mostra) devolve **12 entradas**:

```
chatnd                          <- o PIPE (function), id e nome iguais
chatnd-agente-beta              <- o AGENTE (preset sobre claude-sonnet-4-6)
chico-m1                        Chico
nidum-identificador-ambientes   NIDUM 1.0 - Identificador de Ambientes
nidum-10---documentos           Nidum 1.0 - Documentos
nidum-10---dia-a-dia            Nidum 1.0 - Geral
gpt-5-mini · gpt-5.1 · claude-sonnet-4-6 · claude-opus-4-8 · claude-haiku-4-5 · arena-model
```

Os cinco últimos são **modelos crus** — aparecem no seletor e não deveriam ser escolha de
ninguém. Não é criado pelo corte, mas o corte é a hora de olhar.

---

## Pré-requisitos (antes do dia)

| # | o quê | por quê | estado |
|---|---|---|---|
| 1 | **Republicar a `estruturar_deck_beta` pela workflow, com sha** | hoje o carimbo é `[origem: LOCAL — sem sha, não rastreável ao repo]`. Aceito enquanto beta; **não** aceito quando virar produto. **Destravado em 21/09:** a workflow recusava o alvo — `type: choice` com lista fechada, e `estruturar_deck_beta` não estava nela. O `case` já tinha ramo genérico, então faltava só a linha. **O publish local só foi possível porque a workflow não aceitava o alvo** | ✅ **FEITO em 21/09**: `[origem: repo df8023dda15b ref medicao/fase2-consertos run 35644727299]`. A guarda de branch **não bloqueia** publicar de fora da `main` — ela avisa no sumário e carimba a ref. Fica pendente republicar **da main** depois do merge |
| 2 | ~~Fechar a régua do deck~~ · **RESOLVIDO em 21/09** | as 5 do pipe rodadas com o mesmo pedido: mediana **41** slides, **277** chars/slide. Agente: **32** e **281**. Os dois decks lidos pelo Davi — **conteúdo equivalente**. Ver [D91](08_Decisoes_e_Pendencias.md) | ✅ |
| 3 | ~~Confirmar o que o Chico usa como base~~ · **RESOLVIDO em 21/09** | **o Chico está aposentado e sai junto no corte** (Davi). A pergunta era se o corte atingiria outro colaborador; não atinge, porque o motor dele deixa de existir na mesma operação. O `CLAUDE.md` ainda afirma que ele usa o `chatnd` como base model — **está desatualizado** (a instância diz `claude-sonnet-4-6`) e a linha sai no corte, junto com o resto | ✅ |
| 4 | **A contagem de uso entra JUNTO com o corte** · decidido em 21/09 | não depois: quando o agente substituir o pipe, ele já precisa contar. Mínimo acordado: **pessoas, perguntas, vazias/erro/truncadas**, na mesma tabela `eventos`, com coluna **`origem`** separando `pipe` de `agente`. "Truncada" pela heurística do [D85](08_Decisoes_e_Pendencias.md). **Meio dia, backend — vai por deploy** | ⬜ implementar |

> **Com o 2 e o 3 fechados em 21/09, nenhum pré-requisito adia o corte.** O 1 é uma execução da workflow; o 4 é uma decisão que pode ser tomada depois, aceitando a dívida — desde que aceitá-la seja escolha, e não esquecimento.

---

## 1. O seletor, e como o agente assume o nome `chatnd`

O `chatnd` de hoje é uma **function** (pipe); o agente é um **preset**. São objetos de tipos
diferentes no mesmo seletor, e é isso que torna a troca menos trivial do que "renomear".

**Três caminhos, e eles não são equivalentes:**

| caminho | o que faz | o que quebra |
|---|---|---|
| **A — renomear o preset para "chatnd"** | o agente aparece com o nome certo | ficam **dois** `chatnd` no seletor enquanto a function existir; e o **id** do preset continua `chatnd-agente-beta`, então conversa nova nasce com o id antigo |
| **B — desativar a function e renomear o preset** | um `chatnd` só | conversa **aberta** no pipe aponta para um id que sumiu (ver §2) |
| **C — trocar o id do preset para `chatnd`** | id e nome certos | colide com a function enquanto ela existir; e **id de preset não se troca** pela API sem recriar, o que perde o histórico de acesso |

**DECIDIDO: caminho B, pelo `is_active`** (Davi, 21/09). Com zero conversas abertas não há o
que escoar, e é o caminho mais barato — um comando, reversão em 2,4 s.

✅ **Medido no ensaio:** `is_active: false` **some do seletor sem apagar a function**. O seletor
foi de 12 para 11 entradas e o `chatnd` sumiu:

```
SELETOR no corte: 11 entradas | 'chatnd' presente: False
['gpt-5-mini', 'gpt-5.1', 'claude-sonnet-4-6', 'claude-opus-4-8', 'claude-haiku-4-5',
 'arena-model', 'chico-m1', 'nidum-identificador-ambientes', 'nidum-10---documentos',
 'nidum-10---dia-a-dia', 'chatnd-agente-beta']
```

⏱️ **CORTE: 1,9 s** (desativar a function + renomear o preset).

---

## 2. Quem estiver numa conversa aberta no pipe

**O que se sabe:** cada chat guarda o modelo em `chat.models` — medido: dos 11 chats da primeira
página, 10 apontam para `chatnd-agente-beta` e 1 para `nidum-10---documentos`. O id fica
**gravado no chat**, não é resolvido na hora.

**O que isso implica, e é a parte que precisa de teste, não de raciocínio:** uma conversa
gravada com `models: ["chatnd"]` continuará pedindo `chatnd` depois do corte. Se a function
estiver desativada, a próxima mensagem naquela conversa vai para um modelo que não existe mais.

✅ **TESTADO em 21/09 — e nenhuma das três hipóteses estava certa.**

Eu previa erro, silêncio ou queda para o modelo padrão. **Aconteceu uma quarta: continuou
funcionando.** Com a function desativada, a conversa antiga foi atendida **pelo pipe**:

```
3. CONVERSA ABERTA (a mesma do passo 1, que aponta para 'chatnd')
   ok=True  49s
   -> [Acervos]  A Nidum identifica casas com potencial ainda nao explorado...
```

O marcador `[Acervos]` só o pipe emite. **`is_active=False` tira do seletor, mas não impede a
execução de quem pede a function pelo id.**

**O que isso muda, e não é detalhe:** o corte pelo `is_active` **não é "todo mundo de uma vez"**.
Conversa nova nasce com o agente; conversa aberta segue no pipe. É **migração suave**, não corte.

Hoje isso não custa nada — não há conversas abertas. Mas **é por isso que o pipe precisa de data
de remoção** (abaixo): sem ela, uma conversa esquecida mantém o pipe vivo para sempre.

---

## 3. A reversão — exercitada, não descrita

> A reversão não conta como pronta enquanto não tiver sido **feita uma vez**. Reversão descrita
> é hipótese; o dia do corte não é hora de descobrir que a hipótese estava errada.

**O ensaio, em ambiente de produção e fora do horário:**

| passo | ação | o que confirmar |
|---|---|---|
| 1 | anotar o estado: `is_active` da function, nome e `toolIds` do preset | é o alvo do retorno |
| 2 | fazer o corte (desativar function, renomear preset) | o seletor mostra um `chatnd` só |
| 3 | **conversar** — uma pergunta de acervo, uma de arquivo | o agente responde |
| 4 | **reverter**: reativar a function, devolver o nome do preset | cronometrar |
| 5 | conversar de novo, pelo pipe | o pipe responde como antes |

✅ **MEDIDO em 21/09: reversão completa em 2,4 s.** A meta era 5 minutos.

```
2. CORTE     1.9s | function is_active=False | preset name=chatnd
6. REVERSAO  2.4s | function is_active=True  | preset name=ChatND Agente beta
```

Restauração conferida por leitura: `is_active=True`, nome do preset original, `toolIds` intactos,
seletor de volta a 12, e o pipe respondendo em conversa nova com `[Fonte + Acervos]`.

> **Um `HTTP 400` apareceu** ao mandar mensagem na conversa antiga logo após a reversão.
> **Investigado em 21/09 e NÃO REPRODUZ** — nem com o mesmo id de mensagem, nem refazendo a
> janela pós-toggle (que funcionou em 10 s). Fica como **transitório de causa desconhecida**. O
> que o plano B precisava saber está verificado por outro caminho: **a conversa antiga responde
> normalmente depois da reversão**, testado duas vezes.

⚠️ **O que a reversão NÃO desfaz** — e precisa estar escrito antes, não descoberto depois:
as conversas tidas com o agente durante a janela **continuam existindo** e apontando para o
preset. Reverter devolve o seletor, não o histórico.

---

## 3b. A remoção do pipe — com data, para não virar o pipe eterno

> **Decisão do Davi, 21/09:** o pipe é **removido de vez uma semana após o corte**, se o agente
> estiver estável.

**Por que precisa de data, e não de critério:** o corte pelo `is_active` é migração suave — o
pipe continua servindo quem já está numa conversa. Sem prazo, "desativado" vira um estado
permanente, e o projeto fica com dois motores para manter, um deles invisível no seletor e vivo
no código. **Data evita isso; "quando estabilizar" não.**

| | |
|---|---|
| **corte** | D |
| **remoção do pipe** | **D + 7 dias** |
| **condição** | o agente estável — nenhum dos três sinais de reverter (abaixo) tendo ocorrido |
| **o que "remover" significa** | a function `chatnd` sai de vez; o `CLAUDE.md` perde a linha do Chico e a seção do pipe; a doc de produção é atualizada no mesmo PR |

⚠️ **Antes de remover, conferir se alguma conversa ainda aponta para `chatnd`** — a consulta está
na seção 5. Conversa que apontar vai parar de funcionar de vez, e aí sim sem reversão barata.

---

## 4. O primeiro dia — o que olhar e o que é sinal de reverter

**O problema de fundo:** o pipe tem série histórica na tabela `eventos`; o agente **não grava
nada** (D81). Então no primeiro dia não existe o número do outro lado — e a comparação seria
entre um lado medido e outro lembrado.

**O que dá para olhar, com o que existe hoje:**

| sinal | onde | o que significa |
|---|---|---|
| **latência por turno** | `railway logs`, tempo entre `POST /api/chat/completions` e o fim | o agente é mais lento por desenho (laço de ferramentas). Medido em 21/09: **41–61 s** para estruturar um deck, **300 s+** para o pedido inteiro |
| **turnos que terminam sem resposta** | resposta curta anunciando continuação | é o **D85**, e é o modo de falha mais provável do agente. Sinal forte |
| **502 do gateway** | erro no navegador, ~5 min | **medido: 300,2 s é o teto da borda.** Pedido longo estoura, e o usuário vê erro |
| **respostas sem acervo** | conteúdo genérico, sem citar documento | o agente não achou a base — pior que erro, porque parece resposta |
| **volume de chamadas ao `gpt-5.1`** | custo | o estágio do deck é caro; no agente ele passa a ser chamado por decisão do modelo, não do roteador |

### ⚠️ Confere-se o artefato, nunca a frase que o descreve

**Todo sinal da tabela acima se lê no artefato ou no log** — contagem de slides no `.pptx`, tool
calls no transcrito, chars no `nidum_orcamento`. **A prosa do agente entra como hipótese a
conferir, nunca como evidência** ([D90](08_Decisoes_e_Pendencias.md)).

Não é desconfiança genérica: em 21/09 o agente anunciou ter gerado *"todos os 30 slides,
exatamente como especificado — sem alterações, cortes ou resumos"*, e **o arquivo tinha 32**. A
frase era específica, segura, e tinha o formato de uma verificação. **Frase vaga levanta
suspeita; frase precisa e errada, não.**

Vale também para o relato de erro: *"não encontrei nada no acervo"* precisa ser conferido contra
as buscas que ele de fato fez.

### Os três sinais de reverter, e eles não são graduais

1. **Turno sem resposta em pergunta comum.** Se acontecer fora de "leia o documento inteiro", o
   laço não está fechando e o problema não é de orçamento.
2. **Resposta sem acervo em pergunta institucional.** O pipe garante RAG na rota documentos; o
   agente depende de o modelo decidir buscar. Se ele deixar de buscar, a régua do produto caiu.
3. **502 em uso normal.** Se o teto de 300 s for atingido por pedido que o pipe atendia, o corte
   tirou capacidade do usuário.

**Qualquer um dos três, sozinho, justifica reverter no mesmo dia.** Nenhum deles precisa de
confirmação estatística — são qualitativos e visíveis na primeira ocorrência.

---

## 5. A consulta de uso

**Quantas conversas ainda apontam para o pipe** — a pergunta que decide se a remoção em D+7 é
segura:

```python
# lista os chats e conta por modelo. Content-free: so o id do modelo.
from collections import Counter
cnt = Counter()
for ch in api("/api/v1/chats/list?page=1"):
    det = api("/api/v1/chats/%s" % ch["id"])
    for m in ((det.get("chat") or {}).get("models") or []):
        cnt[m] += 1
print(cnt.most_common())
```

**Medido em 21/09:** dos 11 chats da primeira página, **10** apontam para
`chatnd-agente-beta` e **1** para `nidum-10---documentos`. Nenhum para `chatnd` — mas são
os chats de teste desta sessão, **não** o universo. Antes de remover, rodar sobre **todas** as
páginas.

**E a contagem de uso do dia do corte** sai da tabela `eventos`
(`chatnd_analytics.db`, em `DATA_DIR`), com a coluna `origem` nova:

```sql
SELECT origem,
       COUNT(DISTINCT user_hash)                      AS pessoas,
       COUNT(*)                                       AS perguntas,
       SUM(desfecho = 'vazio')                        AS vazias,
       SUM(desfecho = 'erro')                         AS com_erro,
       SUM(desfecho = 'truncado')                     AS truncadas,
       CAST(AVG(latencia_ms) AS INT)                  AS latencia_media
  FROM eventos
 WHERE ts >= date('now')
 GROUP BY origem;
```

---

## O que este checklist ainda não tem

1. ~~O teste da conversa aberta~~ · **FEITO em 21/09** — e refutou as três hipóteses.
2. ~~A reversão não foi exercitada~~ · **FEITA em 21/09**, 2,4 s.
3. **Nenhum número do agente existe do lado do analytics** (D81) — o primeiro dia será observado
   por log e por relato, não por série.
4. **O `CLAUDE.md` precisa perder a linha do Chico** — ele sai no corte, e a doc
   ainda o descreve como dependente do `chatnd`.
