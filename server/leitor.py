"""
Port de lerTexto (.gs linhas 1157-1267, 1179-1266) -- leitor de entrevista a partir de texto colado.

Adaptação deliberada (CONTRATOS.md §7): no .gs, lerTexto lê de uma lista global mutável CARGOS
(preenchida por carregar_ antes da chamada). Aqui a lista de cargos é passada como parâmetro
explícito -- lerTexto(texto, cargos) -- sem global mutável. O comportamento de sugestão de cargo
(casar/porPessoa) deve ficar idêntico.

Importa de server.formalizacao (Agente B, mesmo módulo): formalizarMissao, formalizarJornada,
ajustaFuncoes, ajustaRotinas, capitalizaNomes2, recorreNormaliza, resumoAjuste, avisoAjuste,
defineNomes.
"""

import regex
import unicodedata


def norm(s: str) -> str:
    """.gs linha 1161: minúsculo, sem acento, sem espaço nas pontas."""
    s = unicodedata.normalize("NFD", str(s or ""))
    s = regex.sub(r"[\p{M}]", "", s, flags=regex.UNICODE)
    return s.lower().strip()


def tokens(s: str) -> list:
    """.gs linha 1163: tokeniza removendo stopwords curtas (de/da/do/e/a/o/para/em)."""
    STOP = {"de", "da", "do", "dos", "das", "e", "a", "o", "para", "em"}
    n = norm(s)
    token_list = regex.split(r"[^a-z0-9]+", n)
    return [t for t in token_list if len(t) > 1 and t not in STOP]


def _pref(a: str, b: str) -> bool:
    """.gs linha 1164: prefixo match."""
    if a == b:
        return True
    min_len = min(len(a), len(b))
    return min_len >= 5 and (a.startswith(b) or b.startswith(a))


def casar(texto: str, cargos: list, minimo: float = 0.99) -> str:
    """.gs linha 1165: acha o cargo cujo nome 'bate' melhor com o texto."""
    tt = tokens(texto)
    if not tt:
        return None

    best = None
    bs = 0

    for c in cargos:
        ct = tokens(c.get("nome", ""))
        if not ct:
            continue

        # Score: quantos tokens do cargo matcheiam tokens do texto
        sc = len([x for x in ct if any(_pref(x, y) for y in tt)]) / len(ct)

        # Melhora com comprimento do nome
        if sc >= minimo and (sc > bs or (sc == bs and best and len(ct) > len(tokens(best.get("nome", ""))))):
            best = c
            bs = sc

    return best.get("id") if best else None


def lerTexto(texto: str, cargos: list) -> dict:
    """Port de lerTexto (.gs linha 1179). Aceita texto puro OU o formato exportado do Google Docs."""
    from server.formalizacao import (
        formalizarMissao, formalizarJornada, ajustaFuncoes, ajustaRotinas,
        capitalizaNomes2, recorreNormaliza, resumoAjuste, avisoAjuste, defineNomes, FREQS
    )

    # .gs linha 1181: Limpa e normaliza linhas
    linhas = texto.replace("\r", "").replace(" ", " ").replace("\\([*_\\-#|.])", "$1").split("\n")
    linhas = [regex.sub(r"^#+\s*", "", l) for l in linhas]
    linhas = [regex.sub(r"\*+", "", l) for l in linhas]
    linhas = [regex.sub(r"\t+", " ", l) for l in linhas]
    linhas = [l.strip() for l in linhas]

    # .gs linha 1183: Encontra primeira linha numerada
    def ehNum(l):
        return bool(regex.search(r"^\d{1,2}\.\s+\S", l))

    i1 = next((i for i, l in enumerate(linhas) if ehNum(l)), -1)
    cab = linhas[:i1] if i1 >= 0 else linhas

    # .gs linha 1185-1194: Extrai campos do cabeçalho (tabela ou linhas)
    ROT = regex.compile(r"^(nome|cargo|tempo de empresa|dia\/hor[aá]rio.*|data da entrevista)\b", flags=regex.IGNORECASE)
    celulas = []
    for l in cab:
        if "|" in l:
            celulas.extend([c.strip() for c in l.split("|")])

    celulas = [c for c in celulas if c and not regex.search(r"^:?-+:?$", c)]

    def campo(nome):
        """Extrai campo do cabeçalho por rótulo."""
        # Tenta nas células (tabela)
        for c in celulas:
            m = regex.search(r"^" + nome + r"\b\s*:?\s*(.*)$", c, flags=regex.IGNORECASE)
            if m and m.group(1).strip():
                return m.group(1).strip()

        # Tenta nas linhas
        for i, l in enumerate(cab):
            m = regex.search(r"^" + nome + r"\b\s*:?\s*(.*)$", l, flags=regex.IGNORECASE)
            if not m:
                continue
            if m.group(1):
                return m.group(1).strip()
            for j in range(i + 1, len(cab)):
                if cab[j]:
                    return "" if ROT.search(cab[j]) else cab[j]
        return ""

    # .gs linha 1195-1199: Encontra bloco de texto por regex
    def bloco(re):
        """Encontra linhas de um bloco (depois de linha numerada que casa com regex)."""
        try:
            i = next(j for j, l in enumerate(linhas) if ehNum(l) and regex.search(re, l, flags=regex.IGNORECASE))
        except StopIteration:
            return []

        AJUDA = {"descrevendo a sua missão.", "explicar o que é uma função.", "defina a pessoa e o cargo.", "auxílio, etc.", "cite as funções."}
        out = []
        for j in range(i + 1, len(linhas)):
            if ehNum(linhas[j]):
                break
            l = linhas[j]
            if l and l.lower() not in AJUDA:
                out.append(l)
        return out

    # .gs linha 1200: Limpa item
    def limpa(s):
        s = str(s or "").rstrip(".;,").strip()
        if not s:
            return s
        return s[0].upper() + s[1:] if len(s) > 1 else s.upper()

    # .gs linha 1201: Placeholder
    VAZIO = regex.compile(r"^(n[aã]o|ainda n[aã]o|nenhum[a]?|n\/a|-)$", flags=regex.IGNORECASE)

    # .gs linhas 1202-1203: Extrai itens de lista (funções, habilidades, etc.)
    def itens(ls):
        out = []
        for l in ls:
            parts = regex.split(r";|\.\s+", l)
            for s in parts:
                s_len = len(s)
                if s_len > 140 or (s.count(",") >= 2 and ":" not in s):
                    sub_parts = regex.split(r",\s*", s)
                else:
                    sub_parts = [s]

                for sub in sub_parts:
                    sub = limpa(sub.strip())
                    if len(sub) > 1 and not VAZIO.search(sub):
                        out.append(sub)
        return out

    # .gs linhas 1204-1213: Extrai rotinas com frequência
    FREQ = [
        (r"^di[aá]ri[ao]s?$", "Diária"), (r"^semana(l|is)$", "Semanal"),
        (r"^quinzena(l|is)$", "Quinzenal"), (r"^mensa(l|is)$", "Mensal"),
        (r"^trimestra(l|is)$", "Trimestral"), (r"^semestra(l|is)$", "Semestral"),
        (r"^anua(l|is)$", "Anual"), (r"^(sob demanda|eventua(l|is)|quando necess)$", "Sob demanda")
    ]

    CONT = regex.compile(r"^(prazo|todo|toda|todos|todas|at[eé]|no|na|nos|nas|dia|dias|das|dos|do|da|de|entre|sendo|quando|com|pelo|pela|para|[aà]s|aos|em|sempre|antes|depois|exceto|conforme)\b", flags=regex.IGNORECASE)

    rotinas = []
    atual = None
    semFreq = 0

    def add_rotina(t):
        nonlocal semFreq, atual
        ps = []
        for p in regex.split(r";\s*|,\s*|\.\s+", t):
            p = p.strip()
            if not p:
                continue
            if ps and CONT.search(p):
                ps[-1] += ", " + p
            else:
                ps.append(p)

        for s in ps:
            s = limpa(s.strip())
            if len(s) > 1 and not VAZIO.search(s):
                if not atual:
                    semFreq += 1
                rotinas.append({"f": atual or "Sob demanda", "t": s})

    for l in bloco(r"rotinas"):
        m = regex.search(r"^([^:]{3,24}):\s*(.*)$", l)
        if m:
            prefixo = m.group(1).strip()
            for re_freq, freq_nome in FREQ:
                if regex.search(re_freq, prefixo, flags=regex.IGNORECASE):
                    atual = freq_nome
                    add_rotina(m.group(2))
                    break
            else:
                add_rotina(l)
        else:
            add_rotina(l)

    # .gs linhas 1214-1221: Extrai respostas (perguntas numeradas, exceto 20-27)
    respostas = []
    for i, l in enumerate(linhas):
        if not ehNum(l) or not regex.search(r"\?\s*$", l):
            continue

        n_match = regex.search(r"^(\d{1,2})\.", l)
        n = int(n_match.group(1)) if n_match else 0

        if 20 <= n <= 27:
            continue

        r = []
        for j in range(i + 1, len(linhas)):
            if ehNum(linhas[j]):
                break
            x = linhas[j]
            if x and x.lower() not in {"descrevendo a sua missão.", "explicar o que é uma função.", "defina a pessoa e o cargo.", "auxílio, etc.", "cite as funções."}:
                r.append(x)

        pergunta = regex.sub(r"^\d{1,2}\.\s*", "", l)[:300]
        respostas.append({"n": n, "p": pergunta, "r": "\n".join(r)[:4000]})

    # .gs linha 1222: Define nomes conhecidos
    nomes_pessoas = [c.get("pessoa", "") for c in cargos] + [campo("nome")]
    defineNomes(nomes_pessoas)

    # .gs linhas 1223-1231: Monta output principal
    out = {
        "cargoNome": campo("cargo"),
        "pessoa": campo("nome"),
        "data": campo("data da entrevista"),
        "missao": formalizarMissao(" ".join(bloco(r"objetivo final")).strip(), [campo("nome")]),
        "funcoes": itens(bloco(r"fun[cç][õo]es atuais")),
        "rotinas": rotinas,
        "lidera": " ".join(bloco(r"liderados?\s+por\s+voc")).strip(),
        "reportaA": " ".join(bloco(r"voc[eê]\s+[eé]\s+liderad|te\s+lideram")).strip(),
        "avisos": [],
        "jornada": formalizarJornada(campo(r"dia\/hor[aá]rio de trabalho")),
        "tempoEmpresa": campo("tempo de empresa"),
        "ferramentas": _extrair_ferramentas(texto),
        "habilidades": itens(bloco(r"habilidades exigidas")),
        "relacoes": [],
        "respostas": respostas
    }

    # .gs linhas 1232-1235: Ajusta funções/rotinas
    rs = resumoAjuste(out["funcoes"], out["rotinas"])
    out["funcoes"] = ajustaFuncoes(out["funcoes"])
    out["funcoes"] = [capitalizaNomes2(f) for f in out["funcoes"]]
    out["rotinas"] = ajustaRotinas(out["rotinas"])
    out["rotinas"] = [{"f": r["f"], "t": capitalizaNomes2(r["t"])} for r in out["rotinas"]]

    if rs["mudadas"] or rs["removidas"] or rs["fora"]:
        out["avisos"].append(avisoAjuste(rs))

    if semFreq:
        out["avisos"].append(f"{semFreq} rotina{'s' if semFreq != 1 else ''} sem frequência ficou em 'Sob demanda': confira.")

    # .gs linhas 1236-1248: Autoavaliação (perguntas 20-27)
    cru = texto.replace("\r", "").split("\n")
    out["auto"] = []
    for q in [20, 21, 22, 23, 24, 25, 26, 27]:
        try:
            i = next(j for j, l in enumerate(cru) if regex.search(r"^\\W*" + str(q) + r"\.", l.replace("\\", "")))
        except StopIteration:
            out["auto"].append(None)
            continue

        found = None
        for l in cru[i + 1:min(i + 7, len(cru))]:
            m = regex.search(r"\*{2,3}\s*\(\s*([1-5])\s*\)\s*\*{2,3}", l) or \
                regex.search(r"\(\s*[xX✓]\s*\)\s*([1-5])", l) or \
                regex.search(r"\(\s*([1-5])\s*[xX✓]\s*\)", l)
            if m:
                found = int(m.group(1))
                break

        out["auto"].append(found)

    # .gs linhas 1245-1248: Aviso de autoavaliação
    pergs_nota = sum(1 for q in [20, 21, 22, 23, 24, 25, 26, 27] if any(regex.search(r"^\\W*" + str(q) + r"\.", l.replace("\\", "")) for l in cru))
    sem_nota = pergs_nota - sum(1 for v in out["auto"] if v)
    if not any(out["auto"]):
        out["auto"] = None
    if sem_nota > 0:
        out["avisos"].append(f"Não consegui ler a nota de {sem_nota} das {pergs_nota} perguntas de autoavaliação, de 20 a 27.")

    # .gs linhas 1249-1251: Recorre
    def semVazio(s):
        if regex.search(r"^(n[aã]o|-)$", s.strip(), flags=regex.IGNORECASE):
            return ""
        return s.strip().rstrip(".")

    prob = semVazio(" ".join(bloco(r"quando h[aá] algum problema")))
    fora = semVazio(" ".join(bloco(r"n[aã]o (compete|[eé] da sua)")))
    recorre_text = prob + ("; fora da área, " + fora if fora and fora != prob else "")
    out["recorre"] = recorreNormaliza(recorre_text)

    # .gs linhas 1252-1255: Avisos finais
    if not out["missao"]:
        out["avisos"].append("Não encontrei a missão (pergunta 1).")
    if not out["funcoes"]:
        out["avisos"].append("Não encontrei as funções (pergunta 3).")
    if not out["rotinas"]:
        out["avisos"].append("Não encontrei rotinas (pergunta 4).")

    if len(out["avisos"]) == 3:
        raise ValueError("Não reconheci esse texto como uma entrevista. Cole o conteúdo do roteiro completo.")

    # .gs linhas 1256-1265: Sugestões (casar + porPessoa)
    out["sugestao"] = casar(out["cargoNome"] + " " + out["pessoa"], cargos) or None
    if not out["sugestao"]:
        nome_parts = norm(out["pessoa"]).split()
        if nome_parts:
            for c in cargos:
                pessoa_parts = norm(c.get("pessoa", "")).split()
                if pessoa_parts and pessoa_parts[0] == nome_parts[0]:
                    out["sugestao"] = c.get("id")
                    break

    def porPessoa(txt):
        tt = tokens(txt)
        for c in cargos:
            p_tokens = tokens(c.get("pessoa", ""))
            if p_tokens and len(p_tokens[0]) >= 3 and p_tokens[0] in tt:
                return c.get("id")
        return None

    out["sugestaoPai"] = casar(out["reportaA"], cargos) or porPessoa(out["reportaA"]) or None

    # .gs linhas 1259-1265: Afeta (trechos que falam de outro cargo)
    out["afeta"] = []
    vistos = set()
    for q in respostas:
        if q.get("n") not in [3, 4, 9, 10, 11, 12, 13, 14, 18, 28]:
            continue
        for fr in regex.split(r"(?<=[.!?])\s+|\n", q.get("r", "")):
            t = fr.strip()
            if len(t) < 12 or len(out["afeta"]) >= 12:
                continue
            id_cargo = casar(t, cargos) or porPessoa(t)
            if id_cargo and id_cargo + "|" + t not in vistos:
                vistos.add(id_cargo + "|" + t)
                out["afeta"].append({"cargoId": id_cargo, "trecho": t[:300], "pergunta": q.get("n")})

    return out


def _extrair_ferramentas(texto: str) -> list:
    """Extrai ferramentas mencionadas no texto."""
    ferramentas = set()
    # .gs linha 1228: busca por palavras-chave
    for m in regex.finditer(r"\b(Lumi[e]?|Excel|WhatsApp|plano de contas|DRE)\b", texto, flags=regex.IGNORECASE):
        ferr = m.group(1)
        if regex.search(r"^lumi", ferr, flags=regex.IGNORECASE):
            ferramentas.add("Lumi")
        else:
            ferramentas.add(ferr[0].upper() + ferr[1:])

    return sorted(list(ferramentas))
