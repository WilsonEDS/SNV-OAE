"""Testa selecionar_codigo isolando o teste geometrico de sobreposicao."""
import ast, math, re, itertools, pathlib

fonte = (pathlib.Path(__file__).resolve().parent.parent / 'associacao_oae_snv.py').read_text(encoding='utf-8')
arvore = ast.parse(fonte)

nomes_func = {"codigo_valido", "prefixo_codigo", "quase_igual",
              "formatar_lista_codigos", "observacao_texto", "selecionar_codigo"}
nomes_const = {"TOLERANCIA_EMPATE_DISTANCIA_M", "TAMANHO_MAX_OBS",
               "LIMITE_CODIGOS_LISTADOS", "EXIGIR_VIA_COMPATIVEL_EM_UNICO_TRECHO"}

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

# 1) conjunto vazio
cod, crit, obs = sel({}, "116", None, None)
checa("vazio", (cod, crit), (None, "SEM_TRECHO"))

# 2) codigo unico compativel
cod, crit, obs = sel(entrada(**{"116BMG0450": 3.0}), "116", None, None)
checa("unico compativel", (cod, crit), ("116BMG0450", "UNICO_TRECHO"))
assert "VIA_COMPATIVEL=SIM" in obs, obs

# 3) codigo unico INCOMPATIVEL -> ainda UNICO_TRECHO (metodologia original),
#    mas a incompatibilidade fica registrada
cod, crit, obs = sel(entrada(**{"101BMG0450": 3.0}), "116", None, None)
checa("unico incompativel -> criterio", (cod, crit), ("101BMG0450", "UNICO_TRECHO"))
assert "VIA_COMPATIVEL=NAO" in obs, obs

# 4) via ausente com codigo unico
cod, crit, obs = sel(entrada(**{"101BMG0450": 3.0}), None, None, None)
checa("unico sem via", crit, "UNICO_TRECHO")
assert "VIA_OAE=AUSENTE" in obs

# 5) dois codigos, nenhum compativel -> DIVERGENTE
cod, crit, obs = sel(entrada(**{"101A": 3.0, "222B": 4.0}), "116", None, None)
checa("divergente", (cod, crit), (None, "TRECHO_DIVERGENTE"))
assert "NENHUM_CODIGO_COMPATIVEL_COM_VIA=116" in obs and "CODIGOS_NO_RAIO=101A,222B" in obs

# 6) dois codigos, via ausente -> DIVERGENTE com causa propria
cod, crit, obs = sel(entrada(**{"101A": 3.0, "222B": 4.0}), None, None, None)
checa("divergente sem via", crit, "TRECHO_DIVERGENTE")
assert "VIA_AUSENTE_OU_NAO_NORMALIZAVEL" in obs

# 7) dois compativeis, distancias distintas -> FRONTEIRA no mais proximo
cod, crit, obs = sel(entrada(**{"116A": 3.0, "116B": 9.0}), "116", None, None)
checa("fronteira", (cod, crit), ("116A", "TRECHO_FRONTEIRA"))
assert "MIN_VIA_M=3.000000" in obs and "MARGEM_M=6.000000" in obs, obs

# 8) empate exato sem coincidencia -> EMPATE
cod, crit, obs = sel(entrada(**{"116A": 3.0, "116B": 3.0}), "116", None, None)
checa("empate", (cod, crit), (None, "TRECHO_EMPATE"))
assert "EMPATE_EXATO_DE_DISTANCIA" in obs and "CODIGOS_EM_EMPATE=116A,116B" in obs

# 9) coincidencia: 116A equidistante e sobreposto a 101X (outra BR)
PARES = {frozenset(("116A", "101X"))}
cod, crit, obs = sel(entrada(**{"116A": 3.0, "101X": 3.0, "116B": 9.0}), "116", None, None)
checa("coincidente", (cod, crit), ("116A", "TRECHO_COINCIDENTE"))
assert "SOBREPOSICAO_COM=101X" in obs

# 10) par coincidente MAIS DISTANTE nao vence trecho compativel mais proximo
PARES = {frozenset(("116B", "101X"))}
cod, crit, obs = sel(entrada(**{"116A": 3.0, "116B": 9.0, "101X": 9.0}), "116", None, None)
checa("coincidente distante nao vence", (cod, crit), ("116A", "TRECHO_FRONTEIRA"))

# 11) duas coincidencias compativeis empatadas -> EMPATE (nao cai em fronteira)
PARES = {frozenset(("116A", "101X")), frozenset(("116B", "101Y"))}
cod, crit, obs = sel(
    entrada(**{"116A": 3.0, "116B": 3.0, "101X": 3.0, "101Y": 3.0}), "116", None, None)
checa("empate de coincidentes", (cod, crit), (None, "TRECHO_EMPATE"))
assert "EMPATE_ENTRE_CODIGOS_COINCIDENTES" in obs

# 12) tres equidistantes, so um coincidente -> vence e registra os descartados
PARES = {frozenset(("116A", "101X"))}
cod, crit, obs = sel(
    entrada(**{"116A": 3.0, "116B": 3.0, "116C": 3.0, "101X": 3.0}), "116", None, None)
checa("coincidente entre equidistantes", (cod, crit), ("116A", "TRECHO_COINCIDENTE"))
assert "DESCARTADOS_NO_MINIMO=116B,116C" in obs, obs

# 13) independencia da ordem de insercao do dicionario
PARES = {frozenset(("116A", "101X"))}
base = {"116A": 3.0, "116B": 3.0, "116C": 3.0, "101X": 3.0}
resultados = set()
for ordem in itertools.permutations(base):
    d = {c: {"id": c, "distancia": base[c], "feicoes_mais_proximas": [(1, base[c])]}
         for c in ordem}
    r = sel(d, "116", None, None)
    resultados.add((r[0], r[1]))
checa("ordem do dicionario irrelevante", len(resultados), 1)

# 14) exaustividade: todo retorno pertence aos seis criterios
CRITERIOS = ("SEM_TRECHO", "UNICO_TRECHO", "TRECHO_COINCIDENTE",
             "TRECHO_FRONTEIRA", "TRECHO_DIVERGENTE", "TRECHO_EMPATE")
casos = [({}, "116"), (entrada(**{"116A": 1.0}), "116"),
         (entrada(**{"116A": 1.0, "116B": 1.0}), "116"),
         (entrada(**{"101A": 1.0, "222B": 2.0}), "116"),
         (entrada(**{"116A": 1.0, "116B": 2.0}), None)]
for pc, via in casos:
    _, crit, _ = sel(pc, via, None, None)
    assert crit in CRITERIOS, crit
    ok += 1

# 15) codigo escolhido sempre compativel quando ha concorrencia resolvida
for pc, via in [(entrada(**{"116A": 1.0, "101X": 0.5}), "116")]:
    c, crit, _ = sel(pc, via, None, None)
    checa("nunca escolhe BR divergente", (c, crit), ("116A", "TRECHO_FRONTEIRA"))

print(f"{ok} verificacoes OK")
