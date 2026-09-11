# 13 — As quatro decisões de operação, lado a lado

> **Insumo de decisão, 11/09/2026.** Pedido do Davi: os quatro juntos, com o que cada um
> muda e o risco, para decidir de uma vez. **Nenhum está decidido aqui.**

As quatro se parecem — todas mexem em como a produção se comporta sem mexer em lógica —
mas têm riscos de naturezas muito diferentes, e uma delas é bem mais perigosa que as
outras três somadas.

---

## 1 · `STORAGE_LOCAL_CACHE=false`

**O que muda.** Liga a limpeza da cópia local. Hoje o arquivo sobe ao R2 **e fica
também no volume do Railway, para sempre** — a função de limpeza existe, está correta, é
chamada, e retorna na primeira linha porque o default é `true` (D58).

**O que ganha.** Para de crescer o volume. Cada arquivo deixa de ocupar espaço em dois
lugares.

**O risco, e ele é real mas contido.** Todo download passa a refazer o fetch do R2 —
**latência em troca de volume**. Quem baixa um arquivo grande sente; quem só conversa,
não.

**Uma coisa que facilita a decisão:** `STORAGE_LOCAL_CACHE` é lido por `os.getenv`
direto, **fora** da camada de configuração persistente. Mudar a variável no Railway
**tem efeito imediato** no próximo start — não depende do item 2 abaixo, e é
**reversível pelo mesmo caminho**.

**Sem o item 3, esta mudança quase não faz nada:** hoje a limpeza é chamada de um único
lugar (fim do processamento de upload). Os outros quatro pontos que deixam cópia para
trás estão no PR #72.

---

## 2 · PR #72 — as chamadas que faltavam

**O que muda.** Acrescenta a limpeza em quatro pontos que hoje deixam cópia no volume:
depois do **upload ao S3**, depois de o **loader do retrieval** ler, depois de **farejar
os primeiros bytes** (hoje baixa o arquivo inteiro para ler 1 KB) e depois de
**transcrever** áudio — este último o pior caso, arquivo grande lido uma vez e nunca
mais. E nas três respostas de download, por `BackgroundTask`.

**O risco.** É `backend/` — **vai por git push → Railway, com downtime**. O código em si
é conservador: a guarda dupla permanece (com `STORAGE_PROVIDER=local` a limpeza não faz
nada, porque ali o arquivo local **é** o arquivo), e o `BackgroundTask` garante que o
`FileResponse` termine de ler antes de apagar — apagar antes do `return` serviria um
download vazio, que é o pior desfecho possível porque *parece* que funcionou.

**Depende do item 1.** Sem `STORAGE_LOCAL_CACHE=false`, este PR não muda comportamento
nenhum: as chamadas novas caem no mesmo `return` da primeira linha. **Mergear sem ligar
é seguro e inútil; ligar sem mergear conserta um quinto do problema.**

---

## 3 · `ENABLE_PERSISTENT_CONFIG` — **este é o perigoso**

**O que é.** Default `True`. Com ele ligado, a configuração vem do **banco**, e a
variável de ambiente só vale na primeira vez. O código é explícito:

```python
if self.config_value is not None and _persist_enabled:
    self.value = self.config_value      # o BANCO manda
```

**O sintoma que isso produz é o pior de todos os do dia:** você muda a variável no
Railway, o deploy sobe **verde**, e o comportamento **não muda**. Nada erra — só não
obedece. É a causa já observada do `RAG_EMBEDDING_BATCH_SIZE=1` persistir apesar do
ambiente, e é o D24 em forma de infraestrutura: configuração mora no banco e o banco não
deixa rastro em commit.

**O risco de desligar, e é por isso que este item é diferente dos outros três.** Passar
para `False` faz as variáveis de ambiente mandarem **em tudo, de uma vez**. Toda chave
ajustada pelo painel ao longo de meses volta ao valor do ambiente ou ao default — **num
único restart, sem lista prévia do que vai mudar**. Não é uma mudança de um
comportamento: é a troca da fonte da verdade de todos eles.

**A alternativa barata, e a minha recomendação se a pergunta for "como faço esta mudança
valer":** deixar `True` e **mudar o valor no painel**, que é onde a verdade mora hoje.
Desligar só se a intenção for justamente tornar o ambiente autoritativo — e nesse caso o
passo anterior é **inventariar o que está no banco divergindo do ambiente**, que ninguém
tem hoje.

---

## 4 · Republicar o pipe pelo `"jur"`

**O que muda.** O `_FATIA_FASE3` embutido no `chatnd.py` ainda tem `"jur"` no
`juridico.pastas`; a esteira já corrigiu para `"juridico"` (a pasta virou `Juridico/` na
reformulação de 03/09 e o mapa ficou na grafia de sigla). Enquanto não republicar, o
boost por assunto do `DIAL_FASE3` não reconhece a pasta do Jurídico pelo caminho.

**O ganho é pequeno e o risco não é zero.** A esteira já carimba `assunto: juridico`
corretamente — a divergência é **degradação, não corrupção**: o pipe segue usando
apelidos e sigla para o boost. Perde-se o sinal por pasta, e só no Jurídico.

**O risco.** Publicar substitui o pipe vivo. E a REGRA DA DOC vale aqui na forma mais
literal: **o que está no ar pode não ser o que está na `main`** — pipe e tools vão por
API, manualmente. Publicar a partir do repo sem conferir o que está publicado pode
sobrescrever alteração feita direto no painel.

**Recomendação:** **não publicar isoladamente por causa disto.** Junta com o próximo
publish, seja qual for o motivo dele — e o passo anterior a qualquer publish é a
conferência do item seguinte (doc `14`).

---

## O que eu faria, se a decisão fosse minha — e não é

| | |
|---|---|
| **1 + 2 juntos** | Fazem sentido como par: ligar a variável e mergear o PR no mesmo deploy. Separados, um é inútil e o outro é parcial. |
| **3** | Deixar `True`. Mudar valor no painel. Desligar exige um inventário banco × ambiente que ninguém tem. |
| **4** | Esperar. Ganho pequeno, e o certo é ter a conferência do `14` antes de qualquer publish. |

**A ordem não é arbitrária:** o item 4 depende de saber o que está publicado, e essa é
justamente a maior lacuna da varredura (`11`). Fazer o `14` primeiro barateia o 4 e todos
os publishes seguintes.

---

## Carimbo

**Última verificação: 2026-09-11.** Nenhuma das quatro está decidida.
