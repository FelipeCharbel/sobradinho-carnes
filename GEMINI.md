# Instruções para o Gemini 4 Argon neste diretório

Este diretório (`Projetos Gemini - Claude`) é um **espaço de trabalho compartilhado** entre você (Gemini 4 Argon, rodando no Google Antigravity) e o **Claude Code**, que roda neste mesmo diretório. Vocês dois podem editar os mesmos arquivos de código em momentos diferentes, então a sincronização de contexto é essencial.

## Regra obrigatória: `MEMORIA_COMPARTILHADA.md`

Antes de iniciar qualquer tarefa neste diretório:

1. **Leia `MEMORIA_COMPARTILHADA.md` por completo.** Ele contém o contexto do projeto, decisões de arquitetura e o histórico de sessões dos dois modelos. Pode haver trabalho recente do Claude Code que afeta o que você está prestes a fazer.
2. Verifique se há algo no histórico recente que conflita com o que o usuário está pedindo, ou que indique trabalho em andamento deixado pelo Claude Code. Se houver ambiguidade real sobre o estado do projeto, pergunte ao usuário antes de prosseguir.

Depois de concluir qualquer tarefa **ou a cada interação relevante de conversa/decisão** (Modo 100% Sempre Sincronizado):

3. **Atualize o bloco `## Checkpoint em Tempo Real` em `MEMORIA_COMPARTILHADA.md`** usando edição parcial (substituindo apenas aquelas 4–6 linhas, sem reescrever o arquivo todo para economizar tokens). Registre o que acabou de ser conversado/decidido ou executado, para que o usuário possa alternar para o Claude Code a qualquer momento sem perder o fio da meada.
4. Quando concluir uma entrega ou tarefa concreta, adicione também uma linha enxuta na tabela de "Histórico de Sessões" com: data, modelo (`Gemini 4 Argon`), resumo do que foi feito, e próximos passos/pendências (mantendo a tabela enxuta com no máximo as últimas 10 entradas).
5. Se a interação envolveu uma decisão de arquitetura, nova convenção, ou mudança estrutural relevante, atualize também as seções "Contexto do Projeto" e/ou "Arquitetura" no mesmo arquivo.
6. Nunca apague ou reescreva silenciosamente entradas feitas pelo Claude Code no histórico. Se algo que o Claude Code registrou estiver desatualizado ou incorreto, marque isso explicitamente em vez de simplesmente remover.

## Inicialização de Novo Projeto / Chat (Protocolo Tela Dupla)

Sempre que o usuário solicitar um novo projeto ou escopo em um chat novo:
1. **Criar a subpasta dedicada do projeto:** Criar `./[nome-do-projeto]/` imediatamente para isolar o contexto.
2. **Iniciar o Claude Code na subpasta:** Executar o comando para abrir o Claude já dentro daquela pasta no terminal:
   `Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '[nome-do-projeto]'; claude"`
   deixando o layout de tela dupla pronto exatamente como o usuário configurou.
3. Atualizar o `## Contexto do Projeto` e `## Checkpoint em Tempo Real` em `MEMORIA_COMPARTILHADA.md`.
4. **Entregar o comando pronto no chat:** É OBRIGATÓRIO fornecer explicitamente na resposta a linha de comando em destaque para o usuário colar no terminal interativo lateral:
   ```powershell
   cd .\[nome-do-projeto]; claude
   ```
   para que ele possa ativar o Claude instantaneamente na aba dele.

## Por que isso existe

Dois modelos diferentes (Claude Code e Gemini 4 Argon) trabalham de forma independente, em sessões separadas, sem visibilidade direta um do outro. O `MEMORIA_COMPARTILHADA.md` é o único mecanismo de continuidade entre eles — sem ele, cada sessão começaria do zero e poderia desfazer ou contradizer o trabalho do outro modelo.
