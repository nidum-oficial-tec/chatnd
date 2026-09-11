#!/usr/bin/env python3
"""
limpeza_armazenamento.py - higiene do armazenamento do ChatND (volume, R2, indice).

ONDE RODA:
  - orfaos-locais: DENTRO DO CONTAINER do ChatND (precisa do volume em /app/backend/data).
    Transporte como no runbook de threads (base64 em pedacos de 2000 chars - a linha do
    railway ssh trunca acima disso):
  - gerados-antigos e anexos-antigos: em QUALQUER lugar com acesso ao banco e ao R2 - o
    workflow semanal (.github/workflows/limpeza_semanal.yml) roda no runner do Actions
    com PROD_DATABASE_URL e R2_* (mesmos secrets do backup na esteira).

    base64 -w0 _nidum_manutencao/limpeza_armazenamento.py > /tmp/l.b64
    railway ssh --service ChatND -- bash -c "echo $(cat /tmp/l.b64) | base64 -d > /tmp/limpeza.py && python3 /tmp/limpeza.py orfaos-locais"

SIMULACAO E O PADRAO (D27: operacao destrutiva roda simulacao antes, independente de
autorizacao). Nada e apagado sem --executar. Cada modo imprime o que faria, quanto
libera, e - com --executar - o que fez, item a item.

MODOS

  orfaos-locais
      Arquivos em /app/backend/data/uploads cujo prefixo <uuid>_ NAO tem registro na
      tabela `file`. Sao copias locais que o provedor S3 do Open WebUI grava antes de
      subir ao R2 e nunca apaga (storage/provider.py, S3StorageProvider.upload_file).
      Seguro apagar: o download (routers/files.py -> Storage.get_file) baixa do R2 para
      o local a cada pedido, NAO le a copia. Medido em 2026-09-10: 2.599 arquivos, 90 MB.

  gerados-antigos [--dias 30]
      Arquivos GERADOS pelo pipe (gerador_de_arquivos_nidum) com mais de N dias:
      pptx/html/pdf/docx/xlsx, `data` vazio (gerado nao e processado), nome no padrao
      PREFIXO_Titulo_dd-mm-yyyy_vN.ext, e fora de qualquer base (knowledge_file).
      Apaga: objeto no R2, copia local, registro em `file`. Espelha a retencao que o
      audio TTS ja tem (TTS_RETER_DIAS=30). O usuario que quiser guardar baixa antes.

  anexos-antigos [--dias 60]
      Colecoes vetoriais `file-<id>` de anexos de CHAT (arquivo fora de qualquer base)
      sem atualizacao ha N dias. Apaga SO os chunks em `document_chunk`; o arquivo
      continua no R2 e na tabela `file` (reanexar reprocessa). Medido em 2026-09-10:
      1.226 chunks (~24 MB) elegiveis a 60 dias; 11.017 chunks (~212 MB) se fosse tudo.

OPCOES
  --executar        apaga de verdade (sem isto, so lista)
  --dias N          janela de retencao (gerados-antigos: 30; anexos-antigos: 60)
  --limite N        no maximo N itens nesta execucao (freio; 0 = sem limite)

FREIOS
  - Sem --executar nada muda. Com --executar, imprime item a item e para no primeiro
    erro de banco; erro de R2/local e registrado e segue (best-effort, como o prune
    de audio do pipe).
  - --limite existe para a primeira execucao real ser pequena e conferivel.
"""
import argparse
import os
import re
import sys
import time
from urllib.parse import urlparse

UPLOADS = "/app/backend/data/uploads"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_")
GERADO_RE = re.compile(r"^[A-Z]{2,8}_.+_\d{2}-\d{2}-\d{4}_v\d+(?: \(\d+\))?\.(pptx|html|pdf|docx|xlsx)$", re.I)
EXT_GERADO = ("pptx", "html", "pdf", "docx", "xlsx")


def mb(n):
    return "%.1f MB" % (n / 1e6)


def conectar():
    import psycopg2
    url = os.environ.get("DATABASE_URL") or os.environ.get("PROD_DATABASE_URL")
    if not url:
        raise SystemExit("ABORTA: falta DATABASE_URL (container) ou PROD_DATABASE_URL (runner).")
    return psycopg2.connect(url)


def _env2(a, b):
    return os.environ.get(a) or os.environ.get(b)


def s3_client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=_env2("S3_ENDPOINT_URL", "R2_ENDPOINT_URL"),
        aws_access_key_id=_env2("S3_ACCESS_KEY_ID", "R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_env2("S3_SECRET_ACCESS_KEY", "R2_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("S3_REGION_NAME") or "auto",
    )


def s3_key_de(path):
    # file.path do provedor S3 e "s3://<bucket>/<key>"
    if not path or not path.startswith("s3://"):
        return None, None
    u = urlparse(path)
    return u.netloc, u.path.lstrip("/")


# --------------------------------------------------------------------------- modos

def orfaos_locais(args):
    if not os.path.isdir(UPLOADS):
        raise SystemExit("orfaos-locais so roda dentro do container (nao achei %s)." % UPLOADS)
    conn = conectar()
    cur = conn.cursor()
    cur.execute("select id from file")
    ids = {r[0] for r in cur.fetchall()}
    conn.close()
    itens = []
    total = 0
    for nome in sorted(os.listdir(UPLOADS)):
        p = os.path.join(UPLOADS, nome)
        if not os.path.isfile(p):
            continue
        m = UUID_RE.match(nome)
        fid = nome[:36] if m else None
        if fid in ids:
            continue
        sz = os.path.getsize(p)
        itens.append((p, nome, sz))
        total += sz
    print("orfaos-locais: %d arquivos sem registro em `file`, %s" % (len(itens), mb(total)))
    for _, nome, sz in itens[:15]:
        print("   ", sz, nome[:110])
    if len(itens) > 15:
        print("    ... (+%d)" % (len(itens) - 15))
    if not args.executar:
        print("SIMULACAO: nada apagado. Use --executar.")
        return
    feitos = 0
    for p, nome, sz in itens:
        if args.limite and feitos >= args.limite:
            print("limite de %d atingido." % args.limite)
            break
        try:
            os.remove(p)
            feitos += 1
            print("  apagado:", nome[:110])
        except OSError as e:
            print("  ERRO local:", nome[:80], e)
    print("orfaos-locais: %d apagados." % feitos)


def gerados_antigos(args):
    corte = time.time() - args.dias * 86400
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        select f.id, f.filename, f.path, coalesce((f.meta->>'size')::bigint,0), f.created_at
          from file f
         where f.created_at < %s
           and (f.data is null or f.data::text in ('{}', 'null'))
           and lower(f.filename) ~ '\\.(pptx|html|pdf|docx|xlsx)$'
           and f.id not in (select file_id from knowledge_file)
         order by f.created_at
        """,
        (corte,),
    )
    linhas = [r for r in cur.fetchall() if GERADO_RE.match(r[1] or "")]
    total = sum(r[3] for r in linhas)
    print("gerados-antigos (> %d dias): %d arquivos, %s" % (args.dias, len(linhas), mb(total)))
    for fid, nome, path, sz, ts in linhas[:20]:
        print("   ", time.strftime("%Y-%m-%d", time.gmtime(ts)), sz, nome[:90])
    if len(linhas) > 20:
        print("    ... (+%d)" % (len(linhas) - 20))
    if not args.executar:
        print("SIMULACAO: nada apagado. Use --executar.")
        conn.close()
        return
    s3 = s3_client()
    feitos = 0
    for fid, nome, path, sz, ts in linhas:
        if args.limite and feitos >= args.limite:
            print("limite de %d atingido." % args.limite)
            break
        bucket, key = s3_key_de(path)
        if bucket and key:
            try:
                s3.delete_object(Bucket=bucket, Key=key)
            except Exception as e:  # best-effort, registrado
                print("  ERRO R2:", nome[:80], e)
        local = os.path.join(UPLOADS, os.path.basename(key or "")) if key else None
        if local and os.path.isfile(local):
            try:
                os.remove(local)
            except OSError as e:
                print("  ERRO local:", nome[:80], e)
        cur.execute("delete from file where id = %s", (fid,))
        conn.commit()
        feitos += 1
        print("  apagado:", nome[:90])
    conn.close()
    print("gerados-antigos: %d apagados." % feitos)


def anexos_antigos(args):
    corte = time.time() - args.dias * 86400
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        select f.id, f.filename, count(dc.id), f.updated_at
          from file f
          join document_chunk dc on dc.collection_name = 'file-' || f.id
         where f.id not in (select file_id from knowledge_file)
           and f.updated_at < %s
         group by f.id, f.filename, f.updated_at
         order by f.updated_at
        """,
        (corte,),
    )
    linhas = cur.fetchall()
    chunks = sum(r[2] for r in linhas)
    cur.execute("select pg_total_relation_size('document_chunk'), count(*) from document_chunk")
    tam, n = cur.fetchone()
    estimativa = chunks * tam / max(n, 1)
    print("anexos-antigos (> %d dias): %d anexos, %d chunks, ~%s da tabela document_chunk"
          % (args.dias, len(linhas), chunks, mb(estimativa)))
    for fid, nome, c, ts in linhas[:20]:
        print("   ", time.strftime("%Y-%m-%d", time.gmtime(ts)), c, "chunks", (nome or "")[:80])
    if len(linhas) > 20:
        print("    ... (+%d)" % (len(linhas) - 20))
    if not args.executar:
        print("SIMULACAO: nada apagado. Use --executar.")
        conn.close()
        return
    feitos = 0
    for fid, nome, c, ts in linhas:
        if args.limite and feitos >= args.limite:
            print("limite de %d atingido." % args.limite)
            break
        cur.execute("delete from document_chunk where collection_name = %s", ("file-" + fid,))
        conn.commit()
        feitos += 1
        print("  indice apagado (%d chunks):" % c, (nome or "")[:80])
    conn.close()
    print("anexos-antigos: %d anexos tirados do indice. Arquivos ficam no R2 e em `file`." % feitos)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modo", choices=["orfaos-locais", "gerados-antigos", "anexos-antigos"])
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--dias", type=int, default=None)
    ap.add_argument("--limite", type=int, default=0)
    args = ap.parse_args()
    if args.dias is None:
        args.dias = {"gerados-antigos": 30, "anexos-antigos": 60}.get(args.modo, 0)
    print("modo=%s executar=%s dias=%s limite=%s" % (args.modo, args.executar, args.dias, args.limite))
    {"orfaos-locais": orfaos_locais, "gerados-antigos": gerados_antigos, "anexos-antigos": anexos_antigos}[args.modo](args)


if __name__ == "__main__":
    sys.exit(main())
