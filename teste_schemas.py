"""Testes rápidos do tot.py, sem chamar a API do Gemini."""
from pydantic import ValidationError

from tot import PESOS, PROMPT_AVALIACAO, PROMPT_GERACAO, PROMPT_SINTESE, NotaCriterio

# 1. Uma nota válida deve funcionar
nota_ok = NotaCriterio(justificativa="Cabe no orçamento de R$ 3 mil.", nota=8)
print("Nota válida:", nota_ok)

# 2. Uma nota fora do intervalo deve ser RECUSADA pelo Pydantic
try:
    NotaCriterio(justificativa="Teste", nota=11)
    print("ERRO: a nota 11 foi aceita!")
except ValidationError:
    print("A nota 11 foi recusada, como esperado.")

# 3. Os prompts devem aceitar o .format() com os campos certos
#    (se faltar ou sobrar um campo, aparece KeyError)
PROMPT_GERACAO.format(contexto="teste", problema="teste")
PROMPT_AVALIACAO.format(contexto="teste", problema="teste", abordagens="teste")
PROMPT_SINTESE.format(contexto="teste", problema="teste", vencedora="teste", analise="teste")
print("Os 3 prompts aceitam o .format().")

# 4. Os pesos devem ter os mesmos nomes dos critérios do schema
print("Critérios com peso:", list(PESOS.keys()))