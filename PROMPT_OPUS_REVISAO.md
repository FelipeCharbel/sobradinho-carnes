# PROMPT DE REVISÃO E CORREÇÃO FINAL (Claude Opus)

O usuário relatou:
"Ainda tem muita coisa errada. Por algum motivo, não sumiu."
(A tarja vermelha de erro ao carregar a plataforma ainda persiste ou algo quebrou na inicialização).

## Tarefas de Correção (Esforço Baixo / Direto ao Ponto)

1. **Evitar Cache do Navegador (Crítico):**
   No `server/main.py`, adicione um middleware simples para adicionar headers `Cache-Control: no-cache, no-store, must-revalidate` nas respostas HTML/estáticas. Isso garante que o navegador do usuário não continue servindo o `index.html` antigo em cache que continha os erros de sintaxe.

2. **Verificar Inicialização de `public/index.html`:**
   - Garanta que no `<head>`, a função `mostra(msg)` mostre detalhes legíveis do erro (incluindo `e.error?.stack` se disponível) para facilitar diagnóstico.
   - Verifique se na inicialização (linhas ~1350-1375) há qualquer chamada que possa falhar:
     - `loginTab` é chamado em `onclick` na linha 582. A função `loginTab` está declarada na linha 1351. Para evitar `ReferenceError: loginTab is not defined` caso algum elemento seja clicado antes do script terminar ou em caso de hoisting, garanta `window.loginTab = loginTab;` ou mova a declaração de `loginTab` para o topo dos scripts utilitários.
     - Verifique `BE.demos()`: certifique-se de que `BE.demos()` sempre retorne um array vazio `[]` e nunca quebre com undefined.
     - Verifique se os event listeners em `$("#loginForm")`, `$("#demoRow")`, etc., não lançam exceção caso algum elemento não exista.

3. **Validação Completa:**
   - Rode `node --check` nos scripts de `public/index.html`.
   - Rode `pytest` para confirmar 65 testes verdes.
   - Faça uma requisição HTTP via Python ou curl testando o retorno com os novos headers anti-cache.

4. **Atualização da Memória:**
   - Atualize `MEMORIA_COMPARTILHADA.md` no bloco `## Checkpoint em Tempo Real`.
