"""Guarda a chave e as tabelas em arquivos locais, para o usuário informar só uma vez."""

import os
from pathlib import Path

from dotenv import load_dotenv, set_key

PASTA = Path(__file__).parent
ARQUIVO_CHAVE = PASTA / ".env"
ARQUIVO_TABELAS = PASTA / "tabelas.txt"


def carregar_chave() -> None:
    load_dotenv(ARQUIVO_CHAVE)


def salvar_chave(chave: str) -> None:
    set_key(ARQUIVO_CHAVE, "ANTHROPIC_API_KEY", chave)
    os.environ["ANTHROPIC_API_KEY"] = chave


def carregar_tabelas() -> str:
    if ARQUIVO_TABELAS.exists():
        return ARQUIVO_TABELAS.read_text(encoding="utf-8")
    return ""


def salvar_tabelas(tabelas: str) -> None:
    ARQUIVO_TABELAS.write_text(tabelas, encoding="utf-8")
