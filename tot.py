"""
Estratégia de raciocínio Tree of Thoughts (ToT) para recomendação de
arquiteturas de software.

Fluxo:
    1. GERAÇÃO   (LLM, temperatura alta):  3 abordagens arquiteturais distintas
    2. AVALIAÇÃO (LLM, temperatura baixa): nota por critério para cada abordagem
    3. SELEÇÃO   (Python, sem LLM):        média ponderada e escolha do vencedor
    4. SÍNTESE   (LLM, temperatura média): resposta final para o usuário

Este módulo NÃO depende do Streamlit: tudo o que ele precisa chega por
parâmetro. Assim, a estratégia pode ser testada isoladamente.
"""

from pydantic import BaseModel, Field

# ==============================================================================
# SCHEMAS DA FASE 1 (GERAÇÃO)
# ==============================================================================


class Ramo(BaseModel):
    """Uma abordagem arquitetural proposta na fase de geração."""

    nome: str = Field(description="Nome curto e descritivo da abordagem")
    estilo: str = Field(
        description="Estilo arquitetural (ex.: monolito modular, microsserviços, serverless)"
    )
    descricao: str = Field(description="Como o sistema funciona, em até 5 frases")
    componentes: str = Field(
        description="Componentes principais: serviços, banco de dados, filas e hospedagem"
    )
    picos: str = Field(description="Como a abordagem lida com os picos de acesso")
    premissas: str = Field(description="Premissas assumidas por falta de informação")
    risco: str = Field(description="Principal risco ou limitação da abordagem")


class ResultadoGeracao(BaseModel):
    """Saída completa da fase de geração."""

    abordagens: list[Ramo] = Field(
        min_length=3,
        max_length=3,
        description="Exatamente 3 abordagens arquiteturalmente distintas",
    )


# ==============================================================================
# SCHEMAS DA FASE 2 (AVALIAÇÃO)
# ==============================================================================


class NotaCriterio(BaseModel):

    justificativa: str = Field(
        description="Uma frase justificando a avaliação, citando dados do problema"
    )
    nota: int = Field(ge=1, le=10, description="Nota inteira de 1 a 10")


class AvaliacaoRamo(BaseModel):
    """Avaliação completa de uma abordagem nos 5 critérios."""

    id_abordagem: str = Field(description="Letra que identifica a abordagem: A, B ou C")
    aderencia: NotaCriterio
    escalabilidade: NotaCriterio
    custo: NotaCriterio
    complexidade: NotaCriterio
    confiabilidade: NotaCriterio


class ResultadoAvaliacao(BaseModel):
    """Saída completa da fase de avaliação."""

    avaliacoes: list[AvaliacaoRamo] = Field(min_length=3, max_length=3)


# ==============================================================================
# PESOS DOS CRITÉRIOS (decisão D4 do DESIGN.md)
# ==============================================================================
# As chaves DEVEM ter os mesmos nomes dos campos de AvaliacaoRamo.
PESOS = {
    "aderencia": 2,
    "escalabilidade": 1,
    "custo": 1,
    "complexidade": 1,
    "confiabilidade": 1,
}    



# ==============================================================================
# PROMPTS DAS FASES (preenchidos com .format() a cada pergunta)
# ==============================================================================

PROMPT_GERACAO = """Você é um arquiteto de software sênior, com experiência em sistemas web e em
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
"""

PROMPT_AVALIACAO = """Você é um avaliador técnico rigoroso e imparcial, especialista em
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
{abordagens}"""   # campos: {contexto}, {problema}, {abordagens}

PROMPT_SINTESE = """Você é um arquiteto de software sênior apresentando a um cliente a
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
{analise}"""     # campos: {contexto}, {problema}, {vencedora}, {analise}