# -*- coding: utf-8 -*-
# =============================================================================
# ASSOCIACAO ESPACIAL OAE (SGE) x MALHA RODOVIARIA (SNV) - QGIS / PyQGIS
# =============================================================================
#
# 1. OBJETIVO
# -----------------------------------------------------------------------------
# Para cada Obra de Arte Especial (OAE) da camada SGE, o procedimento executa
# duas etapas encadeadas e independentes entre si quanto aos criterios:
#
#   Etapa 1 - Associacao: identificar UM unico codigo de trecho do SNV
#             (campo "vl_codigo") ao qual a OAE pertence, ou registrar
#             explicitamente a impossibilidade de faze-lo.
#   Etapa 2 - Quilometragem: calcular o quilometro ("km_SNV") da OAE dentro do
#             trecho selecionado, por interpolacao linear entre "vl_km_inic" e
#             "vl_km_fina". O sentido crescente do km e o sentido de
#             digitalizacao da LineString do trecho: o primeiro vertice e o km
#             inicial e o ultimo, o km final.
#
# O procedimento e DETERMINISTICO: o resultado nao depende da ordem de leitura
# das feicoes de nenhuma das camadas (ver secao 6 desta descricao).
#
#
# 2. DADOS DE ENTRADA
# -----------------------------------------------------------------------------
#   Camada OAE (pontual), nome em NOME_CAMADA_OAE:
#       - CAMPO_EXTENSAO ("Extensao (m)") : extensao da OAE em metros. Usada
#         somente para dimensionar o raio de busca, nunca para decidir trecho.
#       - CAMPO_VIA ("Via")               : rodovia declarada da OAE (ex.: BR-116).
#       - CAMPO_RELACAO_SNV ("Relacao_SNV") : usado somente no campo Status.
#
#   Camada SNV (linear), nome em NOME_CAMADA_SNV:
#       - CAMPO_VL_CODIGO   ("vl_codigo")  : codigo do trecho (ex.: 116BMG0450).
#       - CAMPO_VL_KM_INIC  ("vl_km_inic") : km inicial do trecho.
#       - CAMPO_VL_KM_FINA  ("vl_km_fina") : km final do trecho.
#       - CAMPO_ADMIN_SNV   ("ds_tipo_ad") : tipo de administracao do trecho.
#       - CAMPO_JURIS_SNV   ("ds_jurisdi") : jurisdicao do trecho.
#       - geometria: LineString (ou MultiLineString de uma unica parte)
#         digitalizada no sentido crescente do km.
#
#
# 3. DADOS DE SAIDA
# -----------------------------------------------------------------------------
#   Camada em memoria NOME_CAMADA_SAIDA ("SGExSNV"), com todos os campos
#   originais da OAE seguidos dos campos criados, nesta ordem:
#
#       Trecho_SNV  (texto)  codigo vl_codigo selecionado, ou NULL.
#       Administracao (texto) ds_tipo_ad do trecho atribuido, ou NULL.
#       Jurisdicao  (texto)  ds_jurisdi do trecho atribuido, ou NULL.
#                            Ambos sao lidos no momento em que o Trecho_SNV e
#                            atribuido, da feicao do codigo que realiza a menor
#                            distancia da OAE - a mesma usada no calculo do km.
#                            Ficam preenchidos ainda que o km nao possa ser
#                            calculado, e NULL sempre que nao houver trecho.
#                            Sao copia fiel do texto da SNV.
#       km_SNV      (real)   quilometro interpolado, ou NULL.
#       Rodovias_coincidentes (texto) numeros de BR (tres digitos) das rodovias
#                            em SOBREPOSICAO COMPROVADA no local da OAE, isto e,
#                            que ocupam o mesmo espaco parcial ou totalmente.
#                            A rodovia atribuida vem primeiro, as demais em
#                            ordem numerica, separadas por ";" (ex.: "116;101").
#                            NULL quando nao houver coincidencia detectada, o
#                            que torna o levantamento das OAEs sobre rodovias
#                            coincidentes um filtro direto sobre este campo.
#                            Alimentado exclusivamente pela sobreposicao apurada
#                            no criterio TRECHO_COINCIDENTE (e no TRECHO_EMPATE
#                            entre codigos coincidentes) - proximidade no raio
#                            NAO preenche este campo.
#                            Limitacao: espelha o que o criterio detecta. Duas
#                            rodovias coincidentes cujas geometrias no SNV
#                            estejam digitalizadas com alguns centimetros de
#                            diferenca nao satisfazem a equidistancia exigida e
#                            nao aparecem aqui.
#       Status      (texto)  "Validado" ou "A validar", pela formula da planilha
#                            de conferencia (ver status_validacao): Validado se
#                            (Trecho unico e Relacao_SNV = "L") ou (Trecho
#                            coincidente e Qtd_Codigos < 3). Nunca NULL.
#       Criterio    (texto)  um dos seis criterios da secao 5, em texto
#                            legivel (ex.: "Trecho único").
#       Obs_SNV     (texto)  trilha de rastreabilidade em texto legivel:
#                            distancias, margens, codigos concorrentes, causas
#                            de empate, de nao associacao e de km indeterminado,
#                            e avisos de trecho SNV suspeito.
#       Dist_SNV_m  (real)   distancia planimetrica, em metros, entre a OAE e a
#                            geometria do codigo selecionado (evidencia direta
#                            da qualidade da associacao). NULL se nao associada.
#       Raio_SNV    (real)   raio de busca aplicado aquela OAE, em metros.
#       Qtd_Codigos (inteiro) quantidade de vl_codigo DISTINTOS dentro do raio.
#
#   Textos: internamente o script usa codigos estaveis (UNICO_TRECHO,
#   VIA_OAE=116); na gravacao eles viram texto em portugues, com so a primeira
#   letra maiuscula e as siglas preservadas (ver TEXTO_CRITERIO e TEXTO_OBS).
#
#   Alem da camada, o script imprime resumos conferidos por somatorias
#   (associacao, quilometragem, rodovias coincidentes e situacao dos trechos
#   SNV para o calculo do km).
#
#
# 4. PRINCIPAIS PARAMETROS
# -----------------------------------------------------------------------------
#   CRS_METRICA                 : SRC metrico usado em TODAS as medicoes.
#   FATOR_RAIO                  : multiplicador do raio de busca.
#   TOLERANCIA_EMPATE_DISTANCIA_M : tolerancia numerica de equidistancia.
#   TOLERANCIA_CONEXAO_M        : distancia maxima entre extremos de trechos
#                                 vizinhos (so no aviso de sentido suspeito).
#   CASAS_DECIMAIS_KM           : precisao da comparacao do km de emenda entre
#                                 vizinhos (so no aviso de sentido suspeito).
#   DISTANCIA_MAXIMA_ASSOCIACAO_M : limite duro opcional de associacao (None =
#                                 desativado; ver secao "PARAMETROS EM AVALIACAO").
#
#
# 5. FLUXO METODOLOGICO E CRITERIOS DE CLASSIFICACAO
# -----------------------------------------------------------------------------
#   (a) Reprojeta SNV e OAE para CRS_METRICA; indexa a SNV espacialmente.
#   (b) Prepara previamente TODA a SNV (uma vez, antes das OAEs): valida o
#       intervalo de km e reduz a geometria a uma linha de parte unica, na
#       ordem de vertices em que esta gravada.
#   (c) Para cada OAE:
#       c1. raio = max(extensao_da_OAE, mediana_das_extensoes) * FATOR_RAIO.
#           A mediana e o piso do raio; ela protege OAEs com extensao ausente,
#           nula ou negativa, sem inflar o raio das demais.
#       c2. Coleta as feicoes SNV cuja distancia real <= raio e agrupa por
#           vl_codigo distinto. A distancia de um CODIGO e a MENOR distancia
#           entre a OAE e qualquer feicao portadora daquele codigo.
#       c3. Seleciona um unico codigo e classifica (ver abaixo).
#       c4. Se ha codigo, projeta a OAE sobre a geometria escolhida e interpola
#           km = vl_km_inic + fracao * (vl_km_fina - vl_km_inic), sendo fracao
#           a posicao da projecao ao longo da linha (0 no primeiro vertice, 1
#           no ultimo).
#
#   Criterios (mutuamente exclusivos, exaustivos, avaliados NESTA ORDEM):
#
#     SEM_TRECHO         Geometria da OAE invalida/multiponto, OU nenhum
#                        vl_codigo valido dentro do raio de busca.
#     UNICO_TRECHO       Exatamente um vl_codigo distinto dentro do raio, E ele
#                        e compativel com a Via. Ver notas (i) e (ii).
#     TRECHO_DIVERGENTE  Nenhum codigo do raio e compativel com a Via declarada
#                        da OAE, ou a Via esta ausente/nao normalizavel.
#                        Abrange tanto o caso de codigo unico incompativel
#                        quanto o de varios codigos, todos incompativeis.
#     TRECHO_EMPATE      Dois ou mais codigos compativeis com a Via estao a
#                        MESMA DISTANCIA da OAE (dentro da tolerancia), de modo
#                        que o conjunto vencedor nao se reduz a um unico
#                        codigo. Nenhum criterio objetivo os separa e o
#                        desempate por ordem de leitura e proibido: a OAE
#                        permanece sem trecho e sem km. Os codigos empatados e
#                        a distancia comum sao registrados em Obs_SNV.
#     TRECHO_COINCIDENTE O vencedor unico esta na distancia minima entre TODOS
#                        os codigos compativeis E compartilha uma porcao linear
#                        local (de comprimento positivo, situada exatamente na
#                        posicao de menor distancia da OAE) com outro codigo
#                        equidistante. Caso tipico de trechos coincidentes.
#     TRECHO_FRONTEIRA   Vencedor unico por menor distancia entre os codigos
#                        compativeis, sem coincidencia local comprovada.
#                        Caso tipico de OAE proxima ao limite entre trechos.
#
#     Nota (i): a compatibilidade com a Via e PRE-CONDICAO UNIVERSAL. Um unico
#     trecho no raio e apenas o unico candidato disponivel, e nao evidencia de
#     que a OAE pertenca aquela rodovia; se o codigo nao for da Via declarada,
#     a OAE e classificada TRECHO_DIVERGENTE e nao recebe trecho nem km.
#     Consequencia registrada: OAE sem Via preenchida ou nao normalizavel nunca
#     possui codigo compativel e, portanto, nunca e associada.
#
#     Nota (ii): a cardinalidade que distingue UNICO_TRECHO e medida sobre
#     TODOS os codigos do raio, nao apenas sobre os compativeis. Havendo outros
#     codigos no raio, existiu concorrencia espacial a documentar e a decisao
#     pertence ao ramo de concorrencia, ainda que so um codigo seja compativel.
#
#   Sentido do km:
#     Os trechos do SNV sao LineStrings digitalizadas no sentido crescente da
#     rota, de modo que a propria ordem dos vertices define o sentido: nao ha
#     consulta a trechos vizinhos nem a outros atributos.
#     O km_SNV nao e calculado (fica NULL, com a causa em Obs_SNV) quando:
#       - duas feicoes do mesmo codigo empatam em distancia da OAE;
#       - o intervalo de km e invalido (ausente, negativo ou kf <= ki);
#       - a geometria tem duas ou mais partes - juntar partes pode inverter a
#         ordem dos vertices e, com ela, o sentido;
#       - a projecao falha.
#     Principio: o km e coerente com a GEOMETRIA do trecho atribuido. Se a SNV
#     estiver errada, o km acompanha o erro; corrigida a SNV, nova execucao
#     corrige o km.
#     Aviso (so diagnostico, nunca altera o km): cada trecho e comparado com a
#     sequencia de km dos vizinhos da mesma BR. Se o vizinho anterior toca o
#     ultimo vertice, ou o posterior toca o primeiro, Obs_SNV recebe
#     TRECHO_SNV_POSSIVELMENTE_INVERTIDO; se os dois tocam o mesmo extremo,
#     TRECHO_SNV_CONTINUIDADE_CONTRADITORIA. Nesses trechos o km sai espelhado
#     (ki + kf - km correto). Trecho sem vizinhos nao tem com o que ser
#     comparado e, se invertido, passa sem aviso.
#
#
# 6. GARANTIAS DE DETERMINISMO
# -----------------------------------------------------------------------------
#   - Distancias por codigo sao reduzidas por min() sobre o conjunto COMPLETO
#     de feicoes candidatas, nunca pela primeira lida.
#   - Toda decisao exige cardinalidade 1; qualquer empate vira classe propria
#     (TRECHO_EMPATE) ou km indeterminado. Nao ha desempate por ordem.
#   - Ordenacoes existentes (sorted) servem a impressao, nunca a selecao.
#   - Restricao numerica conhecida: a relacao "equidistante dentro da
#     tolerancia" nao e transitiva. Com TOLERANCIA_EMPATE_DISTANCIA_M = 1e-8 m
#     o efeito e desprezivel, mas a restricao esta registrada.
#
#
# 7. PARAMETROS EM AVALIACAO (desativados por padrao)
# -----------------------------------------------------------------------------
#   Um ponto permanece identificado na revisao tecnica como decisao
#   metodologica em aberto. Ele nao foi alterado silenciosamente: esta
#   implementado como parametro DESLIGADO por padrao.
#
#   DISTANCIA_MAXIMA_ASSOCIACAO_M (padrao None) - nao existe distancia maxima
#   de aceitacao; o raio de busca e o unico limitante. Ver Dist_SNV_m.
#
#   A compatibilidade com a Via deixou de ser parametro: por decisao registrada
#   do responsavel pela metodologia, ela e agora pre-condicao universal da
#   associacao (ver criterio UNICO_TRECHO na secao 5).
#
# =============================================================================

import math
import re
import statistics
from collections import Counter

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCsException,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsSpatialIndex,
    QgsVectorLayer,
    QgsWkbTypes,
    NULL,
)


# -----------------------------------------------------------------------------
# 0) CONFIGURACAO
# -----------------------------------------------------------------------------
NOME_CAMADA_OAE = "SGE"
NOME_CAMADA_SNV = "SNV_202607A"
NOME_CAMADA_SAIDA = "SGExSNV"

CAMPO_EXTENSAO = "Extensão (m)"
CAMPO_VIA = "Via"
CAMPO_RELACAO_SNV = "Relacao_SNV"

CAMPO_VL_CODIGO = "vl_codigo"
CAMPO_VL_KM_INIC = "vl_km_inic"
CAMPO_VL_KM_FINA = "vl_km_fina"
CAMPO_ADMIN_SNV = "ds_tipo_ad"
CAMPO_JURIS_SNV = "ds_jurisdi"

CAMPO_TRECHO_SNV = "Trecho_SNV"
CAMPO_ADMINISTRACAO = "Administracao"
CAMPO_JURISDICAO = "Jurisdicao"
CAMPO_KM_SNV = "km_SNV"
CAMPO_DIST_SNV = "Dist_SNV_m"
CAMPO_RAIO_SNV = "Raio_SNV"
CAMPO_QTD_CODIGOS = "Qtd_Codigos"
CAMPO_RODOVIAS_COINC = "Rodovias_coincidentes"
CAMPO_STATUS = "Status"
CAMPO_CRITERIO = "Criterio"
CAMPO_OBSERVACAO = "Obs_SNV"

# Todas as medicoes (distancia, comprimento, projecao) ocorrem neste SRC.
# EPSG:5880 (SIRGAS 2000 / Brazil Polyconic) cobre o territorio nacional em
# metros; medir em graus produziria distancias e raios sem significado fisico.
CRS_METRICA = QgsCoordinateReferenceSystem("EPSG:5880")

# O raio de busca e proporcional ao porte da OAE. Nao e um criterio de
# validade: e apenas a janela de coleta de candidatos.
FATOR_RAIO = 2.0

TOLERANCIA_EMPATE_DISTANCIA_M = 1e-8

# Usadas APENAS no aviso de trecho com sentido suspeito: nunca alteram o km.
# Distancia maxima entre extremos para considerar dois trechos conectados. A
# publicacao revisada apresentou as mesmas conexoes entre 1 e 20 metros; um
# metro basta e evita ligar trechos que apenas passam perto.
TOLERANCIA_CONEXAO_M = 1.0
# Precisao com que o km de emenda de dois trechos vizinhos e comparado: o SNV
# publica km com 3 casas decimais, isto e, ao metro.
CASAS_DECIMAIS_KM = 3

# Alerta de auditoria (nao altera o calculo): razao entre o comprimento
# geometrico do trecho e a extensao declarada (vl_km_fina - vl_km_inic).
# Desvios grandes indicam que a hipotese de proporcionalidade da interpolacao
# esta fragilizada naquele trecho.
TOLERANCIA_ESCALA_KM_GEOM = 0.10

# Limite duro OPCIONAL de associacao, em metros. None = desativado (metodologia
# original: nao ha distancia maxima; o raio de busca e o unico limitante).
DISTANCIA_MAXIMA_ASSOCIACAO_M = None

# Obs_SNV e truncado neste tamanho. 254 mantem a saida exportavel para
# Shapefile/DBF. Em GeoPackage o valor pode ser ampliado sem perda.
TAMANHO_MAX_OBS = 254
# Mesmo limite conservador para Rodovias_coincidentes, truncado de forma
# explicita pelo mesmo motivo que Obs_SNV: texto acima do comprimento declarado
# se perde sem aviso no provedor.
TAMANHO_MAX_RODOVIAS = 254
# Quantos codigos concorrentes sao listados antes de resumir por contagem.
LIMITE_CODIGOS_LISTADOS = 6

# Tupla para garantir a ordem de impressao dos grupos.
CRITERIOS_VALIDOS = (
    "SEM_TRECHO",
    "UNICO_TRECHO",
    "TRECHO_COINCIDENTE",
    "TRECHO_FRONTEIRA",
    "TRECHO_DIVERGENTE",
    "TRECHO_EMPATE",
)


# -----------------------------------------------------------------------------
# 1) FUNCOES AUXILIARES DE SANEAMENTO DE VALORES
# -----------------------------------------------------------------------------
def numero_finito_positivo(valor):
    """Converte um atributo para float exigindo valor finito e estritamente positivo.

    Parametros:
        valor: conteudo bruto de um atributo (QVariant, str, int, float, None).

    Retorna:
        float > 0, ou None quando o valor for nulo, booleano, nao numerico,
        infinito, NaN ou <= 0.

    Hipotese metodologica:
        Extensao de OAE nao positiva nao e dado, e ausencia de dado. Tratar
        zero ou negativo como valor valido produziria raio de busca degenerado.

    Excecoes:
        Booleanos sao rejeitados de proposito: em Python True == 1, o que
        converteria uma flag em extensao de 1 metro.
    """
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) and numero > 0 else None


def numero_finito(valor):
    """Converte um atributo para float exigindo apenas que seja finito.

    Parametros:
        valor: conteudo bruto de um atributo.

    Retorna:
        float finito, ou None para nulo, booleano, nao numerico, infinito ou NaN.

    Hipotese metodologica:
        Usada para km, que pode legitimamente ser zero. A validacao de dominio
        (ki >= 0 e kf > ki) e feita adiante, em preparar_trechos.
    """
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def codigo_valido(valor):
    """Normaliza um identificador textual sem inventar valor para nulos.

    Parametros:
        valor: conteudo bruto de um atributo textual (vl_codigo, vl_br, sg_uf...).

    Retorna:
        str nao vazia, sem espacos nas bordas, ou None.

    Hipotese metodologica:
        Sentinelas textuais de nulo ("NULL", "NONE", "NAN"), comuns em dados
        importados de planilha, sao tratadas como ausencia. Deixa-las passar
        criaria um "codigo" fantasma capaz de vencer uma selecao.
    """
    if valor is None or valor == NULL:
        return None
    codigo = str(valor).strip()
    return codigo if codigo and codigo.upper() not in {"NULL", "NONE", "NAN"} else None


def normalizar_via(valor):
    """Converte o atributo Via da OAE no numero de BR com tres digitos.

    Parametros:
        valor: conteudo bruto de CAMPO_VIA (ex.: "BR-453", "BR 70", "116", "70,0").

    Retorna:
        str com exatamente tres digitos ("453", "070"), ou None quando o texto
        nao corresponder, sem ambiguidade, a uma unica BR.

    Hipotese metodologica:
        O padrao e ancorado (fullmatch) e limitado a 1-3 digitos. Um texto como
        "BR-116/BR-101" ou "BR-1160" NAO e aceito: extrair digitos soltos
        concatenaria rodovias distintas ou truncaria um numero invalido,
        atribuindo a OAE a uma BR que ela nao declara.

    Excecoes:
        Sufixo decimal nulo (",0" / ".0") e tolerado por vir de leitura
        numerica da planilha de origem, nao por interpretacao do dado.
    """
    texto = codigo_valido(valor)
    if texto is None:
        return None
    match = re.fullmatch(r"(?:BR\s*[-–]?\s*)?([0-9]{1,3})(?:[.,]0+)?", texto, re.I)
    return match.group(1).zfill(3) if match else None


def prefixo_codigo(codigo):
    """Extrai o numero da BR embutido nos tres primeiros caracteres do vl_codigo.

    Parametros:
        codigo: vl_codigo do SNV (ex.: "116BMG0450").

    Retorna:
        str de tres digitos ("116"), ou None se o codigo nao tiver a forma
        esperada.

    Hipotese metodologica:
        O SNV codifica a BR nas tres primeiras posicoes de vl_codigo. Exigir
        que sejam digitos evita comparar a Via da OAE com um codigo fora do
        padrao. Observe que apenas a BR e comparada: a UF embutida no codigo
        NAO participa do teste de compatibilidade (ver Avaliacao Tecnica).
    """
    codigo = codigo_valido(codigo)
    if codigo is None or len(codigo) < 3 or not codigo[:3].isdigit():
        return None
    return codigo[:3]


def quase_igual(a, b, tolerancia):
    """Compara dois floats com tolerancia absoluta.

    Retorna:
        True se |a - b| <= tolerancia.

    Hipotese metodologica:
        Tolerancia ABSOLUTA (nao relativa) porque as grandezas comparadas sao
        homogeneas e de ordem conhecida: metros de distancia e quilometros de
        extensao. Tolerancia relativa se comportaria de modo diferente perto
        de zero, justamente onde ocorrem as coincidencias.
    """
    return abs(a - b) <= tolerancia


def formatar_lista_codigos(codigos, limite=LIMITE_CODIGOS_LISTADOS):
    """Formata um conjunto de codigos concorrentes para a trilha de auditoria.

    Parametros:
        codigos: iteravel de vl_codigo.
        limite: quantidade maxima de codigos escritos por extenso.

    Retorna:
        str ordenada alfabeticamente; o excedente vira ",+N".

    Hipotese metodologica:
        A ordenacao existe para tornar o texto de auditoria reproduzivel entre
        execucoes; ela NUNCA participa de qualquer selecao.
    """
    ordenados = sorted(codigos)
    if len(ordenados) <= limite:
        return ",".join(ordenados)
    return ",".join(ordenados[:limite]) + f",+{len(ordenados) - limite}"


def valor_unanime(valores):
    """Reduz a um unico valor um atributo lido de uma ou mais feicoes do trecho.

    Parametros:
        valores: valores brutos do atributo nas feicoes do codigo atribuido que
            realizam a menor distancia da OAE (normalmente uma so).

    Retorna:
        (valor, divergente)
        valor: texto normalizado comum a todas as feicoes, ou None.
        divergente: True quando as feicoes discordam entre si.

    Hipoteses metodologicas:
        - Um mesmo vl_codigo pode estar repartido em varias feicoes, e duas
          delas podem estar a mesma distancia da OAE. Se todas trazem o mesmo
          valor, ele descreve o trecho sem ambiguidade e e gravado.
        - Se discordam, nao ha como saber qual descreve a posicao da OAE sem
          arbitrar - e o procedimento nao arbitra em parte alguma. O campo fica
          NULL e a divergencia e devolvida para registro em Obs_SNV.
        - Os valores passam por codigo_valido(), de modo que espacos nas bordas,
          texto vazio e sentinelas como "NULL" nao gerem falsa divergencia nem
          falso preenchimento. Valor ausente numa feicao e presente noutra conta
          como divergencia: a ausencia nao e prova de que o valor seja o mesmo.
    """
    distintos = {codigo_valido(valor) for valor in valores}
    if len(distintos) == 1:
        return next(iter(distintos)), False
    return None, len(distintos) > 1


def truncar_texto(texto, limite):
    """Limita um texto ao comprimento declarado do campo que vai recebe-lo.

    Parametros:
        texto: conteudo a gravar, ou None.
        limite: comprimento maximo do campo de destino.

    Retorna:
        str de no maximo `limite` caracteres, ou None se nao houver texto.

    Hipotese metodologica:
        Texto excedendo o comprimento declarado do campo e truncado em silencio
        - ou rejeitado - pelo provedor, o que faria a trilha de rastreabilidade
        desaparecer sem aviso. O corte e feito aqui, de forma deterministica, e
        sinalizado com o marcador "...[truncado]", de modo que a perda seja
        sempre visivel no proprio dado.
    """
    if not texto:
        return None
    if len(texto) <= limite:
        return texto
    marcador = "...[truncado]"
    return texto[: limite - len(marcador)] + marcador


def observacao_texto(*partes):
    """Concatena fragmentos nao vazios da trilha de rastreabilidade.

    Retorna:
        str com os fragmentos separados por "; ", ou None se nada houver a
        registrar. Os fragmentos sao codigos internos (ex.: "VIA_OAE=116"),
        convertidos em texto legivel so na gravacao (texto_saida_obs).

    Hipotese metodologica:
        Os fragmentos sao passados em ordem decrescente de relevancia
        (causa da decisao primeiro, detalhes numericos depois), de modo que um
        eventual truncamento, feito depois da conversao, preserve sempre a
        informacao essencial.
    """
    return "; ".join(parte for parte in partes if parte) or None


# -----------------------------------------------------------------------------
# 1.0.1) TEXTOS GRAVADOS NA CAMADA DE SAIDA E STATUS
# -----------------------------------------------------------------------------
# Internamente o script trabalha com codigos estaveis (UNICO_TRECHO,
# VIA_OAE=116): a logica, os contadores e o resumo do console dependem deles.
# Na camada de saida eles sao trocados por texto em portugues, com so a
# primeira letra maiuscula e as siglas preservadas (SNV, OAE, BR, km).

TEXTO_CRITERIO = {
    "SEM_TRECHO": "Sem trecho",
    "UNICO_TRECHO": "Trecho único",
    "TRECHO_DIVERGENTE": "Trecho divergente",
    "TRECHO_EMPATE": "Trecho empate",
    "TRECHO_COINCIDENTE": "Trecho coincidente",
    "TRECHO_FRONTEIRA": "Trecho fronteira",
}

# Itens de Obs_SNV. Os que aparecem como CHAVE=valor viram "Rotulo: valor".
TEXTO_OBS = {
    # avisos e causas
    "ADMINISTRACAO_DIVERGENTE_ENTRE_GEOMETRIAS": "Administração divergente entre geometrias",
    "CODIGOS_COINCIDENTES_COMPATIVEIS_COM_VIA_EQUIDISTANTES_DA_OAE":
        "Códigos coincidentes compatíveis com a via equidistantes da OAE",
    "CODIGOS_COINCIDENTES_COMPATIVEIS_EQUIDISTANTES":
        "Códigos coincidentes compatíveis equidistantes",
    "CODIGOS_COMPATIVEIS_COM_VIA_EQUIDISTANTES_DA_OAE":
        "Códigos compatíveis com a via equidistantes da OAE",
    "CODIGOS_COMPATIVEIS_EQUIDISTANTES": "Códigos compatíveis equidistantes",
    "COINCIDENCIA_ENTRE_CODIGOS_DA_MESMA_BR": "Coincidência entre códigos da mesma BR",
    "EMPATE_DE_GEOMETRIAS_DO_MESMO_CODIGO": "Empate de geometrias do mesmo código",
    "FALHA_NA_PROJECAO_OU_INTERPOLACAO": "Falha na projeção ou interpolação",
    "GEOMETRIA_OAE_INVALIDA_OU_MULTIPONTO": "Geometria da OAE inválida ou multiponto",
    "GEOMETRIA_SNV_AUSENTE": "Geometria SNV ausente",
    "GEOMETRIA_SNV_COMPRIMENTO_NULO": "Geometria SNV de comprimento nulo",
    "GEOMETRIA_SNV_MULTIPARTE": "Geometria SNV multiparte",
    "GEOMETRIA_SNV_NAO_LINEAR": "Geometria SNV não linear",
    "INTERVALO_KM_INVALIDO": "Intervalo de km inválido",
    "JURISDICAO_DIVERGENTE_ENTRE_GEOMETRIAS": "Jurisdição divergente entre geometrias",
    "PREPARO_DO_TRECHO_INCOMPLETO": "Preparo do trecho incompleto",
    "SEM_CANDIDATO_NO_RAIO": "Sem candidato no raio",
    "TRECHO_SNV_CONTINUIDADE_CONTRADITORIA": "Trecho SNV com continuidade contraditória",
    "TRECHO_SNV_POSSIVELMENTE_INVERTIDO": "Trecho SNV possivelmente invertido",
    "UNICO_CODIGO_INCOMPATIVEL_COM_VIA": "Único código incompatível com a via",
    "VIA_AUSENTE_OU_NAO_NORMALIZAVEL": "Via ausente ou não normalizável",
    # chaves de CHAVE=valor
    "ALERTA_ESCALA_KM_GEOM": "Alerta de escala km/geometria",
    "CODIGOS_EM_EMPATE": "Códigos em empate",
    "CODIGOS_NO_RAIO": "Códigos no raio",
    "CODIGO_NO_RAIO": "Código no raio",
    "DESCARTADOS_NO_MINIMO": "Descartados na distância mínima",
    "DIST_EQUIDISTANTE_M": "Distância comum (m)",
    "DIST_M": "Distância (m)",
    "DIST_MIN_M": "Distância mínima (m)",
    "FEICOES_ALEM_DA_DISTANCIA_MAXIMA": "Feições além da distância máxima",
    "FEICOES_SNV_SEM_CODIGO_NO_RAIO": "Feições SNV sem código no raio",
    "FRACAO": "Fração",
    "MARGEM_M": "Margem para o 2º compatível (m)",
    "MIN_VIA_M": "Menor distância entre compatíveis (m)",
    "N_CODIGOS": "Quantidade de códigos no raio",
    "N_COMPATIVEIS": "Quantidade de códigos compatíveis",
    "N_EMPATADOS": "Quantidade de códigos empatados",
    "N_GEOMETRIAS": "Quantidade de geometrias empatadas",
    "NENHUM_CODIGO_COMPATIVEL_COM_VIA": "Nenhum código compatível com a via",
    "PREFIXO_CODIGO": "Prefixo do código",
    "PROJECAO_NO_EXTREMO": "Projeção no extremo",
    "RAIO_M": "Raio (m)",
    "SOBREPOSICAO_COM": "Sobreposição com",
    "VIA_OAE": "Via da OAE",
}

# Valores textuais que aparecem depois do "=".
TEXTO_VALOR_OBS = {
    "AUSENTE": "ausente",
    "INDEFINIDO": "indefinido",
    "INICIO_GEOM": "início da geometria",
    "FIM_GEOM": "fim da geometria",
}

STATUS_VALIDADO = "Validado"
STATUS_A_VALIDAR = "A validar"


def texto_generico(codigo):
    """Converte um codigo sem frase propria: minusculas, espacos, inicial maiuscula.

    Rede de seguranca para que nada saia em caixa alta na camada de saida;
    todo codigo emitido pelo script deve ter frase propria em TEXTO_OBS (ha
    teste que verifica isso).
    """
    texto = codigo.replace("_", " ").lower()
    return texto[:1].upper() + texto[1:]


def texto_saida_obs(observacao):
    """Converte a observacao interna em texto legivel e a ajusta ao campo.

    Parametros:
        observacao: itens internos separados por "; " (ex.:
            "TRECHO_SNV_POSSIVELMENTE_INVERTIDO; VIA_OAE=116"), ou None.

    Retorna:
        Texto legivel ("Trecho SNV possivelmente invertido; Via da OAE: 116"),
        limitado a TAMANHO_MAX_OBS, ou None.

    Hipotese metodologica:
        Valores numericos e codigos SNV nao sao alterados. O truncamento ocorre
        DEPOIS da conversao porque as frases sao um pouco mais longas que os
        codigos; truncar antes cortaria um item ao meio.
    """
    # Atributo nunca preenchido chega como NULL do QGIS, que nao e str.
    if not isinstance(observacao, str) or not observacao:
        return None
    itens = []
    for item in observacao.split("; "):
        chave, separador, valor = item.partition("=")
        rotulo = TEXTO_OBS.get(chave) or texto_generico(chave)
        if separador:
            itens.append(f"{rotulo}: {TEXTO_VALOR_OBS.get(valor, valor)}")
        else:
            itens.append(rotulo)
    return truncar_texto("; ".join(itens), TAMANHO_MAX_OBS)


def texto_saida_criterio(criterio):
    """Texto legivel do criterio para a camada de saida (ex.: "Trecho único")."""
    if not isinstance(criterio, str) or not criterio:
        return None
    return TEXTO_CRITERIO.get(criterio) or texto_generico(criterio)


def status_validacao(criterio, relacao_snv, qtd_codigos):
    """Reproduz a formula de validacao da planilha de conferencia.

    Formula de origem:
        =SE(OU(E(Criterio="UNICO_TRECHO"; Relacao_SNV="L");
               E(Criterio="TRECHO_COINCIDENTE"; Qtd_Codigos<3));
            "VALIDADO"; "A VALIDAR")

    Parametros:
        criterio: codigo INTERNO do criterio (ex.: "UNICO_TRECHO").
        relacao_snv: valor bruto do campo Relacao_SNV da OAE.
        qtd_codigos: quantidade de vl_codigo distintos no raio.

    Retorna:
        STATUS_VALIDADO ou STATUS_A_VALIDAR; nunca None.

    Hipoteses metodologicas:
        - A comparacao usa o codigo interno do criterio, e nao o texto exibido,
          para nao depender da redacao gravada na camada.
        - Relacao_SNV e comparado com "L" sem distinguir maiusculas, como o
          Excel, e tambem sem espacos nas bordas - nesse ponto difere do Excel,
          que considera " L" diferente de "L". Valor vazio ou nulo nao e "L".
    """
    relacao = codigo_valido(relacao_snv)
    validado = (
        (criterio == "UNICO_TRECHO" and relacao is not None and relacao.upper() == "L")
        or (criterio == "TRECHO_COINCIDENTE" and qtd_codigos is not None and qtd_codigos < 3)
    )
    return STATUS_VALIDADO if validado else STATUS_A_VALIDAR


# -----------------------------------------------------------------------------
# 1.1) FUNCOES DE DECISAO DA ASSOCIACAO OAE x CODIGO SNV
# -----------------------------------------------------------------------------
def codigos_sobrepostos(registro_a, registro_b, feicoes, geometria_oae=None):
    """Verifica se dois codigos SNV sao localmente COINCIDENTES junto a OAE.

    Parametros:
        registro_a, registro_b: registros de por_codigo, contendo "distancia" e
            "feicoes_mais_proximas" (lista de (fid, distancia) que realizam a
            menor distancia daquele codigo).
        feicoes: mapa fid -> QgsFeature da copia metrica da SNV.
        geometria_oae: ponto da OAE em CRS_METRICA. Se None, dispensa o teste
            de localidade (uso apenas diagnostico).

    Retorna:
        bool - True somente se existir porcao LINEAR comum de comprimento
        positivo situada exatamente a distancia minima de ambos os codigos.

    Hipoteses metodologicas:
        1. Sobreposicao exige interseccao LINEAR. Cruzamento pontual (viaduto,
           entroncamento) e paralelismo equidistante nao comprovam coincidencia
           de trecho: um cruzamento gera um ponto, nao um trecho comum.
        2. A porcao comum precisa estar NA POSICAO de menor distancia da OAE.
           Duas rodovias podem coincidir a dezenas de quilometros dali e estar,
           por acaso, equidistantes da OAE neste ponto; essa coincidencia remota
           nao explica a equidistancia local e nao pode justificar a escolha.
        3. Nao se aplica buffer, snap ou deslocamento de vertice. Coincidencia
           precisa existir no dado, nao ser fabricada por tolerancia.

    Excecoes:
        A interseccao pode retornar uma GeometryCollection contendo, ao mesmo
        tempo, uma linha comum distante e um ponto de cruzamento proximo. Por
        isso a colecao e percorrida recursivamente e cada parte linear e
        avaliada isoladamente.
    """
    def partes_lineares(geometria):
        """Percorre recursivamente uma geometria e devolve apenas partes lineares."""
        if QgsWkbTypes.geometryType(geometria.wkbType()) == QgsWkbTypes.LineGeometry:
            yield geometria
        elif QgsWkbTypes.flatType(geometria.wkbType()) == QgsWkbTypes.GeometryCollection:
            for parte in geometria.asGeometryCollection():
                yield from partes_lineares(parte)

    for fid_a, _ in registro_a["feicoes_mais_proximas"]:
        for fid_b, _ in registro_b["feicoes_mais_proximas"]:
            comum = feicoes[fid_a].geometry().intersection(feicoes[fid_b].geometry())
            if comum.isNull() or comum.isEmpty():
                continue
            for parte in partes_lineares(comum):
                comprimento = parte.length()
                if not math.isfinite(comprimento) or comprimento <= 0:
                    continue
                if geometria_oae is None:
                    return True
                distancia = parte.distance(geometria_oae)
                # A porcao comum so explica a equidistancia se ela propria
                # estiver na distancia minima de AMBOS os codigos.
                if math.isfinite(distancia) and distancia >= 0 and all(
                    quase_igual(distancia, r["distancia"], TOLERANCIA_EMPATE_DISTANCIA_M)
                    for r in (registro_a, registro_b)
                ):
                    return True
    return False


def rodovias_coincidentes_texto(coincidentes, codigo_escolhido=None):
    """Converte a coincidencia detectada na lista de rodovias que a compoem.

    Parametros:
        coincidentes: dict codigo -> [codigos parceiros], montado em
            selecionar_codigo, contendo apenas pares com sobreposicao linear
            comprovada na posicao de menor distancia da OAE.
        codigo_escolhido: vl_codigo atribuido a OAE, quando houver.

    Retorna:
        (texto, rodovias_distintas)
        texto: numeros de BR separados por ";" (ex.: "116;101"), ou None quando
            nao houver coincidencia detectada.
        rodovias_distintas: quantidade de BRs distintas envolvidas.

    Hipoteses metodologicas:
        - Identifica as OAEs situadas sobre rodovias COINCIDENTES, isto e,
          rodovias que ocupam o mesmo espaco, parcial ou totalmente. Estar
          proximo nao basta: o conjunto vem exclusivamente da sobreposicao
          linear ja comprovada pelo criterio, nunca do raio de busca.
        - A rodovia ATRIBUIDA encabeca a lista, tornando o campo autossuficiente
          na leitura ("aqui a BR-116 e a BR-101 sao coincidentes") sem exigir o
          cruzamento com Trecho_SNV. As demais seguem em ordem numerica.
        - Sem codigo atribuido (TRECHO_EMPATE), todas as BRs saem em ordem
          numerica crescente: os codigos estao todos a mesma distancia minima,
          de modo que nao ha criterio de proximidade que os separe, e a ordem
          numerica assegura o determinismo exigido no restante do procedimento.

    Excecoes:
        Dois codigos DISTINTOS da MESMA BR podem se sobrepor - geometria
        duplicada no SNV, e nao coincidencia entre rodovias. Nesse caso a lista
        deduplicada resulta numa unica BR. O texto permanece verdadeiro, e a
        contagem devolvida permite ao chamador sinalizar a anomalia, de modo que
        a OAE nao seja lida como estando sobre rodovias coincidentes.

    Limitacao registrada:
        O campo espelha estritamente o que o criterio detecta. Duas rodovias
        fisicamente coincidentes cujas geometrias no SNV estejam digitalizadas
        com alguns centimetros de diferenca nao satisfazem a equidistancia
        exigida e nao sao detectadas aqui.
    """
    if not coincidentes:
        return None, 0

    envolvidos = set()
    for codigo, parceiros in coincidentes.items():
        envolvidos.add(codigo)
        envolvidos.update(parceiros)

    rodovias = {prefixo_codigo(c) for c in envolvidos}
    rodovias.discard(None)
    if not rodovias:
        return None, 0

    rodovia_escolhida = prefixo_codigo(codigo_escolhido) if codigo_escolhido else None
    if rodovia_escolhida in rodovias:
        ordenadas = [rodovia_escolhida] + sorted(rodovias - {rodovia_escolhida})
    else:
        ordenadas = sorted(rodovias)
    return ";".join(ordenadas), len(rodovias)


def selecionar_codigo(por_codigo, via, feicoes, geometria_oae):
    """Seleciona um unico vl_codigo para a OAE e classifica a associacao.

    Parametros:
        por_codigo: dict vl_codigo -> {"distancia": float,
                    "feicoes_mais_proximas": [(fid, distancia), ...]}, contendo
                    todos os codigos distintos dentro do raio de busca.
        via: numero da BR da OAE normalizado (3 digitos) ou None.
        feicoes: mapa fid -> QgsFeature da copia metrica da SNV.
        geometria_oae: ponto da OAE em CRS_METRICA.

    Retorna:
        (codigo_ou_None, criterio, causa, rodovias_coincidentes, observacao)
        "causa" e um token curto que identifica o motivo da NAO associacao;
        vale None quando um codigo e efetivamente atribuido.
        "rodovias_coincidentes" e a lista de BRs em sobreposicao comprovada
        (ver rodovias_coincidentes_texto), ou None quando nao houver
        coincidencia detectada. Como o dicionario de coincidencias so existe
        dentro desta funcao, e aqui que ele precisa ser exposto.

    Sequencia de decisao (mutuamente exclusiva e exaustiva):
        1. Conjunto vazio                          -> SEM_TRECHO
        2. Exatamente um codigo no raio:
           2a. compativel com a Via                -> UNICO_TRECHO
           2b. incompativel, ou Via ausente        -> TRECHO_DIVERGENTE
        3. Dois ou mais codigos no raio:
           3a. nenhum compativel com a Via         -> TRECHO_DIVERGENTE
           3b. vencedor nao unico                  -> TRECHO_EMPATE
           3c. vencedor unico com coincidencia     -> TRECHO_COINCIDENTE
           3d. vencedor unico sem coincidencia     -> TRECHO_FRONTEIRA

    Hipoteses metodologicas:
        - A compatibilidade com a Via declarada da OAE e PRE-CONDICAO UNIVERSAL
          da associacao: nenhum codigo de BR diferente da Via pode ser
          atribuido, ainda que seja o unico presente no raio de busca. Em
          consequencia, todo criterio que devolve codigo (UNICO_TRECHO,
          TRECHO_COINCIDENTE, TRECHO_FRONTEIRA) devolve necessariamente um
          codigo compativel. A distancia e criterio de desempate DENTRO do
          conjunto compativel, jamais criterio de admissao.
        - A cardinalidade que distingue UNICO_TRECHO e medida sobre TODOS os
          codigos do raio, nao apenas sobre os compativeis. Havendo outros
          codigos no raio, existiu concorrencia espacial a documentar, e a
          decisao pertence ao ramo 3 mesmo que apenas um codigo seja compativel.
        - A distancia minima e calculada sobre TODOS os codigos compativeis com
          a Via, incluindo os nao coincidentes, e ANTES de qualquer regra de
          prioridade. Isso impede que um par coincidente mais distante vencesse
          um trecho compativel efetivamente mais proximo.
        - A prioridade da coincidencia sobre a fronteira so opera DENTRO do
          conjunto de distancia minima; ela nunca "resgata" um codigo distante.
        - O parceiro que comprova a coincidencia pode pertencer a outra BR
          (situacao normal em trechos coincidentes), mas o codigo ESCOLHIDO
          precisa ser sempre compativel com a Via declarada da OAE. Por isso
          TRECHO_COINCIDENTE permanece alcancavel quando ha um unico codigo
          compativel: a coincidencia fisica de dois codigos SNV sobre o mesmo
          eixo e a informacao que a auditoria precisa isolar, e ela prevalece
          sobre a simples contagem de concorrentes compativeis.
        - Empate entre coincidencias nao e resolvido por fronteira: as duas
          regras pertencem ao mesmo nivel de decisao, e recorrer a segunda apos
          o empate da primeira reintroduziria arbitrariedade.

    Excecoes:
        TRECHO_EMPATE significa que DOIS OU MAIS codigos compativeis com a Via
        estao a MESMA DISTANCIA da OAE, dentro de TOLERANCIA_EMPATE_DISTANCIA_M.
        Nenhum criterio objetivo os separa e o desempate por ordem de leitura e
        proibido; a OAE permanece sem trecho e, portanto, sem km. Os codigos
        empatados e a distancia comum sao registrados em Obs_SNV.

        Uma OAE cuja Via esteja ausente ou nao seja normalizavel nunca possui
        codigo compativel e por isso jamais e associada. A causa fica separada
        da divergencia real, para nao confundir falha de cadastro na origem com
        divergencia entre a posicao da OAE e a malha proxima.
    """
    if not por_codigo:
        return None, "SEM_TRECHO", "SEM_CANDIDATO_NO_RAIO", None, None

    if len(por_codigo) == 1:
        codigo = next(iter(por_codigo))
        prefixo = prefixo_codigo(codigo)
        # Ausencia de concorrencia NAO dispensa a prova de compatibilidade. Um
        # unico trecho no raio e apenas o unico candidato disponivel, e nao
        # evidencia de que a OAE pertenca aquela rodovia: associa-lo sem
        # verificar a Via atribuiria a OAE a outra BR e calcularia o km sobre
        # ela, justamente nas OAEs isoladas, onde o erro e menos visivel.
        if via is None or prefixo != via:
            causa = (
                "VIA_AUSENTE_OU_NAO_NORMALIZAVEL" if via is None
                else "UNICO_CODIGO_INCOMPATIVEL_COM_VIA"
            )
            return None, "TRECHO_DIVERGENTE", causa, None, observacao_texto(
                causa,
                f"VIA_OAE={via or 'AUSENTE'}",
                f"CODIGO_NO_RAIO={codigo}",
                f"PREFIXO_CODIGO={prefixo or 'INDEFINIDO'}",
                f"DIST_M={por_codigo[codigo]['distancia']:.6f}",
                f"N_CODIGOS={len(por_codigo)}",
            )
        return codigo, "UNICO_TRECHO", None, None, observacao_texto(
            f"VIA_OAE={via}",
            f"PREFIXO_CODIGO={prefixo}",
            f"DIST_MIN_M={por_codigo[codigo]['distancia']:.6f}",
            f"N_CODIGOS={len(por_codigo)}",
        )

    compativeis = [c for c in por_codigo if via is not None and prefixo_codigo(c) == via]
    if not compativeis:
        # As duas causas sao distintas para a auditoria: dado de origem ausente
        # na OAE, ou dado presente e efetivamente divergente da malha proxima.
        causa = (
            "VIA_AUSENTE_OU_NAO_NORMALIZAVEL" if via is None
            else "NENHUM_CODIGO_COMPATIVEL_COM_VIA"
        )
        return None, "TRECHO_DIVERGENTE", causa, None, observacao_texto(
            causa if via is None else f"{causa}={via}",
            f"N_CODIGOS={len(por_codigo)}",
            "CODIGOS_NO_RAIO=" + formatar_lista_codigos(por_codigo),
        )

    distancias = sorted(por_codigo[c]["distancia"] for c in compativeis)
    menor = distancias[0]
    # Margem = folga entre o 1o e o 2o codigo compativel. E a evidencia direta
    # da robustez da escolha: margem grande = decisao segura; margem milimetrica
    # = decisao sensivel a precisao do tracado.
    margem = distancias[1] - menor if len(distancias) > 1 else None

    mais_proximos = [c for c in compativeis if quase_igual(
        por_codigo[c]["distancia"], menor, TOLERANCIA_EMPATE_DISTANCIA_M)]

    # Memoriza o teste de sobreposicao por par de codigos: ele envolve
    # interseccao de geometrias e seria refeito varias vezes por OAE.
    cache_sobreposicao = {}

    def sobrepostos(codigo_x, codigo_y):
        chave = (codigo_x, codigo_y) if codigo_x <= codigo_y else (codigo_y, codigo_x)
        if chave not in cache_sobreposicao:
            cache_sobreposicao[chave] = codigos_sobrepostos(
                por_codigo[codigo_x], por_codigo[codigo_y], feicoes, geometria_oae
            )
        return cache_sobreposicao[chave]

    coincidentes = {}
    for codigo in mais_proximos:
        registro = por_codigo[codigo]
        parceiros = [
            outro for outro, candidato in por_codigo.items()
            if outro != codigo
            and quase_igual(registro["distancia"], candidato["distancia"],
                            TOLERANCIA_EMPATE_DISTANCIA_M)
            and sobrepostos(codigo, outro)
        ]
        if parceiros:
            coincidentes[codigo] = parceiros

    vencedores = list(coincidentes) if coincidentes else mais_proximos

    auditoria_comum = observacao_texto(
        f"MIN_VIA_M={menor:.6f}",
        f"MARGEM_M={margem:.6f}" if margem is not None else None,
        f"N_CODIGOS={len(por_codigo)}",
        f"N_COMPATIVEIS={len(compativeis)}",
    )

    if len(vencedores) != 1:
        # O fato metodologico do empate: os codigos listados sao TODOS
        # compativeis com a Via declarada da OAE e estao TODOS a mesma
        # distancia dela, dentro de TOLERANCIA_EMPATE_DISTANCIA_M. Como a
        # compatibilidade ja nao os separa e a distancia tambem nao, nenhum
        # criterio objetivo resta; desempatar pela ordem de leitura tornaria o
        # resultado dependente do arquivo de entrada, e por isso e proibido.
        causa = (
            "CODIGOS_COINCIDENTES_COMPATIVEIS_EQUIDISTANTES" if coincidentes
            else "CODIGOS_COMPATIVEIS_EQUIDISTANTES"
        )
        descricao = (
            "CODIGOS_COINCIDENTES_COMPATIVEIS_COM_VIA_EQUIDISTANTES_DA_OAE"
            if coincidentes
            else "CODIGOS_COMPATIVEIS_COM_VIA_EQUIDISTANTES_DA_OAE"
        )
        # A OAE empatada entre codigos coincidentes esta fisicamente sobre
        # rodovias coincidentes, ainda que a associacao nao tenha sido
        # resolvida: excluí-la do levantamento a deixaria de fora de um
        # conjunto ao qual pertence.
        rodovias_coinc, _ = rodovias_coincidentes_texto(coincidentes)
        return None, "TRECHO_EMPATE", causa, rodovias_coinc, observacao_texto(
            descricao,
            f"VIA_OAE={via}",
            f"N_EMPATADOS={len(vencedores)}",
            "CODIGOS_EM_EMPATE=" + formatar_lista_codigos(vencedores),
            f"DIST_EQUIDISTANTE_M={menor:.6f}",
            auditoria_comum,
        )

    codigo = vencedores[0]
    # Concorrentes descartados na propria distancia minima: sao os casos em que
    # a decisao foi tomada pela regra de coincidencia, e nao pela distancia.
    descartados = [c for c in mais_proximos if c != codigo]

    if coincidentes:
        rodovias_coinc, n_rodovias = rodovias_coincidentes_texto(coincidentes, codigo)
        # Sobreposicao entre codigos distintos da MESMA BR e geometria duplicada
        # no SNV, nao coincidencia entre rodovias: sinalizado para que a OAE nao
        # seja lida como estando sobre rodovias coincidentes.
        anomalia = ("COINCIDENCIA_ENTRE_CODIGOS_DA_MESMA_BR"
                    if n_rodovias == 1 else None)
        return codigo, "TRECHO_COINCIDENTE", None, rodovias_coinc, observacao_texto(
            anomalia,
            "SOBREPOSICAO_COM=" + formatar_lista_codigos(coincidentes[codigo]),
            "DESCARTADOS_NO_MINIMO=" + formatar_lista_codigos(descartados)
            if descartados else None,
            auditoria_comum,
        )
    return codigo, "TRECHO_FRONTEIRA", None, None, auditoria_comum


# -----------------------------------------------------------------------------
# 1.2) FUNCOES AUXILIARES GEOMETRICAS
# -----------------------------------------------------------------------------
def retangulo_centrado(ponto, raio):
    """Constroi o envelope de consulta ao indice espacial.

    Hipotese metodologica:
        O quadrado de semilado igual ao raio CONTEM o circulo de busca. Todo
        candidato a distancia <= raio necessariamente intersecta este envelope,
        de modo que a filtragem por indice nao descarta candidato algum; a
        distancia real e reavaliada depois.
    """
    return QgsRectangle(
        ponto.x() - raio,
        ponto.y() - raio,
        ponto.x() + raio,
        ponto.y() + raio,
    )


def preparar_linha(geometria):
    """Reduz a geometria de um trecho SNV a uma linha de parte unica.

    Parametros:
        geometria: QgsGeometry do trecho, ja em CRS_METRICA.

    Retorna:
        (linha, causa)
        linha: QgsGeometry de parte unica e comprimento positivo, na mesma
            ordem de vertices em que esta gravada, ou None.
        causa: None quando a linha e apta; senao o motivo da recusa.

    Hipoteses metodologicas:
        - Os trechos do SNV sao LineStrings digitalizadas no sentido crescente
          da rota. A ordem dos vertices E o sentido do km: o primeiro vertice
          corresponde a vl_km_inic e o ultimo a vl_km_fina. Por isso a ordem
          gravada nunca e alterada aqui.
        - Uma MultiLineString de UMA parte (forma comum em Shapefile e
          GeoPackage) e apenas um envelope: a parte e extraida tal como esta.

    Excecoes:
        Duas ou mais partes sao recusadas (GEOMETRIA_SNV_MULTIPARTE). Junta-las
        exigiria mergeLines(), que pode inverter ou reordenar as partes - e,
        com isso, inverter o sentido do km sem aviso.
    """
    if geometria is None or geometria.isNull() or geometria.isEmpty():
        return None, "GEOMETRIA_SNV_AUSENTE"
    if QgsWkbTypes.geometryType(geometria.wkbType()) != QgsWkbTypes.LineGeometry:
        return None, "GEOMETRIA_SNV_NAO_LINEAR"

    linha = QgsGeometry(geometria)
    if linha.isMultipart():
        partes = linha.asGeometryCollection()
        if len(partes) != 1:
            return None, "GEOMETRIA_SNV_MULTIPARTE"
        linha = QgsGeometry(partes[0])

    comprimento = linha.length()
    if not math.isfinite(comprimento) or comprimento <= 0:
        return None, "GEOMETRIA_SNV_COMPRIMENTO_NULO"
    return linha, None


def geometria_pontual_metrica(feicao, transformacao):
    """Clona e reprojeta a geometria da OAE para o SRC metrico.

    Parametros:
        feicao: QgsFeature da camada OAE.
        transformacao: QgsCoordinateTransform ou None (camada ja metrica).

    Retorna:
        QgsGeometry pontual em CRS_METRICA, ou None.

    Hipoteses metodologicas:
        Um MultiPoint so e aceito quando contem exatamente um ponto. Escolher
        um dentre varios seria arbitrar a posicao da OAE e, por consequencia,
        arbitrar o trecho e o km resultantes.

    Excecoes:
        Falha de reprojecao (QgsCsException) e coordenadas nao finitas resultam
        em None, o que classifica a OAE como SEM_TRECHO com causa registrada.
    """
    geometria = feicao.geometry()
    if geometria is None or geometria.isNull() or geometria.isEmpty():
        return None
    if QgsWkbTypes.geometryType(geometria.wkbType()) != QgsWkbTypes.PointGeometry:
        return None

    geometria = QgsGeometry(geometria)
    if transformacao is not None:
        try:
            geometria.transform(transformacao)
        except QgsCsException:
            return None

    if geometria.isMultipart():
        pontos = geometria.asMultiPoint()
        if len(pontos) != 1:
            return None
        ponto = pontos[0]
    else:
        ponto = geometria.asPoint()
    if not all(math.isfinite(v) for v in (ponto.x(), ponto.y())):
        return None
    return QgsGeometry.fromPointXY(QgsPointXY(ponto))


# -----------------------------------------------------------------------------
# 2) CAMADAS E CAMPOS
# -----------------------------------------------------------------------------
projeto = QgsProject.instance()

lista_oae = projeto.mapLayersByName(NOME_CAMADA_OAE)
lista_snv = projeto.mapLayersByName(NOME_CAMADA_SNV)

if not lista_oae:
    raise Exception(f'Camada "{NOME_CAMADA_OAE}" nao encontrada no projeto.')
if not lista_snv:
    raise Exception(f'Camada "{NOME_CAMADA_SNV}" nao encontrada no projeto.')
# Nome duplicado impediria saber qual camada foi processada: o resultado
# deixaria de ser rastreavel, portanto a execucao e interrompida.
if len(lista_oae) != 1 or len(lista_snv) != 1:
    raise Exception("Nomes duplicados de camadas de entrada: mantenha uma SGE e uma SNV.")

camada_oae = lista_oae[0]
camada_snv = lista_snv[0]
if not all(c.isValid() and c.crs().isValid() for c in (camada_oae, camada_snv)):
    raise Exception("Camada de entrada ou seu CRS invalido.")

if camada_oae.geometryType() != QgsWkbTypes.PointGeometry:
    raise Exception(f'A camada "{NOME_CAMADA_OAE}" precisa ser pontual.')
if camada_snv.geometryType() != QgsWkbTypes.LineGeometry:
    raise Exception(f'A camada "{NOME_CAMADA_SNV}" precisa ser linear.')

campos_oae = {campo.name() for campo in camada_oae.fields()}
campos_snv = {campo.name() for campo in camada_snv.fields()}

obrigatorios_oae = {CAMPO_EXTENSAO, CAMPO_VIA, CAMPO_RELACAO_SNV}
obrigatorios_snv = {
    CAMPO_VL_CODIGO, CAMPO_VL_KM_INIC, CAMPO_VL_KM_FINA,
    CAMPO_ADMIN_SNV, CAMPO_JURIS_SNV,
}

faltantes_oae = sorted(obrigatorios_oae - campos_oae)
faltantes_snv = sorted(obrigatorios_snv - campos_snv)
if faltantes_oae:
    raise Exception(f"Campos ausentes em {NOME_CAMADA_OAE}: {', '.join(faltantes_oae)}")
if faltantes_snv:
    raise Exception(f"Campos ausentes em {NOME_CAMADA_SNV}: {', '.join(faltantes_snv)}")

campos_novos = {
    CAMPO_TRECHO_SNV,
    CAMPO_ADMINISTRACAO,
    CAMPO_JURISDICAO,
    CAMPO_KM_SNV,
    CAMPO_RODOVIAS_COINC,
    CAMPO_STATUS,
    CAMPO_CRITERIO,
    CAMPO_OBSERVACAO,
    CAMPO_DIST_SNV,
    CAMPO_RAIO_SNV,
    CAMPO_QTD_CODIGOS,
}
# Colisao de nomes duplicaria colunas na saida e tornaria ambiguo qual delas
# contem o resultado desta execucao.
colisoes = sorted(campos_novos & campos_oae)
if colisoes:
    raise Exception(
        "A SGE ja possui campos reservados para a saida: " + ", ".join(colisoes)
    )

if not CRS_METRICA.isValid():
    raise Exception("CRS_METRICA invalida.")

contexto_transformacao = projeto.transformContext()
transformacao_oae = None
if camada_oae.crs() != CRS_METRICA:
    transformacao_oae = QgsCoordinateTransform(
        camada_oae.crs(), CRS_METRICA, contexto_transformacao
    )

transformacao_snv = None
if camada_snv.crs() != CRS_METRICA:
    transformacao_snv = QgsCoordinateTransform(
        camada_snv.crs(), CRS_METRICA, contexto_transformacao
    )


# -----------------------------------------------------------------------------
# 3) COPIA METRICA DA SNV E INDICE ESPACIAL
# -----------------------------------------------------------------------------
# Toda a SNV e reprojetada uma unica vez. Reprojetar por consulta produziria
# resultados dependentes do caminho percorrido e custo desnecessario.
tipo_geometria_snv = QgsWkbTypes.displayString(camada_snv.wkbType())
if camada_snv.wkbType() in (QgsWkbTypes.Unknown, QgsWkbTypes.NoGeometry):
    raise Exception("Tipo de geometria da SNV indefinido; nao e possivel copiar a camada.")

snv_metrica = QgsVectorLayer(
    f"{tipo_geometria_snv}?crs={CRS_METRICA.authid()}",
    "snv_metrica_temporaria",
    "memory",
)
if not snv_metrica.isValid():
    raise Exception("Falha ao criar a camada temporaria metrica da SNV.")

provedor_snv = snv_metrica.dataProvider()
provedor_snv.addAttributes(camada_snv.fields())
snv_metrica.updateFields()

feicoes_metricas = []
snv_descartadas_geometria = 0
for feicao in camada_snv.getFeatures():
    geometria = feicao.geometry()
    if geometria is None or geometria.isNull() or geometria.isEmpty():
        snv_descartadas_geometria += 1
        continue

    geometria = QgsGeometry(geometria)
    if transformacao_snv is not None:
        try:
            geometria.transform(transformacao_snv)
        except QgsCsException:
            snv_descartadas_geometria += 1
            continue

    nova_snv = QgsFeature(snv_metrica.fields())
    nova_snv.setGeometry(geometria)
    nova_snv.setAttributes(feicao.attributes())
    feicoes_metricas.append(nova_snv)

if not feicoes_metricas:
    raise Exception(
        "Nenhuma feicao SNV com geometria valida apos a reprojecao; "
        "a associacao resultaria integralmente em SEM_TRECHO."
    )
if not provedor_snv.addFeatures(feicoes_metricas)[0]:
    raise RuntimeError("Falha ao criar a copia metrica da SNV.")
snv_metrica.updateExtents()

indice_snv = QgsSpatialIndex(snv_metrica.getFeatures())
snv_por_id = {feicao.id(): feicao for feicao in snv_metrica.getFeatures()}


# -----------------------------------------------------------------------------
# 4) MEDIANA DAS EXTENSOES VALIDAS
# -----------------------------------------------------------------------------
# A mediana e o piso do raio de busca. Preferida a media por ser robusta a
# OAEs excepcionalmente longas, que de outro modo inflariam o raio de todas.
extensoes_validas = []
for feicao in camada_oae.getFeatures():
    extensao = numero_finito_positivo(feicao[CAMPO_EXTENSAO])
    if extensao is not None:
        extensoes_validas.append(extensao)

if not extensoes_validas:
    raise Exception(
        f'Nenhuma extensao positiva e finita em "{CAMPO_EXTENSAO}"; '
        "nao e possivel calcular a mediana."
    )

mediana_extensao = statistics.median(extensoes_validas)


# -----------------------------------------------------------------------------
# 5) PREPARACAO DOS TRECHOS SNV E CALCULO DO KM
# -----------------------------------------------------------------------------
def preparar_trechos(snv_por_id):
    """Valida, uma unica vez, cada trecho SNV para o calculo do km.

    Parametros:
        snv_por_id: dict fid -> QgsFeature da copia metrica da SNV.

    Retorna:
        dict fid -> {"linha", "ki", "kf", "erro", "alerta_sentido"}
        erro: None quando o trecho e apto; senao a causa que impede o km.
        alerta_sentido: preenchido depois, por diagnosticar_trechos.

    Hipoteses metodologicas:
        - O sentido do km e o sentido de digitalizacao da LineString (ver
          preparar_linha). O km nao depende de trechos vizinhos nem de outros
          atributos: o trecho e autossuficiente. Os vizinhos so sao
          consultados, a parte, para AVISAR de sentido suspeito.
        - O preparo e propriedade do TRECHO, nao da OAE, e por isso ocorre uma
          unica vez, antes do laco das OAEs.

    Excecoes registradas em "erro" (todas resultam em km_SNV nulo):
        INTERVALO_KM_INVALIDO - km ausente, negativo ou vl_km_fina <= vl_km_inic,
            caso em que a interpolacao seria degenerada ou de sinal invertido;
        e as causas de preparar_linha (GEOMETRIA_SNV_AUSENTE,
        GEOMETRIA_SNV_NAO_LINEAR, GEOMETRIA_SNV_MULTIPARTE,
        GEOMETRIA_SNV_COMPRIMENTO_NULO).
    """
    preparados = {}
    for fid, feicao in snv_por_id.items():
        ki = numero_finito(feicao[CAMPO_VL_KM_INIC])
        kf = numero_finito(feicao[CAMPO_VL_KM_FINA])
        linha, erro = None, None
        if ki is None or kf is None or ki < 0 or kf <= ki:
            erro = "INTERVALO_KM_INVALIDO"
        else:
            linha, erro = preparar_linha(feicao.geometry())
        preparados[fid] = {"linha": linha, "ki": ki, "kf": kf, "erro": erro,
                           "alerta_sentido": None}
    return preparados



def diagnosticar_sentido(extremos, anteriores, posteriores):
    """Avalia se a digitalizacao de um trecho contradiz a sequencia de km da SNV.

    Parametros:
        extremos: ((x, y) do primeiro vertice, (x, y) do ultimo vertice).
        anteriores: extremos dos vizinhos cujo vl_km_fina e igual ao vl_km_inic
            do trecho avaliado.
        posteriores: extremos dos vizinhos cujo vl_km_inic e igual ao
            vl_km_fina do trecho avaliado.

    Retorna:
        None quando nao ha erro detectavel, ou um dos avisos:
        "TRECHO_SNV_POSSIVELMENTE_INVERTIDO" - os vizinhos indicam que o km
            cresce no sentido oposto ao da digitalizacao;
        "TRECHO_SNV_CONTINUIDADE_CONTRADITORIA" - anterior e posterior tocam o
            MESMO extremo, o que nenhuma digitalizacao explica.

    Hipoteses metodologicas:
        - E SO DIAGNOSTICO. O km continua sendo calculado pela geometria; o
          aviso apenas registra que a SNV parece incoerente naquele trecho,
          para que seja revisada.
        - Pela digitalizacao, o vizinho anterior deveria tocar o PRIMEIRO
          vertice e o posterior, o ULTIMO. Usa-se apenas o extremo do trecho
          AVALIADO que cada vizinho toca: nada se presume sobre o sentido do
          vizinho, que tambem pode estar invertido.
        - Ausencia de evidencia nao e erro. Sem vizinho, com vizinho tocando os
          dois extremos (anel, retorno) ou com vizinhos do mesmo lado em
          extremos diferentes, aquele lado nao conta. Funcao independente do
          QGIS, para poder ser testada isoladamente.
    """
    def extremo_tocado(vizinhos):
        """Indice (0 ou 1) do extremo tocado pelos vizinhos de um lado, ou None."""
        tocados = set()
        for extremos_vizinho in vizinhos:
            indices = {
                i for i, ponto in enumerate(extremos)
                for ponto_vizinho in extremos_vizinho
                if math.dist(ponto, ponto_vizinho) <= TOLERANCIA_CONEXAO_M
            }
            if len(indices) > 1:
                return None
            tocados |= indices
        return next(iter(tocados)) if len(tocados) == 1 else None

    # True = o vizinho confirma a digitalizacao; False = a contradiz.
    votos = []
    anterior = extremo_tocado(anteriores)
    posterior = extremo_tocado(posteriores)
    if anterior is not None:
        votos.append(anterior == 0)
    if posterior is not None:
        votos.append(posterior == 1)
    if not votos or all(votos):
        return None
    if not any(votos):
        return "TRECHO_SNV_POSSIVELMENTE_INVERTIDO"
    return "TRECHO_SNV_CONTINUIDADE_CONTRADITORIA"


def diagnosticar_trechos(preparados, snv_por_id):
    """Grava em cada trecho apto o aviso de sentido suspeito, se houver.

    Parametros:
        preparados: resultado de preparar_trechos (alterado no lugar).
        snv_por_id: dict fid -> QgsFeature da copia metrica da SNV.

    Hipoteses metodologicas:
        - Vizinhos sao trechos da MESMA BR (prefixo do vl_codigo), com
          vl_codigo diferente, cujo km de emenda coincide ao metro
          (CASAS_DECIMAIS_KM). O prefixo do codigo dispensa exigir vl_br, sg_uf
          e sg_tipo_tr. Uma falsa vizinhanca entre UFs exigiria km iguais ao
          metro e extremos a ate TOLERANCIA_CONEXAO_M, o que e improvavel.
        - Feicoes de mesmo vl_codigo sao particoes do proprio trecho, e nao
          vizinhos capazes de testemunhar seu sentido.
        - So trechos aptos entram, como avaliados e como vizinhos: sem linha de
          parte unica nao ha primeiro e ultimo vertice confiaveis.
    """
    dados = {}
    por_inicio = {}
    por_final = {}
    for fid, registro in preparados.items():
        if registro["erro"] or registro["linha"] is None:
            continue
        vertices = registro["linha"].asPolyline()
        codigo = codigo_valido(snv_por_id[fid][CAMPO_VL_CODIGO])
        rodovia = prefixo_codigo(codigo)
        if len(vertices) < 2 or rodovia is None:
            continue
        extremos = ((vertices[0].x(), vertices[0].y()),
                    (vertices[-1].x(), vertices[-1].y()))
        dados[fid] = (codigo, rodovia, extremos)
        ki = round(registro["ki"], CASAS_DECIMAIS_KM)
        kf = round(registro["kf"], CASAS_DECIMAIS_KM)
        por_inicio.setdefault((rodovia, ki), []).append(fid)
        por_final.setdefault((rodovia, kf), []).append(fid)

    for fid, (codigo, rodovia, extremos) in dados.items():
        registro = preparados[fid]
        ki = round(registro["ki"], CASAS_DECIMAIS_KM)
        kf = round(registro["kf"], CASAS_DECIMAIS_KM)
        anteriores = [dados[f][2] for f in por_final.get((rodovia, ki), [])
                      if dados[f][0] != codigo]
        posteriores = [dados[f][2] for f in por_inicio.get((rodovia, kf), [])
                       if dados[f][0] != codigo]
        registro["alerta_sentido"] = diagnosticar_sentido(
            extremos, anteriores, posteriores)


print("Preparando os trechos SNV...")
snv_preparada = preparar_trechos(snv_por_id)
diagnosticar_trechos(snv_preparada, snv_por_id)
resumo_trechos = Counter(
    registro["erro"] or "APTO_AO_CALCULO_DO_KM" for registro in snv_preparada.values()
)
resumo_alertas_sentido = Counter(
    registro["alerta_sentido"] for registro in snv_preparada.values()
    if registro["alerta_sentido"]
)


def interpolar_km(km_inicial, km_final, fracao):
    """Converte a posicao relativa ao longo do trecho em quilometro.

    Parametros:
        km_inicial, km_final: vl_km_inic e vl_km_fina do trecho.
        fracao: posicao relativa da projecao da OAE ao longo da linha, de 0 (no
            primeiro vertice) a 1 (no ultimo vertice).

    Retorna:
        float - km_inicial + fracao * (km_final - km_inicial).

    Hipoteses metodologicas:
        - O primeiro vertice da LineString e o km inicial, porque o trecho esta
          digitalizado no sentido crescente da rota.
        - A fracao e limitada a [0, 1]: nenhuma OAE recebe km fora do intervalo
          declarado do proprio trecho ao qual foi associada.
    """
    fracao = min(1.0, max(0.0, fracao))
    return km_inicial + fracao * (km_final - km_inicial)


def calcular_km(geometria_oae, linha, km_inicial, km_final):
    """Projeta a OAE sobre o trecho e interpola o quilometro correspondente.

    Parametros:
        geometria_oae: ponto da OAE em CRS_METRICA.
        linha: linha de parte unica do trecho, na ordem de vertices gravada
            (preparar_linha).
        km_inicial, km_final: vl_km_inic e vl_km_fina ja validados
            (finitos, km_inicial >= 0, km_final > km_inicial).

    Retorna:
        dict {"km", "fracao", "comprimento_m", "escala"} ou None quando a
        projecao falhar. "escala" = comprimento geometrico / extensao declarada
        em metros.

    Hipoteses metodologicas:
        1. A OAE e projetada ORTOGONALMENTE sobre o eixo do trecho: adota-se o
           ponto do eixo mais proximo da OAE como sua posicao linear.
        2. A quilometragem varia LINEARMENTE ao longo da geometria. Ela e exata
           quando o comprimento geometrico coincide com a extensao declarada e
           aproximada quando divergem (generalizacao do tracado, km herdado de
           versoes anteriores do SNV). Por isso "escala" e devolvido e
           sinalizado quando o desvio e grande.
        3. O sentido e o da digitalizacao (ver interpolar_km).

    Excecoes:
        Retorna None se o comprimento for nulo/nao finito, se a projecao
        falhar ou se lineLocatePoint devolver posicao negativa (falha do GEOS).
    """
    comprimento = linha.length()
    if not math.isfinite(comprimento) or comprimento <= 0:
        return None

    ponto_projetado = linha.nearestPoint(geometria_oae)
    if ponto_projetado is None or ponto_projetado.isNull() or ponto_projetado.isEmpty():
        return None

    posicao = linha.lineLocatePoint(ponto_projetado)
    if not math.isfinite(posicao) or posicao < 0:
        return None

    fracao = min(1.0, max(0.0, posicao / comprimento))
    extensao_declarada_m = (km_final - km_inicial) * 1000.0
    return {
        "km": interpolar_km(km_inicial, km_final, fracao),
        "fracao": fracao,
        "comprimento_m": comprimento,
        "escala": comprimento / extensao_declarada_m if extensao_declarada_m > 0 else None,
    }


# -----------------------------------------------------------------------------
# 6) CAMADA DE SAIDA
# -----------------------------------------------------------------------------
tipo_geometria_saida = QgsWkbTypes.displayString(camada_oae.wkbType())
if camada_oae.wkbType() in (QgsWkbTypes.Unknown, QgsWkbTypes.NoGeometry):
    raise Exception("Tipo de geometria da OAE indefinido; nao e possivel criar a saida.")

# A saida permanece no SRC ORIGINAL da OAE: o SRC metrico e instrumento de
# medicao, nao formato de entrega.
saida = QgsVectorLayer(
    f"{tipo_geometria_saida}?crs={camada_oae.crs().authid()}",
    NOME_CAMADA_SAIDA,
    "memory",
)
if not saida.isValid():
    raise Exception("Falha ao criar a camada de saida em memoria.")

provedor_saida = saida.dataProvider()
provedor_saida.addAttributes(camada_oae.fields())


def comprimento_origem(nome_campo):
    """Comprimento declarado de um campo de texto da SNV, para replica-lo na saida.

    Retorna o comprimento do campo de origem, ou TAMANHO_MAX_OBS quando o
    provedor nao o informa (comprimento 0 ou negativo, comum em GeoPackage).
    Replicar o comprimento evita truncar na saida um valor que a propria SNV
    comporta.
    """
    comprimento = camada_snv.fields().field(nome_campo).length()
    return comprimento if comprimento and comprimento > 0 else TAMANHO_MAX_OBS


TAMANHO_ADMINISTRACAO = comprimento_origem(CAMPO_ADMIN_SNV)
TAMANHO_JURISDICAO = comprimento_origem(CAMPO_JURIS_SNV)

provedor_saida.addAttributes(
    [
        # Ordem definida pelo responsavel: primeiro o resultado (trecho, seus
        # atributos, km, coincidencia, validacao, criterio e observacao), depois
        # os dados de apoio a conferencia.
        QgsField(CAMPO_TRECHO_SNV, QVariant.String, len=80),
        QgsField(CAMPO_ADMINISTRACAO, QVariant.String, len=TAMANHO_ADMINISTRACAO),
        QgsField(CAMPO_JURISDICAO, QVariant.String, len=TAMANHO_JURISDICAO),
        QgsField(CAMPO_KM_SNV, QVariant.Double, len=20, prec=3),
        QgsField(CAMPO_RODOVIAS_COINC, QVariant.String, len=TAMANHO_MAX_RODOVIAS),
        QgsField(CAMPO_STATUS, QVariant.String, len=20),
        QgsField(CAMPO_CRITERIO, QVariant.String, len=30),
        QgsField(CAMPO_OBSERVACAO, QVariant.String, len=TAMANHO_MAX_OBS),
        QgsField(CAMPO_DIST_SNV, QVariant.Double, len=20, prec=3),
        QgsField(CAMPO_RAIO_SNV, QVariant.Double, len=20, prec=3),
        QgsField(CAMPO_QTD_CODIGOS, QVariant.Int),
    ]
)
saida.updateFields()

idx_trecho = saida.fields().indexOf(CAMPO_TRECHO_SNV)
idx_administracao = saida.fields().indexOf(CAMPO_ADMINISTRACAO)
idx_jurisdicao = saida.fields().indexOf(CAMPO_JURISDICAO)
idx_km = saida.fields().indexOf(CAMPO_KM_SNV)
idx_dist = saida.fields().indexOf(CAMPO_DIST_SNV)
idx_raio = saida.fields().indexOf(CAMPO_RAIO_SNV)
idx_qtd = saida.fields().indexOf(CAMPO_QTD_CODIGOS)
idx_rodovias_coinc = saida.fields().indexOf(CAMPO_RODOVIAS_COINC)
idx_status = saida.fields().indexOf(CAMPO_STATUS)
idx_criterio = saida.fields().indexOf(CAMPO_CRITERIO)
idx_observacao = saida.fields().indexOf(CAMPO_OBSERVACAO)

# Derivado dos campos efetivamente criados, e nao de uma constante literal,
# para que a inclusao de novos campos de auditoria nao quebre a montagem.
QTD_CAMPOS_NOVOS = saida.fields().count() - camada_oae.fields().count()
if QTD_CAMPOS_NOVOS != len(campos_novos):
    raise RuntimeError("Estrutura da camada de saida divergente da esperada.")

contagem = {criterio: 0 for criterio in CRITERIOS_VALIDOS}
contagem.update(
    {
        "TOTAL": 0,
        "KM_CALCULADO": 0,
        "KM_NAO_DETERMINADO": 0,
        "VIA_NAO_NORMALIZAVEL": 0,
        "ALERTA_ESCALA": 0,
        "ALERTA_EXTREMO": 0,
        "COINCIDENCIA_DETECTADA": 0,
        "COINCIDENCIA_MESMA_BR": 0,
        "ATRIBUTO_TRECHO_DIVERGENTE": 0,
        "KM_EM_TRECHO_SUSPEITO": 0,
    }
)

novas_feicoes = []
contagem_status = Counter()
motivos_km_nulo = Counter()
motivos_sem_associacao = Counter()


# -----------------------------------------------------------------------------
# 7) PROCESSAMENTO DAS OAEs
# -----------------------------------------------------------------------------
for oae in camada_oae.getFeatures():
    contagem["TOTAL"] += 1

    # Raio proporcional ao porte da obra, com piso na mediana: uma OAE longa
    # pode estar legitimamente afastada do eixo lancado no SNV, enquanto uma
    # OAE sem extensao declarada nao pode ficar sem janela de busca.
    extensao = numero_finito_positivo(oae[CAMPO_EXTENSAO])
    base_raio = max(extensao, mediana_extensao) if extensao is not None else mediana_extensao
    raio_procura = base_raio * FATOR_RAIO

    via = normalizar_via(oae[CAMPO_VIA])
    if via is None:
        contagem["VIA_NAO_NORMALIZAVEL"] += 1

    nova = QgsFeature(saida.fields())
    nova.setGeometry(QgsGeometry(oae.geometry()))
    nova.setAttributes(oae.attributes() + [None] * QTD_CAMPOS_NOVOS)
    nova.setAttribute(idx_raio, raio_procura)

    geom_oae_metrica = geometria_pontual_metrica(oae, transformacao_oae)
    if geom_oae_metrica is None:
        criterio = "SEM_TRECHO"
        nova.setAttribute(idx_qtd, 0)
        nova.setAttribute(idx_criterio, criterio)
        nova.setAttribute(idx_status, status_validacao(criterio, oae[CAMPO_RELACAO_SNV], 0))
        nova.setAttribute(idx_observacao, "GEOMETRIA_OAE_INVALIDA_OU_MULTIPONTO")
        contagem[criterio] += 1
        contagem_status[STATUS_A_VALIDAR] += 1
        motivos_sem_associacao["SEM_TRECHO:GEOMETRIA_OAE_INVALIDA_OU_MULTIPONTO"] += 1
        novas_feicoes.append(nova)
        continue

    ponto_oae = QgsPointXY(geom_oae_metrica.asPoint())
    ids_no_retangulo = indice_snv.intersects(
        retangulo_centrado(ponto_oae, raio_procura)
    )

    # Agrupamento por codigo DISTINTO. A distancia de um codigo e a menor
    # distancia real entre a OAE e qualquer geometria portadora desse codigo.
    por_codigo = {}
    feicoes_sem_codigo_no_raio = 0
    feicoes_alem_do_limite = 0

    for fid in ids_no_retangulo:
        trecho = snv_por_id.get(fid)
        if trecho is None:
            continue

        # O indice devolve candidatos por envelope; a distancia real e o
        # criterio efetivo de admissao no conjunto de candidatos.
        geometria_trecho = trecho.geometry()
        distancia = geometria_trecho.distance(geom_oae_metrica)
        if not math.isfinite(distancia) or distancia < 0 or distancia > raio_procura:
            continue
        if (DISTANCIA_MAXIMA_ASSOCIACAO_M is not None
                and distancia > DISTANCIA_MAXIMA_ASSOCIACAO_M):
            feicoes_alem_do_limite += 1
            continue

        codigo = codigo_valido(trecho[CAMPO_VL_CODIGO])
        if codigo is None:
            feicoes_sem_codigo_no_raio += 1
            continue

        registro = por_codigo.setdefault(codigo, {"feicoes": []})
        registro["feicoes"].append((fid, distancia))

    # O minimo e os empates sao calculados sobre o conjunto COMPLETO de
    # candidatos, o que elimina qualquer dependencia da ordem de leitura para
    # distancias iguais dentro da tolerancia.
    for registro in por_codigo.values():
        registro["distancia"] = min(d for _, d in registro["feicoes"])
        registro["feicoes_mais_proximas"] = [
            (fid, d) for fid, d in registro.pop("feicoes")
            if quase_igual(d, registro["distancia"], TOLERANCIA_EMPATE_DISTANCIA_M)
        ]

    qtd_codigos = len(por_codigo)
    nova.setAttribute(idx_qtd, qtd_codigos)

    codigo_escolhido, criterio, causa, rodovias_coinc, observacao = selecionar_codigo(
        por_codigo, via, snv_por_id, geom_oae_metrica
    )
    nova.setAttribute(idx_rodovias_coinc,
                      truncar_texto(rodovias_coinc, TAMANHO_MAX_RODOVIAS))
    if rodovias_coinc:
        contagem["COINCIDENCIA_DETECTADA"] += 1
        if ";" not in rodovias_coinc:
            contagem["COINCIDENCIA_MESMA_BR"] += 1
    if qtd_codigos == 0:
        observacao = observacao_texto(
            observacao,
            f"FEICOES_SNV_SEM_CODIGO_NO_RAIO={feicoes_sem_codigo_no_raio}"
            if feicoes_sem_codigo_no_raio else None,
            f"FEICOES_ALEM_DA_DISTANCIA_MAXIMA={feicoes_alem_do_limite}"
            if feicoes_alem_do_limite else None,
            "N_CODIGOS=0",
            f"RAIO_M={raio_procura:.3f}",
        )
    if criterio not in CRITERIOS_VALIDOS:
        raise RuntimeError(f"Criterio interno invalido: {criterio}")

    # Pos-condicao verificada em execucao. Com a compatibilidade de Via
    # promovida a pre-condicao universal, os TRES criterios que devolvem codigo
    # ficam sujeitos a mesma invariante: o codigo atribuido pertence a Via
    # declarada e esta na distancia minima entre os compativeis. Falhar aqui
    # indica defeito de implementacao, nao dado ruim - por isso interrompe.
    if criterio in ("UNICO_TRECHO", "TRECHO_COINCIDENTE", "TRECHO_FRONTEIRA"):
        distancias_compativeis = [
            r["distancia"] for c, r in por_codigo.items() if prefixo_codigo(c) == via
        ]
        if (via is None
                or not distancias_compativeis
                or codigo_escolhido is None
                or prefixo_codigo(codigo_escolhido) != via
                or not quase_igual(
                    por_codigo[codigo_escolhido]["distancia"],
                    min(distancias_compativeis),
                    TOLERANCIA_EMPATE_DISTANCIA_M)):
            raise RuntimeError("Selecao violou compatibilidade da Via ou menor distancia.")

    nova.setAttribute(idx_criterio, criterio)
    contagem[criterio] += 1
    # Status depende so do criterio, de Relacao_SNV e de Qtd_Codigos, todos ja
    # definidos aqui; o calculo do km, mais adiante, nao o altera.
    status = status_validacao(criterio, oae[CAMPO_RELACAO_SNV], qtd_codigos)
    nova.setAttribute(idx_status, status)
    contagem_status[status] += 1

    if codigo_escolhido is None:
        nova.setAttribute(idx_observacao, observacao)
        # Contabiliza a CAUSA, nao apenas o criterio: TRECHO_DIVERGENTE reune
        # tres situacoes distintas (Via ausente, unico codigo incompativel e
        # nenhum compativel entre varios), que precisam ser dimensionadas
        # separadamente para orientar o saneamento do dado de origem.
        motivos_sem_associacao[f"{criterio}:{causa or 'NAO_INFORMADA'}"] += 1
        novas_feicoes.append(nova)
        continue

    distancia_escolhida = por_codigo[codigo_escolhido]["distancia"]
    feicoes_mais_proximas = por_codigo[codigo_escolhido]["feicoes_mais_proximas"]
    nova.setAttribute(idx_trecho, codigo_escolhido)
    nova.setAttribute(idx_dist, round(distancia_escolhida, 3))

    # Administracao e Jurisdicao descrevem o TRECHO atribuido e sao lidas aqui,
    # junto do Trecho_SNV, e nao da feicao usada no km: o calculo do km pode
    # sair antecipadamente (empate entre geometrias, sentido indeterminado), e
    # a OAE ficaria com trecho atribuido mas sem esses atributos.
    for idx_destino, campo_origem, tamanho, marcador in (
        (idx_administracao, CAMPO_ADMIN_SNV, TAMANHO_ADMINISTRACAO,
         "ADMINISTRACAO_DIVERGENTE_ENTRE_GEOMETRIAS"),
        (idx_jurisdicao, CAMPO_JURIS_SNV, TAMANHO_JURISDICAO,
         "JURISDICAO_DIVERGENTE_ENTRE_GEOMETRIAS"),
    ):
        valor, divergente = valor_unanime(
            snv_por_id[fid][campo_origem] for fid, _ in feicoes_mais_proximas
        )
        nova.setAttribute(idx_destino, truncar_texto(valor, tamanho))
        if divergente:
            observacao = observacao_texto(marcador, observacao)
            contagem["ATRIBUTO_TRECHO_DIVERGENTE"] += 1

    # O codigo pode estar em mais de uma feicao. A geometria usada para
    # projetar a OAE precisa ser univoca pela menor distancia; empate entre
    # geometrias do mesmo codigo nao recebe desempate, pois escolher qualquer
    # uma delas arbitraria a posicao linear e, portanto, o proprio km.
    if len(feicoes_mais_proximas) != 1:
        nova.setAttribute(idx_observacao, observacao_texto(
            "EMPATE_DE_GEOMETRIAS_DO_MESMO_CODIGO",
            f"N_GEOMETRIAS={len(feicoes_mais_proximas)}",
            observacao))
        contagem["KM_NAO_DETERMINADO"] += 1
        motivos_km_nulo["EMPATE_DE_GEOMETRIAS_DO_MESMO_CODIGO"] += 1
        novas_feicoes.append(nova)
        continue

    fid_escolhido = feicoes_mais_proximas[0][0]
    preparo = snv_preparada[fid_escolhido]
    linha = preparo["linha"]

    # Trecho recusado no preparo (intervalo de km invalido ou geometria que nao
    # e uma linha de parte unica): o km nao pode ser calculado. A guarda sobre
    # linha e km cobre ainda uma eventual alteracao futura de preparar_trechos.
    if preparo["erro"] or linha is None or preparo["ki"] is None or preparo["kf"] is None:
        causa = preparo["erro"] or "PREPARO_DO_TRECHO_INCOMPLETO"
        nova.setAttribute(idx_observacao, observacao_texto(causa, observacao))
        contagem["KM_NAO_DETERMINADO"] += 1
        motivos_km_nulo[causa] += 1
        novas_feicoes.append(nova)
        continue

    # Aviso de sentido suspeito do trecho (diagnosticar_trechos). So entra na
    # observacao: o km abaixo e calculado pela geometria, com ou sem aviso, e
    # permanece coerente com o trecho tal como esta publicado na SNV.
    alerta_sentido = preparo["alerta_sentido"]

    resultado_km = calcular_km(
        geom_oae_metrica,
        linha,
        preparo["ki"],
        preparo["kf"],
    )
    if resultado_km is None:
        nova.setAttribute(idx_observacao, observacao_texto(
            alerta_sentido, "FALHA_NA_PROJECAO_OU_INTERPOLACAO", observacao))
        contagem["KM_NAO_DETERMINADO"] += 1
        motivos_km_nulo["FALHA_NA_PROJECAO_OU_INTERPOLACAO"] += 1
        novas_feicoes.append(nova)
        continue

    # Alerta de auditoria, nao criterio: sinaliza os km cuja hipotese de
    # proporcionalidade entre geometria e quilometragem esta enfraquecida.
    escala = resultado_km["escala"]
    alerta_escala = None
    if escala is not None and abs(escala - 1.0) > TOLERANCIA_ESCALA_KM_GEOM:
        alerta_escala = f"ALERTA_ESCALA_KM_GEOM={escala:.3f}"
        contagem["ALERTA_ESCALA"] += 1

    # Segundo alerta de auditoria, tambem sem efeito sobre o valor calculado:
    # a projecao caindo exatamente sobre um extremo indica que a OAE esta no
    # limite do trecho - frequentemente porque pertence ao trecho vizinho - e
    # que o km resultante e o proprio limite declarado, e nao uma posicao
    # interpolada com evidencia propria.
    fracao = resultado_km["fracao"]
    alerta_extremo = None
    if fracao <= 0.0:
        alerta_extremo = "PROJECAO_NO_EXTREMO=INICIO_GEOM"
    elif fracao >= 1.0:
        alerta_extremo = "PROJECAO_NO_EXTREMO=FIM_GEOM"
    if alerta_extremo:
        contagem["ALERTA_EXTREMO"] += 1

    if alerta_sentido:
        contagem["KM_EM_TRECHO_SUSPEITO"] += 1

    nova.setAttribute(idx_km, round(resultado_km["km"], 3))
    nova.setAttribute(idx_observacao, observacao_texto(
        alerta_sentido,
        alerta_escala,
        alerta_extremo,
        f"FRACAO={resultado_km['fracao']:.6f}",
        observacao,
    ))
    contagem["KM_CALCULADO"] += 1
    novas_feicoes.append(nova)


# Conversao dos codigos internos em texto legivel, num unico ponto, depois de
# toda a logica e de todos os contadores terem usado os codigos.
for nova in novas_feicoes:
    nova.setAttribute(idx_criterio, texto_saida_criterio(nova[idx_criterio]))
    nova.setAttribute(idx_observacao, texto_saida_obs(nova[idx_observacao]))

if not provedor_saida.addFeatures(novas_feicoes)[0] or saida.featureCount() != contagem["TOTAL"]:
    raise RuntimeError("Falha na gravacao das OAEs na camada de saida.")
saida.updateExtents()
projeto.addMapLayer(saida)


# -----------------------------------------------------------------------------
# 8) RESUMOS E CONFERENCIA DAS SOMAS
# -----------------------------------------------------------------------------
# As somatorias sao verificadas antes da impressao: um resumo que nao fecha
# indicaria caminho de execucao nao contabilizado e invalidaria a auditoria.
associadas = (
    contagem["UNICO_TRECHO"]
    + contagem["TRECHO_COINCIDENTE"]
    + contagem["TRECHO_FRONTEIRA"]
)
sem_associacao = contagem["TOTAL"] - associadas
soma_grupos = sum(contagem[criterio] for criterio in CRITERIOS_VALIDOS)
soma_km = contagem["KM_CALCULADO"] + contagem["KM_NAO_DETERMINADO"]
if (
    soma_grupos != contagem["TOTAL"] or soma_km != associadas
    or sum(motivos_km_nulo.values()) != contagem["KM_NAO_DETERMINADO"]
    or sum(motivos_sem_associacao.values()) != sem_associacao
    or sum(contagem_status.values()) != contagem["TOTAL"]
):
    raise RuntimeError("Inconsistencia nas somatorias dos resumos.")

print("=" * 72)
print("RESUMO - Associacao OAEs x SNV")
print("=" * 72)
for criterio in CRITERIOS_VALIDOS:
    print(f"{criterio + ':':38} {contagem[criterio]}")
print(f"Soma dos seis grupos:                  {soma_grupos}")
print(f"Total de OAEs:                         {contagem['TOTAL']}")
print(f"Associadas a um codigo SNV:            {associadas}")
print(f"Sem codigo SNV atribuido:              {sem_associacao}")
print(f"Conferencia: {associadas} + {sem_associacao} = {contagem['TOTAL']}")
print(f"Status {STATUS_VALIDADO}:                     {contagem_status[STATUS_VALIDADO]}")
print(f"Status {STATUS_A_VALIDAR}:                    {contagem_status[STATUS_A_VALIDAR]}")
print("Causas da nao associacao (criterio : causa):")
for motivo, quantidade in sorted(motivos_sem_associacao.items()):
    criterio_motivo, _, causa_motivo = motivo.partition(":")
    print(f"  {criterio_motivo:20} {causa_motivo:48} {quantidade}")
print(f"OAEs com Via ausente/nao normalizavel: {contagem['VIA_NAO_NORMALIZAVEL']}")
print(f"Mediana das extensoes validas:         {mediana_extensao:.3f} m")
print(f"Feicoes SNV sem geometria/reprojecao:  {snv_descartadas_geometria}")
# Conta OCORRENCIAS: uma OAE pode divergir nos dois atributos ao mesmo tempo.
print(f"Administracao/Jurisdicao divergentes:  {contagem['ATRIBUTO_TRECHO_DIVERGENTE']}"
      " ocorrencias (geometrias empatadas do mesmo codigo)")
print(f"Camada criada:                         {NOME_CAMADA_SAIDA}")
print()
print("=" * 72)
print("RESUMO - Calculo do quilometro")
print("=" * 72)
print(f"OAEs com trecho atribuido:             {associadas}")
print(f"km_SNV calculado:                      {contagem['KM_CALCULADO']}")
print(f"km_SNV nao calculado (com trecho):     {contagem['KM_NAO_DETERMINADO']}")
for motivo, quantidade in sorted(motivos_km_nulo.items()):
    print(f"  {motivo}: {quantidade}")
print(f"Soma calculado + nao calculado:        {soma_km}")
print(f"km_SNV nao aplicavel (sem trecho):     {sem_associacao}")
print(f"Conferencia geral: {soma_km} + {sem_associacao} = {contagem['TOTAL']}")
print(f"km com alerta de escala (>{TOLERANCIA_ESCALA_KM_GEOM:.0%}):     {contagem['ALERTA_ESCALA']}")
print(f"km com projecao no extremo do trecho:  {contagem['ALERTA_EXTREMO']}")
print(f"km em trecho SNV com sentido suspeito: {contagem['KM_EM_TRECHO_SUSPEITO']}"
      " (calculado pela geometria; ver Obs_SNV)")
print("=" * 72)
print()
print("RESUMO - OAEs sobre rodovias coincidentes")
print("=" * 72)
print(f"OAEs com coincidencia detectada:       {contagem['COINCIDENCIA_DETECTADA']}")
print(f"  em TRECHO_COINCIDENTE:               {contagem['TRECHO_COINCIDENTE']}")
print(f"  em TRECHO_EMPATE (nao associadas):   "
      f"{contagem['COINCIDENCIA_DETECTADA'] - contagem['TRECHO_COINCIDENTE']}")
# Sobreposicao entre codigos distintos da mesma BR e geometria duplicada no SNV,
# nao coincidencia entre rodovias: nao integra o levantamento pretendido.
print(f"  entre codigos da MESMA BR (anomalia):{contagem['COINCIDENCIA_MESMA_BR']}")
print("=" * 72)
print()
print("SITUACAO DOS TRECHOS SNV PARA O CALCULO DO KM (NAO OAEs)")
print(f"  APTO_AO_CALCULO_DO_KM: {resumo_trechos['APTO_AO_CALCULO_DO_KM']}")
for situacao in sorted(set(resumo_trechos) - {"APTO_AO_CALCULO_DO_KM"}):
    print(f"  {situacao}: {resumo_trechos[situacao]}")
print(f"Total de feicoes SNV avaliadas: {sum(resumo_trechos.values())}")
print("  Avisos de sentido (so diagnostico, o km nao e alterado):")
for alerta in ("TRECHO_SNV_POSSIVELMENTE_INVERTIDO",
               "TRECHO_SNV_CONTINUIDADE_CONTRADITORIA"):
    print(f"    {alerta}: {resumo_alertas_sentido[alerta]}")
print(f"SNV excluidas por geometria/reprojecao: {snv_descartadas_geometria}")
print()
print("PARAMETROS DESTA EXECUCAO")
print(f"  CRS metrico:                     {CRS_METRICA.authid()}")
print(f"  FATOR_RAIO:                      {FATOR_RAIO}")
print(f"  TOLERANCIA_EMPATE_DISTANCIA_M:   {TOLERANCIA_EMPATE_DISTANCIA_M}")
print(f"  DISTANCIA_MAXIMA_ASSOCIACAO_M:   {DISTANCIA_MAXIMA_ASSOCIACAO_M}")
print("  VIA_COMPATIVEL:                  pre-condicao universal (obrigatoria)")
print("  SENTIDO_DO_KM:                   ordem de digitalizacao da LineString SNV")
