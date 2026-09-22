# -*- coding: utf-8 -*-
# =============================================================================
# TRECHOS COINCIDENTES PROVADOS PELA GEOMETRIA (METODOLOGIA 2) - QGIS / PyQGIS
# =============================================================================
#
# 1. OBJETIVO
# -----------------------------------------------------------------------------
# Identificar, na malha SNV, os trechos FEDERAIS EXISTENTES que compartilham
# eixo com outro trecho, provando a coincidencia pela GEOMETRIA: sobreposicao
# parcial ou total entre as linhas. Nada e lido do atributo "ds_coinc".
#
# Esta e a metodologia 2. A metodologia 1 (trechos_coincidentes.py) responde a
# mesma pergunta lendo "ds_coinc", isto e, reportando o que o DNIT DECLARA, e
# por isso herda os defeitos da declaracao: um ds_coinc desatualizado,
# incompleto ou com codigo fora do padrao cria uma coincidencia que nao existe,
# ou esconde uma que existe, e olhando apenas a m1 nao ha como saber qual dos
# dois ocorreu.
#
# As duas saidas valem por serem INDEPENDENTES. Onde elas divergem ha ou erro de
# cadastro no ds_coinc, ou defeito de digitalizacao na malha - em ambos os casos
# um achado. Esperar que coincidam seria perder o proposito de ter duas.
#
# A prova aqui e a mesma que associacao_oae_snv.py aplica localmente ao redor de
# uma OAE (funcao codigos_sobrepostos), generalizada para a malha inteira, sem
# ponto de referencia.
#
#
# 2. DADOS DE ENTRADA
# -----------------------------------------------------------------------------
#   Camada SNV (linear), nome em NOME_CAMADA_SNV:
#       - CAMPO_VL_CODIGO   ("vl_codigo")  : codigo do trecho (ex.: 116BMG0450);
#         dele sai o numero da BR.
#       - CAMPO_SUPERFICIE  ("ds_superfi") : superficie do trecho. "PLA"
#         identifica trecho PLANEJADO.
#       - CAMPO_JURISDICAO  ("ds_jurisdi") : jurisdicao do trecho.
#       - CAMPO_UF_SNV      ("sg_uf")      : UF, usada como chave do dissolve.
#
#   A camada precisa estar carregada no projeto aberto do QGIS. O script e para
#   ser executado no Console Python do QGIS: a secao 6 usa o framework
#   Processing.
#
#
# 3. DADOS DE SAIDA
# -----------------------------------------------------------------------------
#   Duas camadas em memoria, ambas no tipo de geometria e no SRC da SNV:
#
#   a) NOME_CAMADA_SAIDA ("Trechos_Coincidentes_M2") - detalhe, trecho a trecho:
#       - TODOS os campos originais da SNV;
#       - CAMPO_TRECHOS_COINC ("Trechos-coinc") : BRs que dividem o eixo, a
#         propria primeiro e as parceiras em ordem numerica;
#       - CAMPO_QTD_PARCEIROS ("Qtd_parceiros") : trechos distintos sobrepostos;
#       - CAMPO_EXT_SOBREP_KM ("Ext_sobrep_km") : extensao do proprio trecho
#         efetivamente coberta por algum parceiro;
#       - CAMPO_PERC_SOBREP   ("Perc_sobrep")   : essa extensao dividida pela
#         extensao do trecho;
#       - CAMPO_TIPO_SOBREP   ("Tipo_sobrep")   : TOTAL | PARCIAL |
#         INDETERMINADO;
#       - CAMPO_TIPO_COINC    ("Tipo_coinc")    : ENTRE_BRS | MESMA_BR | AMBOS |
#         INDETERMINADO.
#
#   b) NOME_CAMADA_DISSOLVIDA ("Trechos_Coincidentes_M2_dissolvido") - agregada,
#      um registro por UF e combinacao de BRs, com sg_uf, Trechos-coinc,
#      CAMPO_QTD_TRECHOS ("Qtd_trechos") e CAMPO_EXT_KM ("Ext_km").
#
#   A camada de origem nao e modificada. A estrutura espelha a da metodologia 1
#   para que as duas possam ser cruzadas diretamente por vl_codigo.
#
#
# 4. CRITERIOS
# -----------------------------------------------------------------------------
#   4.1 Filtro de superficie e jurisdicao
#       Identico ao da metodologia 1: ds_superfi != 'PLA' AND
#       ds_jurisdi = 'Federal'. Trecho PLANEJADO nao tem existencia fisica e
#       trecho nao federal esta fora do escopo. Os PARCEIROS saem do mesmo
#       universo ja filtrado: provar uma coincidencia com um trecho que a
#       propria metodologia exclui tornaria as duas saidas incomparaveis.
#
#   4.2 Prova da sobreposicao
#       Interseccao EXATA entre as duas geometrias, da qual somente as porcoes
#       LINEARES de comprimento positivo contam. Um cruzamento (viaduto,
#       entroncamento) produz um ponto, nao um trecho comum, e nao prova
#       coincidencia alguma.
#
#       Nao se aplica buffer, snap ou deslocamento de vertice, pela mesma
#       hipotese ja registrada em associacao_oae_snv.py: a coincidencia precisa
#       existir no dado, nao ser fabricada por tolerancia. Em compensacao, fica
#       a limitacao correspondente - dois eixos fisicamente coincidentes
#       digitalizados com centimetros de diferenca NAO sao detectados aqui. E
#       exatamente uma das divergencias que o confronto com a metodologia 1
#       serve para revelar.
#
#   4.3 Extensao coberta
#       Medida sobre a UNIAO das porcoes comuns, nunca pela soma delas: dois
#       parceiros podem cobrir o mesmo pedaco de eixo, e somar contaria esse
#       pedaco duas vezes, podendo produzir percentual acima de 100%.
#
#   4.4 TOTAL x PARCIAL
#       TOTAL quando a cobertura alcanca LIMIAR_SOBREPOSICAO_TOTAL da extensao
#       do trecho. A folga absorve arredondamento de coordenada sem admitir
#       sobreposicao realmente parcial. Perc_sobrep e gravado junto para que a
#       classificacao seja conferivel, e nao um rotulo opaco.
#
#   4.5 Pares da mesma BR
#       Dois codigos DISTINTOS da MESMA BR sobrepostos sao geometria duplicada
#       no SNV, e nao coincidencia entre rodovias. O fato e verdadeiro e precisa
#       ser auditavel, por isso a feicao entra na saida - mas marcada em
#       Tipo_coinc e contada a parte, para nao ser lida como duas rodovias
#       dividindo um eixo.
#
#   4.6 Determinismo
#       Cada par e avaliado uma unica vez e o resultado e lancado nas duas
#       feicoes; as listas de parceiros sao conjuntos e as BRs saem ordenadas.
#       O resultado nao depende da ordem de leitura das feicoes.
#
# =============================================================================

import math
from collections import Counter

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsDistanceArea,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsProject,
    QgsSpatialIndex,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsWkbTypes,
    NULL,
)

# Importado aqui, e nao na secao 6 que o usa, para que a ausencia do framework
# interrompa a execucao antes da varredura da malha, e nao depois dela.
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
NOME_CAMADA_SAIDA = "Trechos_Coincidentes_M2"
NOME_CAMADA_DISSOLVIDA = "Trechos_Coincidentes_M2_dissolvido"

CAMPO_VL_CODIGO = "vl_codigo"
CAMPO_SUPERFICIE = "ds_superfi"
CAMPO_JURISDICAO = "ds_jurisdi"
CAMPO_UF_SNV = "sg_uf"

CAMPO_TRECHOS_COINC = "Trechos-coinc"
CAMPO_QTD_PARCEIROS = "Qtd_parceiros"
CAMPO_EXT_SOBREP_KM = "Ext_sobrep_km"
CAMPO_PERC_SOBREP = "Perc_sobrep"
CAMPO_TIPO_SOBREP = "Tipo_sobrep"
CAMPO_TIPO_COINC = "Tipo_coinc"

CAMPO_QTD_TRECHOS = "Qtd_trechos"
CAMPO_EXT_KM = "Ext_km"

# Filtro equivalente a ds_superfi != 'PLA' AND ds_jurisdi = 'Federal'.
SUPERFICIE_EXCLUIDA = "PLA"
JURISDICAO_EXIGIDA = "Federal"

# Separador das BRs em Trechos-coinc, o mesmo do ds_coinc lido na metodologia 1.
SEPARADOR_CODIGOS = ";"

# Fracao da extensao do trecho a partir da qual a sobreposicao e TOTAL.
LIMIAR_SOBREPOSICAO_TOTAL = 0.999

# Mesmo limite conservador adotado em associacao_oae_snv.py: 254 caracteres
# mantem a saida exportavel para Shapefile/DBF sem perda silenciosa.
TAMANHO_MAX_TRECHOS = 254

# Elipsoide de recurso quando o SRC da camada nao declarar o seu: GRS80, o do
# SIRGAS 2000, em que o SNV e publicado.
ELIPSOIDE_PADRAO = "EPSG:7019"

# A varredura da malha nacional e demorada, e um console mudo e indistinguivel
# de um travamento.
INTERVALO_PROGRESSO = 5000

# Quantos grupos sao listados no resumo final.
LIMITE_RESUMO_PREFIXOS = 10

# Tuplas para garantir a ordem de impressao dos grupos no resumo.
MOTIVOS_EXCLUSAO = (
    "SUPERFICIE_NULA",
    "SUPERFICIE_PLANEJADA",
    "JURISDICAO_NULA",
    "JURISDICAO_DIVERGENTE",
)
TIPOS_COINC = ("ENTRE_BRS", "MESMA_BR", "AMBOS", "INDETERMINADO")
TIPOS_SOBREP = ("TOTAL", "PARCIAL", "INDETERMINADO")


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

        Copia verbatim de trechos_coincidentes.py, pelo mesmo motivo que impede
        importar aquele script.
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

        Copia verbatim de trechos_coincidentes.py: o filtro precisa ser
        identico ao da metodologia 1 para que as duas saidas sejam comparaveis.
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


def texto_rodovias(prefixo_proprio, prefixos_parceiros):
    """Monta o texto das BRs que dividem o eixo de um trecho.

    Parametros:
        prefixo_proprio: BR do proprio trecho (tres digitos) ou None.
        prefixos_parceiros: iteravel com as BRs dos trechos sobrepostos,
            podendo conter None.

    Retorna:
        str com as BRs separadas por ";", a propria primeiro e as demais em
        ordem numerica crescente, sem repeticao; ou None quando nenhum PARCEIRO
        tiver BR identificavel.

    Hipoteses metodologicas:
        A BR propria encabeca a lista para que o campo seja autossuficiente na
        leitura ("aqui a BR-020 divide o eixo com a 010 e a 030") sem exigir o
        cruzamento com vl_codigo. As demais seguem em ordem numerica, que
        assegura o determinismo. Mesma forma de rodovias_coincidentes_texto em
        associacao_oae_snv.py.

        Consequencia deliberada: dois trechos do MESMO eixo, um da BR-010 e
        outro da BR-020, produzem textos distintos ("010;020" e "020;010") e
        portanto caem em grupos distintos do dissolve. O dissolve da metodologia
        2 agrega o eixo tal como visto de cada BR, e nao o eixo em si.

        Sem nenhum parceiro identificavel o retorno e None, e nao a BR propria
        sozinha: o trecho E coincidente, mas escrever apenas "020" o descreveria
        como um eixo exclusivo da BR-020, afirmando o contrario do que se
        provou.
    """
    parceiras = {prefixo for prefixo in prefixos_parceiros if prefixo is not None}
    if not parceiras:
        return None

    rodovias = set(parceiras)
    if prefixo_proprio is not None:
        rodovias.add(prefixo_proprio)

    if prefixo_proprio in rodovias:
        ordenadas = [prefixo_proprio] + sorted(rodovias - {prefixo_proprio})
    else:
        ordenadas = sorted(rodovias)
    return truncar_texto(SEPARADOR_CODIGOS.join(ordenadas), TAMANHO_MAX_TRECHOS)


def tipo_coincidencia(prefixo_proprio, prefixos_parceiros):
    """Classifica a natureza da sobreposicao quanto as BRs envolvidas.

    Parametros:
        prefixo_proprio: BR do proprio trecho (tres digitos) ou None.
        prefixos_parceiros: iteravel com as BRs dos trechos sobrepostos.

    Retorna:
        "ENTRE_BRS"     - todos os parceiros sao de outra BR;
        "MESMA_BR"      - todos os parceiros sao da mesma BR do trecho;
        "AMBOS"         - ha parceiros dos dois tipos;
        "INDETERMINADO" - a BR propria nao e identificavel;
        None            - nenhum parceiro tem BR identificavel.

    Hipotese metodologica:
        Dois codigos DISTINTOS da MESMA BR sobrepostos sao geometria duplicada
        no SNV, e nao coincidencia entre rodovias. Distinguir os casos impede
        que a duplicacao seja contabilizada como eixo compartilhado, sem
        escondê-la: a anomalia continua na saida, nomeada.

        Sem a BR propria a comparacao nao pode ser feita, e o caso e nomeado em
        vez de ser silenciosamente classificado como ENTRE_BRS - o que
        afirmaria, sem prova, que as BRs sao diferentes.
    """
    parceiras = {prefixo for prefixo in prefixos_parceiros if prefixo is not None}
    if not parceiras:
        return None
    if prefixo_proprio is None:
        return "INDETERMINADO"

    mesma_br = prefixo_proprio in parceiras
    outras_brs = bool(parceiras - {prefixo_proprio})
    if mesma_br and outras_brs:
        return "AMBOS"
    if mesma_br:
        return "MESMA_BR"
    return "ENTRE_BRS"


def classificar_sobreposicao(ext_sobrep, ext_trecho):
    """Calcula a fracao coberta do trecho e classifica a sobreposicao.

    Parametros:
        ext_sobrep: extensao do trecho coberta por algum parceiro.
        ext_trecho: extensao total do proprio trecho, na mesma unidade.

    Retorna:
        tupla (percentual, tipo):
            percentual: ext_sobrep / ext_trecho, ou None quando indeterminado;
            tipo      : "TOTAL", "PARCIAL" ou "INDETERMINADO".

    Hipoteses metodologicas:
        Um trecho de extensao nula, negativa ou nao finita nao tem percentual
        de cobertura definido. Devolver 0 ou 1 nesse caso inventaria um valor, e
        o rotulo INDETERMINADO mantem a lacuna visivel no proprio dado.

        O limiar e inclusivo: cobertura exatamente igual a
        LIMIAR_SOBREPOSICAO_TOTAL ja e TOTAL. A folga existe para absorver
        arredondamento de coordenada, nao para admitir sobreposicao realmente
        parcial, e por isso e pequena.
    """
    if ext_trecho is None or not math.isfinite(ext_trecho) or ext_trecho <= 0:
        return None, "INDETERMINADO"
    if ext_sobrep is None or not math.isfinite(ext_sobrep) or ext_sobrep < 0:
        return None, "INDETERMINADO"

    percentual = ext_sobrep / ext_trecho
    tipo = "TOTAL" if percentual >= LIMIAR_SOBREPOSICAO_TOTAL else "PARCIAL"
    return percentual, tipo


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


def partes_lineares(geometria):
    """Percorre recursivamente uma geometria e devolve apenas partes lineares.

    Parametros:
        geometria: QgsGeometry, possivelmente uma GeometryCollection.

    Retorna:
        gerador de QgsGeometry lineares.

    Hipotese metodologica:
        A interseccao de dois trechos pode devolver uma GeometryCollection com,
        ao mesmo tempo, uma linha comum e um ponto de cruzamento. Percorrer a
        colecao e avaliar cada parte isoladamente impede que o ponto - que
        representa um viaduto ou entroncamento, nao um eixo compartilhado -
        seja contado como prova.

        Extraida de codigos_sobrepostos (associacao_oae_snv.py), onde e uma
        funcao aninhada, para o nivel de modulo.
    """
    if QgsWkbTypes.geometryType(geometria.wkbType()) == QgsWkbTypes.LineGeometry:
        yield geometria
    elif QgsWkbTypes.flatType(geometria.wkbType()) == QgsWkbTypes.GeometryCollection:
        for parte in geometria.asGeometryCollection():
            yield from partes_lineares(parte)


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
    CAMPO_VL_CODIGO,
    CAMPO_SUPERFICIE,
    CAMPO_JURISDICAO,
    CAMPO_UF_SNV,
}
faltantes_snv = sorted(obrigatorios_snv - campos_snv)
if faltantes_snv:
    raise Exception(f"Campos ausentes em {NOME_CAMADA_SNV}: {', '.join(faltantes_snv)}")
# Campos homonimos na saida seriam indistinguiveis na tabela de atributos e o
# valor calculado poderia ser lido como se fosse dado de origem.
campos_novos = {
    CAMPO_TRECHOS_COINC,
    CAMPO_QTD_PARCEIROS,
    CAMPO_EXT_SOBREP_KM,
    CAMPO_PERC_SOBREP,
    CAMPO_TIPO_SOBREP,
    CAMPO_TIPO_COINC,
}
conflitantes = sorted(campos_novos & campos_snv)
if conflitantes:
    raise Exception(
        f'A camada "{NOME_CAMADA_SNV}" ja possui os campos: {", ".join(conflitantes)}.'
    )

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
        "Medicao elipsoidal indisponivel: as extensoes sairiam nas unidades do SRC."
    )


def comprimento_km(geometria):
    """Mede uma geometria linear em quilometros sobre o elipsoide.

    Parametros:
        geometria: QgsGeometry linear.

    Retorna:
        float em km, ou None quando a medicao nao resulta num numero finito.

    Hipotese metodologica:
        Uma medicao nao finita e devolvida como ausencia em vez de zero: zero
        seria indistinguivel de um trecho realmente sem extensao e entraria nos
        somatorios como se fosse medida valida.
    """
    if geometria is None or geometria.isNull() or geometria.isEmpty():
        return None
    medida = medidor.convertLengthMeasurement(
        medidor.measureLength(geometria), QgsUnitTypes.DistanceKilometers
    )
    return medida if math.isfinite(medida) else None


# -----------------------------------------------------------------------------
# 3) UNIVERSO FILTRADO E INDICE ESPACIAL
# -----------------------------------------------------------------------------
contagem = {
    "TOTAL": 0,
    "GEOMETRIA_INVALIDA": 0,
    "ANALISADOS": 0,
    "COM_SOBREPOSICAO": 0,
    "SEM_BR_PARCEIRA": 0,
}
contagem.update({motivo: 0 for motivo in MOTIVOS_EXCLUSAO})
contagem.update({f"COINC_{tipo}": 0 for tipo in TIPOS_COINC})
contagem.update({f"SOBREP_{tipo}": 0 for tipo in TIPOS_SOBREP})

feicoes = {}
indice = QgsSpatialIndex()

for trecho in camada_snv.getFeatures():
    contagem["TOTAL"] += 1

    # O filtro vem primeiro: trecho planejado ou nao federal esta fora do
    # escopo, e nao pode nem entrar na saida nem provar a coincidencia alheia.
    motivo = motivo_exclusao(trecho[CAMPO_SUPERFICIE], trecho[CAMPO_JURISDICAO])
    if motivo is not None:
        contagem[motivo] += 1
        continue

    geometria = trecho.geometry()
    if geometria is None or geometria.isNull() or geometria.isEmpty():
        contagem["GEOMETRIA_INVALIDA"] += 1
        continue

    contagem["ANALISADOS"] += 1
    feicoes[trecho.id()] = trecho
    indice.addFeature(trecho)

print(f'Camada de origem : {NOME_CAMADA_SNV} ({contagem["TOTAL"]} trechos lidos)')
print(f'Trechos analisados apos o filtro: {contagem["ANALISADOS"]}')


# -----------------------------------------------------------------------------
# 4) DETECCAO DOS PARES SOBREPOSTOS
# -----------------------------------------------------------------------------
# Cada par e avaliado UMA vez (apenas contra candidatos de id maior) e o
# resultado e lancado nas duas feicoes. Alem de dividir o custo pela metade,
# isso torna o resultado independente da ordem de leitura.
parceiros = {}
sobreposicoes = {}
pares_sobrepostos = 0

ordenados = sorted(feicoes)
for posicao, fid_a in enumerate(ordenados, start=1):
    if posicao % INTERVALO_PROGRESSO == 0:
        print(f"  ... {posicao}/{len(ordenados)} trechos varridos")

    geometria_a = feicoes[fid_a].geometry()
    for fid_b in indice.intersects(geometria_a.boundingBox()):
        if fid_b <= fid_a:
            continue
        geometria_b = feicoes[fid_b].geometry()
        # Predicado antes da construcao: a maioria dos candidatos do indice
        # apenas compartilha retangulo envolvente e nao chega a se tocar.
        if not geometria_a.intersects(geometria_b):
            continue

        comum = geometria_a.intersection(geometria_b)
        if comum.isNull() or comum.isEmpty():
            continue

        # Somente porcao LINEAR de comprimento positivo prova coincidencia. Um
        # cruzamento produz um ponto, nao um trecho comum.
        comuns = []
        for parte in partes_lineares(comum):
            comprimento = parte.length()
            if math.isfinite(comprimento) and comprimento > 0:
                comuns.append(parte)
        if not comuns:
            continue

        pares_sobrepostos += 1
        for fid, parceiro in ((fid_a, fid_b), (fid_b, fid_a)):
            parceiros.setdefault(fid, set()).add(parceiro)
            sobreposicoes.setdefault(fid, []).extend(comuns)

print(f"Pares sobrepostos detectados: {pares_sobrepostos}")


# -----------------------------------------------------------------------------
# 5) CAMADA DE DETALHE
# -----------------------------------------------------------------------------
# A saida permanece no SRC ORIGINAL da SNV: a prova e de interseccao exata, e
# reprojetar desloca vertices, o que tanto destruiria coincidencias reais quanto
# fabricaria inexistentes. As medicoes sao elipsoidais e dispensam o plano.
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
    [
        QgsField(CAMPO_TRECHOS_COINC, QVariant.String, len=TAMANHO_MAX_TRECHOS),
        QgsField(CAMPO_QTD_PARCEIROS, QVariant.Int),
        QgsField(CAMPO_EXT_SOBREP_KM, QVariant.Double, len=20, prec=3),
        QgsField(CAMPO_PERC_SOBREP, QVariant.Double, len=20, prec=6),
        QgsField(CAMPO_TIPO_SOBREP, QVariant.String, len=20),
        QgsField(CAMPO_TIPO_COINC, QVariant.String, len=20),
    ]
)
saida.updateFields()

indices_novos = {nome: saida.fields().indexOf(nome) for nome in campos_novos}
if any(indice_campo < 0 for indice_campo in indices_novos.values()):
    raise RuntimeError("Estrutura da camada de saida divergente da esperada.")

# Chave (sg_uf, Trechos-coinc): a contagem por grupo nasce da MESMA passagem que
# gera a camada de detalhe, e nao de uma releitura posterior, de modo que
# Qtd_trechos nunca possa divergir do que foi efetivamente gravado.
grupos = Counter()
novas_feicoes = []

for fid in ordenados:
    if fid not in parceiros:
        continue

    trecho = feicoes[fid]
    contagem["COM_SOBREPOSICAO"] += 1

    prefixo_proprio = prefixo_codigo(trecho[CAMPO_VL_CODIGO])
    prefixos_parceiros = {
        prefixo_codigo(feicoes[parceiro][CAMPO_VL_CODIGO])
        for parceiro in parceiros[fid]
    }

    texto = texto_rodovias(prefixo_proprio, prefixos_parceiros)
    tipo_coinc = tipo_coincidencia(prefixo_proprio, prefixos_parceiros)
    if texto is None:
        contagem["SEM_BR_PARCEIRA"] += 1
    if tipo_coinc is not None:
        contagem[f"COINC_{tipo_coinc}"] += 1

    # Uniao, e nao soma: dois parceiros podem cobrir o mesmo pedaco de eixo.
    ext_sobrep_km = comprimento_km(QgsGeometry.unaryUnion(sobreposicoes[fid]))
    perc_sobrep, tipo_sobrep = classificar_sobreposicao(
        ext_sobrep_km, comprimento_km(trecho.geometry())
    )
    contagem[f"SOBREP_{tipo_sobrep}"] += 1

    nova = QgsFeature(saida.fields())
    nova.setGeometry(QgsGeometry(trecho.geometry()))
    nova.setAttributes(trecho.attributes() + [None] * len(campos_novos))
    nova.setAttribute(indices_novos[CAMPO_TRECHOS_COINC], texto)
    nova.setAttribute(indices_novos[CAMPO_QTD_PARCEIROS], len(parceiros[fid]))
    nova.setAttribute(indices_novos[CAMPO_EXT_SOBREP_KM], ext_sobrep_km)
    nova.setAttribute(indices_novos[CAMPO_PERC_SOBREP], perc_sobrep)
    nova.setAttribute(indices_novos[CAMPO_TIPO_SOBREP], tipo_sobrep)
    nova.setAttribute(indices_novos[CAMPO_TIPO_COINC], tipo_coinc)
    novas_feicoes.append(nova)

    grupos[(texto_bruto(trecho[CAMPO_UF_SNV]), texto)] += 1

# addFeatures devolve (bool, lista); testar a tupla inteira daria sempre
# verdadeiro e engoliria a falha de gravacao.
if novas_feicoes and not provedor_saida.addFeatures(novas_feicoes)[0]:
    raise RuntimeError("Falha ao gravar as feicoes na camada de saida.")
saida.updateExtents()

if contagem["COM_SOBREPOSICAO"] != len(novas_feicoes):
    raise RuntimeError("Contagem de sobrepostos divergente das feicoes gravadas.")
if saida.featureCount() != len(novas_feicoes):
    raise RuntimeError("A camada de saida nao recebeu todas as feicoes selecionadas.")


# -----------------------------------------------------------------------------
# 6) DISSOLVE POR UF E COMBINACAO DE BRs
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

    extensao_km = comprimento_km(grupo.geometry())
    if extensao_km is not None:
        extensao_total_km += extensao_km

    nova = QgsFeature(dissolvido.fields())
    nova.setGeometry(QgsGeometry(grupo.geometry()))
    nova.setAttributes([chave[0], chave[1], grupos[chave], extensao_km])
    feicoes_dissolvidas.append(nova)
    resumo_grupos.append((rotulo_grupo(*chave), grupos[chave], extensao_km or 0.0))

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
# 7) RESUMO E CONFERENCIA
# -----------------------------------------------------------------------------
print(f'Excluidos pelo filtro {CAMPO_SUPERFICIE} != "{SUPERFICIE_EXCLUIDA}"'
      f' e {CAMPO_JURISDICAO} = "{JURISDICAO_EXIGIDA}":')
for motivo in MOTIVOS_EXCLUSAO:
    print(f"  {motivo.ljust(22)}: {contagem[motivo]}")
print(f'  GEOMETRIA_INVALIDA    : {contagem["GEOMETRIA_INVALIDA"]}')

print(f'Camada criada    : {NOME_CAMADA_SAIDA} ({contagem["COM_SOBREPOSICAO"]} trechos)')
print("  natureza da coincidencia:")
for tipo in TIPOS_COINC:
    print(f'    {tipo.ljust(15)}: {contagem[f"COINC_{tipo}"]}')
print("  extensao da sobreposicao:")
for tipo in TIPOS_SOBREP:
    print(f'    {tipo.ljust(15)}: {contagem[f"SOBREP_{tipo}"]}')
print(f'  {CAMPO_TRECHOS_COINC} nulo    : {contagem["SEM_BR_PARCEIRA"]}')

print(f"Camada criada    : {NOME_CAMADA_DISSOLVIDA} ({len(feicoes_dissolvidas)} grupos,"
      f" {extensao_total_km:.3f} km)")

if resumo_grupos:
    print(f"Grupos de maior extensao (ate {LIMITE_RESUMO_PREFIXOS}):")
    # Ordena por extensao decrescente e, no empate, pelo rotulo: a listagem e
    # apenas de conferencia e precisa ser reproduzivel entre execucoes.
    ordenados_resumo = sorted(resumo_grupos, key=lambda item: (-item[2], item[0]))
    for rotulo, quantidade, extensao_km in ordenados_resumo[:LIMITE_RESUMO_PREFIXOS]:
        print(f"  {rotulo}: {quantidade} trechos, {extensao_km:.3f} km")

print("Confronte esta saida com a da metodologia 1 (trechos_coincidentes.py):")
print("  a divergencia entre as duas e o achado de interesse, nao um defeito.")
