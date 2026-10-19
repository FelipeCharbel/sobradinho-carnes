"""
O coração das regras de acesso. Ver docs/CONTRATOS.md §7 para os pontos que o Coordenador vai
conferir linha a linha contra o Codigo.gs. NÃO resumir a lógica — portar função por função.
"""
import json
import copy
from sqlalchemy.orm import Session
from server.models import Cargo, Entrevista, Solicitacao, Usuario

SIGLA = "SC"
AUTO = ["Carga de trabalho", "Capacitação", "Clareza do que se espera do cargo", "Motivação",
        "Ferramentas e recursos", "Reconhecimento", "Abertura para sugestões", "Satisfação geral"]
PERFIS = {
    "admin": {"nome": "Administrador", "desc": "Equipe Grupo Gestão. Vê e administra tudo, inclusive rascunhos."},
    "socio": {"nome": "Sócio", "desc": "Vê todos os cargos da empresa, somente com manuais publicados."},
    "gestor": {"nome": "Gestor", "desc": "Vê o próprio cargo e tudo abaixo dele no organograma."},
    "colaborador": {"nome": "Colaborador", "desc": "Vê o próprio cargo e os colegas do mesmo nível na mesma área."}
}
TIPO_CORRECAO_ = "correcao-cargo"


def _J_(s, padrao=None):
    """Helper: json.loads com fallback para padrão."""
    try:
        return json.loads(s) if s else padrao
    except (json.JSONDecodeError, TypeError):
        return padrao


def _norm_(s):
    """Normalization: NFD + remove accents, lowercase."""
    import unicodedata
    s = str(s or "").lower().strip()
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("utf-8")


def _slug_(s):
    """Slug: normalizar e remover caracteres especiais."""
    s = _norm_(s).replace(" ", "-")
    s = "".join(c if c.isalnum() or c == "-" else "" for c in s)
    s = s.replace("--", "-").strip("-")
    return s[:24] if s else "cargo"


def _nivelDe_(cargo, por):
    """Nível (1 = topo) contando superiores."""
    n = 1
    p = por.get(cargo.get("pai")) if cargo.get("pai") else None
    while p and n < 30:
        n += 1
        p = por.get(p.get("pai")) if p.get("pai") else None
    return n


def _codigoDe_(lista, cargo):
    """Port de codigoDe_ (.gs linha 192): código do cargo (SC-RHU-01), ordem dentro da área."""
    ar = "".join(c for c in _norm_(cargo.get("area", "")) if c.isalpha()).upper()[:3]
    idx = [c for c in lista if c.get("area") == cargo.get("area")].index(cargo) + 1
    return f"{SIGLA}-{ar}-{str(idx).zfill(2)}"


def carregar_(db: Session) -> dict:
    """Port de carregar_ (.gs linha 201)."""
    # Carrega cargos
    rows = db.query(Cargo).all()
    cargos = []
    por = {}
    for r in rows:
        c = {
            "id": r.id,
            "nome": r.nome,
            "area": r.area,
            "pai": r.pai if r.pai else None,
            "pessoa": r.pessoa,
            "x": r.x,
            "y": r.y
        }
        if r.status:
            c["conteudo"] = {
                "missao": r.missao or "",
                "funcoes": _J_(r.funcoes, []),
                "rotinas": _J_(r.rotinas, []),
                "jornada": r.jornada or "",
                "tempoEmpresa": r.tempoEmpresa or "",
                "formacao": r.formacao or "",
                "experiencia": r.experiencia or "",
                "habilidades": _J_(r.habilidades, []),
                "relacoes": _J_(r.relacoes, []),
                "recorre": r.recorre or "",
                "ferramentas": _J_(r.ferramentas, []),
                "status": r.status,
                "entrevistaId": r.entrevistaId,
                "revisao": r.revisao or 0,
                "historico": _J_(r.historico, [])
            }
        else:
            c["conteudo"] = None
        cargos.append(c)
        por[c["id"]] = c

    # Calcula nível
    for c in cargos:
        c["nivel"] = _nivelDe_(c, por)

    # Carrega entrevistas
    entrevistas = []
    for e in db.query(Entrevista).all():
        entrevistas.append({
            "id": e.id,
            "cargo": e.cargoId,
            "pessoa": e.pessoa,
            "data": e.data or "",
            "link": e.link or "",
            "auto": _J_(e.auto, None),
            "temRespostas": bool(e.respostas)
        })

    # Carrega solicitações
    solicitacoes = []
    for s in db.query(Solicitacao).all():
        solicitacoes.append({
            "id": s.id,
            "cargoId": s.cargoId,
            "origemId": s.origemId or "",
            "texto": s.texto or "",
            "motivo": s.motivo or "",
            "status": s.status or "Aberta",
            "criadoPor": s.criadoPor or "",
            "criadoPorEmail": (s.criadoPorEmail or "").lower(),
            "criadoEm": s.criadoEm.isoformat() if s.criadoEm else "",
            "resolvidoPor": s.resolvidoPor or "",
            "resolvidoEm": s.resolvidoEm.isoformat() if s.resolvidoEm else "",
            "resposta": s.resposta or "",
            "tipo": s.tipo or "",
            "cargoSugerido": s.cargoSugerido or ""
        })

    # Carrega usuários
    usuarios = []
    for u in db.query(Usuario).all():
        usuarios.append({
            "email": u.email.lower(),
            "nome": u.nome,
            "perfil": u.perfil,
            "cargo": u.cargoId,
            "cargoInformado": u.cargoInformado or "",
            "cargoSolicitado": u.cargoSolicitado,
            "status": u.status,
            "salt": u.salt,
            "hash": u.hash
        })

    return {
        "cargos": cargos,
        "entrevistas": entrevistas,
        "solicitacoes": solicitacoes,
        "usuarios": usuarios
    }


def modelo_(D: dict) -> dict:
    """Port de modelo_ (.gs linha 286)."""
    def byId(id):
        for c in D["cargos"]:
            if c["id"] == id:
                return c
        return None

    def desc(id):
        """IDs de todos os descendentes diretos e indiretos."""
        result = []
        for c in D["cargos"]:
            if c["pai"] == id:
                result.append(c["id"])
                result.extend(desc(c["id"]))
        return result

    def scope(u):
        """Set de IDs visíveis para o usuário."""
        if not u or u.get("status") != "Ativo":
            return set()
        if u.get("perfil") in ("admin", "socio"):
            return set(c["id"] for c in D["cargos"])
        meu = byId(u.get("cargo"))
        if not meu:
            return set()
        if u.get("perfil") == "gestor":
            return set([meu["id"]] + desc(meu["id"]))
        if u.get("perfil") == "colaborador":
            return set(c["id"] for c in D["cargos"] if c.get("area") == meu.get("area") and c.get("nivel") == meu.get("nivel"))
        return set()

    def estadoReal(c):
        return "sem" if not c.get("conteudo") else c["conteudo"].get("status", "sem")

    def estadoPublico(c):
        return "publicado" if estadoReal(c) == "publicado" else "construcao"

    def estadoVisto(c, u):
        return estadoReal(c) if u.get("perfil") == "admin" else estadoPublico(c)

    def mostra(c, u):
        if not c.get("conteudo"):
            return False
        return u.get("perfil") == "admin" or c["conteudo"].get("status") == "publicado"

    def codigoDe(c):
        return _codigoDe_(D["cargos"], c)

    def posicaoDe(c):
        superior = None
        if c.get("pai"):
            p = byId(c["pai"])
            if p:
                superior = {"id": p["id"], "nome": p["nome"], "pessoa": p["pessoa"]}
        subordinados = [{"id": x["id"], "nome": x["nome"], "pessoa": x["pessoa"]}
                       for x in D["cargos"] if x.get("pai") == c["id"]]
        return {
            "codigo": codigoDe(c),
            "superior": superior,
            "temSuperior": bool(c.get("pai")),
            "subordinados": subordinados
        }

    def manual_(c, u):
        m = copy.deepcopy(c["conteudo"]) if c.get("conteudo") else {}
        if u.get("perfil") != "admin":
            m.pop("entrevistaId", None)
            m.pop("historico", None)
        return m

    def ficha(u, c, s):
        e = None
        for ent in D["entrevistas"]:
            if ent["cargo"] == c["id"]:
                e = ent
                break
        ve = c["id"] in s
        base = {
            "id": c["id"],
            "nome": c["nome"],
            "area": c["area"],
            "nivel": c["nivel"],
            "pessoa": c["pessoa"],
            **posicaoDe(c)
        }
        if not ve:
            return {**base, "estado": estadoPublico(c), "conteudo": None, "restrito": True}
        f = {**base, "estado": estadoVisto(c, u), "conteudo": manual_(c, u) if mostra(c, u) else None, "restrito": False}
        if u.get("perfil") == "admin":
            f["dataEntrevista"] = e["data"] if e else ""
            f["entrevista"] = copy.deepcopy(e) if e else None
        return f

    def media(l):
        v = [x for x in l if x]
        return round(sum(v) / len(v) * 10) / 10 if v else None

    def diagnostico(u, area):
        todas = [e for e in D["entrevistas"] if isinstance(e.get("auto"), list) and any(e["auto"])]
        def _byId(id):
            return byId(id)
        cargo_de = lambda e: _byId(e["cargo"])
        def do_area(a):
            return [e for e in todas if cargo_de(e) and cargo_de(e).get("area") == a]
        MIN = 3
        areas = []
        for a in set(c.get("area") for c in D["cargos"]):
            areas.append({"area": a, "n": len(do_area(a)), "total": len([e for e in D["entrevistas"] if cargo_de(e) and cargo_de(e).get("area") == a])})
        filtro = area if area and any(x["area"] == area for x in areas) else ""
        resp = do_area(filtro) if filtro else todas
        n = len(resp)
        liberado = u.get("perfil") == "admin" or n >= MIN
        itens = []
        for i, nome in enumerate(AUTO):
            m = media([e["auto"][i] for e in resp]) if liberado else None
            itens.append({"nome": nome, "media": m, "invertido": i == 0})
        comparativo = []
        if not filtro:
            for a in areas:
                if a["n"] and (u.get("perfil") == "admin" or a["n"] >= MIN):
                    comparativo.append({
                        "area": a["area"],
                        "n": a["n"],
                        "satisfacao": media([e["auto"][7] for e in do_area(a["area"])]),
                        "sobrecarga": media([e["auto"][0] for e in do_area(a["area"])])
                    })
        return {"area": filtro, "areas": [a for a in areas if a["total"]], "n": n, "total": (areas[next(i for i, a in enumerate(areas) if a["area"] == filtro)]["total"] if filtro else len(D["entrevistas"])) if filtro else len(D["entrevistas"]), "min": MIN, "liberado": liberado, "itens": itens, "comparativo": comparativo}

    def diagnosticoAgregado(area):
        todas = [e for e in D["entrevistas"] if isinstance(e.get("auto"), list) and any(e["auto"])]
        def _byId(id):
            return byId(id)
        cargo_de = lambda e: _byId(e["cargo"])
        def do_area(a):
            return [e for e in todas if cargo_de(e) and cargo_de(e).get("area") == a]
        MIN = 3
        areas = list(set(c.get("area") for c in D["cargos"]))
        filtro = area if area in areas else ""
        resp = do_area(filtro) if filtro else todas
        n = len(resp)
        liberado = n >= MIN
        itens = []
        for i, nome in enumerate(AUTO):
            m = media([e["auto"][i] for e in resp]) if liberado else None
            itens.append({"nome": nome, "media": m, "invertido": i == 0})
        comparativo = []
        for a in areas:
            if len(do_area(a)) >= MIN:
                comparativo.append({"area": a, "n": len(do_area(a)), "satisfacao": media([e["auto"][7] for e in do_area(a)]), "sobrecarga": media([e["auto"][0] for e in do_area(a)])})
        return {"agregado": True, "area": filtro, "areas": [{"area": a, "poucos": True} if len(do_area(a)) < MIN else {"area": a} for a in areas], "n": n if liberado else None, "min": MIN, "liberado": liberado, "poucos": not liberado, "itens": itens, "comparativo": comparativo}

    return {
        "byId": byId,
        "scope": scope,
        "estadoReal": estadoReal,
        "estadoPublico": estadoPublico,
        "estadoVisto": estadoVisto,
        "mostra": mostra,
        "codigoDe": codigoDe,
        "posicaoDe": posicaoDe,
        "ficha": ficha,
        "diagnostico": diagnostico,
        "diagnosticoAgregado": diagnosticoAgregado
    }


def retrato_(D: dict, u: dict) -> dict:
    """Port de retrato_ (.gs linha 341)."""
    M = modelo_(D)
    s = M["scope"](u)
    admin = u.get("perfil") == "admin"
    meu_cargo = M["byId"](u.get("cargo")) if u.get("cargo") else None

    visiveis = [c for c in D["cargos"] if c["id"] in s]
    resumo = {
        "total": len(visiveis),
        "publicado": len([c for c in visiveis if M["estadoReal"](c) == "publicado"])
    }

    if admin:
        resumo["revisao"] = len([c for c in visiveis if M["estadoReal"](c) == "revisao"])
        resumo["sem"] = len([c for c in visiveis if M["estadoReal"](c) == "sem"])
        resumo["pendentes"] = len([u2 for u2 in D["usuarios"] if u2["status"] == "Pendente"])
        resumo["semLista"] = [{"id": c["id"], "nome": c["nome"]} for c in visiveis if M["estadoReal"](c) == "sem"]

    fichas = {}
    for c in D["cargos"]:
        fichas[c["id"]] = M["ficha"](u, c, s)

    out = {
        "me": {
            "nome": u["nome"],
            "perfil": u["perfil"],
            "perfilNome": PERFIS.get(u["perfil"], {}).get("nome", ""),
            "regra": PERFIS.get(u["perfil"], {}).get("desc", ""),
            "cargo": u.get("cargo"),
            "cargoNome": meu_cargo["nome"] if meu_cargo else None,
            "area": meu_cargo.get("area") if meu_cargo else None,
            "nVisiveis": len(s),
            "nTotal": len(D["cargos"]),
            "admin": admin
        },
        "estrutura": [
            {
                "id": c["id"],
                "nome": c["nome"],
                "area": c["area"],
                "nivel": c["nivel"],
                "pai": c["pai"],
                "pessoa": c["pessoa"],
                "x": c["x"],
                "y": c["y"],
                "codigo": M["codigoDe"](c),
                "estado": M["estadoVisto"](c, u) if c["id"] in s else M["estadoPublico"](c),
                "acesso": c["id"] in s
            }
            for c in D["cargos"]
        ],
        "fichas": fichas,
        "ordem": [c["id"] for c in sorted(D["cargos"], key=lambda c: (c["nivel"], c["area"]))],
        "resumo": resumo,
        "solicitacoes": [
            {**x, "criadoPorEmail": None, "cargoNome": M["byId"](x["cargoId"]).get("nome", "Cargo excluído"), "origemNome": (M["byId"](x["origemId"]).get("nome", "") if x.get("origemId") else "")}
            for x in D["solicitacoes"] if x["tipo"] != TIPO_CORRECAO_ and (admin or x["criadoPorEmail"] == u["email"])
        ][::-1],
        "meusPedidos": meusPedidosDe_(D, M, u["email"])
    }

    if admin:
        out["pedidosCargo"] = pedidosAdmin_(D, M)

    if admin:
        out["entrevistas"] = []
        for e in D["entrevistas"]:
            c = M["byId"](e["cargo"])
            if c:
                out["entrevistas"].append({**e, "cargoNome": c["nome"], "area": c["area"], "estado": M["estadoReal"](c)})
        out["perfis"] = [{"k": k, "nome": v["nome"], "desc": v["desc"]} for k, v in PERFIS.items()]
        out["usuarios"] = []
        for uu in D["usuarios"]:
            adm = uu["perfil"] == "admin"
            cs = uu.get("cargoSolicitado") if not adm else None
            sol = M["byId"](cs) if cs else None
            out["usuarios"].append({
                "email": uu["email"],
                "nome": uu["nome"],
                "perfil": uu["perfil"],
                "cargo": uu["cargo"],
                "cargoInformado": "" if adm else uu.get("cargoInformado", ""),
                "cargoSolicitado": cs,
                "cargoSolicitadoNome": (sol["nome"] + " · " + sol["area"] if sol else ""),
                "status": uu["status"],
                "cargoNome": (M["byId"](uu["cargo"]).get("nome", "—") if uu["cargo"] else "—"),
                "ve": len(M["scope"]({**uu, "status": "Ativo"}))
            })
        out["registro"] = []  # Implementar se necessário para testes

    if u.get("perfil") == "admin":
        out["diag"] = {"": M["diagnostico"](u, "")}
        for area in set(c["area"] for c in D["cargos"]):
            out["diag"][area] = M["diagnostico"](u, area)
        out["opcoesAreas"] = True
    elif u.get("perfil") == "socio":
        out["diag"] = {"": M["diagnosticoAgregado"]("")}
        for area in set(c["area"] for c in D["cargos"]):
            out["diag"][area] = M["diagnosticoAgregado"](area)
        out["opcoesAreas"] = True

    return out


def meusPedidosDe_(D: dict, M: dict, email: str) -> list:
    """Port de meusPedidosDe_ (.gs linha 614)."""
    def pedido_vista(x):
        atual = M["byId"](x["cargoId"]) if x.get("cargoId") else None
        sug = M["byId"](x.get("cargoSugerido")) if x.get("cargoSugerido") else None
        return {
            "id": x["id"],
            "status": x["status"],
            "motivo": x["motivo"],
            "resposta": x["resposta"],
            "criadoEm": x["criadoEm"],
            "resolvidoEm": x["resolvidoEm"],
            "resolvidoPor": x["resolvidoPor"],
            "nome": x["criadoPor"],
            "cargoAtualNome": (atual["nome"] + " · " + atual["area"] if atual else "Sem cargo"),
            "cargoSugerido": x.get("cargoSugerido") or "",
            "cargoSugeridoNome": ((sug["nome"] + " · " + sug["area"] if sug else "Cargo excluído") if x.get("cargoSugerido") else "Meu cargo não está na lista")
        }
    result = [pedido_vista(x) for x in D["solicitacoes"] if x["tipo"] == TIPO_CORRECAO_ and x["criadoPorEmail"] == email]
    for p in result:
        p.pop("email", None)
    return result[::-1]


def pedidosAdmin_(D: dict, M: dict) -> list:
    """Port de pedidosAdmin_ (.gs linha 618)."""
    def pedido_vista(x):
        atual = M["byId"](x["cargoId"]) if x.get("cargoId") else None
        sug = M["byId"](x.get("cargoSugerido")) if x.get("cargoSugerido") else None
        return {
            "id": x["id"],
            "status": x["status"],
            "motivo": x["motivo"],
            "resposta": x["resposta"],
            "criadoEm": x["criadoEm"],
            "resolvidoEm": x["resolvidoEm"],
            "resolvidoPor": x["resolvidoPor"],
            "nome": x["criadoPor"],
            "email": x["criadoPorEmail"],
            "cargoAtualNome": (atual["nome"] + " · " + atual["area"] if atual else "Sem cargo"),
            "cargoSugerido": x.get("cargoSugerido") or "",
            "cargoSugeridoNome": ((sug["nome"] + " · " + sug["area"] if sug else "Cargo excluído") if x.get("cargoSugerido") else "Meu cargo não está na lista")
        }
    vistos = [pedido_vista(x) for x in D["solicitacoes"] if x["tipo"] == TIPO_CORRECAO_]
    vistos = vistos[::-1]
    return [p for p in vistos if p["status"] == "Aberta"] + [p for p in vistos if p["status"] != "Aberta"][:20]
