import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from google.api_core.exceptions import BadRequest, Forbidden
from google.cloud import bigquery

import banco
import configuracao

CHAVE = json.dumps({"type": "service_account", "project_id": "p"}).encode()


@pytest.fixture(autouse=True)
def arquivos(monkeypatch, tmp_path):
    monkeypatch.setattr(configuracao, "ARQUIVO_CREDENCIAL", tmp_path / "credencial.json")


@pytest.fixture
def conexao():
    falso = MagicMock()
    with patch.object(banco, "cliente", return_value=falso):
        yield falso


@pytest.mark.parametrize("conteudo", [b"nao e json", b"[1]", b'{"type": "authorized_user"}'])
def test_conectar_recusa_arquivo_errado(conteudo):
    with pytest.raises(banco.ErroBigQuery):
        banco.conectar(conteudo)
    assert not banco.conectado()


def test_conectar_salva_so_depois_de_testar():
    with patch.object(bigquery.Client, "from_service_account_info") as criar:
        criar.return_value.list_datasets.side_effect = Forbidden("sem permissão")
        with pytest.raises(banco.ErroBigQuery, match="sem permissão"):
            banco.conectar(CHAVE)
        assert not banco.conectado()

        criar.return_value.list_datasets.side_effect = None
        criar.return_value.list_datasets.return_value = []
        banco.conectar(CHAVE)
    assert banco.conectado()

    banco.desconectar()
    assert not banco.conectado()


def tabela_falsa(nome):
    return SimpleNamespace(
        project="p",
        dataset_id="d",
        table_id=nome,
        schema=[
            bigquery.SchemaField("valor", "NUMERIC"),
            bigquery.SchemaField(
                "cliente", "RECORD", fields=[bigquery.SchemaField("nome", "STRING")]
            ),
        ],
    )


def test_ler_tabelas_inclui_colunas_aninhadas(conexao):
    conexao.list_datasets.return_value = [MagicMock()]
    conexao.list_tables.return_value = [MagicMock()]
    conexao.get_table.return_value = tabela_falsa("pedidos")

    texto, cortada = banco.ler_tabelas()

    assert texto == "p.d.pedidos (valor NUMERIC, cliente RECORD, cliente.nome STRING)"
    assert not cortada


def test_ler_tabelas_avisa_quando_corta(conexao, monkeypatch):
    monkeypatch.setattr(banco, "LIMITE_TABELAS", 2)
    conexao.list_datasets.return_value = [MagicMock()]
    conexao.list_tables.return_value = [MagicMock()] * 3
    conexao.get_table.return_value = tabela_falsa("t")

    texto, cortada = banco.ler_tabelas()

    assert len(texto.splitlines()) == 2
    assert cortada


def test_validar_usa_dry_run_e_retorna_bytes(conexao):
    conexao.query.return_value.total_bytes_processed = 2048

    assert banco.validar("SELECT 1") == 2048

    assert conexao.query.call_args.kwargs["job_config"].dry_run is True


def test_validar_traduz_erro_do_bigquery(conexao):
    conexao.query.side_effect = BadRequest("Unrecognized name: lucro")
    with pytest.raises(banco.ErroBigQuery, match="lucro"):
        banco.validar("SELECT lucro")


def test_executar_limita_bytes_e_linhas(conexao):
    linhas = MagicMock()
    linhas.__iter__.return_value = iter([{"a": 1}])
    linhas.total_rows = 5000
    conexao.query.return_value.result.return_value = linhas

    assert banco.executar("SELECT 1") == ([{"a": 1}], 5000)

    assert conexao.query.call_args.kwargs["job_config"].maximum_bytes_billed == banco.LIMITE_BYTES
    assert conexao.query.return_value.result.call_args.kwargs["max_results"] == banco.LIMITE_LINHAS


@pytest.mark.parametrize("sql", ["DELETE FROM `p.d.t` WHERE TRUE", "SELECT 1; DROP TABLE `p.d.t`"])
def test_executar_nunca_envia_o_que_nao_e_leitura(conexao, sql):
    with pytest.raises(banco.ErroBigQuery):
        banco.executar(sql)
    conexao.query.assert_not_called()


def test_executar_avisa_quando_falha(conexao):
    conexao.query.return_value.result.side_effect = OSError("sem internet")
    with pytest.raises(banco.ErroBigQuery, match="sem internet"):
        banco.executar("SELECT 1")


@pytest.mark.parametrize(
    "quantidade, texto",
    [(10, "10 bytes"), (2048, "2,0 KB"), (5 * 1024**3, "5,0 GB"), (3 * 1024**4, "3,0 TB")],
)
def test_formatar_bytes(quantidade, texto):
    assert banco.formatar_bytes(quantidade) == texto
