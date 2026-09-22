"""Extrai e testa as funcoes puras (sem dependencia QGIS) de trechos_coincidentes.py."""
import ast, pathlib

fonte = (pathlib.Path(__file__).resolve().parent.parent / 'trechos_coincidentes.py').read_text(encoding='utf-8')
arvore = ast.parse(fonte)

alvos = {"codigo_valido", "prefixo_codigo", "truncar_texto",
         "separar_codigos", "prefixos_coincidentes"}
consts = {"SEPARADOR_CODIGOS", "MINIMO_CODIGOS", "TAMANHO_MAX_TRECHOS"}

ns = {"NULL": object()}
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

# --- 1) caso do enunciado ---
checa("enunciado",
      g["prefixos_coincidentes"]("010BDF0015;020BDF0015;030BDF0015"),
      ("010;020;030", 3, 0))

# --- 2) quebra de ds_coinc em codigos ---
for entrada, esperado in [
    ("010BDF0015;020BDF0015", ["010BDF0015", "020BDF0015"]),
    ("010BDF0015", ["010BDF0015"]),
    (" 010BDF0015 ; ;020BDF0015;", ["010BDF0015", "020BDF0015"]),
    (";;;", []),
    ("", []),
    (None, []),
    ("NULL", []),
    ("NaN", []),
    ("   ", []),
]:
    checa(f"separar_codigos({entrada!r})", g["separar_codigos"](entrada), esperado)

# --- 3) selecao: "mais de um codigo" conta codigos nao vazios ---
# Um codigo seguido de separador nao e coincidencia.
checa("um codigo com separador final",
      len(g["separar_codigos"]("010BDF0015;")) >= g["MINIMO_CODIGOS"], False)
checa("dois codigos",
      len(g["separar_codigos"]("010BDF0015;020BDF0015")) >= g["MINIMO_CODIGOS"], True)
checa("nulo nao entra",
      len(g["separar_codigos"](None)) >= g["MINIMO_CODIGOS"], False)

# --- 4) ordem preservada e duplicatas mantidas ---
checa("ordem preservada",
      g["prefixos_coincidentes"]("030BDF0015;010BDF0015;020BDF0015")[0], "030;010;020")
checa("duplicatas mantidas",
      g["prefixos_coincidentes"]("010BDF0015;010BDF0020")[0], "010;010")

# --- 5) espacos e separadores vazios ---
checa("ruido de formatacao",
      g["prefixos_coincidentes"](" 010BDF0015 ; ;020BDF0015;"), ("010;020", 2, 0))

# --- 6) codigos fora do padrao: descartados e contados ---
checa("um token invalido",
      g["prefixos_coincidentes"]("010BDF0015;ABCBDF0015"), ("010", 2, 1))
checa("codigo curto",
      g["prefixos_coincidentes"]("010BDF0015;12"), ("010", 2, 1))
checa("todos invalidos",
      g["prefixos_coincidentes"]("ABCBDF0015;XYZBDF0015"), (None, 2, 2))
# A feicao com todos os tokens invalidos AINDA e coincidente: a contagem de
# codigos permanece 2, so o texto fica nulo.
checa("selecao independe do padrao do codigo",
      g["prefixos_coincidentes"]("ABCBDF0015;XYZBDF0015")[1] >= g["MINIMO_CODIGOS"], True)

# --- 7) nulos e sentinelas ---
for entrada in [None, "", "NULL", "None", "NaN", "   "]:
    checa(f"prefixos_coincidentes({entrada!r})",
          g["prefixos_coincidentes"](entrada), (None, 0, 0))

# --- 8) prefixo de tres digitos ---
for entrada, esperado in [("116BMG0450", "116"), ("070BRO0010", "070"),
                          ("010BDF0015", "010"), ("AB1BMG0450", None),
                          ("12", None), ("", None), (None, None)]:
    checa(f"prefixo_codigo({entrada!r})", g["prefixo_codigo"](entrada), esperado)

# --- 9) truncamento no comprimento do campo ---
muitos = g["SEPARADOR_CODIGOS"].join(f"{i:03d}BDF0015" for i in range(200))
texto, qtd, descartados = g["prefixos_coincidentes"](muitos)
checa("truncado no limite", len(texto), g["TAMANHO_MAX_TRECHOS"])
checa("truncamento sinalizado", texto.endswith("...[TRUNCADO]"), True)
checa("contagem nao truncada", (qtd, descartados), (200, 0))

# --- 10) determinismo: mesma entrada, mesmo resultado ---
entrada = "010BDF0015;ABC;020BDF0015"
checa("determinismo",
      g["prefixos_coincidentes"](entrada), g["prefixos_coincidentes"](entrada))

print(f"{ok} verificacoes OK")
