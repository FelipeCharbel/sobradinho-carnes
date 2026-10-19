# Guia de Deploy: Supabase + Vercel

Este documento descreve como implantar a Sobradinho Carnes em produção usando **Supabase** (banco de dados Postgres gerenciado) e **Vercel** (servidor serverless).

## ⚠️ Importante

Este guia descreve os passos de configuração baseado em documentação pública de Supabase e Vercel. **Os passos não foram validados contra uma conta real de Supabase neste ambiente de desenvolvimento.** Recomenda-se testes em um ambiente de staging antes de colocar em produção.

---

## 1. Preparar o Projeto

### 1.1 Verificar estrutura de arquivos

Certifique-se de que você tem:

```
sobradinho-carnes/
├── server/
│   ├── main.py
│   ├── db.py          ✓ Ajustado para Postgres (Fase 2)
│   ├── seed.py
│   └── ...
├── public/
│   └── index.html
├── requirements.txt
├── vercel.json        (criar abaixo)
└── README.md
```

### 1.2 Verificar `requirements.txt`

Confirme que `psycopg[binary]` está presente (necessário para Postgres):

```
sqlalchemy==2.0.28
psycopg[binary]==3.1.18
fastapi==0.110.0
uvicorn[standard]==0.27.0
```

---

## 2. Criar Projeto no Supabase

### 2.1 Inscrever-se e criar projeto

1. Acesse [https://supabase.com](https://supabase.com)
2. Clique em **"Start your project"**
3. Entre com GitHub ou e-mail
4. Clique em **"New Project"**
5. Escolha um nome (ex.: `sobradinho-carnes-prod`)
6. Selecione região próxima (ex.: `São Paulo - sa-east-1` se disponível)
7. Defina uma senha forte para o usuário `postgres`
8. Clique em **"Create new project"**

### 2.2 Encontrar a connection string

1. Após o projeto ser criado, clique em **"Connect"** (botão no canto superior direito)
2. Na modal que abre, selecione **"URI"** (não "Connection parameters")
3. Copie a connection string no formato:

```
postgresql://postgres:[password]@[host]:[port]/postgres
```

**Exemplos:**
```
postgresql://postgres:abc123xyz@db.example.supabase.co:5432/postgres
```

---

## 3. Configurar Variáveis de Ambiente no Vercel

### 3.1 Acessar projeto na Vercel

1. Acesse [https://vercel.com](https://vercel.com)
2. Clique no projeto `sobradinho-carnes` (ou crie um novo)
3. Vá para **Settings** → **Environment Variables**

### 3.2 Adicionar `DATABASE_URL`

1. Clique em **"Add New"**
2. Nome: `DATABASE_URL`
3. Valor: cole a connection string do Supabase (ex.: `postgresql://postgres:...@db.example.supabase.co:5432/postgres`)
4. Scopes: selecione todos (Production, Preview, Development)
5. Clique em **"Save"**

### 3.3 Adicionar `SECRET_KEY`

Se ainda não existe:

1. Clique em **"Add New"**
2. Nome: `SECRET_KEY`
3. Valor: gere uma string aleatória segura (ex.: com `python -c "import secrets; print(secrets.token_hex(32))"`)
4. Scopes: selecione todos
5. Clique em **"Save"**

---

## 4. Preparar o Banco de Dados

### 4.1 Executar seed contra a instância Supabase

**Antes do primeiro acesso**, execute `seed.py` contra o banco de produção para criar a tabela `Configuracao` e registrar o código do primeiro admin:

```bash
export DATABASE_URL="postgresql://postgres:[password]@db.example.supabase.co:5432/postgres"
python -m server.seed
```

Se bem-sucedido, você verá:

```
Banco criado. Primeiro admin: SC-2026-001
```

**Guarde esse código** — é necessário para fazer login pela primeira vez.

### 4.2 Verificar tabelas

Você pode verificar as tabelas criadas no Supabase:

1. Acesse o projeto Supabase → **SQL Editor**
2. Execute:

```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'public';
```

Você deve ver as 9 tabelas: `Cargos`, `Entrevistas`, `Usuarios`, `Configuracao`, etc.

---

## 5. Deploying para Vercel

### 5.1 Criar `vercel.json` (se não existir)

```json
{
  "buildCommand": "pip install -r requirements.txt",
  "devCommand": "uvicorn server.main:app --host 0.0.0.0 --port 3000",
  "outputDirectory": "public",
  "functions": {
    "server/main.py": {
      "runtime": "python3.11"
    }
  }
}
```

### 5.2 Deploy via Git

1. Faça commit de todas as mudanças:

```bash
git add .
git commit -m "Fase 2: exportação PPTX + Supabase"
git push origin main
```

2. No Vercel, o deploy será **automático** (webhooks do GitHub)

3. Acompanhe o deploy em **Vercel Dashboard** → **Deployments**

### 5.3 Verificar deploy

Após o deploy bem-sucedido:

1. Acesse a URL do projeto (ex.: `https://sobradinho-carnes.vercel.app`)
2. Faça login com o código do primeiro admin (gerado no seed)
3. Verifique se o banco está funcionando (tente adicionar um cargo)

---

## 6. Gerenciamento de Conexões em Serverless

### 6.1 Problema: Esgotamento de Conexões

Em ambientes serverless, cada invocação pode manter uma conexão aberta. Com muitas invocações simultâneas, você pode esgotar o limite de conexões do Supabase.

**Solução: Use o Connection Pooler do Supabase** (Modo Transaction)

### 6.2 Ativar Connection Pooler

1. No Supabase, vá para **Project Settings** → **Database**
2. Em **Connection info**, você verá dois opcodes:
   - **Direct connection** (porta 5432): uso local/dev
   - **Connection pooler** (porta 6543): uso serverless ✓

3. Para serverless (Vercel), use a connection pooler:

```
postgresql://postgres:[password]@db.example.supabase.co:6543/postgres
```

4. Atualize `DATABASE_URL` no Vercel com a porta **6543** em vez de 5432

### 6.3 Configuração no código

`server/db.py` já contém `pool_pre_ping=True`, que reconecta automaticamente se a conexão cair. Nenhuma mudança é necessária no código.

---

## 7. Troubleshooting

### "Connection refused" ou timeout

- Verifique se `DATABASE_URL` foi salva corretamente no Vercel
- Confirme se o host está acessível (whitelist de IPs)
- Se usar connection pooler, verifique se é a porta 6543

### "too many connections"

- Use o connection pooler (porta 6543) em vez da conexão direta
- Reduza `pool_size` em `db.py` se necessário (padrão é automático)

### Dados não persistem após deploy

- Isso indica que você estava usando SQLite em arquivo
- Confirme que `DATABASE_URL` aponta para Supabase (começa com `postgresql://` ou `postgres://`)
- Reexecute `seed.py` contra Supabase se não tiver feito

### Erro ao fazer login

- Execute `seed.py` para criar a tabela `Configuracao`
- Use o código gerado (ex.: `SC-2026-001`)

---

## 8. Monitoramento

### Verificar logs

1. **Vercel**: Dashboard → **Deployments** → selecione um → **Logs**
2. **Supabase**: Dashboard → **Logs** → **Postgres** para queries SQL

### Métricas de uso

- **Supabase**: Project → **Reports** → Storage, Bandwidth, Database
- **Vercel**: Project → **Analytics** → Runtime, Requests

---

## 9. Próximos Passos

- [ ] Validar login e fluxo de entrevista em produção
- [ ] Testar download de apresentações (.pptx)
- [ ] Configurar backups automáticos do Supabase (já ativado por padrão)
- [ ] Documentar procedimento de recuperação em caso de falha
- [ ] Integrar logs centralizados (Sentry, DataDog, etc.)

---

**Última atualização**: 2026-10-19
**Status de validação**: Baseado em documentação pública; não testado contra conta real de Supabase neste ambiente.
