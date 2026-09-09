"""Extrai e testa as funcoes puras (sem dependencia QGIS) do script revisado."""
import ast, math, re, pathlib

fonte = (pathlib.Path(__file__).resolve().parent.parent / 'associacao_oae_snv.py').read_text(encoding='utf-8')
arvore = ast.parse(fonte)
linhas = fonte.splitlines(True)

alvos = {"numero_finito_positivo", "numero_finito", "normalizar_via",
         "prefixo_codigo", "quase_igual", "formatar_lista_codigos",
         "observacao_texto", "resolver_orientacao"}
consts = {"TOLERANCIA_CONEXAO_M", "TAMANHO_MAX_OBS", "LIMITE_CODIGOS_LISTADOS"}

ns = {"math": math, "re": re, "NULL": object()}
trechos = []
for no in arvore.body:
    if isinstance(no, ast.Assign) and getattr(no.targets[0], "id", None) in consts:
        trechos.append(ast.get_source_segment(fonte, no))
    if isinstance(no, ast.FunctionDef) and no.name in alvos:
        trechos.append(ast.get_source_segment(fonte, no))
# codigo_valido depende de NULL; incluir
for no in arvore.body:
    if isinstance(no, ast.FunctionDef) and no.name == "codigo_valido":
        trechos.insert(0, ast.get_source_segment(fonte, no))
exec("\n\n".join(trechos), ns)

g = ns
ok = 0
def checa(rotulo, obtido, esperado):
    global ok
    assert obtido == esperado, f"FALHOU {rotulo}: obtido={obtido!r} esperado={esperado!r}"
    ok += 1

# --- normalizacao da Via ---
for entrada, esperado in [
    ("BR-453", "453"), ("BR-70", "070"), ("BR 70", "070"), ("116", "116"),
    ("70,0", "070"), ("70.0", "070"), ("BR–101", "101"),
    ("BR-116/BR-101", None), ("1160", None), ("", None), (None, None),
    ("Rodovia", None), ("BR-", None), ("  BR-232 ", "232"),
]:
    checa(f"normalizar_via({entrada!r})", g["normalizar_via"](entrada), esperado)

# --- prefixo do vl_codigo ---
for entrada, esperado in [("116BMG0450", "116"), ("070BRO0010", "070"),
                          ("AB1BMG0450", None), ("12", None), (None, None)]:
    checa(f"prefixo_codigo({entrada!r})", g["prefixo_codigo"](entrada), esperado)

# --- saneamento numerico ---
checa("extensao True", g["numero_finito_positivo"](True), None)
checa("extensao 0", g["numero_finito_positivo"](0), None)
checa("extensao -5", g["numero_finito_positivo"](-5), None)
checa("extensao 12.5", g["numero_finito_positivo"]("12.5"), 12.5)
checa("km 0", g["numero_finito"](0), 0.0)
checa("km inf", g["numero_finito"](float("inf")), None)

# --- listagem de codigos concorrentes (deterministica) ---
checa("lista curta", g["formatar_lista_codigos"](["b", "a"]), "a,b")
checa("lista longa", g["formatar_lista_codigos"]([f"c{i}" for i in range(9)], 3),
      "c0,c1,c2,+6")

# --- truncamento da observacao ---
longo = g["observacao_texto"]("X" * 400)
checa("obs truncada", len(longo), g["TAMANHO_MAX_OBS"])
assert longo.endswith("...[TRUNCADO]")
checa("obs vazia", g["observacao_texto"](None, ""), None)
checa("obs ordem", g["observacao_texto"]("A", None, "B"), "A; B")

# --- resolver_orientacao ---
R = g["resolver_orientacao"]
A, B = (0.0, 0.0), (1000.0, 0.0)          # trecho avaliado: extremo0=A, extremo1=B
ANT = ((-500.0, 0.0), (0.0, 0.0))          # vizinho anterior toca A
POS = ((1000.0, 0.0), (1500.0, 0.0))       # vizinho posterior toca B

r = R((A, B), [(1, "ANT1", ANT)], [])
checa("so anterior -> sentido", r["sentido"], "INICIO_GEOM_KM_INIC")
checa("so anterior -> evidencia", r["evidencia"], "ANTERIOR")
checa("so anterior -> codigo", r["anterior"], "ANT1")

r = R((A, B), [], [(2, "POS1", POS)])
checa("so posterior -> sentido", r["sentido"], "INICIO_GEOM_KM_INIC")
checa("so posterior -> evidencia", r["evidencia"], "POSTERIOR")

r = R((A, B), [(1, "ANT1", ANT)], [(2, "POS1", POS)])
checa("ambos -> sentido", r["sentido"], "INICIO_GEOM_KM_INIC")
checa("ambos -> evidencia", r["evidencia"], "AMBOS")

# geometria armazenada ao contrario: extremo0 = B
r = R((B, A), [(1, "ANT1", ANT)], [(2, "POS1", POS)])
checa("invertida -> sentido", r["sentido"], "INICIO_GEOM_KM_FINAL")

# sem vizinhos
checa("sem vizinho", R((A, B), [], [])["motivo"], "SEM_VIZINHO_COMPATIVEL")

# dois anteriores concorrentes
r = R((A, B), [(1, "X", ANT), (2, "Y", ANT)], [])
checa("dois anteriores", r["motivo"], "CONEXAO_AMBIGUA")

# vizinho que toca os dois extremos (anel)
ANEL = ((0.0, 0.0), (1000.0, 0.0))
checa("anel", R((A, B), [(1, "X", ANEL)], [])["motivo"], "CONEXAO_AMBIGUA")

# anterior e posterior no MESMO extremo -> contradicao
POS_EM_A = ((0.0, 0.0), (0.0, 900.0))
checa("conflito", R((A, B), [(1, "X", ANT)], [(2, "Y", POS_EM_A)])["motivo"],
      "VIZINHOS_CONFLITANTES")

# tolerancia de conexao: 0,99 m conecta; 1,01 m nao
QUASE = ((-500.0, 0.0), (0.99, 0.0))
checa("conexao 0,99 m", R((A, B), [(1, "X", QUASE)], [])["sentido"], "INICIO_GEOM_KM_INIC")
LONGE = ((-500.0, 0.0), (1.01, 0.0))
checa("conexao 1,01 m", R((A, B), [(1, "X", LONGE)], [])["motivo"], "SEM_VIZINHO_COMPATIVEL")

# independencia da ordem de leitura dos vizinhos
r1 = R((A, B), [(1, "X", ANT), (2, "Y", ANT)], [])
r2 = R((A, B), [(2, "Y", ANT), (1, "X", ANT)], [])
checa("ordem irrelevante", r1, r2)

print(f"{ok} verificacoes OK")
