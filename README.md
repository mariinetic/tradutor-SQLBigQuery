# Tradutor SQL BigQuery

Escreva uma pergunta em português e receba o SQL do BigQuery. O app só gera o SQL: não se conecta ao BigQuery e não executa nada.

## Como abrir

No Windows, dê dois cliques em `abrir.bat`. Na primeira vez, ele prepara tudo sozinho, o que pode levar alguns minutos. É preciso ter o [Python](https://www.python.org/downloads/) instalado.

O app abre no navegador e pede uma chave da API da Anthropic, criada em <https://platform.claude.com>. Você só informa a chave uma vez, e ela fica salva no arquivo `.env`, neste computador. Cada tradução é cobrada na sua conta da API.

## Como usar

Escreva a pergunta e aperte Enter, ou clique em um dos exemplos. Para copiar o SQL, use o ícone no canto do código.

Para o SQL sair com os nomes certos, cole suas tabelas e colunas em **Minhas tabelas**, em qualquer formato. Elas ficam salvas no arquivo `tabelas.txt`. Sem isso, o SQL usa nomes de exemplo para você trocar.

O app mostra também o que foi considerado, como "do mês" significar o mês atual.

## Limites

A checagem é local: confere a sintaxe e se o SQL é só leitura, mas não sabe se as tabelas e colunas existem. Revise o SQL antes de usar.

O app aceita acesso apenas deste computador, porque guarda a sua chave. Não o publique na internet como está: quem o abrisse usaria a sua chave.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Os testes não chamam a API de verdade e não têm custo.

## Avaliação da tradução

Este script envia 12 perguntas ao modelo e confere se o SQL de cada uma está correto. Ele chama a API de verdade, então tem custo. Usa a chave salva pelo app.

```powershell
.\.venv\Scripts\python.exe avaliar.py
```

O relatório aparece no terminal e fica salvo em `avaliacao.txt`.
