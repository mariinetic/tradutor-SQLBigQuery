"""Interface do tradutor. Para abrir: dois cliques em abrir.bat"""

from pathlib import Path

import anthropic
import streamlit as st

import banco
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


def atualizar_tabelas() -> None:
    """Precisa rodar antes de o campo de tabelas ser desenhado na tela."""
    with st.spinner("Lendo suas tabelas..."):
        tabelas, cortada = banco.ler_tabelas()
    st.session_state.tabelas = tabelas
    configuracao.salvar_tabelas(tabelas)
    if cortada:
        st.session_state.aviso_tabelas = (
            f"O projeto tem muitas tabelas, então li só as {banco.LIMITE_TABELAS} primeiras. "
            "Apague ou cole tabelas em Minhas tabelas, se precisar."
        )


def secao_bigquery() -> None:
    conectado = banco.conectado()
    rotulo = "BigQuery conectado" if conectado else "Conectar ao BigQuery (opcional)"
    with st.expander(rotulo, icon=":material/cloud_done:" if conectado else ":material/cloud:"):
        try:
            if conectado:
                st.caption("O SQL é conferido no BigQuery, e suas tabelas são lidas sozinhas.")
                with st.container(horizontal=True):
                    atualizar = st.button("Atualizar tabelas", icon=":material/sync:")
                    sair = st.button("Desconectar", icon=":material/link_off:")
                if atualizar:
                    atualizar_tabelas()
                if sair:
                    banco.desconectar()
                    st.session_state.pop("validacao", None)
                    st.rerun()
            else:
                st.caption(
                    "Envie a chave JSON de uma conta de serviço do Google Cloud, com os "
                    "papéis BigQuery Data Viewer e BigQuery Job User. Ela fica salva neste "
                    "computador."
                )
                arquivo = st.file_uploader("Chave JSON", type="json")
                if st.button("Conectar", icon=":material/link:", disabled=arquivo is None):
                    banco.conectar(arquivo.getvalue())
                    atualizar_tabelas()
                    st.rerun()
        except banco.ErroBigQuery as erro:
            st.error(str(erro), icon=":material/error:")
        aviso = st.session_state.pop("aviso_tabelas", None)
        if aviso:
            st.warning(aviso, icon=":material/warning:")


def validar_no_bigquery(sql: str | None) -> dict | None:
    """Confere o SQL no BigQuery, quando conectado e se for só leitura."""
    if not sql or not banco.conectado() or checar_sql(sql):
        return None
    try:
        with st.spinner("Conferindo no BigQuery..."):
            return {"bytes": banco.validar(sql)}
    except banco.ErroBigQuery as erro:
        return {"erro": str(erro)}


def mostrar_validacao(sql: str, validacao: dict) -> None:
    if "erro" in validacao:
        st.error(f"O BigQuery não aceitou esse SQL: {validacao['erro']}", icon=":material/error:")
        return

    leitura = banco.formatar_bytes(validacao["bytes"])
    if validacao["bytes"] > banco.LIMITE_BYTES:
        limite = banco.formatar_bytes(banco.LIMITE_BYTES)
        st.warning(
            f"SQL válido, mas leria {leitura}, acima do limite de {limite} para executar por aqui.",
            icon=":material/warning:",
        )
        return

    st.success(f"Conferido no BigQuery. Vai ler cerca de {leitura}.", icon=":material/check_circle:")
    if st.button("Executar consulta", key="executar", icon=":material/play_arrow:"):
        try:
            with st.spinner("Executando..."):
                st.session_state.dados = banco.executar(sql)
        except banco.ErroBigQuery as erro:
            st.error(str(erro), icon=":material/error:")

    if "dados" in st.session_state:
        linhas, total = st.session_state.dados
        if linhas:
            st.dataframe(linhas, hide_index=True)
            st.caption(f"Mostrando {len(linhas)} de {total} linhas.")
        else:
            st.info("A consulta não retornou nenhuma linha.", icon=":material/info:")


def mostrar_resultado(pergunta: str, resultado) -> None:
    with st.container(key="cartao_resultado"):
        if resultado.sql:
            st.subheader(":material/code: SQL gerado", anchor=False)
            st.caption(pergunta)
            st.code(resultado.sql, language="sql", wrap_lines=True)
            problema = checar_sql(resultado.sql)
            if problema:
                st.warning(problema, icon=":material/warning:")
            validacao = st.session_state.get("validacao")
            if validacao and not problema:
                mostrar_validacao(resultado.sql, validacao)
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

    secao_bigquery()

    with st.expander("Minhas tabelas (opcional)", icon=":material/table_chart:"):
        st.caption(
            "Com o BigQuery conectado, esta lista é preenchida sozinha. Sem ele, cole "
            "suas tabelas e colunas em qualquer formato. Tudo fica salvo para as "
            "próximas vezes."
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
    st.session_state.pop("dados", None)
    if resultado:
        st.session_state.resultado = (pendente, resultado)
        st.session_state.validacao = validar_no_bigquery(resultado.sql)
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
