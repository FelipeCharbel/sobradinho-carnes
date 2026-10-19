CONTRATOS FASE 2 — Exportação PPTX (skill `manual-cargos-funcoes`) + Nuvem
============================================================================

Fonte de verdade da Fase 2. Lida junto com `docs/CONTRATOS.md` (Fase 1, ainda vigente) e os 4
arquivos da skill em `C:/Users/Felipe Charbel/.claude/skills/manual-cargos-funcoes/`
(`scripts/build_manual.py`, `scripts/spec-exemplo.json`, `references/padrao-visual.md`,
`references/guia-de-escrita.md`).

---

## 0. Decisão de arquitetura: `build_manual.py` é um SCRIPT, não uma lib

O arquivo original da skill (527 linhas) lê `SPEC` de `sys.argv[1]` (caminho de arquivo JSON) e
escreve o `.pptx` final via **manipulação de ZIP em disco** (`tmp_out = OUT + ".tmp"`, depois
`zipfile.ZipFile(tmp_out)` → `zipfile.ZipFile(OUT, "w", ...)`, lendo e escrevendo arquivos reais).
Para virar uma função Python chamável em memória (`io.BytesIO`), como pede a Fase 2, é necessário:

1. Trocar `SPEC = json.load(open(sys.argv[1]))` por um parâmetro `spec: dict`.
2. Trocar `T2 = os.path.join(...)` por um caminho fixo para `sobradinho-carnes/assets/T2.pptx`
   (ok manter como arquivo em disco — é só leitura).
3. **O ponto delicado**: as linhas finais do script (486-526) abrem `T2` de novo com
   `zipfile.ZipFile(T2)` para pegar hashes de imagens, leem `tmp_out` com `zipfile.ZipFile(tmp_out)`
   e escrevem um ZIP novo em `OUT` trocando entradas (cor do tema, selo, "g6"). Isso continua
   funcionando perfeitamente com `io.BytesIO` no lugar de `tmp_out`/`OUT`: `zipfile.ZipFile` aceita
   qualquer objeto file-like. Troque:
   - `prs.save(tmp_out)` → `prs.save(buffer_tmp)` (um `io.BytesIO()`).
   - `zin = zipfile.ZipFile(tmp_out)` → `zipfile.ZipFile(buffer_tmp)` (dar `seek(0)` antes).
   - `zout = zipfile.ZipFile(OUT, "w", ...)` → `zipfile.ZipFile(buffer_final, "w", ...)`.
   - No final, `buffer_final.seek(0)` e devolver `buffer_final` (um `io.BytesIO` com os bytes do
     `.pptx` pronto), em vez de `os.remove(tmp_out)`.
4. O restante da lógica (clonagem de slides, reflow de texto, recolor, divisórias, selo tingido)
   **não muda nada** — é só transformar entrada/saída de arquivo para `dict`/`BytesIO`.

**Não reescreva a lógica de geração.** É script testado e aprovado pela skill; a única mudança
autorizada é a forma de entrada (dict em vez de arquivo JSON) e saída (BytesIO em vez de arquivo).

---

## 1. Lacuna real de schema: nem todo campo do `spec-exemplo.json` existe no banco

O `spec-exemplo.json` da skill espera, por cargo: `n, nome, missao, funcoes, rotinas, formacao,
experiencia, habilidades, competencias, relacionamentos, autonomia, supervisao, processos`.

O modelo de dados da Sobradinho Carnes (tabela `Cargos`, ver `docs/CONTRATOS.md` §2) só guarda:
`missao, funcoes, rotinas, jornada, tempoEmpresa, formacao, experiencia, habilidades, relacoes,
recorre, ferramentas`. **Não existem colunas para `competencias`, `autonomia` nem `processos`** —
são campos do questionário próprio da skill, mais detalhado que a entrevista do Web App.

Regra de ouro da skill (`guia-de-escrita.md`): **nunca inventar conteúdo**; o que não há na coleta
vira `"A confirmar."`. Portar esse princípio para `spec_builder.py`:

| Campo do spec | Fonte no banco | Regra |
|---|---|---|
| `n` | — | Sequencial **"3.1", "3.2"...** na ordem dos cargos **publicados**, por área então nome (mesma ordem de `retrato_.ordem`). NÃO é o `codigo` SC-XXX-01 do organograma — é outra numeração, só para o manual. |
| `nome` | `Cargo.nome` | direto |
| `missao` | `Cargo.missao` | direto (sem aspas — a skill adiciona) |
| `funcoes` | `Cargo.funcoes` (JSON lista) | aplicar pontuação (ver §2) |
| `rotinas` | `Cargo.rotinas` (JSON lista de `{f,t}`) | reagrupar nos 4 blocos fixos da skill (ver §3) |
| `formacao` | `Cargo.formacao` (STRING única) | envolver em lista de 1 item: `[texto]` com pontuação; vazio → `["A confirmar."]` |
| `experiencia` | `Cargo.experiencia` (STRING única) | igual a `formacao` |
| `habilidades` | `Cargo.habilidades` (JSON lista) | aplicar pontuação; vazio → `["A confirmar."]` |
| `competencias` | **não existe** | sempre `["A confirmar."]`. NÃO usar `ferramentas` como substituto — são conceitos diferentes (ferramentas = nomes de sistema; competências = "Domínio de/Conhecimento de"). |
| `relacionamentos` | `Cargo.relacoes` (JSON lista) | aplicar pontuação; vazio → `["A confirmar."]` |
| `autonomia` | **não existe** | sempre `["A confirmar."]` |
| `supervisao` | **derivado do organograma**, não de uma coluna | ver §4 — NÃO é "A confirmar.": tem regra própria |
| `processos` | **não existe** | sempre `["A confirmar."]` |

## 2. Pontuação das listas (guia-de-escrita.md §4/§5/§6/§7)

Para `funcoes`, `habilidades`, `relacionamentos` (= `relacoes`), e os itens de `formacao`/
`experiencia` quando não forem `"A confirmar."`: cada item termina em `;`, o **último** item da
lista termina em `.`. Função utilitária única em `spec_builder.py`:

```python
def pontua_lista(itens: list[str]) -> list[str]:
    """Remove pontuação final de cada item, acrescenta ';' em todos menos o último, que leva '.'.
    Lista vazia -> ["A confirmar."] (sem pontuação extra, já está correto)."""
```
Usar em TODO campo de lista do spec, exceto quando o valor final for exatamente `["A confirmar."]`
ou `["Não exerce supervisão."]` (esses dois já vêm prontos, não pontuar de novo).

## 3. Rotinas: de 8 frequências (Fase 1) para os 4 blocos fixos da skill

A Fase 1 suporta 8 frequências (`FREQS` em `formalizacao.py`): Diária, Semanal, Quinzenal, Mensal,
Trimestral, Semestral, Anual, Sob demanda. A skill só tem **4 blocos fixos, nesta ordem exata**:
Diariamente, Semanalmente, Mensalmente, Sob demanda (`guia-de-escrita.md` §5).

Regra de dobra (não perder informação): Diária→Diariamente, Semanal→Semanalmente,
Mensal→Mensalmente direto. **Quinzenal, Trimestral, Semestral e Anual caem no bloco "Sob
demanda"**, mas cada item desses leva um prefixo entre parênteses com a frequência original, para
não perder a informação: `"(Trimestral) Avaliar os relatórios de indicadores."`. Bloco vazio depois
da dobra → `["A confirmar."]`. O resultado final é **sempre exatamente 4 pares**, nesta ordem:
`[["Diariamente", [...]], ["Semanalmente", [...]], ["Mensalmente", [...]], ["Sob demanda", [...]]]`
(mesmo formato de `scripts/spec-exemplo.json`).

## 4. Supervisão exercida: derivada do organograma (não é "A confirmar.")

`guia-de-escrita.md` §7: *"Supervisão exercida: cargos que lidera formalmente. Quem não lidera
ninguém: 'Não exerce supervisão.'"* — isso **existe** na plataforma: são os cargos cujo `pai`
aponta para este cargo (`subordinados`, já calculado em `modelo_.posicaoDe`). Regra:
- Tem subordinados → lista os **nomes** deles, pontuados (`;`/`.`).
- Não tem nenhum → `["Não exerce supervisão."]` (frase fixa, não "A confirmar.").

## 5. Contrato RPC — endpoints de exportação

```
GET /api/export/cargo/{cargo_id}?token=<token>
  -> 200, Content-Type: application/vnd.openxmlformats-officedocument.presentationml.presentation
     Content-Disposition: attachment; filename="Ficha - <nome do cargo>.pptx"
     corpo: bytes do .pptx (5 páginas, modo "cargo" do build_manual.py)
  -> 403 {"erro": "..."} se o cargo não está no scope do usuário (mesma regra de modelo_.scope)
  -> 404 {"erro": "Cargo não encontrado."}
  -> 400 {"erro": "Este cargo ainda não tem manual publicado."} se c.conteudo é None ou status != "publicado"
     (exceção: admin pode baixar rascunho em revisão — ver nota)

GET /api/export/manual-completo?token=<token>
  -> 200, mesmo Content-Type, Content-Disposition: attachment; filename="Manual de Cargos - Sobradinho Carnes.pptx"
     corpo: bytes do .pptx completo (modo "completo", só cargos com status "publicado", com organograma)
  -> 403 {"erro": "NEGADO"} se perfil não é admin nem sócio
```

**Nota de autenticação:** os demais endpoints da Fase 1 recebem o token no corpo JSON do RPC
(`POST /api/rpc`); aqui o navegador vai disparar um download via `<a href>`/`window.location`, que
não manda corpo JSON. Passar o token como **query string** (`?token=...`) é a forma prática de
autenticar um download direto de arquivo. `handlers_export.py` deve validar esse token com a MESMA
função `sessao_()` da Fase 1 (`server/auth.py`) — não criar um mecanismo de auth paralelo.

**Regra de acesso (Agente A, `handlers_export.py`):**
- `/api/export/cargo/{id}`: usa `modelo_(carregar_(db)).scope(u)` — mesma regra de visibilidade que
  já existe para abrir a ficha no drawer. Admin vê e baixa qualquer cargo (inclusive rascunho em
  revisão — explicitamente pedido pelo prompt da Fase 2 não, mas é consistente com o resto da Fase 1
  onde admin vê tudo); não-admin só baixa cargo com `status == "publicado"` dentro do próprio scope.
- `/api/export/manual-completo`: só `perfil in ("admin", "socio")`, replicando `soAdmin_`-like check
  mas aceitando sócio também (sócio já vê todos os cargos publicados no retrato da Fase 1).

## 6. Módulos e assinaturas (fronteira entre Agente A e Agente B)

```python
# server/generator/spec_builder.py (Agente A)
def construir_spec_cargo(cargo_dict: dict, organograma: list[dict]) -> dict:
    """Devolve o dict de UM cargo no formato da skill (nome, missao, funcoes, rotinas, formacao,
    experiencia, habilidades, competencias, relacionamentos, autonomia, supervisao, processos),
    aplicando as regras das seções 1-4 deste contrato. 'organograma' é a lista de todos os cargos
    (para calcular supervisao a partir de quem tem pai == cargo_dict['id'])."""

def construir_spec_manual(db) -> dict:
    """Monta o dict completo: cliente='Sobradinho Carnes', cor='E2010F', emails (ver §7),
    introducao (3 parágrafos, ver guia-de-escrita.md §8 -- escopo = áreas dos cargos publicados),
    cargos=[construir_spec_cargo(c, organograma) para cada cargo com status=='publicado', ordenados
    por área então nome, com 'n' sequencial "3.1","3.2"...]. NÃO inclui modo='completo' explicitamente
    (é o padrão do build_manual.py)."""

def construir_spec_um_cargo(cargo_id: str, db) -> dict:
    """Monta o dict no modo 'cargo' (ver .gs / build_manual.py linha 25): {"modo": "cargo",
    "cliente", "cor", "cargos": [construir_spec_cargo(...)]} -- só esse cargo, sem emails/introducao
    (não usados no modo cargo)."""

# server/generator/slide_engine.py (Agente A)
def gerar_slide_cargo(spec: dict) -> "io.BytesIO":
    """spec já no modo 'cargo' (de construir_spec_um_cargo). Devolve BytesIO do .pptx de 5 páginas.
    Port de build_manual.py conforme §0 deste contrato."""

def gerar_manual_completo(spec: dict) -> "io.BytesIO":
    """spec no modo 'completo' (de construir_spec_manual). Devolve BytesIO do .pptx institucional
    inteiro, COM o slide de organograma (ver organograma_slide.py) inserido conforme §8."""

# server/generator/organograma_slide.py (Agente A)
def inserir_slide_organograma(prs, estrutura: list[dict], brand_hex: str, dark_hex: str, apos_slide_index: int):
    """Insere UM slide novo (python-pptx shapes: retângulos por cargo, linhas conectando a quem
    reporta via 'pai', cor por nível hierárquico dentro da paleta cor-do-cliente/tom-escuro/neutro)
    na posição 'apos_slide_index' do deck 'prs' (Presentation já aberta pelo slide_engine).
    'estrutura' = lista de {id, nome, area, nivel, pai} (mesmo formato do retrato_.estrutura da
    Fase 1). Ver §8 para a posição exata e o ajuste de numeração do sumário que isso implica."""

# server/handlers_export.py (Agente A)
# GET /api/export/cargo/{cargo_id} e GET /api/export/manual-completo -- ver §5.

# server/db.py (Agente B) -- adapta o existente, não reescreve do zero
def get_engine():
    """ACRESCENTAR: detectar DATABASE_URL que comece com 'postgres://' ou 'postgresql://' (formato
    comum do Supabase) e normalizar para 'postgresql+psycopg://' (usa o driver psycopg3, já em
    requirements.txt) antes de create_engine. Acrescentar pool_pre_ping=True sempre (conexões
    Postgres gerenciadas caem e precisam de ping antes de reusar). Manter o fallback sqlite:///
    exatamente como está hoje -- não quebrar o `DATABASE_URL` ausente (continua caindo no SQLite
    local)."""
```

## 7. E-mails do Grupo Gestão e cor institucional

`spec["emails"]` (contra-capa do manual completo) e `spec["cor"]` (`E2010F`, vermelho institucional
da Sobradinho Carnes) **não existem em nenhuma tabela** — são constantes de configuração desta
entrega. Agente A define como constantes no topo de `spec_builder.py`:
```python
COR_INSTITUCIONAL = "E2010F"
EMAILS_GRUPO_GESTAO: list[str] = []  # lista vazia por padrão -- ver nota abaixo
```
**Nota:** sem uma lista real de e-mails fornecida nesta tarefa, `EMAILS_GRUPO_GESTAO` fica vazia
(a página final do manual sai sem e-mails, igual ao comportamento do `build_manual.py` quando
`emails` é lista vazia — não é erro). Documentar isso no README como pendência de configuração.

## 8. Slide de organograma (Modo A) — posição exata e ajuste do sumário

Insira o organograma como **uma página extra dentro da seção 2** ("Descrição dos Cargos"), logo
depois das 4 páginas explicativas existentes (`orig[10]` a `orig[13]` clonados em
`build_manual.py`) e **antes** da divisória 3 "Cargos". Isso soma **+1 slide** ao deck, e por isso
desloca a numeração do sumário a partir da seção "Cargos" em diante. Em `build_manual.py`,
`build_sumario(..., first=True)` grava:

```python
for p, pg in zip(pars(right)[:3], [pg2(3 + EXTRA), pg2(5 + EXTRA), pg2(10 + EXTRA)]):
```

e mais abaixo, por cargo:

```python
set_run(r, with_page(r.find(qn("a:t")).text, pg2(11 + EXTRA + 5 * ci)))
```

Com +1 slide antes da seção "Cargos": a entrada "Introdução" (`3 + EXTRA`) e "Descrição dos
Cargos" (`5 + EXTRA`) **não mudam** (o organograma entra DEPOIS de onde a seção 2 começa); só
**"Cargos" vira `11 + EXTRA`** (era `10 + EXTRA`) e **cada cargo vira `12 + EXTRA + 5*ci`** (era
`11 + EXTRA + 5*ci`). Agente A: localizar essas duas linhas no `slide_engine.py` portado e ajustar
os números fixos (+1 nos dois), e validar no final que `len(final) == len(built)` (asserção que já
existe no script) continua batendo depois de inserir o slide do organograma.

---

## 9. Fronteira exata entre Agente A e Agente B

- **Agente A não toca** em `public/index.html`, `server/db.py`, `vercel.json` nem em
  `docs/DEPLOY_SUPABASE.md` — isso é do Agente B.
- **Agente B não toca** em `server/generator/*`, `server/handlers_export.py` nem
  `tests/test_export.py` — isso é do Agente A.
- Agente B consome os dois endpoints (`/api/export/cargo/{id}`, `/api/export/manual-completo`) só
  pela URL com `?token=...` (nenhuma dependência de código Python do Agente A).
- Agente B importa de `server/formalizacao.py` (já existe, Fase 1) `formalizarMissao`,
  `ajustaFuncoes` (plural, já existe), `ajustaRotinas` (plural, já existe) para o item "Modelagem no
  Input" — não precisa criar nada novo em `formalizacao.py`, só CHAMAR essas funções no ponto certo
  do fluxo de salvar a entrevista no frontend (ver §11 abaixo — na real, a formalização já acontece
  no SERVIDOR em `salvarEntrevista_`/`validarConteudo`; o pedido do item 4 da Fase 2 é sobre o modal
  de edição mostrar/aplicar o texto JÁ formalizado ao reabrir para editar, não duplicar a lógica no
  cliente).

## 10. Testes obrigatórios (`tests/test_export.py`, Agente A)

1. `construir_spec_cargo`: cargo com todos os campos preenchidos → nenhum `"A confirmar."` onde há
   dado real; cargo sem `competencias`/`autonomia`/`processos` (sempre, pois não existem no banco)
   → esses 3 saem como `["A confirmar."]`; cargo sem subordinados → `supervisao ==
   ["Não exerce supervisão."]`; cargo com 2 subordinados → `supervisao` lista os dois nomes.
2. `construir_spec_cargo` com rotina `"Trimestral"` → cai em "Sob demanda" com prefixo
   `"(Trimestral) "` no item.
3. `gerar_slide_cargo`: binário não vazio, é um .pptx válido (abre com
   `pptx.Presentation(io.BytesIO(resultado))` sem exceção), tem exatamente 5 slides.
4. `gerar_manual_completo`: abre sem exceção, contém pelo menos capa + sumário + introdução +
   organograma + (5 × nº de cargos publicados) + contra-capa; nenhuma referência a `"3.XX"` (só
   aparece no modo "cargo").
5. Nenhuma regressão: `pytest tests/test_fluxo.py tests/test_formalizacao.py` continuam 100% verdes.

## 11. Modelagem no input (Agente B) — o que já existe vs. o que falta

A Fase 1 **já aplica** `formalizarMissao`/`ajustaFuncoes`/`ajustaRotinas` no servidor, dentro de
`leitor.lerTexto` (quando a entrevista é lida do texto colado) e implicitamente via
`validarConteudo` (valida, não reformata, exceto o bloqueio de publicar com estilo errado). O que
falta, e é o escopo real do item 4 da Fase 2: no modal de **edição manual** de uma entrevista já
existente (`openInterview(cargoId, true)` em `public/index.html`), ao exibir os campos para edição,
garantir que o texto mostrado já passou por `apresentaFuncao`/`apresentaRotina` (funções client-side
que já existem no `Index.html` original, linha ~1561-1562: `capitalizaNomes2(formalizar(...))`) —
ou seja, conferir se esse modal já usa essas funções (provavelmente sim, portado do original) e,
se não usar em algum campo, adicionar a chamada. **Não duplicar `ajustaFuncao`/`formalizarMissao`
em JavaScript** — essas já existem como funções client-side espelhadas do motor de texto original
(ver `Index.html` linhas 1290-1854 portadas) desde a Fase 1; o trabalho aqui é de conferência e
pequenos ajustes de UI, não de reimplementação.
