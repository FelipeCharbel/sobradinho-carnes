# Memória Compartilhada — Claude Code & Gemini 4 Argon

Este arquivo é o ponto único de contexto compartilhado entre o **Claude Code** e o **Gemini 4 Argon** (rodando no Google Antigravity), ambos operando neste mesmo diretório: `Projetos Gemini - Claude`.

Regra geral: **todo modelo lê este arquivo antes de iniciar uma tarefa e atualiza este arquivo depois de concluí-la.** Isso evita que um modelo sobrescreva ou ignore o trabalho do outro.

---

## Contexto do Projeto

- **Projeto Atual:** `sobradinho-carnes` (Subpasta: `./sobradinho-carnes/`)
- **Objetivo:** Projeto central da Sobradinho Carnes para integração e junção de componentes/materiais.

## Arquitetura

- **Diretório do projeto:** `./sobradinho-carnes/`
- Estrutura a ser definida de acordo com os módulos e recursos que o usuário deseja integrar.

## Checkpoint em Tempo Real (Última Interação)

- **Último modelo ativo:** Claude Code / Opus (2026-10-19)
- **Assunto em discussão / execução:** Executado `PROMPT_OPUS_REVISAO.md` (usuário: "ainda tem muita coisa errada, não sumiu"). Decisão anterior ainda vigente: Fase 1 = site idêntico do Apps Script migrado para FastAPI + banco SQL (SQLite local, Postgres em produção) + frontend estático na Vercel; Fase 2 = skill `manual-cargos-funcoes` plugada (`.pptx`). Prompts em `PROMPT_MIGRACAO_VERCEL.md` / `PROMPT_FASE2_SLIDES.md`.
- **Arquivos tocados agora:** `public/index.html`, `server/main.py`, `vercel.json`, `MEMORIA_COMPARTILHADA.md` (este e o da pasta pai).
- **Status:** Diagnóstico primeiro: o JS **já estava íntegro** — `node --check` limpo nos dois blocos de script, e um varredor confirmou que todos os `$("#id")`/`on("#id")` executados no carregamento existem no HTML estático. Logo, o sintoma restante era **cache do navegador** servindo o `index.html` antigo e quebrado. Correções aplicadas: (1) middleware `sem_cache` em `server/main.py` — `Cache-Control: no-cache, no-store, must-revalidate, max-age=0` + `Pragma: no-cache` + `Expires: 0`, e **remoção de `ETag`/`Last-Modified`** (sem isso o `StaticFiles` responderia 304 e o navegador reusaria o corpo antigo); rotas `/api/export/` ficam de fora para não atrapalhar os downloads `.pptx`. (2) Bloco `headers` em `vercel.json`, porque na Vercel o `/public` é servido pela CDN e **não** passa pelo middleware. (3) `mostra()` do `<head>` agora imprime `arquivo:linha:coluna` + `e.error.stack` (e o `reason.stack` em promessas). (4) Stubs `window.loginTab/openSenha/tema` no `<head>`: os botões do login existem no HTML antes do script do fim do `body` rodar, então um clique precoce virava `ReferenceError` na tarja vermelha; os stubs absorvem o clique e são substituídos pelas funções reais. Mais `window.loginTab = loginTab` explícito. (5) `BE.demos()` blindado em `const DEMOS` (sempre array, com try/catch). (6) Helper `on(sel, ev, fn)` aplicado aos 11 listeners de inicialização (`demoRow`, `loginForm`, `cgTrocar`, `cgDuvida`, `paCodigo`, `cgLista`, `cgBusca`×2, `paForm`, `logoutBtn`, `menuBtn`) + null-checks em `loginTab`, `cgRender`, `closeMenu` e no `keydown` do Escape — um id ausente não derruba mais a inicialização inteira. (7) `const BE = REMOTO ? Remote : Server` → `const BE = Remote`: `Server` não existe em nenhum lugar do arquivo e viraria `ReferenceError` se `REMOTO` fosse `false`. Validação: `node --check` → 0 erros nos dois scripts; `pytest` → 65/65; HTTP real contra uvicorn → `/` e `/index.html` 200 com os três headers anti-cache e **sem ETag**, `If-None-Match` falso devolve 200 (não 304), `/api/rpc api_cargosPublicos` → `{"dado":[]}`, `/api/export/` → 403 sem header anti-cache (exclusão funcionando), e o HTML servido contém as correções novas e não contém mais o trecho antigo.
- **Próxima ação esperada:** O usuário precisa recarregar com **Ctrl+Shift+R** (ou abrir em aba anônima) **uma vez** para descartar o `index.html` já em cache; daí em diante os headers impedem reincidência. Se a tarja vermelha ainda aparecer, pedir o **texto exato** dela — agora traz arquivo, linha, coluna e stack. Depois: Fase 3 (`novaEntrevista_`/`lerDoc_`), `EMAILS_GRUPO_GESTAO` e deploy real Vercel+Supabase.

## Convenções de Trabalho entre os Modelos

- **Divisão de Papéis**:
  - **Gemini**: Absorção de contexto massivo, inteligência estratégica, arquitetura do projeto e formulação de prompts refinados/comandos para o Claude.
  - **Claude Code**: Executor principal de código, testes, arquivos e Git no terminal interativo.
- **Claude Code**: ver `CLAUDE.md`.
- **Gemini 4 Argon**: ver `GEMINI.md`.
- **Economia de Tokens**: Sempre editar este arquivo via substituição parcial (`Edit` / `replace_file_content`) apenas nas linhas necessárias. Manter a tabela de Histórico de Sessões com no máximo as 10 entregas mais recentes.
- Em caso de conflito ou dúvida sobre o que o outro modelo fez, registrar aqui e sinalizar explicitamente no log abaixo (não sobrescrever silenciosamente).

## Histórico de Sessões

> Formato de cada entrada: Data | Modelo | O que foi feito | O que falta / próximos passos

| Data | Modelo | Resumo da tarefa | Próximos passos |
|------|--------|-------------------|------------------|
| 2026-10-18 | Claude Code | Criação da estrutura inicial compartilhada: `CLAUDE.md`, `GEMINI.md` e este arquivo `MEMORIA_COMPARTILHADA.md`. | Aguardando definição do projeto a ser desenvolvido. |
| 2026-10-18 | Gemini 4 Argon + Claude Code | Teste de disparo automático via CLI (`claude -p`) validado com sucesso. | Pronto para iniciar projetos em conjunto. |
| 2026-10-19 | Gemini | Inicialização da estrutura do projeto `refinamento-site-sobradinho`. | Arquivado/pausado para novo escopo. |
| 2026-10-19 | Gemini | Inicialização do projeto `sobradinho-carnes` e abertura do Claude no terminal da pasta. | Alinhar o que será integrado e arquitetar estrutura. |
| 2026-10-19 | Claude Code | Recuperado `raw_source/Index.html` completo (389KB) a partir do campo `userHtml` embutido em `raw_source/Index_compiled.html`. | Confirmar se pode remover o backup `Index.html.bak_*`; retomar pendência das coletas de cargos. |
| 2026-10-19 | Claude Code (Agente B) | Migração de Agente B: `public/index.html` (fetch), `server/formalizacao.py` (~1700 linhas), `server/leitor.py` (lerTexto completo), configs (requirements.txt, .env, .gitignore, vercel.json), `tests/test_formalizacao.py` (40+ testes). | Implementar stubs; rodar pytest. |
| 2026-10-19 | Claude Code (Agente A) | **COMPLETADO**: (1) `server/models.py` + TentativaLogin; (2) `server/auth.py` melhorado com login_ persistente; (3) `server/handlers_admin.py` ~1300 linhas (25+ funções internas: lerEntrevista_, respostas_, salvarEntrevista_, publicar_, salvarCargo_, excluirCargo_, salvarUsuario_, salvarPosicoes_, definirSuperior_, salvarCargos_, salvarOrganograma_, importarCargos_, solicitar_, resolverSolicitacao_, pedirCorrecaoCargo_, resolverCorrecaoCargo_, meusPedidosDe_, validarConteudo, + 17+ wrappers api_*); (4) `server/handlers_tobe.py` ~600 linhas (tobeIniciado_, iniciarTobe_, tobeAdmin_, comSync_, corrigePais_, sincronizarTobe_, tobeVisao_, + 5 stubs Fase 1); (5) `server/main.py` dispatcher 32 funções (resp_/mudar_/mudar+sync); (6) `requirements.txt` corrigido (regex==2026.9.29). Todos os arquivos compilam (py_compile OK), imports OK, estrutura integrada. | pytest tests/test_fluxo.py -v; testes de bloqueio login; revisão final; deploy Vercel. |
| 2026-10-19 | Claude Code | **Correção de bug crítico** (`PROMPT_CORRECAO_FRONTEND.md`): restauradas as aspas tipográficas `“`/`”` em 26 linhas de `public/index.html` que haviam sido quebradas por uma limpeza anterior (substituição global por `"` ASCII), causando `SyntaxError` total no `<script>` e impedindo o carregamento da plataforma. `node --check` dos blocos `<script>` → 0 erros; `pytest` → 65/65 passando; requisição HTTP real → 200 OK. Fase 1/2 (ponte `/api/rpc`, botões `.pptx`, `apresentaFuncao`/`apresentaRotina`) confirmadas preservadas. | Validação visual no navegador (login, views, modal); seguir com migração Vercel / Fase 2. |
| 2026-10-19 | Claude Code (Opus) | **Anti-cache + blindagem da inicialização** (`PROMPT_OPUS_REVISAO.md`). Antes de mexer, confirmado que o JS já estava íntegro (`node --check` limpo; todos os ids usados no carregamento existem no HTML estático) → a tarja vermelha que "não sumiu" era **cache do navegador**. (1) Middleware `sem_cache` em `server/main.py`: `no-cache, no-store, must-revalidate, max-age=0` + `Pragma`/`Expires` e remoção de `ETag`/`Last-Modified` (senão o `StaticFiles` responde 304 e o navegador reusa o corpo antigo); `/api/export/` excluído para não atrapalhar os downloads `.pptx`. (2) Bloco `headers` em `vercel.json` (na Vercel o `/public` é CDN e não passa pelo middleware). (3) `mostra()` do `<head>` agora traz `arquivo:linha:coluna` + `e.error.stack`. (4) Stubs `window.loginTab/openSenha/tema` no `<head>` (clique nos botões do login antes de o script do fim do body rodar virava `ReferenceError`) + `window.loginTab = loginTab`. (5) `BE.demos()` blindado em `const DEMOS` (sempre array). (6) Helper `on(sel,ev,fn)` nos 11 listeners de inicialização + null-checks em `loginTab`/`cgRender`/`closeMenu`/Escape. (7) `const BE = REMOTO ? Remote : Server` → `const BE = Remote` (`Server` não existe no arquivo). Validado: `node --check` 0 erros, `pytest` 65/65, HTTP real 200 com os headers e sem ETag, `If-None-Match` falso → 200, `/api/rpc` OK, `/api/export/` sem header anti-cache. | Usuário dar **um** Ctrl+Shift+R (ou aba anônima) e validar no navegador. Se a tarja persistir, enviar o texto exato (agora com linha/coluna e stack). Depois: Fase 3 + deploy Vercel+Supabase. |

---

_Última atualização: 2026-10-19 por Claude Code (Opus)._
