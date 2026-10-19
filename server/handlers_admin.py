"""
api_* (exceto TO BE) + funções internas correspondentes. Ver docs/CONTRATOS.md §1.2 para o
wrapper de cada api_* (resp/mudar/mutar+sync) e §7 para a fronteira com formalizacao.py/leitor.py
(Agente B). Toda api_* aqui chama sessao_/so_admin_ de auth.py.
"""
import json
import uuid
import re
from datetime import datetime
from sqlalchemy.orm import Session
from server.models import Cargo, Entrevista, Usuario, Solicitacao, Registro, TentativaLogin
from server.auth import ErroNegocio, sessao_, so_admin_, hash_senha_
from server.modelo import carregar_, modelo_, retrato_


# Helper de normalização
def _norm_(s: str) -> str:
    """Normaliza: minúsculo, sem acentos, sem espaço nas pontas."""
    import unicodedata
    s = str(s or "").lower().strip()
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("utf-8")


def _slug_(s: str) -> str:
    """Cria slug a partir de um texto."""
    s = _norm_(s).replace(" ", "-")
    s = "".join(c if c.isalnum() or c == "-" else "" for c in s)
    s = s.replace("--", "-").strip("-")
    return s[:24] if s else "cargo"


def dadosCargo_(d: dict, rotulo: str = "") -> dict:
    """Port de dadosCargo_ (.gs linha 183): valida/limpa nome, area, pessoa."""
    nome = str(d.get("nome") or "").strip()[:80]
    area = str(d.get("area") or "").strip()[:60]
    pessoa = str(d.get("pessoa") or "").strip()[:80]
    r = (rotulo + ": ") if rotulo else ""
    if not nome:
        raise ErroNegocio(r + "falta o nome do cargo.")
    if not area:
        raise ErroNegocio(r + "falta a área" + ((" (" + nome + ")") if rotulo else "") + ".")
    return {"nome": nome, "area": area, "pessoa": pessoa}


def fazCiclo_(id: str, pai: str, paiDe: dict) -> bool:
    """Port de fazCiclo_ (.gs linha 190)."""
    p = pai
    k = 0
    while p and k < 80:
        if p == id:
            return True
        p = paiDe.get(p)
        k += 1
    return False


def novoIdCargo_(nome: str, usados: set) -> str:
    """Port de novoIdCargo_ (.gs linha 181)."""
    import random
    import string

    base = _slug_(nome)
    id = base
    while id in usados:
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        id = f"{base}-{suffix}"
    usados.add(id)
    return id


def anotaHistorico_(hist: list, rev: int, u: dict, motivo: str) -> list:
    """Port de anotaHistorico_ (.gs linha 196): anota no histórico, últimas 30 entradas."""
    hist = hist or []
    novo = {
        "rev": rev,
        "data": datetime.utcnow().isoformat(),
        "por": u.get("nome", ""),
        "motivo": motivo[:300] if motivo else ""
    }
    return (hist + [novo])[-30:]


def definirSuperior_(token: str, id: str, pai: str, db: Session, secret: str) -> bool:
    """Port de definirSuperior_ (.gs linha 1047): confere ciclo, grava pai."""
    u = sessao_(token, db, secret)
    so_admin_(u, "ligar cargos no organograma")

    D = carregar_(db)
    c = next((x for x in D["cargos"] if x["id"] == id), None)
    pai = str(pai or "").strip()

    if not c:
        raise ErroNegocio("Cargo não encontrado.")
    if pai and not any(x["id"] == pai for x in D["cargos"]):
        raise ErroNegocio("O cargo superior escolhido não existe.")
    if pai == id:
        raise ErroNegocio("Um cargo não pode responder a ele mesmo.")

    paiDe = {}
    for x in D["cargos"]:
        paiDe[x["id"]] = x.get("pai") or ""

    if pai and fazCiclo_(id, pai, paiDe):
        raise ErroNegocio("Um cargo não pode ficar abaixo dele mesmo nem de quem está abaixo dele.")

    cargo = db.query(Cargo).filter(Cargo.id == id).first()
    if cargo:
        cargo.pai = pai if pai else None
        db.add(cargo)
        db.add(Registro(quando=datetime.utcnow(), quem=u["nome"], acao=f"Ligou cargo {cargo.nome}"))
        db.commit()

    return True


def salvarCargos_(token: str, lista: list, db: Session, secret: str) -> dict:
    """Port de salvarCargos_ (.gs linha 1077): batch update com confere tudo antes de gravar."""
    u = sessao_(token, db, secret)
    so_admin_(u, "editar organograma")

    if not isinstance(lista, list) or not lista:
        raise ErroNegocio("Nenhuma alteração para salvar.")
    if len(lista) > 300:
        raise ErroNegocio("No máximo 300 cargos por vez.")

    # Carrega cargos atuais da BD
    cargos_bd = {c.id: c for c in db.query(Cargo).all()}
    mapa = {}  # id -> pai como está na BD

    for cid, c in cargos_bd.items():
        mapa[cid] = c.pai or ""

    vistos = set()
    itens = []

    for d in lista:
        d = d or {}
        id = str(d.get("id") or "")

        if id not in cargos_bd:
            raise ErroNegocio("Cargo não encontrado.")
        if id in vistos:
            raise ErroNegocio(f"{cargos_bd[id].nome}: o mesmo cargo aparece mais de uma vez na lista.")
        vistos.add(id)

        dados = dadosCargo_(d, str(cargos_bd[id].nome))
        pai = str(d.get("pai") or "")

        if pai and pai not in cargos_bd:
            raise ErroNegocio(f"{dados['nome']}: o cargo superior escolhido não existe.")
        if pai == id:
            raise ErroNegocio(f"{dados['nome']}: um cargo não pode responder a ele mesmo.")

        itens.append({"id": id, "pai": pai, **dados})

    # Confere ciclos
    for it in itens:
        mapa[it["id"]] = it["pai"]
    for it in itens:
        if fazCiclo_(it["id"], it["pai"], mapa):
            raise ErroNegocio(f"{it['nome']}: um cargo não pode ficar abaixo dele mesmo nem de quem está abaixo dele.")

    # Grava
    for it in itens:
        c = cargos_bd[it["id"]]
        c.nome = it["nome"]
        c.area = it["area"]
        c.pai = it["pai"] if it["pai"] else None
        c.pessoa = it["pessoa"]
        db.add(c)

    db.add(Registro(quando=datetime.utcnow(), quem=u["nome"], acao=f"Editou {len(itens)} cargos no organograma"))
    db.commit()

    return {"n": len(itens)}


def salvarOrganograma_(token: str, d: dict, db: Session, secret: str) -> dict:
    """Port de salvarOrganograma_ (.gs linha 1109): posições + ligações com confere tudo."""
    u = sessao_(token, db, secret)
    so_admin_(u, "mover cargos no organograma")

    d = d or {}
    posicoes = [p for p in (d.get("posicoes") or []) if p]
    ligacoes = [l for l in (d.get("ligacoes") or []) if l]
    reset = d.get("reset", False)

    if not reset and not posicoes and not ligacoes:
        raise ErroNegocio("Nada para salvar.")
    if len(posicoes) > 500 or len(ligacoes) > 500:
        raise ErroNegocio("Alterações demais de uma vez. Salve em partes.")

    cargos_bd = {c.id: c for c in db.query(Cargo).all()}
    mapa = {cid: (c.pai or "") for cid, c in cargos_bd.items()}

    # Processa posições
    pos = []
    for p in posicoes:
        p = p or {}
        id = str(p.get("id") or "")
        x = int(p.get("x") or 0)
        y = int(p.get("y") or 0)

        if id not in cargos_bd:
            raise ErroNegocio("Cargo não encontrado.")
        if not (-20000 <= x <= 20000) or not (-20000 <= y <= 20000):
            raise ErroNegocio("Posição inválida.")
        pos.append({"id": id, "x": x, "y": y})

    # Processa ligações
    lig = []
    for l in ligacoes:
        l = l or {}
        id = str(l.get("id") or "")
        pai = str(l.get("pai") or "")

        if id not in cargos_bd:
            raise ErroNegocio("Cargo não encontrado.")
        if pai and pai not in cargos_bd:
            raise ErroNegocio("O cargo superior escolhido não existe.")
        if pai == id:
            raise ErroNegocio(f"{cargos_bd[id].nome}: um cargo não pode responder a ele mesmo.")

        mapa[id] = pai
        lig.append({"id": id, "pai": pai})

    # Confere ciclos
    for l in lig:
        if l["pai"] and fazCiclo_(l["id"], l["pai"], mapa):
            raise ErroNegocio(f"{cargos_bd[l['id']].nome}: um cargo não pode ficar abaixo dele mesmo nem de quem está abaixo dele.")

    # Grava
    if reset:
        for c in cargos_bd.values():
            c.x = None
            c.y = None
            db.add(c)

    for p in pos:
        c = cargos_bd[p["id"]]
        c.x = p["x"]
        c.y = p["y"]
        db.add(c)

    for l in lig:
        c = cargos_bd[l["id"]]
        c.pai = l["pai"] if l["pai"] else None
        db.add(c)

    if reset or pos or lig:
        db.add(Registro(quando=datetime.utcnow(), quem=u["nome"], acao=f"Salvou organograma: {len(pos)} posições e {len(lig)} ligações"))
        db.commit()

    return {"n": len(pos), "ligacoes": len(lig)}


def validarConteudo(d: dict) -> dict:
    """Port de validarConteudo (.gs linha 1273): valida missão, funções, rotinas."""
    from server.formalizacao import FREQS, violacoesEstilo, mensagemEstilo

    d = d or {}
    publicar = bool(d.get("publicar"))

    missao = str(d.get("missao") or "").strip()
    funcoes = [s for s in (str(x).strip() for x in (d.get("funcoes") or [])) if s]
    rotinas = []
    for r in (d.get("rotinas") or []):
        r = r or {}
        t = str(r.get("t") or "").strip()
        if t:
            rotinas.append({"f": r.get("f"), "t": t})

    if not missao and publicar:
        raise ErroNegocio("Escreva a missão do cargo antes de publicar (pode salvar para revisão sem ela).")
    if len(missao) > 800:
        raise ErroNegocio("A missão está muito longa (máximo 800 letras).")
    if not funcoes:
        raise ErroNegocio("Inclua pelo menos uma função.")
    if len(funcoes) > 60 or any(len(f) > 400 for f in funcoes):
        raise ErroNegocio("Funções demais ou longas demais.")
    if len(rotinas) > 150 or any((r["f"] not in FREQS) or len(r["t"]) > 400 for r in rotinas):
        raise ErroNegocio(f"Rotinas inválidas: cada rotina precisa de uma frequência ({', '.join(FREQS)}).")

    def _txt(v, maxlen):
        return str(v or "").strip()[:maxlen]

    def _lst(v):
        itens = v if isinstance(v, list) else str(v or "").split("\n")
        itens = [s for s in (str(x).strip() for x in itens) if s][:30]
        return [s[:200] for s in itens]

    if publicar:
        v = violacoesEstilo(funcoes, rotinas)
        if v:
            raise ErroNegocio(mensagemEstilo(v) + " (Você pode salvar para revisão sem ajustar.)")

    respostas_in = d.get("respostas") if isinstance(d.get("respostas"), list) else []
    respostas = []
    for q in respostas_in[:40]:
        q = q or {}
        p = _txt(q.get("p"), 300)
        if p:
            try:
                n = int(q.get("n") or 0)
            except (TypeError, ValueError):
                n = 0
            respostas.append({"n": n, "p": p, "r": _txt(q.get("r"), 4000)})

    return {
        "missao": missao,
        "funcoes": funcoes,
        "rotinas": rotinas,
        "respostas": respostas,
        "jornada": _txt(d.get("jornada"), 400),
        "formacao": _txt(d.get("formacao"), 160),
        "experiencia": _txt(d.get("experiencia"), 200),
        "habilidades": _lst(d.get("habilidades")),
        "relacoes": _lst(d.get("relacoes")),
        "recorre": _txt(d.get("recorre"), 200),
        "ferramentas": _lst(d.get("ferramentas")),
        "tempoEmpresa": _txt(d.get("tempoEmpresa"), 60),
    }


def lerEntrevista_(token: str, entrada: dict, db: Session, secret: str) -> dict:
    """Port de lerEntrevista_ (.gs linha 383)."""
    from server.leitor import lerTexto

    u = sessao_(token, db, secret)
    so_admin_(u, "ler entrevista")

    D = carregar_(db)
    cargos = D["cargos"]

    entrada = entrada or {}
    texto = str(entrada.get("texto") or "").strip()
    link = str(entrada.get("link") or "").strip()

    if not texto and link:
        texto = _baixarTextoDocs_(link)

    if len(texto) < 30:
        raise ErroNegocio("Cole o link do Google Docs da entrevista ou o texto dela.")
    if len(texto) > 60000:
        raise ErroNegocio("Texto grande demais.")

    # Chama o leitor
    r = lerTexto(texto, cargos)
    return r


def _baixarTextoDocs_(link: str) -> str:
    """Extrai o doc_id do link do Google Docs e baixa o texto via export público (?format=txt)."""
    import urllib.request
    import urllib.error

    m = re.search(r"/document/d/([a-zA-Z0-9-_]+)", link)
    if not m:
        raise ErroNegocio("O link precisa ser de um Google Docs, no formato https://docs.google.com/document/d/...")

    doc_id = m.group(1)
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

    try:
        with urllib.request.urlopen(url, timeout=6) as resp:
            return resp.read().decode("utf-8", errors="ignore").strip()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        raise ErroNegocio(
            "Não foi possível acessar o link do Google Docs diretamente. "
            "Por favor, abra o documento, copie o texto inteiro e cole no campo de texto abaixo."
        )


def respostas_(token: str, cargoId: str, db: Session, secret: str) -> list:
    """Port de respostas_ (.gs linha 533): lê a entrevista inteira (respostas)."""
    u = sessao_(token, db, secret)
    so_admin_(u, "ver entrevista completa")

    e = db.query(Entrevista).filter(Entrevista.cargoId == str(cargoId)).first()
    if not e or not e.respostas:
        return []

    try:
        return json.loads(e.respostas)
    except (json.JSONDecodeError, TypeError):
        return []


def salvarEntrevista_(token: str, d: dict, db: Session, secret: str) -> dict:
    """Port de salvarEntrevista_ (.gs linha 474): valida, liga entrevista ao cargo, gravahistórico."""
    u = sessao_(token, db, secret)
    so_admin_(u, "salvar entrevista")

    D = carregar_(db)
    M = modelo_(D)
    d = d or {}
    d["publicar"] = bool(d.get("publicar", False))

    # Valida conteúdo
    cont = validarConteudo(d)

    # Valida link (padrão Google Docs)
    if d.get("link"):
        link = str(d.get("link")).strip()
        if not re.match(r"^https://docs\.google\.com/document/d/[\w-]+", link):
            raise ErroNegocio("O link precisa ser de um Google Docs, no formato https://docs.google.com/document/d/...")

    # A entrevista NUNCA cria cargo: se liga a um cargo que já existe
    cargo_id = str(d.get("cargoId") or "")
    c = M["byId"](cargo_id)
    if not c:
        raise ErroNegocio("Escolha um cargo que já esteja no organograma. Se ele não existe, inclua-o primeiro em \"Editar organograma\".")

    # Dados do cargo (nome, area, pessoa): só mudam se editado à mão nesta tela
    if d.get("cargo") and isinstance(d.get("cargo"), dict):
        cargo_dados = dadosCargo_(d["cargo"])
        if (cargo_dados["nome"] != c["nome"] or
            cargo_dados["area"] != c["area"] or
            cargo_dados["pessoa"] != c["pessoa"]):
            cargo = db.query(Cargo).filter(Cargo.id == c["id"]).first()
            if cargo:
                cargo.nome = cargo_dados["nome"]
                cargo.area = cargo_dados["area"]
                cargo.pessoa = cargo_dados["pessoa"]
                db.add(cargo)
                db.add(Registro(quando=datetime.utcnow(), quem=u["nome"],
                              acao=f"Editou o cargo {c['nome']}" +
                                  (f" → {cargo_dados['nome']}" if cargo_dados["nome"] != c["nome"] else "")))
                db.commit()
                # Recarrega
                D = carregar_(db)
                M = modelo_(D)
                c = M["byId"](cargo_id)

    # Entrevista: acha ou cria ID novo
    e = next((x for x in D["entrevistas"] if x["cargo"] == c["id"]), None)
    eid = e["id"] if e else (max([x["id"] for x in D["entrevistas"]], default=0) + 1)

    # Auto-avaliação (8 elementos, valores 1-5 ou null)
    auto = None
    if isinstance(d.get("auto"), list):
        auto = d["auto"][:8]
        auto = [int(v) if v in [1, 2, 3, 4, 5] else None for v in auto]
    elif e:
        auto = e.get("auto")

    # Grava entrevista
    ent = Entrevista(
        id=eid,
        cargoId=c["id"],
        pessoa=str(d.get("pessoa") or c.get("pessoa") or "").strip()[:80],
        data=str(d.get("data") or "").strip()[:20],
        link=str(d.get("link") or "").strip(),
        auto=json.dumps(auto) if auto else "",
        registradoPor=u["nome"],
        registradoEm=datetime.utcnow(),
        respostas=json.dumps(cont["respostas"]) if cont["respostas"] else ""
    )
    # Merge (UPDATE se existe, INSERT se não)
    if e:
        existing = db.query(Entrevista).filter(Entrevista.id == eid).first()
        if existing:
            existing.pessoa = ent.pessoa
            existing.data = ent.data
            existing.link = ent.link
            existing.auto = ent.auto
            existing.registradoPor = ent.registradoPor
            existing.registradoEm = ent.registradoEm
            existing.respostas = ent.respostas
            db.add(existing)
        else:
            db.add(ent)
    else:
        db.add(ent)

    # Solicitações de mudança (até 20)
    if isinstance(d.get("solicitacoes"), list):
        for s in d["solicitacoes"][:20]:
            novaSolicitacao_(u, D, {
                "cargoId": s.get("cargoId"),
                "origemId": c["id"],
                "texto": s.get("texto"),
                "motivo": s.get("motivo")
            }, db)

    # Revisão e histórico
    rev = (c.get("conteudo", {}) or {}).get("revisao", 0) + 1 if c.get("conteudo") else 0
    if c.get("conteudo"):
        motivo_revisao = str(d.get("motivoRevisao") or "").strip()[:300] or "Atualização do manual"
    else:
        motivo_revisao = "Emissão inicial, a partir de entrevista"
    hist = anotaHistorico_(c.get("conteudo", {}).get("historico", []) if c.get("conteudo") else [], rev, u, motivo_revisao)

    # Grava cargo atualizado
    cargo = db.query(Cargo).filter(Cargo.id == c["id"]).first()
    if cargo:
        cargo.missao = cont["missao"]
        cargo.funcoes = json.dumps(cont["funcoes"])
        cargo.rotinas = json.dumps(cont["rotinas"])
        cargo.jornada = cont["jornada"]
        cargo.tempoEmpresa = cont["tempoEmpresa"]
        cargo.formacao = cont["formacao"]
        cargo.experiencia = cont["experiencia"]
        cargo.habilidades = json.dumps(cont["habilidades"])
        cargo.relacoes = json.dumps(cont["relacoes"])
        cargo.recorre = cont["recorre"]
        cargo.ferramentas = json.dumps(cont["ferramentas"])
        cargo.status = "publicado" if d.get("publicar") else "revisao"
        cargo.entrevistaId = eid
        cargo.revisao = rev
        cargo.historico = json.dumps(hist)
        db.add(cargo)

    db.add(Registro(quando=datetime.utcnow(), quem=u["nome"],
                  acao=(("Publicou" if d.get("publicar") else "Salvou para revisão") +
                        f" o manual: {c['nome']}")))
    db.commit()

    return {"id": c["id"]}


def publicar_(token: str, id: str, ligar: bool, db: Session, secret: str) -> bool:
    """Port de publicar_ (.gs linha 504)."""
    from server.formalizacao import violacoesEstilo, mensagemEstilo

    u = sessao_(token, db, secret)
    so_admin_(u, "publicar manual")

    D = carregar_(db)
    M = modelo_(D)
    c = M["byId"](str(id))

    if not c or not c.get("conteudo"):
        raise ErroNegocio("Esse cargo ainda não tem entrevista.")

    if ligar and not c["conteudo"].get("missao"):
        raise ErroNegocio("Falta a missão deste cargo. Clique em Editar e escreva antes de publicar.")

    if ligar:
        v = violacoesEstilo(c["conteudo"].get("funcoes", []), c["conteudo"].get("rotinas", []))
        if v:
            raise ErroNegocio(mensagemEstilo(v) + " Clique em Editar e use \"Ajustar frases\".")

    cargo = db.query(Cargo).filter(Cargo.id == c["id"]).first()
    if cargo:
        cargo.status = "publicado" if ligar else "revisao"
        db.add(cargo)
        db.add(Registro(quando=datetime.utcnow(), quem=u["nome"],
                      acao=(("Publicou" if ligar else "Tirou do ar") + f" o manual: {c['nome']}")))
        db.commit()

    return True


def salvarCargo_(token: str, d: dict, db: Session, secret: str) -> dict:
    """Port de salvarCargo_ (.gs linha 1063): cria/edita um cargo isolado."""
    u = sessao_(token, db, secret)
    so_admin_(u, "editar cargo")

    D = carregar_(db)
    M = modelo_(D)
    d = d or {}

    dados = dadosCargo_(d)
    cargo_id = str(d.get("id") or "")
    pai = str(d.get("pai") or "")

    # Se é novo, gera ID
    if not cargo_id:
        usados = {c["id"] for c in D["cargos"]}
        cargo_id = novoIdCargo_(dados["nome"], usados)

    # Confere ciclo
    paiDe = {c["id"]: c.get("pai") or "" for c in D["cargos"]}
    if not cargo_id in paiDe:  # Cargo novo
        paiDe[cargo_id] = pai
    else:  # Cargo existente, pode estar mudando pai
        paiDe[cargo_id] = pai

    if pai and fazCiclo_(cargo_id, pai, paiDe):
        raise ErroNegocio("Um cargo não pode ficar abaixo dele mesmo nem de quem está abaixo dele.")

    # Grava/atualiza
    cargo = db.query(Cargo).filter(Cargo.id == cargo_id).first()
    if cargo:
        cargo.nome = dados["nome"]
        cargo.area = dados["area"]
        cargo.pessoa = dados["pessoa"]
        cargo.pai = pai if pai else None
        db.add(cargo)
    else:
        cargo = Cargo(
            id=cargo_id,
            nome=dados["nome"],
            area=dados["area"],
            pessoa=dados["pessoa"],
            pai=pai if pai else None
        )
        db.add(cargo)

    db.add(Registro(quando=datetime.utcnow(), quem=u["nome"], acao=f"Salvou cargo {dados['nome']}"))
    db.commit()

    return {"id": cargo_id}


def excluirCargo_(token: str, id: str, db: Session, secret: str) -> bool:
    """Port de excluirCargo_ (.gs linha 1144): impede excluir com subordinados ou usuário."""
    u = sessao_(token, db, secret)
    so_admin_(u, "excluir cargo")

    D = carregar_(db)
    M = modelo_(D)
    c = M["byId"](str(id))

    if not c:
        raise ErroNegocio("Cargo não encontrado.")

    # Impede excluir se tem subordinados
    subordinados = [x for x in D["cargos"] if x.get("pai") == c["id"]]
    if subordinados:
        raise ErroNegocio(f"Não é possível excluir {c['nome']} enquanto ele tem subordinados.")

    # Impede excluir se tem usuário
    usuarios_ligados = [x for x in D["usuarios"] if x.get("cargo") == c["id"]]
    if usuarios_ligados:
        raise ErroNegocio(f"Não é possível excluir {c['nome']} enquanto há usuário associado.")

    # Remove entrevistas do cargo
    db.query(Entrevista).filter(Entrevista.cargoId == c["id"]).delete()

    # Remove o cargo
    db.query(Cargo).filter(Cargo.id == c["id"]).delete()

    db.add(Registro(quando=datetime.utcnow(), quem=u["nome"], acao=f"Excluiu cargo {c['nome']}"))
    db.commit()

    return True


def salvarUsuario_(token: str, email: str, dados: dict, db: Session, secret: str) -> bool:
    """Port de salvarUsuario_ (.gs linha 515): valida e edita usuário."""
    u = sessao_(token, db, secret)
    so_admin_(u, "editar usuário")

    D = carregar_(db)
    M = modelo_(D)

    email = str(email).lower()
    alvo = db.query(Usuario).filter(Usuario.email == email).first()
    if not alvo:
        raise ErroNegocio("Usuário não encontrado.")

    dados = dados or {}
    perfil = str(dados.get("perfil") or "")
    status = str(dados.get("status") or "")
    cargo_id = str(dados.get("cargo") or "")

    # Valida perfil
    if perfil not in ["admin", "socio", "gestor", "colaborador"]:
        raise ErroNegocio("Perfil inválido.")

    # Valida status
    if status not in ["Ativo", "Pendente", "Inativo"]:
        raise ErroNegocio("Situação inválida.")

    # Se não-admin, exige cargo
    if perfil != "admin" and cargo_id and not M["byId"](cargo_id):
        raise ErroNegocio("Escolha um cargo para este perfil.")

    # Impede remover o último admin ativo
    if (alvo.perfil == "admin" and perfil != "admin" and
        len([x for x in D["usuarios"] if x.get("perfil") == "admin" and x.get("status") == "Ativo"]) < 2):
        raise ErroNegocio("Não é possível remover o último administrador.")

    # Impede a pessoa desativar o próprio acesso
    if alvo.email == u["email"] and status != "Ativo":
        raise ErroNegocio("Você não pode desativar o próprio acesso.")

    # Ao aprovar, limpa pedido de cargo
    alvo.perfil = perfil
    alvo.status = status
    alvo.cargoId = cargo_id if perfil != "admin" else ""
    if status == "Ativo":
        alvo.cargoSolicitado = ""
        alvo.cargoInformado = ""

    db.add(alvo)
    db.add(Registro(quando=datetime.utcnow(), quem=u["nome"],
                  acao=f"Alterou {alvo.nome}: Perfil {perfil}, Status {status}"))
    db.commit()

    return True


def salvarPosicoes_(token: str, d: dict, db: Session, secret: str) -> dict:
    """Port de salvarPosicoes_ (.gs linha 1026): salva posições no organograma."""
    u = sessao_(token, db, secret)
    so_admin_(u, "mover cargos no organograma")

    d = d or {}
    reset = bool(d.get("reset", False))
    posicoes = d.get("posicoes") or []

    if not isinstance(posicoes, list):
        posicoes = []

    if len(posicoes) > 500:
        raise ErroNegocio("Alterações demais de uma vez. Salve em partes.")

    cargos_bd = {c.id: c for c in db.query(Cargo).all()}

    if reset:
        for c in cargos_bd.values():
            c.x = None
            c.y = None
            db.add(c)
    else:
        for p in posicoes:
            p = p or {}
            cargo_id = str(p.get("id") or "")
            x = int(p.get("x") or 0)
            y = int(p.get("y") or 0)

            if cargo_id not in cargos_bd:
                raise ErroNegocio("Cargo não encontrado.")
            if not (-20000 <= x <= 20000) or not (-20000 <= y <= 20000):
                raise ErroNegocio("Posição inválida.")

            c = cargos_bd[cargo_id]
            c.x = x
            c.y = y
            db.add(c)

    db.add(Registro(quando=datetime.utcnow(), quem=u["nome"],
                  acao=f"Salvou {len(posicoes)} posições" + (" (reset)" if reset else "")))
    db.commit()

    return {"n": len(posicoes)}


def importarCargos_(token: str, linhas: list, db: Session, secret: str) -> dict:
    """Port de importarCargos_ (.gs linha 689): importa lista de cargos."""
    u = sessao_(token, db, secret)
    so_admin_(u, "importar organograma")

    if not isinstance(linhas, list) or not linhas:
        raise ErroNegocio("Cole pelo menos um cargo.")
    if len(linhas) > 300:
        raise ErroNegocio("No máximo 300 cargos por vez.")

    D = carregar_(db)
    novos = []
    usados = {c["id"] for c in D["cargos"]}

    # Primeiro passo: valida dados e gera IDs
    for i, l in enumerate(linhas):
        l = l or {}
        dados = dadosCargo_(l, f"Linha {i+1}")
        novo_id = novoIdCargo_(dados["nome"], usados)
        novos.append({
            "id": novo_id,
            **dados,
            "sup": str(l.get("superior") or "").strip()[:80]
        })

    # Segundo passo: resolve superiores (por ID ou por nome)
    todos = ([{"id": c["id"], "nome": c["nome"]} for c in D["cargos"]] +
             [{"id": n["id"], "nome": n["nome"]} for n in novos])

    paiDe = {}
    for n in novos:
        if not n["sup"]:
            n["pai"] = ""
            continue

        sup_norm = _norm_(n["sup"])
        achados = [c for c in todos if c["id"] == n["sup"] or _norm_(c["nome"]) == sup_norm]

        if not achados:
            raise ErroNegocio(f"Linha {linhas.index(next(l for l in linhas if l.get('nome') == n['nome']))+1}: não achei o cargo superior \"{n['sup']}\" ({n['nome']}).")
        if len(achados) > 1:
            raise ErroNegocio(f"Linha {linhas.index(next(l for l in linhas if l.get('nome') == n['nome']))+1}: há mais de um cargo chamado \"{n['sup']}\". Use nomes diferentes.")
        if achados[0]["id"] == n["id"]:
            raise ErroNegocio(f"Linha {linhas.index(next(l for l in linhas if l.get('nome') == n['nome']))+1}: o cargo {n['nome']} não pode responder a ele mesmo.")

        n["pai"] = achados[0]["id"]

    # Terceiro passo: confere ciclos
    for c in D["cargos"]:
        paiDe[c["id"]] = c.get("pai") or ""
    for n in novos:
        paiDe[n["id"]] = n["pai"]

    for n in novos:
        if n["pai"] and fazCiclo_(n["id"], n["pai"], paiDe):
            raise ErroNegocio(f"O cargo {n['nome']} acabou ficando abaixo dele mesmo. Confira a coluna \"Reporta a\".")

    # Quarto passo: grava os novos cargos
    for n in novos:
        cargo = Cargo(
            id=n["id"],
            nome=n["nome"],
            area=n["area"],
            pessoa=n["pessoa"],
            pai=n["pai"] if n["pai"] else None
        )
        db.add(cargo)

    db.add(Registro(quando=datetime.utcnow(), quem=u["nome"], acao=f"Importou {len(novos)} cargos para o organograma"))
    db.commit()

    return {"n": len(novos)}


def novaSolicitacao_(u: dict, D: dict, s: dict, db: Session) -> dict:
    """Port de novaSolicitacao_ (.gs linha 574): cria uma solicitação de mudança."""
    s = s or {}
    cargo_id = str(s.get("cargoId") or "")
    alvo = next((c for c in D["cargos"] if c["id"] == cargo_id), None)

    if not alvo:
        raise ErroNegocio("Escolha o cargo que precisa mudar.")

    texto = str(s.get("texto") or "").strip()[:1000]
    if len(texto) < 5:
        raise ErroNegocio("Descreva o que precisa mudar.")

    id = "S" + uuid.uuid4().hex[:10].upper()

    sol = Solicitacao(
        id=id,
        cargoId=alvo["id"],
        origemId=str(s.get("origemId") or ""),
        texto=texto,
        motivo=str(s.get("motivo") or "").strip()[:600],
        status="Aberta",
        criadoPor=u.get("nome", ""),
        criadoPorEmail=u.get("email", "").lower(),
        criadoEm=datetime.utcnow()
    )
    db.add(sol)
    db.add(Registro(quando=datetime.utcnow(), quem=u.get("nome", ""),
                  acao=f"Abriu solicitação de mudança para {alvo['nome']}"))
    db.commit()

    return {"id": id}


def solicitar_(token: str, d: dict, db: Session, secret: str) -> dict:
    """Port de solicitar_ (.gs linha 585): cria solicitação."""
    u = sessao_(token, db, secret)
    D = carregar_(db)
    M = modelo_(D)
    d = d or {}

    # Acesso: só admin ou quem vê o cargo
    cargo_id = str(d.get("cargoId") or "")
    if u.get("perfil") != "admin" and cargo_id not in M["scope"](u):
        raise ErroNegocio("NEGADO")

    return novaSolicitacao_(u, D, d, db)


def resolverSolicitacao_(token: str, id: str, status: str, resposta: str, db: Session, secret: str) -> bool:
    """Port de resolverSolicitacao_ (.gs linha 590)."""
    u = sessao_(token, db, secret)
    so_admin_(u, "resolver solicitação")

    if status not in ["Aberta", "Concluída", "Recusada"]:
        raise ErroNegocio("Situação inválida.")

    D = carregar_(db)
    s = next((x for x in D["solicitacoes"] if x["id"] == str(id)), None)

    if not s:
        raise ErroNegocio("Solicitação não encontrada.")

    fecha = status != "Aberta"

    sol = db.query(Solicitacao).filter(Solicitacao.id == s["id"]).first()
    if sol:
        sol.status = status
        sol.resposta = str(resposta or "").strip()[:600]
        if fecha:
            sol.resolvidoPor = u["nome"]
            sol.resolvidoEm = datetime.utcnow()
        db.add(sol)

    # Se concluída, anota no histórico do cargo
    if status == "Concluída":
        alvo = next((c for c in D["cargos"] if c["id"] == s["cargoId"]), None)
        if alvo and alvo.get("conteudo"):
            cargo = db.query(Cargo).filter(Cargo.id == alvo["id"]).first()
            if cargo:
                hist = json.loads(cargo.historico or "[]")
                hist = anotaHistorico_(hist, alvo["conteudo"].get("revisao", 0), u,
                                      f"Solicitação concluída: {s['texto'][:200]}")
                cargo.historico = json.dumps(hist)
                db.add(cargo)

    db.add(Registro(quando=datetime.utcnow(), quem=u["nome"],
                  acao=f"Resolveu solicitação: {status}"))
    db.commit()

    return True


def pedirCorrecaoCargo_(token: str, d: dict, db: Session, secret: str) -> dict:
    """Port de pedirCorrecaoCargo_ (.gs linha 622): não-admin pede correção de cargo."""
    u = sessao_(token, db, secret)
    d = d or {}

    if u.get("perfil") == "admin":
        raise ErroNegocio("O administrador não pede correção de cargo. Os cargos são ajustados em Usuários.")

    D = carregar_(db)
    M = modelo_(D)

    motivo = str(d.get("motivo") or "").strip()[:600]
    if len(motivo) < 10:
        raise ErroNegocio("Descreva o motivo com pelo menos 10 caracteres.")

    nao_lista = bool(d.get("naoEstaNaLista", False))
    sugerido = "" if nao_lista else str(d.get("cargoSugerido") or "")

    if not nao_lista and not sugerido:
        raise ErroNegocio("Escolha o seu cargo correto na lista, ou marque que ele não está na lista.")

    if sugerido and not M["byId"](sugerido):
        raise ErroNegocio("O cargo escolhido não existe mais. Atualize a página e escolha de novo.")

    if sugerido and sugerido == (u.get("cargo") or ""):
        raise ErroNegocio("O cargo escolhido já é o seu cargo atual.")

    # Impede mais de um pedido aberto por vez
    abertos = [x for x in D["solicitacoes"] if
               x.get("tipo") == "correcao-cargo" and
               x.get("status") == "Aberta" and
               x.get("criadoPorEmail") == u.get("email")]
    if abertos:
        raise ErroNegocio("Você já tem um pedido aguardando análise. Aguarde a resposta do administrador antes de enviar outro.")

    atual = M["byId"](u.get("cargo")) if u.get("cargo") else None
    alvo = M["byId"](sugerido) if sugerido else None

    id = "C" + uuid.uuid4().hex[:10].upper()

    sol = Solicitacao(
        id=id,
        tipo="correcao-cargo",
        cargoId=u.get("cargo") or "",
        cargoSugerido=sugerido,
        origemId="",
        texto=f"Correção de cargo: de {atual['nome'] if atual else 'sem cargo'} para {alvo['nome'] if alvo else 'um cargo que não está na lista'}",
        motivo=motivo,
        status="Aberta",
        criadoPor=u.get("nome", ""),
        criadoPorEmail=u.get("email", "").lower(),
        criadoEm=datetime.utcnow()
    )
    db.add(sol)
    db.add(Registro(quando=datetime.utcnow(), quem=u.get("nome", ""),
                  acao="Pediu correção de cargo"))
    db.commit()

    return {"id": id}


def resolverCorrecaoCargo_(token: str, id: str, decisao: str, resposta: str, cargoId: str, db: Session, secret: str) -> bool:
    """Port de resolverCorrecaoCargo_ (.gs linha 641): admin aprova/recusa pedido de cargo."""
    u = sessao_(token, db, secret)
    so_admin_(u, "resolver pedido de cargo")

    D = carregar_(db)
    M = modelo_(D)

    # Acha o pedido de correção
    s = next((x for x in D["solicitacoes"] if
              x.get("tipo") == "correcao-cargo" and
              x.get("id") == str(id)), None)

    if not s:
        raise ErroNegocio("Pedido não encontrado.")

    if s.get("status") != "Aberta":
        raise ErroNegocio("Este pedido já foi respondido.")

    decisao = str(decisao or "").strip()
    resposta = str(resposta or "").strip()[:600]

    if decisao not in ["Aprovada", "Recusada"]:
        raise ErroNegocio("Escolha aprovar ou recusar o pedido.")

    if decisao == "Recusada":
        if len(resposta) < 5:
            raise ErroNegocio("Escreva a resposta ao solicitante, com pelo menos 5 caracteres.")
    else:
        # Aprovada: troca o cargo do usuário
        alvo_usuario = next((x for x in D["usuarios"] if x.get("email") == s.get("criadoPorEmail")), None)
        if not alvo_usuario:
            raise ErroNegocio("O usuário deste pedido não existe mais.")

        if alvo_usuario.get("perfil") == "admin":
            raise ErroNegocio("Este usuário é administrador e não tem cargo.")

        novo_cargo = s.get("cargoSugerido") or str(cargoId or "")
        if not novo_cargo:
            raise ErroNegocio("Escolha o cargo que será aplicado.")

        if not M["byId"](novo_cargo):
            raise ErroNegocio("O cargo escolhido não existe.")

        # Atualiza usuário
        usuario = db.query(Usuario).filter(Usuario.email == alvo_usuario["email"]).first()
        if usuario:
            usuario.cargoId = novo_cargo
            db.add(usuario)
            db.add(Registro(quando=datetime.utcnow(), quem=u["nome"],
                          acao=f"Aprovou correção de cargo de {usuario.nome}: {M['byId'](novo_cargo)['nome']}"))

    # Atualiza solicitação
    sol = db.query(Solicitacao).filter(Solicitacao.id == s["id"]).first()
    if sol:
        sol.status = decisao
        sol.resposta = resposta if decisao == "Recusada" else (resposta or "Cargo atualizado.")
        sol.resolvidoPor = u["nome"]
        sol.resolvidoEm = datetime.utcnow()
        db.add(sol)

        if decisao == "Recusada":
            db.add(Registro(quando=datetime.utcnow(), quem=u["nome"],
                          acao=f"Recusou correção de cargo de {s['criadoPor']}"))

    db.commit()

    return True


def meusPedidosDe_(D: dict, M: dict, email: str) -> list:
    """Port de meusPedidosDe_ (.gs linha 614): os pedidos de uma pessoa."""
    email = str(email).lower()
    pedidos = [x for x in D["solicitacoes"] if
               x.get("tipo") == "correcao-cargo" and
               x.get("criadoPorEmail") == email]

    result = []
    for x in reversed(pedidos):
        atual = M["byId"](x.get("cargoId")) if x.get("cargoId") else None
        sug = M["byId"](x.get("cargoSugerido")) if x.get("cargoSugerido") else None

        result.append({
            "id": x["id"],
            "status": x.get("status", ""),
            "motivo": x.get("motivo", ""),
            "resposta": x.get("resposta", ""),
            "criadoEm": x.get("criadoEm", ""),
            "resolvidoEm": x.get("resolvidoEm", ""),
            "resolvidoPor": x.get("resolvidoPor", ""),
            "nome": x.get("criadoPor", ""),
            "cargoAtualNome": f"{atual['nome']} · {atual['area']}" if atual else "Sem cargo",
            "cargoSugerido": x.get("cargoSugerido", "") or "",
            "cargoSugeridoNome": (f"{sug['nome']} · {sug['area']}" if sug else "Cargo excluído") if x.get("cargoSugerido") else "Meu cargo não está na lista"
        })

    return result


# API Wrappers
def api_login(email: str, senha: str, db: Session, secret: str) -> dict:
    """Login com snapshot."""
    from server.auth import login_
    r = login_(email, senha, db, secret)
    D = carregar_(db)
    return {
        "token": r["token"],
        "trocar": r["trocar"],
        "snap": retrato_(D, r["u"])
    }


def api_snapshot(token: str, db: Session, secret: str) -> dict:
    """Retorna retrato do usuário atual."""
    u = sessao_(token, db, secret)
    D = carregar_(db)
    return retrato_(D, u)


def api_primeiroAcesso(d: dict, db: Session) -> dict:
    """Primeiro acesso."""
    from server.auth import primeiro_acesso_
    return primeiro_acesso_(d, db)


def api_cargosPublicos(db: Session) -> list:
    """Lista cargos públicos."""
    cargos = db.query(Cargo).all()
    result = [{"id": c.id, "nome": c.nome, "area": c.area} for c in cargos]
    result.sort(key=lambda c: (c["area"], c["nome"]))
    return result


def api_logout(token: str, db: Session, secret: str) -> bool:
    """Logout (invalida sessão em token stateless - sem ação necessária)."""
    return True


def api_trocarSenha(token: str, atual: str, nova: str, db: Session, secret: str) -> bool:
    """Troca de senha do usuário."""
    from server.auth import trocar_senha_
    return trocar_senha_(token, atual, nova, db, secret)


def api_redefinirSenha(token: str, email: str, db: Session, secret: str) -> dict:
    """Redefine senha de um usuário (admin only)."""
    from server.auth import redefinir_senha_
    return redefinir_senha_(token, email, db, secret)


def api_lerEntrevista(token: str, entrada: dict, db: Session, secret: str) -> dict:
    """Lê e processa texto de entrevista."""
    return lerEntrevista_(token, entrada, db, secret)


def api_respostas(token: str, cargoId: str, db: Session, secret: str) -> list:
    """Retorna respostas da entrevista de um cargo."""
    return respostas_(token, cargoId, db, secret)


def api_salvarEntrevista(token: str, d: dict, db: Session, secret: str) -> dict:
    """Salva/atualiza entrevista de um cargo."""
    return salvarEntrevista_(token, d, db, secret)


def api_novaEntrevista(token: str, d: dict, db: Session, secret: str) -> dict:
    """STUB: Cria novo documento de entrevista."""
    raise ErroNegocio("Disponível só pelo texto colado nesta versão.")


def api_publicar(token: str, id: str, ligar: bool, db: Session, secret: str) -> bool:
    """Publica ou tira do ar um manual."""
    return publicar_(token, id, ligar, db, secret)


def api_salvarCargo(token: str, d: dict, db: Session, secret: str) -> dict:
    """Salva um cargo novo ou existente."""
    return salvarCargo_(token, d, db, secret)


def api_excluirCargo(token: str, id: str, db: Session, secret: str) -> bool:
    """Exclui um cargo."""
    return excluirCargo_(token, id, db, secret)


def api_salvarUsuario(token: str, email: str, dados: dict, db: Session, secret: str) -> bool:
    """Edita um usuário."""
    return salvarUsuario_(token, email, dados, db, secret)


def api_salvarPosicoes(token: str, d: dict, db: Session, secret: str) -> dict:
    """Salva posições de cargos no organograma."""
    return salvarPosicoes_(token, d, db, secret)


def api_definirSuperior(token: str, id: str, pai: str, db: Session, secret: str) -> bool:
    """Define o superior de um cargo."""
    return definirSuperior_(token, id, pai, db, secret)


def api_salvarCargos(token: str, lista: list, db: Session, secret: str) -> dict:
    """Salva batch de cargos."""
    return salvarCargos_(token, lista, db, secret)


def api_salvarOrganograma(token: str, d: dict, db: Session, secret: str) -> dict:
    """Salva organograma (posições + ligações)."""
    return salvarOrganograma_(token, d, db, secret)


def api_importarCargos(token: str, linhas: list, db: Session, secret: str) -> dict:
    """Importa lista de cargos."""
    return importarCargos_(token, linhas, db, secret)


def api_solicitar(token: str, d: dict, db: Session, secret: str) -> dict:
    """Cria solicitação de mudança."""
    return solicitar_(token, d, db, secret)


def api_resolverSolicitacao(token: str, id: str, status: str, resposta: str, db: Session, secret: str) -> bool:
    """Resolve uma solicitação."""
    return resolverSolicitacao_(token, id, status, resposta, db, secret)


def api_pedirCorrecaoCargo(token: str, d: dict, db: Session, secret: str) -> dict:
    """Não-admin pede correção de cargo."""
    return pedirCorrecaoCargo_(token, d, db, secret)


def api_meusPedidos(token: str, db: Session, secret: str) -> list:
    """Retorna pedidos de correção de cargo da pessoa."""
    u = sessao_(token, db, secret)
    D = carregar_(db)
    M = modelo_(D)
    return meusPedidosDe_(D, M, u["email"])


def api_resolverCorrecaoCargo(token: str, id: str, decisao: str, resposta: str, cargoId: str, db: Session, secret: str) -> bool:
    """Admin resolve pedido de correção de cargo."""
    return resolverCorrecaoCargo_(token, id, decisao, resposta, cargoId, db, secret)


def api_visualizarComo(token: str, d: dict, db: Session, secret: str) -> dict:
    """STUB: Visualiza retrato como outro perfil."""
    from server.handlers_tobe import visualizarComo_
    u = sessao_(token, db, secret)
    so_admin_(u, "visualizar como")
    return visualizarComo_(d or {}, db)
