import streamlit as st

st.title("Experimento do rerun (com session_state)")

# Só cria a chave se ela AINDA não existir.
# Sem esse "if", o contador voltaria a 0 em todo rerun.
if "contador" not in st.session_state:
    st.session_state.contador = 0

if st.button("Clique aqui"):
    st.session_state.contador = st.session_state.contador + 1
    
pergunta = st.chat_input("Descreva seu problema de arquitetura...")
with st.chat_message("user"):
    st.markdown("Olá, esta é a minha pergunta")

with st.chat_message("assistant"):
    st.markdown("Olá, esta é a resposta do bot")
st.write(f"O contador vale: {st.session_state.contador}")