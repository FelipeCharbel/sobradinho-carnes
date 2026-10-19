Você é o **COORDENADOR (Opus 5.5)** da **Fase 2** da plataforma "Gestão Sobradinho Carnes". Na Fase 1, a plataforma foi migrada com sucesso do Apps Script para FastAPI + SQLite local + frontend estático (com 100% dos testes verdes). 

Agora, na **Fase 2**, você coordenará a integração dos superpoderes da skill `manual-cargos-funcoes` na plataforma, delegando o trabalho para **2 subagentes Haiku 5.5 (Agente A e Agente B)** em paralelo, revisando, integrando e validando ponta a ponta.

---

# 0. LEITURA OBRIGATÓRIA ANTES DE INICIAR
1. `MEMORIA_COMPARTILHADA.md` e `CLAUDE.md`.
2. `docs/CONTRATOS.md` (contratos vigentes da Fase 1).
3. `C:/Users/Felipe Charbel/.claude/skills/manual-cargos-funcoes/`:
   - `scripts/build_manual.py` (motor de geração PPTX com clonagem de slides T2, reflow de listas e contraste).
   - `scripts/spec-exemplo.json` (schema JSON que alimenta o gerador).
   - `assets/T2.pptx` e `assets/selo-circular-preto.png` (template oficial A4 vertical e artefatos visuais).
   - `references/padrao-visual.md` e `references/guia-de-escrita.md`.

---

# 1. ESCOPO DA FASE 2 & REGRAS DE OURO

1. **Modo B (Por Cargo - Incremental):**
   - No drawer/card de cada cargo no frontend: botão **"Baixar Apresentação do Cargo (.pptx)"**.
   - Gera o arquivo `.pptx` de exatamente **5 páginas** daquele cargo (divisória com número/nome em contraste, missão/funções, rotinas, especificações, relações internas).
   - **Regra:** Conforme alinhado com o usuário, **SEM organograma** no Modo B.

2. **Modo A (Manual Completo - Institucional):**
   - Na barra superior/painel do Administrador e do Sócio: botão **"Exportar Manual Completo (.pptx)"**.
   - Compila todos os cargos com status `publicado` no formato do template T2 (capa institucional, sumário dinâmico, introdução, divisórias de seções, páginas de cada cargo e contra-capa com e-mails).
   - **Regra Especial:** Conforme alinhado com o usuário, o Modo A **DEVE GERAR O SLIDE DE ORGANOGRAMA** aproveitando a árvore hierárquica já validada na plataforma (`pai`, `superior`, `subordinados`, `níveis`).

3. **Paridade Visual e Técnica dos Slides:**
   - O gerador deve usar a biblioteca `python-pptx` (já instalada) e os assets oficiais (`assets/T2.pptx` e `assets/selo-circular-preto.png`).
   - Cor primária da Sobradinho Carnes: Vermelho institucional (`#E2010F` / `#B9010C`), com contraste automático de texto claro/escuro e divisórias alternando tom escuro conforme `padrao-visual.md`.

4. **Modelagem Refinada no Input (Guia de Escrita da Skill):**
   - Garantir que a inserção/edição de coletas aplique 100% das regras do `guia-de-escrita.md` (verbos no infinitivo, pontuação `;` e `.`, rotinas em 4 blocos fixos Diariamente/Semanalmente/Mensalmente/Sob demanda, e `A confirmar.` em itálico onde não houver dado).

5. **Deploy em Nuvem (Preparação Vercel + Supabase):**
   - Configuração de adapter no `server/db.py` para suportar `DATABASE_URL` do Supabase/PostgreSQL com pooling/SSL, mantendo o fallback para SQLite local em desenvolvimento.

---

# 2. ARQUITETURA ALVO (Fase 2)

```
sobradinho-carnes/
├── assets/
│   ├── T2.pptx                      # Copiado da skill
│   └── selo-circular-preto.png      # Copiado da skill
├── server/
│   ├── generator/
│   │   ├── __init__.py
│   │   ├── spec_builder.py          # Converte cargos/estrutura do banco SQL no JSON de spec oficial
│   │   ├── slide_engine.py          # Port e modularização do build_manual.py (python-pptx)
│   │   └── organograma_slide.py     # Gerador do slide de organograma vetorial/hierárquico para o Modo A
│   ├── handlers_export.py           # Endpoints de exportação (download de binário .pptx)
│   └── ... (arquivos da Fase 1 mantidos)
├── public/
│   └── index.html                   # Botões de download integrados na UI
└── tests/
    └── test_export.py               # Testes de geração e integridade dos PPTX (Modo A e Modo B)
```

---

# 3. DIVISÃO DE TAREFAS DOS AGENTES

## COORDENADOR (Opus 5.5)
1. Copiar os assets (`T2.pptx`, `selo-circular-preto.png`) da pasta da skill para `sobradinho-carnes/assets/`.
2. Especificar o contrato em `docs/CONTRATOS_FASE2.md`:
   - Endpoint `GET /api/export/cargo/{cargo_id}` (retorna stream `.pptx` com `Content-Disposition`).
   - Endpoint `GET /api/export/manual-completo` (retorna stream `.pptx` com `Content-Disposition`).
   - Schema de conversão do banco de dados para o dicionário da spec do gerador.
3. Disparar **Agente A e Agente B em paralelo**.
4. Revisar as implementações, validar que os `.pptx` gerados abrem sem corrupção no PowerPoint/LibreOffice/Google Slides.
5. Rodar a suíte completa de testes (`pytest`), atualizar `README.md` e a `MEMORIA_COMPARTILHADA.md`.

## AGENTE A (Haiku 5.5) — MOTOR DE GERAÇÃO PPTX (Backend Generator)
Arquivos: `server/generator/spec_builder.py`, `server/generator/slide_engine.py`, `server/generator/organograma_slide.py`, `server/handlers_export.py`, `tests/test_export.py`.
- **`spec_builder.py`:** Função que extrai do banco SQL os dados da empresa (`Sobradinho Carnes`, cor `#E2010F`), e-mails do Grupo Gestão e mapeia a ficha do cargo para o schema exato do `spec-exemplo.json`.
- **`slide_engine.py`:** Adaptar `build_manual.py` para operar como biblioteca em memória (`io.BytesIO`), suportando:
  - `gerar_slide_cargo(cargo_dict) -> BytesIO`: Gera as 5 páginas isoladas (Modo B).
  - `gerar_manual_completo(spec_dict) -> BytesIO`: Gera capa, sumário, introdução, organograma, cargos publicados e contra-capa (Modo A).
- **`organograma_slide.py`:** Implementar a geração da página de organograma no Modo A usando formas geométricas do `python-pptx` (caixas com cores de nível hierárquico e linhas de reporte baseadas em `pai`).
- **`handlers_export.py`:** Rotas FastAPI com validação de token/sessão (admin/sócio podem baixar completo; colaboradores só o próprio cargo).
- **Testes:** Validar geração de binário não vazio, integridade das 5 páginas no Modo B e presença do slide de organograma no Modo A.

## AGENTE B (Haiku 5.5) — FRONTEND UI, MODELAGEM & DEPLOY NUVEM
Arquivos: `public/index.html`, `server/db.py`, `vercel.json`, `docs/DEPLOY_SUPABASE.md`.
- **Frontend (`public/index.html`):**
  - No Drawer do cargo (`renderDrawer`): Adicionar botão destacado **"Baixar Ficha (.pptx)"** com ícone de apresentação chamando o download de `/api/export/cargo/{id}`.
  - Na barra superior/painel admin: Adicionar botão **"Exportar Manual Completo (.pptx)"** chamando `/api/export/manual-completo`.
  - Tratamento de loading/feedback visual enquanto o arquivo é gerado e baixado pelo navegador.
- **Modelagem no Input:**
  - Garantir que o modal de edição/leitura de entrevista aplique o `formalizarMissao`, `ajustaFuncoes` e `ajustaRotinas` automaticamente antes de salvar, conforme as regras da skill.
- **Configuração de Nuvem / Vercel:**
  - Ajustar `server/db.py` para suportar `postgresql+psycopg://` com detecção automática via `DATABASE_URL`.
  - Escrever o guia passo a passo em `docs/DEPLOY_SUPABASE.md` para conexão do banco na Vercel.

---

# 4. CRITÉRIOS DE ACEITE DA FASE 2
1. `pytest tests/test_export.py` passando 100%.
2. Clicar em "Baixar Ficha (.pptx)" no card de um cargo e o navegador baixar o arquivo de 5 páginas perfeito.
3. Clicar em "Exportar Manual Completo (.pptx)" e baixar a apresentação institucional completa contendo o slide de Organograma.
4. Nenhuma regressão nos testes existentes da Fase 1 (`test_fluxo.py` e `test_formalizacao.py`).
5. Atualização da `MEMORIA_COMPARTILHADA.md` com a conclusão da Fase 2.

Comece confirmando em 5 linhas o plano antes de disparar os subagentes.
