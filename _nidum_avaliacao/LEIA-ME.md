# _nidum_avaliacao — régua de busca do ChatND

> Frente **R3** do plano de 07/11/2026 (causa raiz: a base guarda textos e não
> conhecimento; o acesso é por ferramentas genéricas; e nada mede a busca).
> R1 (camada de conhecimento) e R2 (camada de busca própria) são aceitas **por esta régua**.

## O que ela mede

Se a **busca** traz o documento certo, e em que posição. Ela não mede a resposta do modelo:
mede o que o modelo **recebe**.

Para o usuário, três falhas parecem iguais, mas têm causas opostas:

| Falha | Onde está o problema | A régua vê? |
|---|---|---|
| O documento não está na base | esteira | sim (`--conferir`) |
| Está na base e a busca não o trouxe | busca | **sim (o objetivo da régua)** |
| A busca trouxe e o modelo ignorou | agente / prompt | não; isso exige o rastro de produção (peça 3) |

## Arquivos

| Arquivo | O que é |
|---|---|
| `gabarito_busca.json` | perguntas, tipo e documentos-ouro de cada uma. **Muda só por PR**, e o ouro é conferido por quem conhece o documento. |
| `regua_busca.py` | roda o gabarito contra a busca de produção e gera o relatório |
| `teste_regua_busca.py` | prova offline das contas: ranking por documento, ouro sem acento, mínimo das listas |
| `resultados/regua_<data>.md` | relatório legível de cada execução (versionado) |
| `resultados/regua_<data>.json` | bruto da execução (não versionado) |

## Tipos de pergunta

| Tipo | Exemplo | Por que separado |
|---|---|---|
| `fato` | "Quem conduziu a reunião de coautores de 13/07?" | o caso básico |
| `recencia` | "Qual a reunião mais recente?" | a busca por significado não entende "recente" |
| `lista` | "Em que fase está cada projeto?" | busca por trechos falha quando a resposta exige vários documentos |
| `tabela_slide` | o quadro de fases do deck do Comitê | tabela convertida vira trecho fraco |
| `tema` | "O que a metodologia define sobre o EGP?" | documento institucional, sem data |
| `armadilha` | documento que **não existe** | o certo é dizer que não há; fica fora da média da busca |

Cada pergunta roda de dois jeitos:
- **`pergunta`:** o texto do usuário;
- **`palavras`:** a mesma pergunta como lista de palavras, do jeito que o agente reescreve.

A diferença entre as duas é a medida da falha nº 1 (a pergunta reescrita).

## Métricas

- **Acerto@5 / Acerto@20:** o documento-ouro aparece entre os 5 ou 20 primeiros **documentos distintos**. Nas listas, é o número mínimo de documentos (`ouro_minimo`).
- **MRR:** média de 1/posição do primeiro ouro. Quanto mais perto de 1, melhor.
- **Cobertura@20:** fração dos documentos-ouro no top 20 (listas).

## Como rodar

Só leitura em produção. A chave vem de variável de ambiente (`NIDUM_URL`, `NIDUM_TOKEN`) ou
do `.env.local` (`--env-local`, lê `NIDUM_API_KEY`), e nunca é impressa nem gravada.

```bash
py _nidum_avaliacao/teste_regua_busca.py
py _nidum_avaliacao/regua_busca.py --env-local --conferir
py _nidum_avaliacao/regua_busca.py --env-local
```

Cada busca leva de 15 a 30 s, porque o índice por palavra é remontado a cada chamada (ver R2).
A régua inteira roda em série, para não pesar no servidor: cerca de 40 min.

## Regra de uso

**Nenhuma mudança na busca, na esteira ou no prompt é dada como melhoria sem a régua antes e depois.**
É a mesma lição da REGRA DO CLASSIFICADOR (CLAUDE.md): sem o depois, você não consertou, você escreveu.
