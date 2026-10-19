# PROMPT DE CORREÇÃO CRÍTICA: LEITOR DE ENTREVISTAS (TEXTO & DOCS)

**Papéis e Modelo Operacional:**
- **Coordenador Geral**: Claude Sonnet (arquitetura, revisão estrita de código e validação ponta a ponta).
- **Subagente Haiku 1**: Motor Backend Python (`server/leitor.py`, `server/handlers_admin.py` e testes).
- **Subagente Haiku 2**: Frontend & Contratos RPC (`public/index.html`, modal de leitura e persistência).

---

## 1. Contexto e Diagnóstico da Causa Raiz

Ao tentar ler qualquer entrevista (mesmo colando o texto completo no modal "Adicionar entrevista do Docs"), a plataforma exibe uma mensagem de erro na tela:
```
'str' object has no attribute 'normalize'
```

### Causa Raiz Exata Identificada:
No arquivo `server/leitor.py`, linha 20:
```python
def norm(s: str) -> str:
    """.gs linha 1161: minúsculo, sem acento, sem espaço nas pontas."""
    s = str(s or "").normalize("NFD")   # <-- ERRO CRÍTICO: .normalize() é método de JavaScript, NÃO existe em str do Python!
    s = regex.sub(r"[\p{M}]", "", s, flags=regex.UNICODE)
    return s.lower().strip()
```
Em Python, objetos `str` não têm o método `.normalize()`. O correto é:
```python
import unicodedata
s = unicodedata.normalize("NFD", str(s or ""))
```
Como toda chamada a `lerTexto()` chama `norm(s)` para casar cargos e ocupantes, o backend sempre disparava `AttributeError`, impedindo 100% dos usuários de ler qualquer entrevista colada ou do Docs.

---

## 2. Tarefa do Subagente Haiku 1 — Motor Backend & Leitor

1. **Correção em `server/leitor.py`:**
   - Corrigir a função `norm(s)` para usar `unicodedata.normalize("NFD", str(s or ""))`.
   - Fazer uma varredura completa em `server/leitor.py` buscando por qualquer outro método JavaScript importado erroneamente (ex: `.slice`, `.substr`, `.trim()`, `.match`, `replace` com regex sem `regex.sub`, etc.).
   - Garantir que `lerTexto(texto, cargos)` processe adequadamente:
     - Cabeçalho: Nome, Cargo, Tempo de empresa, Dia/horário de trabalho, Data da entrevista.
     - Pergunta 1: Missão do cargo (formalizada).
     - Pergunta 3: Funções atuais (divididas por linhas, com verbos no infinitivo).
     - Pergunta 4: Rotinas (diárias, semanais, mensais, sob demanda).
     - Perguntas 20 a 27: Notas de autoavaliação (1 a 5).
     - Demais perguntas do questionário.
     - Sugestão automática do cargo (`out["sugestao"]`) e ocupante no organograma existente.

2. **Suporte a Leitura por Link do Google Docs em `server/handlers_admin.py`:**
   - Em `lerEntrevista_(token, entrada, db, secret)`:
     - Se o campo `entrada.get("link")` for informado e `entrada.get("texto")` estiver vazio, tentar extrair o `doc_id` do link (`/document/d/([a-zA-Z0-9-_]+)`).
     - Tentar baixar o texto via export público do Google Docs:
       `https://docs.google.com/document/d/{doc_id}/export?format=txt`
       usando `urllib.request` ou `requests` com timeout de 6 segundos.
     - Se conseguir baixar o texto, alimentar `lerTexto(texto, cargos)`.
     - Se falhar (documento com permissão restrita ou sem internet), retornar mensagem amigável: `"Não foi possível acessar o link do Google Docs diretamente. Por favor, abra o documento, copie o texto inteiro e cole no campo de texto abaixo."`.

3. **Criação de Testes Automatizados (`tests/test_leitor_entrevista.py`):**
   - Criar teste com o caso real do usuário:
     ```text
     Roteiro de Entrevista
     Levantamento de cargos e funções — perguntas originais, organizadas por área.
     Nome
     Well
     Cargo
     Gestor de Compras
     Tempo de empresa
     9 anos
     Dia/horário de trabalho
     Segunda a sexta, das 8h às 18h
     1. Qual o objetivo final do seu cargo?
     Garantir o melhor abastecimento de carnes com o menor custo e alta qualidade.
     3. Quais são as suas funções principais?
     Negociar preços com frigoríficos; Acompanhar cotações do boi gordo; Gerir equipe de compras.
     4. Quais são as suas rotinas?
     Diárias: Acompanhar pedidos e entregas;
     Semanais: Fechar cotações de compras;
     Mensais: Apurar resultados do setor de compras.
     ```
   - Validar que o retorno contém `pessoa == 'Well'`, `cargoNome == 'Gestor de Compras'`, missão formalizada, lista de funções e rotinas populadas sem erros.

---

## 3. Tarefa do Subagente Haiku 2 — Frontend & Fluxo do Modal

1. **Revisar `public/index.html` (Funções `ivLer`, `renderModal`, `ivSalvar`):**
   - Na função `ivLer()`:
     - Assegurar que ao clicar em "Ler entrevista", ela faça `api("lerEntrevista", {link, texto})`.
     - Tratar erros exibindo `toast(e.message)`.
     - Ao ter sucesso, preencher `IV.p = r`, alterar para `IV.step = 2` e disparar `renderModal()`.
   - No `step === 2` do modal ("Conferir e salvar"):
     - Conferir se os campos de input/textarea (`ivMissao`, `ivFunc`, caixas de rotina `ivR_...`, `ivDias`, `ivHorario`, `ivObs`, `ivFerr`, `ivFormacao`) carregam os dados retornados sem quebrar por `null` ou `undefined`.
     - Validar que o botão "Salvar entrevista" (ou "Publicar") chama `ivSalvar()` corretamente, persistindo o manual do cargo no banco SQLite via `api("salvarEntrevista", ...)`.

---

## 4. Revisão e Validação pelo Coordenador Sonnet

1. Executar os novos testes:
   ```bash
   pytest tests/test_leitor_entrevista.py
   pytest
   ```
   Garantir que todos os testes (anteriores + novos) fiquem 100% verdes.
2. Executar requisição HTTP real no despachante `/api/rpc`:
   - Realizar login com usuário administrador.
   - Enviar POST `/api/rpc` com `fn: "lerEntrevista_"` e texto de teste.
   - Confirmar resposta HTTP 200 com payload estruturado contendo pessoa, cargo, missão, funções e rotinas.
3. Atualizar `MEMORIA_COMPARTILHADA.md` nas seções `## Checkpoint em Tempo Real` e no `Histórico de Sessões`.
