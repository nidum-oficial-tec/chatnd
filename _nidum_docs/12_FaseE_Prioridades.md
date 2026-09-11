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

## Bloqueadores — sem isto, o corte não acontece

**#2 · Wrappers invisíveis.** O usuário vê **uma IA só**. Sem os wrappers, o seletor
mostra o nome do modelo — e "nunca revelar qual LLM/provedor está por trás" é regra
inviolável do projeto, não preferência. **É o único item cuja ausência viola uma regra
escrita.**

> **RESPOSTA DE 11/09 (pedido do Davi: configuração, código, ou impossível?):
> é CONFIGURAÇÃO, e isso muda o prazo do corte.**
>
> Lendo `utils/models.py`: um preset já aparece no seletor com o **nome dele**
> (`custom_model.name`), nunca com o do modelo base. O que revela o provedor é o
> **modelo base estar listado como entrada própria** — e ele pode ser removido da
> lista: basta uma entrada de override para ele (mesmo id, `base_model_id = None`)
> com `is_active = False`, e o código faz `models.remove(model)`. O painel expõe
> isso como o toggle de ativo/inativo do modelo.
>
> **Duas ressalvas honestas.** (a) O `owned_by`/`connection_type` do modelo base
> continua viajando no payload do preset — o seletor os usa só para escolher
> **ícone** (`ollama`, `external`), não texto, mas quem abrir a API ou o devtools
> vê. Esconder do seletor e esconder de quem procura são barras diferentes. (b)
> Conferi **lendo o código**, não testando no painel — o teste é abrir o seletor
> com o base desativado e confirmar.
>
> **Consequência:** o #2 deixa de ser bloqueador de engenharia e vira um toggle por
> modelo base. O prazo do corte passa a ser governado pelo **#6** (fechar os 28% de
> ambição de deck) e pelo **#13** (canal do projeto).
>
> **E o registro que importa para quem ler depois (Davi, 11/09): o obstáculo era
> IMAGINADO, não real.** O #2 entrou na lista como bloqueador técnico e atravessou a
> semana como tal — quando a resposta era um toggle no painel. **O corte não tem
> bloqueador de engenharia; tem decisão de produto.**
>
> Quem repetir esse exercício: antes de classificar um item como bloqueador, gaste os
> vinte minutos de ler como o mecanismo funciona hoje. Um item na coluna errada não
> atrasa só a si mesmo — reordena tudo o que vem depois dele.
>
> **E a ressalva virou achado próprio, não pendência desta fase.** O `owned_by` e o
> `info.base_model_id` viajam no payload de `/api/models` para **qualquer usuário
> autenticado** — e isso vale **também para os wrappers de hoje**. Os wrappers escondem
> do **seletor**, não da **API**. Ver **D61**: é assunto de agora, e a Fase E não muda
> nada nele.

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

**#3 · Etiquetas de procedência no contexto.** As cotas e o `MAX_CHARS_TOTAL` são
mecânica de pipe e podem morrer; **as etiquetas, não.** São elas que sustentam a parede
geral × documentos (D23) — o agente declara a procedência e por isso pode ver as duas
fontes sem misturá-las. Sem etiqueta, a parede vira promessa.

**#12 · Anexos: "substitui, não soma".** O acervo reduzido quando há anexo é regra de
orçamento **e** de foco: quem anexa um documento quer falar dele. No laço agêntico o
modelo decide quando buscar, então a regra precisa virar **instrução**, não corte.

**#8 · Áudio anexado (Whisper local).** Entrada por voz é uso real e o Whisper já está
no volume. Barato de manter, caro de perder.

**#9 · Saída de voz.** Player, keepalive SSE, cancelamento limpo, retenção de 30 dias.
Mais trabalhoso que o #8 e menos usado — mas é o item que mais "aparece" se sumir.

---

## Baixo impacto, ou o agente já cobre

**#1 · Classificador de rota.** **Este item é o que a Fase E substitui**, não o que ela
precisa portar: no laço, o modelo escolhe a ferramenta e a rota fixa deixa de existir.
**Uma ressalva séria:** o "Chico" usa o `chatnd` como base model, e mudar as categorias
do roteador atravessa produto. O corte não é só nosso.

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
