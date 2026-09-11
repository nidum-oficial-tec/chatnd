# 11 — Varredura de cobertura: o que ninguém confere, e o que desliga em silêncio

> **Levantamento de 10/09/2026.** Não é plano aprovado — é o mapa do que ficou de fora.
> Nasceu de um dia em que seis defeitos diferentes tinham a mesma forma.

---

## Por que esta varredura existe

Em 10/09/2026, num único dia, apareceram: 92 caminhos abandonados por um modo que
desligava a detecção de movimentação; 67 arquivos perdidos numa área de passagem que
nenhuma guarda vigiava; 70 "sumiços inexplicados" que eram exclusões declaradas; 56
órfãos que eram artefatos gerados; uma classe de conferência cega por comparar zero com
zero; e uma limpeza de disco que existia, era chamada, e não fazia nada porque o default
a desliga.

Nenhum deles é bug de lógica. **Todos são defeitos de ALCANCE** — código correto
cobrindo menos do que se supunha. E defeito de alcance não aparece em revisão de código,
porque o código que você lê está certo.

Daí as duas perguntas desta varredura:

1. **Que objetos existem e nenhum relatório enumera?**
2. **Que modos, flags e defaults desligam uma proteção sem dizer?**

---

## Parte 1 — Objetos sem dono

### O que JÁ tem conferência

| objeto | quem confere |
|---|---|
| Coleções no painel × `sync_config` | `conferir_registros.colecao_fora_do_config` |
| Coleções × repo (órfãos/faltantes) | `orfaos_indice.py`, `conferir.py` |
| Coleções × SharePoint | `conferir.py` (diária) |
| Arquivos na base sem coleção | `higiene_owui.py` |
| Valves doc × código | `conferir_registros` (3 classes) |
| Ids de coleção citados na doc | `conferir_registros.id_fantasma` |
| Fixtures × pastas do repo | `conferir_registros.fixture_vencida` |
| Nome de exibição de modelo × doc | `conferir_registros.modelo_renomeado` |
| `FRAC_CATASTROFE` fora do desenho | `conferir_registros.frac_catastrofe` |
| Volume / armazenamento | PR #181 (aberto) |

### O que NÃO tem — em ordem de risco

**1. O pipe e as tools publicados. É a maior lacuna, e de longe.**

`chatnd.py` e `gerador_de_arquivos_nidum.py` são publicados **por API**, manualmente —
`POST /api/v1/functions/id/chatnd/update`. Mergear na `main` **não publica**. Logo o que
está no ar pode ser qualquer versão, e **nada compara o painel com o repositório**.

A REGRA DA DOC (no `CLAUDE.md`) existe justamente porque esse descompasso é real e já
apodreceu a documentação uma vez. Mas a regra pede disciplina humana; não há conferência.
O `diagnostico_modelos.py` olha modelos, não funções.

> **O coração do produto é o único objeto que ninguém confere.**

**2. Grupos, usuários e concessões de acesso.** As coleções têm `access_grants`, e
nenhum relatório enumera quem tem acesso a quê. Uma base que ficasse legível para um
grupo errado não produziria sintoma nenhum — o D31 já diz que nome de pasta não é
política de acesso, mas ninguém verifica qual é a política.

**3. Vetores sem arquivo.** A `higiene_owui` caça *arquivos* órfãos. Os *embeddings* de
um arquivo removido ficam no pgvector? Não medimos. Custa espaço e pode devolver trecho
de documento que já saiu da base — que seria vazamento com aparência de resposta normal.

**4. Objetos do OWUI que nunca foram inventariados:** `prompts`, `notes`, `channels`,
`automations`, `skills`, `memories`, `evaluations`. Cada um é um router que existe, com
dados que persistem. Nenhum aparece em relatório algum. Não sabemos sequer se estão
vazios — e "não sabemos se está vazio" é exatamente o estado que o D51 descreve.

**5. `_arquivo/`.** Cresce por decisão (regra 1: nunca deletar). Ninguém mede quanto,
nem confere que o que está lá é o que deveria. Hoje tem os 92 caminhos abandonados.

**6. Suítes que não rodam em CI.** `teste_tipo_contrato` e `teste_restritos` estão
**vermelhos** e ninguém viu, porque nenhum workflow os roda. Uma suíte que não roda é
documentação que se acha teste.

**7. Recursos do Railway.** Buckets, volumes desanexados e serviços órfãos foram
auditados **à mão** em 09/09 (D40–D43). Não há conferência recorrente: a próxima
divergência será achada pela fatura.

---

## Parte 2 — Modos que desligam mecanismos

Os seis casos fechados estão no **D52**. O que esta varredura acrescenta:

**`ENABLE_PERSISTENT_CONFIG`, default `True` — e este é o mais perigoso dos que restam.**

Com ele ligado, a configuração vem do **banco**, e a variável de ambiente é usada só na
primeira vez. Mudar uma env var no Railway e reiniciar **não muda nada** se a chave já
estiver no banco. É a causa já observada de `RAG_EMBEDDING_BATCH_SIZE=1` persistir apesar
do ambiente, e é o D24 em forma de infraestrutura: **configuração mora no banco, e o
banco não deixa rastro em commit.**

O sintoma é o pior possível: você muda a variável, o deploy sobe verde, e o
comportamento não muda. Nada erra — só não obedece.

**`--permitir-remocao-grande`: um NO-OP, e um exemplo do jeito CERTO.** A flag não faz
mais nada desde a V2 — e, em vez de ser ignorada em silêncio, ela **avisa em voz alta**
que é no-op. É o contraexemplo útil desta varredura: uma proteção aposentada que declara
a própria aposentadoria não engana ninguém.

**Onde procurar os próximos:** todo `if not <flag>` que embrulha uma remoção, uma
verificação ou um alarme; e todo `os.getenv(..., 'true')` cujo valor decide se uma guarda
roda. O padrão de risco é sempre o mesmo — **o default protege contra o erro comum e
desliga a proteção contra o erro raro.**

---

## O que fazer com isto

Em ordem de valor, sem estimativa de esforço (isso é conversa, não planilha):

1. **Conferência do pipe/tools publicados × repositório.** Fecha a maior lacuna, e é a
   única que atinge o produto em si.
2. **Rodar as suítes existentes em CI.** Duas já estão vermelhas; o conserto é de
   workflow, não de código.
3. **Inventário de concessões de acesso.** Enumerar é barato; a ausência é que é cara.
4. **Inventário dos objetos nunca olhados** (`prompts`, `notes`, `channels`, …) — uma
   linha por tipo dizendo quantos existem já muda "não sabemos" para "sabemos".
5. **Vetores sem arquivo** — medir antes de decidir se é problema.
6. **Inventário escrito dos modos que desligam proteção** (D52), com um teste por modo.

---

## Carimbo

**Última verificação: 2026-09-10.** Este documento descreve ausências; ausência envelhece
mais devagar que presença, mas envelhece — cada item resolvido sai daqui e entra na
tabela de quem confere o quê.
