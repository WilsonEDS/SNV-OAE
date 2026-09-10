# Solicitação: Relatório Técnico — Associação OAE × SNV e cálculo do km_SNV

> Este arquivo é um **prompt**, não um relatório. Copie o conteúdo abaixo da
> linha divisória e acione-o em uma sessão com acesso a este repositório.

---

## Papel e tarefa

Você é um engenheiro responsável pela documentação técnica de uma metodologia
geoespacial. Produza um **relatório técnico completo** sobre o algoritmo contido
em `associacao_oae_snv.py`, entregue como arquivo **Word (.docx) editável**.

O documento deve permitir que um **leitor técnico independente**, sem
participação no desenvolvimento, compreenda, reproduza e confira integralmente
a metodologia: cada critério rastreável até o código que o implementa, cada
decisão justificada, cada limitação declarada.

> **Restrição de redação — obrigatória.** O documento **não deve mencionar
> auditoria, auditor, processo auditorial ou submissão a exame externo**, em
> nenhum ponto: título, resumo, corpo, legendas, notas ou apêndices. Escreva-o
> com o rigor que esse fim exigiria, mas sem jamais nomeá-lo. Onde for preciso
> referir-se a quem confere o trabalho, use "leitor técnico independente",
> "terceiro" ou "revisor técnico". Onde couber falar da propriedade do dado,
> use "rastreabilidade", "verificabilidade" ou "conferência", nunca
> "auditabilidade".

Leia, antes de escrever, os arquivos do repositório:

- `associacao_oae_snv.py` — algoritmo (fonte da verdade sobre os critérios);
- `REVISAO_TECNICA.md` — avaliação técnica, fluxo consolidado e decisões;
- `testes/teste_funcoes_puras.py` e `testes/teste_classificacao.py` — o que já
  está verificado e como.

**O código é a fonte normativa.** Onde este prompt e o código divergirem, vale o
código: relate a divergência em vez de contorná-la.

## Objeto documentado

Procedimento em PyQGIS que, para cada Obra de Arte Especial (OAE) da camada SGE:

1. associa a OAE a um trecho da malha rodoviária do SNV, identificado pelo campo
   `vl_codigo`, classificando a associação em um de seis critérios;
2. calcula o quilômetro (`km_SNV`) da OAE nesse trecho, por interpolação linear
   entre `vl_km_inic` e `vl_km_fina`, respeitando o sentido crescente da
   quilometragem.

Seis critérios, mutuamente exclusivos e exaustivos, avaliados nesta ordem:
`SEM_TRECHO`, `UNICO_TRECHO`, `TRECHO_DIVERGENTE`, `TRECHO_EMPATE`,
`TRECHO_COINCIDENTE`, `TRECHO_FRONTEIRA`.

> **Atenção.** A tupla `CRITERIOS_VALIDOS` no código está em ordem de
> **impressão** dos resumos, que **não** é a ordem de avaliação. A ordem de
> avaliação é a acima, e é a que consta da sequência de decisão documentada na
> docstring de `selecionar_codigo`. A Figura 2 deve reproduzir a ordem de
> avaliação, nunca a da tupla.

Campos de saída: `Trecho_SNV`, `km_SNV`, `Dist_SNV_m`, `Raio_SNV`,
`Qtd_Codigos`, `Criterio`, `Sentido_KM`, `Obs_SNV`.

## Formato e norma

- Arquivo **.docx**, português do Brasil, registro técnico impessoal.
- Estrutura conforme **ABNT NBR 10719** (relatório técnico-científico).
- **15 a 20 páginas** de elementos textuais, sem contar pré-textuais e apêndices.
- Sumário automático; figuras e tabelas numeradas sequencialmente, com legenda
  e chamada no texto ("conforme a Figura 3", "ver Tabela 2").
- Fonte monoespaçada para código, nomes de campo e identificadores.

## Estrutura exigida

**Pré-textuais** — capa e folha de rosto com campos identificáveis a preencher
(título, órgão, autor, responsável técnico, versão, data, referência do commit);
resumo (até 250 palavras) com palavras-chave; listas de figuras, tabelas,
abreviaturas e siglas; sumário.

1. **Introdução** — contexto do problema: por que localizar OAEs sobre o SNV;
   consequências de uma associação errada; estado da questão antes deste
   procedimento.
2. **Objetivos** — geral e específicos, enunciados de forma verificável.
3. **Materiais e dados de entrada** — camadas SGE e SNV, campos obrigatórios,
   sistema de referência métrico adotado (EPSG:5880) e a razão de medir em
   metros; premissas assumidas sobre os dados.
4. **Metodologia** — núcleo do documento:
   - 4.1 Visão geral do fluxo em duas etapas;
   - 4.2 Pré-processamento: reprojeção, indexação espacial, mediana das
     extensões e raio de busca;
   - 4.3 Formação do conjunto de candidatos e agrupamento por `vl_codigo`;
   - 4.4 Compatibilidade com a `Via` como pré-condição universal;
   - 4.5 Os seis critérios — **uma subseção por critério**, cada uma com:
     regra formal, justificativa metodológica, evidência registrada em
     `Obs_SNV` e o croqui reservado (ver "Figuras");
   - 4.6 Determinação do sentido da quilometragem por continuidade geométrica e
     quilométrica;
   - 4.7 Cálculo do `km_SNV`: projeção, posição relativa e interpolação;
   - 4.8 Tratamento dos casos em que o sentido ou o km não podem ser
     determinados de forma inequívoca.
5. **Garantias metodológicas** — determinismo (independência da ordem de leitura
   das feições), exclusividade e exaustividade dos critérios, invariantes
   verificadas em execução, tolerâncias adotadas e sua justificativa numérica.
6. **Verificação e validação** — o que as 75 verificações automatizadas cobrem,
   o que não cobrem, e o que só a execução em QGIS sobre as camadas reais pode
   confirmar.
7. **Resultados** — inteiramente reservado (ver "Resultados").
8. **Decisões metodológicas registradas** — as quatro decisões consolidadas:
   cardinalidade de `UNICO_TRECHO` medida sobre todos os códigos do raio; `Via`
   ausente classificada como `TRECHO_DIVERGENTE`; prevalência de
   `TRECHO_COINCIDENTE`; `km_SNV` nulo quando o sentido é indeterminado. Para
   cada uma: questão, alternativas consideradas, decisão e consequência.
9. **Limitações conhecidas e riscos residuais** — extraia de `REVISAO_TECNICA.md`
   ao menos: ausência de distância máxima de associação; UF não verificada na
   compatibilidade (apenas o número da BR); chave de vizinhança restritiva em
   divisas e mudanças de tipo de trecho; hipótese de proporcionalidade entre
   comprimento geométrico e quilometragem declarada; não transitividade da
   equidistância dentro da tolerância. Para cada risco: descrição, efeito
   possível sobre o resultado e como o próprio relatório permite detectá-lo.
10. **Conclusões e recomendações** — o que está consolidado, o que depende da
    execução real e o que deve ser decidido antes de tornar a metodologia
    definitiva.

**Referências** — normas e documentação citadas (ABNT, SNV/DNIT, PyQGIS).

**Apêndice A — Algoritmo**: listagem **íntegra** de `associacao_oae_snv.py`, em
fonte monoespaçada, com numeração de linhas, identificação do commit e data.
Não resumir, não reescrever, não reindentar.

> A restrição de redação acima aplica-se ao **texto que você escrever**. O
> Apêndice A reproduz código-fonte tal como versionado: não edite comentários
> nem docstrings do script para atender à restrição — alterar o código para
> acomodar o documento inverteria a relação entre os dois. Se termos ali
> presentes contrariarem a restrição, a decisão é do responsável pelo código,
> não do relatório; registre a observação na entrega em tela e siga.

**Apêndice B — Dicionário de dados da camada de saída**: cada campo com tipo,
domínio de valores e significado. Para `Obs_SNV`, tabela completa dos tokens de
rastreabilidade (`MIN_VIA_M`, `MARGEM_M`, `CODIGOS_EM_EMPATE`, `DIST_EQUIDISTANTE_M`,
`SOBREPOSICAO_COM`, `ALERTA_ESCALA_KM_GEOM`, `PROJECAO_NO_EXTREMO`, causas de
não associação e de sentido indeterminado), com o significado de cada um.

## Figuras

Reduza texto usando diagramas. **Gere** os seguintes fluxogramas:

- **Figura 1** — fluxo geral em duas etapas (associação → quilometragem).
- **Figura 2** — árvore de decisão dos seis critérios, com a ordem de avaliação
  e as condições em cada nó. É a figura central do relatório.
- **Figura 3** — determinação do sentido: vizinho anterior, vizinho posterior,
  evidência única e casos de indeterminação.
- **Figura 4** — cálculo do km: projeção ortogonal, fração ao longo da geometria
  e interpolação nos dois sentidos possíveis.

**Reserve**, sem preencher, um quadro por critério (Figuras 5 a 10), para
inserção posterior de recorte de tela do QGIS com caso real:

```
Figura N — Critério <NOME_DO_CRITERIO>
┌──────────────────────────────────────────────┐
│                                              │
│        [reservado — croqui QGIS]             │
│                                              │
└──────────────────────────────────────────────┘
Deve evidenciar: <o que a figura precisa mostrar>
```

O quadro deve ser um retângulo vazio com borda, ocupando cerca de meia página,
de modo que a imagem seja colada dentro dele sem alterar a paginação. A legenda
e a linha "Deve evidenciar" já vêm escritas, descrevendo com precisão o que
aquele croqui precisa demonstrar naquele critério — por exemplo, para
`TRECHO_COINCIDENTE`: a OAE, os dois códigos equidistantes, a porção linear
comum entre eles e o código efetivamente atribuído.

## Resultados

O script **ainda não foi executado sobre as camadas reais**. Portanto:

- **Não invente, não estime e não ilustre nenhum número.** Nenhum valor
  numérico de resultado pode aparecer no documento.
- Monte as tabelas com estrutura completa — cabeçalhos, todas as linhas de
  categoria, linhas de total e de conferência — e células de valor **vazias**,
  marcadas de forma inequívoca para preenchimento.
- Tabelas mínimas: (a) distribuição das OAEs pelos seis critérios, com soma e
  conferência contra o total; (b) `km_SNV` calculado × não determinado, com as
  causas discriminadas; (c) diagnóstico de sentido dos trechos SNV, por
  evidência e por causa de indeterminação; (d) causas de não associação,
  discriminadas por critério.
- Junto de cada tabela, indique **de onde sai cada número** no resumo impresso
  pelo script, para que o preenchimento seja conferível.
- Reserve espaço para os gráficos estatísticos correspondentes, no mesmo padrão
  de quadro vazio das Figuras 5–10.

## Restrições

1. **Não altere a metodologia.** O relatório descreve o algoritmo tal como está.
   Se encontrar inconsistência entre código e documentação, registre-a em
   "Limitações conhecidas" em vez de corrigi-la silenciosamente no texto.
2. **Rastreabilidade.** Cada critério descrito deve remeter à função e à seção
   do código que o implementa, para conferência direta pelo leitor técnico.
3. **Justificar, não narrar.** Ao descrever um critério, explique *por que* a
   regra é aquela e o que ela previne — não parafraseie o que a linha de código
   faz.
4. **Nenhum número sem origem.** Todo valor citado no corpo do texto (tolerâncias,
   fator do raio, EPSG) deve corresponder a uma constante do código, nomeada
   explicitamente.
5. **Identificação da versão.** Registre no relatório o commit do código
   documentado, para que o documento e o algoritmo permaneçam associáveis.
   Obtenha-o no momento da geração (`git rev-parse --short HEAD`) e confirme
   que a árvore de trabalho está limpa (`git status --short`); se houver
   alteração não commitada, registre isso no relatório, porque nesse caso o
   documento não descreve nenhuma versão reproduzível do algoritmo.

## Entrega

Um arquivo `.docx` no repositório, mais um resumo em tela contendo: estrutura
produzida, lista das figuras geradas, lista dos espaços reservados a preencher
e o que permanece pendente da execução em QGIS.
