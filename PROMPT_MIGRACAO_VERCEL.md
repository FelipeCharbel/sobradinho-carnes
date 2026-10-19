Você é o **COORDENADOR (Opus 5.5)** da migração da plataforma "Gestão Sobradinho Carnes" do Google Apps Script para uma stack própria (FastAPI + banco SQL + frontend estático), pronta para deploy na Vercel. Você NÃO escreve a maior parte do código: você planeja, delega a **2 subagentes Haiku 5.5 (Agente A e Agente B)** em paralelo, revisa, integra e testa.

# 0. LEITURA OBRIGATÓRIA ANTES DE QUALQUER COISA
1. `MEMORIA_COMPARTILHADA.md` e `CLAUDE.md` (protocolo de sincronização com o Gemini).
2. `raw_source/Codigo.gs` (backend original, ~168 KB) e `raw_source/Index.html` (SPA original, ~389 KB, 2.990 linhas).
   - Ignore `raw_source/Index_compiled.html` e `raw_source/Index.html.bak_*` (referências antigas).

# 1. OBJETIVO E REGRAS DE OURO
- **Paridade 100%**: o site hospedado fora do Apps Script deve ter exatamente a mesma aparência e o mesmo comportamento. Fase 1 = SÓ migração. Nada da skill `manual-cargos-funcoes` entra agora (isso é a Fase 2).
- **Não reescreva o frontend.** Toda comunicação passa por UMA função em `Index.html` (~linha 206452 do arquivo bruto, bloco `const Remote = (() => { ... const run = (fn, ...a) => new Promise(... google.script.run ...) })`). Basta trocar esse `run` por um `fetch("/api/rpc")`. O formato de resposta é `{dado: ...}` ou `{erro: "mensagem"}` (veja `resp_` e `mudar_` no Codigo.gs: as alterações devolvem `{r, snap}`).
- **Não invente regra de negócio.** Cada função `api_*` e `*_` do Codigo.gs deve ser portada fielmente. O que não puder ser portado (ver seção 5) vira stub explícito e documentado.
- Nada de segredos no repositório. Responder em português do Brasil.

# 2. ESTRUTURA ALVO (dentro de `./sobradinho-carnes/`)
```
public/index.html            # Index.html adaptado (só a ponte run/fetch muda)
server/main.py               # FastAPI: POST /api/rpc, serve /public, GET /api/health
server/db.py                 # SQLAlchemy; DATABASE_URL (SQLite local por padrão, Postgres em produção)
server/models.py             # 9 tabelas = ABAS do Codigo.gs (colunas idênticas e mesma ordem)
server/auth.py               # hash de senha, tokens de sessão, bloqueio de tentativas
server/modelo.py             # carregar_(), modelo_(), retrato_() (regras de acesso por perfil)
server/handlers_admin.py     # api_* de cargos, entrevistas, usuários, solicitações, organograma
server/handlers_tobe.py      # api_tobe*, sincronizarTobe_, tobeSalvar_, tobePublicar_, etc.
server/formalizacao.py       # port do motor de texto (ajustaFuncao, ajustaRotina, formalizarMissao, jornada, recorre...)
server/leitor.py             # port de lerTexto() (leitor de entrevista a partir de texto)
server/seed.py               # equivalente a configurar()/novoCodigoAdmin()
tests/                       # pytest: paridade das funções de texto + fluxo de login/snapshot
requirements.txt  vercel.json  README.md  .env.example  .gitignore
```

# 3. CONTRATOS QUE VOCÊ (COORDENADOR) DEVE FECHAR **ANTES** DE DELEGAR
Escreva em `docs/CONTRATOS.md` e só então dispare os agentes:
- **Contrato RPC**: `POST /api/rpc` body `{"fn": "api_xxx", "args": [...]}` → `{"dado": ...}` | `{"erro": "..."}`. Lista completa das `api_*` (copie as ~35 assinaturas do Codigo.gs, linhas "funções chamadas pela tela").
- **Assinaturas Python** de cada módulo (nomes, parâmetros, retornos) para A e B não colidirem.
- **Schema das 9 tabelas** (ABAS do Codigo.gs). Campos JSON do original (funcoes, rotinas, habilidades, relacoes, ferramentas, historico, respostas, auto, base, personalizado, conflito, snapshot) ficam como TEXT contendo JSON, igual à planilha.
- **Sessão**: no Apps Script era `CacheService` (30 min). Na Vercel não há memória compartilhada: use **token assinado (HMAC) stateless** com expiração de 1800 s renovada a cada uso, contendo o e-mail; revalide o usuário no banco a cada chamada (erro `"SESSAO"` se inválido, como no original).
- **Hash de senha**: compatível com `hashSenha_` (SHA-256 em base64, 600 voltas, `h = salt+":"+senha`, depois `h = b64(sha256(h+salt))` repetido) para que usuários migrados da planilha continuem entrando.
- **Concurrency**: o `LockService` vira transação do banco.

# 4. DIVISÃO DE TAREFAS

## COORDENADOR (Opus 5.5)
1. Ler as fontes, escrever `docs/CONTRATOS.md` e as stubs vazias de cada arquivo com docstrings das assinaturas.
2. Disparar Agente A e Agente B **em paralelo**, cada um com a sua lista abaixo e o contrato.
3. Revisar o código entregue linha a linha contra o Codigo.gs (principalmente `modelo_`/`retrato_`: o que cada perfil NÃO pode ver, como `admin`/`socio`/`gestor`/`colaborador`).
4. Integrar `main.py`, rodar os testes, subir o servidor e validar no navegador (login, snapshot, organograma, abrir cargo, TO BE).
5. Escrever `README.md` (rodar local + deploy Vercel) e atualizar `MEMORIA_COMPARTILHADA.md` (checkpoint + histórico).

## AGENTE A (Haiku 5.5) — BACKEND DE DADOS E REGRAS
Arquivos: `db.py`, `models.py`, `auth.py`, `modelo.py`, `handlers_admin.py`, `handlers_tobe.py`, `seed.py`, `main.py`.
- Criar as 9 tabelas e o `seed.py` (cria o primeiro admin com código de uso único, como `novoCodigoAdmin`; imprime o código no terminal).
- Portar: `login_`, `primeiroAcesso_`, `sessao_`, `trocarSenha_`, `redefinirSenha_`, `carregar_`, `modelo_`, `retrato_`, `salvarEntrevista_`, `publicar_`, `salvarUsuario_`, `respostas_`, solicitações e correção de cargo (`pedirCorrecaoCargo_`, `resolverCorrecaoCargo_`), `importarCargos_`, `salvarCargo_`, `salvarCargos_`, `salvarOrganograma_`, `salvarPosicoes_`, `definirSuperior_`, `excluirCargo_`, `visualizarComo_`.
- Portar todo o bloco TO BE (`iniciarTobe_`, `sincronizarTobe_`, `tobeVisao_`, `tobeSalvar_`, `tobeJustificar_`, `tobeResolver_`, `tobePublicar_`, `corrigePais_`, `comSync_`).
- `main.py`: despachar `fn` por dicionário, aplicar `resp_`/`mudar_` (alterações devolvem `{r, snap}`), traduzir exceções em `{erro}`.
- Testes: login com senha errada (bloqueio após 5 tentativas), perfil colaborador não vê entrevistas, ciclo de organograma rejeitado.

## AGENTE B (Haiku 5.5) — MOTOR DE TEXTO, FRONTEND E INFRA
Arquivos: `formalizacao.py`, `leitor.py`, `public/index.html`, `vercel.json`, `requirements.txt`, `.env.example`, `.gitignore`, `tests/test_formalizacao.py`.
- Portar para Python, de forma **literal**, todo o motor de redação: `PARES`, `ajustaFuncao/ajustaRotina`, `nucleoInf`, `narrativaInf`, `violacoesEstilo`, `mensagemEstilo`, `formalizar`, `formalizarMissao/missaoFormal`, `formalizarJornada` (+ `jornadaPartes/Calc/Fecha/Monta`), `recorreItens/recorreNormaliza`, `capitalizaNomes2/defineNomes` e `lerTexto` (leitor). As regex JS (lookbehind, `\p{L}`, flag `u`) devem ser convertidas para o módulo `regex` do Python se necessário.
- Testes de paridade: ao menos 40 casos entrada→saída extraídos dos comentários/exemplos do Codigo.gs (ex.: "Conferência do ponto" → "Conferir o ponto"; "Dias úteis de 8 as 17h" → jornada completa).
- `public/index.html`: copiar `raw_source/Index.html` e trocar SOMENTE o `run` por `fetch("/api/rpc", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({fn, args:a})})`, guardando o token que o servidor devolve em `api_login`. Remover qualquer referência a `google.script`.
- `vercel.json` (FastAPI serverless em `server/main.py` + estáticos de `public/`), `requirements.txt` (fastapi, uvicorn, sqlalchemy, psycopg[binary], pydantic, regex, python-pptx, pillow, lxml, pytest, httpx), `.env.example` (`DATABASE_URL`, `SECRET_KEY`).

# 5. O QUE NÃO PODE SER PORTADO (stubs documentados)
- `lerDoc_` e `novaEntrevista_` (DocumentApp/Drive): retornar erro claro "Disponível só pelo texto colado nesta versão". O leitor continua funcionando via `texto`. Registre como pendência da Fase 2.
- Leitura de formatação (cor/negrito) das notas 20–27: só funcionava com Docs; no texto colado, aceitar o formato `***( 4 )***`.

# 6. CRITÉRIOS DE ACEITE (você só encerra quando TODOS passarem)
1. `pytest` verde.
2. `uvicorn server.main:app --port 8000` sobe; `/` abre a tela de login idêntica ao original.
3. Fluxo ponta a ponta no navegador: primeiro acesso como admin (código do seed) → login → criar cargo → ligar no organograma → salvar entrevista (texto colado) → publicar → entrar como colaborador e confirmar que ele NÃO vê rascunhos/entrevistas.
4. Nenhum `google.script` restante em `public/`.
5. README com passos de deploy na Vercel (Postgres via `DATABASE_URL`) e aviso de que SQLite em arquivo não persiste na Vercel.
6. `MEMORIA_COMPARTILHADA.md` atualizado (checkpoint + 1 linha no histórico).

Comece pela seção 0 e confirme em 5 linhas o plano antes de disparar os agentes.
