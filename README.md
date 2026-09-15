# SNV-OAE — Associação de OAEs à malha rodoviária federal

Script PyQGIS que localiza Obras de Arte Especiais (OAEs) sobre a malha
rodoviária do SNV: identifica o trecho a que cada obra pertence e calcula o seu
quilômetro.

Arquivo principal: **`associacao_oae_snv.py`**.

---

## O que o script faz

Para cada OAE da camada SGE, executa duas etapas encadeadas:

1. **Associação** — identifica **um único** código de trecho do SNV
   (`vl_codigo`) ao qual a OAE pertence, ou registra explicitamente por que isso
   não foi possível.
2. **Quilometragem** — calcula o quilômetro da OAE (`km_SNV`) dentro do trecho
   selecionado, por interpolação linear entre `vl_km_inic` e `vl_km_fina`,
   respeitando o sentido crescente da quilometragem.

O procedimento é **determinístico**: o resultado não depende da ordem de leitura
das feições em nenhuma das camadas. Toda decisão exige um vencedor único; onde
não há critério objetivo que separe os candidatos, a OAE fica sem trecho — o
desempate por ordem de leitura é proibido.

Todas as medições ocorrem em SRC métrico (EPSG:5880, SIRGAS 2000 / Polycônica
do Brasil). As camadas de entrada podem estar em qualquer SRC válido.

## Dados de entrada

Duas camadas precisam estar carregadas no projeto QGIS, com os nomes definidos
em `NOME_CAMADA_OAE` e `NOME_CAMADA_SNV`.

| Camada | Geometria | Campos obrigatórios |
|---|---|---|
| **SGE** (OAEs) | pontual | `Extensão (m)`, `Via` |
| **SNV** (rodovias) | linear | `vl_codigo`, `vl_km_inic`, `vl_km_fina`, `vl_br`, `sg_uf`, `sg_tipo_tr` |

A extensão da OAE serve apenas para dimensionar o raio de busca — nunca para
decidir o trecho. `vl_br` + `sg_uf` + `sg_tipo_tr` formam a **chave de
continuidade**: só trechos com a mesma chave são considerados vizinhos.

## Saída

Uma camada em memória (`NOME_CAMADA_SAIDA`) com todos os campos originais da
OAE mais nove campos de resultado e rastreabilidade:

| Campo | Tipo | Conteúdo |
|---|---|---|
| `Trecho_SNV` | texto | `vl_codigo` selecionado, ou NULL |
| `km_SNV` | real | quilômetro interpolado, ou NULL |
| `Dist_SNV_m` | real | distância, em metros, da OAE ao trecho atribuído |
| `Raio_SNV` | real | raio de busca aplicado àquela OAE |
| `Qtd_Codigos` | inteiro | quantidade de `vl_codigo` distintos no raio |
| `Rodovias_coincidentes` | texto | BRs em **sobreposição comprovada** no local (ex.: `116;101`); NULL sem coincidência |
| `Criterio` | texto | um dos seis critérios abaixo |
| `Sentido_KM` | texto | `INICIO_GEOM_KM_INIC`, `INICIO_GEOM_KM_FINAL`, `NAO_DETERMINADO` ou `NAO_APLICAVEL` |
| `Obs_SNV` | texto | trilha de rastreabilidade: distâncias, margens, códigos concorrentes e causas |

O script também imprime três resumos conferidos por somatórias: associação,
quilometragem e diagnóstico de sentido dos trechos SNV.

## Critérios de classificação

Mutuamente exclusivos e exaustivos, avaliados **nesta ordem**:

| Critério | Condição |
|---|---|
| `SEM_TRECHO` | geometria da OAE inválida, ou nenhum `vl_codigo` válido dentro do raio |
| `UNICO_TRECHO` | exatamente um código no raio, **e** compatível com a `Via` |
| `TRECHO_DIVERGENTE` | nenhum código do raio é compatível com a `Via`, ou a `Via` está ausente |
| `TRECHO_EMPATE` | dois ou mais códigos compatíveis à **mesma distância** da OAE |
| `TRECHO_COINCIDENTE` | vencedor único que compartilha porção linear local com outro código equidistante |
| `TRECHO_FRONTEIRA` | vencedor único por menor distância, sem coincidência comprovada |

A compatibilidade com a `Via` declarada da OAE é **pré-condição universal**:
nenhum código de BR diferente é atribuído, ainda que seja o único no raio.
A distância é critério de desempate *dentro* do conjunto compatível, nunca de
admissão.

## Determinação do sentido e cálculo do km

O sentido é propriedade do **trecho**, não da OAE, e é resolvido uma única vez
para toda a SNV antes do laço das obras. Um trecho vizinho cujo `vl_km_fina`
coincide com o `vl_km_inic` do trecho avaliado identifica o extremo de km
inicial; um vizinho posterior identifica o extremo final. A evidência precisa
ser única e não contraditória — caso contrário o sentido fica
`NAO_DETERMINADO` e **o km não é calculado**. Nenhum quilômetro é arbitrado sem
evidência de continuidade.

Havendo sentido, a OAE é projetada ortogonalmente sobre o eixo, obtém-se sua
posição relativa ao longo da geometria e o km é interpolado entre os limites
declarados do trecho.

## Como executar

1. Carregue as camadas SGE e SNV no projeto QGIS.
2. Confira os nomes em `NOME_CAMADA_OAE` e `NOME_CAMADA_SNV`, no início do
   script.
3. Execute `associacao_oae_snv.py` no Console Python do QGIS.

A camada de saída é adicionada ao projeto e os resumos são impressos no console.

## Principais parâmetros

Todos no início do arquivo:

| Parâmetro | Valor | Função |
|---|---|---|
| `CRS_METRICA` | EPSG:5880 | SRC de todas as medições |
| `FATOR_RAIO` | 2.0 | multiplicador do raio de busca |
| `TOLERANCIA_CONEXAO_M` | 1.0 | distância máxima entre extremos para considerar dois trechos conectados |
| `TOLERANCIA_EMPATE_DISTANCIA_M` | 1e-8 | tolerância numérica de equidistância |
| `DISTANCIA_MAXIMA_ASSOCIACAO_M` | `None` | limite duro opcional de associação (desativado) |

O raio de busca de cada OAE é `max(extensão, mediana das extensões) ×
FATOR_RAIO`. A mediana funciona como piso, protegendo obras com extensão
ausente ou inválida sem inflar o raio das demais.

## Testes

As funções sem dependência do QGIS são extraídas do script e exercitadas fora
do ambiente QGIS:

```bash
python3 testes/teste_funcoes_puras.py     # 45 verificações
python3 testes/teste_classificacao.py     # 55 verificações
```

Cobrem a normalização de dados, a determinação do sentido, os seis critérios e
as invariantes do procedimento — entre elas a compatibilidade obrigatória com a
`Via` e a independência do resultado frente à ordem de leitura das feições.

## Limitações conhecidas

- **Não há distância máxima de associação.** O raio delimita a busca, não a
  validade; o campo `Dist_SNV_m` permite avaliar cada associação.
- **A compatibilidade compara apenas o número da BR**, não a UF embutida no
  `vl_codigo`. Em divisas estaduais, um trecho da mesma BR em UF vizinha é
  candidato válido.
- **A chave de vizinhança é restritiva.** Em divisas e mudanças de tipo de
  trecho a cadeia se rompe, e o sentido pode ficar indeterminado.
- **A interpolação pressupõe proporcionalidade** entre comprimento geométrico e
  quilometragem declarada. Desvios acima de 10% são sinalizados em `Obs_SNV`.
- **A detecção de coincidência espelha o critério.** Rodovias coincidentes com
  geometrias digitalizadas alguns centímetros distantes não satisfazem a
  equidistância exigida e não aparecem em `Rodovias_coincidentes`.
