"""Extrai e testa as funcoes puras (sem dependencia QGIS) de trechos_coincidentes.py."""
import ast, pathlib

fonte = (pathlib.Path(__file__).resolve().parent.parent / 'trechos_coincidentes.py').read_text(encoding='utf-8')
arvore = ast.parse(fonte)

alvos = {"codigo_valido", "prefixo_codigo", "truncar_texto", "texto_bruto",
         "motivo_exclusao", "separar_codigos", "prefixos_coincidentes",
         "brs_do_eixo", "rotulo_grupo"}
consts = {"SEPARADOR_CODIGOS", "MINIMO_CODIGOS", "TAMANHO_MAX_TRECHOS",
          "SUPERFICIE_EXCLUIDA", "JURISDICAO_EXIGIDA", "MOTIVOS_EXCLUSAO"}

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

# --- 11) leitura crua do atributo (sem normalizar) ---
for entrada, esperado in [
    (None, None), ("PLA", "PLA"), ("", ""), (" x ", " x "),
    ("federal", "federal"), ("NULL", "NULL"),
]:
    checa(f"texto_bruto({entrada!r})", g["texto_bruto"](entrada), esperado)
# Diferenca deliberada em relacao a codigo_valido, que sanea.
checa("texto_bruto nao apara", g["texto_bruto"](" PLA ") == g["codigo_valido"](" PLA "),
      False)

# --- 12) filtro ds_superfi != 'PLA' AND ds_jurisdi = 'Federal' ---
# passa
for superficie in ["ASF", "IMP", "LEN", "EOP"]:
    checa(f"passa ({superficie}, Federal)",
          g["motivo_exclusao"](superficie, "Federal"), None)
# superficie planejada
checa("planejado", g["motivo_exclusao"]("PLA", "Federal"), "SUPERFICIE_PLANEJADA")
# jurisdicao divergente
for jurisdicao in ["Estadual", "Municipal", "Coincidente", "federal", "FEDERAL"]:
    checa(f"jurisdicao {jurisdicao!r}",
          g["motivo_exclusao"]("ASF", jurisdicao), "JURISDICAO_DIVERGENTE")

# --- 13) semantica SQL: NULL reprova dos dois lados ---
checa("superficie nula", g["motivo_exclusao"](None, "Federal"), "SUPERFICIE_NULA")
checa("jurisdicao nula", g["motivo_exclusao"]("ASF", None), "JURISDICAO_NULA")
# Ordem de avaliacao: a superficie e julgada antes.
checa("ambas nulas", g["motivo_exclusao"](None, None), "SUPERFICIE_NULA")
checa("planejado e sem jurisdicao",
      g["motivo_exclusao"]("PLA", None), "SUPERFICIE_PLANEJADA")

# --- 14) string vazia e valor, nao nulo (como em SQL) ---
checa("superficie vazia passa", g["motivo_exclusao"]("", "Federal"), None)
checa("jurisdicao vazia", g["motivo_exclusao"]("ASF", ""), "JURISDICAO_DIVERGENTE")

# --- 15) comparacao exata: espacos nas bordas importam ---
checa("PLA com espacos nao e PLA", g["motivo_exclusao"](" PLA ", "Federal"), None)
checa("Federal com espacos",
      g["motivo_exclusao"]("ASF", " Federal "), "JURISDICAO_DIVERGENTE")

# --- 16) os motivos devolvidos sao os declarados em MOTIVOS_EXCLUSAO ---
motivos_possiveis = {
    g["motivo_exclusao"](s_, j_)
    for s_ in [None, "", "PLA", " PLA ", "ASF"]
    for j_ in [None, "", "Federal", "federal", "Estadual"]
}
checa("motivos declarados", motivos_possiveis - {None} <= set(g["MOTIVOS_EXCLUSAO"]),
      True)
# As constantes do filtro sao as do enunciado.
checa("superficie excluida", g["SUPERFICIE_EXCLUIDA"], "PLA")
checa("jurisdicao exigida", g["JURISDICAO_EXIGIDA"], "Federal")

# --- 17) rotulo dos grupos do dissolve ---
checa("rotulo normal", g["rotulo_grupo"]("DF", "010;020"), "DF: 010;020")
checa("rotulo sem BR", g["rotulo_grupo"]("DF", None), "DF: (sem BR identificada)")
checa("rotulo sem UF", g["rotulo_grupo"](None, "010;020"), "(sem UF): 010;020")
checa("rotulo sem nada", g["rotulo_grupo"](None, None),
      "(sem UF): (sem BR identificada)")

# --- chave canonica do eixo (BRs_eixo) ---
# O caso da tela: o mesmo eixo visto da BR-210 e da BR-174 gerava dois grupos no
# dissolve, porque Trechos-coinc depende de qual trecho o gerou. A chave
# canonica faz os dois cairem no mesmo grupo.
checa("eixo visto da 210", g["brs_do_eixo"]("210;174"), "174;210")
checa("eixo visto da 174", g["brs_do_eixo"]("174;210"), "174;210")
checa("mesma chave dos dois lados",
      g["brs_do_eixo"]("210;174"), g["brs_do_eixo"]("174;210"))
checa("eixo do AC", g["brs_do_eixo"]("364;307"), g["brs_do_eixo"]("307;364"))

# ordem numerica crescente, sem repeticao
checa("ordem crescente", g["brs_do_eixo"]("020;010;030"), "010;020;030")
checa("duplicata removida", g["brs_do_eixo"]("010;010"), "010")
checa("duplicata no meio", g["brs_do_eixo"]("010;020;010"), "010;020")
checa("ja canonico", g["brs_do_eixo"]("010;020;030"), "010;020;030")

# nulos e textos sem BR alguma
for entrada in [None, "", ";;", "   ", "NULL"]:
    checa(f"brs_do_eixo({entrada!r})", g["brs_do_eixo"](entrada), None)

# so tokens de exatamente tres digitos entram na chave
checa("token invalido descartado", g["brs_do_eixo"]("010;ABC"), "010")
checa("so invalidos", g["brs_do_eixo"]("ABC;XYZ"), None)
checa("token curto", g["brs_do_eixo"]("010;12"), "010")
checa("token longo", g["brs_do_eixo"]("010;0100"), "010")
# O marcador de truncamento nao pode virar uma "BR" e criar um grupo espurio.
checa("marcador de truncamento",
      g["brs_do_eixo"]("010;020;...[TRUNCADO]"), "010;020")

# idempotencia: aplicar a chave sobre ela mesma nao muda nada
for entrada in ["210;174", "010;010", "020;010;030", "010;ABC"]:
    checa(f"idempotente({entrada!r})",
          g["brs_do_eixo"](g["brs_do_eixo"](entrada)), g["brs_do_eixo"](entrada))

print(f"{ok} verificacoes OK")
