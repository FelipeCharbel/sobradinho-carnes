"""
Inicialização: cria tabelas e gera código de primeiro administrador.
Equivalente a configurar()/novoCodigoAdmin() do .gs (linha 41-70).
"""
import uuid
from server.db import get_session, init_db
from server.models import Configuracao


def novoCodigoAdmin(db) -> str:
    """Port de novoCodigoAdmin (.gs linha 57): gera e PERSISTE no banco (não em env var --
    ver Configuracao em models.py) o código de uso único do primeiro administrador."""
    codigo = uuid.uuid4().hex[:10].upper()
    existente = db.query(Configuracao).filter(Configuracao.chave == "ADMIN_CODIGO").first()
    if existente:
        existente.valor = codigo
    else:
        db.add(Configuracao(chave="ADMIN_CODIGO", valor=codigo))
    db.commit()
    msg = f"CÓDIGO DE ADMINISTRADOR (vale para um único cadastro): {codigo}"
    print(msg)
    return codigo


def configurar(db=None) -> str:
    """Cria as tabelas se não existirem e gera código de admin."""
    init_db()
    fechar = db is None
    if db is None:
        db = get_session()
    try:
        codigo = novoCodigoAdmin(db)
    finally:
        if fechar:
            db.close()
    resumo = (f"Plataforma inicializada.\nCÓDIGO DO PRIMEIRO ADMINISTRADOR: {codigo}\n"
              "(use na tela 'Primeiro acesso', em 'Sou do Grupo Gestão'. Vale para um único cadastro.)")
    print(resumo)
    return resumo


if __name__ == "__main__":
    configurar()
