"""Extrai e testa as funcoes puras (sem dependencia QGIS) do script revisado."""
import ast, math, re, pathlib

fonte = (pathlib.Path(__file__).resolve().parent.parent / 'associacao_oae_snv.py').read_text(encoding='utf-8')
arvore = ast.parse(fonte)
linhas = fonte.splitlines(True)

alvos = {"numero_finito_positivo", "numero_finito", "normalizar_via",
         "prefixo_codigo", "quase_igual", "formatar_lista_codigos",
         "truncar_texto", "observacao_texto", "interpolar_km",
         "preparar_trechos", "diagnosticar_sentido",
         "diagnosticar_trechos", "prefixo_codigo", "texto_generico",
         "texto_saida_obs", "texto_saida_criterio", "status_validacao"}
consts = {"TAMANHO_MAX_OBS", "LIMITE_CODIGOS_LISTADOS", "TOLERANCIA_CONEXAO_M",
          "CASAS_DECIMAIS_KM", "CAMPO_VL_CODIGO", "TEXTO_CRITERIO", "TEXTO_OBS",
          "TEXTO_VALOR_OBS", "STATUS_VALIDADO", "STATUS_A_VALIDAR",
          "CAMPO_VL_KM_INIC",
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

# --- montagem da observacao (codigos internos, sem truncar) ---
checa("obs vazia", g["observacao_texto"](None, ""), None)
checa("obs ordem", g["observacao_texto"]("A", None, "B"), "A; B")
checa("obs nao trunca: so a gravacao trunca",
      len(g["observacao_texto"]("X" * 400)), 400)

# --- textos gravados na camada de saida ---
T = g["texto_saida_obs"]
checa("aviso simples", T("TRECHO_SNV_POSSIVELMENTE_INVERTIDO"),
      "Trecho SNV possivelmente invertido")
checa("chave=valor numerico", T("VIA_OAE=116"), "Via da OAE: 116")
checa("chave=valor textual", T("PROJECAO_NO_EXTREMO=INICIO_GEOM"),
      "Projeção no extremo: início da geometria")
checa("valor ausente", T("VIA_OAE=AUSENTE"), "Via da OAE: ausente")
checa("varios itens", T("VIA_AUSENTE_OU_NAO_NORMALIZAVEL; N_CODIGOS=3"),
      "Via ausente ou não normalizável; Quantidade de códigos no raio: 3")
checa("codigos SNV preservados", T("SOBREPOSICAO_COM=101BMG0330,222BMG0010"),
      "Sobreposição com: 101BMG0330,222BMG0010")
checa("numero preservado", T("DIST_MIN_M=3.000000"), "Distância mínima (m): 3.000000")
checa("chave desconhecida -> generico", T("ALGO_NOVO_SNV=7"), "Algo novo snv: 7")
checa("obs vazia -> None", T(None), None)
checa("obs NULL do QGIS -> None", T(object()), None)
# Truncamento DEPOIS da conversao, com marcador em minusculas.
longa = T("; ".join(["TRECHO_SNV_POSSIVELMENTE_INVERTIDO"] * 20))
checa("obs truncada no limite", len(longa), g["TAMANHO_MAX_OBS"])
checa("marcador em minusculas", longa.endswith("...[truncado]"), True)

C = g["texto_saida_criterio"]
for codigo, texto in [("SEM_TRECHO", "Sem trecho"), ("UNICO_TRECHO", "Único trecho"),
                      ("TRECHO_DIVERGENTE", "Trecho divergente"),
                      ("TRECHO_EMPATE", "Trecho empate"),
                      ("TRECHO_COINCIDENTE", "Trecho coincidente"),
                      ("TRECHO_FRONTEIRA", "Trecho fronteira")]:
    checa(f"criterio {codigo}", C(codigo), texto)
checa("criterio NULL do QGIS -> None", C(object()), None)

# Nenhum texto gravado pode ter palavra inteira em maiusculas, salvo siglas.
SIGLAS = {"SNV", "OAE", "BR"}
gravados = (list(g["TEXTO_CRITERIO"].values()) + list(g["TEXTO_OBS"].values())
            + list(g["TEXTO_VALOR_OBS"].values())
            + [g["STATUS_VALIDADO"], g["STATUS_A_VALIDAR"]])
for texto in gravados:
    for palavra in re.findall(r"[A-Za-zÀ-ÿ]{2,}", texto):
        assert not (palavra.isupper() and palavra not in SIGLAS), (texto, palavra)
    assert texto[0] == texto[0].upper() or texto in g["TEXTO_VALOR_OBS"].values(), texto
ok += 1

# Todo codigo que o script pode gravar em Obs_SNV tem frase propria: varre o
# codigo-fonte atras de literais em maiusculas e exige que cada um seja item
# de Obs_SNV, criterio, valor, ou um uso interno conhecido (contadores etc.).
docstrings = set()
for no in ast.walk(arvore):
    if isinstance(no, (ast.Module, ast.FunctionDef, ast.ClassDef)) and no.body \
            and isinstance(no.body[0], ast.Expr) \
            and isinstance(no.body[0].value, ast.Constant):
        docstrings.add(id(no.body[0].value))
literais = set()
for no in ast.walk(arvore):
    if isinstance(no, ast.Constant) and isinstance(no.value, str) \
            and id(no) not in docstrings:
        s = no.value
        if re.fullmatch(r"[A-Z][A-Z0-9_]{3,}", s):
            literais.add(s)                                  # "AVISO"
        m = re.fullmatch(r"([A-Z][A-Z0-9_]{2,})=([A-Z][A-Z_]*)?", s)
        if m:                                                # "CHAVE=" / "CHAVE=VALOR"
            literais.add(m.group(1))
            if m.group(2):
                literais.add(m.group(2))
USO_INTERNO = {  # contadores, chaves do resumo do console, sentinelas e nomes
    "ALERTA_ESCALA", "ALERTA_EXTREMO", "APTO_AO_CALCULO_DO_KM",
    "ATRIBUTO_TRECHO_DIVERGENTE", "COINCIDENCIA_DETECTADA", "COINCIDENCIA_MESMA_BR",
    "KM_CALCULADO", "KM_EM_TRECHO_SUSPEITO", "KM_NAO_DETERMINADO", "TOTAL",
    "VIA_NAO_NORMALIZAVEL", "NAO_INFORMADA", "NULL", "NONE", "NAN", "SNV_202607A",
}
# A varredura precisa de fato enxergar os itens gravados; sem isso, um teste
# "sem pendencias" passaria tambem com a varredura quebrada.
for esperado in ("VIA_OAE", "FEICOES_SNV_SEM_CODIGO_NO_RAIO", "INICIO_GEOM",
                 "TRECHO_SNV_POSSIVELMENTE_INVERTIDO", "AUSENTE", "UNICO_TRECHO"):
    assert esperado in literais, esperado
ok += 1
sem_frase = sorted(literais - set(g["TEXTO_OBS"]) - set(g["TEXTO_CRITERIO"])
                   - set(g["TEXTO_VALOR_OBS"]) - USO_INTERNO)
checa("todo item de Obs_SNV tem frase propria", sem_frase, [])

# --- Status: formula da planilha ---
S = g["status_validacao"]
V, AV = g["STATUS_VALIDADO"], g["STATUS_A_VALIDAR"]
checa("unico trecho + L", S("UNICO_TRECHO", "L", 1), V)
checa("unico trecho + l minusculo", S("UNICO_TRECHO", "l", 1), V)
checa("unico trecho + L com espacos", S("UNICO_TRECHO", " L ", 1), V)
checa("unico trecho + outro valor", S("UNICO_TRECHO", "X", 1), AV)
checa("unico trecho + vazio", S("UNICO_TRECHO", "", 1), AV)
checa("unico trecho + nulo", S("UNICO_TRECHO", None, 1), AV)
checa("coincidente + 2 codigos", S("TRECHO_COINCIDENTE", None, 2), V)
checa("coincidente + 3 codigos", S("TRECHO_COINCIDENTE", None, 3), AV)
checa("coincidente + 5 codigos e L", S("TRECHO_COINCIDENTE", "L", 5), AV)
checa("L so vale para unico trecho", S("TRECHO_FRONTEIRA", "L", 1), AV)
checa("poucos codigos so vale para coincidente", S("TRECHO_FRONTEIRA", None, 1), AV)
for criterio in ("SEM_TRECHO", "TRECHO_DIVERGENTE", "TRECHO_EMPATE"):
    checa(f"{criterio} -> a validar", S(criterio, "L", 0), AV)
checa("compara codigo interno, nao texto exibido", S("Único trecho", "L", 1), AV)

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

# --- aviso de sentido suspeito (so diagnostico) ---
D = g["diagnosticar_sentido"]
INV = "TRECHO_SNV_POSSIVELMENTE_INVERTIDO"
CON = "TRECHO_SNV_CONTINUIDADE_CONTRADITORIA"
# Trecho avaliado: primeiro vertice em (0,0), ultimo em (1000,0).
E = ((0.0, 0.0), (1000.0, 0.0))
TOCA_INICIO = ((-500.0, 0.0), (0.0, 0.0))       # vizinho com extremo no 1o vertice
TOCA_FIM = ((1000.0, 0.0), (1500.0, 0.0))       # vizinho com extremo no ultimo
TOCA_INICIO_INVERTIDO = ((0.0, 0.0), (-500.0, 0.0))  # sentido do vizinho e irrelevante

# Digitalizacao confirmada -> sem aviso.
checa("confirmado pelo anterior", D(E, [TOCA_INICIO], []), None)
checa("confirmado pelo posterior", D(E, [], [TOCA_FIM]), None)
checa("confirmado por ambos", D(E, [TOCA_INICIO], [TOCA_FIM]), None)
checa("vizinho invertido nao importa", D(E, [TOCA_INICIO_INVERTIDO], []), None)

# Vizinhos no extremo oposto -> trecho possivelmente invertido.
checa("invertido pelo anterior", D(E, [TOCA_FIM], []), INV)
checa("invertido pelo posterior", D(E, [], [TOCA_INICIO]), INV)
checa("invertido por ambos", D(E, [TOCA_FIM], [TOCA_INICIO]), INV)

# Anterior e posterior no mesmo extremo -> continuidade contraditoria.
checa("contraditorio no 1o vertice", D(E, [TOCA_INICIO], [TOCA_INICIO]), CON)
checa("contraditorio no ultimo vertice", D(E, [TOCA_FIM], [TOCA_FIM]), CON)

# Ausencia de evidencia nao e erro.
checa("sem vizinhos", D(E, [], []), None)
checa("vizinho que nao toca", D(E, [((5000.0, 0.0), (6000.0, 0.0))], []), None)
ANEL = ((0.0, 0.0), (1000.0, 0.0))              # toca os dois extremos
checa("vizinho tocando os dois extremos", D(E, [ANEL], []), None)
checa("vizinhos do mesmo lado em extremos diferentes",
      D(E, [TOCA_INICIO, TOCA_FIM], []), None)
# Lado ambiguo nao anula o outro lado.
checa("lado ambiguo + lado que inverte", D(E, [ANEL], [TOCA_INICIO]), INV)

# Limiar de conexao (1,0 m).
checa("conexao a 0,99 m conta", D(E, [((-500.0, 0.0), (1000.99, 0.0))], []), INV)
checa("conexao a 1,01 m nao conta", D(E, [((-500.0, 0.0), (1001.01, 0.0))], []), None)

# Independencia da ordem dos vizinhos.
checa("ordem dos vizinhos irrelevante",
      D(E, [TOCA_FIM, ((5000.0, 0.0), (6000.0, 0.0))], []),
      D(E, [((5000.0, 0.0), (6000.0, 0.0)), TOCA_FIM], []))

# --- busca de vizinhos do aviso (geometria simulada) ---
class Ponto:
    def __init__(self, x, y): self._x, self._y = x, y
    def x(self): return self._x
    def y(self): return self._y

class Linha:
    """Simula QgsGeometry de parte unica: so asPolyline() e usado."""
    def __init__(self, *coords): self._pts = [Ponto(*c) for c in coords]
    def asPolyline(self): return self._pts

def trecho(codigo, ki, kf, *coords):
    return {"codigo": codigo, "registro": {"linha": Linha(*coords), "ki": ki, "kf": kf,
                                           "erro": None, "alerta_sentido": None}}

# Cada cenario usa km e posicoes proprios; em cada um, a regra testada
# muda o resultado (sem ela, o aviso esperado nao sairia, ou sairia indevido).
malha = {
    # 1) BR-116: A (0-10) e C (20-30) corretos; B (10-20) digitalizado AO CONTRARIO.
    "A": trecho("116BMG0010", 0.0, 10.0, (0, 0), (10000, 0)),
    "B": trecho("116BMG0020", 10.0, 20.0, (20000, 0), (10000, 0)),
    "C": trecho("116BMG0030", 20.0, 30.0, (20000, 0), (30000, 0)),
    # 2) BR-101 sobre as mesmas emendas, digitalizada contra os trechos da 116.
    #    So nao recebe aviso porque vizinhos precisam ser da MESMA BR.
    "D": trecho("101BMG0010", 10.0, 20.0, (20000, 0), (10000, 0)),
    # 3) Duas feicoes do MESMO codigo: F so nao recebe aviso porque E, sendo
    #    particao do proprio trecho, nao conta como vizinho.
    "E": trecho("116BMG0050", 50.0, 60.0, (50000, 0), (60000, 0)),
    "F": trecho("116BMG0050", 60.0, 62.0, (62000, 0), (60000, 0)),
    # 4) km com ruido abaixo do metro dos dois lados da emenda (79.9996 e
    #    80.0004, ambos 80.000 ao metro): H, invertido, so e detectado porque a
    #    emenda e comparada ao metro.
    "G": trecho("116BMG0070", 70.0, 79.9996, (70000, 0), (80000, 0)),
    "H": trecho("116BMG0080", 80.0004, 90.0, (90000, 0), (80000, 0)),
}
preparados = {fid: d["registro"] for fid, d in malha.items()}
feicoes = {fid: {"vl_codigo": d["codigo"]} for fid, d in malha.items()}
# 5) Trecho recusado no preparo nao e avaliado nem serve de vizinho.
preparados["R"] = {"linha": None, "ki": 0.0, "kf": 1.0,
                   "erro": "GEOMETRIA_SNV_MULTIPARTE", "alerta_sentido": None}
feicoes["R"] = {"vl_codigo": "116BMG0099"}
g["diagnosticar_trechos"](preparados, feicoes)
alertas = {fid: r["alerta_sentido"] for fid, r in preparados.items()}

checa("A correto, apesar de B invertido", alertas["A"], None)
checa("B invertido detectado", alertas["B"], INV)
checa("C correto", alertas["C"], None)
checa("outra BR nao e vizinha", alertas["D"], None)
checa("particao do mesmo codigo nao e vizinha", alertas["F"], None)
checa("km com ruido abaixo do metro emenda", alertas["H"], INV)
checa("trecho recusado no preparo fica sem aviso", alertas["R"], None)

print(f"{ok} verificacoes OK")
