# GLPI MariaDB MCP

Servidor MCP (consulta somente leitura) para expor um acesso controlado ao banco MariaDB do GLPI
para agentes de IA via HTTP com autenticação por token.

## Arquitetura

```text
Codex / Claude / Antigravity
        |
        | Streamable HTTP + Bearer token
        v
  GLPI MariaDB MCP (aplicação)
        |
        | usuário MariaDB com permissões SELECT
        v
      MariaDB (GLPI)
```

## Funcionalidades principais

- Endpoint streamable em `/mcp`
- Health check em `/health`
- Autenticação via `Authorization: Bearer <TOKEN>`
- Descoberta de tabelas e colunas
- Descrição de tabelas e índices
- Prévia limitada de registros (`preview`)
- Análise de consultas com `EXPLAIN`
- Execução controlada de `SELECT` (somente leitura)
- Timeouts e limite de linhas para proteger o banco

## Ferramentas (API interno)

| Tool              | Descrição                                  |
| ----------------- | ------------------------------------------ |
| `server_status`   | Verifica o status do servidor MCP          |
| `database_status` | Verifica a conexão com o MariaDB           |
| `search_tables`   | Pesquisa tabelas pelo nome                 |
| `describe_table`  | Mostra colunas e índices de uma tabela     |
| `search_columns`  | Pesquisa colunas por nome                  |
| `preview_table`   | Retorna uma amostra limitada de registros  |
| `explain_select`  | Retorna o plano de execução de um `SELECT` |
| `execute_select`  | Executa consulta somente leitura           |

## Requisitos

- Python 3.13
- Rede com acesso ao MariaDB (host/porta)
- Usuário MariaDB com permissão apenas `SELECT`
- (Para implantação) Docker e Docker Compose ou Portainer

## Desenvolvimento local

1. Instale dependências:

```bash
uv sync
```

2. Crie a configuração local copiando o exemplo:

```powershell
Copy-Item .env.example .env
# Edite .env com os valores reais
```

3. Inicie a aplicação:

```bash
uv run --env-file .env python -m app.server
```

Endpoints locais (padrão):

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/mcp`

## Variáveis de ambiente

| Variável                  | Obrigatória | Padrão      | Descrição                      |
| ------------------------- | ----------- | ----------- | ------------------------------ |
| `MCP_HOST`                | não         | `127.0.0.1` | Interface HTTP                 |
| `MCP_PORT`                | não         | `8000`      | Porta interna                  |
| `MCP_BEARER_TOKEN`        | sim         | -           | Token de autenticação (Bearer) |
| `MARIADB_HOST`            | sim         | -           | Host do MariaDB                |
| `MARIADB_PORT`            | não         | `3306`      | Porta do MariaDB               |
| `MARIADB_DATABASE`        | sim         | -           | Database do GLPI               |
| `MARIADB_USER`            | sim         | -           | Usuário somente leitura        |
| `MARIADB_PASSWORD`        | sim         | -           | Senha do usuário               |
| `MARIADB_CONNECT_TIMEOUT` | não         | `10`        | Timeout de conexão (s)         |
| `MARIADB_QUERY_TIMEOUT`   | não         | `10`        | Timeout de consulta (s)        |

Gere um token seguro (exemplo):

```bash
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

Nunca versionar arquivos `.env`, senhas ou tokens.

## Testes

Rode a suíte de testes com:

```bash
uv run pytest
```

## Docker

Para construir e executar:

```bash
docker compose up --build -d
```

Endpoints (exemplo de acesso em produção):

- `http://<IP-DO-SERVIDOR>:18274/health`
- `http://<IP-DO-SERVIDOR>:18274/mcp`

### Portainer

Ao criar uma Stack a partir deste repositório, informe as variáveis obrigatórias:

- `MCP_BEARER_TOKEN`, `MARIADB_HOST`, `MARIADB_DATABASE`, `MARIADB_USER`, `MARIADB_PASSWORD`

As demais variáveis possuem valores padrão no `compose.yaml`.

## Autenticação

Todas as requisições à API devem conter o header:

```
Authorization: Bearer <SEU_TOKEN>
```

Requisições sem token válido retornam `401 Unauthorized`.

## Segurança e limitações conhecidas

- Projeto versão inicial (0.1.0) para uso em rede interna.
- Medidas de proteção: uso de token, usuário MariaDB somente leitura, validação textual de SQL,
  bloqueio de múltiplas instruções, timeouts e limites de linhas.
- Limitações: token único compartilhado, ausência de TLS/HTTPS por padrão, sem rate limiting,
  sem pool de conexões, validação textual de SQL (não é um parser completo).

Use apenas em redes controladas; recomenda-se evoluir para HTTPS e tokens por cliente.

## Observações finais

- Não publique IPs reais, senhas, tokens ou hostnames internos.
- Projeto interno — não compartilhar credenciais nem dados de infraestrutura.

---
