# DDD App - Containerizado

Sistema completo para gerenciamento de contatos com consulta de regiões por DDD, totalmente containerizado com Docker.

## Arquitetura

- **PostgreSQL** (porta 5432) - Banco de dados
- **API DDD** (porta 3003) - Consulta de regiões por DDD
- **API Contatos** (porta 3004) - CRUD de contatos com integração à API DDD
- **Frontend Next.js** (porta 3000) - Interface web

## Como executar

1. **Pré-requisitos:**
   - Docker
   - Docker Compose

2. **Executar todo o sistema:**
   ```bash
   docker-compose up --build
   ```

3. **Executar em background:**
   ```bash
   docker-compose up -d --build
   ```

4. **Parar os serviços:**
   ```bash
   docker-compose down
   ```

5. **Parar e remover volumes (limpar dados):**
   ```bash
   docker-compose down -v
   ```

## Acessos

- **Frontend:** http://localhost:3000
- **API Contatos:** http://localhost:3004
- **API DDD:** http://localhost:3003
- **PostgreSQL:** localhost:5432

## Logs

Ver logs de um serviço específico:
```bash
docker-compose logs -f [nome-do-serviço]
```

Serviços disponíveis: `postgres`, `ddd-api`, `contacts-api`, `frontend`

## Desenvolvimento

Para desenvolvimento, você pode executar apenas alguns serviços:

```bash
# Apenas banco e APIs
docker-compose up postgres ddd-api contacts-api

# Apenas o frontend (se as APIs estiverem rodando)
docker-compose up frontend
```

## Estrutura dos Containers

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │───▶│  Contacts API   │───▶│    DDD API      │    │   PostgreSQL    │
│   (Next.js)     │    │   (FastAPI)     │    │   (FastAPI)     │    │                 │
│   Port: 3000    │    │   Port: 3004    │    │   Port: 3003    │    │   Port: 5432    │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                                               │
                                └───────────────────────────────────────────────┘
```
