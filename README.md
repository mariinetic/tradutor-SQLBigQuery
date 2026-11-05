# Tradutor SQL BigQuery

Escreva uma pergunta em português e receba o SQL do BigQuery. Se quiser, conecte o app ao BigQuery para ele ler suas tabelas, conferir o SQL e executar a consulta.

## Como abrir

No Windows, dê dois cliques em `abrir.bat`. Na primeira vez, ele prepara tudo sozinho, o que pode levar alguns minutos. É preciso ter o [Python](https://www.python.org/downloads/) instalado.

O app abre no navegador e pede uma chave da API da Anthropic, criada em <https://platform.claude.com>. Você só informa a chave uma vez, e ela fica salva no arquivo `.env`, neste computador. Cada tradução é cobrada na sua conta da API.

## Como usar

Escreva a pergunta e aperte Enter, ou clique em um dos exemplos. Para copiar o SQL, use o ícone no canto do código.

Para o SQL sair com os nomes certos, cole suas tabelas e colunas em **Minhas tabelas**, em qualquer formato. Elas ficam salvas no arquivo `tabelas.txt`. Sem isso, o SQL usa nomes de exemplo para você trocar.

O app mostra também o que foi considerado, como "do mês" significar o mês atual.

## Como conectar ao BigQuery

A conexão é opcional. Para fazer:

1. No [Google Cloud](https://console.cloud.google.com), crie ou escolha um projeto.
2. Em **IAM e administrador > Contas de serviço**, crie uma conta de serviço com os papéis **BigQuery Data Viewer** e **BigQuery Job User**.
3. Na conta criada, abra **Chaves > Adicionar chave > Criar nova chave > JSON** e baixe o arquivo.
4. No app, abra **Conectar ao BigQuery**, envie o arquivo e clique em **Conectar**. Ele fica salvo em `credencial_bigquery.json`, neste computador.

Depois de conectado:

- As tabelas são lidas sozinhas, até 200 por vez. Use **Atualizar tabelas** quando elas mudarem. Isso substitui a lista salva em **Minhas tabelas**.
- Cada SQL é conferido com um dry run, que não tem custo de consulta e mostra quanto ele leria.
- A consulta só roda quando você clica em **Executar consulta**, e o BigQuery pode cobrar por ela. O app só executa consultas de leitura, recusa as que leriam mais de 10 GB e mostra até 1.000 linhas.

## Limites

Sem a conexão, a checagem é local: confere a sintaxe e se o SQL é só leitura, mas não sabe se as tabelas e colunas existem. Revise o SQL antes de usar.

O app aceita acesso apenas deste computador, porque guarda as suas chaves. Não o publique na internet como está: quem o abrisse usaria as suas chaves.

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
