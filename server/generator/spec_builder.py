"""
Converte cargos do banco SQL (Fase 1) no dict de spec que `slide_engine.py` (port do
build_manual.py da skill manual-cargos-funcoes) espera. Ver docs/CONTRATOS_FASE2.md §1-§4 e §7
para as regras exatas de cada campo -- schema real em
C:/Users/Felipe Charbel/.claude/skills/manual-cargos-funcoes/scripts/spec-exemplo.json.

NÃO INVENTAR DADO: campos que não existem no banco (competencias, autonomia, processos) vão
sempre como ["A confirmar."] -- ver CONTRATOS_FASE2.md §1. supervisao é a única exceção: é
derivada do organograma (quem tem pai == este cargo), não "A confirmar." (ver §4).
"""

from server.modelo import carregar_, modelo_

COR_INSTITUCIONAL = "E2010F"
EMAILS_GRUPO_GESTAO: list = []  # ver CONTRATOS_FASE2.md §7 -- pendência de configuração

# Frequências Fase 1 (formalizacao.py) e mapeamento para skill (4 blocos fixos)
FREQS_MAPA = {
    "Diária": "Diariamente",
    "Semanal": "Semanalmente",
    "Mensal": "Mensalmente",
    "Quinzenal": "Sob demanda",
    "Trimestral": "Sob demanda",
    "Semestral": "Sob demanda",
    "Anual": "Sob demanda",
    "Sob demanda": "Sob demanda",
}


def pontua_lista(itens: list) -> list:
    """CONTRATOS_FASE2.md §2: remove pontuação final de cada item, acrescenta ';' em todos menos
    o último (que leva '.'). Lista vazia -> ["A confirmar."] (já correto, não pontuar de novo)."""
    if not itens:
        return ["A confirmar."]

    # Remove pontuação final de cada item
    limpos = []
    for item in itens:
        item_str = str(item).strip()
        # Remove ; ou . do final
        if item_str.endswith(";"):
            item_str = item_str[:-1].strip()
        elif item_str.endswith("."):
            item_str = item_str[:-1].strip()
        limpos.append(item_str)

    # Acrescenta ; em todos menos o último, que leva .
    resultado = []
    for i, item in enumerate(limpos):
        if i < len(limpos) - 1:
            resultado.append(item + ";")
        else:
            resultado.append(item + ".")

    return resultado


def dobra_rotinas(rotinas_banco: list) -> list:
    """CONTRATOS_FASE2.md §3: rotinas_banco = lista de {"f": <uma das 8 FREQS>, "t": texto}
    (formato Fase 1). Devolve EXATAMENTE 4 pares [["Diariamente",[...]], ["Semanalmente",[...]],
    ["Mensalmente",[...]], ["Sob demanda",[...]]] (formato da skill). Diária/Semanal/Mensal mapeiam
    direto; Quinzenal/Trimestral/Semestral/Anual caem em "Sob demanda" com prefixo
    "(Trimestral) " (etc.) no item, para não perder a informação da frequência original. Bloco
    vazio depois da dobra -> ["A confirmar."]. Aplicar pontua_lista() em cada bloco não-vazio."""

    if not rotinas_banco:
        rotinas_banco = []

    # Agrupa itens por bloco de destino
    blocos = {
        "Diariamente": [],
        "Semanalmente": [],
        "Mensalmente": [],
        "Sob demanda": [],
    }

    for item in rotinas_banco:
        freq_original = item.get("f", "").strip() if isinstance(item, dict) else ""
        texto = item.get("t", "").strip() if isinstance(item, dict) else ""

        if not texto:
            continue

        bloco_destino = FREQS_MAPA.get(freq_original, "Sob demanda")

        # Se cai em "Sob demanda" e não é originalmente "Sob demanda", adiciona prefixo
        if bloco_destino == "Sob demanda" and freq_original not in ("Sob demanda", ""):
            texto = f"({freq_original}) {texto}"

        blocos[bloco_destino].append(texto)

    # Monta resultado: sempre 4 pares, na ordem fixa
    resultado = [
        ["Diariamente", pontua_lista(blocos["Diariamente"])],
        ["Semanalmente", pontua_lista(blocos["Semanalmente"])],
        ["Mensalmente", pontua_lista(blocos["Mensalmente"])],
        ["Sob demanda", pontua_lista(blocos["Sob demanda"])],
    ]

    return resultado


def supervisao_de(cargo_id: str, organograma: list) -> list:
    """CONTRATOS_FASE2.md §4: organograma = lista de cargos (precisa ter 'id','pai','nome').
    Lista os NOMES dos cargos cujo pai == cargo_id, pontuados. Sem nenhum -> EXATAMENTE
    ["Não exerce supervisão."] (frase fixa do guia-de-escrita.md, não "A confirmar.")."""

    # Encontra subordinados diretos
    subordinados = [c["nome"] for c in organograma if c.get("pai") == cargo_id]

    if not subordinados:
        return ["Não exerce supervisão."]

    return pontua_lista(subordinados)


def construir_spec_cargo(cargo_dict: dict, organograma: list) -> dict:
    """CONTRATOS_FASE2.md §1 (tabela completa) + §6. cargo_dict é um cargo com 'conteudo' (mesmo
    formato de carregar_() da Fase 1: id,nome,missao,funcoes,rotinas,formacao,experiencia,
    habilidades,relacoes,...). organograma é a lista completa de cargos (para supervisao_de).
    Devolve o dict de UM cargo pronto para o spec: {nome, missao, funcoes, rotinas, formacao,
    experiencia, habilidades, competencias, relacionamentos, autonomia, supervisao, processos}.
    'n' NÃO é preenchido aqui -- é responsabilidade de construir_spec_manual/construir_spec_um_cargo
    (numeração sequencial, não por cargo isolado)."""

    conteudo = cargo_dict.get("conteudo", {})
    cargo_id = cargo_dict.get("id", "")

    # Nome (direto)
    nome = cargo_dict.get("nome", "")

    # Missão (direto, sem aspas -- a skill adiciona)
    missao = conteudo.get("missao", "")

    # Funções (lista, com pontuação)
    funcoes = conteudo.get("funcoes", [])
    funcoes_pontuadas = pontua_lista(funcoes) if funcoes else ["A confirmar."]

    # Rotinas (4 blocos fixos, com pontuação)
    rotinas_banco = conteudo.get("rotinas", [])
    rotinas_dobradas = dobra_rotinas(rotinas_banco)

    # Formação (lista de 1 item ou "A confirmar.")
    formacao = conteudo.get("formacao", "").strip()
    if formacao:
        formacao_lista = pontua_lista([formacao])
    else:
        formacao_lista = ["A confirmar."]

    # Experiência (lista de 1 item ou "A confirmar.")
    experiencia = conteudo.get("experiencia", "").strip()
    if experiencia:
        experiencia_lista = pontua_lista([experiencia])
    else:
        experiencia_lista = ["A confirmar."]

    # Habilidades (lista com pontuação ou "A confirmar.")
    habilidades = conteudo.get("habilidades", [])
    habilidades_pontuadas = pontua_lista(habilidades) if habilidades else ["A confirmar."]

    # Competências (sempre "A confirmar." -- não existe no banco)
    competencias = ["A confirmar."]

    # Relacionamentos (lista com pontuação ou "A confirmar.")
    relacionamentos = conteudo.get("relacoes", [])
    relacionamentos_pontuados = pontua_lista(relacionamentos) if relacionamentos else ["A confirmar."]

    # Autonomia (sempre "A confirmar." -- não existe no banco)
    autonomia = ["A confirmar."]

    # Supervisão (derivada do organograma)
    supervisao = supervisao_de(cargo_id, organograma)

    # Processos (sempre "A confirmar." -- não existe no banco)
    processos = ["A confirmar."]

    return {
        "nome": nome,
        "missao": missao,
        "funcoes": funcoes_pontuadas,
        "rotinas": rotinas_dobradas,
        "formacao": formacao_lista,
        "experiencia": experiencia_lista,
        "habilidades": habilidades_pontuadas,
        "competencias": competencias,
        "relacionamentos": relacionamentos_pontuados,
        "autonomia": autonomia,
        "supervisao": supervisao,
        "processos": processos,
    }


def construir_spec_manual(db) -> dict:
    """CONTRATOS_FASE2.md §6. Carrega os cargos via server.modelo.carregar_(db), filtra só
    status=='publicado', ordena por área então nome (mesma ordem usada no resto da Fase 1),
    numera 'n' sequencialmente como "3.1","3.2",... Monta:
    {"cliente": "Sobradinho Carnes", "cor": COR_INSTITUCIONAL, "emails": EMAILS_GRUPO_GESTAO,
     "introducao": [3 parágrafos -- ver guia-de-escrita.md §8: p1 o que é o manual + cliente
     ("Sobradinho Carnes", ramo "comércio e varejo de carnes") + escopo (deduzir das áreas dos
     cargos publicados, frase "Esta versão contempla os cargos das áreas de ..."); p2 para que
     serve (integração, recrutamento, desenvolvimento, evitar sobreposição); p3 referência oficial
     para consulta e avaliação de desempenho -- usar **negrito** nos termos-chave como no
     spec-exemplo.json],
     "cargos": [construir_spec_cargo(c, organograma) para cada cargo publicado, com 'n' setado]}.
    NÃO definir spec["modo"] (o padrão "completo" do build_manual.py já serve)."""

    # Carrega dados
    D = carregar_(db)

    # Filtra cargos publicados, ordena por área depois nome
    cargos_publicados = [
        c for c in D["cargos"]
        if c.get("conteudo") and c["conteudo"].get("status") == "publicado"
    ]
    cargos_publicados.sort(key=lambda c: (c.get("area", ""), c.get("nome", "")))

    # Coleta áreas dos cargos publicados (para escopo)
    areas_publicadas = sorted(set(c.get("area", "") for c in cargos_publicados if c.get("area")))

    # Monta introducao (3 parágrafos)
    if areas_publicadas:
        areas_texto = ", ".join(areas_publicadas)
    else:
        areas_texto = "não informadas"

    introducao = [
        f'O presente **Manual de Cargos, Funções e Rotinas** é um documento organizacional que detalha as **responsabilidades, atividades, habilidades e requisitos** de cada cargo da Sobradinho Carnes, empresa do ramo de comércio e varejo de carnes. Ele reúne, em um único documento, a descrição de cada posição, suas rotinas, seus níveis de autonomia e as competências esperadas de quem a ocupa. Esta versão contempla os cargos das áreas de {areas_texto}.',
        'Mais do que um registro formal, o Manual oferece uma **visão clara de como os cargos se relacionam** e de como cada função contribui para os resultados da empresa. Com isso, facilita a integração de novos colaboradores, apoia os processos de recrutamento e seleção, orienta planos de desenvolvimento e capacitação e reduz conflitos de responsabilidade, evitando sobreposição de tarefas e lacunas na execução das atividades.',
        'O documento também serve como **referência oficial** para consulta e alinhamento no dia a dia e pode ser utilizado em avaliações de desempenho, assegurando transparência e coerência na gestão.'
    ]

    # Monta cargos com numeração sequencial
    cargos_spec = []
    for idx, cargo in enumerate(cargos_publicados, start=1):
        spec_cargo = construir_spec_cargo(cargo, D["cargos"])
        spec_cargo["n"] = f"3.{idx}"
        cargos_spec.append(spec_cargo)

    # Acrescenta estrutura para organograma (ver CONTRATOS_FASE2.md §8)
    estrutura = [
        {
            "id": c["id"],
            "nome": c["nome"],
            "area": c.get("area", ""),
            "nivel": c.get("nivel", 1),
            "pai": c.get("pai"),
        }
        for c in D["cargos"]
    ]

    return {
        "cliente": "Sobradinho Carnes",
        "cor": COR_INSTITUCIONAL,
        "emails": EMAILS_GRUPO_GESTAO,
        "introducao": introducao,
        "cargos": cargos_spec,
        "estrutura": estrutura,
    }


def construir_spec_um_cargo(cargo_id: str, db) -> dict:
    """CONTRATOS_FASE2.md §6, modo "cargo" do build_manual.py (linha 25): só esse cargo, sem
    introducao/emails. Devolve {"modo": "cargo", "cliente": "Sobradinho Carnes",
    "cor": COR_INSTITUCIONAL, "cargos": [construir_spec_cargo(cargo, organograma)]} -- o 'n' do
    cargo aqui vira "3.XX" (o próprio build_manual.py já trata isso quando modo=="cargo" e 'n' não
    foi passado, ver linha 28: `_c.setdefault("n", "3.XX" if MODE == "cargo" else ...)` -- então
    aqui é melhor NÃO setar 'n' e deixar o slide_engine/build_manual decidir)."""

    # Carrega dados
    D = carregar_(db)

    # Encontra o cargo
    cargo = None
    for c in D["cargos"]:
        if c["id"] == cargo_id:
            cargo = c
            break

    if not cargo:
        raise ValueError(f"Cargo {cargo_id} não encontrado")

    # Constrói spec do cargo (sem setar 'n', deixa o build_manual.py decidir)
    spec_cargo = construir_spec_cargo(cargo, D["cargos"])

    # Monta estrutura para o organograma (todo cargo, não apenas este)
    estrutura = [
        {
            "id": c["id"],
            "nome": c["nome"],
            "area": c.get("area", ""),
            "nivel": c.get("nivel", 1),
            "pai": c.get("pai"),
        }
        for c in D["cargos"]
    ]

    return {
        "modo": "cargo",
        "cliente": "Sobradinho Carnes",
        "cor": COR_INSTITUCIONAL,
        "cargos": [spec_cargo],
        "estrutura": estrutura,
    }
