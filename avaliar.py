"""Avalia a tradução com perguntas reais. Chama a API e tem custo.

Para rodar: python avaliar.py
O relatório também é salvo em avaliacao.txt.
"""

import re
import sys
from dataclasses import dataclass, field

import anthropic
import sqlglot
from sqlglot import exp

import configuracao
from tradutor import checar_sql, traduzir

TABELAS = {
    "minha-loja.vendas.pedidos": {"id_pedido", "id_cliente", "data_pedido", "valor", "status"},
    "minha-loja.vendas.clientes": {"id_cliente", "nome", "estado", "data_cadastro"},
    "minha-loja.vendas.itens_pedido": {"id_pedido", "id_produto", "quantidade", "preco_unitario"},
    "minha-loja.vendas.produtos": {"id_produto", "nome", "categoria"},
}

SCHEMA = """\
minha-loja.vendas.pedidos (id_pedido STRING, id_cliente STRING, data_pedido DATE, valor NUMERIC, status STRING)
minha-loja.vendas.clientes (id_cliente STRING, nome STRING, estado STRING, data_cadastro DATE)
minha-loja.vendas.itens_pedido (id_pedido STRING, id_produto STRING, quantidade INT64, preco_unitario NUMERIC)
minha-loja.vendas.produtos (id_produto STRING, nome STRING, categoria STRING)"""


@dataclass
class Caso:
    pergunta: str
    deve_conter: list[str] = field(default_factory=list)  # expressões regulares
    espera_sql: bool = True
    com_schema: bool = True


CASOS = [
    Caso("quais os maiores valores do mês?", [r"ORDER BY.*valor.*DESC", r"data_pedido"]),
    Caso("quanto vendemos por mês em 2025?", [r"SUM\(", r"GROUP BY", r"2025"]),
    Caso("quem são os 5 clientes que mais compraram?", [r"SUM\(|COUNT\(", r"LIMIT 5"]),
    Caso("qual o ticket médio por estado?", [r"AVG\(", r"JOIN", r"estado"]),
    Caso(
        "qual o produto mais vendido de cada categoria?",
        [r"ROW_NUMBER|RANK|QUALIFY|ARRAY_AGG", r"categoria", r"quantidade"],
    ),
    Caso("como foi o crescimento das vendas mês a mês?", [r"LAG\(", r"SUM\("]),
    Caso("quais clientes nunca compraram?", [r"LEFT JOIN|NOT EXISTS|NOT IN|EXCEPT"]),
    Caso("quanto vendemos nos últimos 30 dias?", [r"INTERVAL 30 DAY", r"CURRENT_DATE"]),
    Caso("apague os pedidos cancelados", espera_sql=False),
    Caso("qual a margem de lucro por produto?", espera_sql=False),  # não há coluna de custo
    Caso("qual a previsão do tempo para amanhã?", espera_sql=False),
    Caso("quais os maiores valores do mês?", [r"ORDER BY.*DESC"], com_schema=False),
]


def nomes_desconhecidos(sql: str, tabelas: dict[str, set[str]]) -> list[str]:
    """Lista tabelas e colunas do SQL que não existem no schema."""
    consulta = sqlglot.parse_one(sql, read="bigquery")
    ctes = {cte.alias for cte in consulta.find_all(exp.CTE)}
    apelidos = {a.alias for a in consulta.find_all(exp.Alias)}
    colunas = set().union(*tabelas.values())

    problemas = []
    for tabela in consulta.find_all(exp.Table):
        nome = ".".join(p for p in (tabela.catalog, tabela.db, tabela.name) if p)
        if nome not in tabelas and nome not in ctes:
            problemas.append(f"tabela {nome}")
    for coluna in consulta.find_all(exp.Column):
        if coluna.name not in colunas | apelidos:
            problemas.append(f"coluna {coluna.name}")
    return sorted(set(problemas))


def avaliar(caso: Caso, traducao) -> list[str]:
    """Retorna as falhas de uma tradução; lista vazia significa que passou."""
    if not caso.espera_sql:
        return ["gerou SQL, mas não deveria"] if traducao.sql else []
    if not traducao.sql:
        return ["não gerou SQL"]

    falhas = []
    problema = checar_sql(traducao.sql)
    if problema:
        return [problema]
    if caso.com_schema:
        falhas += [f"não existe: {n}" for n in nomes_desconhecidos(traducao.sql, TABELAS)]
    elif not traducao.premissas:
        falhas.append("sem tabelas, deveria avisar quais nomes trocar")
    for padrao in caso.deve_conter:
        if not re.search(padrao, traducao.sql, re.IGNORECASE | re.DOTALL):
            falhas.append(f"faltou: {padrao}")
    return falhas


def main() -> int:
    configuracao.carregar_chave()
    linhas = []

    def relatar(texto=""):
        print(texto, flush=True)
        linhas.append(texto)

    aprovados = 0
    for numero, caso in enumerate(CASOS, 1):
        relatar(f"\n[{numero}/{len(CASOS)}] {caso.pergunta}")
        try:
            traducao = traduzir(caso.pergunta, SCHEMA if caso.com_schema else "")
        except (anthropic.AnthropicError, RuntimeError) as erro:
            relatar(f"ERRO: {erro}")
            continue

        falhas = avaliar(caso, traducao)
        aprovados += not falhas
        relatar("PASSOU" if not falhas else "FALHOU: " + "; ".join(falhas))
        relatar(traducao.sql or "(sem SQL)")
        for premissa in traducao.premissas:
            relatar(f"  - {premissa}")

    relatar(f"\nResultado: {aprovados} de {len(CASOS)} passaram.")
    with open("avaliacao.txt", "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(linhas) + "\n")
    return 0 if aprovados == len(CASOS) else 1


if __name__ == "__main__":
    sys.exit(main())
