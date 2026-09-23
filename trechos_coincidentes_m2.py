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
#   ser executado no Console Python do QGIS: a secao 7 usa o framework
#   Processing.
#
#
# 3. DADOS DE SAIDA
# -----------------------------------------------------------------------------
#   Tres camadas em memoria, no SRC da SNV:
#
#   a) NOME_CAMADA_SAIDA ("Trechos_Coincidentes_M2") - detalhe, trecho a trecho:
#       - TODOS os campos originais da SNV;
#       - CAMPO_TRECHOS_COINC ("Trechos-coinc") : BRs que dividem o eixo, a
#         propria primeiro e as parceiras em ordem numerica;
#       - CAMPO_BRS_EIXO      ("BRs_eixo")      : as mesmas BRs em forma
#         CANONICA - distintas, em ordem numerica crescente. E a chave do
#         dissolve: Trechos-coinc depende de qual trecho o gerou e faria o
#         mesmo eixo virar dois grupos, um por BR;
#       - CAMPO_QTD_PARCEIROS ("Qtd_parceiros") : trechos distintos sobrepostos;
#       - CAMPO_COD_PARCEIROS ("Cod_parceiros") : quais trechos, e com quantos
#         metros de eixo comum cada um, em ordem decrescente de sobreposicao;
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
#      um registro por UF e combinacao de BRs, com sg_uf, BRs_eixo,
#      CAMPO_QTD_TRECHOS ("Qtd_trechos") e CAMPO_EXT_KM ("Ext_km").
#
#   c) NOME_CAMADA_SOBREPOSICOES ("Trechos_Coincidentes_M2_sobreposicoes") - a
#      geometria da porcao de eixo efetivamente compartilhada por cada par, com
#      CAMPO_CODIGO_A / CAMPO_CODIGO_B e CAMPO_EXT_SOBREP_M ("Ext_sobrep_m").
#      E a camada de prova: ligada sobre a SNV, mostra se cada deteccao e um
#      eixo comum ou apenas um ponto de juncao.
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
#       LINEARES contam. Um cruzamento (viaduto, entroncamento) produz um ponto,
#       nao um trecho comum, e nao prova coincidencia alguma.
#
#       A porcao comum e medida em METROS, sobre o elipsoide, e so vale como
#       prova a partir de TOLERANCIA_SOBREPOSICAO_M. Os dois pontos importam:
#
#       a) A unidade. Medir com QgsGeometry.length() devolve o comprimento
#          PLANAR nas unidades do SRC - graus, no SRC geografico em que o SNV e
#          publicado. Um teste de "comprimento > 0" em graus aceita o residuo de
#          1e-13 grau que o GEOS deixa ao nodear duas linhas que apenas se tocam
#          ou se cruzam: em vez de um POINT limpo, a interseccao sai como
#          LINESTRING degenerado. Era isso que fazia cada juncao entre trechos
#          vizinhos e cada entroncamento da malha virar falso positivo.
#
#       b) O limiar. Mesmo em metros, o dado traz lascas de poucos centimetros
#          nas juncoes, vindas da digitalizacao. Um comprimento minimo NAO e o
#          buffer que a metodologia recusa: buffer FABRICA coincidencia entre
#          linhas que nao se tocam; o comprimento minimo apenas DESCARTA
#          evidencia fraca demais para se distinguir de ruido numerico. Continua
#          valendo a recusa a buffer, snap e deslocamento de vertice.
#
#       Fica a limitacao correspondente: dois eixos fisicamente coincidentes
#       digitalizados com centimetros de diferenca NAO sao detectados aqui, e
#       tampouco um multiplex genuino mais curto que a tolerancia. E exatamente
#       uma das divergencias que o confronto com a metodologia 1 serve para
#       revelar. O histograma impresso no resumo mostra a distribuicao das
#       sobreposicoes encontradas e permite reavaliar o limiar com evidencia.
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

# Importado aqui, e nao na secao 7 que o usa, para que a ausencia do framework
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
NOME_CAMADA_SOBREPOSICOES = "Trechos_Coincidentes_M2_sobreposicoes"

CAMPO_VL_CODIGO = "vl_codigo"
CAMPO_SUPERFICIE = "ds_superfi"
CAMPO_JURISDICAO = "ds_jurisdi"
CAMPO_UF_SNV = "sg_uf"

CAMPO_TRECHOS_COINC = "Trechos-coinc"
CAMPO_BRS_EIXO = "BRs_eixo"
CAMPO_QTD_PARCEIROS = "Qtd_parceiros"
CAMPO_COD_PARCEIROS = "Cod_parceiros"
CAMPO_EXT_SOBREP_KM = "Ext_sobrep_km"
CAMPO_PERC_SOBREP = "Perc_sobrep"
CAMPO_TIPO_SOBREP = "Tipo_sobrep"
CAMPO_TIPO_COINC = "Tipo_coinc"

CAMPO_QTD_TRECHOS = "Qtd_trechos"
CAMPO_EXT_KM = "Ext_km"

CAMPO_CODIGO_A = "Codigo_a"
CAMPO_CODIGO_B = "Codigo_b"
CAMPO_EXT_SOBREP_M = "Ext_sobrep_m"

# Filtro equivalente a ds_superfi != 'PLA' AND ds_jurisdi = 'Federal'.
SUPERFICIE_EXCLUIDA = "PLA"
JURISDICAO_EXIGIDA = "Federal"

# Separador das BRs em Trechos-coinc, o mesmo do ds_coinc lido na metodologia 1.
SEPARADOR_CODIGOS = ";"

# Fracao da extensao do trecho a partir da qual a sobreposicao e TOTAL.
LIMIAR_SOBREPOSICAO_TOTAL = 0.999

# Comprimento minimo, em METROS, da porcao comum que prova coincidencia. Ver a
# secao 4.2 do cabecalho: abaixo disso a evidencia nao se distingue do residuo
# numerico das juncoes e dos entroncamentos.
TOLERANCIA_SOBREPOSICAO_M = 10.0

# Limites, em metros, das faixas do histograma de diagnostico.
FAIXAS_SOBREPOSICAO = (1.0, 10.0, 100.0, 1000.0)

# Como um parceiro sem vl_codigo identificavel e nomeado na saida.
ROTULO_SEM_CODIGO = "(sem codigo)"

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
        esconde-la: a anomalia continua na saida, nomeada.

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


def em_km(metros):
    """Converte uma medida de metros para quilometros preservando a ausencia.

    Parametros:
        metros: float em metros, ou None.

    Retorna:
        float em km, ou None quando nao havia medida.

    Hipotese metodologica:
        A conversao existe como funcao para que so exista UMA primitiva de
        medida no script, em metros. Ter duas medidas em unidades diferentes
        circulando pelo codigo foi a origem do erro corrigido na secao 4.2 do
        cabecalho.
    """
    return None if metros is None else metros / 1000.0


def sobreposicao_relevante(ext_m):
    """Decide se uma porcao comum e longa o bastante para provar coincidencia.

    Parametros:
        ext_m: extensao da porcao comum, em METROS, ou None.

    Retorna:
        True somente quando ext_m e finito e alcanca
        TOLERANCIA_SOBREPOSICAO_M.

    Hipoteses metodologicas:
        O criterio e uma funcao nomeada, e nao um teste solto no meio do laco de
        varredura, porque ele E a metodologia: a versao anterior escondia ali um
        "comprimento > 0" medido em graus, que aceitava o residuo numerico de
        cada juncao da malha como prova de eixo compartilhado.

        O limiar e inclusivo. Nao se trata de tolerancia que fabrica
        coincidencia - isso seria buffer, e continua recusado - mas de descartar
        evidencia fraca demais para se distinguir de ruido.
    """
    if ext_m is None or not math.isfinite(ext_m):
        return False
    return ext_m >= TOLERANCIA_SOBREPOSICAO_M


def texto_parceiros(pares):
    """Lista os trechos sobrepostos com a extensao comum de cada um.

    Parametros:
        pares: iteravel de (vl_codigo do parceiro, extensao comum em metros).

    Retorna:
        str no formato "222BCE0240(12043.7m);135BMA0170(14.1m)", ou None quando
        nao houver parceiro algum.

    Hipoteses metodologicas:
        A ordem e DECRESCENTE por extensao: havendo truncamento, o que sobrevive
        no campo e a evidencia mais forte. O empate e resolvido pelo codigo, de
        modo que o texto seja reproduzivel entre execucoes.

        Sem este campo a camada afirmava "coincidente" sem dizer com quem, e
        conferir um caso exigia inspecao visual no QGIS - foi o que permitiu que
        um erro de unidade passasse despercebido na primeira rodada. Um parceiro
        sem medida valida e nomeado como tal em vez de receber zero, que o
        colocaria junto dos casos legitimamente curtos.
    """
    itens = []
    for codigo, ext_m in pares:
        rotulo = codigo_valido(codigo) or ROTULO_SEM_CODIGO
        medida = ext_m if ext_m is not None and math.isfinite(ext_m) else None
        itens.append((medida, rotulo))
    if not itens:
        return None

    # Os sem medida vao para o fim; os demais em extensao decrescente.
    ordenados = sorted(itens, key=lambda item: (item[0] is None, -(item[0] or 0.0), item[1]))
    textos = [
        f"{rotulo}({medida:.1f}m)" if medida is not None else f"{rotulo}(nao medida)"
        for medida, rotulo in ordenados
    ]
    return truncar_texto(SEPARADOR_CODIGOS.join(textos), TAMANHO_MAX_TRECHOS)


def faixa_sobreposicao(ext_m):
    """Classifica uma extensao de sobreposicao numa faixa do histograma.

    Parametros:
        ext_m: extensao da porcao comum, em metros, ou None.

    Retorna:
        str com o rotulo da faixa (ex.: "< 1 m", "1-10 m", ">= 1000 m"), ou
        "nao medida".

    Hipotese metodologica:
        Os rotulos sao derivados de FAIXAS_SOBREPOSICAO, e nao escritos a mao,
        para que mudar os limites nao deixe o histograma mentindo sobre o que
        esta contando. O histograma existe para que o limiar da tolerancia possa
        ser reavaliado com a distribuicao real do dado em vez de por palpite.
    """
    if ext_m is None or not math.isfinite(ext_m):
        return "nao medida"
    if ext_m < FAIXAS_SOBREPOSICAO[0]:
        return f"< {FAIXAS_SOBREPOSICAO[0]:g} m"
    for inferior, superior in zip(FAIXAS_SOBREPOSICAO, FAIXAS_SOBREPOSICAO[1:]):
        if ext_m < superior:
            return f"{inferior:g}-{superior:g} m"
    return f">= {FAIXAS_SOBREPOSICAO[-1]:g} m"


def brs_do_eixo(texto_trechos):
    """Reduz o texto de BRs de um trecho a chave canonica do eixo.

    Parametros:
        texto_trechos: conteudo de CAMPO_TRECHOS_COINC, ou None.

    Retorna:
        str com as BRs distintas em ordem numerica crescente, unidas por ";",
        ou None quando nao houver BR alguma no texto.

    Hipoteses metodologicas:
        CAMPO_TRECHOS_COINC nao serve como chave de agrupamento porque seu texto
        depende de qual trecho o gerou: o mesmo eixo compartilhado pela BR-174 e
        pela BR-210 aparece como "210;174" no trecho de uma e "174;210" no da
        outra, e o dissolve acaba gravando duas feicoes para um eixo so. A ordem
        canonica elimina a duplicacao sem alterar o campo de origem, que segue
        util trecho a trecho.

        A chave e derivada DO TEXTO, e nao recalculada em paralelo a partir dos
        prefixos, para que BRs_eixo nomeie por construcao exatamente o mesmo
        conjunto de BRs que CAMPO_TRECHOS_COINC. Duas derivacoes independentes
        poderiam divergir sem que nada acusasse.

        So sao aceitos tokens de exatamente tres digitos. Isso descarta o
        marcador de truncamento, que de outro modo entraria na chave de um
        trecho com BRs demais para o campo e criaria um grupo espurio.
    """
    if texto_trechos is None:
        return None
    rodovias = set()
    for parte in str(texto_trechos).split(SEPARADOR_CODIGOS):
        token = codigo_valido(parte)
        if token is not None and len(token) == 3 and token.isdigit():
            rodovias.add(token)
    if not rodovias:
        return None
    return truncar_texto(SEPARADOR_CODIGOS.join(sorted(rodovias)), TAMANHO_MAX_TRECHOS)


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
    CAMPO_BRS_EIXO,
    CAMPO_QTD_PARCEIROS,
    CAMPO_COD_PARCEIROS,
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


def comprimento_m(geometria):
    """Mede uma geometria linear em METROS sobre o elipsoide.

    Parametros:
        geometria: QgsGeometry linear.

    Retorna:
        float em metros, ou None quando a medicao nao resulta num numero finito.

    Hipoteses metodologicas:
        E a UNICA primitiva de medida do script, e devolve metros. Onde se quer
        quilometros, converte-se com em_km no ponto de uso. Ter duas primitivas
        em unidades diferentes foi o que permitiu que o criterio de deteccao
        acabasse comparando graus com zero (ver secao 4.2 do cabecalho).

        Uma medicao nao finita e devolvida como ausencia em vez de zero: zero
        seria indistinguivel de um trecho realmente sem extensao e entraria nos
        somatorios como se fosse medida valida.
    """
    if geometria is None or geometria.isNull() or geometria.isEmpty():
        return None
    medida = medidor.convertLengthMeasurement(
        medidor.measureLength(geometria), QgsUnitTypes.DistanceMeters
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
#
# parceiros[fid] = {fid_parceiro: extensao comum em metros}: a extensao vem da
# MESMA medicao que aceitou o par, e nao de um recalculo posterior.
parceiros = {}
sobreposicoes = {}
pares_aceitos = []
# O histograma conta TODOS os pares com porcao linear, aceitos ou nao: e o que
# permite confirmar que o limiar cortou ruido e nao coincidencia legitima.
histograma = Counter()
pares_descartados = 0

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

        # Somente porcao LINEAR prova coincidencia: um cruzamento produz um
        # ponto, nao um trecho comum.
        lineares = list(partes_lineares(comum))
        if not lineares:
            continue

        # A medicao e em METROS, sobre o elipsoide. Usar QgsGeometry.length()
        # daria GRAUS no SRC geografico do SNV, e "> 0" em graus aceita o
        # residuo de 1e-13 que o GEOS deixa ao nodear duas linhas que apenas se
        # tocam - era o que fazia cada juncao e cada entroncamento da malha
        # virar falso positivo. Ver a secao 4.2 do cabecalho.
        comum_linear = QgsGeometry.unaryUnion(lineares)
        ext_m = comprimento_m(comum_linear)

        histograma[faixa_sobreposicao(ext_m)] += 1
        if not sobreposicao_relevante(ext_m):
            pares_descartados += 1
            continue

        pares_aceitos.append((fid_a, fid_b, ext_m, comum_linear))
        for fid, parceiro in ((fid_a, fid_b), (fid_b, fid_a)):
            parceiros.setdefault(fid, {})[parceiro] = ext_m
            sobreposicoes.setdefault(fid, []).append(comum_linear)

print(f"Pares com porcao linear em comum : {sum(histograma.values())}")
print(f"  aceitos (>= {TOLERANCIA_SOBREPOSICAO_M:g} m) : {len(pares_aceitos)}")
print(f"  descartados pela tolerancia    : {pares_descartados}")


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
        QgsField(CAMPO_BRS_EIXO, QVariant.String, len=TAMANHO_MAX_TRECHOS),
        QgsField(CAMPO_QTD_PARCEIROS, QVariant.Int),
        QgsField(CAMPO_COD_PARCEIROS, QVariant.String, len=TAMANHO_MAX_TRECHOS),
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
    brs_eixo = brs_do_eixo(texto)
    tipo_coinc = tipo_coincidencia(prefixo_proprio, prefixos_parceiros)
    if texto is None:
        contagem["SEM_BR_PARCEIRA"] += 1
    if tipo_coinc is not None:
        contagem[f"COINC_{tipo_coinc}"] += 1

    # Diz COM QUEM e com quantos metros, para que cada deteccao possa ser
    # conferida na tabela de atributos sem inspecao visual.
    cod_parceiros = texto_parceiros(
        (feicoes[parceiro][CAMPO_VL_CODIGO], ext_par)
        for parceiro, ext_par in parceiros[fid].items()
    )

    # Uniao, e nao soma: dois parceiros podem cobrir o mesmo pedaco de eixo.
    ext_sobrep_m = comprimento_m(QgsGeometry.unaryUnion(sobreposicoes[fid]))
    perc_sobrep, tipo_sobrep = classificar_sobreposicao(
        ext_sobrep_m, comprimento_m(trecho.geometry())
    )
    contagem[f"SOBREP_{tipo_sobrep}"] += 1

    nova = QgsFeature(saida.fields())
    nova.setGeometry(QgsGeometry(trecho.geometry()))
    nova.setAttributes(trecho.attributes() + [None] * len(campos_novos))
    nova.setAttribute(indices_novos[CAMPO_TRECHOS_COINC], texto)
    nova.setAttribute(indices_novos[CAMPO_BRS_EIXO], brs_eixo)
    nova.setAttribute(indices_novos[CAMPO_QTD_PARCEIROS], len(parceiros[fid]))
    nova.setAttribute(indices_novos[CAMPO_COD_PARCEIROS], cod_parceiros)
    nova.setAttribute(indices_novos[CAMPO_EXT_SOBREP_KM], em_km(ext_sobrep_m))
    nova.setAttribute(indices_novos[CAMPO_PERC_SOBREP], perc_sobrep)
    nova.setAttribute(indices_novos[CAMPO_TIPO_SOBREP], tipo_sobrep)
    nova.setAttribute(indices_novos[CAMPO_TIPO_COINC], tipo_coinc)
    novas_feicoes.append(nova)

    # A chave do grupo e BRs_eixo, e nao Trechos-coinc: este ultimo traz a BR
    # propria na frente e faria o mesmo eixo virar dois grupos, um por BR.
    grupos[(texto_bruto(trecho[CAMPO_UF_SNV]), brs_eixo)] += 1

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
# 6) CAMADA DAS PORCOES SOBREPOSTAS
# -----------------------------------------------------------------------------
# A camada de prova: contem a geometria do pedaco de eixo que cada par
# efetivamente compartilha. Ligada sobre a SNV, mostra de imediato se uma
# deteccao e um eixo comum ou apenas um ponto de juncao - confirmacao que antes
# dependia de inspecionar a malha a olho, trecho por trecho.
sobrep_camada = QgsVectorLayer(
    f"MultiLineString?crs={camada_snv.crs().authid()}",
    NOME_CAMADA_SOBREPOSICOES,
    "memory",
)
if not sobrep_camada.isValid():
    raise Exception("Falha ao criar a camada de sobreposicoes em memoria.")

provedor_sobrep = sobrep_camada.dataProvider()
provedor_sobrep.addAttributes(
    [
        QgsField(CAMPO_CODIGO_A, QVariant.String, len=30),
        QgsField(CAMPO_CODIGO_B, QVariant.String, len=30),
        QgsField(CAMPO_EXT_SOBREP_M, QVariant.Double, len=20, prec=3),
    ]
)
sobrep_camada.updateFields()

feicoes_sobrep = []
for fid_a, fid_b, ext_m, geometria_comum in pares_aceitos:
    # Os dois codigos saem em ordem alfabetica: o par fica identificavel na
    # tabela independentemente de qual feicao foi lida primeiro.
    codigos = sorted(
        codigo_valido(feicoes[fid][CAMPO_VL_CODIGO]) or ROTULO_SEM_CODIGO
        for fid in (fid_a, fid_b)
    )

    geometria = QgsGeometry(geometria_comum)
    # A uniao das partes de um par pode ser simples ou multipart; a camada e
    # declarada multipart, e converter aqui evita recusa silenciosa na gravacao.
    geometria.convertToMultiType()

    nova = QgsFeature(sobrep_camada.fields())
    nova.setGeometry(geometria)
    nova.setAttributes([codigos[0], codigos[1], ext_m])
    feicoes_sobrep.append(nova)

if feicoes_sobrep and not provedor_sobrep.addFeatures(feicoes_sobrep)[0]:
    raise RuntimeError("Falha ao gravar as feicoes na camada de sobreposicoes.")
sobrep_camada.updateExtents()

if sobrep_camada.featureCount() != len(pares_aceitos):
    raise RuntimeError("A camada de sobreposicoes nao recebeu um registro por par.")


# -----------------------------------------------------------------------------
# 7) DISSOLVE POR UF E COMBINACAO DE BRs
# -----------------------------------------------------------------------------
# native:dissolve faz UNIAO das geometrias do grupo. Simplesmente coleta-las em
# multipart manteria o eixo compartilhado repetido uma vez por BR, e Ext_km
# sairia multiplicado.
dissolvido_bruto = processing.run(
    "native:dissolve",
    {
        "INPUT": saida,
        "FIELD": [CAMPO_UF_SNV, CAMPO_BRS_EIXO],
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
        QgsField(CAMPO_BRS_EIXO, QVariant.String, len=TAMANHO_MAX_TRECHOS),
        QgsField(CAMPO_QTD_TRECHOS, QVariant.Int),
        QgsField(CAMPO_EXT_KM, QVariant.Double, len=20, prec=3),
    ]
)
dissolvido.updateFields()

feicoes_dissolvidas = []
extensao_total_km = 0.0
resumo_grupos = []

for grupo in dissolvido_bruto.getFeatures():
    chave = (texto_bruto(grupo[CAMPO_UF_SNV]), texto_bruto(grupo[CAMPO_BRS_EIXO]))
    if chave not in grupos:
        raise RuntimeError(f"Grupo dissolvido sem correspondencia no detalhe: {chave}.")

    extensao_km = em_km(comprimento_m(grupo.geometry()))
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
projeto.addMapLayer(sobrep_camada)
projeto.addMapLayer(dissolvido)


# -----------------------------------------------------------------------------
# 8) RESUMO E CONFERENCIA
# -----------------------------------------------------------------------------
print(f'Excluidos pelo filtro {CAMPO_SUPERFICIE} != "{SUPERFICIE_EXCLUIDA}"'
      f' e {CAMPO_JURISDICAO} = "{JURISDICAO_EXIGIDA}":')
for motivo in MOTIVOS_EXCLUSAO:
    print(f"  {motivo.ljust(22)}: {contagem[motivo]}")
print(f'  GEOMETRIA_INVALIDA    : {contagem["GEOMETRIA_INVALIDA"]}')

print(f"Sobreposicoes encontradas, por extensao"
      f" (tolerancia em uso: {TOLERANCIA_SOBREPOSICAO_M:g} m):")
# Ordem fixa das faixas, as descartadas primeiro: concentracao em "< 1 m" e o
# ruido de juncao esperado, e e o que o limiar existe para cortar.
faixas_impressas = [f"< {FAIXAS_SOBREPOSICAO[0]:g} m"]
faixas_impressas += [
    f"{inferior:g}-{superior:g} m"
    for inferior, superior in zip(FAIXAS_SOBREPOSICAO, FAIXAS_SOBREPOSICAO[1:])
]
faixas_impressas += [f">= {FAIXAS_SOBREPOSICAO[-1]:g} m", "nao medida"]
for faixa in faixas_impressas:
    if histograma[faixa]:
        print(f"    {faixa.ljust(15)}: {histograma[faixa]}")

print(f'Camada criada    : {NOME_CAMADA_SAIDA} ({contagem["COM_SOBREPOSICAO"]} trechos)')
print("  natureza da coincidencia:")
for tipo in TIPOS_COINC:
    print(f'    {tipo.ljust(15)}: {contagem[f"COINC_{tipo}"]}')
print("  extensao da sobreposicao:")
for tipo in TIPOS_SOBREP:
    print(f'    {tipo.ljust(15)}: {contagem[f"SOBREP_{tipo}"]}')
print(f'  {CAMPO_TRECHOS_COINC} nulo    : {contagem["SEM_BR_PARCEIRA"]}')

print(f"Camada criada    : {NOME_CAMADA_SOBREPOSICOES}"
      f" ({len(pares_aceitos)} porcoes compartilhadas)")
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
print(f"Para conferir um caso, leia {CAMPO_COD_PARCEIROS} na camada de detalhe e")
print(f"  ligue {NOME_CAMADA_SOBREPOSICOES} sobre a SNV.")
