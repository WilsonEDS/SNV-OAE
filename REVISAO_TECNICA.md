# Revisão técnica — Associação OAE (SGE) × SNV e cálculo do `km_SNV`

Documento de apoio à auditoria do script `associacao_oae_snv.py`.
Nenhuma decisão metodológica foi alterada silenciosamente. As duas mudanças que
afetariam critérios estão implementadas como **parâmetros desligados por padrão**
(§1.1 e §1.2), de modo que a execução padrão reproduz exatamente a metodologia
original.

---

## 1. Avaliação técnica

Classificação: **[A]** ambiguidade metodológica · **[E]** erro de programação ·
**[I]** inconsistência lógica · **[R]** risco / ponto de atenção.

### 1.1 [A] `UNICO_TRECHO` não verifica a compatibilidade com a `Via` — **maior achado**

* **Problema.** Em `selecionar_codigo`, o ramo `len(por_codigo) == 1` retorna o
  código antes de qualquer teste de `Via`. O critério de compatibilidade só é
  acionado quando há concorrência (≥ 2 códigos). A verificação de pós-condição
  no laço principal cobre apenas `TRECHO_COINCIDENTE` e `TRECHO_FRONTEIRA`, e
  portanto não detecta o caso.
* **Consequência.** Uma OAE declarada em `BR-116` cujo único trecho no raio seja
  `101BMG…` é associada a **BR-101** e classificada como `UNICO_TRECHO`, sem
  qualquer registro de divergência. O `km_SNV` é então calculado sobre a rodovia
  errada. O critério de `Via` deixa de ser exaustivo: ele vale para OAEs em áreas
  densas e não vale para OAEs isoladas — exatamente onde o erro é menos visível.
  Como o raio de busca chega a 5 × extensão, o efeito não é marginal.
* **Alteração recomendada.** Aplicar o teste de `Via` também com um único código,
  classificando o incompatível como `TRECHO_DIVERGENTE`.
* **Impacto esperado.** Migração de um subconjunto de `UNICO_TRECHO` para
  `TRECHO_DIVERGENTE`, com queda correspondente de `km_SNV` calculado. Nenhuma
  OAE hoje corretamente associada muda de trecho.
* **CORRIGIDO** — alteração autorizada pelo responsável pela metodologia.
  A compatibilidade com a `Via` passou a ser **pré-condição universal** da
  associação: um único trecho no raio é apenas o único candidato disponível, e
  não evidência de que a OAE pertença àquela rodovia. Código único incompatível
  → `TRECHO_DIVERGENTE`, com causa `UNICO_CODIGO_INCOMPATIVEL_COM_VIA` e
  registro de `VIA_OAE`, `CODIGO_NO_RAIO`, `PREFIXO_CODIGO` e `DIST_M` para
  conferência caso a caso. A verificação de pós-condição do laço principal foi
  estendida a `UNICO_TRECHO`, de modo que a invariante passa a ser garantida em
  execução para os três critérios que devolvem código. O parâmetro
  `EXIGIR_VIA_COMPATIVEL_EM_UNICO_TRECHO` foi removido.

#### 1.1.1 Decisões metodológicas registradas

Quatro pontos decorrentes da mudança foram submetidos ao responsável e
decididos:

| # | Questão | Decisão |
|---|---|---|
| 1 | Conjunto que define a cardinalidade de `UNICO_TRECHO` | **Todos os códigos do raio.** Exige `len(por_codigo) == 1` **e** compatibilidade. Com 3 códigos e 1 compatível → `TRECHO_FRONTEIRA`: houve concorrência espacial a documentar |
| 2 | OAE com `Via` ausente/não normalizável | **`TRECHO_DIVERGENTE`**, com causa própria `VIA_AUSENTE_OU_NAO_NORMALIZAVEL`, separada da divergência real |
| 3 | Único compatível que coincide com código de outra BR | **`TRECHO_COINCIDENTE`** prevalece: a coincidência física de dois códigos SNV sobre o mesmo eixo é a informação que a auditoria precisa isolar |
| 4 | `km_SNV` com sentido indeterminado | **Permanece nulo.** Nenhum km é arbitrado sem evidência de continuidade |

As decisões 1 e 3 não conflitam: coincidência exige um *parceiro* — outro
código distinto no raio —, impossível quando `len(por_codigo) == 1`. O cenário
da decisão 3 só ocorre com dois ou mais códigos, onde a decisão 1 já encaminha
para o ramo de concorrência.

**Consequência registrada da decisão 2:** com o filtro obrigatório, toda OAE sem
`Via` utilizável passa a ser não associada. O contador de `Via` não normalizável
já existente no resumo dimensiona esse universo.

### 1.2 [A] Não existe distância máxima de associação

* **Problema.** O raio (`max(extensão, mediana) × 5`) delimita a *busca*, não a
  *validade*. Uma OAE de 3 000 m gera raio de 15 km, e o código mais próximo
  dentro desse raio é aceito sem limite superior de distância.
* **Consequência.** OAEs sobre vias não federais, com coordenada grosseiramente
  errada ou fora da malha, recebem trecho e km com aparência de resultado válido.
  O erro não se distingue de uma associação legítima na tabela de saída.
* **Alteração recomendada.** Definir um limite duro de aceitação, calibrado sobre
  a distribuição observada de `Dist_SNV_m`.
* **Impacto esperado.** Migração de associações remotas para `SEM_TRECHO`, com
  causa registrada.
* **Implementado.** Parâmetro `DISTANCIA_MAXIMA_ASSOCIACAO_M` (padrão `None` =
  desativado, metodologia original) e o novo campo **`Dist_SNV_m`**, que expõe a
  distância efetiva de cada associação e viabiliza a calibração.

### 1.3 [E] `Obs_SNV` podia exceder o comprimento declarado do campo

* **Problema.** O campo é criado com `len=254`, mas a observação era montada por
  concatenação livre (`SOBREPOSICAO_COM=` com muitos códigos + distâncias +
  evidência de sentido), podendo ultrapassar esse limite.
* **Consequência.** Truncamento silencioso ou falha de gravação, conforme o
  provedor — perda de trilha de auditoria sem aviso.
* **Corrigido** (correção de defeito, sem efeito metodológico): `observacao_texto`
  trunca de forma determinística e marca o corte com `...[TRUNCADO]`. Os
  fragmentos passaram a ser ordenados por relevância decrescente (causa da
  decisão primeiro), de modo que o truncamento nunca elimine a informação
  essencial. `TAMANHO_MAX_OBS` é a única fonte do limite, usada tanto na criação
  do campo quanto no corte.

### 1.4 [E] Contagem de campos novos fixada literalmente

* **Problema.** `oae.attributes() + [None] * 7` dependia de um literal casado à
  mão com a lista de campos criados.
* **Consequência.** Qualquer campo adicional desalinha atributos e valores — o
  tipo de defeito que produz coluna deslocada sem erro visível.
* **Corrigido**: a quantidade é derivada de `saida.fields().count() -
  camada_oae.fields().count()`, com verificação explícita da estrutura.

### 1.5 [I] `TRECHO_DIVERGENTE` reunia duas causas distintas

* **Problema.** O motivo único `VIA_INVALIDA_OU_SEM_CODIGO_COMPATIVEL` cobria
  tanto "a OAE não declara `Via` utilizável" quanto "a `Via` é válida e nenhum
  código próximo pertence a ela". São problemas de naturezas opostas: o primeiro
  é falha de cadastro na origem, o segundo é divergência real posição × rodovia.
* **Consequência.** Impossível dimensionar separadamente as duas causas — e,
  portanto, impossível priorizar o saneamento.
* **Corrigido** (auditoria; não altera classificação): causas separadas em
  `VIA_AUSENTE_OU_NAO_NORMALIZAVEL` e `NENHUM_CODIGO_COMPATIVEL_COM_VIA=<BR>`,
  acompanhadas de `CODIGOS_NO_RAIO=`. Um contador de OAEs com `Via` não
  normalizável foi acrescentado ao resumo. Observação: nomear "divergente" o caso
  de `Via` ausente permanece impreciso, mas manter a classe evita criar um sétimo
  critério fora da especificação.

### 1.5.1 [I] `TRECHO_EMPATE` não declarava o fato que o define

* **Problema.** Os motivos gravados (`EMPATE_EXATO_DE_DISTANCIA_ENTRE_CODIGOS_COMPATIVEIS`)
  informavam que houve empate, mas não explicitavam o fato metodológico: **dois
  ou mais códigos compatíveis com a `Via` estão à mesma distância da OAE**, nem
  registravam qual é essa distância.
* **CORRIGIDO.** Descrições reescritas para
  `CODIGOS_COMPATIVEIS_COM_VIA_EQUIDISTANTES_DA_OAE` e
  `CODIGOS_COINCIDENTES_COMPATIVEIS_COM_VIA_EQUIDISTANTES_DA_OAE`, acompanhadas
  de `VIA_OAE=`, `N_EMPATADOS=`, `CODIGOS_EM_EMPATE=` e `DIST_EQUIDISTANTE_M=`.
  A semântica foi documentada na docstring de `selecionar_codigo` e na tabela de
  critérios do cabeçalho: como a compatibilidade já não os separa e a distância
  também não, nenhum critério objetivo resta; o desempate por ordem de leitura é
  proibido e a OAE permanece sem trecho e sem km.

### 1.6 [R] Empates e concorrentes não eram rastreáveis

* **Problema.** `TRECHO_EMPATE` não registrava quais códigos empataram, e
  `TRECHO_COINCIDENTE` não registrava os equidistantes descartados pela regra de
  prioridade. `TRECHO_FRONTEIRA` não indicava a folga da decisão.
* **Consequência.** Casos revisados manualmente exigiam reprocessamento para
  saber o que estava em disputa.
* **Corrigido** (auditoria): `CODIGOS_EM_EMPATE=`, `DESCARTADOS_NO_MINIMO=`,
  `N_CODIGOS=`, `N_COMPATIVEIS=`, `MIN_VIA_M=` e **`MARGEM_M=`** (folga entre o
  1.º e o 2.º código compatível). `MARGEM_M` é a evidência direta da robustez de
  cada `TRECHO_FRONTEIRA`: margem milimétrica indica decisão sensível à precisão
  do traçado e merece verificação.

### 1.7 [R] Interpolação sem verificação de escala geometria × quilometragem

* **Problema.** O `km_SNV` pressupõe proporcionalidade entre comprimento
  geométrico e extensão declarada (`vl_km_fina − vl_km_inic`). No SNV essas
  grandezas divergem com frequência (generalização do traçado, quilometragem
  herdada de versões anteriores). Nada verificava a divergência.
* **Consequência.** Em trechos com divergência relevante, o km interpolado
  acumula erro proporcional ao desvio, sem sinalização. Ao meio do trecho o erro
  aproxima-se de metade da diferença entre as duas medidas.
* **Alteração recomendada.** Não alterar a interpolação — que continua sendo a
  melhor estimativa disponível sem referenciamento linear oficial —, mas
  sinalizar os casos afetados.
* **Implementado** (alerta, não critério): `calcular_km` devolve a razão
  `comprimento_geométrico / extensão_declarada`; desvios acima de
  `TOLERANCIA_ESCALA_KM_GEOM` (10 %) gravam `ALERTA_ESCALA_KM_GEOM=<razão>` em
  `Obs_SNV` e são contabilizados no resumo. **O valor de `km_SNV` não muda.**

### 1.7-b [R] Projeção no extremo do trecho não era sinalizada

* **Problema.** A fração é limitada a [0, 1], o que impede km fora do intervalo
  declarado — mas o caso em que a projeção cai **exatamente** sobre um extremo
  saía indistinguível de um km interpolado no interior do trecho.
* **Consequência.** Uma OAE que na verdade pertence ao trecho vizinho recebe o
  próprio limite declarado como `km_SNV`, com aparência de valor interpolado.
* **CORRIGIDO** (alerta de auditoria; **o valor de `km_SNV` não muda**):
  `PROJECAO_NO_EXTREMO=INICIO_GEOM|FIM_GEOM` em `Obs_SNV` e contador próprio no
  resumo, ao lado de `ALERTA_ESCALA`.

### 1.8 [R] Trecho fechado (anel/retorno) tinha causa mascarada

* **Problema.** Uma linha cujos extremos coincidem não pode ser orientada por
  conectividade — qualquer vizinho que toque um extremo toca o outro. O caso caía
  em `CONEXAO_AMBIGUA` ou `SEM_VIZINHO_COMPATIVEL`, misturando-se a causas
  distintas.
* **Corrigido** (rótulo de auditoria; **resultado idêntico**): causa própria
  `GEOMETRIA_SNV_FECHADA_EXTREMOS_INDISTINGUIVEIS`, com limiar dedicado
  `TOLERANCIA_GEOMETRIA_FECHADA_M = 1e-6 m`.
  *Cuidado deliberado:* o trecho fechado **continua registrado nos índices de
  vizinhança**, permanecendo evidência válida de continuidade para os demais. Se
  fosse removido, a orientação de trechos vizinhos mudaria — e isso seria
  alteração metodológica. O limiar de 1e-6 m (e não os 1,0 m da tolerância de
  conexão) garante que nenhum caso hoje orientável passe a ser bloqueado.

### 1.9 [R] Comparação de `Via` ignora a UF embutida no `vl_codigo`

* **Problema.** `prefixo_codigo` compara apenas os três dígitos da BR. O
  `vl_codigo` também codifica a UF (`116` **B** `MG` `0450`), que não é testada,
  e a camada OAE não fornece UF.
* **Consequência.** Em divisas estaduais, um trecho da mesma BR em UF vizinha é
  candidato plenamente compatível e pode vencer por poucos metros.
* **Recomendação (não implementada — exige dado de entrada inexistente).**
  Incorporar UF à OAE, ou registrar a UF do código escolhido para conferência.
  Enquanto isso, `MARGEM_M` permite isolar as decisões apertadas nessas regiões.

### 1.10 [R] Chave de vizinhança restritiva por construção

* **Problema.** São vizinhos apenas trechos com igual (`vl_br`, `sg_uf`,
  `sg_tipo_tr`). Em divisa de UF e em mudança de tipo de trecho a cadeia se
  rompe, ainda que a quilometragem seja contínua.
* **Consequência.** `SEM_VIZINHO_COMPATIVEL` concentra-se sistematicamente nas
  extremidades de cada agrupamento — origem provável da maior parte dos trechos
  sem orientação. O efeito é conservador (não calcula km em vez de calcular
  errado) e, por isso, **a regra foi mantida**.
* **Recomendação.** Antes de consolidar a metodologia, quantificar quantos
  `SEM_VIZINHO_COMPATIVEL` são divisa/mudança de tipo e avaliar se a chave deve
  relaxar `sg_tipo_tr`. O diagnóstico impresso já fornece a base para isso.

### 1.11 [R] Códigos com múltiplas feições: sem retentativa

* **Problema.** A feição usada para projetar é a de menor distância dentro do
  código. Se essa feição específica não tiver sentido resolvido, o km fica nulo,
  mesmo que outra feição do **mesmo código** esteja orientada.
* **Consequência.** Perda de km recuperável em trechos particionados.
* **Recomendação (não implementada — alteraria a metodologia).** Só faz sentido
  se as feições do código forem partes de uma mesma progressão linear; caso
  contrário, herdar sentido de outra feição arbitra a posição. Mantido o
  comportamento conservador.

### 1.12 [R] Custo do teste de coincidência

* **Problema.** `codigos_sobrepostos` realiza interseções de geometria em laço
  aninhado sobre os códigos do raio, e o mesmo par era reavaliado várias vezes.
* **Corrigido** (desempenho; resultado idêntico): memoização por par de códigos
  dentro da avaliação de cada OAE. O par é normalizado por ordenação, e a função
  é simétrica, de modo que a memoização não altera nenhum resultado.

### 1.13 [E] Entradas degeneradas não verificadas

* SNV sem nenhuma feição válida após a reprojeção produzia índice vazio e
  **todas** as OAEs como `SEM_TRECHO`, sem distinguir "OAE isolada" de "camada
  SNV inutilizável". Agora interrompe com mensagem explícita.
* `QgsWkbTypes.displayString()` com tipo `Unknown`/`NoGeometry` gerava URI
  inválida e camada de memória silenciosamente inválida. Agora há verificação de
  tipo e de `isValid()` para as duas camadas criadas.

### 1.14 Pontos verificados e **corretos** (registrados para a auditoria)

* **Envelope de busca não perde candidatos.** Todo ponto fora do quadrado de
  semilado *r* satisfaz `max(|dx|,|dy|) > r`, logo dista mais que *r*; o quadrado
  contém o círculo e a distância real é reavaliada em seguida.
* **Independência da ordem de leitura.** Distâncias por código são reduzidas por
  `min()` sobre o conjunto completo; toda decisão exige cardinalidade 1; as
  ordenações existentes (`bisect`, `sorted`) servem a consulta e impressão.
  *Verificado por teste sobre todas as permutações de um caso com quatro códigos
  equidistantes: resultado único.*
* **`Via` é filtro duro, distância é desempate interno.** Um código incompatível
  mais próximo nunca vence um compatível mais distante. *Verificado por teste.*
* **Coincidência é localmente comprovada.** Exige interseção linear de
  comprimento positivo situada exatamente na distância mínima de ambos os
  códigos; cruzamento pontual e coincidência remota são rejeitados.
* **Prioridade coincidência → fronteira opera apenas dentro do mínimo**, e o
  mínimo é calculado antes da prioridade, incluindo os não coincidentes.
* **Empate de coincidências não é resgatado por fronteira.** *Verificado.*
* **Sentido nunca é arbitrado**, nem herdado de vizinho: usa-se apenas o fato de
  que o extremo que toca um vizinho anterior é o de km inicial.
* **`addFeatures` retorna tupla no binding Python** — o uso de `[0]` está correto.
* **`fração` limitada a [0, 1]**: nenhum km cai fora do intervalo declarado.
* Os seis critérios são **mutuamente exclusivos e exaustivos**. *Verificado.*
* Todos os `import` do módulo original são efetivamente utilizados.

### 1.15 Restrição numérica registrada

"Equidistante dentro da tolerância" **não é relação transitiva**: com A≈B e B≈C
pode ocorrer A≉C. Com `TOLERANCIA_EMPATE_DISTANCIA_M = 1e-8 m` (10 nm) o efeito
é fisicamente irrelevante, mas fica registrado por integrar formalmente a
definição dos conjuntos `mais_proximos` e `coincidentes`.

---

## 2. Fluxo metodológico consolidado

**Pré-processamento (uma única vez, antes das OAEs).**

1. Validar camadas, tipos geométricos, campos obrigatórios e ausência de colisão
   de nomes na saída.
2. Reprojetar toda a SNV para `EPSG:5880` (SRC métrico) e indexá-la
   espacialmente. Todas as medições ocorrem neste SRC.
3. Calcular a mediana das extensões válidas das OAEs (piso do raio de busca).
4. **Orientar toda a SNV**, trecho a trecho — a orientação é propriedade do
   trecho, não da OAE.

**Determinação do sentido de cada trecho SNV.**

5. Reduzir a geometria a linha simples e contínua (`mergeLines` para multipartes;
   partes desconexas são rejeitadas). Extrair os dois extremos.
6. Buscar vizinhos de mesma chave (`vl_br`, `sg_uf`, `sg_tipo_tr`), excluindo
   feições de mesmo `vl_codigo`:
   * **anterior** — `vl_km_fina` do vizinho ≈ `vl_km_inic` do trecho;
   * **posterior** — `vl_km_inic` do vizinho ≈ `vl_km_fina` do trecho.
   Tolerância de km estritamente numérica (1e-8): lacunas reais não são costuradas.
7. Testar conexão geométrica entre extremos (tolerância 1,0 m). O extremo que
   toca um **anterior** é o de km inicial; o que toca um **posterior** é o de km
   final.
8. Exigir evidência **única e não contraditória**. Caso contrário o sentido é
   `NAO_DETERMINADO`, com causa registrada: `CONEXAO_AMBIGUA`,
   `SEM_VIZINHO_COMPATIVEL`, `VIZINHOS_CONFLITANTES`, `INTERVALO_KM_INVALIDO`,
   `IDENTIFICACAO_SNV_INVALIDA`, `GEOMETRIA_SNV_NAO_E_LINHA_SIMPLES_CONTINUA`,
   `EXTREMOS_SNV_INVALIDOS`, `GEOMETRIA_SNV_FECHADA_EXTREMOS_INDISTINGUIVEIS`.

**Por OAE — `OAE → candidatos SNV → seleção do vl_codigo → classificação`.**

9. Reprojetar o ponto da OAE (multiponto só é aceito com um único ponto).
   Falha ⇒ `SEM_TRECHO`.
10. Raio = `max(extensão, mediana) × 5`. Consultar o índice por envelope,
    reavaliar a **distância real** e descartar o que exceder o raio.
11. Agrupar por `vl_codigo` **distinto**. A distância de um código é a **menor**
    distância entre a OAE e qualquer feição portadora daquele código, calculada
    sobre o conjunto completo de candidatos.
12. Selecionar e classificar, **nesta ordem**:

| # | Condição | Critério |
|---|---|---|
| 1 | nenhum código válido no raio | `SEM_TRECHO` |
| 2a | exatamente um código no raio, **compatível com a `Via`** | `UNICO_TRECHO` |
| 2b | exatamente um código no raio, **incompatível** ou `Via` ausente | `TRECHO_DIVERGENTE` |
| 3 | ≥ 2 códigos e nenhum compatível com a `Via` | `TRECHO_DIVERGENTE` |
| 4 | conjunto vencedor não se reduz a um código | `TRECHO_EMPATE` |
| 5 | vencedor único **com** coincidência local comprovada | `TRECHO_COINCIDENTE` |
| 6 | vencedor único **sem** coincidência local | `TRECHO_FRONTEIRA` |

  Dentro dos casos 3–6: (a) filtrar por compatibilidade de `Via` (prefixo de três
  dígitos do `vl_codigo` = número da BR normalizado); (b) calcular a distância
  **mínima entre todos os compatíveis**, incluindo os não coincidentes;
  (c) formar o conjunto dos equidistantes ao mínimo; (d) dentro dele, identificar
  os que compartilham porção linear de comprimento positivo, situada na distância
  mínima, com outro código equidistante; (e) vencedores = coincidentes, se
  houver, senão os equidistantes; (f) exigir cardinalidade 1.

13. Verificação de pós-condição em execução para `TRECHO_COINCIDENTE` e
    `TRECHO_FRONTEIRA`: código compatível com a `Via` **e** na distância mínima
    entre os compatíveis. Falha interrompe a execução.

**Por OAE — `determinação do sentido → cálculo do km_SNV`.**

14. Selecionar a feição do código escolhido que realiza a menor distância. Empate
    entre feições do mesmo código ⇒ `km_SNV` nulo
    (`EMPATE_DE_GEOMETRIAS_DO_MESMO_CODIGO`).
15. Recuperar o sentido pré-calculado da feição. Ausente ⇒ `km_SNV` nulo, com a
    causa do passo 8.
16. Projetar a OAE ortogonalmente sobre o eixo (`nearestPoint`) e obter a posição
    linear (`lineLocatePoint`). Fração = posição / comprimento, limitada a [0, 1].
17. Interpolar:
    * `INICIO_GEOM_KM_INIC` → `km = ki + fração × (kf − ki)`
    * `INICIO_GEOM_KM_FINAL` → `km = kf + fração × (ki − kf)`
18. Registrar `Dist_SNV_m`, `FRACAO=`, a evidência do sentido (`AMBOS`/
    `ANTERIOR`/`POSTERIOR`) e os códigos vizinhos usados. Sinalizar
    `ALERTA_ESCALA_KM_GEOM` quando comprimento geométrico e extensão declarada
    divergirem mais de 10 %.
19. Conferir as somatórias (grupos = total; calculado + não determinado =
    associadas; causas = totais) e emitir os três resumos.

---

## 3. Código revisado

Arquivo: **`associacao_oae_snv.py`**.

### 3.1 Alterações que **não** afetam a metodologia

| # | Alteração | Natureza |
|---|---|---|
| 1 | Cabeçalho descritivo, docstrings em todas as funções e comentários de justificativa nos pontos críticos | documentação |
| 2 | Truncamento determinístico de `Obs_SNV` com marcador; limite unificado em `TAMANHO_MAX_OBS` | correção (§1.3) |
| 3 | Quantidade de campos novos derivada da estrutura, com verificação | correção (§1.4) |
| 4 | Verificação de SNV vazia após reprojeção; verificação de tipo de geometria e de `isValid()` das camadas criadas | correção (§1.13) |
| 5 | Memoização do teste de sobreposição por par de códigos | desempenho (§1.12) |
| 6 | `normalizar_via` chamada uma única vez por OAE | simplificação |
| 7 | `calcular_km` recebe `ki`/`kf` já validados em vez de reler a feição | consistência |
| 8 | Guarda defensiva antes do cálculo do km | robustez |
| 9 | Novo campo **`Dist_SNV_m`** | auditoria (§1.2) |
| 10 | `MARGEM_M`, `CODIGOS_EM_EMPATE`, `DESCARTADOS_NO_MINIMO`, `N_CODIGOS`, `N_COMPATIVEIS`, `FRACAO`, `VIA_COMPATIVEL` em `Obs_SNV` | auditoria (§1.1, §1.6) |
| 11 | Causas de `TRECHO_DIVERGENTE` separadas | auditoria (§1.5) |
| 12 | `ALERTA_ESCALA_KM_GEOM` e seu contador | auditoria (§1.7) |
| 13 | Causa própria para trecho fechado (**mantido nos índices de vizinhança**) | auditoria (§1.8) |
| 14 | Contadores de causas de não associação e de `Via` não normalizável; bloco de parâmetros no resumo | auditoria |
| 15 | `selecionar_codigo` devolve **causa estruturada** (4 elementos), permitindo discriminar no resumo as três causas distintas de `TRECHO_DIVERGENTE` | auditoria |
| 16 | `PROJECAO_NO_EXTREMO=INICIO_GEOM\|FIM_GEOM` quando a fração resulta em 0 ou 1, com contador próprio | auditoria (§1.7-b) |
| 17 | Novo campo **`Rodovias_coincidentes`** (texto): números de BR das rodovias em **sobreposição comprovada** no local da OAE — as que ocupam o mesmo espaço, parcial ou totalmente. A atribuída primeiro, as demais em ordem numérica, separadas por `;`; NULL sem coincidência. Alimentado pela sobreposição já apurada no critério (`TRECHO_COINCIDENTE` e `TRECHO_EMPATE` entre códigos coincidentes), nunca pela proximidade no raio. `Qtd_Codigos` é mantido | decisão do responsável |
| 18 | `truncar_texto` extraído de `observacao_texto` e aplicado também ao campo novo; `N_CODIGOS=` estendido aos ramos `UNICO_TRECHO` e `TRECHO_DIVERGENTE` de código único | correção / auditoria |

Os itens 11–13 alteram **textos de causa e rótulos de diagnóstico**, não
classificações nem valores de `km_SNV`.

### 3.2 Alterações de lógica — **desligadas por padrão**

| Parâmetro | Padrão | Efeito quando ativado |
|---|---|---|
| `DISTANCIA_MAXIMA_ASSOCIACAO_M` | `None` | §1.2 — candidatos além do limite são descartados |

Com os padrões acima, a classificação e o `km_SNV` de cada OAE são **idênticos**
aos da versão original.

### 3.3 Verificação realizada

As funções sem dependência do QGIS foram extraídas e exercitadas fora do
ambiente QGIS (**100 verificações, todas aprovadas**):

* `normalizar_via` — 14 casos, incluindo a rejeição de `"BR-116/BR-101"` e `"1160"`;
* `prefixo_codigo`, `numero_finito`, `numero_finito_positivo` (inclusive a
  rejeição de booleanos), `formatar_lista_codigos`, `observacao_texto`
  (truncamento no limite exato);
* `resolver_orientacao` — evidência por anterior, por posterior e por ambos;
  geometria armazenada invertida; ausência de vizinhos; dois vizinhos
  concorrentes; anel tocando os dois extremos; anterior e posterior no mesmo
  extremo; limiar de conexão em 0,99 m e 1,01 m; **independência da ordem** dos
  vizinhos;
* `selecionar_codigo` — os seis critérios; código único incompatível e `Via`
  ausente resultando em `TRECHO_DIVERGENTE` com as causas corretas; três códigos
  no raio com um só compatível resultando em `TRECHO_FRONTEIRA` (decisão 1);
  único compatível coincidente resultando em `TRECHO_COINCIDENTE` (decisão 3);
  redação completa de `TRECHO_EMPATE` (`EQUIDISTANTES_DA_OAE`, `N_EMPATADOS`,
  `DIST_EQUIDISTANTE_M`); par coincidente mais distante **não** vencendo um
  compatível mais próximo; empate entre coincidências **não** resgatado por
  fronteira; código incompatível mais próximo **não** vencendo um compatível
  mais distante; resultado invariante sob **todas as permutações** de um caso
  com quatro códigos equidistantes; exaustividade dos critérios; e a
  **invariante de `Via`** — sobre dez combinações de compatibilidade, todo
  código devolvido tem prefixo igual à `Via` e toda não associação tem causa.

Não foi possível executar o script completo: `qgis.core` não está disponível
neste ambiente. **A execução em QGIS sobre as camadas reais permanece
necessária**, com atenção especial aos números de `UNICO_TRECHO` com
`Criterio = 'TRECHO_DIVERGENTE'` (§1.1), à distribuição de `Dist_SNV_m` (§1.2), à de
`MARGEM_M` (§1.6) e à composição de `SEM_VIZINHO_COMPATIVEL` (§1.10).
