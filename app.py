"""
Chatbot de Arquitetura de Sistemas com Tree of Thoughts.
Interface em Streamlit + Gemini com memória nativa (chats.create).
"""

import os

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors

# ==============================================================================
# CONFIGURAÇÃO INICIAL
# ==============================================================================

# Lê o arquivo .env e coloca as variáveis dentro de os.environ.
load_dotenv()

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

    Falhas transitórias (limite de requisições 429 e erros 5xx do servidor)
    são tentadas de novo automaticamente pelo SDK, com espera crescente
    entre as tentativas (backoff exponencial). Erros permanentes, como chave
    inválida (400/403), NÃO são repetidos e chegam direto ao try/except.
    """
    return genai.Client(
        api_key=chave,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                attempts=3,          # 1 tentativa original + até 2 novas tentativas
                initial_delay=2.0,   # espera 2s antes da 2ª tentativa
                exp_base=2.0,        # a espera dobra a cada nova tentativa (2s, 4s...)
                max_delay=10.0,      # nunca espera mais que 10s entre tentativas
            )
        ),
    )


cliente = obter_cliente(chave_api)    

# ==============================================================================
# FUNÇÃO AUXILIAR PARA DESENHAR UMA MENSAGEM
# ==============================================================================

def desenhar_mensagem(papel: str, conteudo: str, erro: bool = False) -> None:
    """Desenha um balão de chat na tela.

    Usamos a MESMA função para redesenhar o histórico e para desenhar
    as mensagens novas. Se a mensagem for um erro, ela aparece em vermelho.
    """
    with st.chat_message(papel):
        if erro:
            st.error(conteudo)
        else:
            st.markdown(conteudo)

# ==============================================================================
# FUNÇÃO AUXILIAR PARA RESPONDER PEGUNTAS
# ==============================================================================

def responder(pergunta: str) -> str:
    """Envia a pergunta ao Gemini e devolve o texto da resposta.

    Recebe APENAS a string do turno atual (requisito do Anexo I).
    O histórico é mantido automaticamente pelo objeto chat do session_state.

    ⚠️ PONTO DE EXTENSÃO: na Etapa 6, o Tree of Thoughts entra AQUI,
    substituindo esta chamada ingênua.
    """  

    chat = st.session_state.chat
    resposta = chat.send_message(pergunta)
    # Em casos raros (ex.: filtros de segurança), o texto vem None
    texto = resposta.text
    if not texto:
        raise ValueError("O modelo devolveu uma resposta vazia.")

    return texto.strip()

def registrar_erro(texto: str) -> None:
    """Mostra o erro na tela E o guarda no histórico visual

    Assim, no próximo rerun, o usuário continua vendo o que aconteceu
    com a pergunta que falhou.

    Observação: o histórico DO MODELO não recebe nada, porque o objeto
    Chat só registra pergunta e resposta quando a chamada dá certo.
    """
    st.error(texto)
    st.session_state.mensagens.append(
        {"role": "assistant", "content": texto, "erro": True}
    )

def nova_conversa() -> None:
    """Reinicia a conversa apagando OS DOIS históricos.

    É usada como callback (on_click) do botão: o Streamlit executa esta função
    ANTES do rerun. Assim, quando o script roda de novo, as chaves já não
    existem, e os PASSOS 1 e 1B recriam tudo vazio.
    """
    for chave in ("mensagens", "chat"):
        # O "if" evita KeyError caso a chave, por algum motivo, já não exista
        if chave in st.session_state:
            del st.session_state[chave]    


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
    desenhar_mensagem(mensagem["role"], mensagem["content"], mensagem.get("erro", False))

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

    # 4.3 Abre o balão do assistente, mostra o spinner enquanto o Gemini
    # processa, e escreve a resposta no mesmo balão quando ela chegar
    with st.chat_message("assistant"):
        try:
            with st.spinner("Analisando arquiteturas possíveis..."):
                resposta = responder(pergunta)

            st.markdown(resposta)
            # 4.4 Guarda a resposta no histórico
            st.session_state.mensagens.append({"role": "assistant", "content": resposta})

        except errors.ClientError as erro:
            # Erros 4xx: o problema está do nosso lado (chave, cota, pedido)
            if erro.code == 429:
                registrar_erro(
                    "⏳ Limite de requisições da API atingido. "
                    "Aguarde cerca de um minuto e tente novamente."
                )
            elif erro.code in (400, 401, 403):
                registrar_erro(
                    "🔑 A chave da API é inválida ou não tem permissão. "
                    "Verifique o valor de GEMINI_API_KEY no arquivo .env."
                )
            else:
                registrar_erro(f"⚠️ Erro na requisição ao Gemini (código {erro.code}).")

        except errors.ServerError as erro:
            # Erros 5xx: o problema está do lado do Google
            registrar_erro(
                f"🛠️ O serviço do Gemini está indisponível no momento "
                f"(código {erro.code}). Tente novamente em instantes."
            )

        except ValueError:
            # Lançado pela responder() quando o modelo devolve um texto vazio
            # (ex.: resposta bloqueada pelos filtros de segurança do Gemini)
            registrar_erro(
                "🤔 O modelo não conseguiu gerar uma resposta para esta pergunta. "
                "Tente reformular."
            )

        except Exception as erro:
            # Rede de segurança: sem internet, timeout ou qualquer erro inesperado
            registrar_erro(
                f"🌐 Não foi possível obter a resposta ({type(erro).__name__}). "
                "Verifique sua conexão com a internet e tente novamente."
            )
    



# ==============================================================================
# BARRA LATERAL: reiniciar a conversa e depuração
# ==============================================================================
with st.sidebar:
    st.header("⚙️ Opções")

    # on_click recebe a FUNÇÃO (sem parênteses): o Streamlit a chama no clique
    st.button("🗑️ Nova conversa", on_click=nova_conversa)

    with st.expander("🧠 Memória do modelo (debug)"):
        historico_modelo = st.session_state.chat.get_history()
        st.caption(f"{len(historico_modelo)} mensagens na memória do Gemini")
        for item in historico_modelo:
            st.markdown(f"**{item.role}:** {item.parts[0].text[:100]}...")