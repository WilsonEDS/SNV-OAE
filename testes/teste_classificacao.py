"""Testa selecionar_codigo isolando o teste geometrico de sobreposicao."""
import ast, collections, itertools, math, re, pathlib

fonte = (pathlib.Path(__file__).resolve().parent.parent / 'associacao_oae_snv.py').read_text(encoding='utf-8')
arvore = ast.parse(fonte)

nomes_func = {"codigo_valido", "prefixo_codigo", "quase_igual",
              "selecionar_codigo", "rodovias_coincidentes_texto",
              "valor_unanime", "numero_do_codigo", "fracao_na_linha",
              "fracao_no_trecho", "desempatar"}
nomes_const = {"TOLERANCIA_EMPATE_DISTANCIA_M", "TOLERANCIA_EMPATE_FRACAO"}

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

class Linha:
    """Simula a LineString: comprimento e posicao da projecao ao longo dela."""
    def __init__(self, comprimento, posicao):
        self.comprimento, self.posicao = comprimento, posicao
    def length(self):
        return self.comprimento
    def lineLocatePoint(self, ponto):
        return self.posicao

# Trechos simulados: o fid de cada feicao e o proprio codigo. Por padrao, sem
# linha apta; sem ponto da OAE, o desempate pelo trecho seguinte nao se aplica.
TRECHOS = collections.defaultdict(lambda: {"linha": None})
OAE = object()

def sel(por_codigo, via, trechos=None, geometria_oae=None):
    return ns["selecionar_codigo"](por_codigo, via,
                                   TRECHOS if trechos is None else trechos, geometria_oae)

def entrada(**codigos):
    """codigo -> distancia"""
    return {c: {"id": c, "distancia": d, "feicoes_mais_proximas": [(c, d)]}
            for c, d in codigos.items()}

ok = 0
def checa(rotulo, obtido, esperado):
    global ok
    assert obtido == esperado, f"FALHOU {rotulo}: {obtido!r} != {esperado!r}"
    ok += 1

CRITERIOS = ("SEM_TRECHO", "UNICO_TRECHO", "TRECHO_COINCIDENTE",
             "TRECHO_FRONTEIRA", "TRECHO_DIVERGENTE", "TRECHO_EMPATE")

# --- 1) conjunto vazio -------------------------------------------------------
cod, crit, causa, rodcoinc = sel({}, "116", None, None)
checa("vazio", (cod, crit, causa), (None, "SEM_TRECHO", "SEM_CANDIDATO_NO_RAIO"))

# --- 2) codigo unico COMPATIVEL ---------------------------------------------
cod, crit, causa, rodcoinc = sel(entrada(**{"116BMG0450": 3.0}), "116", None, None)
checa("unico compativel", (cod, crit, causa), ("116BMG0450", "UNICO_TRECHO", None))

# --- 3) codigo unico INCOMPATIVEL -> TRECHO_DIVERGENTE (regra nova) ----------
cod, crit, causa, rodcoinc = sel(entrada(**{"101BMG0450": 3.0}), "116", None, None)
checa("unico incompativel", (cod, crit, causa),
      (None, "TRECHO_DIVERGENTE", "UNICO_CODIGO_INCOMPATIVEL_COM_VIA"))

# --- 4) codigo unico com Via ausente -> TRECHO_DIVERGENTE -------------------
cod, crit, causa, rodcoinc = sel(entrada(**{"101BMG0450": 3.0}), None, None, None)
checa("unico sem via", (cod, crit, causa),
      (None, "TRECHO_DIVERGENTE", "VIA_AUSENTE_OU_NAO_NORMALIZAVEL"))

# --- 5) dois codigos, nenhum compativel -------------------------------------
cod, crit, causa, rodcoinc = sel(entrada(**{"101A": 3.0, "222B": 4.0}), "116", None, None)
checa("divergente", (cod, crit, causa),
      (None, "TRECHO_DIVERGENTE", "NENHUM_CODIGO_COMPATIVEL_COM_VIA"))

# --- 6) dois codigos, Via ausente -------------------------------------------
cod, crit, causa, rodcoinc = sel(entrada(**{"101A": 3.0, "222B": 4.0}), None, None, None)
checa("divergente sem via", causa, "VIA_AUSENTE_OU_NAO_NORMALIZAVEL")

# --- 7) dois compativeis, distancias distintas -> FRONTEIRA -----------------
cod, crit, causa, rodcoinc = sel(entrada(**{"116A": 3.0, "116B": 9.0}), "116", None, None)
checa("fronteira", (cod, crit, causa), ("116A", "TRECHO_FRONTEIRA", None))

# --- 8) DECISAO 1: varios codigos no raio, apenas UM compativel -------------
# A cardinalidade e medida sobre TODOS os codigos do raio, logo a decisao
# pertence ao ramo de concorrencia e nao a UNICO_TRECHO.
PARES = set()
cod, crit, causa, rodcoinc = sel(
    entrada(**{"101BMG0450": 2.0, "222BMG0010": 4.0, "116BMG0450": 3.0}),
    "116", None, None)
checa("tres no raio, um compativel", (cod, crit), ("116BMG0450", "TRECHO_FRONTEIRA"))

# --- 9) EMPATE: equidistancia entre compativeis, documentada ----------------
cod, crit, causa, rodcoinc = sel(entrada(**{"116A": 3.0, "116B": 3.0}), "116", None, None)
checa("empate", (cod, crit, causa),
      (None, "TRECHO_EMPATE", "CODIGOS_COMPATIVEIS_EQUIDISTANTES"))

# --- 9b) EMPATE desfeito pelo numero do codigo -> FRONTEIRA -----------------
cod, crit, causa, rodcoinc = sel(
    entrada(**{"040BDF0017": 3.0, "040BDF0020": 3.0}), "040", None, None)
checa("empate: maior numero vence", (cod, crit, causa, rodcoinc),
      ("040BDF0020", "TRECHO_FRONTEIRA", "DESEMPATE_PELO_NUMERO_DO_CODIGO", None))
# Compara o numero, nao o texto: 0100 > 0020 > 0009.
cod, _, _, _ = sel(entrada(**{"040BDF0009": 3.0, "040BDF0100": 3.0, "040BDF0020": 3.0}), "040")
checa("empate: numero, nao texto", cod, "040BDF0100")
# So os empatados disputam: um codigo mais distante de numero maior nao entra.
cod, crit, _, _ = sel(entrada(**{"040BDF0017": 3.0, "040BDF0020": 3.0, "040BDF0090": 5.0}), "040")
checa("empate: so entre equidistantes", (cod, crit), ("040BDF0020", "TRECHO_FRONTEIRA"))
# Codigo de outra BR nao participa do desempate.
cod, _, _, _ = sel(entrada(**{"040BDF0017": 3.0, "040BDF0020": 3.0, "116BDF0900": 3.0}), "040")
checa("empate: outra BR nao participa", cod, "040BDF0020")

# --- 9c) numeros iguais (divisa de UF) -> trecho seguinte -------------------
# A OAE esta no fim do 040BDF0020 (fracao 1) e no inicio do 040BGO0020 (fracao 0).
TR = {"040BDF0020": {"linha": Linha(1000, 1000)}, "040BGO0020": {"linha": Linha(800, 0)}}
cod, crit, causa, _ = sel(entrada(**{"040BDF0020": 3.0, "040BGO0020": 3.0}), "040", TR, OAE)
checa("divisa: trecho seguinte", (cod, crit, causa),
      ("040BGO0020", "TRECHO_FRONTEIRA", "DESEMPATE_PELO_TRECHO_SEGUINTE"))
# Codigo sem numero tambem decide pelo trecho seguinte.
TR = {"116A": {"linha": Linha(1000, 0)}, "116B": {"linha": Linha(1000, 1000)}}
cod, _, causa, _ = sel(entrada(**{"116A": 3.0, "116B": 3.0}), "116", TR, OAE)
checa("sem numero: trecho seguinte", (cod, causa), ("116A", "DESEMPATE_PELO_TRECHO_SEGUINTE"))
# Bifurcacao: os dois comecam no ponto da OAE -> continua empate.
TR = {"040BDF0020": {"linha": Linha(1000, 0)}, "040BGO0020": {"linha": Linha(800, 0)}}
cod, crit, causa, _ = sel(entrada(**{"040BDF0020": 3.0, "040BGO0020": 3.0}), "040", TR, OAE)
checa("bifurcacao: empate", (cod, crit, causa),
      (None, "TRECHO_EMPATE", "CODIGOS_COMPATIVEIS_EQUIDISTANTES"))
# Sem linha apta para um deles -> continua empate.
TR = {"040BDF0020": {"linha": Linha(1000, 1000)}, "040BGO0020": {"linha": None}}
cod, crit, _, _ = sel(entrada(**{"040BDF0020": 3.0, "040BGO0020": 3.0}), "040", TR, OAE)
checa("sem linha: empate", (cod, crit), (None, "TRECHO_EMPATE"))
# Duas feicoes do mesmo codigo empatadas: a linha nao e unica -> continua empate.
pc = entrada(**{"040BDF0020": 3.0, "040BGO0020": 3.0})
pc["040BGO0020"]["feicoes_mais_proximas"] = [("g1", 3.0), ("g2", 3.0)]
TR = {"040BDF0020": {"linha": Linha(1000, 1000)}, "g1": {"linha": Linha(10, 0)},
      "g2": {"linha": Linha(10, 0)}}
checa("geometria do codigo nao unica: empate", sel(pc, "040", TR, OAE)[:2],
      (None, "TRECHO_EMPATE"))
# Numero desempata antes do sentido, mesmo que o sentido indicasse o outro.
TR = {"040BDF0017": {"linha": Linha(1000, 0)}, "040BDF0020": {"linha": Linha(1000, 1000)}}
checa("numero antes do sentido",
      sel(entrada(**{"040BDF0017": 3.0, "040BDF0020": 3.0}), "040", TR, OAE)[0], "040BDF0020")

# --- 10) coincidencia com parceiro de outra BR ------------------------------
PARES = {frozenset(("116A", "101X"))}
cod, crit, causa, rodcoinc = sel(
    entrada(**{"116A": 3.0, "101X": 3.0, "116B": 9.0}), "116", None, None)
checa("coincidente", (cod, crit, causa), ("116A", "TRECHO_COINCIDENTE", None))
checa("coincidente: rodovias", rodcoinc, "116;101")

# --- 11) DECISAO 3: unico compativel, mas coincidente -> COINCIDENTE --------
PARES = {frozenset(("116BMG0450", "101BMG0330"))}
cod, crit, causa, rodcoinc = sel(
    entrada(**{"116BMG0450": 3.0, "101BMG0330": 3.0}), "116", None, None)
checa("unico compativel coincidente", (cod, crit), ("116BMG0450", "TRECHO_COINCIDENTE"))

# --- 12) par coincidente MAIS DISTANTE nao vence o compativel mais proximo --
PARES = {frozenset(("116B", "101X"))}
cod, crit, _, rodcoinc = sel(entrada(**{"116A": 3.0, "116B": 9.0, "101X": 9.0}), "116", None, None)
checa("coincidente distante nao vence", (cod, crit), ("116A", "TRECHO_FRONTEIRA"))

# --- 13) empate entre coincidencias nao e resgatado por fronteira -----------
PARES = {frozenset(("116A", "101X")), frozenset(("116B", "101Y"))}
cod, crit, causa, rodcoinc = sel(
    entrada(**{"116A": 3.0, "116B": 3.0, "101X": 3.0, "101Y": 3.0}), "116", None, None)
checa("empate de coincidentes", (cod, crit, causa),
      (None, "TRECHO_EMPATE", "CODIGOS_COINCIDENTES_COMPATIVEIS_EQUIDISTANTES"))
checa("empate de coincidentes: rodovias", rodcoinc, "101;116")
# Com numeros, o empate de coincidentes e desfeito: o escolhido esta sobre
# rodovias coincidentes, logo e TRECHO_COINCIDENTE, e o campo traz so a sua
# coincidencia.
PARES = {frozenset(("116BMG0010", "101BMG0500")), frozenset(("116BMG0020", "222BMG0700"))}
cod, crit, causa, rodcoinc = sel(entrada(**{
    "116BMG0010": 3.0, "116BMG0020": 3.0, "101BMG0500": 3.0, "222BMG0700": 3.0}), "116")
checa("empate de coincidentes desfeito", (cod, crit, causa, rodcoinc),
      ("116BMG0020", "TRECHO_COINCIDENTE", "DESEMPATE_PELO_NUMERO_DO_CODIGO", "116;222"))

# --- 14) tres equidistantes, so um coincidente ------------------------------
PARES = {frozenset(("116A", "101X"))}
cod, crit, _, rodcoinc = sel(
    entrada(**{"116A": 3.0, "116B": 3.0, "116C": 3.0, "101X": 3.0}), "116", None, None)
checa("coincidente entre equidistantes", (cod, crit), ("116A", "TRECHO_COINCIDENTE"))

# --- 15) independencia da ordem de insercao do dicionario ------------------
PARES = {frozenset(("116A", "101X"))}
base = {"116A": 3.0, "116B": 3.0, "116C": 3.0, "101X": 3.0}
resultados = set()
for ordem in itertools.permutations(base):
    d = {c: {"id": c, "distancia": base[c], "feicoes_mais_proximas": [(1, base[c])]}
         for c in ordem}
    r = sel(d, "116", None, None)
    resultados.add(r)
checa("ordem do dicionario irrelevante", len(resultados), 1)
# Tambem nos desempates pelo numero e pelo trecho seguinte.
TR = {"040BDF0020": {"linha": Linha(1000, 1000)}, "040BGO0020": {"linha": Linha(800, 0)},
      "040BDF0017": {"linha": Linha(500, 500)}}
for base in ({"040BDF0017": 3.0, "040BDF0020": 3.0, "040BGO0017": 3.0},
             {"040BDF0020": 3.0, "040BGO0020": 3.0, "040BDF0017": 3.0}):
    resultados = {sel({c: entrada(**base)[c] for c in ordem}, "040", TR, OAE)
                  for ordem in itertools.permutations(base)}
    checa(f"desempate independe da ordem: {sorted(base)}", len(resultados), 1)

# --- 16) INVARIANTE: todo codigo devolvido e compativel com a Via ----------
PARES = {frozenset(("116A", "101X"))}
combinacoes = [
    ({"116A": 1.0}, "116"), ({"101A": 1.0}, "116"), ({"101A": 1.0}, None),
    ({"116A": 1.0, "101X": 1.0}, "116"), ({"116A": 2.0, "101X": 0.5}, "116"),
    ({"101A": 1.0, "222B": 2.0}, "116"), ({"116A": 1.0, "116B": 2.0}, "116"),
    ({"116A": 1.0, "116B": 1.0}, "116"), ({"116A": 1.0, "116B": 2.0}, None),
    ({"101A": 1.0, "222B": 2.0, "116C": 3.0}, "116"),
    ({"116BMG0010": 1.0, "116BMG0020": 1.0}, "116"),
    ({"116BMG0010": 1.0, "116BMG0020": 1.0, "101BMG0010": 0.5}, "116"),
]
for base_c, via in combinacoes:
    d = {c: {"id": c, "distancia": v, "feicoes_mais_proximas": [(1, v)]}
         for c, v in base_c.items()}
    c_sel, crit, causa, _ = sel(d, via, None, None)
    assert crit in CRITERIOS, crit
    if c_sel is not None:
        # Pre-condicao universal: nenhum codigo de outra BR e jamais atribuido.
        assert via is not None and c_sel[:3] == via, (c_sel, via, crit)
        assert causa is None or causa.startswith("DESEMPATE_"), (crit, causa)
    else:
        assert causa, (crit, causa)
    ok += 1

# --- 17) codigo incompativel mais PROXIMO nao vence compativel mais distante -
PARES = set()
c_sel, crit, _, _ = sel(entrada(**{"116A": 1.0, "101X": 0.5}), "116", None, None)
checa("nunca escolhe BR divergente", (c_sel, crit), ("116A", "TRECHO_FRONTEIRA"))

# --- 20) Rodovias_coincidentes: rodovias em sobreposicao comprovada ---------
rc = ns["rodovias_coincidentes_texto"]

# Caso de referencia: OAE associada ao 116BMG0450, sobreposto ao 101BMG0330.
# A rodovia atribuida encabeca a lista.
checa("coincidencia: caso de referencia",
      rc({"116BMG0450": ["101BMG0330"]}, "116BMG0450"), ("116;101", 2))

# A atribuida vem primeiro mesmo quando seu numero e o maior.
checa("atribuida primeiro",
      rc({"222BMG0100": ["101BMG0330"]}, "222BMG0100")[0], "222;101")

# Sem coincidencia detectada -> None.
checa("sem coincidencia", rc({}, "116BMG0450"), (None, 0))
checa("sem coincidencia e sem atribuida", rc({}), (None, 0))

# Tres rodovias coincidentes: atribuida primeiro, demais em ordem numerica.
checa("tres rodovias",
      rc({"222A": ["116B", "101C"]}, "222A")[0], "222;101;116")

# TRECHO_EMPATE: sem codigo atribuido, todas em ordem numerica crescente.
checa("empate sem atribuida",
      rc({"116A": ["101X"], "101X": ["116A"]})[0], "101;116")

# Anomalia: dois codigos DISTINTOS da mesma BR -> uma unica rodovia.
# O texto permanece verdadeiro e a contagem permite sinalizar o caso.
checa("codigos da mesma BR",
      rc({"116BMG0450": ["116BMG0460"]}, "116BMG0450"), ("116", 1))

# Codigo fora do padrao nao produz numero de rodovia e e ignorado.
checa("parceiro com prefixo invalido",
      rc({"116BMG0450": ["ABCBMG0330"]}, "116BMG0450"), ("116", 1))
checa("todos com prefixo invalido", rc({"ABC": ["XYZ"]}, "ABC"), (None, 0))

# Determinismo: o texto nao depende da ordem de insercao do dicionario.
textos = set()
for ordem in itertools.permutations(["116A", "101X", "222B"]):
    textos.add(rc({c: [o for o in ordem if o != c] for c in ordem})[0])
checa("coincidencia: ordem de insercao irrelevante", textos, {"101;116;222"})

# --- 21) INVARIANTE: o campo so e preenchido onde ha coincidencia -----------
PARES = {frozenset(("116A", "101X")), frozenset(("116B", "101Y"))}
casos_inv = [
    (entrada(**{"116A": 1.0}), "116"),
    (entrada(**{"101A": 1.0}), "116"),
    (entrada(**{"101A": 1.0}), None),
    (entrada(**{"116A": 1.0, "116B": 2.0}), "116"),
    (entrada(**{"116A": 1.0, "116B": 1.0}), "116"),
    (entrada(**{"116A": 1.0, "101X": 1.0}), "116"),
    (entrada(**{"116A": 1.0, "116B": 1.0, "101X": 1.0, "101Y": 1.0}), "116"),
    (entrada(**{"101A": 1.0, "222B": 2.0}), "116"),
    ({}, "116"),
]
for pc, via in casos_inv:
    c_sel, crit, _, rodcoinc = sel(pc, via, None, None)
    if rodcoinc:
        # So estes dois criterios comprovam sobreposicao linear.
        assert crit in ("TRECHO_COINCIDENTE", "TRECHO_EMPATE"), (crit, rodcoinc)
        # Havendo codigo atribuido, ele encabeca a lista.
        if c_sel is not None:
            assert rodcoinc.split(";")[0] == c_sel[:3], (c_sel, rodcoinc)
    else:
        assert crit != "TRECHO_COINCIDENTE", (crit, rodcoinc)
    ok += 1

# FRONTEIRA nunca preenche o campo: proximidade nao e coincidencia.
PARES = set()
_, crit, _, rodcoinc = sel(entrada(**{"116A": 3.0, "116B": 9.0}), "116", None, None)
checa("fronteira nao preenche", (crit, rodcoinc), ("TRECHO_FRONTEIRA", None))

# --- 22) Administracao / Jurisdicao: valor do trecho atribuido -------------
vu = ns["valor_unanime"]

# Caso comum: uma unica feicao.
checa("unanime: feicao unica", vu(["Federal"]), ("Federal", False))

# Varias feicoes do mesmo codigo empatadas, com o mesmo valor -> gravado.
checa("unanime: valores iguais", vu(["Federal", "Federal"]), ("Federal", False))

# Espacos nas bordas nao geram falsa divergencia.
checa("unanime: espacos", vu([" Federal", "Federal  "]), ("Federal", False))

# Valores diferentes -> NULL e divergencia sinalizada; nenhum e escolhido.
checa("unanime: divergentes",
      vu(["Federal", "Concessao Federal"]), (None, True))

# Valor ausente na SNV -> NULL, sem divergencia.
checa("unanime: nulo", vu([None]), (None, False))
checa("unanime: sentinela NULL", vu(["NULL"]), (None, False))
checa("unanime: texto vazio", vu(["   "]), (None, False))
checa("unanime: todos ausentes", vu([None, "", "NULL"]), (None, False))

# Ausente numa feicao e presente noutra conta como divergencia: a ausencia
# nao prova que o valor seja o mesmo.
checa("unanime: ausente x presente", vu([None, "Federal"]), (None, True))

# Aceita gerador, como no laco do script.
checa("unanime: gerador", vu(v for v in ["Federal"]), ("Federal", False))

# Determinismo: o resultado nao depende da ordem das feicoes.
resultados = {vu(list(ordem)) for ordem in
              itertools.permutations(["Federal", "Estadual", "Federal"])}
checa("unanime: ordem irrelevante", resultados, {(None, True)})

print(f"{ok} verificacoes OK")
