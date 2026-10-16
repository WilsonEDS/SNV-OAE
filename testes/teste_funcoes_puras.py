"""Extrai e testa as funcoes puras (sem dependencia QGIS) do script revisado."""
import ast, math, re, pathlib

fonte = (pathlib.Path(__file__).resolve().parent.parent / 'associacao_oae_snv.py').read_text(encoding='utf-8')
arvore = ast.parse(fonte)
linhas = fonte.splitlines(True)

alvos = {"numero_finito_positivo", "numero_finito", "normalizar_via",
         "prefixo_codigo", "quase_igual", "formatar_lista_codigos",
         "truncar_texto", "observacao_texto", "interpolar_km",
         "preparar_trechos"}
consts = {"TAMANHO_MAX_OBS", "LIMITE_CODIGOS_LISTADOS", "CAMPO_VL_KM_INIC",
          "CAMPO_VL_KM_FINA"}

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

# --- interpolacao do km pelo sentido de digitalizacao ---
I = g["interpolar_km"]
# Trecho do km 100,000 ao km 112,000, digitalizado no sentido crescente.
checa("fracao 0 -> km inicial (primeiro vertice)", I(100.0, 112.0, 0.0), 100.0)
checa("fracao 1 -> km final (ultimo vertice)", I(100.0, 112.0, 1.0), 112.0)
checa("fracao 0,5 -> meio do trecho", I(100.0, 112.0, 0.5), 106.0)
checa("fracao 0,25", I(100.0, 112.0, 0.25), 103.0)
# Trecho iniciado no km 0.
checa("trecho a partir do km 0", I(0.0, 8.4, 0.5), 4.2)
# A fracao e limitada a [0, 1]: nenhum km fora do intervalo do trecho.
checa("fracao negativa limitada a 0", I(100.0, 112.0, -0.3), 100.0)
checa("fracao acima de 1 limitada a 1", I(100.0, 112.0, 1.7), 112.0)
# Monotonia: avancar ao longo da linha nunca diminui o km.
kms = [I(100.0, 112.0, f / 100) for f in range(101)]
checa("km cresce ao longo da digitalizacao", kms == sorted(kms), True)
checa("km sempre dentro do intervalo", all(100.0 <= k <= 112.0 for k in kms), True)

# --- preparo dos trechos SNV (geometria simulada) ---
class Feicao(dict):
    """Simula QgsFeature: acesso por campo e geometry()."""
    def __init__(self, ki, kf, geometria="LINHA"):
        super().__init__(vl_km_inic=ki, vl_km_fina=kf)
        self._geometria = geometria
    def geometry(self):
        return self._geometria

# preparar_linha real depende do QGIS; aqui devolve a causa codificada na geometria.
g["preparar_linha"] = lambda geom: (geom, None) if geom == "LINHA" else (None, geom)
P = g["preparar_trechos"]
r = P({
    1: Feicao(100.0, 112.0),
    2: Feicao(112.0, 100.0),                      # kf < ki
    3: Feicao(50.0, 50.0),                        # kf == ki
    4: Feicao(-1.0, 5.0),                         # ki negativo
    5: Feicao(None, 5.0),                         # ki ausente
    6: Feicao(0.0, 3.0),                          # trecho a partir do km 0
    7: Feicao(10.0, 20.0, "GEOMETRIA_SNV_MULTIPARTE"),
    8: Feicao(-5.0, 1.0, "GEOMETRIA_SNV_MULTIPARTE"),  # intervalo tem precedencia
})
checa("trecho apto", (r[1]["erro"], r[1]["linha"], r[1]["ki"], r[1]["kf"]),
      (None, "LINHA", 100.0, 112.0))
for fid in (2, 3, 4, 5):
    checa(f"intervalo invalido fid {fid}", r[fid]["erro"], "INTERVALO_KM_INVALIDO")
    checa(f"sem linha quando intervalo invalido fid {fid}", r[fid]["linha"], None)
checa("trecho a partir do km 0 e apto", r[6]["erro"], None)
checa("multiparte recusado", r[7]["erro"], "GEOMETRIA_SNV_MULTIPARTE")
checa("intervalo avaliado antes da geometria", r[8]["erro"], "INTERVALO_KM_INVALIDO")

print(f"{ok} verificacoes OK")
