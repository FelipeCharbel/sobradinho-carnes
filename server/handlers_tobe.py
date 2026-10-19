"""
TO BE (organograma futuro) handlers. Implementação completa do bloco TO BE.
Lógica: AS IS (Cargos) é oficial; TO BE (Tobe) começa como cópia e acompanha mudanças,
exceto campos personalizados (que viram conflitos).
"""
import json
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from server.models import Tobe, TobeHistorico, TobeVersao, Cargo, Entrevista, Usuario
from server.auth import ErroNegocio, sessao_, so_admin_
from server.modelo import carregar_, modelo_


# Constantes (do .gs linhas 719-724)
CONTEUDO_ = ["missao", "funcoes", "rotinas", "jornada", "tempoEmpresa", "formacao",
             "experiencia", "habilidades", "relacoes", "recorre", "ferramentas"]
SYNC_CAMPOS_ = ["nome", "area", "pai", "pessoa", "x", "y"] + CONTEUDO_
LISTAS_ = ["funcoes", "rotinas", "habilidades", "relacoes", "ferramentas"]
ROTULO_ = {
    "nome": "Nome", "area": "Área", "pai": "Superior", "pessoa": "Ocupante",
    "x": "Posição", "y": "Posição", "missao": "Missão", "funcoes": "Funções",
    "rotinas": "Rotinas", "jornada": "Jornada", "tempoEmpresa": "Tempo de empresa",
    "formacao": "Formação", "experiencia": "Experiência", "habilidades": "Habilidades",
    "relacoes": "Relações", "recorre": "Recorre a", "ferramentas": "Ferramentas"
}


def _J_(s, padrao=None):
    """Helper: json.loads com fallback para padrão."""
    try:
        return json.loads(s) if s else padrao
    except (json.JSONDecodeError, TypeError):
        return padrao


def _texto(v, maxlen: int) -> str:
    """Port de texto_ (.gs linha 179)."""
    return str(v or "").strip()[:maxlen]


def _mesmo(a, b) -> bool:
    """Port de mesmo_ (.gs linha 725): igualdade por serialização JSON."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _texto_valor(v) -> str:
    """Port de textoValor_ (.gs linha 753)."""
    if v is None:
        return ""
    if isinstance(v, list):
        partes = []
        for x in v:
            if isinstance(x, dict):
                vals = [str(x.get("f")) if x.get("f") else None, str(x.get("t")) if x.get("t") else None]
                partes.append(": ".join(val for val in vals if val))
            else:
                partes.append(str(x))
        return "; ".join(partes)
    return str(v)


def _hist_linha(lote, quem, origem, status, t, campo, antes, depois, descricao="") -> dict:
    """Port de histLinha_ (.gs linha 755)."""
    return {
        "id": "H" + uuid.uuid4().hex[:10].upper(),
        "quando": datetime.utcnow(),
        "quem": str(quem or ""),
        "origem": origem,
        "cargoId": t["id"] if t else "",
        "cargoNome": t["nome"] if t else "",
        "campo": campo or "",
        "antes": _texto_valor(antes)[:2000],
        "depois": _texto_valor(depois)[:2000],
        "descricao": descricao or "",
        "justificativa": "",
        "status": status,
        "justificadoEm": None,
        "justificadoPor": "",
        "lote": lote,
    }


def normConteudo_(k: str, v):
    """Port de normConteudo_ (.gs linha 870)."""
    if k == "rotinas":
        itens = v if isinstance(v, list) else []
        mapeado = []
        for x in itens:
            xd = x if isinstance(x, dict) else {}
            mapeado.append({"f": _texto(xd.get("f"), 60), "t": _texto(xd.get("t"), 300)})
        return [m for m in mapeado if m["t"]][:60]
    if k in LISTAS_:
        itens = v if isinstance(v, list) else []
        mapeado = [_texto(x, 300) for x in itens]
        return [m for m in mapeado if m][:60]
    return _texto(v, 1000 if k == "missao" else 300)


def _ler_tobe(db: Session) -> list:
    """Lista de dicts da tabela Tobe (equivalente a lerTobe_, .gs linha 746)."""
    T = []
    for t in db.query(Tobe).all():
        T.append({
            "id": t.id, "nome": t.nome, "area": t.area, "pai": t.pai or "",
            "pessoa": t.pessoa or "", "x": t.x, "y": t.y,
            "missao": t.missao or "", "funcoes": _J_(t.funcoes, []),
            "rotinas": _J_(t.rotinas, []), "jornada": t.jornada or "",
            "tempoEmpresa": t.tempoEmpresa or "", "formacao": t.formacao or "",
            "experiencia": t.experiencia or "", "habilidades": _J_(t.habilidades, []),
            "relacoes": _J_(t.relacoes, []), "recorre": t.recorre or "",
            "ferramentas": _J_(t.ferramentas, []),
            "origem": t.origem, "base": _J_(t.base, {}),
            "personalizado": _J_(t.personalizado, []),
            "conflito": _J_(t.conflito, []),
            "removido": bool(t.removido),
        })
    return T


def _persistir_tobe(T: list, db: Session) -> None:
    """Port de gravarTobe_ (.gs linha 767): grava a lista completa, removendo o que não está mais nela."""
    desejados = {t["id"] for t in T}
    existentes = {t.id: t for t in db.query(Tobe).all()}
    for tid, row in existentes.items():
        if tid not in desejados:
            db.delete(row)
    for t in T:
        row = existentes.get(t["id"])
        if row is None:
            row = Tobe(id=t["id"])
            db.add(row)
        row.nome = t["nome"]
        row.area = t["area"]
        row.pai = t.get("pai") or ""
        row.pessoa = t.get("pessoa") or ""
        row.missao = t.get("missao") or ""
        row.funcoes = json.dumps(t.get("funcoes") or [])
        row.rotinas = json.dumps(t.get("rotinas") or [])
        row.jornada = t.get("jornada") or ""
        row.tempoEmpresa = t.get("tempoEmpresa") or ""
        row.formacao = t.get("formacao") or ""
        row.experiencia = t.get("experiencia") or ""
        row.habilidades = json.dumps(t.get("habilidades") or [])
        row.relacoes = json.dumps(t.get("relacoes") or [])
        row.recorre = t.get("recorre") or ""
        row.ferramentas = json.dumps(t.get("ferramentas") or [])
        row.x = t.get("x")
        row.y = t.get("y")
        row.origem = t.get("origem") or "tobe"
        row.base = json.dumps(t.get("base") or {})
        row.personalizado = json.dumps(t.get("personalizado") or [])
        row.conflito = json.dumps(t.get("conflito") or [])
        row.removido = bool(t.get("removido"))
    db.flush()


def _gravar_historico(hist: list, db: Session) -> None:
    """Port de anexaHist_ (.gs linha 765)."""
    for h in hist:
        db.add(TobeHistorico(
            id=h["id"], quando=h["quando"], quem=h["quem"], origem=h["origem"],
            cargoId=h["cargoId"], cargoNome=h["cargoNome"], campo=h["campo"],
            antes=h["antes"], depois=h["depois"], descricao=h["descricao"],
            justificativa=h.get("justificativa", ""), status=h["status"],
            justificadoEm=h.get("justificadoEm"), justificadoPor=h.get("justificadoPor", ""),
            lote=h["lote"],
        ))


def _foto_tobe(T: list) -> str:
    """Port de fotoTobe_ (.gs linha 752). Usar json.dumps SEM ensure_ascii=False e sem
    separators customizados: precisa serializar byte-a-byte igual em toda chamada, para a
    comparação de 'mudou desde a última versão' funcionar."""
    itens = []
    for t in T:
        if t.get("removido"):
            continue
        o = {"id": t["id"]}
        for k in SYNC_CAMPOS_:
            o[k] = t.get(k)
        itens.append(o)
    itens.sort(key=lambda o: o["id"])
    return json.dumps(itens)


MENU_ = {
    "admin": ["inicio", "agenda", "organograma", "cargos", "tobeOrg", "tobeCargos", "editorg", "entrevistas", "usuarios"],
    "socio": ["inicio", "organograma", "cargos"],
    "gestor": ["inicio", "agenda", "organograma", "cargos"],
    "colaborador": ["inicio", "agenda", "organograma", "cargos"],
}


def tobeIniciado_(db: Session) -> bool:
    """Verifica se TO BE foi iniciado (há algum registro em Tobe)."""
    return db.query(Tobe).first() is not None


def iniciarTobe_(u: dict, db: Session) -> None:
    """Primeira abertura: copia AS IS inteiro para TO BE."""
    # Lê cargos do AS IS
    cargos = db.query(Cargo).all()

    for c in cargos:
        t = Tobe(
            id=c.id,
            nome=c.nome,
            area=c.area,
            pai=c.pai,
            pessoa=c.pessoa,
            missao=c.missao or "",
            funcoes=c.funcoes or "",
            rotinas=c.rotinas or "",
            jornada=c.jornada or "",
            tempoEmpresa=c.tempoEmpresa or "",
            formacao=c.formacao or "",
            experiencia=c.experiencia or "",
            habilidades=c.habilidades or "",
            relacoes=c.relacoes or "",
            recorre=c.recorre or "",
            ferramentas=c.ferramentas or "",
            x=c.x,
            y=c.y,
            origem="asis",
            base=json.dumps({
                "nome": c.nome, "area": c.area, "pai": c.pai or "",
                "pessoa": c.pessoa, "x": c.x, "y": c.y,
                "missao": c.missao or "", "funcoes": _J_(c.funcoes, []),
                "rotinas": _J_(c.rotinas, []), "jornada": c.jornada or "",
                "tempoEmpresa": c.tempoEmpresa or "", "formacao": c.formacao or "",
                "experiencia": c.experiencia or "", "habilidades": _J_(c.habilidades, []),
                "relacoes": _J_(c.relacoes, []), "recorre": c.recorre or "",
                "ferramentas": _J_(c.ferramentas, [])
            }),
            personalizado=json.dumps([]),
            conflito=json.dumps([]),
            removido=False
        )
        db.add(t)

    # Registra no histórico
    lote = "L" + uuid.uuid4().hex[:10].upper()
    h = TobeHistorico(
        id="H" + uuid.uuid4().hex[:10].upper(),
        quando=datetime.utcnow(),
        quem=u.get("nome", ""),
        origem="sync",
        cargoId="",
        cargoNome="",
        campo="",
        antes="",
        depois="",
        descricao=f"Cópia inicial do AS IS: {len(cargos)} cargos",
        status="Automática",
        lote=lote
    )
    db.add(h)
    db.commit()


def tobeAdmin_(token: str, o: str, db: Session, secret: str) -> dict:
    """Valida admin e inicia TO BE na primeira vez."""
    u = sessao_(token, db, secret)
    so_admin_(u, o)
    if not tobeIniciado_(db):
        iniciarTobe_(u, db)
    return u


def comSync_(token: str, fn, db: Session, secret: str):
    """Roda fn() e, se TO BE foi iniciado, sincroniza automaticamente."""
    r = fn()
    u = sessao_(token, db, secret)
    if tobeIniciado_(db):
        sincronizarTobe_(u.get("nome", ""), db)
    return r


def corrigePais_(T: list) -> list:
    """Corrige superiores que apontam para cargo excluído: sobem pela cadeia."""
    porId = {t["id"]: t for t in T}
    trocas = []

    for t in T:
        if t.get("removido") or not t.get("pai"):
            continue
        if t["pai"] in porId and not porId[t["pai"]].get("removido"):
            continue

        # Pai foi excluído, procura o pai ativo
        p = t["pai"]
        k = 0
        while p and k < 80:
            if p not in porId:
                p = ""
                break
            if not porId[p].get("removido"):
                break
            p = porId[p].get("pai")
            k += 1

        if p != t["pai"]:
            trocas.append({"t": t, "antes": t["pai"], "novo": p})
            t["pai"] = p

    return trocas


def sincronizarTobe_(quem: str, db: Session) -> dict:
    """Sincroniza TO BE com AS IS: herda mudanças, detecta conflitos."""
    # Lê AS IS e TO BE
    asis = []
    for c in db.query(Cargo).all():
        asis.append({
            "id": c.id, "nome": c.nome, "area": c.area, "pai": c.pai or "",
            "pessoa": c.pessoa, "x": c.x, "y": c.y,
            "missao": c.missao or "", "funcoes": _J_(c.funcoes, []),
            "rotinas": _J_(c.rotinas, []), "jornada": c.jornada or "",
            "tempoEmpresa": c.tempoEmpresa or "", "formacao": c.formacao or "",
            "experiencia": c.experiencia or "", "habilidades": _J_(c.habilidades, []),
            "relacoes": _J_(c.relacoes, []), "recorre": c.recorre or "",
            "ferramentas": _J_(c.ferramentas, [])
        })

    T = []
    for t in db.query(Tobe).all():
        T.append({
            "id": t.id, "nome": t.nome, "area": t.area, "pai": t.pai or "",
            "pessoa": t.pessoa, "x": t.x, "y": t.y,
            "missao": t.missao or "", "funcoes": _J_(t.funcoes, []),
            "rotinas": _J_(t.rotinas, []), "jornada": t.jornada or "",
            "tempoEmpresa": t.tempoEmpresa or "", "formacao": t.formacao or "",
            "experiencia": t.experiencia or "", "habilidades": _J_(t.habilidades, []),
            "relacoes": _J_(t.relacoes, []), "recorre": t.recorre or "",
            "ferramentas": _J_(t.ferramentas, []),
            "origem": t.origem, "base": _J_(t.base, {}),
            "personalizado": _J_(t.personalizado, []),
            "conflito": _J_(t.conflito, []),
            "removido": bool(t.removido)
        })

    porId = {t["id"]: t for t in T}
    lote = "L" + uuid.uuid4().hex[:10].upper()
    hist = []
    criados = 0
    atualizados = 0
    conflitos = 0
    removidos = 0
    tocados = set()
    asisIds = {a["id"] for a in asis}
    agora = datetime.utcnow().isoformat()

    def registra(t, campo, antes, depois, descricao):
        h = {
            "id": "H" + uuid.uuid4().hex[:10].upper(),
            "quando": datetime.utcnow(),
            "quem": quem,
            "origem": "sync",
            "cargoId": t.get("id", "") if t else "",
            "cargoNome": t.get("nome", "") if t else "",
            "campo": campo or "",
            "antes": _texto_valor(antes)[:2000],
            "depois": _texto_valor(depois)[:2000],
            "descricao": descricao,
            "status": "Automática",
            "lote": lote
        }
        hist.append(h)

    # Processa cargos do AS IS
    for a in asis:
        t = porId.get(a["id"])
        if not t:
            # Novo no AS IS: cria no TO BE como herdado
            novo = {
                **a,
                "origem": "asis",
                "base": a.copy(),
                "personalizado": [],
                "conflito": [],
                "removido": False
            }
            T.append(novo)
            porId[a["id"]] = novo
            criados += 1
            tocados.add(a["id"])
            registra(novo, "cargo", "", a["nome"], "Cargo herdado do AS IS")
            continue

        if t["origem"] != "asis":
            continue

        if t["removido"]:
            # Já marcado como excluído: só atualiza base se AS IS mudou
            base = t.get("base", {})
            mudou = False
            for k in SYNC_CAMPOS_:
                if json.dumps(a.get(k)) != json.dumps(base.get(k)):
                    mudou = True
                    break
            if mudou:
                t["base"] = a.copy()
                tocados.add(t["id"])
                registra(t, "cargo", "", "", "Cargo mudou no AS IS, mas segue excluído no TO BE")
            continue

        # Cargo ativo: processa campos
        houve = False
        base = t.get("base", {})
        for k in SYNC_CAMPOS_:
            if k not in base:
                t["base"][k] = a[k]
                tocados.add(t["id"])
                continue

            if json.dumps(a.get(k)) == json.dumps(base.get(k)):
                continue  # AS IS não mudou

            novo = a[k]
            t["base"][k] = novo
            tocados.add(t["id"])

            if json.dumps(t.get(k)) == json.dumps(novo):
                # Convergiu: tira de personalizado
                t["personalizado"] = [c for c in t.get("personalizado", []) if c != k]
                continue

            if k not in t.get("personalizado", []):
                # Herda
                t[k] = novo
                houve = True
                registra(t, k, t.get(k), novo, f"Herdado do AS IS: {ROTULO_.get(k, k)} alterado")
                continue

            # Conflito: personalizado divergente
            conflito_list = [c for c in t.get("conflito", []) if c.get("campo") != k]
            conflito_list.append({
                "campo": k,
                "asis": novo,
                "tobe": t.get(k),
                "em": agora
            })
            t["conflito"] = conflito_list
            conflitos += 1
            houve = True
            registra(t, k, t.get(k), novo,
                    f"Conflito: o AS IS mudou, mas este campo foi personalizado no TO BE")

        if houve:
            atualizados += 1

    # Processa cargos excluídos no AS IS
    for t in T:
        if t["origem"] != "asis" or t["removido"] or t["id"] in asisIds:
            continue

        # Cargo foi excluído no AS IS
        personalizado = t.get("personalizado", [])
        if not personalizado:
            t["removido"] = True
            removidos += 1
            tocados.add(t["id"])
            registra(t, "cargo", t["nome"], "", "Excluído no AS IS: marcado como excluído no TO BE")
        else:
            # Personalizado: cria conflito
            conflito_list = [c for c in t.get("conflito", []) if c.get("campo") != "*"]
            if not any(c.get("campo") == "*" for c in conflito_list):
                conflito_list.append({
                    "campo": "*",
                    "asis": "excluído no AS IS",
                    "tobe": "mantido",
                    "em": agora
                })
                conflitos += 1
                tocados.add(t["id"])
                registra(t, "cargo", "mantido", "excluído no AS IS",
                        "Conflito: o cargo foi excluído no AS IS, mas foi personalizado no TO BE")
            t["conflito"] = conflito_list

    # Corrige pais
    for trocas in corrigePais_(T):
        t = trocas["t"]
        tocados.add(t["id"])
        novo_nome = next((x["nome"] for x in T if x["id"] == t["pai"]), "")
        registra(t, "pai", trocas["antes"], t["pai"],
                f"Superior excluído: o cargo passou para " +
                (f"o superior {novo_nome}" if t["pai"] and novo_nome else "o topo"))

    # Grava mudanças
    if tocados or hist:
        # Atualiza registros em Tobe
        T_dict = {t["id"]: t for t in T}
        for t_id, t_data in T_dict.items():
            t = db.query(Tobe).filter(Tobe.id == t_id).first()
            if t:
                t.nome = t_data["nome"]
                t.area = t_data["area"]
                t.pai = t_data["pai"] if t_data["pai"] else None
                t.pessoa = t_data["pessoa"]
                t.x = t_data["x"]
                t.y = t_data["y"]
                t.missao = t_data["missao"]
                t.funcoes = json.dumps(t_data["funcoes"])
                t.rotinas = json.dumps(t_data["rotinas"])
                t.jornada = t_data["jornada"]
                t.tempoEmpresa = t_data["tempoEmpresa"]
                t.formacao = t_data["formacao"]
                t.experiencia = t_data["experiencia"]
                t.habilidades = json.dumps(t_data["habilidades"])
                t.relacoes = json.dumps(t_data["relacoes"])
                t.recorre = t_data["recorre"]
                t.ferramentas = json.dumps(t_data["ferramentas"])
                t.base = json.dumps(t_data.get("base", {}))
                t.personalizado = json.dumps(t_data.get("personalizado", []))
                t.conflito = json.dumps(t_data.get("conflito", []))
                t.removido = t_data.get("removido", False)
                db.add(t)

        # Adiciona histórico
        for h in hist:
            th = TobeHistorico(
                id=h["id"],
                quando=h["quando"],
                quem=h["quem"],
                origem=h["origem"],
                cargoId=h["cargoId"],
                cargoNome=h["cargoNome"],
                campo=h["campo"],
                antes=h["antes"],
                depois=h["depois"],
                descricao=h["descricao"],
                status=h["status"],
                lote=h["lote"]
            )
            db.add(th)

        db.commit()

    return {"criados": criados, "atualizados": atualizados, "conflitos": conflitos, "removidos": removidos}


def tobeVisao_(db: Session) -> dict:
    """Monta a visão do TO BE para a tela."""
    # Lê TO BE
    tobe = []
    por = {}
    for t in db.query(Tobe).all():
        if not t.removido:
            td = {
                "id": t.id, "nome": t.nome, "area": t.area, "pai": t.pai,
                "pessoa": t.pessoa, "x": t.x, "y": t.y,
                "missao": t.missao or "",
                "funcoes": _J_(t.funcoes, []),
                "rotinas": _J_(t.rotinas, []),
                "jornada": t.jornada or "",
                "tempoEmpresa": t.tempoEmpresa or "",
                "formacao": t.formacao or "",
                "experiencia": t.experiencia or "",
                "habilidades": _J_(t.habilidades, []),
                "relacoes": _J_(t.relacoes, []),
                "recorre": t.recorre or "",
                "ferramentas": _J_(t.ferramentas, []),
                "origem": t.origem,
                "personalizado": _J_(t.personalizado, []),
                "conflitos": _J_(t.conflito, [])
            }
            tobe.append(td)
            por[t.id] = td

    # Histórico (últimas 300, mais novo primeiro)
    hist = []
    for h in db.query(TobeHistorico).all()[-300:]:
        hist.append({
            "id": h.id,
            "quando": h.quando.isoformat() if h.quando else "",
            "quem": h.quem or "",
            "origem": h.origem or "",
            "cargoId": h.cargoId or "",
            "cargoNome": h.cargoNome or "",
            "campo": h.campo or "",
            "antes": h.antes or "",
            "depois": h.depois or "",
            "descricao": h.descricao or "",
            "justificativa": h.justificativa or "",
            "status": h.status or "",
            "justificadoEm": h.justificadoEm.isoformat() if h.justificadoEm else "",
            "justificadoPor": h.justificadoPor or "",
            "lote": h.lote or ""
        })
    hist.reverse()

    # Versão publicada
    versao = None
    ultima_versao = db.query(TobeVersao).order_by(TobeVersao.versao.desc()).first()
    if ultima_versao:
        versao = {
            "numero": ultima_versao.versao,
            "publicadoEm": ultima_versao.publicadoEm.isoformat() if ultima_versao.publicadoEm else "",
            "por": ultima_versao.por or "",
            "nota": ultima_versao.nota or ""
        }

    # Conta pendências e conflitos
    pendentes = len([h for h in hist if h.get("status") == "Pendente de justificativa"])
    conflitos_total = sum(len(t.get("conflitos", [])) for t in tobe)

    # Detecta se rascunho alterou
    foto_atual = json.dumps([{
        "id": t["id"],
        **{k: t[k] for k in SYNC_CAMPOS_ if k in t}
    } for t in sorted(tobe, key=lambda x: x["id"])])

    rascunho_alterado = True
    if ultima_versao and ultima_versao.snapshot:
        rascunho_alterado = ultima_versao.snapshot != foto_atual

    return {
        "iniciado": True,
        "cargos": tobe,
        "historico": hist,
        "pendentes": pendentes,
        "conflitos": conflitos_total,
        "versao": versao,
        "rascunhoAlterado": rascunho_alterado
    }


def tobeSalvar_(u: dict, d: dict, db: Session) -> dict:
    """Port de tobeSalvar_ (.gs linha 876)."""
    from server.handlers_admin import dadosCargo_, fazCiclo_
    import random
    import string

    d = d or {}
    alts = d.get("alteracoes") if isinstance(d.get("alteracoes"), list) else []
    posicoes = d.get("posicoes") if isinstance(d.get("posicoes"), list) else []
    ligacoes = d.get("ligacoes") if isinstance(d.get("ligacoes"), list) else []
    if not alts and not posicoes and not ligacoes and d.get("reset") is not True:
        raise ErroNegocio("Nada para salvar.")
    if len(alts) > 300 or len(posicoes) > 500 or len(ligacoes) > 500:
        raise ErroNegocio("Alterações demais de uma vez. Salve em partes.")

    just = _texto(d.get("justificativa"), 600)
    status = "Justificada" if just else "Pendente de justificativa"

    T = _ler_tobe(db)
    porId = {t["id"]: t for t in T}
    lote = "L" + uuid.uuid4().hex[:10].upper()
    hist = []
    mudados = set()
    vistos = set()

    def ativo(id_):
        t = porId.get(str(id_ or ""))
        if not t or t.get("removido"):
            raise ErroNegocio("Cargo não encontrado.")
        return t

    def personaliza(t, campo):
        if t.get("origem") == "asis" and campo in SYNC_CAMPOS_ and campo not in t.get("personalizado", []):
            t.setdefault("personalizado", []).append(campo)

    def muda_com(t, campo, novo, descricao=None, auto=False):
        antes = t.get(campo)
        if _mesmo(antes, novo):
            return
        t[campo] = novo
        mudados.add(t["id"])
        personaliza(t, campo)
        if auto:
            hist.append(_hist_linha(lote, u.get("nome", ""), "ajuste", "Automática", t, campo, antes, novo,
                                     f"{ROTULO_.get(campo, campo)} reformatado(a) automaticamente ao padrão de redação"))
        else:
            hist.append(_hist_linha(lote, u.get("nome", ""), "manual", status, t, campo, antes, novo,
                                     descricao or f"{ROTULO_.get(campo, campo)} alterado(a) no TO BE"))

    def pos_txt(t):
        x = "" if t.get("x") is None else t.get("x")
        y = "" if t.get("y") is None else t.get("y")
        return f"{x}, {y}"

    def exclui_no_tobe(t):
        for f in T:
            if not f.get("removido") and f.get("pai") == t["id"]:
                muda_com(f, "pai", t.get("pai") or "", f"Subiu para o superior de {t['nome']}, que foi excluído no TO BE")
        t["removido"] = True
        mudados.add(t["id"])
        hist.append(_hist_linha(lote, u.get("nome", ""), "manual", status, t, "cargo", t["nome"], "", "Cargo excluído no TO BE"))

    for a in alts:
        a = a or {}
        if a.get("novo") is True:
            dd = dadosCargo_(a)
            while True:
                novo_id = "tb-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
                if novo_id not in porId:
                    break
            t = {
                "id": novo_id, "nome": dd["nome"], "area": dd["area"], "pai": str(a.get("pai") or ""),
                "pessoa": dd["pessoa"], "x": None, "y": None, "missao": "", "funcoes": [], "rotinas": [],
                "jornada": "", "tempoEmpresa": "", "formacao": "", "experiencia": "", "habilidades": [],
                "relacoes": [], "recorre": "", "ferramentas": [],
                "origem": "tobe", "base": {}, "personalizado": [], "conflito": [], "removido": False,
            }
            T.append(t)
            porId[novo_id] = t
            mudados.add(novo_id)
            vistos.add(novo_id)
            hist.append(_hist_linha(lote, u.get("nome", ""), "manual", status, t, "cargo", "", t["nome"], "Cargo criado no TO BE"))
            conteudo = a.get("conteudo")
            if isinstance(conteudo, dict):
                for k in conteudo:
                    if k in CONTEUDO_:
                        muda_com(t, k, normConteudo_(k, conteudo[k]))
            continue

        id_ = str(a.get("id") or "")
        if id_ in vistos:
            raise ErroNegocio("O mesmo cargo aparece mais de uma vez na lista.")
        t = ativo(id_)
        vistos.add(id_)
        if a.get("excluir") is True:
            exclui_no_tobe(t)
            continue
        dd = dadosCargo_(a)
        muda_com(t, "nome", dd["nome"])
        muda_com(t, "area", dd["area"])
        muda_com(t, "pessoa", dd["pessoa"])
        if "pai" in a:
            muda_com(t, "pai", str(a.get("pai") or ""))
        auto_campos = {str(x) for x in a.get("auto")} if isinstance(a.get("auto"), list) else set()
        conteudo = a.get("conteudo")
        if isinstance(conteudo, dict):
            for k in conteudo:
                if k in CONTEUDO_:
                    muda_com(t, k, normConteudo_(k, conteudo[k]), None, k in auto_campos)

    if d.get("reset") is True:
        for t in T:
            if not t.get("removido") and (t.get("x") is not None or t.get("y") is not None):
                antes = pos_txt(t)
                t["x"] = None
                t["y"] = None
                mudados.add(t["id"])
                personaliza(t, "x")
                personaliza(t, "y")
                hist.append(_hist_linha(lote, u.get("nome", ""), "manual", status, t, "posição", antes, "", "Posições apagadas: organização automática"))

    for p in posicoes:
        p = p or {}
        t = ativo(p.get("id"))
        try:
            x = round(float(p.get("x")))
            y = round(float(p.get("y")))
        except (TypeError, ValueError):
            raise ErroNegocio("Posição inválida.")
        if abs(x) > 20000 or abs(y) > 20000:
            raise ErroNegocio("Posição inválida.")
        if t.get("x") == x and t.get("y") == y:
            continue
        antes = pos_txt(t)
        t["x"] = x
        t["y"] = y
        mudados.add(t["id"])
        personaliza(t, "x")
        personaliza(t, "y")
        hist.append(_hist_linha(lote, u.get("nome", ""), "manual", status, t, "posição", antes, pos_txt(t), "Posição no organograma alterada"))

    for l in ligacoes:
        l = l or {}
        t = ativo(l.get("id"))
        muda_com(t, "pai", str(l.get("pai") or ""), "Superior alterado(a) no TO BE")

    paiDe = {t["id"]: (t.get("pai") or "") for t in T if not t.get("removido")}
    for t in T:
        if t.get("removido") or t["id"] not in mudados or not t.get("pai"):
            continue
        if t["pai"] == t["id"]:
            raise ErroNegocio(f"{t['nome']}: um cargo não pode responder a ele mesmo.")
        alvo = porId.get(t["pai"])
        if not alvo or alvo.get("removido"):
            raise ErroNegocio(f"{t['nome']}: o cargo superior escolhido não existe.")
        if fazCiclo_(t["id"], t["pai"], paiDe):
            raise ErroNegocio(f"{t['nome']}: um cargo não pode ficar abaixo dele mesmo nem de quem está abaixo dele.")

    if not mudados:
        return {"n": 0, "lote": ""}

    if just:
        for h in hist:
            h["justificativa"] = just
            h["justificadoEm"] = datetime.utcnow()
            h["justificadoPor"] = u.get("nome", "")

    T_final = [t for t in T if not (t.get("removido") and t.get("origem") == "tobe")]
    _persistir_tobe(T_final, db)
    _gravar_historico(hist, db)
    db.commit()
    return {"n": len(mudados), "lote": lote}


def tobeJustificar_(u: dict, ref: dict, texto: str, db: Session) -> dict:
    """Port de tobeJustificar_ (.gs linha 946). 'ref' é {"id": ...} ou {"lote": ...}."""
    txt = _texto(texto, 600)
    if len(txt) < 5:
        raise ErroNegocio("A justificativa precisa ter pelo menos 5 caracteres.")
    ref = ref or {}
    id_ = str(ref.get("id") or "")
    lote = str(ref.get("lote") or "")
    if not id_ and not lote:
        raise ErroNegocio("Escolha o que justificar.")
    agora = datetime.utcnow()
    n = 0
    for r in db.query(TobeHistorico).filter(
        TobeHistorico.origem == "manual",
        TobeHistorico.status == "Pendente de justificativa",
    ).all():
        if not ((id_ and r.id == id_) or (lote and r.lote == lote)):
            continue
        r.justificativa = txt
        r.status = "Justificada"
        r.justificadoEm = agora
        r.justificadoPor = u.get("nome", "")
        n += 1
    if not n:
        raise ErroNegocio("Nada pendente para justificar.")
    db.commit()
    return {"n": n}


def tobeResolver_(u: dict, cargoId: str, campo: str, decisao: str, justificativa: str, db: Session) -> bool:
    """Port de tobeResolver_ (.gs linha 965)."""
    T = _ler_tobe(db)
    cargo_id = str(cargoId or "")
    t = next((x for x in T if x["id"] == cargo_id and not x.get("removido")), None)
    if not t:
        raise ErroNegocio("Cargo não encontrado.")
    campo_str = str(campo or "")
    conflito = t.get("conflito", [])
    idx = next((i for i, c in enumerate(conflito) if c.get("campo") == campo_str), -1)
    if idx < 0:
        raise ErroNegocio("Este cargo não tem conflito neste campo.")
    if decisao not in ("manter", "aceitar"):
        raise ErroNegocio("Escolha manter ou aceitar.")
    c = conflito[idx]
    just = _texto(justificativa, 600)
    status = "Justificada" if just else "Pendente de justificativa"
    lote = "L" + uuid.uuid4().hex[:10].upper()
    hist = []
    t["conflito"] = conflito[:idx] + conflito[idx + 1:]

    if decisao == "aceitar" and c.get("campo") == "*":
        t["removido"] = True
        hist.append(_hist_linha(lote, u.get("nome", ""), "manual", status, t, "cargo", t["nome"], "", "Conflito resolvido: exclusão do AS IS aceita"))
    elif decisao == "aceitar":
        campo_alvo = c["campo"]
        antes = t.get(campo_alvo)
        t[campo_alvo] = c.get("asis")
        t.setdefault("base", {})[campo_alvo] = c.get("asis")
        t["personalizado"] = [k for k in t.get("personalizado", []) if k != campo_alvo]
        hist.append(_hist_linha(lote, u.get("nome", ""), "manual", status, t, campo_alvo, antes, c.get("asis"), "Conflito resolvido: valor do AS IS aceito"))
    else:
        hist.append(_hist_linha(lote, u.get("nome", ""), "manual", status, t, c["campo"], c.get("tobe"), c.get("tobe"), "Conflito resolvido: valor do TO BE mantido"))

    for troca in corrigePais_(T):
        hist.append(_hist_linha(lote, u.get("nome", ""), "sync", "Automática", troca["t"], "pai", troca["antes"], troca["novo"], "Superior excluído: o cargo subiu para o superior ativo"))

    if just:
        for h in hist:
            h["justificativa"] = just
            h["justificadoEm"] = datetime.utcnow()
            h["justificadoPor"] = u.get("nome", "")

    T_final = [x for x in T if not (x.get("removido") and x.get("origem") == "tobe")]
    _persistir_tobe(T_final, db)
    _gravar_historico(hist, db)
    db.commit()
    return True


def tobePublicar_(u: dict, d: dict, db: Session) -> dict:
    """Port de tobePublicar_ (.gs linha 986)."""
    d = d or {}
    if d.get("confirmar") is not True:
        raise ErroNegocio("Confirme a publicação para continuar.")
    T = _ler_tobe(db)
    ult = db.query(TobeVersao).order_by(TobeVersao.versao.desc()).first()
    foto = _foto_tobe(T)
    if ult and (ult.snapshot or "") == foto:
        raise ErroNegocio("Nada mudou desde a última versão.")
    numero = (ult.versao + 1) if ult else 1
    db.add(TobeVersao(
        versao=numero, publicadoEm=datetime.utcnow(), por=u.get("nome", ""),
        nota=_texto(d.get("nota"), 300), snapshot=foto,
    ))
    lote = "L" + uuid.uuid4().hex[:10].upper()
    _gravar_historico(
        [_hist_linha(lote, u.get("nome", ""), "publicacao", "Automática", None, "versão", "", f"Versão {numero}",
                     f"Organograma futuro publicado como versão {numero}")],
        db,
    )
    db.commit()
    return {"versao": numero}


def visualizarComo_(d: dict, db: Session) -> dict:
    """Port de visualizarComo_ (.gs linha 1006)."""
    from server.modelo import PERFIS, carregar_, modelo_, retrato_

    d = d or {}
    perfil = str(d.get("perfil") or "")
    if perfil not in PERFIS:
        raise ErroNegocio("Escolha o perfil que quer ver.")
    D = carregar_(db)
    M = modelo_(D)
    cid = str(d.get("cargoId") or "")
    if perfil in ("gestor", "colaborador") and not cid:
        raise ErroNegocio("Escolha um cargo para ver como este perfil.")
    cargo = M["byId"](cid) if cid else None
    if cid and not cargo:
        raise ErroNegocio("Cargo não encontrado.")
    u = {"email": "simulado", "nome": "Visão simulada", "perfil": perfil,
         "cargo": cargo["id"] if cargo else None, "status": "Ativo", "simulado": True}
    s = M["scope"](u)
    r = retrato_(D, u)
    for k in ("entrevistas", "diag", "opcoesAreas", "usuarios", "registro", "perfis", "pedidosCargo"):
        r.pop(k, None)
    for k in ("pendentes", "semLista", "solicitacoesAbertas", "pedidosCargoAbertos"):
        r.get("resumo", {}).pop(k, None)
    for f in r.get("fichas", {}).values():
        f.pop("entrevista", None)
        f.pop("dataEntrevista", None)
        if f.get("conteudo"):
            f["conteudo"].pop("historico", None)
            f["conteudo"].pop("entrevistaId", None)
    visiveis = [c for c in D["cargos"] if c["id"] in s]
    equipe = [{"id": x["id"], "nome": x["nome"], "pessoa": x["pessoa"]}
              for x in D["cargos"] if cargo and x.get("pai") == cargo["id"]] if cargo else []
    cadeia = []
    p = cargo
    k = 0
    while p and k < 30:
        cadeia.append({"id": p["id"], "nome": p["nome"], "pessoa": p["pessoa"]})
        p = M["byId"](p["pai"]) if p.get("pai") else None
        k += 1
    return {
        "perfil": perfil,
        "perfilNome": PERFIS[perfil]["nome"],
        "cargo": {"id": cargo["id"], "nome": cargo["nome"], "area": cargo["area"], "pessoa": cargo["pessoa"]} if cargo else None,
        "menu": MENU_.get(perfil, []),
        "retrato": r,
        "resumo": {
            "cargosComManual": len([c for c in visiveis if c.get("conteudo")]),
            "cargosSoPosicao": len([c for c in visiveis if not c.get("conteudo")]),
            "total": len(visiveis),
        },
        "cadeia": cadeia,
        "equipe": equipe,
        "regras": [
            PERFIS[perfil]["desc"],
            "Entrevistas, autoavaliação e o TO BE não aparecem nesta visão.",
            "Manuais em construção só aparecem para o administrador.",
        ],
    }


# API Wrappers
def api_tobe(token: str, db: Session, secret: str) -> dict:
    """Abre a tela TO BE."""
    u = tobeAdmin_(token, "ver o TO BE", db, secret)
    return tobeVisao_(db)


def api_tobeSalvar(token: str, d: dict, db: Session, secret: str) -> dict:
    """Salva alterações no TO BE."""
    u = tobeAdmin_(token, "salvar o TO BE", db, secret)
    return tobeSalvar_(u, d, db)


def api_tobeJustificar(token: str, ref: dict, texto: str, db: Session, secret: str) -> dict:
    """Justifica uma alteração."""
    u = tobeAdmin_(token, "justificar o TO BE", db, secret)
    return tobeJustificar_(u, ref, texto, db)


def api_tobeResolverConflito(token: str, cargoId: str, campo: str, decisao: str, justificativa: str, db: Session, secret: str) -> bool:
    """Resolve um conflito."""
    u = tobeAdmin_(token, "resolver conflito do TO BE", db, secret)
    return tobeResolver_(u, cargoId, campo, decisao, justificativa, db)


def api_tobeSincronizar(token: str, db: Session, secret: str) -> dict:
    """Sincroniza TO BE com AS IS."""
    u = tobeAdmin_(token, "sincronizar o TO BE", db, secret)
    return sincronizarTobe_(u.get("nome", ""), db)


def api_tobePublicar(token: str, d: dict, db: Session, secret: str) -> dict:
    """Publica uma versão do TO BE."""
    u = tobeAdmin_(token, "publicar o TO BE", db, secret)
    return tobePublicar_(u, d, db)


def api_visualizarComo(token: str, d: dict, db: Session, secret: str) -> dict:
    """Visualiza como outro perfil."""
    from server.auth import so_admin_
    u = sessao_(token, db, secret)
    so_admin_(u, "visualizar como")
    return visualizarComo_(d or {}, db)
