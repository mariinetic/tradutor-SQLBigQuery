from avaliar import CASOS, TABELAS, Caso, avaliar, nomes_desconhecidos
from tradutor import Traducao

SQL_BOM = """
WITH mensal AS (
  SELECT DATE_TRUNC(data_pedido, MONTH) AS mes, SUM(valor) AS total
  FROM `minha-loja.vendas.pedidos` AS p
  WHERE EXTRACT(YEAR FROM p.data_pedido) = 2025
  GROUP BY mes
)
SELECT mes, total FROM mensal ORDER BY total DESC
"""


def test_aceita_nomes_do_schema_apelidos_e_ctes():
    assert nomes_desconhecidos(SQL_BOM, TABELAS) == []


def test_aponta_tabela_e_coluna_inventadas():
    sql = "SELECT lucro FROM `minha-loja.vendas.financeiro`"
    assert nomes_desconhecidos(sql, TABELAS) == [
        "coluna lucro",
        "tabela minha-loja.vendas.financeiro",
    ]


def test_avaliar_exige_o_que_o_caso_pede():
    caso = Caso("x", deve_conter=[r"LIMIT 5"])
    assert avaliar(caso, Traducao(sql=SQL_BOM, premissas=[])) == ["faltou: LIMIT 5"]


def test_avaliar_reprova_sql_quando_nao_devia_gerar():
    caso = Caso("apague tudo", espera_sql=False)
    assert avaliar(caso, Traducao(sql="SELECT 1", premissas=[]))
    assert not avaliar(caso, Traducao(sql=None, premissas=["não altero dados"]))


def test_avaliar_exige_aviso_quando_nao_ha_tabelas():
    caso = Caso("x", com_schema=False)
    assert avaliar(caso, Traducao(sql="SELECT 1", premissas=[]))
    assert not avaliar(caso, Traducao(sql="SELECT 1", premissas=["troque os nomes"]))


def test_ha_casos_de_todos_os_tipos():
    assert any(not c.espera_sql for c in CASOS)
    assert any(not c.com_schema for c in CASOS)
