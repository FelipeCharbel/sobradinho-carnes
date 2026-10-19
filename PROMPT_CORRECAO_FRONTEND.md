# PROMPT DE REVISÃO E CORREÇÃO: SyntaxError em public/index.html

## 1. Contexto do Problema

Ao acessar `http://localhost:8000/`, a plataforma exibe uma tarja vermelha com:
```
Erro ao carregar a plataforma:
Uncaught SyntaxError: Invalid or unexpected token (linha 2816, coluna 295)
```
E anteriormente:
```
Uncaught SyntaxError: Unexpected identifier 'Conferir' (linha 889)
Uncaught ReferenceError: loginTab is not defined
```

## 2. Causa Raiz Identificada pelo Gemini

Em uma etapa anterior de limpeza, houve uma substituição global de aspas tipográficas unicode (`“` / `”`) por aspas duplas ASCII simples (`"`).
Isso quebrou strings literais em JavaScript que já estavam envolvidas por aspas duplas, por exemplo:
- **Linha 889:**
  ```javascript
  // Quebrado:
  const mensagemEstilo = v => "Para publicar, ajuste o padrão: função e rotina começam com verbo no infinitivo. Exemplo: "Conferir o ponto". Revise:" + v.slice(0, 3).map(x => """ + x.t.slice(0, 50) + """).join(", ") ...
  // Original em raw_source/Index.html:
  const mensagemEstilo = v => "Para publicar, ajuste o padrão: função e rotina começam com verbo no infinitivo. Exemplo: “Conferir o ponto”. Revise:" + v.slice(0, 3).map(x => "“" + x.t.slice(0, 50) + "”").join(", ") ...
  ```
- **Linha 1440:**
  ```javascript
  // Quebrado:
  ... marque "Não encontrei meu cargo"." : "A lista de cargos não carregou. Toque em "Tentar de novo" ...
  ```
- **Linha 1722:**
  ```javascript
  // Quebrado:
  if (!confirm("Desfazer a ligação de "" + c.nome + ""? Ele fica sem chefe ..."))
  ```
- **Linha 2887:**
  ```javascript
  // Quebrado:
  const motivos = restantes.slice(0, 2).map(v => """ + v.t.slice(0, 40) ...
  ```

Como o interpretador V8/JavaScript encontra `SyntaxError` ao fazer o parse do `<script>`, **nenhuma função da página é declarada** (nem `loginTab`, nem `carregar`, nem as views), gerando a falha total no carregamento.

Em JavaScript UTF-8, as aspas tipográficas `“` (U+201C) e `”` (U+201D) são caracteres de texto perfeitamente válidos dentro de strings. O arquivo `raw_source/Index.html` original é 100% válido e passa no `node --check` com zero erros.

## 3. Diretrizes de Correção

1. **Restaurar a integridade sintática de `public/index.html`:**
   - Corrigir todas as ocorrências de aspas quebradas (ou restaurar os caracteres originais `“` e `”` de `raw_source/Index.html`, ou escapá-los com `\"`).
   - Manter 100% preservadas as adições da Fase 1 e Fase 2:
     - Ponte `/api/rpc` (substituindo o antigo `google.script.run` e com suporte a token de sessão).
     - Botão **"Exportar Manual Completo (.pptx)"** na barra de `VIEWS.cargos`.
     - Botão **"Baixar Ficha (.pptx)"** no `renderDrawer`.
     - Chamadas de `apresentaFuncao` / `apresentaRotina` no modal.

2. **Validação Obrigatória:**
   - Extrair os blocos `<script>` de `public/index.html` e rodar `node --check` para garantir que o retorno seja 0 (ZERO erros de sintaxe).
   - Rodar `pytest` na pasta raiz para assegurar que os 65 testes continuam verdes.
   - Fazer uma requisição HTTP via Python ou curl em `http://localhost:8000/` e checar se o HTML é retornado perfeitamente.

3. **Atualização da Memória Compartilhada:**
   - Atualizar `MEMORIA_COMPARTILHADA.md` no bloco `## Checkpoint em Tempo Real` e adicionar a linha correspondente no histórico de sessões.
