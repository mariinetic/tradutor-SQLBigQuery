import json

import anthropic
import httpx2
import pytest

from tradutor import MODELO, checar_sql, traduzir


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT valor FROM `p.d.pedidos` ORDER BY valor DESC LIMIT 10",
        "WITH t AS (SELECT 1 AS x) SELECT x FROM t",
        "SELECT * FROM `p.d.t` WHERE d >= DATE_TRUNC(CURRENT_DATE(), MONTH);",
    ],
)
def test_aceita_consultas_de_leitura(sql):
    assert checar_sql(sql) is None


@pytest.mark.parametrize(
    "sql, trecho",
    [
        ("DELETE FROM `p.d.t` WHERE TRUE", "leitura"),
        ("DROP TABLE `p.d.t`", "leitura"),
        ("SELECT 1; DROP TABLE `p.d.t`", "mais de um"),
        ("SELECT FROM WHERE (", "sintaxe"),
    ],
)
def test_aponta_problemas(sql, trecho):
    assert trecho in checar_sql(sql)


def cliente_falso(texto, stop_reason="end_turn"):
    """Cliente real do SDK com a rede simulada; guarda o corpo enviado à API."""
    enviados = []

    def responder(requisicao):
        enviados.append(json.loads(requisicao.content))
        return httpx2.Response(
            200,
            json={
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": MODELO,
                "content": [{"type": "text", "text": texto}] if texto else [],
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    cliente = anthropic.Anthropic(
        api_key="teste",
        http_client=anthropic.DefaultHttpxClient(
            transport=httpx2.MockTransport(responder)
        ),
    )
    return cliente, enviados


def test_traduzir_monta_pedido_e_le_resposta():
    cliente, enviados = cliente_falso('{"sql": "SELECT 1", "premissas": ["mês atual"]}')

    resultado = traduzir("maiores valores do mês?", "p.d.pedidos (valor NUMERIC)", cliente)

    assert resultado.sql == "SELECT 1"
    assert resultado.premissas == ["mês atual"]
    corpo = enviados[0]
    assert corpo["model"] == MODELO
    assert corpo["output_config"]["effort"] == "medium"
    assert corpo["output_config"]["format"]["type"] == "json_schema"
    assert corpo["fallbacks"] == "default"
    assert "maiores valores do mês?" in corpo["messages"][0]["content"]
    assert "p.d.pedidos" in corpo["messages"][0]["content"]


def test_traduzir_aceita_sql_nulo():
    cliente, _ = cliente_falso('{"sql": null, "premissas": ["pede para apagar dados"]}')
    assert traduzir("apague tudo", cliente=cliente).sql is None


@pytest.mark.parametrize(
    "texto, stop_reason, trecho",
    [
        ("", "refusal", "recusou"),
        ('{"sql": "SELE', "refusal", "incompleta"),
        ('{"sql": "SELE', "max_tokens", "incompleta"),
    ],
)
def test_traduzir_avisa_quando_nao_ha_resposta_completa(texto, stop_reason, trecho):
    cliente, _ = cliente_falso(texto, stop_reason)
    with pytest.raises(RuntimeError, match=trecho):
        traduzir("maiores valores", cliente=cliente)
