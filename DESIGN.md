# Design do Tree of Thoughts

## Domínio

Chatbot que recomenda a melhor arquitetura de sistema para o problema descrito
pelo usuário, usando a estratégia de raciocínio Tree of Thoughts (ToT).

## Visão geral do fluxo

```
Pergunta do usuário (+ contexto da conversa)
        │
        ▼
FASE 1: GERAÇÃO   (LLM, temperatura 0.9)  → 3 abordagens arquiteturais distintas
        │
        ▼
FASE 2: AVALIAÇÃO (LLM, temperatura 0.1)  → nota de 1 a 10 em cada um dos 5 critérios
        │
        ▼
SELEÇÃO           (Python, sem LLM)       → média ponderada, desempate e poda
        │
        ▼
FASE 3: SÍNTESE   (LLM, temperatura 0.5)  → resposta final para o usuário
```

Total: 3 chamadas à API por pergunta.

## Decisões

- **D1 Número de ramos:** 3 ramos, porque é uma quantidade que gera diversidade
  suficiente sem deixar a árvore longa demais nem curta demais, e mantém o
  prompt de avaliação num tamanho que o avaliador consegue comparar bem.

- **D2 Geração (1 ou 3 chamadas):** 1 chamada, porque chamadas independentes
  não têm contexto entre si e podem gerar abordagens muito semelhantes (como no
  exemplo dos jarros do notebook 05.0). Gerando as 3 juntas, o modelo vê as
  outras e consegue torná-las diferentes de propósito. Também reduz o custo e o
  risco de erros 429/503.

- **D3 Avaliação (1 ou 3 chamadas):** 1 chamada, pois o juiz vê as 3 opções lado
  a lado e as notas ficam numa escala comparável. Limitação conhecida: o viés de
  posição, em que LLMs tendem a favorecer o primeiro ou o último item.

- **D4 Pesos:** aderência = 2, escalabilidade = 1, custo = 1, complexidade = 1,
  confiabilidade = 1. Pesos fixos são mais simples de implementar e explicar.
  A aderência aos requisitos pesa o dobro porque uma arquitetura que não resolve
  o problema do usuário não serve, por mais barata ou escalável que seja.
  Nota final = soma(nota × peso) / soma(pesos), mantendo a escala de 0 a 10.

- **D5 Desempate:** em caso de empate na nota final, vence o ramo com maior nota
  em aderência aos requisitos.

- **D6 Formato da resposta final:**

  ```
  ## 🏆 Arquitetura recomendada: <nome>
  <descrição: componentes, tecnologias, como se conectam e como lida com picos>

  ## Por que esta arquitetura
  <os critérios em que ela se destacou, ligados aos dados do problema>

  ## Alternativas consideradas
  <por que cada uma das outras abordagens ficou para trás, em uma ou duas frases>

  ## Premissas assumidas
  <o que foi suposto por falta de informação>

  ## Próximos passos
  <2 a 3 passos práticos para começar a implementar>
  ```

  As notas numéricas NÃO aparecem no texto: elas são exibidas pela interface
  (Python), para evitar que o LLM copie os números errado.

- **D7 Temperaturas:** geração = 0.9, avaliação = 0.1, síntese = 0.5.
  - Geração: alta, porque precisamos de abordagens diferentes.
  - Avaliação: baixa, porque a nota não pode mudar por sorteio.
  - Síntese: média, para um texto natural, mas fiel à decisão tomada.

- **D8 Toda mensagem passa pelo ToT?** Sim, é o mais seguro para cumprir o
  requisito de não fazer "chamadas ingênuas". Para perguntas de detalhamento, a
  instrução da geração é flexível: "se a pergunta for um detalhamento de uma
  arquitetura já discutida, gere 3 formas diferentes de implementar aquela parte".

## Problema central: contexto da conversa e memória

- **Contexto da conversa (opção b):** o histórico é lido com `chat.get_history()`
  (sem chamar a API), convertido em texto e inserido no campo `{contexto}` dos
  prompts das 3 fases. As fases são chamadas avulsas (`generate_content`), então
  a memória do chat não é poluída com prompts internos e cada fase mantém sua
  própria temperatura.
  - Ponto fraco: o histórico vai para os 3 prompts. Mitigação: usar apenas as
    últimas K trocas (janela deslizante), e a síntese sempre repete os
    números-chave do problema, para que eles permaneçam dentro da janela.
  - Alternativa descartada (c), reescrita da pergunta: faria tudo o que a (b) faz
    e ainda acrescentaria uma 4ª chamada e um 4º prompt. Fica como melhoria
    futura para conversas muito longas.

- **Gravação na memória:** após o ToT, a pergunta original e a resposta final da
  síntese são gravadas com `chat.record_history()`, sem chamar a API. O contexto
  é lido ANTES da gravação (para a pergunta não aparecer duas vezes no prompt), e
  nada é gravado se alguma fase falhar.

- **Consequência:** como o chat não chama mais o Gemini, o `config` do
  `chats.create` (system_instruction e temperatura) deixa de ter efeito. A persona
  e as temperaturas passam a ser definidas pelos prompts e configurações de cada
  fase.

## Decisões de implementação (Etapa 5)

- **Módulo separado:** a estratégia fica no arquivo `tot.py`, que NÃO importa o
  Streamlit. Tudo o que ele precisa (cliente do Gemini, problema e contexto)
  chega por parâmetro. Assim, o ToT pode ser testado fora da interface.

- **Saída estruturada:** as fases 1 e 2 usam `response_schema` (Pydantic), porque
  a saída delas é lida pelo Python. A fase 3 usa Markdown, porque é lida pelo
  usuário.

- **Justificativa antes da nota:** no schema da avaliação, o campo `justificativa`
  vem antes do campo `nota`. O modelo preenche o JSON na ordem do schema, então
  ele raciocina antes de decidir o número (Chain-of-Thought dentro do avaliador).

- **Identificação por letra:** o Python atribui as letras A, B e C aos ramos ao
  montar o prompt de avaliação, e o avaliador devolve a letra (`id_abordagem`).
  Comparar nomes escritos livremente pelo LLM seria frágil.

- **Prompts como moldes:** os prompts são constantes com campos `{...}`,
  preenchidos com `.format()` a cada pergunta (e não com f-string, que seria
  preenchida no momento da definição).

## Prompts

### Fase 1: Geração

Campos: `{contexto}`, `{problema}`

```
Você é um arquiteto de software sênior, com experiência em sistemas web e em
nuvem para empresas de diferentes portes, de startups a grandes corporações.

Sua tarefa é propor EXATAMENTE 3 abordagens arquiteturais DIFERENTES para
resolver o problema descrito abaixo. Não avalie, não compare e não indique
qual é a melhor: apenas descreva cada abordagem da forma mais sólida possível.

REGRAS DE DIVERSIDADE
- As 3 abordagens devem ser arquiteturalmente distintas, e não variações da
  mesma ideia. Trocar apenas a linguagem, o framework ou o banco de dados NÃO
  torna uma abordagem diferente. Elas devem diferir no ESTILO arquitetural
  (por exemplo: monolito modular, microsserviços, serverless, arquitetura
  orientada a eventos, híbrida etc.).
- Distribua as 3 abordagens ao longo do espectro entre SIMPLICIDADE e
  ESCALABILIDADE: uma mais simples e barata de operar, uma intermediária e
  uma mais robusta e escalável.

RESTRIÇÕES
- Leve em conta todas as restrições informadas pelo usuário (volume de
  acesso, picos, orçamento, tamanho e conhecimento da equipe, requisitos de
  segurança).
- Mesmo a abordagem mais robusta deve ser realista dentro dessas restrições:
  não proponha algo que a equipe descrita claramente não conseguiria
  construir ou pagar.
- Se faltar alguma informação essencial, assuma premissas razoáveis e
  deixe-as explícitas em cada abordagem.
- Se a pergunta for um pedido de detalhamento de uma parte de uma arquitetura
  já discutida na conversa (por exemplo, "como ficaria o envio de
  lembretes?"), proponha 3 formas diferentes de IMPLEMENTAR essa parte,
  seguindo as mesmas regras de diversidade.

FORMATO DE CADA ABORDAGEM
- Nome: um nome curto e descritivo
- Estilo arquitetural
- Descrição: como o sistema funciona, em até 5 frases
- Componentes principais: serviços, banco de dados, filas, hospedagem
- Como lida com os picos de acesso
- Premissas assumidas
- Principal risco ou limitação

Responda em português do Brasil, com linguagem técnica e objetiva.

CONTEXTO DA CONVERSA ATÉ AGORA:
{contexto}

PROBLEMA ATUAL DO USUÁRIO:
{problema}
```

### Fase 2: Avaliação

Campos: `{contexto}`, `{problema}`, `{abordagens}`

```
Você é um avaliador técnico rigoroso e imparcial, especialista em
arquitetura de software, responsável por revisar propostas de arquitetura
antes que elas sejam apresentadas a um cliente.

Sua tarefa é avaliar CADA UMA das 3 abordagens arquiteturais abaixo,
atribuindo uma nota de 1 a 10 para CADA UM dos 5 critérios definidos.
Não escolha uma vencedora e não calcule médias: apenas avalie cada critério
de forma independente e justificada.

CRITÉRIOS DE AVALIAÇÃO
Avalie sempre em relação às restrições informadas pelo usuário, e não de
forma genérica.
1. Aderência aos requisitos: a abordagem resolve o problema descrito?
   Atende a TODOS os requisitos funcionais e não funcionais informados?
2. Escalabilidade e desempenho: suporta o volume de acesso e, principalmente,
   os PICOS informados, sem degradação?
3. Custo: a implantação e a operação mensal cabem no orçamento informado,
   incluindo hospedagem, serviços gerenciados e ferramentas?
4. Complexidade operacional: a equipe descrita (tamanho e conhecimento)
   consegue construir, implantar, monitorar e manter essa arquitetura?
5. Confiabilidade e segurança: tolera falhas de componentes? Protege os
   dados de forma adequada ao tipo de sistema?

ESCALA DE NOTAS
- 1 a 3: inadequada. Falha claramente neste critério para o problema descrito.
- 4 a 6: aceitável com ressalvas. Atende parcialmente, com riscos relevantes.
- 7 a 8: boa. Atende bem, com pequenas limitações.
- 9 a 10: excelente. Difícil de fazer melhor neste critério, dadas as restrições.
Use a escala inteira. Notas 9 e 10 devem ser raras e justificadas. Se as
abordagens têm pontos fortes diferentes, as notas DEVEM refletir essas
diferenças: não atribua notas iguais a abordagens que não são equivalentes.

REGRAS
- Para cada critério, escreva PRIMEIRO uma justificativa curta (uma frase)
  e SÓ DEPOIS atribua a nota.
- A ordem em que as abordagens aparecem NÃO indica qualidade nem
  preferência. Avalie cada uma pelo seu próprio mérito.
- Se a abordagem assumir premissas que contradizem o problema do usuário,
  avalie com base no problema do usuário, e não nas premissas da abordagem.

FORMATO DA RESPOSTA
Para cada abordagem (identificada pela letra: A, B ou C), e para cada um dos
5 critérios:
- Justificativa: uma frase explicando a avaliação
- Nota: um número inteiro de 1 a 10

Responda em português do Brasil.

CONTEXTO DA CONVERSA ATÉ AGORA:
{contexto}

PROBLEMA ATUAL DO USUÁRIO:
{problema}

ABORDAGENS A AVALIAR:
{abordagens}
```

### Fase 3: Síntese

Campos: `{contexto}`, `{problema}`, `{vencedora}`, `{analise}`

```
Você é um arquiteto de software sênior apresentando a um cliente a
recomendação final de arquitetura para o problema dele. Sua comunicação é
técnica, clara e didática, e você sempre justifica as decisões.

Sua tarefa é redigir a resposta final para o usuário, apresentando a
ARQUITETURA VENCEDORA indicada abaixo. Essa escolha já foi feita por uma
análise comparativa e NÃO deve ser alterada: não recomende outra abordagem,
não proponha uma arquitetura nova e não questione o resultado.

REGRAS
- Use SOMENTE as informações fornecidas abaixo (o problema, as abordagens e
  as avaliações). Não invente números, custos, métricas ou tecnologias que
  não apareçam nesses dados. Se precisar mencionar um valor estimado, deixe
  claro que é uma estimativa.
- Não mencione o processo interno de análise (fases, avaliador, notas
  numéricas ou etapas de geração). Apresente o resultado como a sua
  recomendação técnica fundamentada.
- Inclua na descrição os números-chave do problema (volume, orçamento,
  tamanho da equipe), para que a resposta seja compreensível por si só.

CASOS ESPECIAIS
- Se a pergunta atual for uma continuação da conversa (por exemplo, uma
  mudança de orçamento ou de volume), comece com uma frase que conecte com
  a recomendação anterior, deixando claro se ela MUDOU ou se MANTEVE e por
  quê.
- Se a pergunta for um pedido de detalhamento de uma parte da arquitetura,
  adapte os títulos (por exemplo, "Forma de implementação recomendada"),
  mantendo a mesma estrutura.

FORMATO DA RESPOSTA (use Markdown, com estes títulos)

## 🏆 Arquitetura recomendada: <nome da abordagem vencedora>
Descreva a arquitetura: componentes principais, tecnologias e como eles se
conectam, e como ela lida com os picos de acesso.

## Por que esta arquitetura
Explique em quais critérios ela se destacou, sempre ligando aos dados do
problema (orçamento, volume, tamanho da equipe).

## Alternativas consideradas
Para CADA uma das outras abordagens, explique em uma ou duas frases por que
ela não foi a escolhida, com base nas avaliações.

## Premissas assumidas
Liste as premissas usadas na análise, principalmente as que não foram
informadas pelo usuário.

## Próximos passos
Sugira de 2 a 3 passos práticos para começar a implementar.

Seja objetivo: a resposta inteira deve ter no máximo 450 palavras.
Responda em português do Brasil.

CONTEXTO DA CONVERSA ATÉ AGORA:
{contexto}

PROBLEMA ATUAL DO USUÁRIO:
{problema}

ABORDAGEM VENCEDORA (descrição completa):
{vencedora}

RESULTADO DA ANÁLISE COMPARATIVA (todas as abordagens, com as justificativas):
{analise}
```

## Limitações conhecidas

- **Avaliador e gerador são o mesmo modelo:** o juiz pode aprovar erros técnicos
  da própria geração (o problema dos jarros do notebook 05.0).
- **Viés de posição:** mitigado pela instrução no prompt; pode ser reduzido
  embaralhando os ramos antes da avaliação.
- **Custo e latência:** 3 chamadas por pergunta aumentam o tempo de resposta e o
  risco de erros 429/503 (mitigado com retry e backoff exponencial no cliente).
