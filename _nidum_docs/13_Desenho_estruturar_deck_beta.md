# Desenho — `estruturar_deck_beta`

> **Escrito em 21/09/2026, ANTES de implementar**, a pedido do Davi. O desenho existia desde
> antes, só que **em conversa** — e por isso se perdeu entre sessões: ao retomá-lo, nem o
> desenho nem a prova do `bypass_filter` estavam no repositório, e a reconstrução custou uma
> rodada de perguntas. É o custo de ter decidido não documentar planos que seriam reordenados.
> **Plano que sobrevive a uma sessão mora no repositório.**

---

## O problema, medido

O pipe faz uma **chamada dedicada ao `gpt-5.1`** só para produzir a estrutura do deck, e entrega
a estrutura pronta à ferramenta. O agente não tem esse estágio: ele compõe os argumentos da
ferramenta no meio do resto do raciocínio.

| | slides produzidos |
|---|---:|
| pipe (estágio dedicado) | **22** |
| agente (argumentos no meio do raciocínio) | **~10** |

A diferença não é de prompt — é de **estágio**. No pipe, produzir a estrutura é a única coisa
que aquela chamada faz.

## O conserto

Mover o estágio dedicado para uma ferramenta, `estruturar_deck_beta`. **É mover código que já
existe**, não escrever do zero:

| no pipe (`_nidum_tools/chatnd.py`) | o que é |
|---|---|
| `GERADOR` (linha 1547) | o system prompt do estágio |
| `_chamar_gerador` (6094) | a chamada: `generate_chat_completion(..., bypass_filter=True)` com `GERADOR_MODEL` = `gpt-5.1`, `stream=False` |
| `_gerar_arquivo` (6196) | orquestra: monta o sistema, chama, e **tenta uma segunda vez com instrução estrita** se o JSON vier inválido ou vazio |

A ferramenta faz os três e **devolve a estrutura**; quem monta o arquivo continua sendo o
`gerador_de_arquivos_nidum`. O agente passa a ter dois passos explícitos — estruturar, depois
gerar — em vez de um só embutido no raciocínio.

## Publicação

- **id `estruturar_deck_beta`**, anexada **só ao preset do agente**.
- **O pipe não a enxerga**: ele chama a tool por `self.valves.TOOL_ID`, que aponta para o
  `gerador_de_arquivos_nidum`. Enquanto a valve não mudar, o pipe segue pelo caminho de hoje.
- Ninguém além do Davi usa o agente, então o raio de um erro é uma pessoa.

## ⚠️ A prova do `bypass_filter` NÃO está feita

Verificado em 21/09: **nenhuma tool publicada chama `generate_chat_completion`**.

```
gerador_de_arquivos_nidum.py: generate_chat_completion=0 bypass_filter=0
sharepoint_nidum.py:          generate_chat_completion=0 bypass_filter=0
relatorio_ambientes_nidum.py: generate_chat_completion=0 bypass_filter=0
```

As 5 ocorrências de `bypass_filter=True` no projeto estão **todas no `chatnd.py`**, que é um
*pipe* — ele recebe `__request__`/`__user__` por outro caminho. **Que uma tool consiga fazer o
mesmo é premissa, não fato.** Se ela não conseguir, o desenho inteiro cai e a alternativa é
outra (o estágio fica no pipe e o agente o invoca de outro jeito).

**A primeira execução da ferramenta é a prova.** Se falhar, falha barulhento e cedo.

## A régua

Cinco execuções de cada lado. O resultado do pipe já tem baseline: **22 slides**.

| critério | alvo |
|---|---|
| **mediana de slides** | ≥ **80% do pipe** → ≥ 17,6, isto é **18 slides** |
| **densidade** | dentro de **±25%** da do pipe (chars de corpo por slide) |
| **slides mudos** | **zero**, para os tipos de `_TIPOS_EXIGEM_CORPO` |

`_TIPOS_EXIGEM_CORPO` (`gerador_de_arquivos_nidum.py:1117`):
`("conteudo", "destaque", "divisao", "numerada", "cartoes")`. Slide desses tipos sem corpo é
slide mudo — conta como falha, não como variação.

### Por que cinco, e não três

Porque a variância medida hoje **não permite** três. No mesmo dia, o mesmo prompt (`a1`) rodado
duas vezes contra a mesma pasta consumiu **532 e 30.237 chars** — **57×**. Se o agente varia
assim no consumo, não há razão para supor que varie pouco na contagem de slides.

**A regra que isso impõe:** três execuções só bastariam se a diferença **entre** os lados fosse
muito maior que a variação **dentro** de cada lado. Com 57× de variação interna medida, a
suposição é insustentável até prova em contrário. Começa com cinco; se as cinco vierem
apertadas, o próximo par pode usar menos — e a decisão fica registrada com os números.

## O que este desenho NÃO faz

1. **Não toca no pipe.** O caminho de produção segue idêntico até o dia do corte.
2. **Não muda o `gerador_de_arquivos_nidum`.** A ferramenta nova produz estrutura; quem monta o
   arquivo continua sendo ele.
3. **Não resolve o orçamento por turno** — ver D87: estacionado por decisão, desligado.
