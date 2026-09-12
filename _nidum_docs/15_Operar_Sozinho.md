# 15 — Operar sozinho por alguns dias

> Escrito em 12/09/2026, para o Davi operar sem o Claude por alguns dias.
> **Uma regra acima de todas: nada aqui apaga nada.** Todo mecanismo automático
> desta casa só relata ou só adiciona. O único caminho que remove é o
> `sincronizar`, e ele tem freio. Se você ficar em dúvida, a resposta segura é
> **não rodar** — nenhum problema desta lista piora por esperar um dia.

---

## O relógio — o que roda sem ninguém (horários UTC; BRT = −3h)

| quando | o quê | onde |
|---|---|---|
| a cada 12 h | **puxar SharePoint** → traz documento novo para o repo | esteira |
| no merge de `.md` de acervo | **sincronizar** → escreve na base | esteira |
| a cada 6 h | alarme de defasagem (repo × índice) | esteira |
| 06:10 diário | **conferência SharePoint × base** | esteira |
| 07:40 diário | **alarmes vencidos** → escala para PR | esteira |
| 07:00 segunda | higiene da base | esteira |
| 06:00 domingo | backup do Postgres → R2 | esteira |
| 07:30 segunda | limpeza do armazenamento | plataforma |
| 07:40 segunda | conferidor de registros (doc × código × repo) | plataforma |

**Um lugar para olhar todo dia, se for olhar um só:** a aba **Actions** dos dois
repositórios. Vermelho quer dizer *o mecanismo quebrou*, nunca *achou problema* —
relatório que acha algo fica **verde** de propósito (D30).

---

## 1 · A esteira parou

**Sintoma:** documento novo no SharePoint não aparece no chat depois de ~12 h.

**Onde olho:** Actions → *Esteira - puxar SharePoint*. Vermelho = parou.
Se estiver verde, o problema não é o puxar — vá para a conferência (item 2).

**O que você resolve sozinho:**

- **Falha de rede / SSL / timeout.** Re-executar: botão *Re-run all jobs*. A
  esteira é idempotente — rodar duas vezes não duplica nada.
- **Falha que se repete com a mesma mensagem.** Copie a última linha do log. Se
  disser `NameError`, `ImportError` ou `AttributeError`, é código quebrado: **me
  espera**. Foi o que derrubou a esteira por onze horas em 11/09.
- **`AADSTS` / `invalid_client`.** É o *client secret* do SharePoint. A validade
  atual vai até **agosto/2028** (PR #80), então isto não deveria acontecer agora
  — mas se acontecer, é renovação no Entra ID e você já fez uma vez.

**O que espera:** qualquer erro de Python. Não edite script para destravar.

**Enquanto está parado:** nada se perde. O SharePoint é a fonte; o puxar só lê.
O acervo fica **desatualizado**, não corrompido.

---

## 2 · Um alarme disparou

Os alarmes viram **issue com `dono:` e `prazo:`**, rótulo `alarme`. Se o prazo
vencer, o job das 07:40 fica **vermelho e abre um PR** com a lista. Esse PR **não
é para mergear** — é o recibo de que há decisão pendente.

**Três saídas, e só três:**

1. conserte e feche a issue;
2. comente `prazo: AAAA-MM-DD` na issue para adiar — **vira linha escrita, com
   autor e data, e esse é o ponto**;
3. comente `dono: usuario` se o que falta é dono.

**Os alarmes que você vai ver, e o que significam:**

| alarme | o que é | você resolve? |
|---|---|---|
| *Puxador SharePoint parado* | item 1 acima | re-executar, sim |
| *Conferência: divergência SharePoint × base* | órfão ou faltante | **ler, não agir** |
| *Conferência QUEBRADA* | a rede de órfãos está **cega** | re-executar; se repetir, espera |
| *FREIO de segurança disparado* | o sync ia remover demais e **foi barrado** | **espera. Sempre.** |
| *Higiene FALHOU* | auditoria abortou | re-executar |

**Sobre divergência:** hoje ela relata **6 órfãos reais** (laudos de Retrofit que
nasceram na base, não no SharePoint) e faltantes explicados. Isso é estado
conhecido, não incidente. A conferência **só relata** — não existe caminho de
remoção automática, nem "para ligar depois".

**Sobre o FREIO:** ele existe porque remoção em massa já aconteceu uma vez. Se
disparar, ele **já fez o trabalho dele** — nada foi removido. Não force.

---

## 3 · Alguém reclama de resposta errada

Primeiro separe **três coisas diferentes** que parecem a mesma:

**a) Não achou um documento que existe.**
Vá à conferência do dia (Actions → conferência diária → artefato `faltantes`).
Se o documento estiver na lista de faltantes, o motivo provável está na mesma
linha. *Você resolve:* se for nome inválido ou pasta errada, é correção na
origem — renomeie no SharePoint e ele entra sozinho na próxima rodada.

**b) Respondeu com informação errada sobre a Nidum.**
Ligue o `MOSTRAR_ROTA` (Admin → Functions → ChatND → Valves) e refaça a
pergunta: ele diz qual rota o classificador escolheu. Se foi para *geral* quando
devia ser *documentos*, é roteamento. **Isso me espera** — teoria sobre prompt é
hipótese, não diagnóstico, e o projeto já refutou duas de três.

**c) Não entregou o arquivo, ou entregou link quebrado.**
A frase *"Anexo nativo indisponível nesta resposta — entregue por link"* é
**normal e projetada** no pipe: ele nunca emite o card. O link estar **absoluto**
(começa com `https://chatnd…`) é o que importa — se vier relativo, o `WEBUI_URL`
saiu do painel (Admin → Configurações → Geral).

**Onde ficam os logs:** `railway logs --service ChatND` (na pasta
`interface-chatnd/`). Desde 12/09 o laço agêntico registra a exceção com
traceback — antes ele falhava calado.

---

## Nunca sozinho — a lista curta

- **Publicar pipe ou tool.** Só pelo workflow *Publicar pipe/tools (manual)*,
  **com `dry_run` marcado primeiro**. E o `chatnd` não precisa ser publicado: o
  que está no ar é equivalente ao repo (difere só na formatação).
- **Qualquer coisa que apague conteúdo** — inclusive "limpar" a base, rodar
  remoção em massa, ou passar `--confirmar-remocao-em-massa`.
- **Editar script para destravar um workflow.** Se o workflow quebrou por
  código, o conserto é uma PR revisada, não um remendo.
- **Mexer em `ENABLE_PERSISTENT_CONFIG`** (D62). O pré-requisito é um inventário
  banco × ambiente que ninguém tem.
- **Mudar as categorias do roteador.** O Chico está aposentado, mas o
  acoplamento continua no código (D70).

---

## Os cinco comandos que resolvem quase tudo

```bash
gh run list --limit 10                 # o que rodou, e como terminou
gh run rerun <id>                      # re-executar o que falhou por rede
gh issue list --label alarme           # o que está aberto e pedindo decisão
railway logs --service ChatND          # o que o chat fez (de interface-chatnd/)
gh workflow run conferir.yml           # conferência sob demanda (só leitura)
```

---

## Carimbo

**Última verificação: 2026-09-12.** Escrito com a esteira recém-consertada
(#201), a fiação da conferência corrigida (#204) e o gerador publicado. Se algum
horário ou nome de workflow não bater, **o Actions manda, não este documento**.
