"""Conexão com o BigQuery: lê as tabelas, valida o SQL e executa consultas de leitura."""

import json

from google.api_core.exceptions import GoogleAPICallError, GoogleAPIError
from google.auth.exceptions import GoogleAuthError
from google.cloud import bigquery

import configuracao
from tradutor import checar_sql

LIMITE_BYTES = 10 * 1024**3  # consultas que leem mais que isso não são executadas
LIMITE_LINHAS = 1000
LIMITE_TABELAS = 200

# OSError cobre falta de internet e arquivo de credencial ilegível.
ERROS_GOOGLE = (GoogleAPIError, GoogleAuthError, OSError, ValueError)


class ErroBigQuery(Exception):
    """Falha com mensagem pronta para mostrar ao usuário."""


def _mensagem(erro: Exception) -> str:
    return erro.message if isinstance(erro, GoogleAPICallError) else str(erro)


def conectado() -> bool:
    return configuracao.ARQUIVO_CREDENCIAL.exists()


def cliente() -> bigquery.Client:
    return bigquery.Client.from_service_account_json(str(configuracao.ARQUIVO_CREDENCIAL))


def conectar(conteudo: bytes) -> None:
    """Testa a credencial e só a salva se o BigQuery aceitar."""
    try:
        dados = json.loads(conteudo)
    except ValueError as erro:
        raise ErroBigQuery("Esse arquivo não é um JSON válido.") from erro
    if not isinstance(dados, dict) or dados.get("type") != "service_account":
        raise ErroBigQuery("Esse arquivo não é a chave JSON de uma conta de serviço.")

    try:
        teste = bigquery.Client.from_service_account_info(dados)
        next(iter(teste.list_datasets(max_results=1)), None)
    except ERROS_GOOGLE as erro:
        raise ErroBigQuery(f"O BigQuery não aceitou a conexão: {_mensagem(erro)}") from erro
    configuracao.salvar_credencial(conteudo)


def desconectar() -> None:
    configuracao.apagar_credencial()


def _colunas(campos, prefixo: str = "") -> list[str]:
    colunas = []
    for campo in campos:
        nome = f"{prefixo}{campo.name}"
        colunas.append(f"{nome} {campo.field_type}")
        colunas += _colunas(campo.fields, f"{nome}.")
    return colunas


def ler_tabelas() -> tuple[str, bool]:
    """Retorna as tabelas em texto e se a lista foi cortada. Não tem custo de consulta."""
    conexao = cliente()
    linhas = []
    try:
        for dataset in conexao.list_datasets():
            for item in conexao.list_tables(dataset.reference):
                if len(linhas) == LIMITE_TABELAS:
                    return "\n".join(linhas), True
                tabela = conexao.get_table(item.reference)
                nome = f"{tabela.project}.{tabela.dataset_id}.{tabela.table_id}"
                linhas.append(f"{nome} ({', '.join(_colunas(tabela.schema))})")
    except ERROS_GOOGLE as erro:
        raise ErroBigQuery(f"Não consegui ler as tabelas: {_mensagem(erro)}") from erro
    return "\n".join(linhas), False


def validar(sql: str) -> int:
    """Faz um dry run, que não tem custo; retorna quantos bytes a consulta leria."""
    configuracao_job = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    try:
        job = cliente().query(sql, job_config=configuracao_job)
    except ERROS_GOOGLE as erro:
        raise ErroBigQuery(_mensagem(erro)) from erro
    return job.total_bytes_processed or 0


def executar(sql: str) -> tuple[list[dict], int]:
    """Executa só leitura, com limite de dados lidos; retorna as linhas e o total."""
    problema = checar_sql(sql)
    if problema:
        raise ErroBigQuery(problema)

    configuracao_job = bigquery.QueryJobConfig(maximum_bytes_billed=LIMITE_BYTES)
    try:
        linhas = cliente().query(sql, job_config=configuracao_job).result(max_results=LIMITE_LINHAS)
        return [dict(linha) for linha in linhas], linhas.total_rows
    except ERROS_GOOGLE as erro:
        raise ErroBigQuery(f"A consulta falhou: {_mensagem(erro)}") from erro


def formatar_bytes(quantidade: int) -> str:
    if quantidade < 1024:
        return f"{quantidade} bytes"
    valor = quantidade / 1024
    for unidade in ("KB", "MB", "GB"):
        if valor < 1024:
            return f"{valor:.1f} {unidade}".replace(".", ",")
        valor /= 1024
    return f"{valor:.1f} TB".replace(".", ",")
