"""Extrai e testa as funcoes puras (sem dependencia QGIS) de trechos_coincidentes_m2.py."""
import ast, math, pathlib

raiz = pathlib.Path(__file__).resolve().parent.parent
fonte = (raiz / 'trechos_coincidentes_m2.py').read_text(encoding='utf-8')
arvore = ast.parse(fonte)

alvos = {"codigo_valido", "prefixo_codigo", "truncar_texto", "texto_bruto",
         "motivo_exclusao", "texto_rodovias", "tipo_coincidencia",
         "classificar_sobreposicao", "rotulo_grupo"}
consts = {"SEPARADOR_CODIGOS", "TAMANHO_MAX_TRECHOS", "SUPERFICIE_EXCLUIDA",
          "JURISDICAO_EXIGIDA", "MOTIVOS_EXCLUSAO", "LIMIAR_SOBREPOSICAO_TOTAL",
          "TIPOS_COINC", "TIPOS_SOBREP"}

ns = {"math": math, "NULL": object()}
trechos = []
# A ordem do arquivo ja traz as constantes antes das funcoes que as usam.
for no in arvore.body:
    if isinstance(no, ast.Assign) and getattr(no.targets[0], "id", None) in consts:
        trechos.append(ast.get_source_segment(fonte, no))
    if isinstance(no, ast.FunctionDef) and no.name in alvos:
        trechos.append(ast.get_source_segment(fonte, no))
exec("\n\n".join(trechos), ns)

g = ns
faltando = sorted(alvos - set(g)) + sorted(consts - set(g))
assert not faltando, f"nao extraido do script: {faltando}"

ok = 0
def checa(rotulo, obtido, esperado):
    global ok
    assert obtido == esperado, f"FALHOU {rotulo}: obtido={obtido!r} esperado={esperado!r}"
    ok += 1

# --- 1) BRs que dividem o eixo: propria primeiro, parceiras em ordem ---
checa("propria primeiro",
      g["texto_rodovias"]("020", {"010", "030"}), "020;010;030")
checa("uma parceira", g["texto_rodovias"]("020", {"010"}), "020;010")
# Parceira da mesma BR: geometria duplicada, uma unica BR no texto.
checa("mesma BR", g["texto_rodovias"]("010", {"010"}), "010")
checa("mesma BR e outra", g["texto_rodovias"]("010", {"010", "020"}), "010;020")
# Sem BR propria identificavel, so as parceiras, ordenadas.
checa("sem BR propria", g["texto_rodovias"](None, {"030", "010"}), "010;030")
# Sem parceira identificavel o campo e nulo: escrever so a BR propria
# descreveria o trecho como eixo exclusivo dela, o oposto do que se provou.
checa("parceira sem BR", g["texto_rodovias"]("020", {None}), None)
checa("sem parceiras", g["texto_rodovias"]("020", set()), None)
checa("nada", g["texto_rodovias"](None, set()), None)

# --- 2) determinismo: a ordem do conjunto de entrada nao altera a saida ---
checa("determinismo texto_rodovias",
      g["texto_rodovias"]("020", ["030", "010", "030"]),
      g["texto_rodovias"]("020", ["010", "030"]))
checa("determinismo lista vs set",
      g["texto_rodovias"]("020", ["010", "030"]),
      g["texto_rodovias"]("020", {"030", "010"}))

# --- 3) natureza da coincidencia ---
checa("entre BRs", g["tipo_coincidencia"]("020", {"010"}), "ENTRE_BRS")
checa("entre BRs varias", g["tipo_coincidencia"]("020", {"010", "030"}), "ENTRE_BRS")
checa("mesma BR", g["tipo_coincidencia"]("010", {"010"}), "MESMA_BR")
checa("ambos", g["tipo_coincidencia"]("010", {"010", "020"}), "AMBOS")
# Sem a BR propria nao ha como comparar; o caso e nomeado em vez de ser
# classificado como ENTRE_BRS, que afirmaria diferenca sem prova.
checa("BR propria ausente", g["tipo_coincidencia"](None, {"010"}), "INDETERMINADO")
checa("parceira sem BR", g["tipo_coincidencia"]("010", {None}), None)
checa("sem parceiras", g["tipo_coincidencia"]("010", set()), None)
# Os tipos devolvidos sao os declarados.
tipos_possiveis = {
    g["tipo_coincidencia"](p_, set(parc_))
    for p_ in [None, "010", "020"]
    for parc_ in [(), (None,), ("010",), ("020",), ("010", "020"), ("010", None)]
}
checa("tipos declarados", tipos_possiveis - {None} <= set(g["TIPOS_COINC"]), True)

# --- 4) TOTAL x PARCIAL ---
checa("cobertura total", g["classificar_sobreposicao"](10.0, 10.0), (1.0, "TOTAL"))
checa("acima do limiar", g["classificar_sobreposicao"](9.995, 10.0)[1], "TOTAL")
checa("abaixo do limiar", g["classificar_sobreposicao"](9.98, 10.0)[1], "PARCIAL")
checa("parcial franca", g["classificar_sobreposicao"](1.0, 10.0), (0.1, "PARCIAL"))
# O limiar e inclusivo.
limiar = g["LIMIAR_SOBREPOSICAO_TOTAL"]
checa("limiar inclusivo", g["classificar_sobreposicao"](limiar, 1.0)[1], "TOTAL")
checa("limiar e 0.999", limiar, 0.999)

# --- 5) extensao indeterminada nao vira zero nem um ---
for ext_sobrep, ext_trecho in [
    (5.0, 0.0), (5.0, -1.0), (5.0, None), (5.0, float("nan")), (5.0, float("inf")),
    (None, 10.0), (float("nan"), 10.0), (float("inf"), 10.0), (-1.0, 10.0),
]:
    checa(f"indeterminado ({ext_sobrep!r}, {ext_trecho!r})",
          g["classificar_sobreposicao"](ext_sobrep, ext_trecho), (None, "INDETERMINADO"))
checa("tipos de sobreposicao declarados",
      {g["classificar_sobreposicao"](1.0, 10.0)[1],
       g["classificar_sobreposicao"](10.0, 10.0)[1],
       g["classificar_sobreposicao"](1.0, 0.0)[1]} <= set(g["TIPOS_SOBREP"]), True)

# --- 6) truncamento no comprimento do campo ---
muitas = [f"{i:03d}" for i in range(200)]
texto = g["texto_rodovias"]("999", muitas)
checa("truncado no limite", len(texto), g["TAMANHO_MAX_TRECHOS"])
checa("truncamento sinalizado", texto.endswith("...[TRUNCADO]"), True)
checa("BR propria sobrevive ao corte", texto.startswith("999;"), True)

# --- 7) funcoes copiadas do m1: filtro de superficie e jurisdicao ---
for superficie in ["ASF", "IMP", "LEN"]:
    checa(f"passa ({superficie}, Federal)",
          g["motivo_exclusao"](superficie, "Federal"), None)
checa("planejado", g["motivo_exclusao"]("PLA", "Federal"), "SUPERFICIE_PLANEJADA")
checa("estadual", g["motivo_exclusao"]("ASF", "Estadual"), "JURISDICAO_DIVERGENTE")
checa("caixa importa", g["motivo_exclusao"]("ASF", "federal"), "JURISDICAO_DIVERGENTE")
checa("superficie nula", g["motivo_exclusao"](None, "Federal"), "SUPERFICIE_NULA")
checa("jurisdicao nula", g["motivo_exclusao"]("ASF", None), "JURISDICAO_NULA")
checa("vazia nao e nula", g["motivo_exclusao"]("", "Federal"), None)
checa("sem strip", g["motivo_exclusao"]("ASF", " Federal "), "JURISDICAO_DIVERGENTE")
checa("constantes do filtro",
      (g["SUPERFICIE_EXCLUIDA"], g["JURISDICAO_EXIGIDA"]), ("PLA", "Federal"))

# --- 8) prefixo de tres digitos e rotulo dos grupos ---
for entrada, esperado in [("116BMG0450", "116"), ("010BDF0015", "010"),
                          ("AB1BMG0450", None), ("12", None), (None, None)]:
    checa(f"prefixo_codigo({entrada!r})", g["prefixo_codigo"](entrada), esperado)
checa("rotulo normal", g["rotulo_grupo"]("DF", "020;010"), "DF: 020;010")
checa("rotulo sem BR", g["rotulo_grupo"]("DF", None), "DF: (sem BR identificada)")
checa("rotulo sem UF", g["rotulo_grupo"](None, "010"), "(sem UF): 010")

# --- 9) as copias do m1 nao divergiram do original ---
# O script m2 declara copiar verbatim as funcoes puras do m1. Uma divergencia
# silenciosa entre as duas copias faria as metodologias filtrarem universos
# diferentes e a comparacao entre elas perderia sentido.
fonte_m1 = (raiz / 'trechos_coincidentes.py').read_text(encoding='utf-8')
arvore_m1 = ast.parse(fonte_m1)

def corpo_sem_docstring(no):
    """Devolve o ast.dump do corpo da funcao, descartando a docstring."""
    corpo = list(no.body)
    if (corpo and isinstance(corpo[0], ast.Expr)
            and isinstance(corpo[0].value, ast.Constant)
            and isinstance(corpo[0].value.value, str)):
        corpo = corpo[1:]
    return ast.dump(ast.Module(body=corpo, type_ignores=[]))

copiadas = {"codigo_valido", "prefixo_codigo", "truncar_texto", "texto_bruto",
            "motivo_exclusao", "rotulo_grupo"}
m1 = {no.name: no for no in arvore_m1.body
      if isinstance(no, ast.FunctionDef) and no.name in copiadas}
m2 = {no.name: no for no in arvore.body
      if isinstance(no, ast.FunctionDef) and no.name in copiadas}
checa("todas as copiadas existem nos dois", (set(m1), set(m2)), (copiadas, copiadas))
for nome in sorted(copiadas):
    checa(f"{nome} identica ao m1",
          corpo_sem_docstring(m2[nome]), corpo_sem_docstring(m1[nome]))

print(f"{ok} verificacoes OK")
