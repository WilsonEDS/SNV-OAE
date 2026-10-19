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
   selecionado, por interpolação linear entre `vl_km_inic` e `vl_km_fina`, no
   sentido em que a linha do trecho está digitalizada.

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
| **SGE** (OAEs) | pontual | `Extensão (m)`, `Via`, `Relacao_SNV` |
| **SNV** (rodovias) | linear (`LineString`) | `vl_codigo`, `vl_km_inic`, `vl_km_fina`, `ds_tipo_ad`, `ds_jurisdi`, `versao_snv` |

Os nomes de campo são localizados sem distinguir acento, maiúsculas, `_` ou
espaços, e também pelo alias exibido na tabela de atributos: `Versão SNV` e
`versao_snv` são o mesmo campo. Se um campo obrigatório não for encontrado, a
mensagem de erro lista os campos da camada e os mais parecidos.

A extensão da OAE serve apenas para dimensionar o raio de busca — nunca para
decidir o trecho. Em cada trecho SNV, o primeiro vértice da linha corresponde a
`vl_km_inic` e o último a `vl_km_fina`.

## Saída

Uma camada em memória chamada **`SGExSNV`** com os campos originais da OAE
seguidos de onze campos criados, nesta ordem:

| Campo | Tipo | Conteúdo |
|---|---|---|
| `Trecho_SNV` | texto | `vl_codigo` selecionado, ou NULL |
| `Versao_SNV` | texto | `versao_snv` do trecho atribuído — com qual versão da SNV o km foi calculado |
| `Administracao` | texto | `ds_tipo_ad` do trecho atribuído, ou NULL |
| `Jurisdicao` | texto | `ds_jurisdi` do trecho atribuído, ou NULL |
| `km_SNV` | real | quilômetro interpolado, ou NULL |
| `Rodovias_coincidentes` | texto | BRs em **sobreposição comprovada** no local (ex.: `116;101`); NULL sem coincidência |
| `Status` | texto | `Validado` ou `A validar` (ver abaixo) |
| `Criterio` | texto | um dos seis critérios abaixo, em texto legível |
| `Dist_SNV_m` | real | distância, em metros, da OAE ao trecho atribuído |
| `Raio_SNV` | real | raio de busca efetivamente usado para a OAE (fator 2 ou 5) |
| `Qtd_Codigos` | inteiro | quantidade de `vl_codigo` distintos no raio |

Os textos de `Criterio` e `Status` saem em português, com só a primeira letra
maiúscula. As causas de não associação e de km nulo não vão para a camada:
aparecem, contadas, no resumo do console.

### Status

Reproduz a fórmula da planilha de conferência:

```
=SE(OU(E(Criterio="UNICO_TRECHO"; Relacao_SNV="L");
       E(Criterio="TRECHO_COINCIDENTE"; Qtd_Codigos<3)); "VALIDADO"; "A VALIDAR")
```

`Validado` quando a OAE é de **trecho único** e `Relacao_SNV` = `L`, ou de
**trecho coincidente** com menos de três códigos no raio; `A validar` em todos
os demais casos. A comparação com `L` ignora maiúsculas e espaços nas bordas —
neste último ponto difere do Excel, que considera `" L"` diferente de `"L"`.

As colunas `Km`, `Código SNV` e `Versão SNV` da SGE **não são copiadas**: vêm
de uma associação anterior e são substituídas por `km_SNV`, `Trecho_SNV` e
`Versao_SNV`, calculados contra a SNV atual. Se alguma delas não existir na SGE
com esse nome exato, o console avisa.

`Versao_SNV`, `Administracao` e `Jurisdicao` são lidos da SNV no momento em que o
`Trecho_SNV` é atribuído, da feição do código mais próxima da OAE. Ficam
preenchidos mesmo quando o km não pode ser calculado. Se duas feições do mesmo
código estiverem à mesma distância e discordarem nesses valores, o campo fica
NULL e a divergência é contada no resumo do console.

O script também imprime resumos conferidos por somatórias: associação (com
as causas de cada OAE sem trecho e quantas precisaram do raio ampliado),
quilometragem (com as causas de km nulo), rodovias coincidentes e situação dos
trechos SNV para o cálculo do km.

## Critérios de classificação

Mutuamente exclusivos e exaustivos, avaliados **nesta ordem**:

| Critério | Condição |
|---|---|
| Sem trecho | geometria da OAE inválida, ou nenhum `vl_codigo` válido dentro do raio, nem com o fator ampliado |
| Trecho único | exatamente um código no raio, **e** compatível com a `Via` |
| Trecho divergente | nenhum código do raio é compatível com a `Via`, ou a `Via` está ausente |
| Trecho empate | dois ou mais códigos compatíveis à **mesma distância** da OAE |
| Trecho coincidente | vencedor único que compartilha porção linear local com outro código equidistante |
| Trecho fronteira | vencedor único por menor distância, sem coincidência comprovada |

A compatibilidade com a `Via` declarada da OAE é **pré-condição universal**:
nenhum código de BR diferente é atribuído, ainda que seja o único no raio.
A distância é critério de desempate *dentro* do conjunto compatível, nunca de
admissão.

## Cálculo do km

Atribuído o trecho, o sentido do km é o da própria `LineString`: o primeiro
vértice é `vl_km_inic` e o último, `vl_km_fina`. Não há consulta a trechos
vizinhos, tolerâncias nem confronto entre os dados tabulares e a geometria —
essa análise é feita em outra atividade. O que se garante aqui é a coerência
entre o km calculado e os dados do trecho associado.

A OAE é projetada ortogonalmente sobre a linha e obtém-se sua posição relativa
(`fração`), de 0 no primeiro vértice a 1 no último:

```
km_SNV = vl_km_inic + fração × (vl_km_fina − vl_km_inic)
```

O km fica sempre dentro do intervalo do trecho. Se `vl_km_fina` for menor que
`vl_km_inic`, o km continua sendo calculado pela mesma fórmula e decresce ao
longo da linha, coerente com o que o trecho declara.

O km fica NULL somente quando não há como calculá-lo:

- `vl_km_inic` ou `vl_km_fina` ausente;
- a geometria tem duas ou mais partes — juntá-las poderia inverter a ordem dos
  vértices e, com ela, o sentido;
- duas feições do mesmo código estão à mesma distância da OAE;
- a projeção falha.

Uma `MultiLineString` com uma única parte é aceita e usada como está.

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
| `FATOR_RAIO_AMPLIADO` | 5.0 | multiplicador usado só quando não há nenhum trecho no raio normal |
| `TOLERANCIA_EMPATE_DISTANCIA_M` | 1e-8 | tolerância numérica de equidistância |

O raio de busca de cada OAE é `max(extensão, mediana das extensões) ×
FATOR_RAIO`. A mediana funciona como piso, protegendo obras com extensão
ausente ou inválida sem inflar o raio das demais.

Se nenhum `vl_codigo` estiver dentro desse raio, a busca é refeita com
`FATOR_RAIO_AMPLIADO`. A ampliação vale só para esse caso: uma OAE que já tem
trechos no raio normal, ainda que de outra BR, mantém o fator 2.

## Testes

As funções sem dependência do QGIS são extraídas do script e exercitadas fora
do ambiente QGIS:

```bash
python3 testes/teste_funcoes_puras.py     # 133 verificações
python3 testes/teste_classificacao.py     # 59 verificações
```

Cobrem a normalização de dados, o raio em duas etapas, o cálculo do km
(inclusive com limites invertidos), os seis critérios e
as invariantes do procedimento — entre elas a compatibilidade obrigatória com a
`Via` e a independência do resultado frente à ordem de leitura das feições.

## Limitações conhecidas

- **Não há distância máxima de associação.** O raio delimita a busca, não a
  validade; o campo `Dist_SNV_m` permite avaliar cada associação.
- **A compatibilidade compara apenas o número da BR**, não a UF embutida no
  `vl_codigo`. Em divisas estaduais, um trecho da mesma BR em UF vizinha é
  candidato válido.
- **O sentido do km é o da digitalização.** Um trecho digitalizado contra o
  km produz km espelhado dentro do trecho
  (`vl_km_inic + vl_km_fina − km correto`), sem aviso: o km acompanha o dado
  da SNV, e corrigida a SNV, uma nova execução corrige o km.
- **A interpolação pressupõe proporcionalidade** entre comprimento geométrico e
  quilometragem declarada; desvios não são verificados nesta etapa.
- **A detecção de coincidência espelha o critério.** Rodovias coincidentes com
  geometrias digitalizadas alguns centímetros distantes não satisfazem a
  equidistância exigida e não aparecem em `Rodovias_coincidentes`.
