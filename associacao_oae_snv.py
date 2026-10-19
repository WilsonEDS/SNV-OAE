# -*- coding: utf-8 -*-
# =============================================================================
# ASSOCIACAO OAE (SGE) x SNV - TRECHO E QUILOMETRO - QGIS / PyQGIS
# =============================================================================
#
# Para cada Obra de Arte Especial (OAE) da camada SGE:
#   1. associa UM trecho do SNV (vl_codigo) e classifica a associacao em um de
#      seis criterios;
#   2. calcula o km da OAE no trecho, por interpolacao linear entre vl_km_inic e
#      vl_km_fina, no sentido de digitalizacao da LineString do trecho.
#
# ENTRADAS - camadas carregadas no projeto QGIS
#   SGE (pontos): "Extensão (m)", "Via", "Relacao_SNV".
#   SNV (linhas): vl_codigo, vl_km_inic, vl_km_fina, ds_tipo_ad, ds_jurisdi,
#                 versao_snv.
#   Os nomes de campo sao localizados sem distinguir acento, maiusculas, "_" e
#   espacos, e tambem pelo alias (resolver_campo).
#
# SAIDA - camada em memoria "SGExSNV"
#   Campos da SGE, exceto "Km", "Código SNV" e "Versão SNV" (de uma associacao
#   anterior, substituidos pelos calculados aqui), seguidos de:
#     Trecho_SNV            vl_codigo atribuido, ou NULL
#     Versao_SNV            versao_snv do trecho atribuido
#     Administracao         ds_tipo_ad do trecho atribuido
#     Jurisdicao            ds_jurisdi do trecho atribuido
#     km_SNV                km interpolado, ou NULL
#     Rodovias_coincidentes BRs em sobreposicao comprovada no local (ex.:
#                           "116;101"), a atribuida primeiro; NULL sem
#                           coincidencia
#     Status                "Validado" ou "A validar"; Relacao_SNV "T" ou "N"
#                           e sempre "A validar" (ver status_validacao)
#     Criterio              um dos seis criterios abaixo
#     Dist_SNV_m            distancia, em metros, da OAE ao trecho atribuido
#     Raio_SNV              raio de busca efetivamente usado, em metros
#     Qtd_Codigos           quantidade de vl_codigo distintos no raio
#
# FLUXO
#   a) A SNV e lida uma unica vez: geometria em CRS_METRICA, atributos e indice
#      espacial.
#   b) Raio de busca = max(extensao da OAE, mediana das extensoes) x FATOR_RAIO.
#      Se nao houver nenhum trecho no raio, nova busca com FATOR_RAIO_AMPLIADO.
#   c) Os candidatos sao agrupados por vl_codigo; a distancia de um codigo e a
#      menor distancia entre a OAE e as feicoes daquele codigo.
#   d) Criterios, avaliados nesta ordem:
#        Sem trecho          nenhum codigo no raio (ou geometria da OAE invalida)
#        Trecho único        um so codigo no raio, compativel com a Via
#        Trecho divergente   nenhum codigo do raio compativel com a Via
#        Trecho empate       2+ codigos compativeis a mesma distancia
#        Trecho coincidente  vencedor que compartilha porcao linear, na posicao
#                            da OAE, com outro codigo equidistante
#        Trecho fronteira    vencedor unico por menor distancia
#      Compatibilidade com a Via (BR = 3 primeiros digitos do vl_codigo) e
#      pre-condicao: nenhum codigo de outra BR e atribuido.
#   e) km = vl_km_inic + fracao x (vl_km_fina - vl_km_inic), com fracao = posicao
#      da projecao da OAE ao longo da linha (0 no primeiro vertice, 1 no
#      ultimo). O km e coerente com os dados do trecho associado; sentido,
#      vizinhanca e consistencia entre tabela e geometria sao analisados em
#      outra atividade.
#
# O resultado nao depende da ordem de leitura das feicoes: toda escolha exige
# um vencedor unico, e empates nunca sao desfeitos pela ordem.
# =============================================================================

import difflib
import math
import re
import statistics
import unicodedata
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

# Campos de entrada. Os valores abaixo sao os nomes de referencia; na validacao
# cada um e trocado pelo nome real encontrado na camada (resolver_obrigatorios).
CAMPO_EXTENSAO = "Extensão (m)"
CAMPO_VIA = "Via"
CAMPO_RELACAO_SNV = "Relacao_SNV"
CAMPO_VL_CODIGO = "vl_codigo"
CAMPO_VL_KM_INIC = "vl_km_inic"
CAMPO_VL_KM_FINA = "vl_km_fina"
CAMPO_ADMIN_SNV = "ds_tipo_ad"
CAMPO_JURIS_SNV = "ds_jurisdi"
CAMPO_VERSAO_SNV_ORIGEM = "versao_snv"

# Colunas da SGE vindas de uma associacao anterior com a SNV. Nao sao copiadas:
# km_SNV, Trecho_SNV e Versao_SNV as substituem.
CAMPOS_OAE_EXCLUIDOS = ("Km", "Código SNV", "Versão SNV")

# Campos criados, na ordem em que aparecem na saida.
CAMPO_TRECHO_SNV = "Trecho_SNV"
CAMPO_VERSAO_SNV = "Versao_SNV"
CAMPO_ADMINISTRACAO = "Administracao"
CAMPO_JURISDICAO = "Jurisdicao"
CAMPO_KM_SNV = "km_SNV"
CAMPO_RODOVIAS_COINC = "Rodovias_coincidentes"
CAMPO_STATUS = "Status"
CAMPO_CRITERIO = "Criterio"
CAMPO_DIST_SNV = "Dist_SNV_m"
CAMPO_RAIO_SNV = "Raio_SNV"
CAMPO_QTD_CODIGOS = "Qtd_Codigos"
CAMPOS_NOVOS = (
    CAMPO_TRECHO_SNV, CAMPO_VERSAO_SNV, CAMPO_ADMINISTRACAO, CAMPO_JURISDICAO,
    CAMPO_KM_SNV, CAMPO_RODOVIAS_COINC, CAMPO_STATUS, CAMPO_CRITERIO,
    CAMPO_DIST_SNV, CAMPO_RAIO_SNV, CAMPO_QTD_CODIGOS,
)

# Todas as medicoes (distancia, comprimento, projecao) ocorrem neste SRC
# metrico, que cobre o territorio nacional (SIRGAS 2000 / Brazil Polyconic).
CRS_METRICA = QgsCoordinateReferenceSystem("EPSG:5880")

# Raio de busca = base x fator. O fator ampliado so e usado quando o raio
# normal nao alcanca nenhum trecho.
FATOR_RAIO = 2.0
FATOR_RAIO_AMPLIADO = 5.0

# Tolerancia numerica para tratar duas distancias como iguais.
TOLERANCIA_EMPATE_DISTANCIA_M = 1e-8

# Comprimento maximo de campos de texto (seguro para Shapefile/DBF).
TAMANHO_MAX_TEXTO = 254

# Ordem de impressao dos criterios no resumo.
CRITERIOS_VALIDOS = (
    "SEM_TRECHO",
    "UNICO_TRECHO",
    "TRECHO_COINCIDENTE",
    "TRECHO_FRONTEIRA",
    "TRECHO_DIVERGENTE",
    "TRECHO_EMPATE",
)

# Texto gravado em Criterio para cada codigo interno.
TEXTO_CRITERIO = {
    "SEM_TRECHO": "Sem trecho",
    "UNICO_TRECHO": "Trecho único",
    "TRECHO_DIVERGENTE": "Trecho divergente",
    "TRECHO_EMPATE": "Trecho empate",
    "TRECHO_COINCIDENTE": "Trecho coincidente",
    "TRECHO_FRONTEIRA": "Trecho fronteira",
}

STATUS_VALIDADO = "Validado"
STATUS_A_VALIDAR = "A validar"


# -----------------------------------------------------------------------------
# 1) FUNCOES AUXILIARES
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
        Usada para km, que pode legitimamente ser zero ou negativo; so a
        ausencia de valor numerico impede o calculo (ver preparar_trecho).
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
          NULL e a divergencia e contabilizada no resumo.
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
        - ou rejeitado - pelo provedor, o que faria o dado desaparecer sem
        aviso. O corte e feito aqui, de forma deterministica, e
        sinalizado com o marcador "...[truncado]", de modo que a perda seja
        sempre visivel no proprio dado.
    """
    if not texto:
        return None
    if len(texto) <= limite:
        return texto
    marcador = "...[truncado]"
    return texto[: limite - len(marcador)] + marcador


def normalizar_nome_campo(nome):
    """Forma de comparacao de um nome de campo, imune a diferencas de grafia.

    Remove acentos, ignora maiusculas e trata "_" e qualquer espaco (inclusive
    o nao separavel) como um espaco unico. Assim "Versão SNV", "versao_snv" e
    "VERSAO  SNV" se equivalem.
    """
    texto = unicodedata.normalize("NFKD", str(nome or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.replace("_", " ").split()).casefold()


def resolver_campo(campos, nome):
    """Encontra na camada o campo que corresponde a um nome pedido.

    Parametros:
        campos: lista de (nome_real, alias) dos campos da camada.
        nome: nome pedido pelo script (ex.: "Versão SNV").

    Retorna:
        o nome REAL do campo, ou None se nenhum corresponder.

    Excecoes:
        ValueError quando mais de um campo corresponde: nao se escolhe entre
        eles.

    Hipoteses metodologicas:
        - Ordem de busca: nome identico; depois nome com grafia normalizada
          (normalizar_nome_campo); depois alias normalizado. O primeiro nivel
          com correspondencia decide.
        - O nome real e o que importa para ler o valor; o alias e so o rotulo
          que a tabela de atributos pode estar exibindo.
        - Nome cortado (ex.: limite de 10 bytes do Shapefile) NAO e aceito:
          um prefixo poderia casar com o campo errado ("Código" dentro de
          "Código SNV").
    """
    exatos = [real for real, _ in campos if real == nome]
    if exatos:
        return exatos[0]
    alvo = normalizar_nome_campo(nome)
    for indice in (0, 1):
        achados = [c[0] for c in campos if c[indice] and normalizar_nome_campo(c[indice]) == alvo]
        if len(achados) == 1:
            return achados[0]
        if len(achados) > 1:
            raise ValueError(f'"{nome}" corresponde a mais de um campo: {", ".join(achados)}')
    return None


def mensagem_campo_ausente(campos, nomes, nome_camada):
    """Mensagem de erro para campos obrigatorios nao encontrados numa camada.

    Lista, para cada nome, os campos mais parecidos e, ao final, todos os campos
    da camada com seus aliases, para que o nome real possa ser conferido e
    ajustado no script.
    """
    rotulos = {}
    for real, alias in campos:
        rotulos.setdefault(normalizar_nome_campo(real), real)
        if alias:
            rotulos.setdefault(normalizar_nome_campo(alias), real)
    linhas = []
    for nome in nomes:
        parecidos = difflib.get_close_matches(
            normalizar_nome_campo(nome), list(rotulos), n=3, cutoff=0.6)
        sugestao = ", ".join(dict.fromkeys(rotulos[p] for p in parecidos)) or "nenhum"
        linhas.append(f'Campo "{nome}" nao encontrado em {nome_camada}. '
                      f"Mais parecidos: {sugestao}")
    existentes = ", ".join(
        f"{real} (alias: {alias})" if alias and alias != real else real
        for real, alias in campos)
    linhas.append(f"Campos da camada: {existentes}")
    return "\n".join(linhas)


def indices_mantidos(campos, nomes_excluidos):
    """Escolhe os campos da camada de origem que serao copiados para a saida.

    Parametros:
        campos: lista de (nome_real, alias) da camada de origem, na ordem
            original.
        nomes_excluidos: nomes que NAO devem ser copiados.

    Retorna:
        (indices, excluidos, nao_encontrados)
        indices: posicoes dos campos mantidos, na ordem original.
        excluidos: nomes reais efetivamente retirados.
        nao_encontrados: nomes pedidos para exclusao que a camada nao tem (ou
            que correspondem a mais de um campo) - informados no console, para
            que nao passem despercebidos.

    Hipotese metodologica:
        Usa a mesma busca de resolver_campo: tolera acento, maiusculas, "_" e
        espacos, mas nunca prefixos. Em caso de ambiguidade nada e retirado.
    """
    retirar = []
    nao_encontrados = []
    for nome in nomes_excluidos:
        try:
            real = resolver_campo(campos, nome)
        except ValueError:
            real = None
        if real is None:
            nao_encontrados.append(nome)
        else:
            retirar.append(real)
    indices = [i for i, (real, _) in enumerate(campos) if real not in retirar]
    return indices, retirar, nao_encontrados


def status_validacao(criterio, relacao_snv, qtd_codigos):
    """Reproduz a formula de validacao da planilha de conferencia.

    Formula:
        =SE(OU(Relacao_SNV="T"; Relacao_SNV="N"); "A VALIDAR";
            SE(OU(E(Criterio="UNICO_TRECHO"; Relacao_SNV="L");
                  E(Criterio="TRECHO_COINCIDENTE"; Qtd_Codigos<3));
               "VALIDADO"; "A VALIDAR"))

    Parametros:
        criterio: codigo INTERNO do criterio (ex.: "UNICO_TRECHO").
        relacao_snv: valor bruto do campo Relacao_SNV da OAE.
        qtd_codigos: quantidade de vl_codigo distintos no raio.

    Retorna:
        STATUS_VALIDADO ou STATUS_A_VALIDAR; nunca None.

    Hipoteses metodologicas:
        - A comparacao usa o codigo interno do criterio, e nao o texto exibido,
          para nao depender da redacao gravada na camada.
        - Relacao_SNV "T" ou "N" tem prioridade: a OAE fica "A validar"
          qualquer que seja o criterio.
        - Relacao_SNV e comparado sem distinguir maiusculas, como o Excel, e
          tambem sem espacos nas bordas - nesse ponto difere do Excel, que
          considera " L" diferente de "L". Valor vazio ou nulo nao e "L".
    """
    relacao = codigo_valido(relacao_snv)
    relacao = relacao.upper() if relacao is not None else None
    if relacao in ("T", "N"):
        return STATUS_A_VALIDAR
    validado = (
        (criterio == "UNICO_TRECHO" and relacao == "L")
        or (criterio == "TRECHO_COINCIDENTE" and qtd_codigos is not None and qtd_codigos < 3)
    )
    return STATUS_VALIDADO if validado else STATUS_A_VALIDAR


def raio_base(extensao, mediana):
    """Base do raio de busca de uma OAE, em metros.

    A extensao da obra, com piso na mediana das extensoes validas: uma OAE
    longa pode estar afastada do eixo lancado no SNV, e uma OAE sem extensao
    declarada (ou com valor invalido) nao pode ficar sem janela de busca.
    """
    extensao = numero_finito_positivo(extensao)
    return max(extensao, mediana) if extensao is not None else mediana


def buscar_em_etapas(coletar, base):
    """Busca candidatos com FATOR_RAIO e, se nao houver nenhum, com o ampliado.

    Parametros:
        coletar: funcao raio -> por_codigo (ver coletar_candidatos).
        base: base do raio da OAE (raio_base).

    Retorna:
        (por_codigo, raio_usado, ampliado)

    O fator ampliado vale SO para a OAE sem nenhum trecho no raio normal. Uma
    OAE com candidatos, ainda que incompativeis com a Via, nao tem o raio
    ampliado: o que lhe falta nao e alcance.
    """
    raio = base * FATOR_RAIO
    por_codigo = coletar(raio)
    if por_codigo:
        return por_codigo, raio, False
    raio = base * FATOR_RAIO_AMPLIADO
    return coletar(raio), raio, True


# -----------------------------------------------------------------------------
# 2) SELECAO DO TRECHO
# -----------------------------------------------------------------------------
def codigos_sobrepostos(registro_a, registro_b, trechos, geometria_oae=None):
    """Verifica se dois codigos SNV sao localmente COINCIDENTES junto a OAE.

    Parametros:
        registro_a, registro_b: registros de por_codigo, contendo "distancia" e
            "feicoes_mais_proximas" (lista de (fid, distancia) que realizam a
            menor distancia daquele codigo).
        trechos: fid -> registro do trecho SNV (usa a chave "geometria").
        geometria_oae: ponto da OAE em CRS_METRICA. Se None, dispensa o teste
            de localidade.

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
            comum = trechos[fid_a]["geometria"].intersection(trechos[fid_b]["geometria"])
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
        contagem devolvida permite contabilizar a anomalia no resumo; o filtro
        de coincidencia real entre rodovias distintas e o texto conter ";".

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


def selecionar_codigo(por_codigo, via, trechos, geometria_oae):
    """Seleciona um unico vl_codigo para a OAE e classifica a associacao.

    Parametros:
        por_codigo: vl_codigo -> {"distancia", "feicoes_mais_proximas"}, com
            todos os codigos dentro do raio de busca.
        via: numero da BR da OAE (3 digitos) ou None.
        trechos: fid -> registro do trecho SNV (usa a chave "geometria").
        geometria_oae: ponto da OAE em CRS_METRICA.

    Retorna:
        (codigo_ou_None, criterio, causa, rodovias_coincidentes)
        causa: motivo da nao associacao (contabilizado no resumo), ou None.
        rodovias_coincidentes: ver rodovias_coincidentes_texto, ou None.

    Sequencia de decisao:
        1. nenhum codigo                          -> SEM_TRECHO
        2. um codigo: compativel com a Via        -> UNICO_TRECHO
                      incompativel, ou Via ausente -> TRECHO_DIVERGENTE
        3. dois ou mais codigos:
           nenhum compativel                       -> TRECHO_DIVERGENTE
           vencedor nao unico                      -> TRECHO_EMPATE
           vencedor unico com coincidencia         -> TRECHO_COINCIDENTE
           vencedor unico sem coincidencia         -> TRECHO_FRONTEIRA

    Hipoteses metodologicas:
        - A compatibilidade com a Via e pre-condicao: nenhum codigo de outra BR
          e atribuido, ainda que seja o unico no raio. A distancia so desempata
          dentro do conjunto compativel.
        - A distancia minima e calculada sobre TODOS os compativeis antes de
          qualquer prioridade; a coincidencia so desempata dentro desse minimo,
          e nunca resgata um codigo mais distante.
        - O parceiro que comprova a coincidencia pode ser de outra BR; o codigo
          escolhido, nao.
        - Empate nunca e desfeito pela ordem de leitura.
    """
    if not por_codigo:
        return None, "SEM_TRECHO", "SEM_CANDIDATO_NO_RAIO", None

    if len(por_codigo) == 1:
        codigo = next(iter(por_codigo))
        if via is None:
            return None, "TRECHO_DIVERGENTE", "VIA_AUSENTE_OU_NAO_NORMALIZAVEL", None
        if prefixo_codigo(codigo) != via:
            return None, "TRECHO_DIVERGENTE", "UNICO_CODIGO_INCOMPATIVEL_COM_VIA", None
        return codigo, "UNICO_TRECHO", None, None

    compativeis = [c for c in por_codigo if via is not None and prefixo_codigo(c) == via]
    if not compativeis:
        causa = ("VIA_AUSENTE_OU_NAO_NORMALIZAVEL" if via is None
                 else "NENHUM_CODIGO_COMPATIVEL_COM_VIA")
        return None, "TRECHO_DIVERGENTE", causa, None

    menor = min(por_codigo[c]["distancia"] for c in compativeis)
    mais_proximos = [c for c in compativeis if quase_igual(
        por_codigo[c]["distancia"], menor, TOLERANCIA_EMPATE_DISTANCIA_M)]

    # O teste de sobreposicao envolve interseccao de geometrias; memorizado por
    # par de codigos para nao ser refeito.
    cache_sobreposicao = {}

    def sobrepostos(codigo_x, codigo_y):
        chave = (codigo_x, codigo_y) if codigo_x <= codigo_y else (codigo_y, codigo_x)
        if chave not in cache_sobreposicao:
            cache_sobreposicao[chave] = codigos_sobrepostos(
                por_codigo[codigo_x], por_codigo[codigo_y], trechos, geometria_oae)
        return cache_sobreposicao[chave]

    coincidentes = {}
    for codigo in mais_proximos:
        distancia = por_codigo[codigo]["distancia"]
        parceiros = [
            outro for outro, candidato in por_codigo.items()
            if outro != codigo
            and quase_igual(distancia, candidato["distancia"], TOLERANCIA_EMPATE_DISTANCIA_M)
            and sobrepostos(codigo, outro)
        ]
        if parceiros:
            coincidentes[codigo] = parceiros

    vencedores = list(coincidentes) if coincidentes else mais_proximos
    if len(vencedores) != 1:
        # A OAE empatada entre codigos coincidentes esta sobre rodovias
        # coincidentes, mesmo sem trecho atribuido; por isso o campo e
        # preenchido tambem aqui.
        causa = ("CODIGOS_COINCIDENTES_COMPATIVEIS_EQUIDISTANTES" if coincidentes
                 else "CODIGOS_COMPATIVEIS_EQUIDISTANTES")
        return None, "TRECHO_EMPATE", causa, rodovias_coincidentes_texto(coincidentes)[0]

    codigo = vencedores[0]
    if coincidentes:
        return (codigo, "TRECHO_COINCIDENTE", None,
                rodovias_coincidentes_texto(coincidentes, codigo)[0])
    return codigo, "TRECHO_FRONTEIRA", None, None


# -----------------------------------------------------------------------------
# 3) GEOMETRIA E QUILOMETRO
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


def preparar_trecho(geometria, km_inicial, km_final):
    """Prepara um trecho SNV para o calculo do km.

    Retorna:
        (linha, erro): linha de parte unica na ordem de vertices gravada, ou
        None com a causa que impede o km.

    Basta que o trecho tenha km inicial e final numericos e uma linha de parte
    unica. Nenhuma relacao entre os dois km, nem entre eles e a geometria, e
    verificada aqui: o km resultante e coerente com os dados do trecho tal
    como estao; a consistencia desses dados e analisada em outra atividade.
    """
    if km_inicial is None or km_final is None:
        return None, "KM_DO_TRECHO_AUSENTE"
    return preparar_linha(geometria)


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
    """Projeta a OAE sobre o trecho e interpola o km correspondente.

    Parametros:
        geometria_oae: ponto da OAE em CRS_METRICA.
        linha: linha de parte unica do trecho (preparar_linha).
        km_inicial, km_final: vl_km_inic e vl_km_fina do trecho.

    Retorna:
        km (float), ou None se a projecao falhar.

    lineLocatePoint devolve a distancia, ao longo da linha, ate o ponto da
    linha mais proximo da OAE (projecao ortogonal); dividida pelo comprimento,
    e a fracao usada na interpolacao. Devolve valor negativo em caso de falha.
    """
    comprimento = linha.length()
    posicao = linha.lineLocatePoint(geometria_oae)
    if not (math.isfinite(posicao) and posicao >= 0 and comprimento > 0):
        return None
    return interpolar_km(km_inicial, km_final, posicao / comprimento)


# -----------------------------------------------------------------------------
# 4) CAMADAS E CAMPOS
# -----------------------------------------------------------------------------
projeto = QgsProject.instance()

lista_oae = projeto.mapLayersByName(NOME_CAMADA_OAE)
lista_snv = projeto.mapLayersByName(NOME_CAMADA_SNV)
if not lista_oae:
    raise Exception(f'Camada "{NOME_CAMADA_OAE}" nao encontrada no projeto.')
if not lista_snv:
    raise Exception(f'Camada "{NOME_CAMADA_SNV}" nao encontrada no projeto.')
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
if camada_oae.wkbType() in (QgsWkbTypes.Unknown, QgsWkbTypes.NoGeometry):
    raise Exception("Tipo de geometria da OAE indefinido; nao e possivel criar a saida.")


def resolver_obrigatorios(camada, nome_camada, nomes):
    """Localiza os campos obrigatorios de uma camada e devolve seus nomes reais.

    Retorna dict nome_pedido -> nome_real. Interrompe a execucao, com a lista
    dos campos existentes e dos mais parecidos, se algum faltar ou for ambiguo.
    Registra no console cada campo achado com grafia diferente da pedida.
    """
    campos = [(campo.name(), campo.alias()) for campo in camada.fields()]
    reais, ausentes = {}, []
    for nome in nomes:
        try:
            real = resolver_campo(campos, nome)
        except ValueError as erro:
            raise Exception(f"Em {nome_camada}: {erro}")
        if real is None:
            ausentes.append(nome)
        else:
            reais[nome] = real
            if real != nome:
                print(f'Campo "{nome}" encontrado em {nome_camada} como "{real}".')
    if ausentes:
        raise Exception(mensagem_campo_ausente(campos, ausentes, nome_camada))
    return reais


# As constantes passam a guardar o nome REAL de cada campo.
reais_oae = resolver_obrigatorios(
    camada_oae, NOME_CAMADA_OAE, (CAMPO_EXTENSAO, CAMPO_VIA, CAMPO_RELACAO_SNV))
CAMPO_EXTENSAO = reais_oae[CAMPO_EXTENSAO]
CAMPO_VIA = reais_oae[CAMPO_VIA]
CAMPO_RELACAO_SNV = reais_oae[CAMPO_RELACAO_SNV]

reais_snv = resolver_obrigatorios(
    camada_snv, NOME_CAMADA_SNV,
    (CAMPO_VL_CODIGO, CAMPO_VL_KM_INIC, CAMPO_VL_KM_FINA,
     CAMPO_ADMIN_SNV, CAMPO_JURIS_SNV, CAMPO_VERSAO_SNV_ORIGEM))
CAMPO_VL_CODIGO = reais_snv[CAMPO_VL_CODIGO]
CAMPO_VL_KM_INIC = reais_snv[CAMPO_VL_KM_INIC]
CAMPO_VL_KM_FINA = reais_snv[CAMPO_VL_KM_FINA]
CAMPO_ADMIN_SNV = reais_snv[CAMPO_ADMIN_SNV]
CAMPO_JURIS_SNV = reais_snv[CAMPO_JURIS_SNV]
CAMPO_VERSAO_SNV_ORIGEM = reais_snv[CAMPO_VERSAO_SNV_ORIGEM]

# Colunas da SGE copiadas para a saida (todas, menos as excluidas).
indices_oae_mantidos, campos_oae_excluidos, campos_oae_nao_encontrados = indices_mantidos(
    [(campo.name(), campo.alias()) for campo in camada_oae.fields()], CAMPOS_OAE_EXCLUIDOS)
nomes_oae_mantidos = {camada_oae.fields().at(i).name() for i in indices_oae_mantidos}
colisoes = sorted(set(CAMPOS_NOVOS) & nomes_oae_mantidos)
if colisoes:
    raise Exception("A SGE ja possui campos reservados para a saida: " + ", ".join(colisoes))

if not CRS_METRICA.isValid():
    raise Exception("CRS_METRICA invalida.")
contexto_transformacao = projeto.transformContext()
transformacao_oae = (None if camada_oae.crs() == CRS_METRICA else
                     QgsCoordinateTransform(camada_oae.crs(), CRS_METRICA, contexto_transformacao))
transformacao_snv = (None if camada_snv.crs() == CRS_METRICA else
                     QgsCoordinateTransform(camada_snv.crs(), CRS_METRICA, contexto_transformacao))


# -----------------------------------------------------------------------------
# 5) LEITURA DA SNV (UMA UNICA VEZ)
# -----------------------------------------------------------------------------
# Cada trecho vira um registro com a geometria ja em CRS_METRICA e os atributos
# usados adiante, de modo que o laco das OAEs nao releia a camada nem busque
# atributos por nome. O indice espacial e alimentado no mesmo passo.
trechos_snv = {}
indice_snv = QgsSpatialIndex()
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

    km_inicial = numero_finito(feicao[CAMPO_VL_KM_INIC])
    km_final = numero_finito(feicao[CAMPO_VL_KM_FINA])
    linha, erro = preparar_trecho(geometria, km_inicial, km_final)
    trechos_snv[feicao.id()] = {
        "geometria": geometria,
        "codigo": codigo_valido(feicao[CAMPO_VL_CODIGO]),
        "ki": km_inicial,
        "kf": km_final,
        "linha": linha,
        "erro": erro,
        "versao": feicao[CAMPO_VERSAO_SNV_ORIGEM],
        "administracao": feicao[CAMPO_ADMIN_SNV],
        "jurisdicao": feicao[CAMPO_JURIS_SNV],
    }
    entrada_indice = QgsFeature()
    entrada_indice.setId(feicao.id())
    entrada_indice.setGeometry(geometria)
    indice_snv.addFeature(entrada_indice)

if not trechos_snv:
    raise Exception("Nenhuma feicao SNV com geometria valida apos a reprojecao.")
resumo_trechos = Counter(t["erro"] or "APTO_AO_CALCULO_DO_KM" for t in trechos_snv.values())


def coletar_candidatos(geometria_oae, raio):
    """Codigos SNV dentro do raio da OAE, com a menor distancia de cada um.

    Retorna:
        vl_codigo -> {"distancia": menor distancia do codigo,
                      "feicoes_mais_proximas": [(fid, distancia), ...]}
        Feicoes sem vl_codigo valido sao ignoradas.

    O indice devolve candidatos pelo envelope (quadrado que contem o circulo do
    raio); a distancia real decide a admissao. A menor distancia e os empates
    sao apurados sobre o conjunto completo, sem depender da ordem de leitura.
    """
    ponto = QgsPointXY(geometria_oae.asPoint())
    por_codigo = {}
    for fid in indice_snv.intersects(retangulo_centrado(ponto, raio)):
        trecho = trechos_snv[fid]
        if trecho["codigo"] is None:
            continue
        distancia = trecho["geometria"].distance(geometria_oae)
        if math.isfinite(distancia) and 0 <= distancia <= raio:
            por_codigo.setdefault(trecho["codigo"], []).append((fid, distancia))
    for codigo, feicoes in por_codigo.items():
        menor = min(d for _, d in feicoes)
        por_codigo[codigo] = {
            "distancia": menor,
            "feicoes_mais_proximas": [
                (fid, d) for fid, d in feicoes
                if quase_igual(d, menor, TOLERANCIA_EMPATE_DISTANCIA_M)],
        }
    return por_codigo


# -----------------------------------------------------------------------------
# 6) MEDIANA DAS EXTENSOES E CAMADA DE SAIDA
# -----------------------------------------------------------------------------
extensoes_validas = [
    extensao for extensao in (
        numero_finito_positivo(f[CAMPO_EXTENSAO]) for f in camada_oae.getFeatures())
    if extensao is not None
]
if not extensoes_validas:
    raise Exception(f'Nenhuma extensao positiva e finita em "{CAMPO_EXTENSAO}".')
mediana_extensao = statistics.median(extensoes_validas)


def comprimento_origem(nome_campo):
    """Comprimento declarado de um campo de texto da SNV, para replica-lo na saida.

    Retorna o comprimento do campo de origem, ou TAMANHO_MAX_TEXTO quando o
    provedor nao o informa (comprimento 0 ou negativo, comum em GeoPackage).
    Replicar o comprimento evita truncar na saida um valor que a propria SNV
    comporta.
    """
    comprimento = camada_snv.fields().field(nome_campo).length()
    return comprimento if comprimento and comprimento > 0 else TAMANHO_MAX_TEXTO


saida = QgsVectorLayer(
    f"{QgsWkbTypes.displayString(camada_oae.wkbType())}?crs={camada_oae.crs().authid()}",
    NOME_CAMADA_SAIDA,
    "memory",
)
if not saida.isValid():
    raise Exception("Falha ao criar a camada de saida em memoria.")

TAMANHO_VERSAO_SNV = comprimento_origem(CAMPO_VERSAO_SNV_ORIGEM)
TAMANHO_ADMINISTRACAO = comprimento_origem(CAMPO_ADMIN_SNV)
TAMANHO_JURISDICAO = comprimento_origem(CAMPO_JURIS_SNV)
definicao_campos_novos = [
    QgsField(CAMPO_TRECHO_SNV, QVariant.String, len=80),
    QgsField(CAMPO_VERSAO_SNV, QVariant.String, len=TAMANHO_VERSAO_SNV),
    QgsField(CAMPO_ADMINISTRACAO, QVariant.String, len=TAMANHO_ADMINISTRACAO),
    QgsField(CAMPO_JURISDICAO, QVariant.String, len=TAMANHO_JURISDICAO),
    QgsField(CAMPO_KM_SNV, QVariant.Double, len=20, prec=3),
    QgsField(CAMPO_RODOVIAS_COINC, QVariant.String, len=TAMANHO_MAX_TEXTO),
    QgsField(CAMPO_STATUS, QVariant.String, len=20),
    QgsField(CAMPO_CRITERIO, QVariant.String, len=30),
    QgsField(CAMPO_DIST_SNV, QVariant.Double, len=20, prec=3),
    QgsField(CAMPO_RAIO_SNV, QVariant.Double, len=20, prec=3),
    QgsField(CAMPO_QTD_CODIGOS, QVariant.Int),
]
if [campo.name() for campo in definicao_campos_novos] != list(CAMPOS_NOVOS):
    raise RuntimeError("Definicao dos campos de saida diverge de CAMPOS_NOVOS.")

provedor_saida = saida.dataProvider()
provedor_saida.addAttributes(
    [camada_oae.fields().at(i) for i in indices_oae_mantidos] + definicao_campos_novos)
saida.updateFields()


# -----------------------------------------------------------------------------
# 7) PROCESSAMENTO DAS OAEs
# -----------------------------------------------------------------------------
contagem = Counter()
contagem_status = Counter()
motivos_sem_associacao = Counter()
motivos_km_nulo = Counter()


def processar_oae(oae):
    """Associa a OAE a um trecho, calcula o km e devolve os valores dos campos novos.

    Atualiza os contadores do resumo. Devolve dict campo -> valor, com todos os
    nomes de CAMPOS_NOVOS.
    """
    valores = dict.fromkeys(CAMPOS_NOVOS)
    base = raio_base(oae[CAMPO_EXTENSAO], mediana_extensao)
    via = normalizar_via(oae[CAMPO_VIA])
    if via is None:
        contagem["VIA_NAO_NORMALIZAVEL"] += 1

    geometria_oae = geometria_pontual_metrica(oae, transformacao_oae)
    if geometria_oae is None:
        por_codigo, raio = {}, base * FATOR_RAIO
        codigo, criterio = None, "SEM_TRECHO"
        causa, rodovias_coinc = "GEOMETRIA_OAE_INVALIDA_OU_MULTIPONTO", None
    else:
        por_codigo, raio, ampliado = buscar_em_etapas(
            lambda r: coletar_candidatos(geometria_oae, r), base)
        if ampliado:
            contagem["RAIO_AMPLIADO"] += 1
            if por_codigo:
                contagem["RAIO_AMPLIADO_COM_TRECHO"] += 1
        codigo, criterio, causa, rodovias_coinc = selecionar_codigo(
            por_codigo, via, trechos_snv, geometria_oae)

    if criterio not in CRITERIOS_VALIDOS:
        raise RuntimeError(f"Criterio interno invalido: {criterio}")
    # Pos-condicao: todo codigo atribuido pertence a Via e esta na menor
    # distancia entre os compativeis. Falhar aqui e defeito do script.
    if codigo is not None:
        compativeis = [r["distancia"] for c, r in por_codigo.items() if prefixo_codigo(c) == via]
        if (via is None or prefixo_codigo(codigo) != via or not quase_igual(
                por_codigo[codigo]["distancia"], min(compativeis), TOLERANCIA_EMPATE_DISTANCIA_M)):
            raise RuntimeError("Selecao violou compatibilidade da Via ou menor distancia.")

    status = status_validacao(criterio, oae[CAMPO_RELACAO_SNV], len(por_codigo))
    valores[CAMPO_RAIO_SNV] = raio
    valores[CAMPO_QTD_CODIGOS] = len(por_codigo)
    valores[CAMPO_CRITERIO] = TEXTO_CRITERIO[criterio]
    valores[CAMPO_STATUS] = status
    valores[CAMPO_RODOVIAS_COINC] = truncar_texto(rodovias_coinc, TAMANHO_MAX_TEXTO)
    contagem[criterio] += 1
    contagem_status[status] += 1
    if rodovias_coinc:
        contagem["COINCIDENCIA_DETECTADA"] += 1
        if ";" not in rodovias_coinc:
            # Sobreposicao entre codigos da MESMA BR: geometria duplicada no
            # SNV, e nao coincidencia entre rodovias.
            contagem["COINCIDENCIA_MESMA_BR"] += 1

    if codigo is None:
        motivos_sem_associacao[f"{criterio}:{causa}"] += 1
        return valores

    registro = por_codigo[codigo]
    mais_proximas = registro["feicoes_mais_proximas"]
    valores[CAMPO_TRECHO_SNV] = codigo
    valores[CAMPO_DIST_SNV] = round(registro["distancia"], 3)

    # Atributos do trecho, lidos junto do Trecho_SNV (e nao apenas quando o km
    # e calculado), das feicoes do codigo mais proximas da OAE.
    for campo, chave, tamanho in (
            (CAMPO_VERSAO_SNV, "versao", TAMANHO_VERSAO_SNV),
            (CAMPO_ADMINISTRACAO, "administracao", TAMANHO_ADMINISTRACAO),
            (CAMPO_JURISDICAO, "jurisdicao", TAMANHO_JURISDICAO)):
        valor, divergente = valor_unanime(trechos_snv[fid][chave] for fid, _ in mais_proximas)
        valores[campo] = truncar_texto(valor, tamanho)
        if divergente:
            contagem["ATRIBUTO_TRECHO_DIVERGENTE"] += 1

    # km: a geometria usada precisa ser unica. Empate entre feicoes do mesmo
    # codigo nao e desfeito, pois escolher uma delas arbitraria o km.
    km = None
    if len(mais_proximas) != 1:
        motivo = "EMPATE_DE_GEOMETRIAS_DO_MESMO_CODIGO"
    else:
        trecho = trechos_snv[mais_proximas[0][0]]
        motivo = trecho["erro"]
        if motivo is None:
            km = calcular_km(geometria_oae, trecho["linha"], trecho["ki"], trecho["kf"])
            if km is None:
                motivo = "FALHA_NA_PROJECAO"
    if km is None:
        contagem["KM_NAO_DETERMINADO"] += 1
        motivos_km_nulo[motivo] += 1
    else:
        valores[CAMPO_KM_SNV] = round(km, 3)
        contagem["KM_CALCULADO"] += 1
    return valores


novas_feicoes = []
for oae in camada_oae.getFeatures():
    valores = processar_oae(oae)
    atributos = oae.attributes()
    nova = QgsFeature(saida.fields())
    nova.setGeometry(QgsGeometry(oae.geometry()))
    nova.setAttributes([atributos[i] for i in indices_oae_mantidos]
                       + [valores[campo] for campo in CAMPOS_NOVOS])
    novas_feicoes.append(nova)

if not provedor_saida.addFeatures(novas_feicoes)[0] or saida.featureCount() != len(novas_feicoes):
    raise RuntimeError("Falha na gravacao das OAEs na camada de saida.")
saida.updateExtents()
projeto.addMapLayer(saida)


# -----------------------------------------------------------------------------
# 8) RESUMO
# -----------------------------------------------------------------------------
total = len(novas_feicoes)
associadas = sum(contagem[c] for c in ("UNICO_TRECHO", "TRECHO_COINCIDENTE", "TRECHO_FRONTEIRA"))
sem_associacao = total - associadas
if (sum(contagem[c] for c in CRITERIOS_VALIDOS) != total
        or contagem["KM_CALCULADO"] + contagem["KM_NAO_DETERMINADO"] != associadas
        or sum(motivos_km_nulo.values()) != contagem["KM_NAO_DETERMINADO"]
        or sum(motivos_sem_associacao.values()) != sem_associacao
        or sum(contagem_status.values()) != total):
    raise RuntimeError("Inconsistencia nas somatorias do resumo.")

linha_div = "=" * 72
print(linha_div)
print(f"ASSOCIACAO OAE x SNV - camada {NOME_CAMADA_SAIDA}")
print(linha_div)
for criterio in CRITERIOS_VALIDOS:
    print(f"  {TEXTO_CRITERIO[criterio] + ':':24}{contagem[criterio]}")
print(f"  {'Total de OAEs:':24}{total}")
print(f"  {'Associadas:':24}{associadas}")
print(f"  {'Sem trecho atribuido:':24}{sem_associacao}")
for motivo, quantidade in sorted(motivos_sem_associacao.items()):
    print(f"      {motivo}: {quantidade}")
print(f"  {STATUS_VALIDADO + ':':24}{contagem_status[STATUS_VALIDADO]}")
print(f"  {STATUS_A_VALIDAR + ':':24}{contagem_status[STATUS_A_VALIDAR]}")
print(f"  Raio ampliado (fator {FATOR_RAIO_AMPLIADO}): {contagem['RAIO_AMPLIADO']} OAEs,"
      f" {contagem['RAIO_AMPLIADO_COM_TRECHO']} com trecho encontrado")
print(f"  OAEs com Via ausente/nao normalizavel: {contagem['VIA_NAO_NORMALIZAVEL']}")
print(f"  Mediana das extensoes validas: {mediana_extensao:.3f} m")
print()
print("QUILOMETRO")
print(f"  Calculado: {contagem['KM_CALCULADO']}")
print(f"  Nao calculado (com trecho): {contagem['KM_NAO_DETERMINADO']}")
for motivo, quantidade in sorted(motivos_km_nulo.items()):
    print(f"      {motivo}: {quantidade}")
print()
print("RODOVIAS COINCIDENTES E ATRIBUTOS DO TRECHO")
print(f"  OAEs com coincidencia detectada: {contagem['COINCIDENCIA_DETECTADA']}")
print(f"      entre codigos da mesma BR (geometria duplicada): {contagem['COINCIDENCIA_MESMA_BR']}")
print(f"  Versao/Administracao/Jurisdicao divergentes entre geometrias empatadas:"
      f" {contagem['ATRIBUTO_TRECHO_DIVERGENTE']} ocorrencias")
print()
print("TRECHOS SNV")
for situacao, quantidade in sorted(resumo_trechos.items()):
    print(f"  {situacao}: {quantidade}")
print(f"  Sem geometria ou com falha de reprojecao: {snv_descartadas_geometria}")
print()
print("COLUNAS DA SGE NAO COPIADAS: " + (", ".join(campos_oae_excluidos) or "nenhuma"))
if campos_oae_nao_encontrados:
    print("  ATENCAO - pedidas para exclusao, mas ausentes na SGE: "
          + ", ".join(campos_oae_nao_encontrados))
print(f"PARAMETROS: {CRS_METRICA.authid()}; FATOR_RAIO={FATOR_RAIO};"
      f" FATOR_RAIO_AMPLIADO={FATOR_RAIO_AMPLIADO};"
      f" TOLERANCIA_EMPATE_DISTANCIA_M={TOLERANCIA_EMPATE_DISTANCIA_M}")
print(linha_div)
