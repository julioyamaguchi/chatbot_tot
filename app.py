"""
Chatbot de Arquitetura de Sistemas com Tree of Thoughts.
Etapa 1: chat "eco" (sem LLM) para entender o rerun e o session_state.
"""

import os

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ==============================================================================
# CONFIGURAÇÃO INICIAL
# ==============================================================================

# Lê o arquivo .env e coloca as variáveis dentro de os.environ.
load_dotenv()

# Deve ser o PRIMEIRO comando do Streamlit no script.
st.set_page_config(page_title="Arquiteto de Sistemas IA", page_icon="🏗️")

st.title("🏗️ Arquiteto de Sistemas com Tree of Thoughts")

# ==============================================================================
# VERIFICAÇÃO DA CHAVE DA API
# ==============================================================================

chave_api = os.environ.get("GEMINI_API_KEY")

if not chave_api:
    st.error(
        "🔑 Chave da API não encontrada. Crie um arquivo `.env` na pasta do "
        "projeto com a linha: `GEMINI_API_KEY=sua_chave`"
    )
    st.stop()


# ==============================================================================
# CONFIGURAÇÃO DO MODELO
# ==============================================================================
MODELO = "gemini-3.1-flash-lite"

INSTRUCAO_SISTEMA = """Você é um arquiteto de software sênior, especialista em
arquitetura de sistemas web e em nuvem.

Sua função é recomendar arquiteturas de sistema para os problemas descritos
pelo usuário, considerando volume de acesso, picos de tráfego, orçamento,
tamanho e conhecimento da equipe, confiabilidade e segurança.

Regras:
- Responda sempre em português do Brasil, com tom técnico e didático.
- Quando o usuário fizer perguntas de acompanhamento, use o contexto da
  conversa anterior (ex.: "e se o orçamento cair pela metade?").
- Se faltar alguma informação essencial, assuma premissas razoáveis e
  deixe-as explícitas na resposta.
- Se a pergunta não for sobre arquitetura ou desenvolvimento de sistemas,
  explique educadamente que seu foco é arquitetura de software.
"""


@st.cache_resource
def obter_cliente(chave: str) -> genai.Client:
    """Cria o cliente do Gemini UMA única vez e reaproveita em todos os reruns.

    O cliente não guarda estado de conversa, então pode ser compartilhado
    com segurança entre todas as sessões.
    """
    return genai.Client(api_key=chave)


cliente = obter_cliente(chave_api)    

# ==============================================================================
# FUNÇÃO AUXILIAR PARA DESENHAR UMA MENSAGEM
# ==============================================================================
# Avatar de cada papel. None = avatar padrão do Streamlit.

def desenhar_mensagem(papel: str, conteudo: str) -> None:
    """Desenha um balão de chat na tela.

    Usamos a MESMA função para redesenhar o histórico e para desenhar
    as mensagens novas. Assim o visual (avatar) fica sempre igual.
    """
    with st.chat_message(papel):
        st.markdown(conteudo)


def responder(pergunta: str) -> str:
    """Envia a pergunta ao Gemini e devolve o texto da resposta.

    Recebe APENAS a string do turno atual (requisito do Anexo I).
    O histórico é mantido automaticamente pelo objeto chat do session_state.

    ⚠️ PONTO DE EXTENSÃO: na Etapa 6, o Tree of Thoughts entra AQUI,
    substituindo esta chamada ingênua.
    """
    # TODO: envie a pergunta usando o chat guardado no session_state
    #       e devolva só o texto da resposta.
    #       (Lembre do notebook 07.1: chat.send_message(...) e .text)
    ...        
    chat = st.session_state.chat
    resposta = chat.send_message(pergunta)
    return resposta.text.strip()


# ==============================================================================
# PASSO 1: INICIALIZAR O HISTÓRICO VISUAL
# ==============================================================================
# Este bloco roda em TODO rerun, mas o "if" garante que a lista só é criada
# na PRIMEIRA execução da sessão. Nos reruns seguintes, a lista já existe
# e é mantida com todas as mensagens acumuladas.
if "mensagens" not in st.session_state:
    st.session_state.mensagens = []

# ==============================================================================
# PASSO 1B: INICIALIZAR O CHAT DO MODELO (memória do Gemini)
# ==============================================================================
if "chat" not in st.session_state:
    st.session_state.chat = cliente.chats.create(
        model=MODELO,
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCAO_SISTEMA,
            temperature=0.7
        )
    )

# ==============================================================================
# PASSO 2: REDESENHAR TODO O HISTÓRICO
# ==============================================================================
# A cada rerun a tela é apagada e redesenhada do zero.
# Por isso, precisamos desenhar de novo TODAS as mensagens que já foram trocadas.
for mensagem in st.session_state.mensagens:
    # O "role" guardado decide o avatar do balão ("user" ou "assistant")
    desenhar_mensagem(mensagem["role"], mensagem["content"])

# ==============================================================================
# PASSO 3: LER A ENTRADA DO USUÁRIO
# ==============================================================================
# Devolve None na maioria dos reruns, e a string digitada SOMENTE
# no rerun que acontece logo após o usuário apertar Enter.
pergunta = st.chat_input("Descreva seu problema de arquitetura...")

# ==============================================================================
# PASSO 4: PROCESSAR A PERGUNTA NOVA (só quando existe uma)
# ==============================================================================
if pergunta:
    # 4.1 Desenha a pergunta do usuário AGORA (o loop do passo 2 já passou)
    desenhar_mensagem("user", pergunta)

    # 4.2 Guarda a pergunta no histórico, para ser redesenhada nos próximos reruns
    st.session_state.mensagens.append({"role": "user", "content": pergunta})

    # 4.3 Gera a resposta (por enquanto, só um eco; na Etapa 2 vira o Gemini)
    resposta = responder(pergunta)

    # 4.4 Desenha a resposta AGORA
    desenhar_mensagem("assistant", resposta)

    # 4.5 Guarda a resposta no histórico
    st.session_state.mensagens.append({"role": "assistant", "content": resposta})



# ==============================================================================
# DEPURAÇÃO: inspecionar o histórico que o GEMINI está recebendo
# ==============================================================================
with st.sidebar:
    with st.expander("🧠 Memória do modelo (debug)"):
        historico_modelo = st.session_state.chat.get_history()
        st.caption(f"{len(historico_modelo)} mensagens na memória do Gemini")
        for item in historico_modelo:
            st.markdown(f"**{item.role}:** {item.parts[0].text[:100]}...")    