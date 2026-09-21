# -*- coding: ascii -*-
"""
MEDIDOR do orcamento de contexto por turno - le o log e devolve a REGUA.

O QUE ELE FAZ: recebe um despejo de log do ChatND (Railway -> Deployments ->
View logs -> Download, ou o arquivo que a `bateria_orcamento.py` escreve) e
reconstroi o consumo POR TURNO a partir das linhas que o `nidum_orcamento` emite.

As duas linhas que ele procura:

  INFO  nidum_orcamento: query_knowledge_files +8590 chars (turno: 8590/45000)
  WARN  nidum_orcamento: view_file ESTOUROU o turno (103200/45000, +94610) modo=seco

PEDIDO x ENTREGUE - e esta distincao e a correcao de 21/09/2026, sem a qual a
regua NAO PODE FECHAR:

  o contador do `nidum_orcamento` soma o tamanho PEDIDO, tambem quando corta
  (`setattr(..., usado + tamanho)` acontece nos dois ramos). Entao o acumulado
  que aparece no log e a DEMANDA do turno, nao o que entrou no contexto. Com o
  corte LIGADO, um `view_file` de 100.000 chars continua escrevendo
  "(100000/45000)" no log - o modelo recebeu 45.000, o log registra 100.000.

  Lendo o acumulado como se fosse o entregue, a "cauda acima do teto" NUNCA vai
  a zero na fase 2, e o veredito acusaria "o corte nao esta ativo" com o corte
  ativo. Falso negativo, na unica leitura que decide a rodada.

  O entregue e RECONSTRUTIVEL do proprio log, sem mexer no backend: a linha de
  estouro traz o acumulado e o tamanho, entao
      usado_antes = acumulado - tamanho
      sobra       = teto - usado_antes
      entregue    = max(0, min(tamanho, sobra))   (so quando modo=ATIVO)
  Em modo seco nada e cortado e entregue == pedido - por isso a fase 1 mede
  igual antes e a correcao nao reescreve numero nenhum ja apurado.

COMO SEPARA OS TURNOS. Dois caminhos, e o primeiro dispensa heuristica:

  1. MARCADORES. Se o arquivo tiver linhas `#turno <rotulo>`, elas cortam os
     turnos - e a separacao e exata. E o que a `bateria_orcamento.py` escreve:
     ela roda um turno por vez e sabe onde cada um comeca. Nesse caminho nao
     importa quantas pessoas estao na instancia.
  2. QUEDA DO ACUMULADO (o caminho do despejo cru). O acumulado e monotonico
     crescente DENTRO de um turno e recomeca do zero no seguinte (o estado vive
     em `request.state`), entao toda vez que ele CAI, comecou outro turno.
     LIMITE: duas conversas simultaneas intercalam linhas e a separacao erra.
     Rode a bateria com UMA pessoa so na instancia, ou use os marcadores.

A REGUA TEM DOIS NUMEROS, e o segundo e o que importa (ver o docstring de
nidum_orcamento.py):

  1. a CAUDA acima do teto - deve sumir quando o corte liga. E o objetivo.
     Medida no ENTREGUE: e o que de fato entrou no contexto.
  2. a MEDIANA - NAO deve se mover. E a prova de que o teto pegou so a cauda.
     Se a mediana cair, o orcamento virou mordaca e o teto esta baixo demais.

E a DEMANDA fica na tela ao lado, porque ela nao e ruido: e quanto o modelo
pediu. Demanda que cresce com o corte ligado quer dizer que ele esta insistindo,
e isso se ve aqui antes de virar reclamacao de quem usa.

USO:
  py -3 medir_orcamento.py <arquivo_de_log> [--teto 45000]
  py -3 medir_orcamento.py antes.log depois.log      (compara as duas fases)
"""

import io
import os
import re
import sys

RE_SOMA = re.compile(r"nidum_orcamento: (\S+) \+(\d+) chars \(turno: (\d+)/(\d+)\)")
RE_ESTOURO = re.compile(
    r"nidum_orcamento: (\S+) ESTOUROU o turno \((\d+)/(\d+), \+(\d+)\) modo=(\w+)")
RE_MARCADOR = re.compile(r"^#turno\b(.*)$")


class Turno(object):
    """Um turno: o que foi PEDIDO e o que foi ENTREGUE."""

    def __init__(self, rotulo=""):
        self.rotulo = rotulo.strip()
        self.pedido = 0
        self.entregue = 0
        self.cortes = 0

    def __repr__(self):
        return "<turno %s pedido=%d entregue=%d>" % (
            self.rotulo or "?", self.pedido, self.entregue)


def _entregue_do_estouro(acum, tamanho, teto, modo):
    """Quanto CHEGOU ao contexto nesta chamada cortada.

    Em seco nada e cortado: entregue == pedido. Em ATIVO, o que cabia na sobra -
    e a sobra se reconstroi do proprio log (ver o docstring).
    """
    if modo.upper() != "ATIVO":
        return tamanho
    usado_antes = acum - tamanho
    return max(0, min(tamanho, teto - usado_antes))


def ler(caminho):
    """Devolve (turnos, teto, modos, por_tool)."""
    turnos, teto, modos, por_tool = [], None, set(), {}
    atual = None
    com_marcador = False

    def fecha(t):
        if t is not None and (t.pedido or t.entregue or t.rotulo):
            turnos.append(t)

    with io.open(caminho, encoding="utf-8", errors="replace") as fh:
        for linha in fh:
            mm = RE_MARCADOR.match(linha.strip())
            if mm:
                com_marcador = True
                fecha(atual)
                atual = Turno(mm.group(1))
                continue
            m = RE_SOMA.search(linha) or RE_ESTOURO.search(linha)
            if not m:
                continue
            if m.re is RE_SOMA:
                tool = m.group(1)
                tamanho, acum, t = int(m.group(2)), int(m.group(3)), int(m.group(4))
                entregue = tamanho
            else:
                tool, modo = m.group(1), m.group(5)
                acum, t, tamanho = int(m.group(2)), int(m.group(3)), int(m.group(4))
                modos.add(modo)
                entregue = _entregue_do_estouro(acum, tamanho, t, modo)
            teto = t
            por_tool[tool] = por_tool.get(tool, 0) + 1
            # Sem marcador, a QUEDA do acumulado PEDIDO abre turno novo.
            if atual is None:
                atual = Turno()
            elif not com_marcador and acum < atual.pedido:
                fecha(atual)
                atual = Turno()
            atual.pedido = max(atual.pedido, acum)
            atual.entregue += entregue
            if entregue < tamanho:
                atual.cortes += 1
    fecha(atual)
    return turnos, teto, modos, por_tool


def pct(v, q):
    if not v:
        return 0
    s = sorted(v)
    return s[min(len(s) - 1, int(len(s) * q))]


def regua(nome, turnos, teto):
    if not turnos:
        print("%s: NENHUM turno medido - o log nao tem linhas 'nidum_orcamento'." % nome)
        print("    Cheque: (a) o codigo esta no ar? (b) GLOBAL_LOG_LEVEL deixa passar INFO?")
        print("    (c) o turno usou FERRAMENTA? sem tool call nao ha o que orcar.")
        return None
    ent = [t.entregue for t in turnos]
    ped = [t.pedido for t in turnos]
    acima = [v for v in ent if v > teto]
    d = {
        "n": len(turnos),
        "mediana": pct(ent, .5),
        "p75": pct(ent, .75),
        "p90": pct(ent, .90),
        "max": max(ent),
        "acima": len(acima),
        "pior": max(acima) if acima else 0,
        "med_pedido": pct(ped, .5),
        "max_pedido": max(ped),
        "cortes": sum(t.cortes for t in turnos),
    }
    print("%s" % nome)
    print("  turnos medidos ........ %d          <- o DENOMINADOR" % d["n"])
    print("  teto declarado ........ %d chars" % teto)
    print("  MEDIANA (entregue) .... %d chars    <- NAO deve se mover entre as fases" % d["mediana"])
    print("  p75 ................... %d chars" % d["p75"])
    print("  p90 ................... %d chars" % d["p90"])
    print("  maximo ................ %d chars" % d["max"])
    print("  CAUDA acima do teto ... %d de %d (%.1f%%)  <- deve ir a ZERO com o corte"
          % (d["acima"], d["n"], 100.0 * d["acima"] / d["n"]))
    if acima:
        print("  pior turno ............ %d chars (%.1fx o teto)" % (d["pior"], 1.0 * d["pior"] / teto))
    print("  DEMANDA mediana/maxima  %d / %d chars   (o que o modelo PEDIU)"
          % (d["med_pedido"], d["max_pedido"]))
    print("  chamadas cortadas ..... %d" % d["cortes"])
    print("  por turno:")
    for t in turnos:
        marca = "  CORTOU" if t.cortes else ""
        print("      %-28s entregue=%8d  pedido=%8d%s"
              % ((t.rotulo or "(sem rotulo)")[:28], t.entregue, t.pedido, marca))
    return d


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    teto_cli = None
    for i, a in enumerate(sys.argv[1:], start=1):
        if a.startswith("--teto"):
            teto_cli = int(a.split("=")[-1] if "=" in a else sys.argv[i + 1])
    if not args:
        print(__doc__)
        return 2

    resultados = []
    for caminho in args[:2]:
        if not os.path.exists(caminho):
            print("nao encontrei: %s" % caminho)
            return 2
        turnos, teto, modos, por_tool = ler(caminho)
        teto = teto_cli or teto or 45000
        print("=" * 70)
        d = regua(os.path.basename(caminho), turnos, teto)
        if d:
            print("  modo no log ........... %s" % (", ".join(sorted(modos)) or "(sem estouro registrado)"))
            print("  chamadas por tool:")
            for t, n in sorted(por_tool.items(), key=lambda x: -x[1]):
                print("      %-28s %d" % (t, n))
        resultados.append(d)
        print("")

    if len(resultados) == 2 and all(resultados):
        antes, depois = resultados
        print("=" * 70)
        print("A REGUA (antes -> depois)")
        print("")
        dm = depois["mediana"] - antes["mediana"]
        var = (100.0 * dm / antes["mediana"]) if antes["mediana"] else 0
        print("  MEDIANA    %d -> %d  (%+d, %+.1f%%)" % (antes["mediana"], depois["mediana"], dm, var))
        print("  CAUDA      %d -> %d turno(s) acima do teto" % (antes["acima"], depois["acima"]))
        print("  MAXIMO     %d -> %d chars" % (antes["max"], depois["max"]))
        print("  DEMANDA    %d -> %d chars (mediana)" % (antes["med_pedido"], depois["med_pedido"]))
        print("")
        ok_cauda = depois["acima"] == 0
        ok_mediana = abs(var) <= 10
        print("  [%s] a cauda sumiu" % ("OK " if ok_cauda else "NAO"))
        print("  [%s] a mediana nao se moveu (tolerancia 10%%)" % ("OK " if ok_mediana else "NAO"))
        print("")
        if ok_cauda and ok_mediana:
            print("  VEREDITO: o teto pegou SO a cauda. Pode ficar ligado.")
        elif not ok_cauda:
            print("  VEREDITO: ainda ha turno acima do teto NO ENTREGUE. Com o corte")
            print("            ativo isso e aritmeticamente impossivel pelo caminho do")
            print("            `process_tool_result` - entao ou a variavel nao esta em")
            print("            ATIVO (veja 'modo no log'), ou existe tool que devolve")
            print("            conteudo por FORA daquele ponto unico.")
        else:
            print("  VEREDITO: a MEDIANA CAIU. O teto virou mordaca - ele esta cortando")
            print("            turno normal, nao so a cauda. SUBA o teto e meca de novo.")
            print("            (o objetivo era a cauda; se o meio doeu, o numero esta errado)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
