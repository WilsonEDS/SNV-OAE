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
#             "vl_km_fina", respeitando o sentido crescente da quilometragem.
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
#
#   Camada SNV (linear), nome em NOME_CAMADA_SNV:
#       - CAMPO_VL_CODIGO   ("vl_codigo")  : codigo do trecho (ex.: 116BMG0450).
#       - CAMPO_VL_KM_INIC  ("vl_km_inic") : km inicial do trecho.
#       - CAMPO_VL_KM_FINA  ("vl_km_fina") : km final do trecho.
#       - CAMPO_BR_SNV      ("vl_br")      : numero da BR.
#       - CAMPO_UF_SNV      ("sg_uf")      : UF.
#       - CAMPO_TIPO_SNV    ("sg_tipo_tr") : tipo do trecho.
#         (vl_br + sg_uf + sg_tipo_tr formam a "chave de continuidade": somente
#          trechos com a mesma chave sao considerados vizinhos entre si.)
#
#
# 3. DADOS DE SAIDA
# -----------------------------------------------------------------------------
#   Camada em memoria NOME_CAMADA_SAIDA, com todos os campos originais da OAE
#   mais os campos de resultado e auditoria:
#
#       Trecho_SNV  (texto)  codigo vl_codigo selecionado, ou NULL.
#       km_SNV      (real)   quilometro interpolado, ou NULL.
#       Dist_SNV_m  (real)   distancia planimetrica, em metros, entre a OAE e a
#                            geometria do codigo selecionado (evidencia direta
#                            da qualidade da associacao). NULL se nao associada.
#       Raio_SNV    (real)   raio de busca aplicado aquela OAE, em metros.
#       Rodovias_coincidentes (texto) numeros de BR (tres digitos) de TODOS os
#                            vl_codigo dentro do raio, sem repeticao, ordenados
#                            da rodovia mais proxima da OAE para a mais
#                            distante e separados por ";" (ex.: "116;101").
#                            Descreve o ENTORNO da OAE. ATENCAO: nao confundir
#                            com o criterio TRECHO_COINCIDENTE - aqui basta a
#                            rodovia estar no raio, ao passo que o criterio
#                            exige sobreposicao linear comprovada. A quantidade
#                            de codigos distintos consta de Obs_SNV (N_CODIGOS).
#       Criterio    (texto)  um dos seis criterios da secao 5.
#       Sentido_KM  (texto)  INICIO_GEOM_KM_INIC | INICIO_GEOM_KM_FINAL |
#                            NAO_DETERMINADO | NAO_APLICAVEL.
#       Obs_SNV     (texto)  trilha de auditoria: distancias, margens, codigos
#                            concorrentes, causas de empate, causas de nao
#                            associacao e causas de km indeterminado.
#
#   Alem da camada, o script imprime tres resumos conferidos por somatorias
#   (associacao, quilometragem e diagnostico de sentido da SNV).
#
#
# 4. PRINCIPAIS PARAMETROS
# -----------------------------------------------------------------------------
#   CRS_METRICA                 : SRC metrico usado em TODAS as medicoes.
#   FATOR_RAIO                  : multiplicador do raio de busca.
#   TOLERANCIA_CONEXAO_M        : distancia maxima entre extremos para que dois
#                                 trechos sejam considerados conectados.
#   TOLERANCIA_CONTINUIDADE_KM  : tolerancia numerica na comparacao de km.
#   TOLERANCIA_EMPATE_DISTANCIA_M : tolerancia numerica de equidistancia.
#   DISTANCIA_MAXIMA_ASSOCIACAO_M : limite duro opcional de associacao (None =
#                                 desativado; ver secao "PARAMETROS EM AVALIACAO").
#
#
# 5. FLUXO METODOLOGICO E CRITERIOS DE CLASSIFICACAO
# -----------------------------------------------------------------------------
#   (a) Reprojeta SNV e OAE para CRS_METRICA; indexa a SNV espacialmente.
#   (b) Orienta previamente TODA a SNV (uma vez, antes das OAEs), por
#       continuidade geometrica + continuidade quilometrica entre vizinhos de
#       mesma chave (vl_br, sg_uf, sg_tipo_tr).
#   (c) Para cada OAE:
#       c1. raio = max(extensao_da_OAE, mediana_das_extensoes) * FATOR_RAIO.
#           A mediana e o piso do raio; ela protege OAEs com extensao ausente,
#           nula ou negativa, sem inflar o raio das demais.
#       c2. Coleta as feicoes SNV cuja distancia real <= raio e agrupa por
#           vl_codigo distinto. A distancia de um CODIGO e a MENOR distancia
#           entre a OAE e qualquer feicao portadora daquele codigo.
#       c3. Seleciona um unico codigo e classifica (ver abaixo).
#       c4. Se ha codigo, projeta a OAE sobre a geometria escolhida e interpola
#           o km entre vl_km_inic e vl_km_fina segundo o sentido.
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
#   Determinacao do sentido (por trecho SNV, nao por OAE):
#     ANTERIOR  : existe trecho vizinho com vl_km_fina ~= vl_km_inic do trecho,
#                 conectado a um de seus extremos -> aquele extremo e o km
#                 inicial.
#     POSTERIOR : existe trecho vizinho com vl_km_inic ~= vl_km_fina do trecho,
#                 conectado a um de seus extremos -> aquele extremo e o km
#                 final.
#     AMBOS     : as duas evidencias existem e apontam extremos opostos.
#     Sem evidencia unica e nao contraditoria, o sentido fica NAO_DETERMINADO e
#     o km_SNV nao e calculado (nunca arbitrado).
#
#
# 6. GARANTIAS DE DETERMINISMO
# -----------------------------------------------------------------------------
#   - Distancias por codigo sao reduzidas por min() sobre o conjunto COMPLETO
#     de feicoes candidatas, nunca pela primeira lida.
#   - Toda decisao exige cardinalidade 1; qualquer empate vira classe propria
#     (TRECHO_EMPATE) ou km indeterminado. Nao ha desempate por ordem.
#   - Ordenacoes existentes (bisect, sorted) servem a consulta e a impressao,
#     nunca a selecao.
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
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict

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
NOME_CAMADA_SAIDA = "SGExSNV_trecho-km"

CAMPO_EXTENSAO = "Extensão (m)"
CAMPO_VIA = "Via"

CAMPO_VL_CODIGO = "vl_codigo"
CAMPO_VL_KM_INIC = "vl_km_inic"
CAMPO_VL_KM_FINA = "vl_km_fina"
CAMPO_BR_SNV = "vl_br"
CAMPO_UF_SNV = "sg_uf"
CAMPO_TIPO_SNV = "sg_tipo_tr"

CAMPO_TRECHO_SNV = "Trecho_SNV"
CAMPO_KM_SNV = "km_SNV"
CAMPO_DIST_SNV = "Dist_SNV_m"
CAMPO_RAIO_SNV = "Raio_SNV"
CAMPO_RODOVIAS = "Rodovias_coincidentes"
CAMPO_CRITERIO = "Criterio"
CAMPO_SENTIDO_KM = "Sentido_KM"
CAMPO_OBSERVACAO = "Obs_SNV"

# Todas as medicoes (distancia, comprimento, projecao) ocorrem neste SRC.
# EPSG:5880 (SIRGAS 2000 / Brazil Polyconic) cobre o territorio nacional em
# metros; medir em graus produziria distancias e raios sem significado fisico.
CRS_METRICA = QgsCoordinateReferenceSystem("EPSG:5880")

# O raio de busca e proporcional ao porte da OAE. Nao e um criterio de
# validade: e apenas a janela de coleta de candidatos.
FATOR_RAIO = 2.0

# A publicacao auditada apresentou as mesmas conexoes entre 1 e 20 metros.
# Um metro basta; nao ampliar automaticamente para buscar vizinhos ausentes.
TOLERANCIA_CONEXAO_M = 1.0
# Somente tolerancia numerica: nao ligar intervalos separados por lacunas de km.
TOLERANCIA_CONTINUIDADE_KM = 1e-8
TOLERANCIA_EMPATE_DISTANCIA_M = 1e-8
# Extremos separados por menos do que isto sao indistinguiveis por qualquer
# tolerancia de conexao praticada; a linha e tratada como fechada.
TOLERANCIA_GEOMETRIA_FECHADA_M = 1e-6

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
# Mesmo limite conservador para Rodovias_coincidentes. Trinta e poucas rodovias
# num unico raio e inconcebivel, mas o campo e truncado de forma explicita pelo
# mesmo motivo que Obs_SNV: texto acima do comprimento declarado se perde sem
# aviso no provedor.
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
        (ki >= 0 e kf > ki) e feita adiante, em preparar_sentidos.
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
        sinalizado com o marcador [TRUNCADO], de modo que a perda seja sempre
        visivel no proprio dado.
    """
    if not texto:
        return None
    if len(texto) <= limite:
        return texto
    marcador = "...[TRUNCADO]"
    return texto[: limite - len(marcador)] + marcador


def observacao_texto(*partes):
    """Concatena fragmentos nao vazios da trilha de rastreabilidade.

    Retorna:
        str com os fragmentos separados por "; ", limitada a TAMANHO_MAX_OBS, ou
        None se nada houver a registrar.

    Hipotese metodologica:
        Os fragmentos sao passados em ordem decrescente de relevancia
        (causa da decisao primeiro, detalhes numericos depois), de modo que um
        eventual truncamento preserve sempre a informacao essencial e o registre
        de forma visivel com o marcador [TRUNCADO].
    """
    return truncar_texto("; ".join(parte for parte in partes if parte),
                         TAMANHO_MAX_OBS)


def rodovias_por_proximidade(por_codigo):
    """Lista as rodovias presentes no raio de busca, da mais proxima a mais distante.

    Parametros:
        por_codigo: dict vl_codigo -> {"distancia": float, ...}, contendo todos
            os codigos distintos dentro do raio, ja reduzidos a menor distancia.

    Retorna:
        (texto, quantidade_sem_prefixo_valido)
        texto: numeros de BR de tres digitos separados por ";" (ex.: "116;101"),
            ou None quando nenhuma rodovia puder ser identificada.

    Hipoteses metodologicas:
        - Descreve o ENTORNO da OAE, nao o resultado da selecao: entram todos os
          codigos do raio, independentemente da distancia, da compatibilidade
          com a Via ou de terem vencido a associacao.
        - Cada BR aparece UMA vez. Varios trechos da mesma rodovia no raio sao
          um fato sobre o seccionamento do SNV, nao sobre quantas rodovias
          existem ali. A contagem de codigos distintos, que a deduplicacao
          esconde, permanece registrada em Obs_SNV como N_CODIGOS=.
        - A distancia de uma BR e a MENOR entre os codigos que a possuem, o que
          mantem a ordenacao coerente com o criterio de selecao.
        - A ordenacao e por proximidade, e nao alfabetica, porque a posicao na
          lista passa a carregar informacao: o primeiro item e a rodovia mais
          proxima da OAE e, nas OAEs associadas, normalmente a atribuida.
        - Empate de distancia entre BRs distintas e desfeito pelo numero
          crescente. Sem esse desempate o texto dependeria da ordem de leitura
          das feicoes, quebrando o determinismo garantido no restante do
          procedimento.

    Excecoes:
        Codigo cujos tres primeiros caracteres nao sejam digitos nao produz
        numero de rodovia e e OMITIDO da lista, para que o campo permaneca
        estritamente numerico e filtravel. A quantidade de omitidos e devolvida
        para registro em Obs_SNV, de modo que a anomalia nao desapareca.

    Atencao:
        O nome do campo de destino evoca TRECHO_COINCIDENTE, mas o conteudo NAO
        e esse: aqui basta a rodovia estar no raio de busca. TRECHO_COINCIDENTE
        exige sobreposicao linear comprovada na posicao de menor distancia.
    """
    menor_por_rodovia = {}
    sem_prefixo_valido = 0
    for codigo, registro in por_codigo.items():
        rodovia = prefixo_codigo(codigo)
        if rodovia is None:
            sem_prefixo_valido += 1
            continue
        distancia = registro["distancia"]
        if rodovia not in menor_por_rodovia or distancia < menor_por_rodovia[rodovia]:
            menor_por_rodovia[rodovia] = distancia

    ordenadas = sorted(menor_por_rodovia, key=lambda r: (menor_por_rodovia[r], r))
    return (";".join(ordenadas) or None), sem_prefixo_valido


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
        (codigo_ou_None, criterio, causa, observacao_de_auditoria)
        "causa" e um token curto que identifica o motivo da NAO associacao;
        vale None quando um codigo e efetivamente atribuido.

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
        return None, "SEM_TRECHO", "SEM_CANDIDATO_NO_RAIO", None

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
            return None, "TRECHO_DIVERGENTE", causa, observacao_texto(
                causa,
                f"VIA_OAE={via or 'AUSENTE'}",
                f"CODIGO_NO_RAIO={codigo}",
                f"PREFIXO_CODIGO={prefixo or 'INDEFINIDO'}",
                f"DIST_M={por_codigo[codigo]['distancia']:.6f}",
                f"N_CODIGOS={len(por_codigo)}",
            )
        return codigo, "UNICO_TRECHO", None, observacao_texto(
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
        return None, "TRECHO_DIVERGENTE", causa, observacao_texto(
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
        return None, "TRECHO_EMPATE", causa, observacao_texto(
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
        return codigo, "TRECHO_COINCIDENTE", None, observacao_texto(
            "SOBREPOSICAO_COM=" + formatar_lista_codigos(coincidentes[codigo]),
            "DESCARTADOS_NO_MINIMO=" + formatar_lista_codigos(descartados)
            if descartados else None,
            auditoria_comum,
        )
    return codigo, "TRECHO_FRONTEIRA", None, auditoria_comum


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
    """Reduz a geometria de um trecho SNV a uma linha simples e continua.

    Parametros:
        geometria: QgsGeometry do trecho, ja em CRS_METRICA.

    Retorna:
        QgsGeometry de parte unica e comprimento positivo, ou None.

    Hipoteses metodologicas:
        A quilometragem por interpolacao pressupoe uma unica progressao linear
        continua. Uma MultiLineString so e aceita quando mergeLines() consegue
        uni-la em uma unica linha; partes desconexas nao possuem ordem
        intrinseca e sua concatenacao arbitraria produziria km sem sentido.

    Excecoes:
        mergeLines() pode inverter ou reordenar sub-partes. Isso e inofensivo
        aqui porque o sentido NAO e inferido da ordem dos vertices, e sim da
        conectividade com os trechos vizinhos (ver resolver_orientacao).
    """
    if geometria is None or geometria.isNull() or geometria.isEmpty():
        return None

    linha = QgsGeometry(geometria)
    if QgsWkbTypes.geometryType(linha.wkbType()) != QgsWkbTypes.LineGeometry:
        return None

    if linha.isMultipart():
        linha = linha.mergeLines()
        if linha is None or linha.isNull() or linha.isEmpty() or linha.isMultipart():
            return None

    comprimento = linha.length()
    return linha if math.isfinite(comprimento) and comprimento > 0 else None


def extremos_linha(linha):
    """Obtem o primeiro e o ultimo vertice de uma linha simples.

    Retorna:
        (QgsPointXY, QgsPointXY) ou (None, None) se a linha nao tiver vertices.

    Hipotese metodologica:
        Os indices 0 e 1 do par retornado sao apenas rotulos geometricos
        ("inicio" e "fim" do armazenamento). Nada se presume sobre qual deles
        corresponde ao km inicial; essa identificacao e feita adiante, pela
        continuidade quilometrica com os vizinhos.
    """
    primeiro = None
    ultimo = None
    for vertice in linha.vertices():
        if primeiro is None:
            primeiro = QgsPointXY(vertice)
        ultimo = QgsPointXY(vertice)
    if primeiro is None or ultimo is None:
        return None, None
    return primeiro, ultimo


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

obrigatorios_oae = {CAMPO_EXTENSAO, CAMPO_VIA}
obrigatorios_snv = {
    CAMPO_VL_CODIGO, CAMPO_VL_KM_INIC, CAMPO_VL_KM_FINA,
    CAMPO_BR_SNV, CAMPO_UF_SNV, CAMPO_TIPO_SNV,
}

faltantes_oae = sorted(obrigatorios_oae - campos_oae)
faltantes_snv = sorted(obrigatorios_snv - campos_snv)
if faltantes_oae:
    raise Exception(f"Campos ausentes em {NOME_CAMADA_OAE}: {', '.join(faltantes_oae)}")
if faltantes_snv:
    raise Exception(f"Campos ausentes em {NOME_CAMADA_SNV}: {', '.join(faltantes_snv)}")

campos_novos = {
    CAMPO_TRECHO_SNV,
    CAMPO_KM_SNV,
    CAMPO_DIST_SNV,
    CAMPO_RAIO_SNV,
    CAMPO_RODOVIAS,
    CAMPO_CRITERIO,
    CAMPO_SENTIDO_KM,
    CAMPO_OBSERVACAO,
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
# 5) CONTINUIDADE GEOMETRICA E QUILOMETRICA (SENTIDO DOS TRECHOS)
# -----------------------------------------------------------------------------
def resolver_orientacao(extremos, anteriores, posteriores):
    """Determina qual extremo geometrico do trecho corresponde ao km inicial.

    Parametros:
        extremos: ((x0, y0), (x1, y1)) do trecho avaliado.
        anteriores: lista de (fid, codigo, extremos) dos vizinhos cujo
            vl_km_fina coincide com o vl_km_inic do trecho avaliado.
        posteriores: lista de (fid, codigo, extremos) dos vizinhos cujo
            vl_km_inic coincide com o vl_km_fina do trecho avaliado.

    Retorna:
        dict com as chaves:
            "sentido"   : "INICIO_GEOM_KM_INIC" | "INICIO_GEOM_KM_FINAL" | None
            "motivo"    : causa da indeterminacao, quando sentido e None
            "evidencia" : "AMBOS" | "ANTERIOR" | "POSTERIOR" | None
            "anterior"  : codigo do vizinho anterior usado, ou None
            "posterior" : codigo do vizinho posterior usado, ou None

    Hipoteses metodologicas:
        1. A funcao e independente do QGIS (opera sobre coordenadas puras), o
           que a torna testavel isoladamente na auditoria.
        2. NAO se presume o sentido de nenhum vizinho. Usa-se apenas o fato
           objetivo de que o extremo do trecho que toca um vizinho ANTERIOR
           (km menor) e o extremo de km inicial, e vice-versa. Herdar o sentido
           de um vizinho propagaria erro ao longo da malha.
        3. Toda evidencia precisa ser UNICA. Duas feicoes concorrentes de um
           mesmo lado, ou uma unica feicao que toca os dois extremos (aneis
           viarios, retornos), nao recebem desempate.

    Excecoes:
        - CONEXAO_AMBIGUA      : evidencia nao unica (item 3).
        - SEM_VIZINHO_COMPATIVEL: nenhum vizinho conectado dos dois lados.
        - VIZINHOS_CONFLITANTES: anterior e posterior apontam o MESMO extremo,
          o que e geometricamente impossivel e indica inconsistencia do dado.
    """
    evidencias = []
    for candidatos in (anteriores, posteriores):
        conexoes = []
        for fid, codigo, extremos_vizinho in candidatos:
            pares = [
                (i, j)
                for i, ponto in enumerate(extremos)
                for j, ponto_vizinho in enumerate(extremos_vizinho)
                if math.dist(ponto, ponto_vizinho) <= TOLERANCIA_CONEXAO_M
            ]
            if pares:
                conexoes.append((fid, codigo, pares))
        evidencias.append(conexoes)

    anteriores_conectados, posteriores_conectados = evidencias
    resultado = {
        "sentido": None,
        "motivo": None,
        "evidencia": None,
        "anterior": None,
        "posterior": None,
    }
    if any(
        len(lado) > 1 or any(len(pares) != 1 for _, _, pares in lado)
        for lado in evidencias
    ):
        resultado["motivo"] = "CONEXAO_AMBIGUA"
        return resultado

    ant = anteriores_conectados[0] if anteriores_conectados else None
    pos = posteriores_conectados[0] if posteriores_conectados else None
    if ant is None and pos is None:
        resultado["motivo"] = "SEM_VIZINHO_COMPATIVEL"
        return resultado

    # pares[0][0] e o indice do extremo DO TRECHO AVALIADO que realiza a
    # conexao. Se o anterior e o posterior indicam o mesmo extremo, o dado e
    # contraditorio e nenhum sentido pode ser afirmado.
    if ant and pos and ant[2][0][0] == pos[2][0][0]:
        resultado["motivo"] = "VIZINHOS_CONFLITANTES"
        return resultado

    # Um anterior identifica o extremo de km inicial. Um posterior identifica
    # o extremo de km final. Quando ambos existem, precisam ser opostos.
    inicio_geom_km_inic = ant[2][0][0] == 0 if ant else pos[2][0][0] == 1
    resultado["sentido"] = (
        "INICIO_GEOM_KM_INIC" if inicio_geom_km_inic else "INICIO_GEOM_KM_FINAL"
    )
    resultado["evidencia"] = "AMBOS" if ant and pos else "ANTERIOR" if ant else "POSTERIOR"
    resultado["anterior"] = ant[1] if ant else None
    resultado["posterior"] = pos[1] if pos else None
    return resultado


def preparar_sentidos(snv_por_id):
    """Prepara geometrias e resolve o sentido de TODOS os trechos SNV.

    Parametros:
        snv_por_id: dict fid -> QgsFeature da copia metrica da SNV.

    Retorna:
        (preparados, sentidos)
            preparados: fid -> {"codigo", "chave", "linha", "ki", "kf",
                                "extremos", "erro"}
            sentidos  : fid -> dict retornado por resolver_orientacao.

    Hipoteses metodologicas:
        1. A orientacao e propriedade do TRECHO, nao da OAE. Por isso e
           resolvida uma unica vez, antes do laco das OAEs: duas OAEs no mesmo
           trecho nao podem receber sentidos diferentes.
        2. Sao vizinhos apenas trechos com a mesma chave (vl_br, sg_uf,
           sg_tipo_tr). Cruzar tipos ou UFs ligaria rodovias distintas cujas
           quilometragens sao independentes.
        3. Feicoes de MESMO vl_codigo sao excluidas da vizinhanca: no SNV o
           codigo identifica o trecho, de modo que outra feicao com o mesmo
           codigo e uma particao do proprio trecho, e nao um vizinho capaz de
           testemunhar seu sentido.
        4. Uma linha cujos extremos coincidem (anel/retorno) tem extremos
           indistinguiveis por qualquer tolerancia de conexao e nao pode ser
           orientada; ela permanece, porem, disponivel como VIZINHA das demais.

    Excecoes registradas em "erro" (todas resultam em sentido indeterminado):
        IDENTIFICACAO_SNV_INVALIDA, INTERVALO_KM_INVALIDO,
        GEOMETRIA_SNV_NAO_E_LINHA_SIMPLES_CONTINUA, EXTREMOS_SNV_INVALIDOS,
        GEOMETRIA_SNV_FECHADA_EXTREMOS_INDISTINGUIVEIS.
    """
    preparados = {}
    por_inicio = defaultdict(list)
    por_final = defaultdict(list)
    for fid, feicao in snv_por_id.items():
        codigo = codigo_valido(feicao[CAMPO_VL_CODIGO])
        chave = tuple(
            codigo_valido(feicao[campo])
            for campo in (CAMPO_BR_SNV, CAMPO_UF_SNV, CAMPO_TIPO_SNV)
        )
        linha = preparar_linha(feicao.geometry())
        ki = numero_finito(feicao[CAMPO_VL_KM_INIC])
        kf = numero_finito(feicao[CAMPO_VL_KM_FINA])
        registro = {
            "codigo": codigo, "chave": chave, "linha": linha,
            "ki": ki, "kf": kf, "extremos": None, "erro": None,
        }
        preparados[fid] = registro
        if not codigo or any(not parte for parte in chave):
            registro["erro"] = "IDENTIFICACAO_SNV_INVALIDA"
        elif ki is None or kf is None or ki < 0 or kf <= ki:
            # kf <= ki torna a interpolacao degenerada ou de sinal invertido.
            registro["erro"] = "INTERVALO_KM_INVALIDO"
        elif linha is None:
            registro["erro"] = "GEOMETRIA_SNV_NAO_E_LINHA_SIMPLES_CONTINUA"
        else:
            a, b = extremos_linha(linha)
            if a is None or b is None:
                registro["erro"] = "EXTREMOS_SNV_INVALIDOS"
                continue
            extremos = ((a.x(), a.y()), (b.x(), b.y()))
            if not all(math.isfinite(v) for ponto in extremos for v in ponto):
                registro["erro"] = "EXTREMOS_SNV_INVALIDOS"
                continue
            registro["extremos"] = extremos
            # A feicao entra nos indices ANTES da verificacao de anel: mesmo um
            # trecho nao orientavel continua sendo evidencia valida de
            # continuidade para os seus vizinhos.
            por_inicio[chave].append((ki, fid))
            por_final[chave].append((kf, fid))
            if math.dist(extremos[0], extremos[1]) <= TOLERANCIA_GEOMETRIA_FECHADA_M:
                registro["erro"] = "GEOMETRIA_SNV_FECHADA_EXTREMOS_INDISTINGUIVEIS"

    for indice in (por_inicio, por_final):
        for entradas in indice.values():
            entradas.sort()  # Indice de consulta, nunca criterio de desempate.

    def buscar(indice, registro, limite):
        """Recupera vizinhos cujo km de emenda coincide com 'limite'.

        A busca binaria opera sobre a janela [limite - tol, limite + tol]. A
        tolerancia e estritamente numerica (1e-8 km = 0,01 mm): lacunas reais
        de quilometragem NAO sao costuradas, pois representariam continuidade
        inexistente na malha.
        """
        entradas = indice.get(registro["chave"], [])
        inicio = bisect_left(entradas, (limite - TOLERANCIA_CONTINUIDADE_KM, -math.inf))
        fim = bisect_right(entradas, (limite + TOLERANCIA_CONTINUIDADE_KM, math.inf))
        return [
            (fid, preparados[fid]["codigo"], preparados[fid]["extremos"])
            for _, fid in entradas[inicio:fim]
            if preparados[fid]["codigo"] != registro["codigo"]
        ]

    sentidos = {}
    for fid, registro in preparados.items():
        if registro["erro"]:
            sentidos[fid] = {
                "sentido": None, "motivo": registro["erro"],
                "evidencia": None, "anterior": None, "posterior": None,
            }
            continue
        sentidos[fid] = resolver_orientacao(
            registro["extremos"],
            buscar(por_final, registro, registro["ki"]),
            buscar(por_inicio, registro, registro["kf"]),
        )
    return preparados, sentidos


print("Preparando o sentido dos trechos SNV...")
snv_preparada, sentidos_snv = preparar_sentidos(snv_por_id)
resumo_sentidos = Counter(
    info["evidencia"] if info["sentido"] else info["motivo"]
    for info in sentidos_snv.values()
)
# O diagnostico de sentido nao e fixado no codigo: cada execucao reavalia a
# camada efetivamente carregada e publica seus proprios numeros.


def calcular_km(geometria_oae, linha, km_inicial, km_final, sentido):
    """Projeta a OAE sobre o trecho e interpola o quilometro correspondente.

    Parametros:
        geometria_oae: ponto da OAE em CRS_METRICA.
        linha: geometria linear simples e continua do trecho (preparar_linha).
        km_inicial, km_final: vl_km_inic e vl_km_fina ja validados
            (finitos, km_inicial >= 0, km_final > km_inicial).
        sentido: "INICIO_GEOM_KM_INIC" ou "INICIO_GEOM_KM_FINAL".

    Retorna:
        dict {"km", "fracao", "comprimento_m", "escala"} ou None quando o
        calculo nao puder ser concluido com evidencia suficiente.
        "escala" = comprimento geometrico / extensao declarada em metros.

    Hipoteses metodologicas:
        1. A OAE e projetada ORTOGONALMENTE sobre o eixo do trecho: adota-se o
           ponto do eixo mais proximo da OAE como sua posicao linear.
        2. A quilometragem varia LINEARMENTE ao longo da geometria. E a
           hipotese central do metodo. Ela e exata quando o comprimento
           geometrico coincide com a extensao declarada e aproximada quando
           divergem (generalizacao do tracado, km herdado de versoes
           anteriores do SNV). Por isso "escala" e devolvido e auditado.
        3. A fracao e limitada a [0, 1]: nenhuma OAE recebe km fora do
           intervalo declarado do proprio trecho ao qual foi associada.
        4. Sentido ausente NUNCA e arbitrado. Sem sentido, nao ha km.

    Excecoes:
        Retorna None se o comprimento for nulo/nao finito, se a projecao
        falhar, se lineLocatePoint devolver posicao negativa (falha do GEOS) ou
        se o sentido nao for um dos dois valores previstos.
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
    if km_inicial is None or km_final is None:
        return None

    if sentido == "INICIO_GEOM_KM_INIC":
        km = km_inicial + fracao * (km_final - km_inicial)
    elif sentido == "INICIO_GEOM_KM_FINAL":
        # A geometria comeca no km FINAL: a fracao percorre a quilometragem
        # em ordem decrescente.
        km = km_final + fracao * (km_inicial - km_final)
    else:
        return None

    extensao_declarada_m = abs(km_final - km_inicial) * 1000.0
    escala = comprimento / extensao_declarada_m if extensao_declarada_m > 0 else None
    return {
        "km": km,
        "fracao": fracao,
        "comprimento_m": comprimento,
        "escala": escala,
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
provedor_saida.addAttributes(
    [
        QgsField(CAMPO_TRECHO_SNV, QVariant.String, len=80),
        QgsField(CAMPO_KM_SNV, QVariant.Double, len=20, prec=3),
        QgsField(CAMPO_DIST_SNV, QVariant.Double, len=20, prec=3),
        QgsField(CAMPO_RAIO_SNV, QVariant.Double, len=20, prec=3),
        QgsField(CAMPO_RODOVIAS, QVariant.String, len=TAMANHO_MAX_RODOVIAS),
        QgsField(CAMPO_CRITERIO, QVariant.String, len=30),
        QgsField(CAMPO_SENTIDO_KM, QVariant.String, len=30),
        QgsField(CAMPO_OBSERVACAO, QVariant.String, len=TAMANHO_MAX_OBS),
    ]
)
saida.updateFields()

idx_trecho = saida.fields().indexOf(CAMPO_TRECHO_SNV)
idx_km = saida.fields().indexOf(CAMPO_KM_SNV)
idx_dist = saida.fields().indexOf(CAMPO_DIST_SNV)
idx_raio = saida.fields().indexOf(CAMPO_RAIO_SNV)
idx_rodovias = saida.fields().indexOf(CAMPO_RODOVIAS)
idx_criterio = saida.fields().indexOf(CAMPO_CRITERIO)
idx_sentido = saida.fields().indexOf(CAMPO_SENTIDO_KM)
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
    }
)

novas_feicoes = []
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
    # Valor inicial: sem trecho associado, o sentido nao se aplica. Sera
    # sobrescrito por NAO_DETERMINADO ou pelo sentido efetivo quando houver
    # trecho.
    nova.setAttribute(idx_sentido, "NAO_APLICAVEL")

    geom_oae_metrica = geometria_pontual_metrica(oae, transformacao_oae)
    if geom_oae_metrica is None:
        criterio = "SEM_TRECHO"
        # Rodovias_coincidentes fica NULL: nenhuma rodovia chegou a ser
        # avaliada, o que e diferente de ter sido avaliada e nada encontrado.
        nova.setAttribute(idx_criterio, criterio)
        nova.setAttribute(idx_observacao, "GEOMETRIA_OAE_INVALIDA_OU_MULTIPONTO")
        contagem[criterio] += 1
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
    rodovias, codigos_sem_prefixo = rodovias_por_proximidade(por_codigo)
    nova.setAttribute(idx_rodovias, truncar_texto(rodovias, TAMANHO_MAX_RODOVIAS))

    codigo_escolhido, criterio, causa, observacao = selecionar_codigo(
        por_codigo, via, snv_por_id, geom_oae_metrica
    )
    if qtd_codigos == 0:
        observacao = observacao_texto(
            observacao,
            f"{feicoes_sem_codigo_no_raio}_FEICOES_SNV_SEM_CODIGO_NO_RAIO"
            if feicoes_sem_codigo_no_raio else None,
            f"{feicoes_alem_do_limite}_FEICOES_ALEM_DA_DISTANCIA_MAXIMA"
            if feicoes_alem_do_limite else None,
            "N_CODIGOS=0",
            f"RAIO_M={raio_procura:.3f}",
        )
    # Codigo fora do padrao nao gera numero de rodovia e fica de fora da lista;
    # a omissao e registrada para nao desaparecer do resultado.
    if codigos_sem_prefixo:
        observacao = observacao_texto(
            observacao, f"N_CODIGOS_SEM_PREFIXO_VALIDO={codigos_sem_prefixo}")

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
    nova.setAttribute(idx_trecho, codigo_escolhido)
    nova.setAttribute(idx_dist, round(distancia_escolhida, 3))

    # O codigo pode estar em mais de uma feicao. A geometria usada para
    # projetar a OAE precisa ser univoca pela menor distancia; empate entre
    # geometrias do mesmo codigo nao recebe desempate, pois escolher qualquer
    # uma delas arbitraria a posicao linear e, portanto, o proprio km.
    feicoes_mais_proximas = por_codigo[codigo_escolhido]["feicoes_mais_proximas"]
    if len(feicoes_mais_proximas) != 1:
        nova.setAttribute(idx_sentido, "NAO_DETERMINADO")
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
    info_sentido = sentidos_snv[fid_escolhido]
    sentido = info_sentido["sentido"]
    motivo_sentido = info_sentido["motivo"]

    # Guarda defensiva: por construcao, toda feicao com sentido definido possui
    # linha e intervalo de km validos. A verificacao mantem a garantia explicita
    # caso preparar_sentidos venha a ser alterado.
    if sentido is None or linha is None or preparo["ki"] is None or preparo["kf"] is None:
        nova.setAttribute(idx_sentido, "NAO_DETERMINADO")
        causa = motivo_sentido or "PREPARO_DO_TRECHO_INCOMPLETO"
        nova.setAttribute(idx_observacao, observacao_texto(causa, observacao))
        contagem["KM_NAO_DETERMINADO"] += 1
        motivos_km_nulo[causa] += 1
        novas_feicoes.append(nova)
        continue

    resultado_km = calcular_km(
        geom_oae_metrica,
        linha,
        preparo["ki"],
        preparo["kf"],
        sentido,
    )
    if resultado_km is None:
        nova.setAttribute(idx_sentido, "NAO_DETERMINADO")
        nova.setAttribute(idx_observacao, observacao_texto(
            "FALHA_NA_PROJECAO_OU_INTERPOLACAO", observacao))
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

    nova.setAttribute(idx_km, round(resultado_km["km"], 3))
    nova.setAttribute(idx_sentido, sentido)
    nova.setAttribute(idx_observacao, observacao_texto(
        alerta_escala,
        alerta_extremo,
        "EVIDENCIA=" + info_sentido["evidencia"],
        "ANT=" + info_sentido["anterior"] if info_sentido["anterior"] else None,
        "POS=" + info_sentido["posterior"] if info_sentido["posterior"] else None,
        f"FRACAO={resultado_km['fracao']:.6f}",
        observacao,
    ))
    contagem["KM_CALCULADO"] += 1
    novas_feicoes.append(nova)


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
print("Causas da nao associacao (criterio : causa):")
for motivo, quantidade in sorted(motivos_sem_associacao.items()):
    criterio_motivo, _, causa_motivo = motivo.partition(":")
    print(f"  {criterio_motivo:20} {causa_motivo:48} {quantidade}")
print(f"OAEs com Via ausente/nao normalizavel: {contagem['VIA_NAO_NORMALIZAVEL']}")
print(f"Mediana das extensoes validas:         {mediana_extensao:.3f} m")
print(f"Feicoes SNV sem geometria/reprojecao:  {snv_descartadas_geometria}")
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
print("=" * 72)
print()
print("DIAGNOSTICO DO SENTIDO - TRECHOS SNV (NAO OAEs)")
for evidencia in ("AMBOS", "ANTERIOR", "POSTERIOR"):
    print(f"  Confirmado por {evidencia}: {resumo_sentidos[evidencia]}")
for motivo in sorted(set(resumo_sentidos) - {"AMBOS", "ANTERIOR", "POSTERIOR"}):
    print(f"  {motivo}: {resumo_sentidos[motivo]}")
print(f"Total de feicoes SNV avaliadas: {sum(resumo_sentidos.values())}")
print(f"SNV excluidas por geometria/reprojecao: {snv_descartadas_geometria}")
print()
print("PARAMETROS DESTA EXECUCAO")
print(f"  CRS metrico:                     {CRS_METRICA.authid()}")
print(f"  FATOR_RAIO:                      {FATOR_RAIO}")
print(f"  TOLERANCIA_CONEXAO_M:            {TOLERANCIA_CONEXAO_M}")
print(f"  TOLERANCIA_CONTINUIDADE_KM:      {TOLERANCIA_CONTINUIDADE_KM}")
print(f"  TOLERANCIA_EMPATE_DISTANCIA_M:   {TOLERANCIA_EMPATE_DISTANCIA_M}")
print(f"  DISTANCIA_MAXIMA_ASSOCIACAO_M:   {DISTANCIA_MAXIMA_ASSOCIACAO_M}")
print("  VIA_COMPATIVEL:                  pre-condicao universal (obrigatoria)")
