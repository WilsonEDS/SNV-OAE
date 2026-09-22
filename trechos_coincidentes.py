# -*- coding: utf-8 -*-
# =============================================================================
# TRECHOS COINCIDENTES DECLARADOS NO SNV - QGIS / PyQGIS
# =============================================================================
#
# 1. OBJETIVO
# -----------------------------------------------------------------------------
# Extrair da camada SNV os trechos FEDERAIS EXISTENTES que o proprio dado
# DECLARA como coincidentes, resumir essa declaracao aos numeros de BR
# envolvidos e agregar o resultado por UF.
#
# A camada SNV traz o campo "ds_coinc" com a lista de codigos de trecho que
# ocupam o mesmo eixo fisico, separados por ";". Quando essa lista tem mais de
# um codigo, o trecho e coincidente. O procedimento copia essas feicoes para uma
# camada nova e acrescenta um campo com os prefixos de tres digitos dos codigos
# listados - ou seja, as BRs que compartilham aquele eixo.
#
#   ds_coinc      = "010BDF0015;020BDF0015;030BDF0015"
#   Trechos-coinc = "010;020;030"
#
# Sobre essa camada de detalhe e feito um DISSOLVE por UF e por combinacao de
# BRs, que responde a pergunta de fundo: em cada UF, quais eixos sao
# compartilhados por quais BRs e quantos quilometros isso representa.
#
# O procedimento e puramente ATRIBUTIVO quanto a coincidencia: nao ha medicao,
# projecao ou prova geometrica de sobreposicao. Ele reporta o que a base afirma,
# nao o que a geometria demonstra. Essa distincao e deliberada e importa para a
# leitura do resultado: associacao_oae_snv.py resolve coincidencia por prova
# geometrica (codigos_sobrepostos / Rodovias_coincidentes) e NAO le "ds_coinc".
# Esta saida existe justamente para permitir confrontar as duas visoes - o
# declarado e o provado - sem que uma contamine a outra.
#
#
# 2. DADOS DE ENTRADA
# -----------------------------------------------------------------------------
#   Camada SNV (linear), nome em NOME_CAMADA_SNV:
#       - CAMPO_DS_COINC    ("ds_coinc")   : lista de codigos coincidentes
#         separados por ";" (ex.: "010BDF0015;020BDF0015"). Vazia ou com um
#         unico codigo quando o trecho nao e coincidente.
#       - CAMPO_SUPERFICIE  ("ds_superfi") : superficie do trecho. "PLA"
#         identifica trecho PLANEJADO.
#       - CAMPO_JURISDICAO  ("ds_jurisdi") : jurisdicao do trecho ("Federal",
#         "Estadual", "Municipal"...).
#       - CAMPO_UF_SNV      ("sg_uf")      : UF, usada como chave do dissolve.
#
#   A camada precisa estar carregada no projeto aberto do QGIS. O script e para
#   ser executado no Console Python do QGIS: a secao 5 usa o framework
#   Processing.
#
#
# 3. DADOS DE SAIDA
# -----------------------------------------------------------------------------
#   Duas camadas em memoria, ambas no tipo de geometria e no SRC da SNV:
#
#   a) NOME_CAMADA_SAIDA ("Trechos_Coincidentes") - detalhe, trecho a trecho:
#       - TODOS os campos originais da SNV, com os valores originais;
#       - CAMPO_TRECHOS_COINC ("Trechos-coinc"): prefixos de tres digitos dos
#         codigos de "ds_coinc", separados por ";", NA ORDEM EM QUE APARECEM no
#         campo de origem e com as repeticoes preservadas.
#
#   b) NOME_CAMADA_DISSOLVIDA ("Trechos_Coincidentes_dissolvido") - agregada,
#      um registro por UF e combinacao de BRs:
#       - CAMPO_UF_SNV        ("sg_uf")        : UF do grupo;
#       - CAMPO_TRECHOS_COINC ("Trechos-coinc"): combinacao de BRs do grupo;
#       - CAMPO_QTD_TRECHOS   ("Qtd_trechos")  : trechos de detalhe agregados;
#       - CAMPO_EXT_KM        ("Ext_km")       : extensao do grupo, em km,
#         medida na geometria JA dissolvida.
#
#   A camada de origem nao e modificada.
#
#
# 4. CRITERIOS
# -----------------------------------------------------------------------------
#   4.1 Filtro de superficie e jurisdicao
#       Equivale a expressao ds_superfi != 'PLA' AND ds_jurisdi = 'Federal'.
#       Trecho PLANEJADO nao tem existencia fisica, logo nao pode compartilhar
#       eixo com coisa alguma no terreno; trecho nao federal esta fora do escopo
#       do trabalho. Nenhum dos dois sustenta uma coincidencia relevante aqui, e
#       por isso o filtro e aplicado ANTES do criterio de ds_coinc - as
#       contagens de coincidencia passam a se referir ao universo ja filtrado.
#
#   4.2 Selecao por coincidencia
#       Entra na saida a feicao cujo "ds_coinc", depois de descartados os tokens
#       vazios, apresentar MINIMO_CODIGOS (2) ou mais codigos. "Mais de um
#       codigo" e contado sobre os codigos declarados, antes de qualquer juizo
#       sobre a forma deles: a coincidencia e um fato do dado de origem e nao
#       pode depender de o codigo estar bem formado.
#
#   4.3 Prefixo
#       O SNV codifica a BR nas tres primeiras posicoes do codigo do trecho.
#       Exigem-se tres DIGITOS, mesma regra de prefixo_codigo em
#       associacao_oae_snv.py: um token fora do padrao nao produz BR e e
#       descartado, sendo contabilizado no resumo. Se nenhum prefixo sobrar,
#       CAMPO_TRECHOS_COINC fica NULL - a feicao permanece na saida, porque ela
#       E coincidente; apenas nao foi possivel nomear as BRs.
#
#   4.4 Ordem e repeticao
#       A ordem original e preservada e as repeticoes NAO sao removidas. O campo
#       e um resumo fiel de "ds_coinc", e nao um conjunto normalizado: ordenar
#       ou deduplicar descartaria a correspondencia posicional com o codigo de
#       origem, que e o que torna o resultado conferivel feicao a feicao.
#
#   4.5 Dissolve
#       Uniao real das geometrias (native:dissolve) agrupando por sg_uf e
#       Trechos-coinc. Uniao, e nao mera coleta em multipart: os trechos
#       coincidentes ocupam o MESMO eixo, de modo que apenas junta-los manteria
#       a linha compartilhada repetida tantas vezes quantas forem as BRs e
#       inflaria a extensao do grupo.
#
# =============================================================================

from collections import Counter

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsDistanceArea,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsProject,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsWkbTypes,
    NULL,
)

# Importado aqui, e nao na secao 5 que o usa, para que a ausencia do framework
# interrompa a execucao antes da passagem completa pela SNV, e nao depois dela.
try:
    import processing
except ImportError as erro:
    raise Exception(
        "Framework Processing indisponivel: execute no Console Python do QGIS."
    ) from erro


# -----------------------------------------------------------------------------
# 0) CONFIGURACAO
# -----------------------------------------------------------------------------
NOME_CAMADA_SNV = "SNV_202607A"
NOME_CAMADA_SAIDA = "Trechos_Coincidentes"
NOME_CAMADA_DISSOLVIDA = "Trechos_Coincidentes_dissolvido"

CAMPO_DS_COINC = "ds_coinc"
CAMPO_SUPERFICIE = "ds_superfi"
CAMPO_JURISDICAO = "ds_jurisdi"
# Mesmo nome de campo usado em associacao_oae_snv.py.
CAMPO_UF_SNV = "sg_uf"

CAMPO_TRECHOS_COINC = "Trechos-coinc"
CAMPO_QTD_TRECHOS = "Qtd_trechos"
CAMPO_EXT_KM = "Ext_km"

# Filtro equivalente a ds_superfi != 'PLA' AND ds_jurisdi = 'Federal'.
SUPERFICIE_EXCLUIDA = "PLA"
JURISDICAO_EXIGIDA = "Federal"

# Separador usado pelo SNV dentro de ds_coinc.
SEPARADOR_CODIGOS = ";"

# "Mais de um codigo": dois ou mais codigos declarados apos o descarte dos
# tokens vazios.
MINIMO_CODIGOS = 2

# Mesmo limite conservador adotado em associacao_oae_snv.py: 254 caracteres
# mantem a saida exportavel para Shapefile/DBF sem perda silenciosa.
TAMANHO_MAX_TRECHOS = 254

# Elipsoide de recurso quando o SRC da camada nao declarar o seu: GRS80, o do
# SIRGAS 2000, em que o SNV e publicado.
ELIPSOIDE_PADRAO = "EPSG:7019"

# Quantos grupos sao listados no resumo final.
LIMITE_RESUMO_PREFIXOS = 10

# Tupla para garantir a ordem de impressao dos motivos de exclusao.
MOTIVOS_EXCLUSAO = (
    "SUPERFICIE_NULA",
    "SUPERFICIE_PLANEJADA",
    "JURISDICAO_NULA",
    "JURISDICAO_DIVERGENTE",
)


# -----------------------------------------------------------------------------
# 1) FUNCOES AUXILIARES DE SANEAMENTO DE VALORES
# -----------------------------------------------------------------------------
def codigo_valido(valor):
    """Normaliza um identificador textual sem inventar valor para nulos.

    Parametros:
        valor: conteudo bruto de um atributo textual (vl_codigo, ds_coinc...).

    Retorna:
        str nao vazia, sem espacos nas bordas, ou None.

    Hipotese metodologica:
        Sentinelas textuais de nulo ("NULL", "NONE", "NAN"), comuns em dados
        importados de planilha, sao tratadas como ausencia. Deixa-las passar
        criaria um "codigo" fantasma capaz de vencer uma selecao.

        Copia verbatim de associacao_oae_snv.py: aquele arquivo e um script
        plano, cuja importacao executaria a associacao inteira, e por isso nao
        pode ser importado. Manter nome e texto identicos torna a equivalencia
        verificavel na revisao.
    """
    if valor is None or valor == NULL:
        return None
    codigo = str(valor).strip()
    return codigo if codigo and codigo.upper() not in {"NULL", "NONE", "NAN"} else None


def prefixo_codigo(codigo):
    """Extrai o numero da BR embutido nos tres primeiros caracteres do codigo.

    Parametros:
        codigo: codigo de trecho do SNV (ex.: "116BMG0450").

    Retorna:
        str de tres digitos ("116"), ou None se o codigo nao tiver a forma
        esperada.

    Hipotese metodologica:
        O SNV codifica a BR nas tres primeiras posicoes do codigo. Exigir que
        sejam digitos evita promover a BR um fragmento de texto fora do padrao.

        Copia verbatim de associacao_oae_snv.py pelo motivo registrado em
        codigo_valido.
    """
    codigo = codigo_valido(codigo)
    if codigo is None or len(codigo) < 3 or not codigo[:3].isdigit():
        return None
    return codigo[:3]


def truncar_texto(texto, limite):
    """Limita um texto ao comprimento declarado do campo que vai recebe-lo.

    Parametros:
        texto: conteudo a gravar, ou None.
        limite: comprimento maximo do campo de destino.

    Retorna:
        str de no maximo `limite` caracteres, ou None se nao houver texto.

    Hipotese metodologica:
        Texto excedendo o comprimento declarado do campo e truncado em silencio
        - ou rejeitado - pelo provedor, o que faria a informacao desaparecer sem
        aviso. O corte e feito aqui, de forma deterministica, e sinalizado com o
        marcador [TRUNCADO], de modo que a perda seja sempre visivel no proprio
        dado.

        Copia verbatim de associacao_oae_snv.py pelo motivo registrado em
        codigo_valido.
    """
    if not texto:
        return None
    if len(texto) <= limite:
        return texto
    marcador = "...[TRUNCADO]"
    return texto[: limite - len(marcador)] + marcador


def texto_bruto(valor):
    """Le um atributo textual SEM normalizar, distinguindo apenas o nulo.

    Parametros:
        valor: conteudo bruto de um atributo textual.

    Retorna:
        str exatamente como armazenada (espacos e caixa preservados), ou None
        quando o atributo e nulo.

    Hipotese metodologica:
        Existe em separado de codigo_valido porque serve a um proposito oposto.
        codigo_valido sanea: apara espacos e trata sentinelas textuais de nulo,
        o que e correto para identificadores. O filtro de superficie e
        jurisdicao, ao contrario, precisa reproduzir uma comparacao de igualdade
        tal como o QGIS a avaliaria - qualquer normalizacao aqui faria o script
        aceitar registros que a expressao equivalente rejeitaria, e a
        divergencia passaria despercebida. Pelo mesmo motivo, string vazia NAO e
        tratada como nulo: em SQL, '' e um valor, e '' != 'PLA' e verdadeiro.
    """
    if valor is None or valor == NULL:
        return None
    return str(valor)


def motivo_exclusao(superficie, jurisdicao):
    """Aplica o filtro ds_superfi != 'PLA' AND ds_jurisdi = 'Federal'.

    Parametros:
        superficie: conteudo bruto de CAMPO_SUPERFICIE.
        jurisdicao: conteudo bruto de CAMPO_JURISDICAO.

    Retorna:
        None quando o trecho passa no filtro; caso contrario o motivo da
        exclusao, um dos valores de MOTIVOS_EXCLUSAO.

    Hipoteses metodologicas:
        Semantica SQL, nao Python: uma comparacao com NULL nao e verdadeira,
        portanto o atributo nulo REPROVA dos dois lados. Em Python puro,
        None != 'PLA' seria verdadeiro e admitiria em silencio trechos sem
        superficie declarada - exatamente os registros sobre os quais nada se
        sabe. O nulo e separado do valor divergente no retorno porque as duas
        situacoes tem causas distintas: uma e lacuna de cadastro, a outra e
        trecho fora do escopo, e o resumo precisa poder distingui-las.

        A comparacao e exata, sem aparar espacos nem uniformizar a caixa. Um
        ' Federal ' ou 'federal' na base e um defeito do dado, e corrigi-lo aqui
        em silencio faria esta saida divergir do que a mesma expressao produz na
        interface do QGIS - o resultado deixaria de ser conferivel.
    """
    superficie = texto_bruto(superficie)
    if superficie is None:
        return "SUPERFICIE_NULA"
    if superficie == SUPERFICIE_EXCLUIDA:
        return "SUPERFICIE_PLANEJADA"

    jurisdicao = texto_bruto(jurisdicao)
    if jurisdicao is None:
        return "JURISDICAO_NULA"
    if jurisdicao != JURISDICAO_EXIGIDA:
        return "JURISDICAO_DIVERGENTE"

    return None


def separar_codigos(valor):
    """Quebra o conteudo de ds_coinc na lista de codigos declarados.

    Parametros:
        valor: conteudo bruto de CAMPO_DS_COINC.

    Retorna:
        list[str] com os codigos na ordem original, repeticoes preservadas.
        Lista vazia quando o campo e nulo, sentinela ou so contem separadores.

    Hipoteses metodologicas:
        Tokens vazios (separadores consecutivos, separador final, espacos) sao
        ruido de formatacao, nao codigos: conta-los inflaria artificialmente a
        quantidade de coincidencias e faria entrar na saida trechos que
        declaram um unico codigo seguido de ";".

        A ordem e as repeticoes sao mantidas porque a lista precisa continuar
        correspondendo, posicao a posicao, ao texto de ds_coinc; e essa
        correspondencia que permite conferir o resultado feicao a feicao.
    """
    bruto = codigo_valido(valor)
    if bruto is None:
        return []
    codigos = []
    for parte in bruto.split(SEPARADOR_CODIGOS):
        codigo = codigo_valido(parte)
        if codigo is not None:
            codigos.append(codigo)
    return codigos


def prefixos_coincidentes(valor):
    """Resume ds_coinc nos numeros de BR dos codigos declarados.

    Parametros:
        valor: conteudo bruto de CAMPO_DS_COINC.

    Retorna:
        tupla (texto, qtd_codigos, qtd_descartados):
            texto           : prefixos de tres digitos unidos por ";", na ordem
                              original e com repeticoes, ou None se nenhum
                              codigo tiver prefixo valido;
            qtd_codigos     : quantidade de codigos declarados (base da selecao);
            qtd_descartados : quantos desses codigos nao produziram prefixo.

    Hipotese metodologica:
        A contagem de codigos e devolvida junto com o texto, e nao recalculada
        pelo chamador, para que a selecao da feicao e o conteudo gravado nela
        derivem da MESMA leitura de ds_coinc. Recontar em outro ponto abriria a
        possibilidade de um trecho ser selecionado por um criterio e descrito
        por outro.
    """
    codigos = separar_codigos(valor)
    prefixos = []
    descartados = 0
    for codigo in codigos:
        prefixo = prefixo_codigo(codigo)
        if prefixo is None:
            descartados += 1
        else:
            prefixos.append(prefixo)
    texto = truncar_texto(SEPARADOR_CODIGOS.join(prefixos), TAMANHO_MAX_TRECHOS)
    return texto, len(codigos), descartados


def rotulo_grupo(uf, trechos):
    """Descreve um grupo do dissolve para as mensagens de resumo.

    Parametros:
        uf: valor de sg_uf do grupo, ou None.
        trechos: valor de Trechos-coinc do grupo, ou None.

    Retorna:
        str no formato "UF: BRs", com "(sem UF)" / "(sem BR identificada)" no
        lugar dos nulos.

    Hipotese metodologica:
        Um grupo nulo impresso como "None" seria confundido com falha do script.
        Nomear a ausencia deixa claro que ela veio do dado.
    """
    return f"{uf or '(sem UF)'}: {trechos or '(sem BR identificada)'}"


# -----------------------------------------------------------------------------
# 2) CAMADA E CAMPOS
# -----------------------------------------------------------------------------
projeto = QgsProject.instance()

lista_snv = projeto.mapLayersByName(NOME_CAMADA_SNV)
if not lista_snv:
    raise Exception(f'Camada "{NOME_CAMADA_SNV}" nao encontrada no projeto.')
# Nome duplicado impediria saber qual camada foi processada: o resultado
# deixaria de ser rastreavel, portanto a execucao e interrompida.
if len(lista_snv) != 1:
    raise Exception(f'Nome de camada duplicado: mantenha uma unica "{NOME_CAMADA_SNV}".')

camada_snv = lista_snv[0]
if not camada_snv.isValid() or not camada_snv.crs().isValid():
    raise Exception("Camada de entrada ou seu CRS invalido.")
if camada_snv.geometryType() != QgsWkbTypes.LineGeometry:
    raise Exception(f'A camada "{NOME_CAMADA_SNV}" precisa ser linear.')
if camada_snv.wkbType() in (QgsWkbTypes.Unknown, QgsWkbTypes.NoGeometry):
    raise Exception("Tipo de geometria da SNV indefinido; nao e possivel criar a saida.")

campos_snv = {campo.name() for campo in camada_snv.fields()}
obrigatorios_snv = {
    CAMPO_DS_COINC,
    CAMPO_SUPERFICIE,
    CAMPO_JURISDICAO,
    CAMPO_UF_SNV,
}
faltantes_snv = sorted(obrigatorios_snv - campos_snv)
if faltantes_snv:
    raise Exception(f"Campos ausentes em {NOME_CAMADA_SNV}: {', '.join(faltantes_snv)}")
# Dois campos homonimos na saida seriam indistinguiveis na tabela de atributos e
# o valor calculado poderia ser lido como se fosse dado de origem.
if CAMPO_TRECHOS_COINC in campos_snv:
    raise Exception(
        f'A camada "{NOME_CAMADA_SNV}" ja possui o campo "{CAMPO_TRECHOS_COINC}".'
    )


# -----------------------------------------------------------------------------
# 3) CAMADA DE SAIDA (DETALHE)
# -----------------------------------------------------------------------------
# A saida permanece no SRC ORIGINAL da SNV: nada aqui e reprojetado, e a
# medicao da secao 5 e elipsoidal, independente do plano de projecao.
saida = QgsVectorLayer(
    f"{QgsWkbTypes.displayString(camada_snv.wkbType())}?crs={camada_snv.crs().authid()}",
    NOME_CAMADA_SAIDA,
    "memory",
)
if not saida.isValid():
    raise Exception("Falha ao criar a camada de saida em memoria.")

provedor_saida = saida.dataProvider()
provedor_saida.addAttributes(camada_snv.fields())
provedor_saida.addAttributes(
    [QgsField(CAMPO_TRECHOS_COINC, QVariant.String, len=TAMANHO_MAX_TRECHOS)]
)
saida.updateFields()

idx_trechos_coinc = saida.fields().indexOf(CAMPO_TRECHOS_COINC)
if idx_trechos_coinc < 0:
    raise RuntimeError("Estrutura da camada de saida divergente da esperada.")


# -----------------------------------------------------------------------------
# 4) PROCESSAMENTO DOS TRECHOS
# -----------------------------------------------------------------------------
contagem = {
    "TOTAL": 0,
    "SELECIONADOS": 0,
    "SEM_DS_COINC": 0,
    "CODIGO_UNICO": 0,
    "CODIGO_FORA_DO_PADRAO": 0,
    "SEM_PREFIXO_VALIDO": 0,
}
contagem.update({motivo: 0 for motivo in MOTIVOS_EXCLUSAO})
# Chave (sg_uf, Trechos-coinc): a contagem por grupo nasce da MESMA passagem que
# gera a camada de detalhe, e nao de uma releitura posterior, de modo que
# Qtd_trechos nunca possa divergir do que foi efetivamente gravado.
grupos = Counter()
novas_feicoes = []

for trecho in camada_snv.getFeatures():
    contagem["TOTAL"] += 1

    # O filtro vem primeiro: trecho planejado ou nao federal esta fora do
    # escopo, e contabiliza-lo como "coincidente" distorceria o resumo.
    motivo = motivo_exclusao(trecho[CAMPO_SUPERFICIE], trecho[CAMPO_JURISDICAO])
    if motivo is not None:
        contagem[motivo] += 1
        continue

    texto_prefixos, qtd_codigos, qtd_descartados = prefixos_coincidentes(
        trecho[CAMPO_DS_COINC]
    )

    if qtd_codigos == 0:
        contagem["SEM_DS_COINC"] += 1
        continue
    if qtd_codigos < MINIMO_CODIGOS:
        contagem["CODIGO_UNICO"] += 1
        continue

    contagem["SELECIONADOS"] += 1
    contagem["CODIGO_FORA_DO_PADRAO"] += qtd_descartados
    if texto_prefixos is None:
        contagem["SEM_PREFIXO_VALIDO"] += 1

    nova = QgsFeature(saida.fields())
    nova.setGeometry(QgsGeometry(trecho.geometry()))
    nova.setAttributes(trecho.attributes() + [None])
    nova.setAttribute(idx_trechos_coinc, texto_prefixos)
    novas_feicoes.append(nova)

    grupos[(texto_bruto(trecho[CAMPO_UF_SNV]), texto_prefixos)] += 1

# addFeatures devolve (bool, lista); testar a tupla inteira daria sempre
# verdadeiro e engoliria a falha de gravacao.
if novas_feicoes and not provedor_saida.addFeatures(novas_feicoes)[0]:
    raise RuntimeError("Falha ao gravar as feicoes na camada de saida.")
saida.updateExtents()

if contagem["SELECIONADOS"] != len(novas_feicoes):
    raise RuntimeError("Contagem de selecionados divergente das feicoes gravadas.")
if saida.featureCount() != len(novas_feicoes):
    raise RuntimeError("A camada de saida nao recebeu todas as feicoes selecionadas.")


# -----------------------------------------------------------------------------
# 5) DISSOLVE POR UF E COMBINACAO DE BRs
# -----------------------------------------------------------------------------
# native:dissolve faz UNIAO das geometrias do grupo. Simplesmente coleta-las em
# multipart manteria o eixo compartilhado repetido uma vez por BR, e Ext_km
# sairia multiplicado.
dissolvido_bruto = processing.run(
    "native:dissolve",
    {
        "INPUT": saida,
        "FIELD": [CAMPO_UF_SNV, CAMPO_TRECHOS_COINC],
        "OUTPUT": "memory:",
    },
)["OUTPUT"]

# A extensao e medida sobre o ELIPSOIDE, e nao no EPSG:5880 que
# associacao_oae_snv.py adota. A divergencia e deliberada: la se medem
# distancias locais ao redor de uma OAE, onde o plano projetado e instrumento
# adequado; aqui se somam extensoes de centenas de quilometros espalhadas pelo
# pais, faixa em que a distorcao da policonica se acumula ao longo do eixo.
medidor = QgsDistanceArea()
medidor.setSourceCrs(camada_snv.crs(), projeto.transformContext())
medidor.setEllipsoid(camada_snv.crs().ellipsoidAcronym() or ELIPSOIDE_PADRAO)
# Sem elipsoide, measureLength devolve o comprimento nas unidades do SRC - graus,
# num SRC geografico como o do SNV. O numero continuaria saindo, silenciosamente
# errado por ordens de grandeza, e por isso a execucao para aqui.
if not medidor.willUseEllipsoid():
    raise Exception(
        "Medicao elipsoidal indisponivel: Ext_km sairia nas unidades do SRC."
    )

dissolvido = QgsVectorLayer(
    f"{QgsWkbTypes.displayString(dissolvido_bruto.wkbType())}"
    f"?crs={camada_snv.crs().authid()}",
    NOME_CAMADA_DISSOLVIDA,
    "memory",
)
if not dissolvido.isValid():
    raise Exception("Falha ao criar a camada dissolvida em memoria.")

provedor_dissolvido = dissolvido.dataProvider()
# Somente os quatro campos do grupo. native:dissolve propaga para o resultado os
# atributos da PRIMEIRA feicao de cada grupo: um vl_codigo ou vl_km_inic herdado
# ao acaso seria lido como se descrevesse o grupo inteiro.
provedor_dissolvido.addAttributes(
    [
        QgsField(CAMPO_UF_SNV, QVariant.String, len=10),
        QgsField(CAMPO_TRECHOS_COINC, QVariant.String, len=TAMANHO_MAX_TRECHOS),
        QgsField(CAMPO_QTD_TRECHOS, QVariant.Int),
        QgsField(CAMPO_EXT_KM, QVariant.Double, len=20, prec=3),
    ]
)
dissolvido.updateFields()

feicoes_dissolvidas = []
extensao_total_km = 0.0
resumo_grupos = []

for grupo in dissolvido_bruto.getFeatures():
    chave = (texto_bruto(grupo[CAMPO_UF_SNV]), texto_bruto(grupo[CAMPO_TRECHOS_COINC]))
    if chave not in grupos:
        raise RuntimeError(f"Grupo dissolvido sem correspondencia no detalhe: {chave}.")

    extensao_km = medidor.convertLengthMeasurement(
        medidor.measureLength(grupo.geometry()), QgsUnitTypes.DistanceKilometers
    )
    extensao_total_km += extensao_km

    nova = QgsFeature(dissolvido.fields())
    nova.setGeometry(QgsGeometry(grupo.geometry()))
    nova.setAttributes([chave[0], chave[1], grupos[chave], extensao_km])
    feicoes_dissolvidas.append(nova)
    resumo_grupos.append((rotulo_grupo(*chave), grupos[chave], extensao_km))

if feicoes_dissolvidas and not provedor_dissolvido.addFeatures(feicoes_dissolvidas)[0]:
    raise RuntimeError("Falha ao gravar as feicoes na camada dissolvida.")
dissolvido.updateExtents()

# O dissolve nao pode perder nem inventar trecho: a soma das contagens por grupo
# tem de reproduzir exatamente o detalhe.
if len(feicoes_dissolvidas) != len(grupos):
    raise RuntimeError("Numero de grupos dissolvidos divergente do detalhe.")
if sum(grupos.values()) != len(novas_feicoes):
    raise RuntimeError("Soma de Qtd_trechos divergente do total de trechos gravados.")

projeto.addMapLayer(saida)
projeto.addMapLayer(dissolvido)


# -----------------------------------------------------------------------------
# 6) RESUMO E CONFERENCIA
# -----------------------------------------------------------------------------
print(f'Camada de origem : {NOME_CAMADA_SNV} ({contagem["TOTAL"]} trechos lidos)')
print(f'Excluidos pelo filtro {CAMPO_SUPERFICIE} != "{SUPERFICIE_EXCLUIDA}"'
      f' e {CAMPO_JURISDICAO} = "{JURISDICAO_EXIGIDA}":')
for motivo in MOTIVOS_EXCLUSAO:
    print(f"  {motivo.ljust(22)}: {contagem[motivo]}")

print(f'Camada criada    : {NOME_CAMADA_SAIDA} ({contagem["SELECIONADOS"]} trechos)')
print("  (as contagens abaixo se referem apenas aos trechos que passaram no filtro)")
print(f'  sem {CAMPO_DS_COINC} preenchido : {contagem["SEM_DS_COINC"]}')
print(f'  com codigo unico        : {contagem["CODIGO_UNICO"]}')
print(f'  codigos fora do padrao  : {contagem["CODIGO_FORA_DO_PADRAO"]}')
print(f'  {CAMPO_TRECHOS_COINC} nulo    : {contagem["SEM_PREFIXO_VALIDO"]}')

print(f"Camada criada    : {NOME_CAMADA_DISSOLVIDA} ({len(feicoes_dissolvidas)} grupos,"
      f" {extensao_total_km:.3f} km)")

if resumo_grupos:
    print(f"Grupos de maior extensao (ate {LIMITE_RESUMO_PREFIXOS}):")
    # Ordena por extensao decrescente e, no empate, pelo rotulo: a listagem e
    # apenas de conferencia e precisa ser reproduzivel entre execucoes.
    ordenados = sorted(resumo_grupos, key=lambda item: (-item[2], item[0]))
    for rotulo, quantidade, extensao_km in ordenados[:LIMITE_RESUMO_PREFIXOS]:
        print(f"  {rotulo}: {quantidade} trechos, {extensao_km:.3f} km")
