"""
FastAPI: POST /api/rpc (dispatcher), GET /api/health, serve /public (estáticos, incluindo
public/index.html em "/"). Ver docs/CONTRATOS.md §1 (contrato RPC) e §1.1 (resp_/mudar_/comSync_).
"""
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from server.db import get_session, init_db
from server.auth import ErroNegocio, sessao_, criar_token
from server.modelo import carregar_, retrato_
from server.handlers_admin import (
    api_login, api_snapshot, api_primeiroAcesso, api_cargosPublicos, api_logout,
    api_lerEntrevista, api_respostas, api_salvarEntrevista, api_novaEntrevista,
    api_publicar, api_salvarCargo, api_excluirCargo, api_salvarUsuario,
    api_salvarPosicoes, api_definirSuperior, api_salvarCargos, api_salvarOrganograma,
    api_trocarSenha, api_redefinirSenha, api_importarCargos, api_solicitar,
    api_resolverSolicitacao, api_pedirCorrecaoCargo, api_meusPedidos,
    api_resolverCorrecaoCargo, api_visualizarComo
)
from server.handlers_tobe import (
    api_tobe, api_tobeSalvar, api_tobeJustificar,
    api_tobeResolverConflito, api_tobeSincronizar, api_tobePublicar
)
from server.handlers_export import router as export_router

app = FastAPI()
SECRET = os.getenv("SECRET_KEY", "dev-secret-change-in-production")

# Registra router de exportação (Fase 2)
app.include_router(export_router)

# Inicializa banco ao startup
@app.on_event("startup")
def startup():
    init_db()
    from server.models import Configuracao
    db = get_session()
    try:
        cfg = db.query(Configuracao).filter_by(chave="ADMIN_CODIGO").first()
        if not cfg:
            from server.seed import novoCodigoAdmin
            novoCodigoAdmin(db)
    finally:
        db.close()


@app.middleware("http")
async def sem_cache(request: Request, call_next):
    """Impede o navegador de servir um index.html (ou css/js) antigo do cache.
    Sem isso, uma correção no front-end pode não chegar ao usuário: ele continua
    executando a versão em cache. Downloads (.pptx) ficam de fora."""
    resp = await call_next(request)
    caminho = request.url.path
    if caminho.startswith("/api/export/"):
        return resp
    tipo = resp.headers.get("content-type", "")
    estatico_de_pagina = tipo.startswith(("text/html", "text/css", "text/javascript",
                                          "application/javascript", "application/json"))
    if estatico_de_pagina or not caminho.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        # ETag/Last-Modified do StaticFiles permitiriam 304 (corpo antigo reaproveitado)
        for h in ("etag", "last-modified"):
            if h in resp.headers:
                del resp.headers[h]
    return resp


def resp_(fn):
    """.gs linha 79: roda fn(); devolve {"dado": fn()} ou {"erro": str(e)} se exceção."""
    try:
        return {"dado": fn()}
    except ErroNegocio as e:
        return {"erro": str(e)}
    except Exception as e:
        return {"erro": str(e) or "Erro desconhecido"}


def mudar_(token: str, fn, db, secret: str):
    """.gs linha 82: roda fn() dentro de uma transação, devolve {"dado": {"r": resultado, "snap": ...}}.
    comSync_ é envolvido aqui quando necessário."""
    try:
        r = fn()
        u = sessao_(token, db, secret)
        D = carregar_(db)
        snap = retrato_(D, u)
        # Renova token
        novo_token = criar_token(u["email"], secret)
        return {"dado": {"r": r, "snap": snap, "token": novo_token}}
    except ErroNegocio as e:
        return {"erro": str(e)}
    except Exception as e:
        return {"erro": str(e) or "Erro desconhecido"}


# Tabela de dispatch: fn_name -> (func, wrapper_type)
# wrapper_type: "resp" (sem snap), "mudar" (com snap), "mudar+sync" (com sync automático)
DISPATCH = {
    # Autenticação e snapshot
    "api_login": (api_login, "resp"),
    "api_primeiroAcesso": (api_primeiroAcesso, "resp"),
    "api_cargosPublicos": (api_cargosPublicos, "resp"),
    "api_logout": (api_logout, "resp"),
    "api_snapshot": (api_snapshot, "resp"),
    "api_trocarSenha": (api_trocarSenha, "resp"),
    "api_redefinirSenha": (api_redefinirSenha, "mudar"),

    # Entrevistas
    "api_lerEntrevista": (api_lerEntrevista, "resp"),
    "api_respostas": (api_respostas, "resp"),
    "api_salvarEntrevista": (api_salvarEntrevista, "mudar+sync"),
    "api_novaEntrevista": (api_novaEntrevista, "mudar"),
    "api_publicar": (api_publicar, "mudar"),

    # Cargos e organograma
    "api_salvarCargo": (api_salvarCargo, "mudar+sync"),
    "api_excluirCargo": (api_excluirCargo, "mudar+sync"),
    "api_salvarUsuario": (api_salvarUsuario, "mudar"),
    "api_salvarPosicoes": (api_salvarPosicoes, "mudar+sync"),
    "api_definirSuperior": (api_definirSuperior, "mudar+sync"),
    "api_salvarCargos": (api_salvarCargos, "mudar+sync"),
    "api_salvarOrganograma": (api_salvarOrganograma, "mudar+sync"),
    "api_importarCargos": (api_importarCargos, "mudar+sync"),

    # Solicitações e pedidos
    "api_solicitar": (api_solicitar, "mudar"),
    "api_resolverSolicitacao": (api_resolverSolicitacao, "mudar"),
    "api_pedirCorrecaoCargo": (api_pedirCorrecaoCargo, "mudar"),
    "api_meusPedidos": (api_meusPedidos, "resp"),
    "api_resolverCorrecaoCargo": (api_resolverCorrecaoCargo, "mudar"),

    # TO BE
    "api_tobe": (api_tobe, "resp"),
    "api_tobeSalvar": (api_tobeSalvar, "mudar"),
    "api_tobeJustificar": (api_tobeJustificar, "mudar"),
    "api_tobeResolverConflito": (api_tobeResolverConflito, "mudar"),
    "api_tobeSincronizar": (api_tobeSincronizar, "mudar"),
    "api_tobePublicar": (api_tobePublicar, "mudar"),
    "api_visualizarComo": (api_visualizarComo, "resp"),
}


@app.post("/api/rpc")
async def rpc_endpoint(payload: dict):
    """Dispatcher RPC."""
    fn = payload.get("fn", "")
    args = payload.get("args", [])

    if fn not in DISPATCH:
        return {"erro": "Função desconhecida."}

    func, wrapper_type = DISPATCH[fn]
    db = get_session()

    try:
        if wrapper_type == "resp":
            # Funções simples: resp_
            if fn == "api_login":
                return resp_(lambda: func(args[0] if len(args) > 0 else "", args[1] if len(args) > 1 else "", db, SECRET))
            elif fn == "api_primeiroAcesso":
                return resp_(lambda: func(args[0] if len(args) > 0 else {}, db))
            elif fn == "api_cargosPublicos":
                return resp_(lambda: func(db))
            elif fn == "api_logout":
                return resp_(lambda: func(args[0] if len(args) > 0 else "", db, SECRET))
            elif fn == "api_snapshot":
                return resp_(lambda: func(args[0] if len(args) > 0 else "", db, SECRET))
            elif fn == "api_trocarSenha":
                return resp_(lambda: func(args[0] if len(args) > 0 else "", args[1] if len(args) > 1 else "", args[2] if len(args) > 2 else "", db, SECRET))
            elif fn == "api_lerEntrevista":
                return resp_(lambda: func(args[0] if len(args) > 0 else "", args[1] if len(args) > 1 else {}, db, SECRET))
            elif fn == "api_respostas":
                return resp_(lambda: func(args[0] if len(args) > 0 else "", args[1] if len(args) > 1 else "", db, SECRET))
            elif fn == "api_meusPedidos":
                return resp_(lambda: func(args[0] if len(args) > 0 else "", db, SECRET))
            elif fn == "api_tobe":
                return resp_(lambda: func(args[0] if len(args) > 0 else "", db, SECRET))
            elif fn == "api_visualizarComo":
                return resp_(lambda: func(args[0] if len(args) > 0 else "", args[1] if len(args) > 1 else {}, db, SECRET))
            else:
                return {"erro": "Função desconhecida."}

        elif wrapper_type == "mudar":
            # Funções que modificam: mudar_
            token = args[0] if len(args) > 0 else ""
            if fn == "api_redefinirSenha":
                return mudar_(token, lambda: func(token, args[1] if len(args) > 1 else "", db, SECRET), db, SECRET)
            elif fn == "api_novaEntrevista":
                return mudar_(token, lambda: func(token, args[1] if len(args) > 1 else {}, db, SECRET), db, SECRET)
            elif fn == "api_publicar":
                return mudar_(token, lambda: func(token, args[1] if len(args) > 1 else "", args[2] if len(args) > 2 else False, db, SECRET), db, SECRET)
            elif fn == "api_salvarUsuario":
                return mudar_(token, lambda: func(token, args[1] if len(args) > 1 else "", args[2] if len(args) > 2 else {}, db, SECRET), db, SECRET)
            elif fn == "api_solicitar":
                return mudar_(token, lambda: func(token, args[1] if len(args) > 1 else {}, db, SECRET), db, SECRET)
            elif fn == "api_resolverSolicitacao":
                return mudar_(token, lambda: func(token, args[1] if len(args) > 1 else "", args[2] if len(args) > 2 else "", args[3] if len(args) > 3 else "", db, SECRET), db, SECRET)
            elif fn == "api_pedirCorrecaoCargo":
                return mudar_(token, lambda: func(token, args[1] if len(args) > 1 else {}, db, SECRET), db, SECRET)
            elif fn == "api_resolverCorrecaoCargo":
                return mudar_(token, lambda: func(token, args[1] if len(args) > 1 else "", args[2] if len(args) > 2 else "", args[3] if len(args) > 3 else "", args[4] if len(args) > 4 else "", db, SECRET), db, SECRET)
            elif fn == "api_tobeSalvar":
                return mudar_(token, lambda: func(token, args[1] if len(args) > 1 else {}, db, SECRET), db, SECRET)
            elif fn == "api_tobeJustificar":
                return mudar_(token, lambda: func(token, args[1] if len(args) > 1 else {}, args[2] if len(args) > 2 else "", db, SECRET), db, SECRET)
            elif fn == "api_tobeResolverConflito":
                return mudar_(token, lambda: func(token, args[1] if len(args) > 1 else "", args[2] if len(args) > 2 else "", args[3] if len(args) > 3 else "", args[4] if len(args) > 4 else "", db, SECRET), db, SECRET)
            elif fn == "api_tobeSincronizar":
                return mudar_(token, lambda: func(token, db, SECRET), db, SECRET)
            elif fn == "api_tobePublicar":
                return mudar_(token, lambda: func(token, args[1] if len(args) > 1 else {}, db, SECRET), db, SECRET)
            else:
                return {"erro": "Função desconhecida."}

        elif wrapper_type == "mudar+sync":
            # mudar_ + sync automático
            token = args[0] if len(args) > 0 else ""
            if fn == "api_salvarEntrevista":
                from server.handlers_tobe import comSync_
                return mudar_(token, lambda: comSync_(token, lambda: func(token, args[1] if len(args) > 1 else {}, db, SECRET), db, SECRET), db, SECRET)
            elif fn == "api_salvarCargo":
                from server.handlers_tobe import comSync_
                return mudar_(token, lambda: comSync_(token, lambda: func(token, args[1] if len(args) > 1 else {}, db, SECRET), db, SECRET), db, SECRET)
            elif fn == "api_excluirCargo":
                from server.handlers_tobe import comSync_
                return mudar_(token, lambda: comSync_(token, lambda: func(token, args[1] if len(args) > 1 else "", db, SECRET), db, SECRET), db, SECRET)
            elif fn == "api_salvarPosicoes":
                from server.handlers_tobe import comSync_
                return mudar_(token, lambda: comSync_(token, lambda: func(token, args[1] if len(args) > 1 else {}, db, SECRET), db, SECRET), db, SECRET)
            elif fn == "api_definirSuperior":
                from server.handlers_tobe import comSync_
                return mudar_(token, lambda: comSync_(token, lambda: func(token, args[1] if len(args) > 1 else "", args[2] if len(args) > 2 else "", db, SECRET), db, SECRET), db, SECRET)
            elif fn == "api_salvarCargos":
                from server.handlers_tobe import comSync_
                return mudar_(token, lambda: comSync_(token, lambda: func(token, args[1] if len(args) > 1 else [], db, SECRET), db, SECRET), db, SECRET)
            elif fn == "api_salvarOrganograma":
                from server.handlers_tobe import comSync_
                return mudar_(token, lambda: comSync_(token, lambda: func(token, args[1] if len(args) > 1 else {}, db, SECRET), db, SECRET), db, SECRET)
            elif fn == "api_importarCargos":
                from server.handlers_tobe import comSync_
                return mudar_(token, lambda: comSync_(token, lambda: func(token, args[1] if len(args) > 1 else [], db, SECRET), db, SECRET), db, SECRET)
            else:
                return {"erro": "Função desconhecida."}

        else:
            return {"erro": "Função desconhecida."}

    except Exception as e:
        return {"erro": str(e) or "Erro desconhecido"}
    finally:
        db.close()


@app.get("/api/health")
async def health():
    """Health check."""
    return {"ok": True}


# Serve static files
try:
    public_path = os.path.join(os.path.dirname(__file__), "..", "public")
    app.mount("/", StaticFiles(directory=public_path, html=True), name="static")
except Exception as e:
    # Se a pasta public não existir, prosseguir sem erros
    pass
