# 12 — Fase E: os 14 itens organizados por impacto

> **Insumo de decisão, de 10/09/2026.** A lista dos 14 está no `08`; aqui ela vai
> ordenada por **o que quebra para quem usa** se o preset agêntico substituir o pipe sem
> o item. Não é plano: é para decidir rápido o que importa antes do corte.

---

## A pergunta que ordena a lista

Não é "o que o pipe faz" — é **"o que o usuário perde no dia seguinte ao corte"**. Um
item que só existe porque o pipe é um pipe não precisa ser portado: precisa ser
descartado com o motivo escrito.

---

## Item ENCERRADO — o #2 saiu da lista

**#2 · Wrappers invisíveis — ITEM ENCERRADO, não é mais da lista (11/09/2026).**

> Entrou aqui como **bloqueador técnico** e atravessou a semana assim. Investigado, virou
> nada — em três camadas, e nenhuma era o que parecia:
>
> 1. **O bloqueador era imaginado.** Um preset já aparece no seletor com o **nome dele**;
>    esconder o modelo base é um **toggle** (`is_active` numa entrada de override, e
>    `utils/models.py` faz `models.remove(model)`). Configuração, não código.
> 2. **Havia uma violação real ao lado, invisível.** `info.base_model_id` e `owned_by`
>    viajam no payload de `/api/models` para **qualquer usuário autenticado** — e isso já
>    valia **com os wrappers de hoje**. Confirmado em produção pelo devtools.
> 3. **A violação, examinada, não era violação.** Vaza o **modelo**, nunca a **chave**;
>    todo mundo com conta é de dentro; e a regra protege o **texto das respostas**, não o
>    payload de uma API interna. **A regra é que estava mal escrita** — reescrita com
>    escopo explícito no `CLAUDE.md`. Ver **D61**.
>
> **Consequência: o #2 sai da lista.** Não é bloqueador e não é item.

**O prazo do corte passa a ser governado por dois itens, e só:** o **#6** (fechar os 28%
de ambição de deck, que já tem número) e o **#13** (canal do projeto, que carrega a
pendência D20 junto).

## Bloqueadores — sem isto, o corte não acontece

**#6 · Geração de arquivos.** Uso diário e uma das quatro rotas. A Fase A provou que a
tool **funciona no preset** — o que falta é medido e nomeado: **ambição de deck a 28%**
(18 slides do pipe × 10 do agente, mesmo modelo, mesmo pedido) e o round-trip de edição
lendo os **bytes brutos** do Storage. Não é portar: é fechar a diferença que já tem
número.

**#13 · Canal do projeto.** Pasta = instruções + coleções + arquivos avulsos, com o
bloco "Material do projeto" como SYSTEM. É **como as pessoas usam hoje**. E carrega a
pendência D20 junto (o middleware injeta os arquivos da pasta a cada mensagem e o
`_anexos_recentes` não distingue origem) — **o corte é a oportunidade de consertar isso
na origem**, em vez de portar o defeito.

---

## Alto valor — o agente pode fazer diferente, mas precisa fazer

> **Dois dos quatro saíram (D79).** O #8 e o #9 foram descartados em 12/09/2026. A leitura de *alto valor* media o custo de **perder** o recurso, não a **necessidade** dele — e só a segunda decide escopo de corte. O texto deles fica abaixo, marcado, porque a razão pela qual entraram continua sendo informação para quem reabrir.

**#3 · Etiquetas de procedência no contexto.** As cotas e o `MAX_CHARS_TOTAL` são
mecânica de pipe e podem morrer; **as etiquetas, não.** São elas que sustentam a parede
geral × documentos (D23) — o agente declara a procedência e por isso pode ver as duas
fontes sem misturá-las. Sem etiqueta, a parede vira promessa.

**#12 · Anexos: "substitui, não soma".** O acervo reduzido quando há anexo é regra de
orçamento **e** de foco: quem anexa um documento quer falar dele. No laço agêntico o
modelo decide quando buscar, então a regra precisa virar **instrução**, não corte.

**#8 · Áudio anexado (Whisper local) — DESCARTADO (12/09/2026, D79).** Entrada por voz é uso real e o Whisper já está
no volume. Barato de manter, caro de perder.

**#9 · Saída de voz — DESCARTADO (12/09/2026, D79).** Player, keepalive SSE, cancelamento limpo, retenção de 30 dias.
Mais trabalhoso que o #8 e menos usado — mas é o item que mais "aparece" se sumir.

---

## Baixo impacto, ou o agente já cobre

**#1 · Classificador de rota.** **Este item é o que a Fase E substitui**, não o que ela
precisa portar: no laço, o modelo escolhe a ferramenta e a rota fixa deixa de existir.
**A ressalva está SUSPENSA, não resolvida (11/09/2026).** O "Chico" usa o `chatnd` como
base model, e mudar as categorias do roteador atravessa produto — *"o corte não é só
nosso"*. Com o Chico **aposentado**, o #1 deixa de depender de terceiro. **Mas o
acoplamento continua no código: se o Chico voltar, isto volta a ser PRÉ-REQUISITO, e
não consideração.** Ver **D70** — *bloqueio removido* e *bloqueio adormecido* se
parecem enquanto duram e se comportam de forma oposta quando a condição muda.

**#5 · Termos canônicos.** Nasceu para consertar o classificador — o `gpt-5-mini` não
sabe que "fazer da casa um ninho" é frase do Documento Fundador. **Sem classificador,
metade do motivo evapora.** A outra metade — a trava determinística — continua valendo,
e é ela que deve sobreviver, não a valve inteira.

**#10 · Busca web.** O D23 já provou que a parede se sustenta com procedência declarada,
tendo a ferramenta na mão. Vira tool com instrução, não rota.

**#7 · Imagem.** Rota inteira que precisa virar tool. Decisão de produto mais que de
engenharia: o refino assistido por visão é o que dá qualidade, e ele depende de anexo.

**#4 · Âncora dos fundadores.** Comportamento de *fallback* para busca vazia. No laço, o
agente pode simplesmente buscar de novo com outros termos — que é melhor. Candidato a
**descarte com motivo**, não a porte.

**#11 · Analytics** e **#14 · Diagnóstico.** Observabilidade, não função. Não bloqueiam
o corte, mas cortar sem eles é cortar às cegas: a comparação pipe × agente precisa de
número, e o `MOSTRAR_ROTA`/`DEBUG_TRECHOS` é como se vê o que o agente fez. **Portar
antes do corte custa pouco e paga na própria transição.**

---

## Duas observações que a lista de 14 não traz

**Os itens #1 e #5 são um item só.** Um existe para consertar o outro. Contá-los
separado superestima o trabalho e esconde que o corte **elimina** os dois.

**Falta um 15º item, e ele não é do pipe: a conferência do que está publicado.** O pipe
e as tools vão para produção por API, manualmente — nada compara o painel com o
repositório (ver `11_Varredura_Cobertura.md`). Durante a Fase E vão coexistir duas
implementações do mesmo produto, e **é exatamente quando "qual versão está no ar?" deixa
de ser curiosidade e vira a pergunta central.**

---

## Carimbo

**Última verificação: 2026-09-10.** Ordenação proposta, não decidida. O `08` continua
sendo a fonte da lista dos 14; este documento só a organiza.
