"""
Rotas FastAPI de exportação .pptx. Ver docs/CONTRATOS_FASE2.md §5 (contrato dos endpoints) e §6
(assinaturas). Registrar estas rotas em server/main.py (acrescentar ao app existente da Fase 1,
sem remover nada que já está lá).
"""
from fastapi import APIRouter, Response, Query, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from server.auth import ErroNegocio, sessao_
from server.db import get_session
from server.modelo import carregar_, modelo_
from server.generator.spec_builder import construir_spec_manual, construir_spec_um_cargo
from server.generator.slide_engine import gerar_slide_cargo, gerar_manual_completo
import os

router = APIRouter()

PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


@router.get("/api/export/cargo/{cargo_id}")
def exportar_cargo(
    cargo_id: str,
    token: str = Query(...),
    db: Session = Depends(get_session),
    secret: str = None
):
    """CONTRATOS_FASE2.md §5. Valida sessao_(token). Confere que cargo_id está no scope do
    usuário (modelo_(carregar_(db)).scope(u)) -- 403 {"erro":"NEGADO"} se não estiver. 404 se o
    cargo não existe. Se não-admin e o cargo não está "publicado", 400 com mensagem
    "Este cargo ainda não tem manual publicado.". Senão, construir_spec_um_cargo + gerar_slide_cargo,
    devolver Response(content=bytes_do_pptx, media_type=PPTX_MEDIA_TYPE, headers={
    "Content-Disposition": 'attachment; filename="Ficha - <nome do cargo>.pptx"'}). Erros de
    negócio (ErroNegocio) viram {"erro": str(e)} com status 400/403 conforme o caso -- NÃO deixar
    vazar stack trace."""

    # Usa secret do environment se não fornecido (padrão do main.py)
    if secret is None:
        secret = os.getenv("SECRET_KEY", "dev-secret-change-in-production")

    try:
        # Valida token
        u = sessao_(token, db, secret)

        # Carrega dados
        D = carregar_(db)
        M = modelo_(D)

        # Encontra o cargo
        cargo = None
        for c in D["cargos"]:
            if c["id"] == cargo_id:
                cargo = c
                break

        if not cargo:
            return JSONResponse(status_code=404, content={"erro": "Cargo não encontrado."})

        # Verifica se está no scope do usuário
        scope_user = M["scope"](u)
        if cargo_id not in scope_user:
            return JSONResponse(status_code=403, content={"erro": "NEGADO"})

        # Verifica se o cargo tem conteúdo e status
        if not cargo.get("conteudo"):
            return JSONResponse(status_code=400, content={"erro": "Este cargo ainda não tem manual publicado."})

        status = cargo["conteudo"].get("status", "")
        is_admin = u.get("perfil") == "admin"

        # Non-admin só pode baixar publicado
        if not is_admin and status != "publicado":
            return JSONResponse(status_code=400, content={"erro": "Este cargo ainda não tem manual publicado."})

        # Constrói spec e gera PPTX
        spec = construir_spec_um_cargo(cargo_id, db)
        pptx_bytes = gerar_slide_cargo(spec)

        # Devolve resposta HTTP com o PPTX
        nome_cargo = cargo.get("nome", "cargo")
        filename = f"Ficha - {nome_cargo}.pptx"

        return Response(
            content=pptx_bytes.getvalue(),
            media_type=PPTX_MEDIA_TYPE,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except ErroNegocio as e:
        status_code = 403 if str(e) in ("SESSAO", "NEGADO") else 400
        return JSONResponse(status_code=status_code, content={"erro": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"erro": str(e) or "Erro desconhecido"})


@router.get("/api/export/manual-completo")
def exportar_manual_completo(
    token: str = Query(...),
    db: Session = Depends(get_session),
    secret: str = None
):
    """CONTRATOS_FASE2.md §5. Valida sessao_(token); exige perfil in ("admin","socio") -- 403
    {"erro":"NEGADO"} senão. construir_spec_manual + gerar_manual_completo, devolver
    Response(content=..., media_type=PPTX_MEDIA_TYPE, headers={"Content-Disposition":
    'attachment; filename="Manual de Cargos - Sobradinho Carnes.pptx"'})."""

    # Usa secret do environment se não fornecido (padrão do main.py)
    if secret is None:
        secret = os.getenv("SECRET_KEY", "dev-secret-change-in-production")

    try:
        # Valida token
        u = sessao_(token, db, secret)

        # Verifica permissão: apenas admin ou socio
        if u.get("perfil") not in ("admin", "socio"):
            return JSONResponse(status_code=403, content={"erro": "NEGADO"})

        # Constrói spec e gera PPTX
        spec = construir_spec_manual(db)
        pptx_bytes = gerar_manual_completo(spec)

        # Devolve resposta HTTP com o PPTX
        filename = "Manual de Cargos - Sobradinho Carnes.pptx"

        return Response(
            content=pptx_bytes.getvalue(),
            media_type=PPTX_MEDIA_TYPE,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except ErroNegocio as e:
        status_code = 403 if str(e) in ("SESSAO", "NEGADO") else 400
        return JSONResponse(status_code=status_code, content={"erro": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"erro": str(e) or "Erro desconhecido"})
