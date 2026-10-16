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
   selecionado, por interpolação linear entre `vl_km_inic` e `vl_km_fina`. O
   sentido crescente do km é o sentido em que a linha do trecho está
   digitalizada.

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
| **SNV** (rodovias) | linear (`LineString`) | `vl_codigo`, `vl_km_inic`, `vl_km_fina`, `ds_tipo_ad`, `ds_jurisdi` |

A extensão da OAE serve apenas para dimensionar o raio de busca — nunca para
decidir o trecho. Cada trecho SNV deve estar digitalizado no sentido crescente
do km: o primeiro vértice corresponde a `vl_km_inic` e o último a `vl_km_fina`.

## Saída

Uma camada em memória (`NOME_CAMADA_SAIDA`) com todos os campos originais da
OAE mais dez campos de resultado e rastreabilidade:

| Campo | Tipo | Conteúdo |
|---|---|---|
| `Trecho_SNV` | texto | `vl_codigo` selecionado, ou NULL |
| `Administracao` | texto | `ds_tipo_ad` do trecho atribuído, ou NULL |
| `Jurisdicao` | texto | `ds_jurisdi` do trecho atribuído, ou NULL |
| `km_SNV` | real | quilômetro interpolado, ou NULL |
| `Dist_SNV_m` | real | distância, em metros, da OAE ao trecho atribuído |
| `Raio_SNV` | real | raio de busca aplicado àquela OAE |
| `Qtd_Codigos` | inteiro | quantidade de `vl_codigo` distintos no raio |
| `Rodovias_coincidentes` | texto | BRs em **sobreposição comprovada** no local (ex.: `116;101`); NULL sem coincidência |
| `Criterio` | texto | um dos seis critérios abaixo |
| `Obs_SNV` | texto | trilha de rastreabilidade: distâncias, margens, códigos concorrentes e causas |

`Administracao` e `Jurisdicao` são lidos da SNV no momento em que o
`Trecho_SNV` é atribuído, da feição do código mais próxima da OAE. Ficam
preenchidos mesmo quando o km não pode ser calculado. Se duas feições do mesmo
código estiverem à mesma distância e discordarem nesses valores, o campo fica
NULL e a divergência é registrada em `Obs_SNV`.

O script também imprime resumos conferidos por somatórias: associação,
quilometragem, rodovias coincidentes e situação dos trechos SNV para o cálculo
do km.

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

## Cálculo do km

Os trechos do SNV são `LineString` digitalizadas no sentido crescente da rota,
então a própria ordem dos vértices define o sentido do km. Não há consulta a
trechos vizinhos nem a outros atributos.

Atribuído o trecho, a OAE é projetada ortogonalmente sobre a linha e obtém-se
sua posição relativa (`fração`), de 0 no primeiro vértice a 1 no último:

```
km_SNV = vl_km_inic + fração × (vl_km_fina − vl_km_inic)
```

O km fica NULL, com a causa registrada em `Obs_SNV`, quando:

- duas feições do mesmo código estão à mesma distância da OAE;
- o intervalo de km do trecho é inválido (ausente, negativo ou
  `vl_km_fina` ≤ `vl_km_inic`);
- a geometria tem duas ou mais partes (`GEOMETRIA_SNV_MULTIPARTE`) — juntá-las
  poderia inverter a ordem dos vértices e, com ela, o sentido;
- a projeção falha.

Uma `MultiLineString` com uma única parte é aceita e usada como está.

### Coerência com a SNV e aviso de sentido suspeito

O km é coerente com a **geometria do trecho atribuído**. Se a SNV estiver
errada, o km acompanha o erro; corrigida a SNV, uma nova execução corrige o km.

Para que esses erros não passem em silêncio, cada trecho é comparado com a
sequência de km dos vizinhos da mesma BR: o vizinho anterior deveria tocar o
primeiro vértice e o posterior, o último. Quando isso não acontece, `Obs_SNV`
recebe um aviso, **e o km continua sendo calculado pela geometria**:

| Aviso | Situação |
|---|---|
| `TRECHO_SNV_POSSIVELMENTE_INVERTIDO` | os vizinhos estão no extremo oposto ao esperado — o km sai espelhado dentro do trecho |
| `TRECHO_SNV_CONTINUIDADE_CONTRADITORIA` | anterior e posterior tocam o mesmo extremo |

Vizinhos são trechos da mesma BR (prefixo do `vl_codigo`), com outro código,
cujo km de emenda coincide ao metro e cujos extremos estão a até 1 m. Trecho
sem vizinho não tem com o que ser comparado e não recebe aviso. O resumo do
console mostra quantos trechos e quantas OAEs foram sinalizados.

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
| `TOLERANCIA_EMPATE_DISTANCIA_M` | 1e-8 | tolerância numérica de equidistância |
| `TOLERANCIA_CONEXAO_M` | 1.0 | distância máxima entre extremos de trechos vizinhos (só no aviso de sentido) |
| `DISTANCIA_MAXIMA_ASSOCIACAO_M` | `None` | limite duro opcional de associação (desativado) |

O raio de busca de cada OAE é `max(extensão, mediana das extensões) ×
FATOR_RAIO`. A mediana funciona como piso, protegendo obras com extensão
ausente ou inválida sem inflar o raio das demais.

## Testes

As funções sem dependência do QGIS são extraídas do script e exercitadas fora
do ambiente QGIS:

```bash
python3 testes/teste_funcoes_puras.py     # 75 verificações
python3 testes/teste_classificacao.py     # 66 verificações
```

Cobrem a normalização de dados, o preparo dos trechos, a interpolação do km e
o aviso de sentido suspeito,
os seis critérios e
as invariantes do procedimento — entre elas a compatibilidade obrigatória com a
`Via` e a independência do resultado frente à ordem de leitura das feições.

## Limitações conhecidas

- **Não há distância máxima de associação.** O raio delimita a busca, não a
  validade; o campo `Dist_SNV_m` permite avaliar cada associação.
- **A compatibilidade compara apenas o número da BR**, não a UF embutida no
  `vl_codigo`. Em divisas estaduais, um trecho da mesma BR em UF vizinha é
  candidato válido.
- **O sentido do km depende da digitalização.** Um trecho digitalizado contra
  o km produz km espelhado dentro do trecho
  (`vl_km_inic + vl_km_fina − km correto`). O caso é sinalizado em `Obs_SNV`
  quando os vizinhos o evidenciam; um trecho isolado, sem vizinhos, passa sem
  aviso.
- **A interpolação pressupõe proporcionalidade** entre comprimento geométrico e
  quilometragem declarada. Desvios acima de 10% são sinalizados em `Obs_SNV`.
- **A detecção de coincidência espelha o critério.** Rodovias coincidentes com
  geometrias digitalizadas alguns centímetros distantes não satisfazem a
  equidistância exigida e não aparecem em `Rodovias_coincidentes`.
