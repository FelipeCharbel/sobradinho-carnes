"""
Camada de acesso ao banco (substitui PropertiesService + SpreadsheetApp do Codigo.gs).

DATABASE_URL vem do ambiente (.env): "sqlite:///./sobradinho.db" por padrão, ou uma URL Postgres em
produção (ver docs/CONTRATOS.md §6 e §9). AVISO: SQLite em arquivo não persiste entre invocações
serverless na Vercel — em produção é obrigatório Postgres.

Concorrência (ver CONTRATOS.md §6): cada chamada de mudar_/escrever_ roda dentro de UMA transação
(session.commit() ao final, rollback() em qualquer exceção). Isso substitui o LockService.getScriptLock()
do original (.gs linha 198) — não é necessário lock explícito adicional além da transação.
"""
import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from server.models import Base

_engine = None
_SessionLocal = None

def get_engine():
    """Cria (uma vez, cacheado) o Engine do SQLAlchemy a partir de DATABASE_URL (env).

    Se DATABASE_URL começar com 'postgres://' ou 'postgresql://' (formato Supabase/Heroku),
    normaliza para 'postgresql+psycopg://' para usar o driver psycopg3.
    Adiciona pool_pre_ping=True para reconectar em caso de desconexão (importante em Postgres gerenciado).
    """
    global _engine
    if _engine is None:
        database_url = os.getenv("DATABASE_URL", "sqlite:///./sobradinho.db")

        # Normalizar postgres:// ou postgresql:// para postgresql+psycopg://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

        # Adicionar pool_pre_ping para todas as conexões (essencial para Postgres gerenciado)
        if database_url.startswith("postgresql+psycopg://"):
            _engine = create_engine(database_url, echo=False, pool_pre_ping=True)
        else:
            # SQLite: sem pool_pre_ping (não é necessário)
            _engine = create_engine(database_url, echo=False)
    return _engine


def get_session() -> Session:
    """Devolve uma nova Session do SQLAlchemy ligada ao engine de get_engine()."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal()


@contextmanager
def transacao(db: Session):
    """Context manager: abre uma transação, yield, commit no sucesso, rollback em exceção
    (reraise). Usar em toda função de escrita (equivalente a escrever_() do .gs, linha 198)."""
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Cria as 9 tabelas (ver models.py) se não existirem. Equivalente ao papel de configurar()
    que cria as abas da planilha (.gs linha 41-55), mas só a parte de schema — o seed de dados
    (código do primeiro admin) fica em seed.py."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
