# Contacts Service API

API para gerenciamento de contatos com integração ao serviço de DDD.

## Configuração

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

2. Configure o PostgreSQL:
   - Crie um banco de dados chamado `contacts_db`
   - Ajuste a string de conexão no arquivo `main.py` (linha 11)

3. Execute a aplicação:
```bash
python main.py
```

A API estará disponível em `http://localhost:3004`

## Endpoints

- `POST /contacts/` - Criar novo contato
- `GET /contacts/` - Listar todos os contatos
- `GET /contacts/{phone}` - Buscar contato por telefone
- `PUT /contacts/{phone}` - Atualizar contato
- `DELETE /contacts/{phone}` - Deletar contato
- `PATCH /contacts/{phone}/favorite` - Alternar favorito

## Banco de Dados

A tabela `contacts` será criada automaticamente com os campos:
- phone (chave primária)
- name
- address
- region (obtida automaticamente via API de DDD)
- is_favorite
