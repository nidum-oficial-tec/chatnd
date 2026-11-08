# Runbook - threads nativas x arenas do glibc (memoria do ChatND)

> Branch `fix/malloc-arena-max`. Diagnostico feito em producao em 2026-09-06 (container
> do deploy de 2026-09-04 13:08 UTC, commit b54af66). Nada aqui foi aplicado ainda:
> deploy bloqueado ate a fatura (terca). Sequencia: PASSO 1 sozinho, observar, so
> entao PASSO 2 se ainda precisar.

## 1. O que foi medido (nao e hipotese)

| medida | valor |
|---|---|
| threads no PID 1 | 896 (895 em `futex_do_wait`, 1 em `do_epoll_wait`) |
| threads Python (`py-spy dump`) | **37**: 32 = executor default do asyncio (`ThreadPoolExecutor-4_*`, teto 32, reusado), 3 `tqdm_monitor`, 1 anyio, MainThread |
| threads nativas (sem frame Python) | **~859**, em grupos de exatos **23** e **46/47** |
| cota de CPU do cgroup | **24** vCPU - mas `os.cpu_count()` devolve **48** (host) |
| `omp_get_max_threads()` | 48 (duas copias de libgomp: torch e sklearn) |
| pilhas das 877 threads | **0,05 GB** RSS - thread quase nao custa RAM |
| **arenas do glibc** (heaps anon rw-p alinhadas a 64 MiB) | **457 heaps, 9,29 GB** de 12,75 GB do container |
| heap principal `[heap]` | 0,91 GB |
| demais anon (pymalloc, buffers) | 0,53 + 0,23 GB |
| file-backed | 0,81 GB, dos quais 735 MB = `bge-reranker-base` (mmap do safetensors) |
| alocador | glibc (nao ha jemalloc mapeado) |

Leitura: 23 = 24-1 (lib que le o cgroup), 47 = 48-1 (lib que le o host). Cada rajada
e um pool OpenMP/BLAS novo nascendo; cada thread viva que aloca ganha uma arena
propria de ate 64 MiB (teto default: 8 x nucleos do HOST = 384 arenas) e a memoria
liberada fica presa nela. As rajadas (27 em 32 h) sao disparadas por ATIVIDADE em
horario de expediente, nao por timer - a "1 thread a cada 2,5 min" era media.

Sua hipotese original (ThreadPoolExecutor por handler / Thread em job periodico) NAO
existe no codigo: o fork e upstream v0.9.6 puro exceto `env.py`, `main.py`,
`middleware.py` e `editorial/`, e nenhum deles cria thread. O
`ThreadPoolExecutor()` por chamada em `retrieval/utils.py:593` existe, e context-managed,
e o dump prova que nao vaza - fica como esta.

## 2. PASSO 1 - `MALLOC_ARENA_MAX=2` (terca, sozinho)

- Onde: ja esta no `Dockerfile` desta branch (`ENV MALLOC_ARENA_MAX=2`). Opcional:
  tambem como variavel do Railway (mesmo efeito; a variavel vence o ENV).
- Custo: nenhum de latencia. Contencao de malloc entre threads - app I/O-bound com
  <= 32 threads Python; risco baixo. Reversivel na hora (tirar a variavel/ENV).
- Prova local (Docker, 24 cpus, mesma carga): **+1200 MB sem vs +360 MB com** - ver
  secao 5.
- Observar por algumas horas apos o deploy (ver secao 4, `probe6`):
  - `cgroup memory.current` estabiliza abaixo de ~4 GB apos aquecer (modelo do reranker
    carregado + heap principal + file cache)
  - `heaps` (arenas) para de crescer com as rajadas de threads
  - as rajadas de threads em si PODEM continuar - elas deixam de custar RAM
- Criterio para PASSAR ao passo 2: memoria ainda subindo com as rajadas, OU quiser
  reduzir as 800+ threads por higiene. Se o passo 1 bastar, o reranker fica em
  velocidade plena.

## 3. PASSO 2 - teto de threads numericas = 8 (so se precisar, medindo)

> **ESTADO (07/11/2026): APLICADO, com 4 e nao 8.** Precisou: a busca em 13 bases
> derrubava o servidor (`libgomp: Thread creation failed`) a cada 1-2 buscas seguidas.
> Valor 4 porque o reranker roda em paralelo uma vez por base (13 x 4 = 52 threads de
> calculo para 24 vCPU; com 8 seriam ~104). Depois: 24 buscas em serie, 0 quedas,
> mediana 69,6 s por busca (era 84-92 s). Whisper NAO foi remedido. Ver D94 em
> `_nidum_docs/08_Decisoes_e_Pendencias.md`.

Variaveis do Railway (nao entram no Dockerfile de proposito - so depois de medido):

```
OMP_NUM_THREADS=8
OPENBLAS_NUM_THREADS=8
MKL_NUM_THREADS=8
NUMEXPR_NUM_THREADS=8
```

- Efeito medido: processo novo com numpy+sklearn cai de 63 threads (32 cpus) para 15
  (= 2 pools de 7 + main); em prod, de ~96 para ~17. Rajadas de 47 viram 7.
- O que se perde: paralelismo do **reranker `bge-reranker-base`** (CrossEncoder, torch
  CPU) e do **Whisper local** (CTranslate2). Hoje os pools de 48 rodam num cgroup de 24
  - ja 2x sobrescritos, entao parte do "paralelismo" e contencao. A 8 mantem a
  maior parte; a 1 ficaria mensuravelmente mais lento.
- ANTES de aplicar: medir a latencia de uma pergunta na rota `documentos` (rerank) e
  de uma transcricao de audio de ~30 s. DEPOIS: repetir. Se piorar alem do
  aceitavel, subir para 12 ou remover.

## 4. Monitor em producao (container vivo ate o redeploy de terca)

Plantado em 2026-09-06 02:47 UTC, pid 9421, `sh /tmp/mon/monitor.sh` (copia em
`_nidum_manutencao/monitor_threads_prod.sh`). A cada 5 s conta `/proc/1/task`; quando
o numero SOBE, tira `py-spy dump` na hora e guarda os tids novos. Intervalo de 5 s (e
nao 30 s) porque a rajada dura segundos - a 30 s o dump cairia depois do retorno.

Ler:

```bash
railway ssh --project 4a6c796f-b47b-45a0-8d44-dfdddfa08ade --environment production --service ChatND -- 'cat /tmp/mon/monitor.out; ls /tmp/mon'
```

Numa rajada, o arquivo `burst_<ts>.pyspy` mostra qual thread Python esta `(active)` e em
qual funcao - esse e o call site. Trazer para local:

```bash
railway ssh --project 4a6c796f-b47b-45a0-8d44-dfdddfa08ade --environment production --service ChatND -- 'cd /tmp/mon && tar cz burst_* threads.log monitor.out | base64 -w0' > mon.b64
```

Sondas usadas no diagnostico (rodam em processo separado, nao tocam o app):
`probe6.py` (arenas x legitimo x file-backed) esta em
`_nidum_manutencao/sonda_memoria_prod.py`. Rodar: base64 do arquivo, `echo ... |
base64 -d > /tmp/p.py && python3 /tmp/p.py` via `railway ssh`.

Tudo em `/tmp/mon` MORRE com o container no redeploy. Puxar antes.

## 5. Prova local (Docker; este PC so tem Python 3.14)

```bash
docker run --rm --cpus=24 -v "$(pwd)/_nidum_manutencao:/w" -w /w python:3.11-slim-bookworm sh -c "pip install -q numpy scikit-learn && python prova_threads_arenas.py"
```

Sai 0 se: (fase 1) sem teto >= 40 heaps novas e com teto RSS <= 40% do sem; (fase 2)
com `OMP_NUM_THREADS=8` o processo tem <= 17 threads e menos que sem teto.
`threading.active_count()` NAO serve de assercao aqui - as threads sao nativas; a
prova conta `/proc/self/task` e heaps alinhadas a 64 MiB em `/proc/self/smaps`.

## 6. Aberto

- **Call site** que cria os pools novos: nao identificado. Duas hipoteses (time por
  thread chamadora; `threadpoolctl` redimensionando) NAO reproduziram - pools sao
  globais e reusados. O monitor da secao 4 e a aposta para fecha-lo. As correcoes
  acima sao agnosticas ao call site.
- 7,58 GB das arenas NAO hospedam thread parada - sao arenas de threads que ja
  morreram (anyio workers, etc.) com memoria liberada presa. O passo 1 ataca isso
  tambem; o passo 2 nao.
