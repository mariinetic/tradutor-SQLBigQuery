from unittest.mock import patch

import anthropic
import httpx2
import pytest
from streamlit.testing.v1 import AppTest

import configuracao
import tradutor
from tradutor import Traducao


@pytest.fixture(autouse=True)
def ambiente(monkeypatch, tmp_path):
    """Isola cada teste dos arquivos reais de chave e de tabelas."""
    monkeypatch.setattr(configuracao, "ARQUIVO_CHAVE", tmp_path / ".env")
    monkeypatch.setattr(configuracao, "ARQUIVO_TABELAS", tmp_path / "tabelas.txt")
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")


def abrir():
    return AppTest.from_file("app.py", default_timeout=30).run()


def botao(tela, texto):
    return next(b for b in tela.button if b.label == texto)


def traduzir_pergunta(tela=None):
    tela = tela or abrir()
    tela.text_input(key="pergunta").set_value("quais os maiores valores do mês?")
    return botao(tela, "Traduzir").click().run()


def erro_da_api(classe, status, mensagem="erro"):
    resposta = httpx2.Response(
        status, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    )
    return classe(mensagem, response=resposta, body=None)


def test_sem_chave_pede_a_chave_e_salva(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    tela = abrir()
    assert not tela.exception
    assert not any(b.label == "Traduzir" for b in tela.button)

    tela.text_input[0].set_value("sk-nova")
    with patch.object(tradutor, "validar_chave"):
        botao(tela, "Salvar e começar").click().run()

    assert not tela.exception
    assert any(b.label == "Traduzir" for b in tela.button)
    assert "sk-nova" in configuracao.ARQUIVO_CHAVE.read_text()


def test_chave_recusada_nao_e_salva(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    tela = abrir()
    tela.text_input[0].set_value("sk-errada")
    recusa = erro_da_api(anthropic.AuthenticationError, 401)
    with patch.object(tradutor, "validar_chave", side_effect=recusa):
        botao(tela, "Salvar e começar").click().run()

    assert "não foi aceita" in tela.error[0].value
    assert not configuracao.ARQUIVO_CHAVE.exists()


def test_mostra_sql_e_premissas():
    traducao = Traducao(sql="SELECT 1", premissas=["mês atual"])
    with patch.object(tradutor, "traduzir", return_value=traducao):
        tela = traduzir_pergunta()
    assert not tela.exception
    assert tela.code[0].value == "SELECT 1"
    assert not tela.warning
    assert any("mês atual" in m.value for m in tela.markdown)


def test_pergunta_vazia_nao_chama_a_api():
    with patch.object(tradutor, "traduzir") as traduzir:
        botao(abrir(), "Traduzir").click().run()
    traduzir.assert_not_called()


def test_exemplo_traduz_com_um_clique():
    traducao = Traducao(sql="SELECT 1", premissas=[])
    with patch.object(tradutor, "traduzir", return_value=traducao) as traduzir:
        tela = botao(abrir(), "Maiores valores do mês").click().run()
    assert traduzir.call_args.args[0] == "Maiores valores do mês"
    assert tela.text_input(key="pergunta").value == "Maiores valores do mês"
    assert tela.code[0].value == "SELECT 1"


def test_resultado_continua_na_tela_ao_editar_os_campos():
    traducao = Traducao(sql="SELECT 1", premissas=[])
    with patch.object(tradutor, "traduzir", return_value=traducao):
        tela = traduzir_pergunta()
        tela.text_area(key="tabelas").set_value("p.d.t (a)").run()
    assert tela.code[0].value == "SELECT 1"


def test_tabelas_ficam_salvas_e_vao_para_a_traducao():
    tela = abrir()
    tela.text_area(key="tabelas").set_value("p.d.pedidos (valor)").run()
    assert abrir().text_area(key="tabelas").value == "p.d.pedidos (valor)"

    traducao = Traducao(sql="SELECT 1", premissas=[])
    with patch.object(tradutor, "traduzir", return_value=traducao) as traduzir:
        traduzir_pergunta(tela)
    assert traduzir.call_args.args[1] == "p.d.pedidos (valor)"


def test_avisa_sobre_sql_que_altera_dados():
    traducao = Traducao(sql="DELETE FROM `p.d.t` WHERE TRUE", premissas=[])
    with patch.object(tradutor, "traduzir", return_value=traducao):
        tela = traduzir_pergunta()
    assert "leitura" in tela.warning[0].value


def test_avisa_quando_nao_ha_sql():
    traducao = Traducao(sql=None, premissas=["pede para apagar dados"])
    with patch.object(tradutor, "traduzir", return_value=traducao):
        tela = traduzir_pergunta()
    assert not tela.code
    assert any("Não deu" in s.value for s in tela.subheader)


def test_mostra_erro_da_traducao():
    mensagem = "A resposta veio incompleta. Tente de novo."
    with patch.object(tradutor, "traduzir", side_effect=RuntimeError(mensagem)):
        tela = traduzir_pergunta()
    assert not tela.exception
    assert tela.error[0].value == mensagem


def test_conta_sem_credito_recebe_mensagem_clara():
    erro = erro_da_api(
        anthropic.BadRequestError, 400, "Your credit balance is too low to access the API."
    )
    with patch.object(tradutor, "traduzir", side_effect=erro):
        tela = traduzir_pergunta()
    assert "sem créditos" in tela.error[0].value


def test_chave_invalida_volta_para_a_tela_da_chave():
    erro = erro_da_api(anthropic.AuthenticationError, 401)
    with patch.object(tradutor, "traduzir", side_effect=erro):
        tela = traduzir_pergunta()
    assert not tela.exception
    assert any(b.label == "Salvar e começar" for b in tela.button)


def test_botao_de_trocar_chave():
    tela = botao(abrir(), "Trocar chave da API").click().run()
    assert any(b.label == "Salvar e começar" for b in tela.button)


def test_interface_nao_tem_emojis():
    textos = "".join(p.read_text(encoding="utf-8") for p in (
        configuracao.PASTA / "app.py",
        configuracao.PASTA / "estilo.css",
    ))
    assert all(ord(c) < 0x2190 for c in textos)
