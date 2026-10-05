# Contact Manager

Aplicação full-stack do teste técnico Neofuturo para gestão de contatos, tags,
importação em lote, resumos de IA e enriquecimento de endereço por CEP.

## Stack

- Frontend: Next.js 16, React 19 e TypeScript.
- Backend: FastAPI, SQLAlchemy 2, Alembic e Pydantic.
- Banco: PostgreSQL 16.
- Integrações: OpenAI e ViaCEP, isoladas em services.

## Pré-requisitos

- Python 3.11+, Node.js 20.9+ e npm.
- Docker em execução, Docker Compose e Git.
- Google Chrome para os testes de interface.
- Portas locais 5432, 8000 e 3000 livres para executar a aplicação.

## Estrutura

- `backend/`: API, modelos, services, migrations e testes Python.
- `frontend/`: páginas Next.js, cliente HTTP, tipos e testes de interface.
- `docker-compose.yml`: somente PostgreSQL, com healthcheck e volume persistente.

## Variáveis de ambiente

Na raiz do repositório, prepare os arquivos locais sem sobrescrever configurações
já existentes:

```bash
cp -n .env.example .env
cp -n frontend/.env.example frontend/.env.local
```

- `DATABASE_URL`: conexão SQLAlchemy com PostgreSQL; o exemplo usa as credenciais
  públicas de desenvolvimento do Compose.
- `OPENAI_API_KEY`: opcional para subir a aplicação; preencha somente no `.env`
  local para habilitar geração real de resumos. Sem chave, essa ação retorna 503.
- `FRONTEND_ORIGINS`: origens CORS separadas por vírgula; por padrão permite
  `http://localhost:3000` e `http://127.0.0.1:3000`. Espaços e itens vazios são ignorados.
- `NEXT_PUBLIC_API_URL`: endereço público da API, por padrão
  `http://127.0.0.1:8000`. Não coloque segredos em variáveis `NEXT_PUBLIC_*`.

A API lê o `.env` da **raiz**, não `backend/.env`. O Next.js lê
`frontend/.env.local`. Ambos são ignorados pelo Git. Os exemplos não contêm chaves
reais; não versione credenciais e não use as credenciais locais em produção.

## Banco de dados

Execute na raiz, onde está o `docker-compose.yml`:

```bash
docker compose config
docker compose up -d
docker compose ps
```

O serviço `db` deve aparecer como `healthy` e publica PostgreSQL somente em
`127.0.0.1:5432`. Os dados são preservados no volume;
`docker compose down` interrompe os containers sem apagar os dados. Não use `down -v`
no ambiente que contém contatos reais.

## Backend

Em um terminal na raiz, crie e ative o ambiente virtual:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
alembic upgrade head
alembic current
alembic check
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

No Windows PowerShell, use `.venv\Scripts\Activate.ps1` para ativá-lo.

A API estará em `http://127.0.0.1:8000`, com Swagger em
`http://127.0.0.1:8000/docs` e saúde em `http://127.0.0.1:8000/health`.
As migrations criam todo o schema; não é necessário criar tabelas manualmente.

## Frontend

Em outro terminal na raiz:

```bash
cd frontend
npm ci
npm run dev
```

Abra `http://localhost:3000`. A listagem dá acesso ao detalhe e a `/import`.
Por padrão, o CORS permite `localhost:3000` e `127.0.0.1:3000`; mantenha a porta
3000 ou ajuste `FRONTEND_ORIGINS` para usar outra origem local.

## Testes

Use um banco separado para não misturar fixtures com contatos reais. Na raiz,
crie o banco de testes uma única vez:

```bash
docker compose exec -T db createdb -U postgres contact_manager_test
```

Depois, com o virtualenv ativo, execute em `backend/`:

```bash
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/contact_manager_test
export OPENAI_API_KEY=""
alembic upgrade head
pytest
```

Use um terminal separado para os testes ou remova esses overrides com
`unset DATABASE_URL OPENAI_API_KEY` antes de iniciar novamente a API principal.
Os testes isolam seus dados com transações e simulam OpenAI e ViaCEP.

Em `frontend/`, execute:

```bash
npm run lint
npm run build
npm install --prefix /tmp/contact-manager-browser --no-save playwright@1.63.0
PLAYWRIGHT_MODULE_PATH=/tmp/contact-manager-browser/node_modules/playwright npm run test:browser
```

O último comando usa Node Test Runner e Playwright, com Chrome instalado, API
simulada e Next.js temporário. A ferramenta fica fora das dependências da
aplicação. Não execute builds simultâneos com essa suíte. Opções de portas e
instalação estão em [frontend/tests/README.md](frontend/tests/README.md).

## Funcionalidades

- Criação via API com nome sem espaços extras, e-mail lowercase validado,
  telefone brasileiro de 11 dígitos e rejeição de e-mail duplicado (409).
- Listagem paginada, filtro por tag, indicador de resumo e detalhe completo.
- Criação de tags via API e associação/remoção pelo detalhe do frontend.
- Importação parcial pela API e `/import`: cole um array JSON com `full_name`,
  `email`, `phone` e `source` opcional. Itens inválidos e duplicatas no banco ou
  no lote são rejeitados sem impedir a persistência dos válidos.
- O relatório usa `imported`, `rejected` e `errors: [{index, reason}]`. O índice
  da API começa em zero; a interface mostra os itens a partir de 1 e mantém os
  motivos retornados pelo backend. JSON inválido ou que não seja array não é enviado.
- Resumo com OpenAI somente por clique explícito, com histórico persistido.
- Consulta ViaCEP com CEP de 8 dígitos, com ou sem hífen, e endereço persistido.

## Decisões técnicas

- Endereço em PostgreSQL JSONB; tags N:N com chave composta; resumos 1:N com
  timestamps timezone-aware. Constraints protegem a integridade no banco; o pool
  verifica conexões antes de reutilizá-las para tolerar reinícios do PostgreSQL.
- Normalização centralizada em services e reaproveitada pelos schemas Pydantic.
- Carregamento inicial em Server Components; ações em Client Components pequenos,
  HTTP centralizado e atualização local de estado, sem biblioteca externa de estado.
- OpenAI usa `gpt-4o-mini`, timeout de 15s, `max_retries=0`, limite de 150 tokens
  de saída e uma chamada por ação explícita. O frontend bloqueia cliques repetidos
  durante envio, não faz polling nem retry automático.
- Testes usam mocks para integrações externas; abrir páginas, build e lint não
  geram resumos nem consomem OpenAI.

## Diferenciais

- Suíte backend com testes unitários e de integração para normalização, contatos,
  tags, consultas, importação e integrações externas simuladas, sem internet real.
- Rate limit da OpenAI retorna HTTP 429 com mensagem amigável, sem expor detalhes
  internos nem persistir resumo parcial. `max_retries=0` impede novas tentativas;
  o teste com SDK e transporte simulado confirma uma única chamada, sem fallback.
- Cache ViaCEP em memória por CEP normalizado, sem dependência externa. O TTL de
  1 hora, medido com `time.monotonic()`, reduz consultas repetidas e permite
  atualização periódica. Armazena apenas endereços válidos, nunca erros.
- O cache limita-se a 256 entradas: remove expiradas antes da inserção e, se
  necessário, a mais antiga. É local ao processo, reinicia com a aplicação e
  cada worker possui seu próprio cache. Os testes limpam o cache entre cenários.
- Deploy não realizado nesta etapa.

## Deploy

Repositório preparado, mas **nenhum deploy foi realizado**. Arquitetura prevista:
Vercel para o frontend Next.js, Railway para a API e Railway PostgreSQL para o banco.
O Docker Compose continua sendo exclusivamente local.

No painel do **Railway**, configure o backend:

- Root Directory: `backend`.
- Builder: Railpack; Build Command sem override. O `requirements.txt` já declara
  as dependências necessárias e é instalado automaticamente pelo
  [Railpack](https://railpack.com/languages/python/).
- Start Command: `sh start.sh`. O script aplica `alembic upgrade head` e só então
  executa Uvicorn em `0.0.0.0`, usando `PORT` fornecida pelo Railway (fallback local
  de 8000). Não use `--reload` em produção.
- Healthcheck Path: `/health`; retorna HTTP 200 sem consultar banco, OpenAI ou ViaCEP.
- `DATABASE_URL`: referência à variável do serviço PostgreSQL do Railway, não
  à conexão local. URLs `postgresql://` são convertidas para `postgresql+psycopg://`,
  preservando credenciais e parâmetros; URLs já configuradas são mantidas.
- `OPENAI_API_KEY`: opcional, somente no backend. Sem chave, a aplicação inicia
  normalmente e apenas a geração de resumo de contato existente retorna 503.
- `FRONTEND_ORIGINS`: origem HTTPS pública da Vercel, sem caminho ou barra final.
  Para mais de uma origem, separe por vírgulas. A configuração substitui o padrão
  local; não permite `*` nem credenciais. GET, POST e DELETE mantêm suporte a preflight.

Não foi criado `railway.toml`: o Railway
[descontinuou Config as Code para novos serviços](https://docs.railway.com/config-as-code).
Use o script versionado e configure Root Directory, Start Command e health check
no painel, sem duplicar essas definições em arquivos da plataforma.

Na **Vercel**, use Root Directory `frontend`, preset Next.js, instalação npm padrão
e Build Command `npm run build`. Não é necessário `vercel.json`. Configure
`NEXT_PUBLIC_API_URL` com a URL HTTPS pública do backend antes do build; mudanças
nessa variável exigem novo build. Ela é pública e nunca deve conter chaves.

No deploy futuro, publique o backend, use seu domínio na Vercel e, depois, atualize
`FRONTEND_ORIGINS` com a origem final da Vercel e reinicie/republique o backend.
Segredos ficam nas variáveis do backend; não envie `.env` locais ao Git ou frontend.
O cache ViaCEP permanece em memória por processo, sendo limpo a cada reinício.

## Verificação local

No Swagger, crie contatos e tags. Confira a listagem, filtro, paginação e detalhe;
adicione/remova tags e importe um lote misto em `/import`. Consulte o GET do
contato para conferir persistência. Para IA, visualizar um resumo existente não
gera cobrança; clicar em **Gerar resumo com IA** faz uma chamada real se houver
chave configurada. Não é preciso repetir essa chamada para validar a interface.

## Validação manual

Testes manuais realizados:

- Criação de contato pelo Swagger, confirmando normalização do nome, email e telefone.
- Tentativa de criação com email duplicado, confirmando rejeição com HTTP 409.
- Visualização dos contatos na listagem e navegação para o detalhe.
- Criação de tags pelo Swagger e associação/remoção pelo frontend.
- Recarregamento da página para confirmar persistência das associações.
- Validação do filtro por tag e da paginação.
- Importação em lote pelo frontend, conferindo contatos importados, rejeitados e motivos.
- Validação de JSON inválido (`[`) e conteúdo que não é array (`{}`), confirmando
  erros antes do envio.
- Consulta de CEP pelo frontend e persistência do endereço após recarregar a página.
- Geração explícita de resumo com IA e persistência após recarregar, sem geração automática.
- Consulta de `GET /contacts/{contact_id}` pelo Swagger, confirmando que tags,
  endereço e último resumo correspondem aos dados exibidos no frontend.
