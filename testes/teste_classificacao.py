"""Testa selecionar_codigo isolando o teste geometrico de sobreposicao."""
import ast, math, re, itertools, pathlib

fonte = (pathlib.Path(__file__).resolve().parent.parent / 'associacao_oae_snv.py').read_text(encoding='utf-8')
arvore = ast.parse(fonte)

nomes_func = {"codigo_valido", "prefixo_codigo", "quase_igual",
              "formatar_lista_codigos", "truncar_texto", "observacao_texto",
              "selecionar_codigo", "rodovias_por_proximidade"}
nomes_const = {"TOLERANCIA_EMPATE_DISTANCIA_M", "TAMANHO_MAX_OBS",
               "LIMITE_CODIGOS_LISTADOS"}

ns = {"math": math, "re": re, "NULL": object()}
partes = []
for no in arvore.body:
    if isinstance(no, ast.Assign) and getattr(no.targets[0], "id", None) in nomes_const:
        partes.append(ast.get_source_segment(fonte, no))
    elif isinstance(no, ast.FunctionDef) and no.name in nomes_func:
        partes.append(ast.get_source_segment(fonte, no))
exec("\n\n".join(partes), ns)

# Sobreposicao simulada: pares declarados no conjunto PARES sao coincidentes.
PARES = set()
def falso_sobrepostos(ra, rb, feicoes, geom=None):
    return frozenset((ra["id"], rb["id"])) in PARES
ns["codigos_sobrepostos"] = falso_sobrepostos

sel = ns["selecionar_codigo"]

def entrada(**codigos):
    """codigo -> distancia"""
    return {c: {"id": c, "distancia": d, "feicoes_mais_proximas": [(1, d)]}
            for c, d in codigos.items()}

ok = 0
def checa(rotulo, obtido, esperado):
    global ok
    assert obtido == esperado, f"FALHOU {rotulo}: {obtido!r} != {esperado!r}"
    ok += 1

CRITERIOS = ("SEM_TRECHO", "UNICO_TRECHO", "TRECHO_COINCIDENTE",
             "TRECHO_FRONTEIRA", "TRECHO_DIVERGENTE", "TRECHO_EMPATE")

# --- 1) conjunto vazio -------------------------------------------------------
cod, crit, causa, obs = sel({}, "116", None, None)
checa("vazio", (cod, crit, causa), (None, "SEM_TRECHO", "SEM_CANDIDATO_NO_RAIO"))

# --- 2) codigo unico COMPATIVEL ---------------------------------------------
cod, crit, causa, obs = sel(entrada(**{"116BMG0450": 3.0}), "116", None, None)
checa("unico compativel", (cod, crit, causa), ("116BMG0450", "UNICO_TRECHO", None))
assert "VIA_OAE=116" in obs and "DIST_MIN_M=3.000000" in obs, obs

# --- 3) codigo unico INCOMPATIVEL -> TRECHO_DIVERGENTE (regra nova) ----------
cod, crit, causa, obs = sel(entrada(**{"101BMG0450": 3.0}), "116", None, None)
checa("unico incompativel", (cod, crit, causa),
      (None, "TRECHO_DIVERGENTE", "UNICO_CODIGO_INCOMPATIVEL_COM_VIA"))
assert "CODIGO_NO_RAIO=101BMG0450" in obs and "PREFIXO_CODIGO=101" in obs, obs

# --- 4) codigo unico com Via ausente -> TRECHO_DIVERGENTE -------------------
cod, crit, causa, obs = sel(entrada(**{"101BMG0450": 3.0}), None, None, None)
checa("unico sem via", (cod, crit, causa),
      (None, "TRECHO_DIVERGENTE", "VIA_AUSENTE_OU_NAO_NORMALIZAVEL"))
assert "VIA_OAE=AUSENTE" in obs

# --- 5) dois codigos, nenhum compativel -------------------------------------
cod, crit, causa, obs = sel(entrada(**{"101A": 3.0, "222B": 4.0}), "116", None, None)
checa("divergente", (cod, crit, causa),
      (None, "TRECHO_DIVERGENTE", "NENHUM_CODIGO_COMPATIVEL_COM_VIA"))
assert "NENHUM_CODIGO_COMPATIVEL_COM_VIA=116" in obs and "CODIGOS_NO_RAIO=101A,222B" in obs

# --- 6) dois codigos, Via ausente -------------------------------------------
cod, crit, causa, obs = sel(entrada(**{"101A": 3.0, "222B": 4.0}), None, None, None)
checa("divergente sem via", causa, "VIA_AUSENTE_OU_NAO_NORMALIZAVEL")

# --- 7) dois compativeis, distancias distintas -> FRONTEIRA -----------------
cod, crit, causa, obs = sel(entrada(**{"116A": 3.0, "116B": 9.0}), "116", None, None)
checa("fronteira", (cod, crit, causa), ("116A", "TRECHO_FRONTEIRA", None))
assert "MIN_VIA_M=3.000000" in obs and "MARGEM_M=6.000000" in obs, obs

# --- 8) DECISAO 1: varios codigos no raio, apenas UM compativel -------------
# A cardinalidade e medida sobre TODOS os codigos do raio, logo a decisao
# pertence ao ramo de concorrencia e nao a UNICO_TRECHO.
PARES = set()
cod, crit, causa, obs = sel(
    entrada(**{"101BMG0450": 2.0, "222BMG0010": 4.0, "116BMG0450": 3.0}),
    "116", None, None)
checa("tres no raio, um compativel", (cod, crit), ("116BMG0450", "TRECHO_FRONTEIRA"))
assert "N_CODIGOS=3" in obs and "N_COMPATIVEIS=1" in obs, obs

# --- 9) EMPATE: equidistancia entre compativeis, documentada ----------------
cod, crit, causa, obs = sel(entrada(**{"116A": 3.0, "116B": 3.0}), "116", None, None)
checa("empate", (cod, crit, causa),
      (None, "TRECHO_EMPATE", "CODIGOS_COMPATIVEIS_EQUIDISTANTES"))
assert "CODIGOS_COMPATIVEIS_COM_VIA_EQUIDISTANTES_DA_OAE" in obs, obs
assert "VIA_OAE=116" in obs and "N_EMPATADOS=2" in obs, obs
assert "CODIGOS_EM_EMPATE=116A,116B" in obs, obs
assert "DIST_EQUIDISTANTE_M=3.000000" in obs, obs
ok += 4

# --- 10) coincidencia com parceiro de outra BR ------------------------------
PARES = {frozenset(("116A", "101X"))}
cod, crit, causa, obs = sel(
    entrada(**{"116A": 3.0, "101X": 3.0, "116B": 9.0}), "116", None, None)
checa("coincidente", (cod, crit, causa), ("116A", "TRECHO_COINCIDENTE", None))
assert "SOBREPOSICAO_COM=101X" in obs

# --- 11) DECISAO 3: unico compativel, mas coincidente -> COINCIDENTE --------
PARES = {frozenset(("116BMG0450", "101BMG0330"))}
cod, crit, causa, obs = sel(
    entrada(**{"116BMG0450": 3.0, "101BMG0330": 3.0}), "116", None, None)
checa("unico compativel coincidente", (cod, crit), ("116BMG0450", "TRECHO_COINCIDENTE"))
assert "SOBREPOSICAO_COM=101BMG0330" in obs, obs

# --- 12) par coincidente MAIS DISTANTE nao vence o compativel mais proximo --
PARES = {frozenset(("116B", "101X"))}
cod, crit, _, obs = sel(entrada(**{"116A": 3.0, "116B": 9.0, "101X": 9.0}), "116", None, None)
checa("coincidente distante nao vence", (cod, crit), ("116A", "TRECHO_FRONTEIRA"))

# --- 13) empate entre coincidencias nao e resgatado por fronteira -----------
PARES = {frozenset(("116A", "101X")), frozenset(("116B", "101Y"))}
cod, crit, causa, obs = sel(
    entrada(**{"116A": 3.0, "116B": 3.0, "101X": 3.0, "101Y": 3.0}), "116", None, None)
checa("empate de coincidentes", (cod, crit, causa),
      (None, "TRECHO_EMPATE", "CODIGOS_COINCIDENTES_COMPATIVEIS_EQUIDISTANTES"))
assert "CODIGOS_COINCIDENTES_COMPATIVEIS_COM_VIA_EQUIDISTANTES_DA_OAE" in obs, obs

# --- 14) tres equidistantes, so um coincidente ------------------------------
PARES = {frozenset(("116A", "101X"))}
cod, crit, _, obs = sel(
    entrada(**{"116A": 3.0, "116B": 3.0, "116C": 3.0, "101X": 3.0}), "116", None, None)
checa("coincidente entre equidistantes", (cod, crit), ("116A", "TRECHO_COINCIDENTE"))
assert "DESCARTADOS_NO_MINIMO=116B,116C" in obs, obs

# --- 15) independencia da ordem de insercao do dicionario ------------------
PARES = {frozenset(("116A", "101X"))}
base = {"116A": 3.0, "116B": 3.0, "116C": 3.0, "101X": 3.0}
resultados = set()
for ordem in itertools.permutations(base):
    d = {c: {"id": c, "distancia": base[c], "feicoes_mais_proximas": [(1, base[c])]}
         for c in ordem}
    r = sel(d, "116", None, None)
    resultados.add(r[:3])
checa("ordem do dicionario irrelevante", len(resultados), 1)

# --- 16) INVARIANTE: todo codigo devolvido e compativel com a Via ----------
PARES = {frozenset(("116A", "101X"))}
combinacoes = [
    ({"116A": 1.0}, "116"), ({"101A": 1.0}, "116"), ({"101A": 1.0}, None),
    ({"116A": 1.0, "101X": 1.0}, "116"), ({"116A": 2.0, "101X": 0.5}, "116"),
    ({"101A": 1.0, "222B": 2.0}, "116"), ({"116A": 1.0, "116B": 2.0}, "116"),
    ({"116A": 1.0, "116B": 1.0}, "116"), ({"116A": 1.0, "116B": 2.0}, None),
    ({"101A": 1.0, "222B": 2.0, "116C": 3.0}, "116"),
]
for base_c, via in combinacoes:
    d = {c: {"id": c, "distancia": v, "feicoes_mais_proximas": [(1, v)]}
         for c, v in base_c.items()}
    c_sel, crit, causa, _ = sel(d, via, None, None)
    assert crit in CRITERIOS, crit
    if c_sel is not None:
        # Pre-condicao universal: nenhum codigo de outra BR e jamais atribuido.
        assert via is not None and c_sel[:3] == via, (c_sel, via, crit)
        assert causa is None, (crit, causa)
    else:
        assert causa, (crit, causa)
    ok += 1

# --- 17) codigo incompativel mais PROXIMO nao vence compativel mais distante -
PARES = set()
c_sel, crit, _, _ = sel(entrada(**{"116A": 1.0, "101X": 0.5}), "116", None, None)
checa("nunca escolhe BR divergente", (c_sel, crit), ("116A", "TRECHO_FRONTEIRA"))

# --- 18) Rodovias_coincidentes: lista das rodovias do raio -------------------
rod = ns["rodovias_por_proximidade"]

def entrada_d(**codigos):
    return {c: {"distancia": d} for c, d in codigos.items()}

# Caso de referencia do responsavel: duas feicoes da BR-116 a 3 m e a BR-101 a
# 40 m -> a mais proxima primeiro, BR repetida uma unica vez.
texto, sem_prefixo = rod(entrada_d(**{
    "116BMG0450": 3.0, "116BMG0460": 3.0, "101BMG0330": 40.0}))
checa("caso de referencia", (texto, sem_prefixo), ("116;101", 0))

# Rodovia unica: tres digitos, sem separador.
checa("rodovia unica", rod(entrada_d(**{"116BMG0450": 3.0})), ("116", 0))

# Conjunto vazio -> None.
checa("sem candidatos", rod({}), (None, 0))

# A distancia de uma BR e a MENOR entre seus codigos: 116 entra com 2.0.
checa("menor distancia por BR",
      rod(entrada_d(**{"116A": 9.0, "116B": 2.0, "101X": 5.0}))[0], "116;101")

# Ordem estritamente por proximidade, nao alfabetica.
checa("ordem por proximidade",
      rod(entrada_d(**{"101X": 50.0, "116A": 1.0, "222B": 10.0}))[0], "116;222;101")

# Empate de distancia entre BRs distintas -> desempate por numero crescente.
checa("empate desempatado por numero",
      rod(entrada_d(**{"222B": 4.0, "101X": 4.0, "116A": 4.0}))[0], "101;116;222")

# Codigo fora do padrao: omitido da lista e contabilizado.
checa("prefixo invalido omitido",
      rod(entrada_d(**{"AB1BMG0450": 1.0, "116BMG0450": 3.0})), ("116", 1))

# Todos fora do padrao -> None, com a contagem preservada.
checa("todos invalidos", rod(entrada_d(**{"ABC": 1.0, "XYZ": 2.0})), (None, 2))

# Determinismo: o texto nao depende da ordem de insercao do dicionario.
base_rod = {"116A": 4.0, "101X": 4.0, "222B": 4.0, "116B": 9.0}
textos = set()
for ordem in itertools.permutations(base_rod):
    textos.add(rod({c: {"distancia": base_rod[c]} for c in ordem})[0])
checa("ordem de insercao irrelevante", textos, {"101;116;222"})

# --- 19) N_CODIGOS preservado em todos os ramos -----------------------------
# A contagem que Qtd_Codigos fornecia nao pode sumir com a troca do campo.
PARES = set()
for pc, via, rotulo in [
    (entrada(**{"116A": 1.0}), "116", "UNICO_TRECHO"),
    (entrada(**{"101A": 1.0}), "116", "DIVERGENTE de codigo unico"),
    (entrada(**{"101A": 1.0, "222B": 2.0}), "116", "DIVERGENTE de varios"),
    (entrada(**{"116A": 1.0, "116B": 2.0}), "116", "FRONTEIRA"),
    (entrada(**{"116A": 1.0, "116B": 1.0}), "116", "EMPATE"),
]:
    _, _, _, obs = sel(pc, via, None, None)
    assert obs and "N_CODIGOS=" in obs, (rotulo, obs)
    ok += 1

print(f"{ok} verificacoes OK")
