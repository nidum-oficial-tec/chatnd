# Checklist do dia do corte — o agente substitui o pipe

> **Rascunho de 21/09/2026.** Adiado três vezes por ser "se sobrar tempo"; passou a ter lugar
> fixo na fila por decisão do Davi, exatamente por isso. **É documento, não operação** — nada
> aqui foi executado.
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
| 1 | **Republicar a `estruturar_deck_beta` pela workflow, com sha** | hoje o carimbo é `[origem: LOCAL — sem sha, não rastreável ao repo]`. Aceito enquanto beta; **não** aceito quando virar produto. **Destravado em 21/09:** a workflow recusava o alvo — `type: choice` com lista fechada, e `estruturar_deck_beta` não estava nela. O `case` já tinha ramo genérico, então faltava só a linha. **O publish local só foi possível porque a workflow não aceitava o alvo** | ⬜ rodar a workflow |
| 2 | ~~Fechar a régua do deck~~ · **RESOLVIDO em 21/09** | as 5 do pipe rodadas com o mesmo pedido: mediana **41** slides, **277** chars/slide. Agente: **32** e **281**. Os dois decks lidos pelo Davi — **conteúdo equivalente**. Ver [D91](08_Decisoes_e_Pendencias.md) | ✅ |
| 3 | ~~Confirmar o que o Chico usa como base~~ · **RESOLVIDO em 21/09** | **o Chico está aposentado e sai junto no corte** (Davi). A pergunta era se o corte atingiria outro colaborador; não atinge, porque o motor dele deixa de existir na mesma operação. O `CLAUDE.md` ainda afirma que ele usa o `chatnd` como base model — **está desatualizado** (a instância diz `claude-sonnet-4-6`) e a linha sai no corte, junto com o resto | ✅ |
| 4 | **Decidir a dívida do analytics (D81)** | o pipe grava cada turno na tabela `eventos`; o agente não grava nada. Depois do corte, a comparação seria entre um lado medido e outro lembrado | ⬜ decisão |

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

**Recomendado: B, em duas etapas separadas por dias.** Primeiro renomeia o preset e desativa a
function; depois, com o uso estabilizado, resolve o id. Fazer as duas coisas no mesmo dia
mistura dois modos de falha diferentes na mesma janela.

⬜ **Antes de executar:** conferir se `is_active: false` na function a some do seletor sem
apagá-la. É o que permite a reversão em minutos.

---

## 2. Quem estiver numa conversa aberta no pipe

**O que se sabe:** cada chat guarda o modelo em `chat.models` — medido: dos 11 chats da primeira
página, 10 apontam para `chatnd-agente-beta` e 1 para `nidum-10---documentos`. O id fica
**gravado no chat**, não é resolvido na hora.

**O que isso implica, e é a parte que precisa de teste, não de raciocínio:** uma conversa
gravada com `models: ["chatnd"]` continuará pedindo `chatnd` depois do corte. Se a function
estiver desativada, a próxima mensagem naquela conversa vai para um modelo que não existe mais.

⬜ **Teste obrigatório antes do corte, e ele é barato:**
1. abrir uma conversa no pipe, mandar uma mensagem;
2. desativar a function;
3. **voltar à mesma conversa e mandar outra mensagem**;
4. registrar o que acontece: erro, silêncio, ou queda para o modelo padrão.

**Sem esse teste o checklist está adivinhando.** As três saídas pedem respostas diferentes: erro
visível é aceitável (o usuário reabre), silêncio é inaceitável, e queda para o modelo padrão é o
pior — a pessoa segue conversando **sem acervo** e sem saber.

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

⬜ **Meta: reversão completa em menos de 5 minutos.** Se levar mais, o caminho está errado e
precisa de script, não de disciplina.

⚠️ **O que a reversão NÃO desfaz** — e precisa estar escrito antes, não descoberto depois:
as conversas tidas com o agente durante a janela **continuam existindo** e apontando para o
preset. Reverter devolve o seletor, não o histórico.

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

## O que este checklist ainda não tem

1. **O teste da conversa aberta (§2) não foi feito.** É a maior lacuna: três saídas possíveis,
   e a pior delas é silenciosa.
2. **A reversão não foi exercitada (§3).**
3. **Nenhum número do agente existe do lado do analytics** (D81) — o primeiro dia será observado
   por log e por relato, não por série.
4. **O `CLAUDE.md` precisa perder a linha do Chico** — ele sai no corte, e a doc
   ainda o descreve como dependente do `chatnd`.
