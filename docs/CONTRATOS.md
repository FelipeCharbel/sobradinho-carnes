CONTRATOS — Migração "Gestão Sobradinho Carnes" (Apps Script → FastAPI)
========================================================================

Este documento é a fonte única de verdade para a Fase 1 da migração. Agente A e Agente B devem
seguir exatamente o que está aqui. Qualquer dúvida de nomenclatura, tipo ou comportamento resolve-se
olhando `raw_source/Codigo.gs` (a linha é citada abaixo) — nunca inventando.

**Convenção de nomes (importante):** as funções internas portadas mantêm o **nome exatamente igual**
ao do `Codigo.gs`, inclusive o `_` final (`login_`, `carregar_`, `modelo_`, `retrato_`,
`salvarEntrevista_`, `tobeSalvar_`...). Isso não é idiomático em Python, mas é deliberado: o
Coordenador revisa o código entregue linha a linha contra o `.gs`, e nomes idênticos tornam o diff
trivial. Só as funções `api_*` (camadas HTTP) e os módulos/arquivos usam nomes "normais" de Python.

---

## 1. Contrato RPC

```
POST /api/rpc
Content-Type: application/json
{ "fn": "api_login", "args": [email, senha] }

200 OK
{ "dado": ... }          // sucesso
  — ou —
{ "erro": "mensagem" }   // erro de negócio (sempre HTTP 200; o erro vem no corpo, igual ao Apps Script)
```

- `fn` é o nome exato de uma função `api_*` (tabela abaixo). Qualquer outro nome → `{"erro": "Função desconhecida."}`.
- `args` é um array posicional, na mesma ordem dos parâmetros da função `api_*` no `.gs`. O primeiro
  argumento de toda função que recebe `token` é sempre `token` (igual ao `.gs`); o frontend já manda
  assim (ver `Index.html`, `const api = (fn, ...args) => BE[fn](TOKEN, ...args)`).
- Erros inesperados (exceção não tratada) também devem virar `{"erro": "..."}` com a mensagem da
  exceção — nunca um HTTP 500 com stack trace. `GET /api/health` devolve `{"ok": true}` simples.
- **Toda alteração (mutação) devolve `{"r": ..., "snap": <retrato novo>}`** dentro do `dado`, exceto
  a única excepção documentada abaixo (`api_trocarSenha`). O retrato (`snap`) é recalculado para a
  mesma sessão que fez a chamada — isso poupa uma ida ao servidor no frontend (ver `mudar_` no `.gs`,
  linha 82).

### 1.1 Wrappers `resp_` / `mudar_` / `comSync_` (Python, em `main.py`)

Portar fielmente os três combinadores do `.gs` (linhas 79, 82, 793):

```python
def resp_(fn):
    """Equivalente a resp_ do .gs (linha 79): roda fn(), devolve {"dado": ...} ou {"erro": str(e)}."""

def mudar_(token, fn, db):
    """Equivalente a mudar_ (linha 82): roda fn() dentro de uma transação (ver §6), devolve
    {"dado": {"r": resultado, "snap": retrato_(carregar_(db), sessao_(token, db))}}."""

def com_sync_(token, fn, db):
    """Equivalente a comSync_ (linha 793): roda fn(); se o TO BE já foi iniciado
    (tobe_iniciado_(db)), chama sincronizarTobe_(sessao_(token, db).nome, db) depois. Usado dentro das
    ações do AS IS que podem repercutir no TO BE (ver coluna 'comSync' na tabela 1.2)."""
```

### 1.2 Lista completa das `api_*` (31 funções — `.gs` linhas 84-118)

Legenda da coluna **wrapper**: `resp` = só `resp_` (sem snapshot novo); `mudar` = `mudar_` (devolve
`{r, snap}`); `mudar+sync` = `mudar_` envolvendo `comSync_` (AS IS que repercute no TO BE).
**Módulo** indica onde a função `api_*` e a função interna (`_`) devem morar.

| # | `api_*` (args) | wrapper | função interna chamada | retorno de `r` (quando mudar) | módulo |
|---|---|---|---|---|---|
| 1 | `api_login(email, senha)` | resp | `login_` | — | handlers_admin.py |
| 2 | `api_primeiroAcesso(d)` | resp | `primeiroAcesso_` | — | handlers_admin.py |
| 3 | `api_cargosPublicos()` | resp | `ler_("Cargos")` + sort | — | handlers_admin.py |
| 4 | `api_logout(token)` | resp | invalida sessão | — | auth.py |
| 5 | `api_snapshot(token)` | resp | `sessao_` + `retrato_` | — | handlers_admin.py |
| 6 | `api_lerEntrevista(token, entrada)` | resp | `lerEntrevista_` | — | handlers_admin.py (chama `leitor.lerTexto`) |
| 7 | `api_respostas(token, cargoId)` | resp | `respostas_` | — | handlers_admin.py |
| 8 | `api_salvarEntrevista(token, d)` | mudar+sync | `salvarEntrevista_` | `{id}` | handlers_admin.py |
| 9 | `api_novaEntrevista(token, d)` | mudar | **STUB** (§5) | erro fixo | handlers_admin.py |
| 10 | `api_publicar(token, id, ligar)` | mudar | `publicar_` | `true` | handlers_admin.py |
| 11 | `api_salvarCargo(token, d)` | mudar+sync | `salvarCargo_` | `{id}` | handlers_admin.py |
| 12 | `api_excluirCargo(token, id)` | mudar+sync | `excluirCargo_` | `true` | handlers_admin.py |
| 13 | `api_salvarUsuario(token, email, dados)` | mudar | `salvarUsuario_` | `true` | handlers_admin.py |
| 14 | `api_salvarPosicoes(token, d)` | mudar+sync | `salvarPosicoes_` | `{n}` | handlers_admin.py |
| 15 | `api_definirSuperior(token, id, pai)` | mudar+sync | `definirSuperior_` | `true` | handlers_admin.py |
| 16 | `api_salvarCargos(token, lista)` | mudar+sync | `salvarCargos_` | `{n}` | handlers_admin.py |
| 17 | `api_salvarOrganograma(token, d)` | mudar+sync | `salvarOrganograma_` | `{n, ligacoes}` | handlers_admin.py |
| 18 | `api_trocarSenha(token, atual, nova)` | **resp** (ver nota) | `trocarSenha_` | — | auth.py |
| 19 | `api_redefinirSenha(token, email)` | mudar | `redefinirSenha_` | `{provisoria, nome}` | auth.py |
| 20 | `api_importarCargos(token, linhas)` | mudar+sync | `importarCargos_` | `{n}` | handlers_admin.py |
| 21 | `api_solicitar(token, d)` | mudar | `solicitar_` | `{id}` | handlers_admin.py |
| 22 | `api_resolverSolicitacao(token, id, status, resposta)` | mudar | `resolverSolicitacao_` | `true` | handlers_admin.py |
| 23 | `api_pedirCorrecaoCargo(token, d)` | mudar | `pedirCorrecaoCargo_` | `{id}` | handlers_admin.py |
| 24 | `api_meusPedidos(token)` | resp | `meusPedidosDe_` | — | handlers_admin.py |
| 25 | `api_resolverCorrecaoCargo(token, id, decisao, resposta, cargoId)` | mudar | `resolverCorrecaoCargo_` | `true` | handlers_admin.py |
| 26 | `api_tobe(token)` | resp | `tobeVisao_` (inicia TO BE na 1ª vez) | — | handlers_tobe.py |
| 27 | `api_tobeSalvar(token, d)` | mudar | `tobeSalvar_` | `{n, lote}` | handlers_tobe.py |
| 28 | `api_tobeJustificar(token, ref, texto)` | mudar | `tobeJustificar_` | `{n}` | handlers_tobe.py |
| 29 | `api_tobeResolverConflito(token, cargoId, campo, decisao, justificativa)` | mudar | `tobeResolver_` | `true` | handlers_tobe.py |
| 30 | `api_tobeSincronizar(token)` | mudar | `sincronizarTobe_` | `{criados, atualizados, conflitos, removidos}` | handlers_tobe.py |
| 31 | `api_tobePublicar(token, d)` | mudar | `tobePublicar_` | `{versao}` | handlers_tobe.py |
| 32 | `api_visualizarComo(token, d)` | resp | `visualizarComo_` (exige admin) | — | handlers_tobe.py |

**Nota crítica (#18):** `api_trocarSenha` **não** usa `mudar_` no original (`.gs` linha 101):
`resp_(() => escrever_(() => trocarSenha_(token, atual, nova)))`. Ou seja, devolve `{"dado": true}`,
**sem** `snap`. O frontend (`Index.html` linha 1309) também não usa `mut()` para essa chamada. Replicar
exatamente — não "corrigir" para o padrão das outras.

**`api_tobe`** (#26) inicia o TO BE na primeira abertura (`if (!tobeIniciado_()) ... iniciarTobe_(u)`),
mas dentro de uma transação, e **não** devolve `snap` (é `resp_`, não `mudar_`) — o TO BE não aparece
no retrato do AS IS.

---

## 2. Schema das 9 tabelas (`ABAS` do `.gs`, linhas 11-21)

Todas as colunas marcadas **JSON-TEXT** guardam `json.dumps(...)` em uma coluna `Text`/`String`,
exatamente como a planilha guarda `JSON.stringify(...)` numa célula de texto — **não** usar tipo JSON
nativo do Postgres nem `ARRAY`: a paridade de serialização (incluindo `"[]"` vs `null` vs `""`) importa
para os testes de `carregar_`.

### Cargos (chave: `id`, string)
| coluna | tipo | observação |
|---|---|---|
| id | String, PK | `slug-xxxx` (ver `novoIdCargo_`) |
| nome, area, pessoa | String | |
| pai | String, nullable | id de outro Cargo ou `""`/`None` |
| missao | Text | |
| funcoes | Text (JSON-TEXT, lista de string) | |
| rotinas | Text (JSON-TEXT, lista de `{f, t}`) | |
| jornada | Text | |
| tempoEmpresa, formacao, experiencia, recorre | String | |
| habilidades, relacoes, ferramentas | Text (JSON-TEXT, lista de string) | |
| status | String | `""` (sem conteúdo) \| `"revisao"` \| `"publicado"` |
| entrevistaId | Integer, nullable | FK lógica para Entrevistas.id |
| revisao | Integer, default 0 | |
| historico | Text (JSON-TEXT, lista de `{rev, data, por, motivo}`, até 30 itens) | |
| x, y | Integer, nullable | posição no organograma |

### Entrevistas (chave: `id`, inteiro)
`id` (Integer, PK, igual a `proximoIdEntrevista_` = max+1), `cargoId` (String), `pessoa` (String),
`data` (String — a planilha guarda como texto livre, não Date), `link` (String), `auto` (Text,
JSON-TEXT lista de 8 números/null ou `""`), `registradoPor` (String), `registradoEm` (DateTime),
`respostas` (Text, JSON-TEXT lista de `{n,p,r}`, até ~49000 chars — pode ser `""`).

### Usuarios (chave: `email`, string, PK)
`email` (String, PK, lower), `nome` (String), `perfil` (String: `admin|socio|gestor|colaborador`),
`cargoId` (String, nullable), `cargoInformado` (String), `cargoSolicitado` (String, nullable),
`status` (String: `Ativo|Pendente|Inativo`), `salt` (String), `hash` (String), `criadoEm` (DateTime),
`ultimoAcesso` (DateTime, nullable), `trocarSenha` (String/Integer — `""` ou `1`).

### Propostas (chave: `id`) — **sem uso** desde o TO BE (comentário do `.gs` linha 15)
Criar a tabela por paridade de schema, mas nenhum handler grava/lê nela na Fase 1: `id, tipo, cargoId,
nome, area, pai, de, para, motivo, fonte` (todas String).

### Solicitacoes (chave: `id`, string)
`id` (String, PK — prefixo `S` ou `C` conforme origem), `cargoId`, `origemId`, `texto`, `motivo`,
`status` (`Aberta|Concluída|Recusada|Aprovada`), `criadoPor`, `criadoPorEmail`, `criadoEm` (DateTime),
`resolvidoPor`, `resolvidoEm` (DateTime, nullable), `resposta`, `tipo` (String, vazio ou
`"correcao-cargo"` — ver `TIPO_CORRECAO_`), `cargoSugerido` (String, nullable).

### Registro (sem chave própria — append-only, como a aba da planilha)
`quando` (DateTime), `quem` (String), `acao` (String, até 300 chars). Usar `id` Integer autoincrement
como PK técnica (a planilha não tem id; a ordem é a de inserção).

### Tobe (chave: `id`, string)
Mesmas colunas de conteúdo que Cargos (`nome, area, pai, pessoa, missao, funcoes, rotinas, jornada,
tempoEmpresa, formacao, experiencia, habilidades, relacoes, recorre, ferramentas, x, y`) **mais**:
`origem` (String: `asis|tobe`), `base` (Text, JSON-TEXT objeto — snapshot do AS IS no momento),
`personalizado` (Text, JSON-TEXT lista de nomes de campo), `conflito` (Text, JSON-TEXT lista de
`{campo, asis, tobe, em}`), `removido` (Boolean/Integer 0-1).

### TobeHistorico (chave: `id`, string, prefixo `H`)
`id, quando (DateTime), quem, origem (sync|manual|ajuste|publicacao), cargoId, cargoNome, campo,
antes (Text), depois (Text), descricao, justificativa, status (Automática|Pendente de
justificativa|Justificada), justificadoEm (DateTime, nullable), justificadoPor, lote (String)`.

### TobeVersoes (chave: `versao`, inteiro)
`versao` (Integer, PK), `publicadoEm` (DateTime), `por` (String), `nota` (String),
`snapshot` (Text, JSON-TEXT — string de `fotoTobe_`, usada só para comparar igualdade, não para exibir).

---

## 3. Sessão (substitui `CacheService`)

O `.gs` usa `CacheService.getScriptCache()` com chave `"s:" + token` → email, TTL `SESSAO_SEGUNDOS`
(1800s), renovado a cada `sessao_(token)` (linha 280). Na Vercel (serverless, sem memória
compartilhada) isso vira um **token assinado stateless (HMAC-SHA256)**:

```python
# server/auth.py
def criar_token(email: str, secret: str) -> str:
    """payload = {"email": email, "exp": time.time() + 1800}; token = base64(payload) + "." +
    HMAC-SHA256(base64(payload), secret). Formato: "<payload_b64>.<assinatura_b64>"."""

def sessao_(token: str, db, secret: str) -> dict:
    """Equivalente a sessao_ do .gs (linha 275):
    1. Verifica assinatura e validade (exp não passado); se falhar, raise ErroNegocio("SESSAO").
    2. Busca o usuário pelo email do payload; se não existir ou status != "Ativo", raise("SESSAO").
    3. 'Renova a cada uso': gera e retorna um NOVO token (próxima resposta HTTP deve incluir o
       token renovado para o frontend trocar o que guarda — ver nota abaixo).
    4. Devolve {"email", "nome", "perfil", "cargo", "status"} igual ao .gs.
    """
```

**Nota de integração com o frontend (Agente B):** o `.gs` original renova a sessão dentro do próprio
`CacheService` (o token do cliente nunca muda). Como aqui o token é stateless, cada resposta de
`main.py` deve devolver também o token renovado (campo extra, ex. `"token"` dentro de `dado`, **sem
quebrar o contrato `{dado}/{erro}`**: pode ir como `dado.token` quando o payload original for um
objeto — e quando `dado` for primitivo/array, o token renovado vai num header `X-Session-Token`). O
Agente B deve ajustar a ponte `run()` em `Index.html` para ler esse token renovado (de
`dado.token` se existir, senão do header) e atualizar o que guarda, sem mudar mais nada da tela.
Documentar a escolha final no próprio código com um comentário curto.

`MAX_TENTATIVAS` (5) e o bloqueio de 15 min (900s) de `login_` (linha 262) também precisam de um
contador persistente — como não há `CacheService`, usar uma tabela simples (`tentativas_login`:
email, contador, bloqueado_até) ou reaproveitar `Usuarios` com colunas extras não-schema (decisão do
Agente A; documentar no código).

---

## 4. Hash de senha (compatibilidade com a planilha existente)

Replicar `hashSenha_` **byte a byte** (`.gs` linha 220):

```python
import hashlib, base64

def hash_senha_(senha: str, salt: str) -> str:
    """
    h = salt + ":" + senha
    repetir 600 vezes (VOLTAS_HASH):
        h = base64.b64encode(hashlib.sha256((h + salt).encode("utf-8")).digest()).decode()
    devolver h
    """
```

Comparação em tempo constante (`igual_`, linha 225): usar `hmac.compare_digest`, nunca `==`.

---

## 5. O que NÃO pode ser portado (stubs obrigatórios)

- **`novaEntrevista_`** (`.gs` linha 542): cria um Google Doc a partir de `TEMPLATE_ENTREVISTA` via
  `DocumentApp`/`DriveApp`. `api_novaEntrevista` deve existir no dispatcher, mas levantar erro de
  negócio fixo: `"Disponível só pelo texto colado nesta versão."` (sem tentar nada de Drive). Comentar
  no código: `# Fase 2: recriar via Google Docs API ou geração de .docx local`.
- **`lerDoc_`** (`.gs` linha 396) e toda a leitura de formatação das notas 20-27 por cor/negrito do
  Google Docs (`.gs` linhas 419-473, `ATRIBUTOS_`, `atribDe_`, `textoComMarca_`, `linhasDeOpcoes_`,
  `linhaDeTabela_`): **não portar**. `api_lerEntrevista` só aceita `entrada.texto` (texto colado); se
  vier só `entrada.link` sem texto suficiente, devolver o mesmo erro do original ("Cole o link do
  Google Docs da entrevista ou o texto dela.") — mas sem tentar abrir o link. O formato
  `***( 4 )***` (nota marcada) já funciona igual no texto colado, porque `lerTexto` (linha 1238-1244)
  lê esse padrão direto da string, sem precisar do Docs. **Nada muda em `lerTexto` por causa disso.**

---

## 6. Concorrência (`LockService` → transação)

`escrever_(fn)` no `.gs` (linha 198) pega um lock global de 20s, roda `fn()`, libera. Em Python/SQL:
toda função que grava (`gravar_`, `anexaAba_`, `gravarTobe_`, etc.) deve rodar dentro de uma única
transação SQLAlchemy (`with db.begin(): ...` ou `session.commit()` ao final, `rollback()` em exceção).
Como é um banco único (SQLite local / Postgres em produção) e não múltiplos processos Apps Script,
uma transação por chamada de `mudar_`/`escrever_` já garante a mesma serialização que o `LockService`
dava. Não é necessário lock explícito adicional — documentar essa equivalência num comentário em
`db.py`.

---

## 7. Fronteira exata entre Agente A e Agente B

- **`validarConteudo(d)`** (`.gs` linha 1273) mora em `handlers_admin.py` (Agente A) — é validação de
  entrada específica de `salvarEntrevista_`, não faz parte do motor de texto. Mas **importa** de
  `formalizacao.py` (Agente B): a constante `FREQS` (lista de frequências válidas) e as funções
  `violacoesEstilo`, `mensagemEstilo`. Agente B deve expor essas três coisas em `formalizacao.py`
  exatamente com esses nomes.
- **`lerTexto`** (`.gs` linha 1179, em `leitor.py`, Agente B) usa no original uma lista global mutável
  `CARGOS` (preenchida por `carregar_` antes de cada chamada) para sugerir o cargo da entrevista
  (`casar`, linha 1165). **Adaptação deliberada para Python:** a assinatura vira
  `lerTexto(texto: str, cargos: list[dict]) -> dict`, recebendo a lista de cargos como parâmetro
  explícito (sem global mutável). `handlers_admin.lerEntrevista_` (Agente A) chama
  `leitor.lerTexto(texto, cargos=D["cargos"])` depois de `carregar_()`. O comportamento de matching
  (`casar`, `porPessoa`) fica idêntico — só a forma de passar os cargos muda.
- **`modelo_(D)` e `retrato_(D, u)`** (`.gs` linhas 286 e 341, em `modelo.py`, Agente A) são o coração
  das regras de acesso. Portar **função por função** dentro do dict retornado (`byId, scope,
  estadoReal, estadoPublico, estadoVisto, mostra, codigoDe, posicaoDe, ficha, diagnostico,
  diagnosticoAgregado`) exatamente como no `.gs` — não resumir a lógica. Casos que o Coordenador vai
  conferir linha a linha na revisão:
  - `scope(u)`: admin/socio veem tudo; gestor vê o próprio cargo + descendentes; colaborador vê só
    cargos da mesma área **e mesmo nível** que o seu.
  - `mostra(c, u)`: só mostra conteúdo se `status === "publicado"` **ou** `u.perfil === "admin"`.
  - `manual_`: quem não é admin nunca recebe `entrevistaId` nem `historico` dentro do conteúdo.
  - `ficha`: quem está fora do `scope` recebe só `{..., estado: estadoPublico(c), conteudo: null,
    restrito: true}` — nunca o nome real do estado interno (`revisao`/`sem`) nem qualquer conteúdo.
  - `ficha` para admin inclui `dataEntrevista` e `entrevista` (a entrevista inteira, exceto
    `respostas`, que só vem por `api_respostas` sob pedido) — mais ninguém recebe essas duas chaves.
  - `retrato_`: `entrevistas`, `perfis`, `usuarios`, `registro`, `diag` (completo) e `pedidosCargo`
    só existem no retrato quando `admin`. `diag` (agregado, `diagnosticoAgregado`) só existe quando
    `socio`. Gestor e colaborador não recebem a chave `diag` de forma alguma.
  - `diagnosticoAgregado`: nunca identifica pessoa, entrevista, link ou cargo; abaixo de `MIN=3`
    respostas não mostra média nem contagem (`poucos: true`).

---

## 8. Assinaturas Python por módulo (resumo para não colidir)

```python
# server/db.py (Agente A)
def get_session() -> Session: ...
def init_db() -> None: ...  # cria as 9 tabelas

# server/models.py (Agente A) — 9 classes SQLAlchemy: Cargo, Entrevista, Usuario, Proposta,
# Solicitacao, Registro, Tobe, TobeHistorico, TobeVersao (nomes de classe em PT, singular, livre;
# nomes de TABELA devem ser os originais: "Cargos", "Entrevistas", etc.)

# server/auth.py (Agente A)
def hash_senha_(senha, salt) -> str: ...
def igual_(a, b) -> bool: ...
def criar_token(email, secret) -> str: ...
def sessao_(token, db, secret) -> dict: ...
def login_(email, senha, db, secret) -> dict: ...
def primeiroAcesso_(d, db) -> dict: ...
def trocarSenha_(token, atual, nova, db, secret) -> bool: ...
def redefinirSenha_(token, email, db, secret) -> dict: ...
def soAdmin_(u, o) -> None: ...  # raise NEGADO se não for admin

# server/modelo.py (Agente A)
def carregar_(db) -> dict: ...           # {cargos, entrevistas, solicitacoes, usuarios}
def modelo_(D) -> dict: ...              # dict de funções (ver §7)
def retrato_(D, u) -> dict: ...

# server/handlers_admin.py (Agente A) — api_* + funções internas da tabela §1.2 (exceto TO BE)
# server/handlers_tobe.py (Agente A) — api_tobe* + sincronizarTobe_, tobeVisao_, etc.
# server/seed.py (Agente A)
def configurar(db) -> str: ...           # cria tabelas vazias se preciso + chama novoCodigoAdmin
def novoCodigoAdmin(db) -> str: ...      # gera e imprime o código de admin único

# server/main.py (Agente A) — FastAPI app, dispatcher fn->handler, POST /api/rpc, GET /api/health,
# StaticFiles em /public

# server/formalizacao.py (Agente B) — PARES, FREQS, ajustaFuncao, ajustaRotina, nucleoInf,
# narrativaInf, violacoesEstilo, mensagemEstilo, formalizar, formalizarMissao, missaoFormal,
# formalizarJornada (+ jornadaPartes/Calc/Fecha/Monta), recorreItens, recorreNormaliza,
# capitalizaNomes2, defineNomes (mesmos nomes do .gs)

# server/leitor.py (Agente B)
def lerTexto(texto: str, cargos: list[dict]) -> dict: ...  # ver adaptação em §7
```

---

## 9. Critérios de aceite — recapitulação rápida

Ver seção 6 do prompt original (`PROMPT_MIGRACAO_VERCEL.md`). Resumo operacional: `pytest` verde,
`uvicorn server.main:app` sobe, fluxo ponta a ponta no navegador, zero `google.script` em `public/`,
README com deploy Vercel + aviso SQLite, `MEMORIA_COMPARTILHADA.md` atualizado.
