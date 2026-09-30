# Contact Manager

Mini-aplicação full-stack para gestão inteligente de contatos. Nesta etapa, o
projeto contém apenas a infraestrutura inicial do backend, banco de dados e
frontend.

## Stack

- FastAPI, SQLAlchemy 2 e Alembic
- PostgreSQL 16
- Next.js, React e TypeScript

## Pré-requisitos

- Python 3.11 ou superior
- Node.js 20.9 ou superior
- Docker com Docker Compose

## Variáveis de ambiente

Na raiz do projeto, crie o arquivo local de configuração a partir do exemplo:

```bash
cp .env.example .env
```

O arquivo `.env` é ignorado pelo Git e não deve ser versionado.

## Banco de dados

Inicie o PostgreSQL:

```bash
docker compose up -d
```

Para conferir o estado do container, execute `docker compose ps`.

## Backend

Crie e ative o ambiente virtual:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

No Windows PowerShell, use `.venv\Scripts\Activate.ps1` para ativá-lo.

Instale as dependências e inicie a API:

```bash
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

A API estará disponível em `http://localhost:8000`, e a documentação Swagger
em `http://localhost:8000/docs`.

Para executar os testes:

```bash
pytest
```

## Frontend

Em outro terminal, instale as dependências e inicie o Next.js:

```bash
cd frontend
npm install
npm run dev
```

O frontend estará disponível em `http://localhost:3000`.
