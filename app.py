"""Interface do tradutor. Para abrir: dois cliques em abrir.bat"""

from pathlib import Path

import anthropic
import streamlit as st

import configuracao
from tradutor import checar_sql, tem_credencial, traduzir, validar_chave

EXEMPLOS = [
    ("Maiores valores do mês", ":material/trending_up:"),
    ("Total de vendas por mês", ":material/calendar_month:"),
    ("Os 5 clientes que mais compraram", ":material/group:"),
]

MARCA = """
<div class="marca">
  <div class="marca-icone">
    <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor"
         stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <ellipse cx="12" cy="5" rx="8" ry="3"/>
      <path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/>
      <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>
    </svg>
  </div>
  <div>
    <h1>Tradutor SQL BigQuery</h1>
    <p>Escreva sua pergunta em português e receba o SQL pronto.</p>
  </div>
</div>
"""


def tela_da_chave() -> None:
    st.markdown(MARCA, unsafe_allow_html=True)
    with st.container(key="cartao_chave"):
        st.subheader(":material/key: Conecte sua conta", anchor=False)
        st.write(
            "Falta só a chave da API, e você só precisa informar uma vez. "
            "Ela fica salva neste computador."
        )
        st.link_button(
            "Criar uma chave",
            "https://platform.claude.com",
            icon=":material/open_in_new:",
        )
        with st.form("chave", border=False):
            chave = st.text_input("Cole sua chave aqui", type="password").strip()
            enviou = st.form_submit_button(
                "Salvar e começar", type="primary", icon=":material/arrow_forward:"
            )
    if not enviou or not chave:
        return

    try:
        validar_chave(chave)
    except anthropic.AuthenticationError:
        st.error("Essa chave não foi aceita. Confira se copiou inteira.", icon=":material/error:")
    except anthropic.APIConnectionError:
        st.error("Não consegui conectar. Confira sua internet.", icon=":material/wifi_off:")
    except anthropic.APIStatusError as erro:
        st.error(f"A API retornou um erro ({erro.status_code}): {erro.message}", icon=":material/error:")
    else:
        configuracao.salvar_chave(chave)
        st.session_state.trocar_chave = False
        st.rerun()


def executar_traducao(pergunta: str, tabelas: str):
    """Traduz e mostra qualquer erro em português; retorna None se falhar."""
    try:
        with st.spinner("Traduzindo..."):
            return traduzir(pergunta, tabelas)
    except anthropic.AuthenticationError:
        st.session_state.trocar_chave = True
        st.rerun()
    except anthropic.RateLimitError:
        erro = "Limite de uso da API atingido. Espere um pouco e tente de novo."
    except anthropic.APIConnectionError:
        erro = "Não consegui conectar à API. Confira sua internet."
    except anthropic.APIStatusError as e:
        if "credit" in e.message.lower():
            erro = "Sua conta da API está sem créditos. Adicione créditos em platform.claude.com."
        else:
            erro = f"A API retornou um erro ({e.status_code}): {e.message}"
    except RuntimeError as e:
        erro = str(e)
    st.error(erro, icon=":material/error:")
    return None


def usar_exemplo(exemplo: str) -> None:
    st.session_state.pergunta = exemplo
    st.session_state.pendente = exemplo


def mostrar_resultado(pergunta: str, resultado) -> None:
    with st.container(key="cartao_resultado"):
        if resultado.sql:
            st.subheader(":material/code: SQL gerado", anchor=False)
            st.caption(pergunta)
            st.code(resultado.sql, language="sql", wrap_lines=True)
            problema = checar_sql(resultado.sql)
            if problema:
                st.warning(problema, icon=":material/warning:")
        else:
            st.subheader(":material/info: Não deu para gerar o SQL", anchor=False)
            st.caption(pergunta)

        if resultado.premissas:
            st.markdown("**O que foi considerado**")
            for premissa in resultado.premissas:
                st.markdown(f"- {premissa}")


st.set_page_config(page_title="Tradutor SQL BigQuery", page_icon=":material/database:")
estilo = (Path(__file__).parent / "estilo.css").read_text(encoding="utf-8")
st.markdown(f"<style>{estilo}</style>", unsafe_allow_html=True)

configuracao.carregar_chave()
if st.session_state.get("trocar_chave") or not tem_credencial():
    tela_da_chave()
    st.stop()

if "tabelas" not in st.session_state:
    st.session_state.tabelas = configuracao.carregar_tabelas()

st.markdown(MARCA, unsafe_allow_html=True)

with st.container(key="cartao_pergunta"):
    with st.form("pergunta_form", border=False):
        pergunta = st.text_input(
            "O que você quer saber?",
            key="pergunta",
            placeholder="Ex.: quais os maiores valores do mês?",
        )
        if st.form_submit_button("Traduzir", type="primary", icon=":material/auto_awesome:"):
            st.session_state.pendente = pergunta

    with st.container(key="exemplos", horizontal=True):
        for exemplo, icone in EXEMPLOS:
            st.button(exemplo, icon=icone, on_click=usar_exemplo, args=(exemplo,))

    with st.expander("Minhas tabelas (opcional)", icon=":material/table_chart:"):
        st.caption(
            "Cole suas tabelas e colunas em qualquer formato para o SQL sair com os "
            "nomes certos. Elas ficam salvas para as próximas vezes."
        )
        st.text_area(
            "Tabelas e colunas",
            key="tabelas",
            placeholder="meu-projeto.vendas.pedidos (id_pedido, data_pedido, valor)",
            height=140,
            label_visibility="collapsed",
            on_change=lambda: configuracao.salvar_tabelas(st.session_state.tabelas),
        )

pendente = st.session_state.pop("pendente", "").strip()
if pendente:
    resultado = executar_traducao(pendente, st.session_state.tabelas)
    if resultado:
        st.session_state.resultado = (pendente, resultado)
    else:
        st.session_state.pop("resultado", None)

# Guardado na sessão porque o Streamlit refaz a tela a cada edição nos campos.
if "resultado" in st.session_state:
    mostrar_resultado(*st.session_state.resultado)

with st.container(key="rodape"):
    st.button(
        "Trocar chave da API",
        icon=":material/key:",
        type="tertiary",
        on_click=lambda: st.session_state.update(trocar_chave=True),
    )
