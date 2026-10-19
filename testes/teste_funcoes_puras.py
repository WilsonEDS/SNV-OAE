"""Extrai e testa as funcoes puras (sem dependencia QGIS) do script."""
import ast, math, re, pathlib

fonte = (pathlib.Path(__file__).resolve().parent.parent / 'associacao_oae_snv.py').read_text(encoding='utf-8')
arvore = ast.parse(fonte)

alvos = {"codigo_valido", "numero_finito_positivo", "numero_finito", "normalizar_via",
         "prefixo_codigo", "quase_igual", "valor_unanime", "truncar_texto",
         "status_validacao", "raio_base", "buscar_em_etapas", "preparar_trecho",
         "interpolar_km", "calcular_km", "indices_mantidos", "normalizar_nome_campo",
         "resolver_campo", "mensagem_campo_ausente"}
consts = {"FATOR_RAIO", "FATOR_RAIO_AMPLIADO", "TEXTO_CRITERIO", "CRITERIOS_VALIDOS",
          "STATUS_VALIDADO", "STATUS_A_VALIDAR", "CAMPOS_OAE_EXCLUIDOS", "CAMPOS_NOVOS",
          "CAMPO_TRECHO_SNV", "CAMPO_VERSAO_SNV", "CAMPO_ADMINISTRACAO", "CAMPO_JURISDICAO",
          "CAMPO_KM_SNV", "CAMPO_RODOVIAS_COINC", "CAMPO_STATUS", "CAMPO_CRITERIO",
          "CAMPO_DIST_SNV", "CAMPO_RAIO_SNV", "CAMPO_QTD_CODIGOS"}

import difflib, unicodedata
NULL = object()
ns = {"math": math, "re": re, "NULL": NULL, "difflib": difflib,
      "unicodedata": unicodedata}
trechos = []
vistos = set()
for no in arvore.body:
    # So a PRIMEIRA atribuicao de cada constante (o valor literal). As
    # posteriores, como CAMPO_VL_CODIGO = reais_snv[...], dependem das camadas
    # carregadas no QGIS.
    nome_const = getattr(no.targets[0], "id", None) if isinstance(no, ast.Assign) else None
    if nome_const in consts and nome_const not in vistos:
        vistos.add(nome_const)
        trechos.append(ast.get_source_segment(fonte, no))
    if isinstance(no, ast.FunctionDef) and no.name in alvos:
        trechos.append(ast.get_source_segment(fonte, no))
exec("\n\n".join(trechos), ns)
assert vistos == consts, consts - vistos

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


# --- textos de Criterio e Status gravados na saida ---
TC = g["TEXTO_CRITERIO"]
checa("todo criterio tem texto", set(TC), set(g["CRITERIOS_VALIDOS"]))
for codigo, texto in [("SEM_TRECHO", "Sem trecho"), ("UNICO_TRECHO", "Trecho único"),
                      ("TRECHO_DIVERGENTE", "Trecho divergente"),
                      ("TRECHO_EMPATE", "Trecho empate"),
                      ("TRECHO_COINCIDENTE", "Trecho coincidente"),
                      ("TRECHO_FRONTEIRA", "Trecho fronteira")]:
    checa(f"criterio {codigo}", TC[codigo], texto)
for texto in list(TC.values()) + [g["STATUS_VALIDADO"], g["STATUS_A_VALIDAR"]]:
    checa(f"so a primeira maiuscula: {texto}", texto == texto[0] + texto[1:].lower(), True)

# --- campos criados na saida ---
checa("campos novos, na ordem", g["CAMPOS_NOVOS"], (
    "Trecho_SNV", "Versao_SNV", "Administracao", "Jurisdicao", "km_SNV",
    "Rodovias_coincidentes", "Status", "Criterio", "Dist_SNV_m", "Raio_SNV", "Qtd_Codigos"))
checa("Obs_SNV nao e mais criado", "Obs_SNV" in g["CAMPOS_NOVOS"], False)
checa("Obs_SNV nao aparece no script", "Obs_SNV" in fonte, False)

# --- atributos do trecho e textos ---
U = g["valor_unanime"]
checa("unanime: um valor", U(["202607A"]), ("202607A", False))
checa("unanime: repetido", U(["202607A", "202607A"]), ("202607A", False))
checa("unanime: divergente -> nulo", U(["202607A", "202607B"]), (None, True))
checa("unanime: vazio", U([]), (None, False))
TT = g["truncar_texto"]
checa("texto curto intacto", TT("116;101", 254), "116;101")
checa("texto nulo", TT(None, 254), None)
checa("texto truncado no limite", len(TT("x" * 300, 254)), 254)

# --- raio de busca ---
RB = g["raio_base"]
checa("extensao maior que a mediana", RB(50, 20), 50)
checa("extensao menor que a mediana -> mediana", RB(10, 20), 20)
checa("extensao ausente -> mediana", RB(None, 20), 20)
checa("extensao invalida -> mediana", RB("abc", 20), 20)
checa("extensao negativa -> mediana", RB(-5, 20), 20)
checa("fatores", (g["FATOR_RAIO"], g["FATOR_RAIO_AMPLIADO"]), (2.0, 5.0))

B = g["buscar_em_etapas"]
def coletor(alcance):
    """Simula coletar_candidatos: codigos cuja distancia <= raio pedido."""
    pedidos = []
    def coletar(raio):
        pedidos.append(raio)
        return {c: {"distancia": d} for c, d in alcance.items() if d <= raio}
    return coletar, pedidos
coletar, pedidos = coletor({"116BMG0010": 30})
por_codigo, raio, ampliado = B(coletar, 20)
checa("achado com fator 2: raio", (raio, ampliado), (40.0, False))
checa("achado com fator 2: uma so busca", pedidos, [40.0])
checa("achado com fator 2: candidatos", list(por_codigo), ["116BMG0010"])
coletar, pedidos = coletor({"116BMG0010": 70})
por_codigo, raio, ampliado = B(coletar, 20)
checa("so com fator 5: raio usado", (raio, ampliado), (100.0, True))
checa("so com fator 5: duas buscas", pedidos, [40.0, 100.0])
checa("so com fator 5: candidatos", list(por_codigo), ["116BMG0010"])
coletar, pedidos = coletor({"116BMG0010": 500})
por_codigo, raio, ampliado = B(coletar, 20)
checa("nem com fator 5", (por_codigo, raio, ampliado), ({}, 100.0, True))
# Candidato no raio normal, mesmo de outra BR, impede a ampliacao: os codigos
# mais distantes nao sao buscados.
coletar, pedidos = coletor({"381BMG0100": 30, "116BMG0010": 70})
por_codigo, raio, ampliado = B(coletar, 20)
checa("candidato incompativel nao amplia", (list(por_codigo), raio, ampliado),
      (["381BMG0100"], 40.0, False))

# --- preparo do trecho e calculo do km ---
g["preparar_linha"] = lambda geometria: ("LINHA:" + geometria, None)
P = g["preparar_trecho"]
checa("trecho apto", P("g", 10.0, 11.0), ("LINHA:g", None))
checa("km inicial ausente", P("g", None, 11.0), (None, "KM_DO_TRECHO_AUSENTE"))
checa("km final ausente", P("g", 10.0, None), (None, "KM_DO_TRECHO_AUSENTE"))
checa("km zero e valido", P("g", 0.0, 5.0), ("LINHA:g", None))
# Fora do escopo desta etapa: limites invertidos ou iguais nao bloqueiam o km.
checa("limites invertidos aceitos", P("g", 600.0, 500.0), ("LINHA:g", None))
checa("limites iguais aceitos", P("g", 5.0, 5.0), ("LINHA:g", None))

class Linha:
    """Simula a LineString: comprimento e posicao da projecao ao longo dela."""
    def __init__(self, comprimento, posicao):
        self.comprimento, self.posicao = comprimento, posicao
    def length(self):
        return self.comprimento
    def lineLocatePoint(self, ponto):
        return self.posicao
K = g["calcular_km"]
checa("km no meio", K(None, Linha(2000, 1000), 11.0, 13.0), 12.0)
checa("km no primeiro vertice", K(None, Linha(2000, 0), 11.0, 13.0), 11.0)
checa("km no ultimo vertice", K(None, Linha(2000, 2000), 11.0, 13.0), 13.0)
checa("km com limites invertidos segue a linha", K(None, Linha(1000, 250), 600.0, 500.0), 575.0)
checa("falha da projecao", K(None, Linha(1000, -1), 10.0, 11.0), None)
checa("projecao nao finita", K(None, Linha(1000, float("nan")), 10.0, 11.0), None)
checa("linha de comprimento nulo", K(None, Linha(0, 0), 10.0, 11.0), None)

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
checa("compara codigo interno, nao texto exibido", S("Trecho único", "L", 1), AV)
# Relacao_SNV "T" ou "N" tem prioridade: sempre a validar.
for relacao in ("T", "N", "t", "n", " T ", " N "):
    checa(f"coincidente + 2 codigos + {relacao!r}", S("TRECHO_COINCIDENTE", relacao, 2), AV)
    checa(f"unico trecho + {relacao!r}", S("UNICO_TRECHO", relacao, 1), AV)
for relacao in ("L", "", None, "X", "TN"):
    checa(f"coincidente + 2 codigos + {relacao!r} segue validado",
          S("TRECHO_COINCIDENTE", relacao, 2), V)

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

# Limites invertidos: o km acompanha a linha, do km inicial ao final.
checa("invertido: fracao 0 -> km inicial", I(600.0, 500.0, 0.0), 600.0)
checa("invertido: fracao 1 -> km final", I(600.0, 500.0, 1.0), 500.0)
checa("invertido: fracao 0,25", I(600.0, 500.0, 0.25), 575.0)

# --- localizacao dos campos pelo nome ---
R = g["resolver_campo"]
SNV = [("vl_codigo", ""), ("ds_tipo_ad", ""), ("ds_jurisdi", ""), ("versao_snv", "")]
# O caso real: o script pedia "Versão SNV" e a camada tem "versao_snv".
checa("Versão SNV acha versao_snv", R(SNV, "Versão SNV"), "versao_snv")
checa("nome identico", R(SNV, "versao_snv"), "versao_snv")
checa("maiusculas", R(SNV, "VERSAO_SNV"), "versao_snv")
checa("acento decomposto (NFD)",
      R([("Versa\u0303o SNV", "")], "Versão SNV"), "Versa\u0303o SNV")
checa("espaco nao separavel", R([("Versão\u00a0SNV", "")], "Versão SNV"), "Versão\u00a0SNV")
checa("espacos sobrando", R([(" Versão  SNV ", "")], "Versão SNV"), " Versão  SNV ")
checa("encontrado pelo alias", R([("v_snv", "Versão SNV")], "Versão SNV"), "v_snv")
checa("ausente", R(SNV, "Extensão (m)"), None)
checa("nome cortado NAO e aceito", R([("Versão SN", "")], "Versão SNV"), None)
checa("prefixo NAO e aceito", R([("Código", "")], "Código SNV"), None)
# Nome identico tem prioridade: nao ha ambiguidade com uma variante de grafia.
checa("identico vence variante", R([("Km", ""), ("KM", "")], "Km"), "Km")
try:
    R([("versao_snv", ""), ("Versão SNV", "")], "VERSAO SNV")
    raise AssertionError("ambiguidade nao detectada")
except ValueError:
    ok += 1
# Nome real tem prioridade sobre alias de outro campo.
checa("nome vence alias", R([("a", "versao_snv"), ("versao_snv", "")], "Versão SNV"),
      "versao_snv")

msg = g["mensagem_campo_ausente"]([("versao_sn", "Versão SNV"), ("vl_codigo", "")],
                                 ["Versão SNV x"], "SNV_202607A")
checa("mensagem cita o campo pedido", '"Versão SNV x" nao encontrado em SNV_202607A' in msg, True)
checa("mensagem sugere o mais parecido", "Mais parecidos: versao_sn" in msg, True)
checa("mensagem lista campos com alias", "versao_sn (alias: Versão SNV)" in msg, True)

# --- colunas da SGE copiadas para a saida ---
M = g["indices_mantidos"]
EXC = g["CAMPOS_OAE_EXCLUIDOS"]
checa("colunas excluidas sao as pedidas", EXC, ("Km", "Código SNV", "Versão SNV"))
nomes = ["ID", "Km", "Via", "Código SNV", "Extensão (m)", "Versão SNV", "Relacao_SNV"]
sge = [(n, "") for n in nomes]
idx, excluidos, ausentes = M(sge, EXC)
checa("mantem os demais, na ordem original", [nomes[i] for i in idx],
      ["ID", "Via", "Extensão (m)", "Relacao_SNV"])
checa("informa as excluidas", excluidos, ["Km", "Código SNV", "Versão SNV"])
checa("nenhuma ausente", ausentes, [])
# Mesma tolerancia da busca: sem acento ou com "_" tambem sao retiradas.
nomes2 = ["ID", "KM", "Codigo SNV", "versao_snv"]
idx, excluidos, ausentes = M([(n, "") for n in nomes2], EXC)
checa("grafia diferente tambem e retirada", [nomes2[i] for i in idx], ["ID"])
checa("nomes reais retirados", excluidos, ["KM", "Codigo SNV", "versao_snv"])
# Ausente e informada; nada e retirado por engano.
idx, excluidos, ausentes = M([("ID", ""), ("Km", "")], EXC)
checa("ausentes informadas", ausentes, ["Código SNV", "Versão SNV"])
checa("so a encontrada sai", idx, [0])
# Ambiguidade: nada e retirado e o nome e informado.
idx, excluidos, ausentes = M([("Km", "x"), ("km_", "Km")], ("Km",))
checa("identico resolve sem ambiguidade", excluidos, ["Km"])
idx, excluidos, ausentes = M([("KM", ""), ("km", "")], ("Km",))
checa("ambiguo: nada retirado", (idx, excluidos, ausentes), ([0, 1], [], ["Km"]))
# Campos usados pelo script nunca sao retirados.
for usado in ("Extensão (m)", "Via", "Relacao_SNV"):
    checa(f"{usado} nao e excluido",
          any(g["normalizar_nome_campo"](usado) == g["normalizar_nome_campo"](e) for e in EXC),
          False)

print(f"{ok} verificacoes OK")
