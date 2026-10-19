"""
As 9 tabelas = as 9 ABAS do Codigo.gs (linhas 11-21). Colunas e ordem idênticas ao original.
Ver docs/CONTRATOS.md §2 para o detalhe de cada coluna, tipo e observações (campos JSON-TEXT etc.).

Nomes de TABELA devem ser literalmente "Cargos", "Entrevistas", "Usuarios", "Propostas",
"Solicitacoes", "Registro", "Tobe", "TobeHistorico", "TobeVersoes" (__tablename__), para bater
1:1 com a planilha original. Nomes de CLASSE são livres (sugestão: Cargo, Entrevista, Usuario,
Proposta, Solicitacao, Registro, Tobe, TobeHistorico, TobeVersao).

Campos JSON-TEXT (funcoes, rotinas, habilidades, relacoes, ferramentas, historico, respostas, auto,
base, personalizado, conflito, snapshot): guardar como Text/String contendo json.dumps(...) — nunca
tipo JSON nativo do Postgres. Ler/escrever esses campos sempre via json.loads/json.dumps nos módulos
que os usam (modelo.py, handlers_admin.py, handlers_tobe.py), não aqui.
"""
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean, ForeignKey
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Cargo(Base):
    __tablename__ = "Cargos"
    id = Column(String, primary_key=True)
    nome = Column(String, nullable=False)
    area = Column(String, nullable=False)
    pai = Column(String, nullable=True)
    pessoa = Column(String, nullable=False)
    missao = Column(Text, default="")
    funcoes = Column(Text, default="")  # JSON-TEXT
    rotinas = Column(Text, default="")  # JSON-TEXT
    jornada = Column(Text, default="")
    tempoEmpresa = Column(String, default="")
    formacao = Column(String, default="")
    experiencia = Column(String, default="")
    habilidades = Column(Text, default="")  # JSON-TEXT
    relacoes = Column(Text, default="")  # JSON-TEXT
    recorre = Column(String, default="")
    ferramentas = Column(Text, default="")  # JSON-TEXT
    status = Column(String, default="")  # "", "revisao", "publicado"
    entrevistaId = Column(Integer, nullable=True)
    revisao = Column(Integer, default=0)
    historico = Column(Text, default="")  # JSON-TEXT
    x = Column(Integer, nullable=True)
    y = Column(Integer, nullable=True)

class Entrevista(Base):
    __tablename__ = "Entrevistas"
    id = Column(Integer, primary_key=True)
    cargoId = Column(String, nullable=False)
    pessoa = Column(String, nullable=False)
    data = Column(String, default="")
    link = Column(String, default="")
    auto = Column(Text, default="")  # JSON-TEXT
    registradoPor = Column(String, default="")
    registradoEm = Column(DateTime, nullable=True)
    respostas = Column(Text, default="")  # JSON-TEXT

class Usuario(Base):
    __tablename__ = "Usuarios"
    email = Column(String, primary_key=True)
    nome = Column(String, nullable=False)
    perfil = Column(String, nullable=False)  # admin|socio|gestor|colaborador
    cargoId = Column(String, nullable=True)
    cargoInformado = Column(String, default="")
    cargoSolicitado = Column(String, nullable=True)
    status = Column(String, nullable=False)  # Ativo|Pendente|Inativo
    salt = Column(String, nullable=False)
    hash = Column(String, nullable=False)
    criadoEm = Column(DateTime, nullable=False)
    ultimoAcesso = Column(DateTime, nullable=True)
    trocarSenha = Column(String, default="")  # "", "1"

class Proposta(Base):
    __tablename__ = "Propostas"
    id = Column(String, primary_key=True)
    tipo = Column(String, default="")
    cargoId = Column(String, default="")
    nome = Column(String, default="")
    area = Column(String, default="")
    pai = Column(String, default="")
    de = Column(String, default="")
    para = Column(String, default="")
    motivo = Column(String, default="")
    fonte = Column(String, default="")

class Solicitacao(Base):
    __tablename__ = "Solicitacoes"
    id = Column(String, primary_key=True)
    cargoId = Column(String, nullable=False)
    origemId = Column(String, default="")
    texto = Column(String, default="")
    motivo = Column(String, default="")
    status = Column(String, nullable=False)  # Aberta|Concluída|Recusada|Aprovada
    criadoPor = Column(String, default="")
    criadoPorEmail = Column(String, default="")
    criadoEm = Column(DateTime, nullable=False)
    resolvidoPor = Column(String, default="")
    resolvidoEm = Column(DateTime, nullable=True)
    resposta = Column(String, default="")
    tipo = Column(String, default="")  # "", "correcao-cargo"
    cargoSugerido = Column(String, nullable=True)

class Registro(Base):
    __tablename__ = "Registro"
    id = Column(Integer, primary_key=True, autoincrement=True)
    quando = Column(DateTime, nullable=False)
    quem = Column(String, nullable=False)
    acao = Column(String, nullable=False)

class Tobe(Base):
    __tablename__ = "Tobe"
    id = Column(String, primary_key=True)
    nome = Column(String, nullable=False)
    area = Column(String, nullable=False)
    pai = Column(String, default="")
    pessoa = Column(String, default="")
    missao = Column(Text, default="")
    funcoes = Column(Text, default="")  # JSON-TEXT
    rotinas = Column(Text, default="")  # JSON-TEXT
    jornada = Column(Text, default="")
    tempoEmpresa = Column(String, default="")
    formacao = Column(String, default="")
    experiencia = Column(String, default="")
    habilidades = Column(Text, default="")  # JSON-TEXT
    relacoes = Column(Text, default="")  # JSON-TEXT
    recorre = Column(String, default="")
    ferramentas = Column(Text, default="")  # JSON-TEXT
    x = Column(Integer, nullable=True)
    y = Column(Integer, nullable=True)
    origem = Column(String, default="tobe")  # asis|tobe
    base = Column(Text, default="")  # JSON-TEXT
    personalizado = Column(Text, default="")  # JSON-TEXT
    conflito = Column(Text, default="")  # JSON-TEXT
    removido = Column(Boolean, default=False)

class TobeHistorico(Base):
    __tablename__ = "TobeHistorico"
    id = Column(String, primary_key=True)
    quando = Column(DateTime, nullable=False)
    quem = Column(String, default="")
    origem = Column(String, default="")  # sync|manual|ajuste|publicacao
    cargoId = Column(String, default="")
    cargoNome = Column(String, default="")
    campo = Column(String, default="")
    antes = Column(Text, default="")
    depois = Column(Text, default="")
    descricao = Column(String, default="")
    justificativa = Column(String, default="")
    status = Column(String, default="")  # Automática|Pendente de justificativa|Justificada
    justificadoEm = Column(DateTime, nullable=True)
    justificadoPor = Column(String, default="")
    lote = Column(String, default="")

class TobeVersao(Base):
    __tablename__ = "TobeVersoes"
    versao = Column(Integer, primary_key=True)
    publicadoEm = Column(DateTime, nullable=False)
    por = Column(String, nullable=False)
    nota = Column(String, default="")
    snapshot = Column(Text, default="")  # JSON-TEXT

class TentativaLogin(Base):
    __tablename__ = "TentativasLogin"
    email = Column(String, primary_key=True)
    contador = Column(Integer, default=0)
    bloqueado_ate = Column(DateTime, nullable=True)


class Configuracao(Base):
    """Substitui PropertiesService.getScriptProperties() do .gs: chave/valor persistente no
    banco (necessário porque não há processo único de longa duração nem env var compartilhada
    entre invocações serverless). Hoje guarda só a chave "ADMIN_CODIGO"."""
    __tablename__ = "Configuracao"
    chave = Column(String, primary_key=True)
    valor = Column(String, default="")
