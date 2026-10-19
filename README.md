# Gestão Sobradinho Carnes — migração para FastAPI

Fase 1: migração da plataforma de gestão do Google Apps Script (`raw_source/Codigo.gs` +
`raw_source/Index.html`) para uma stack própria: **FastAPI + SQLAlchemy + frontend estático**,
pronta para deploy na Vercel. Ver `docs/CONTRATOS.md` para o contrato completo (RPC, schema das
tabelas, sessão, hash de senha) usado na migração.

Fase 2: integração da skill `manual-cargos-funcoes` — exportação de manuais de cargos em
`.pptx` (ficha individual e manual institucional completo, com organograma) direto da
plataforma, mais preparação para banco Postgres gerenciado (Supabase). Ver
`docs/CONTRATOS_FASE2.md` para o contrato completo dessa fase.

## Rodando localmente

```bash
pip install -r requirements.txt

# 1. Prepara o banco (SQLite por padrão) e gera o código do primeiro administrador
python -m server.seed
# imprime algo como:
# CÓDIGO DE ADMINISTRADOR (vale para um único cadastro): XXXXXXXXXX

# 2. Sobe o servidor
uvicorn server.main:app --reload --port 8000
```

Abra `http://localhost:8000/` — é a mesma tela de login do Apps Script original. Em
"Primeiro acesso" → "Sou do Grupo Gestão", use o código impresso pelo `seed.py` para criar o
primeiro administrador.

### Variáveis de ambiente

Copie `.env.example` para `.env` e ajuste:

- `DATABASE_URL` — `sqlite:///./sobradinho.db` (padrão local) ou uma URL Postgres em produção.
- `SECRET_KEY` — segredo do HMAC dos tokens de sessão. **Gere um valor aleatório forte**; nunca
  comite o `.env` (já está no `.gitignore`).

## Rodando os testes

```bash
pytest tests/ -v
```

65 testes cobrem: hash de senha compatível com a planilha original, bloqueio de login após 5
tentativas, regras de visibilidade por perfil (`modelo_`/`retrato_`), rejeição de ciclos no
organograma, o motor de redação de texto (formalização de funções/rotinas/jornada/missão/
"recorre a", ≥40 casos de paridade com os exemplos do `Codigo.gs`), o fluxo completo do TO BE
(editar com personalização → conflito com o AS IS → resolver → justificar → publicar), e a
geração de `.pptx` (Fase 2: mapeamento de schema, dobra de frequências, organograma, integridade
do arquivo gerado — zero entradas duplicadas no ZIP OOXML).

## Exportação de manuais em .pptx (Fase 2)

- **Ficha de um cargo** (Modo B, 5 páginas, sem organograma): botão "Baixar Ficha (.pptx)" no
  drawer de qualquer cargo visível, ou `GET /api/export/cargo/{cargo_id}?token=...`. Quem não é
  admin só baixa cargos com manual **publicado** dentro do próprio escopo de visibilidade.
- **Manual completo** (Modo A, institucional, com organograma): botão "Exportar Manual Completo
  (.pptx)" na tela de Cargos (só admin/sócio), ou `GET /api/export/manual-completo?token=...`.
  Compila todos os cargos publicados, no template oficial T2 (`assets/T2.pptx`), cor institucional
  `#E2010F`.
- O token vai na **query string** desses dois endpoints (não no corpo JSON como o resto do RPC),
  porque é um download direto pelo navegador via `<a href>`.

## Deploy na Vercel

1. Crie um banco **Postgres** (Vercel Postgres, Neon, Supabase etc.) — **SQLite em arquivo não
   persiste em funções serverless**: cada invocação pode rodar num container efêmero diferente,
   então qualquer dado gravado em SQLite local se perde entre chamadas. Use SQLite **só para
   desenvolvimento local**.
2. Configure as variáveis de ambiente do projeto na Vercel: `DATABASE_URL` (string de conexão do
   Postgres) e `SECRET_KEY`.
3. Rode `python -m server.seed` **uma vez**, localmente, apontando `DATABASE_URL` para o mesmo
   banco Postgres de produção (ou crie uma rotina equivalente de inicialização), para gerar o
   código do primeiro administrador antes do primeiro acesso em produção.
4. `vercel deploy` — o `vercel.json` já aponta `/api/*` para `server/main.py` (FastAPI) e o
   restante para os estáticos em `public/`. **Confira a sintaxe de `runtime` em `vercel.json`
   contra a documentação atual da Vercel antes do primeiro deploy** — o formato de runtime Python
   da Vercel muda de tempos em tempos e não foi validado contra uma conta real neste ambiente de
   desenvolvimento.

Para usar **Supabase** como banco Postgres gerenciado, ver o passo a passo em
`docs/DEPLOY_SUPABASE.md` (também não validado contra uma conta real — revisar antes de seguir).

## O que foi portado (Fase 1)

Todas as ~31 funções `api_*` do `Codigo.gs` original, incluindo o bloco TO BE inteiro
(`sincronizarTobe_`, `tobeSalvar_`, `tobeJustificar_`, `tobeResolver_`, `tobePublicar_`,
`visualizarComo_`) e o motor de redação de texto (`formalizar`, `ajustaFuncao`/`ajustaRotina`,
`formalizarMissao`, `formalizarJornada`, `recorreNormaliza`, `lerTexto`). Ver `docs/CONTRATOS.md`
para a lista completa com o módulo de cada função.

## Pendências conhecidas (documentadas, não escondidas)

- **`novaEntrevista_` e `lerDoc_`** (criação/leitura de Google Docs): fora de escopo nesta versão.
  `api_novaEntrevista` devolve o erro "Disponível só pelo texto colado nesta versão." O leitor de
  entrevistas (`lerTexto`) continua funcionando normalmente a partir de texto colado, inclusive a
  autoavaliação marcada no formato `***( 4 )***`. Fica para a Fase 2.
- **Renovação de sessão só nas mutações.** O `.gs` original renova o TTL da sessão em
  **toda** chamada autenticada (`sessao_` roda em quase todo handler). Como o token aqui é
  assinado e stateless (sem cache compartilhado), a implementação atual só devolve um token
  renovado nas chamadas que gravam algo (`mudar_`/`mudar+sync`); chamadas só de leitura (ex.:
  abrir o snapshot repetidamente sem salvar nada) não renovam o prazo de 30 minutos. Na prática,
  isso só afeta sessões muito longas de uso só-leitura; não afeta o fluxo normal de uso
  (quem navega e edita volta a renovar o token a cada salvamento). Fica registrado como melhoria
  da Fase 2 caso vire um problema real de uso.
- **Bloqueio de login** persiste tentativas numa tabela própria (`TentativasLogin`), já que não
  há `CacheService` equivalente — comportamento equivalente ao original (5 erros → 15 min de
  bloqueio), só que a persistência é em banco em vez de cache em memória.
- **Código do primeiro administrador** (`ADMIN_CODIGO`) é persistido numa tabela própria
  (`Configuracao`), não em variável de ambiente — necessário porque não há processo único de
  longa duração nem variável de ambiente compartilhada entre invocações serverless.
- **Campos do manual sem correspondência no banco (Fase 2).** O schema da skill
  `manual-cargos-funcoes` pede `competencias`, `autonomia` e `processos` por cargo — nenhum dos
  três existe no modelo de dados da Sobradinho Carnes (a entrevista da Fase 1 não coleta isso).
  Esses três campos saem sempre como `"A confirmar."` no `.pptx` gerado, nunca inventados. A
  `supervisão exercida` é a exceção: é calculada de verdade a partir do organograma (quem reporta
  a quem), não "A confirmar.".
- **E-mails do Grupo Gestão na contra-capa do manual completo** ficam em uma lista vazia por
  padrão (`EMAILS_GRUPO_GESTAO` em `server/generator/spec_builder.py`) — não há uma lista real
  configurada nesta entrega. Preencher essa constante antes de gerar o manual completo em
  produção, se a contra-capa precisar dos e-mails.
- **Organograma no manual completo é uma extensão desta migração**, não faz parte do template
  original da skill (que explicitamente não gera organograma). O slide é desenhado com formas
  simples do `python-pptx` (retângulos + linhas), suficiente para mostrar a hierarquia completa,
  mas sem o refinamento visual de um organograma desenhado à mão.

## Estrutura

```
public/index.html      Index.html original, só com a ponte run()->fetch("/api/rpc") trocada
server/main.py          FastAPI: POST /api/rpc, GET /api/health, serve /public
server/db.py            SQLAlchemy engine/session, transação
server/models.py        9 tabelas originais + TentativasLogin + Configuracao (infra)
server/auth.py          hash de senha, login, sessão (token HMAC), primeiro acesso
server/modelo.py        carregar_/modelo_/retrato_: regras de acesso por perfil
server/handlers_admin.py  cargos, entrevistas, usuários, solicitações, organograma
server/handlers_tobe.py   bloco TO BE inteiro
server/formalizacao.py    motor de redação de texto (ajustaFuncao, formalizarJornada, ...)
server/leitor.py          lerTexto: leitor de entrevista a partir de texto colado
server/seed.py             cria as tabelas e o código do primeiro administrador
server/generator/spec_builder.py    converte cargos do banco no schema da skill (Fase 2)
server/generator/slide_engine.py    port do build_manual.py para io.BytesIO (Fase 2)
server/generator/organograma_slide.py  slide de organograma com python-pptx (Fase 2)
server/handlers_export.py  GET /api/export/cargo/{id}, GET /api/export/manual-completo (Fase 2)
assets/T2.pptx, assets/selo-circular-preto.png  template e artefatos oficiais (Fase 2)
tests/                     pytest (65 testes)
docs/CONTRATOS.md          contrato da Fase 1 (fonte de verdade dos detalhes)
docs/CONTRATOS_FASE2.md    contrato da Fase 2 (exportação .pptx, mapeamento de schema)
docs/DEPLOY_SUPABASE.md    guia de deploy com banco Postgres gerenciado (Fase 2)
```
