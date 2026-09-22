# -*- coding: utf-8 -*-
# =============================================================================
# TRECHOS COINCIDENTES DECLARADOS NO SNV - QGIS / PyQGIS
# =============================================================================
#
# 1. OBJETIVO
# -----------------------------------------------------------------------------
# Extrair da camada SNV os trechos que o proprio dado DECLARA como coincidentes
# e resumir essa declaracao aos numeros de BR envolvidos.
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
# O procedimento e puramente ATRIBUTIVO: nao ha medicao, projecao ou prova
# geometrica de sobreposicao. Ele reporta o que a base afirma, nao o que a
# geometria demonstra. Essa distincao e deliberada e importa para a leitura do
# resultado: associacao_oae_snv.py resolve coincidencia por prova geometrica
# (codigos_sobrepostos / Rodovias_coincidentes) e NAO le "ds_coinc". Esta saida
# existe justamente para permitir confrontar as duas visoes - o declarado e o
# provado - sem que uma contamine a outra.
#
#
# 2. DADOS DE ENTRADA
# -----------------------------------------------------------------------------
#   Camada SNV (linear), nome em NOME_CAMADA_SNV:
#       - CAMPO_DS_COINC ("ds_coinc") : lista de codigos coincidentes separados
#         por ";" (ex.: "010BDF0015;020BDF0015"). Vazia ou com um unico codigo
#         quando o trecho nao e coincidente.
#
#   A camada precisa estar carregada no projeto aberto do QGIS. O script e para
#   ser executado no Console Python do QGIS.
#
#
# 3. DADOS DE SAIDA
# -----------------------------------------------------------------------------
#   Camada em memoria NOME_CAMADA_SAIDA ("Trechos_Coincidentes"), no mesmo tipo
#   de geometria e no mesmo SRC da SNV de origem, contendo:
#       - TODOS os campos originais da SNV, com os valores originais;
#       - CAMPO_TRECHOS_COINC ("Trechos-coinc"): prefixos de tres digitos dos
#         codigos de "ds_coinc", separados por ";", NA ORDEM EM QUE APARECEM no
#         campo de origem e com as repeticoes preservadas.
#
#   Somente feicoes com MINIMO_CODIGOS ou mais codigos em "ds_coinc" entram na
#   saida. A camada de origem nao e modificada.
#
#
# 4. CRITERIOS
# -----------------------------------------------------------------------------
#   4.1 Selecao
#       Entra na saida a feicao cujo "ds_coinc", depois de descartados os tokens
#       vazios, apresentar MINIMO_CODIGOS (2) ou mais codigos. "Mais de um
#       codigo" e contado sobre os codigos declarados, antes de qualquer juizo
#       sobre a forma deles: a coincidencia e um fato do dado de origem e nao
#       pode depender de o codigo estar bem formado.
#
#   4.2 Prefixo
#       O SNV codifica a BR nas tres primeiras posicoes do codigo do trecho.
#       Exigem-se tres DIGITOS, mesma regra de prefixo_codigo em
#       associacao_oae_snv.py: um token fora do padrao nao produz BR e e
#       descartado, sendo contabilizado no resumo. Se nenhum prefixo sobrar,
#       CAMPO_TRECHOS_COINC fica NULL - a feicao permanece na saida, porque ela
#       E coincidente; apenas nao foi possivel nomear as BRs.
#
#   4.3 Ordem e repeticao
#       A ordem original e preservada e as repeticoes NAO sao removidas. O campo
#       e um resumo fiel de "ds_coinc", e nao um conjunto normalizado: ordenar
#       ou deduplicar descartaria a correspondencia posicional com o codigo de
#       origem, que e o que torna o resultado conferivel feicao a feicao.
#
# =============================================================================

from collections import Counter

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
    NULL,
)


# -----------------------------------------------------------------------------
# 0) CONFIGURACAO
# -----------------------------------------------------------------------------
NOME_CAMADA_SNV = "SNV_202607A"
NOME_CAMADA_SAIDA = "Trechos_Coincidentes"

CAMPO_DS_COINC = "ds_coinc"
CAMPO_TRECHOS_COINC = "Trechos-coinc"

# Separador usado pelo SNV dentro de ds_coinc.
SEPARADOR_CODIGOS = ";"

# "Mais de um codigo": dois ou mais codigos declarados apos o descarte dos
# tokens vazios.
MINIMO_CODIGOS = 2

# Mesmo limite conservador adotado em associacao_oae_snv.py: 254 caracteres
# mantem a saida exportavel para Shapefile/DBF sem perda silenciosa.
TAMANHO_MAX_TRECHOS = 254

# Quantos conjuntos de prefixos sao listados no resumo final.
LIMITE_RESUMO_PREFIXOS = 10


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
if CAMPO_DS_COINC not in campos_snv:
    raise Exception(f"Campo ausente em {NOME_CAMADA_SNV}: {CAMPO_DS_COINC}")
# Dois campos homonimos na saida seriam indistinguiveis na tabela de atributos e
# o valor calculado poderia ser lido como se fosse dado de origem.
if CAMPO_TRECHOS_COINC in campos_snv:
    raise Exception(
        f'A camada "{NOME_CAMADA_SNV}" ja possui o campo "{CAMPO_TRECHOS_COINC}".'
    )


# -----------------------------------------------------------------------------
# 3) CAMADA DE SAIDA
# -----------------------------------------------------------------------------
# A saida permanece no SRC ORIGINAL da SNV: nada aqui e medido, portanto nao ha
# motivo para reprojetar.
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
combinacoes = Counter()
novas_feicoes = []

for trecho in camada_snv.getFeatures():
    contagem["TOTAL"] += 1

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
    else:
        combinacoes[texto_prefixos] += 1

    nova = QgsFeature(saida.fields())
    nova.setGeometry(QgsGeometry(trecho.geometry()))
    nova.setAttributes(trecho.attributes() + [None])
    nova.setAttribute(idx_trechos_coinc, texto_prefixos)
    novas_feicoes.append(nova)

# addFeatures devolve (bool, lista); testar a tupla inteira daria sempre
# verdadeiro e engoliria a falha de gravacao.
if novas_feicoes and not provedor_saida.addFeatures(novas_feicoes)[0]:
    raise RuntimeError("Falha ao gravar as feicoes na camada de saida.")
saida.updateExtents()
projeto.addMapLayer(saida)


# -----------------------------------------------------------------------------
# 5) RESUMO E CONFERENCIA
# -----------------------------------------------------------------------------
print(f'Camada de origem : {NOME_CAMADA_SNV} ({contagem["TOTAL"]} trechos lidos)')
print(f'Camada criada    : {NOME_CAMADA_SAIDA} ({contagem["SELECIONADOS"]} trechos)')
print(f'  sem {CAMPO_DS_COINC} preenchido : {contagem["SEM_DS_COINC"]}')
print(f'  com codigo unico        : {contagem["CODIGO_UNICO"]}')
print(f'  codigos fora do padrao  : {contagem["CODIGO_FORA_DO_PADRAO"]}')
print(f'  {CAMPO_TRECHOS_COINC} nulo    : {contagem["SEM_PREFIXO_VALIDO"]}')

if contagem["SELECIONADOS"] != len(novas_feicoes):
    raise RuntimeError("Contagem de selecionados divergente das feicoes gravadas.")
if saida.featureCount() != len(novas_feicoes):
    raise RuntimeError("A camada de saida nao recebeu todas as feicoes selecionadas.")

if combinacoes:
    print(f"Combinacoes de BR mais frequentes (ate {LIMITE_RESUMO_PREFIXOS}):")
    # Ordena por frequencia decrescente e, no empate, pelo texto: a listagem e
    # apenas de conferencia e precisa ser reproduzivel entre execucoes.
    ordenadas = sorted(combinacoes.items(), key=lambda item: (-item[1], item[0]))
    for texto, quantidade in ordenadas[:LIMITE_RESUMO_PREFIXOS]:
        print(f"  {texto}: {quantidade}")
