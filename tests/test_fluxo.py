"""
Agente A: testes de auth/regras de acesso. Casos mínimos exigidos:

1. Login com senha errada 5 vezes seguidas bloqueia por 15 min (MAX_TENTATIVAS, .gs linha 263);
   a 6ª tentativa (mesmo com senha certa) deve falhar com "Muitas tentativas...".
2. Perfil colaborador não recebe a chave 'entrevistas' nem 'diag' no retrato (retrato_ só monta
   essas chaves para admin/socio -- CONTRATOS.md §7).
3. Tentar ligar um cargo abaixo dele mesmo (ciclo) em definirSuperior_/salvarCargos_/
   salvarOrganograma_ deve levantar erro, sem gravar nada.
"""
import os
import pytest
import tempfile
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret"

from server.db import init_db
from server.models import Base, Usuario, Cargo, Tobe, TobeHistorico, TobeVersao
from server.auth import hash_senha_, ErroNegocio, login_, primeiro_acesso_, sessao_, criar_token
from server.modelo import carregar_, modelo_, retrato_
from server.handlers_admin import (
    definirSuperior_, salvarCargos_, salvarOrganograma_, fazCiclo_,
    salvarEntrevista_, publicar_, validarConteudo,
)
from server.handlers_tobe import (
    tobeAdmin_, tobeSalvar_, tobeJustificar_, tobeResolver_, tobePublicar_,
    sincronizarTobe_, visualizarComo_,
)


@pytest.fixture
def db():
    """Cria um banco SQLite em memória para cada teste."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    return session


def test_login_bloqueio_5_tentativas(db):
    """Teste 1: Login bloqueado após 5 tentativas erradas."""
    # Cria usuário de teste
    salt = "testsalt123456"
    senha = "senha1234"
    usuario = Usuario(
        email="teste@example.com",
        nome="Teste User",
        perfil="admin",
        status="Ativo",
        salt=salt,
        hash=hash_senha_(senha, salt),
        criadoEm=datetime.utcnow()
    )
    db.add(usuario)
    db.commit()

    # Tenta login com senha errada 5 vezes
    for i in range(5):
        with pytest.raises(ErroNegocio, match="E-mail ou senha incorretos"):
            login_("teste@example.com", "senhaerrada", db, "test-secret")

    # A 6ª tentativa, mesmo com a senha CERTA, deve falhar com a mensagem de bloqueio:
    # no .gs (linha 263) a checagem de tentativas vem antes da checagem de senha, então o
    # bloqueio de 15 min vale mesmo se a próxima tentativa acertar a senha.
    with pytest.raises(ErroNegocio, match="Muitas tentativas. Aguarde 15 minutos e tente de novo."):
        login_("teste@example.com", senha, db, "test-secret")


def test_colaborador_sem_entrevistas_ni_diag(db):
    """Teste 2: Colaborador não recebe 'entrevistas' nem 'diag' no retrato."""
    # Cria admin
    salt_admin = "salt-admin"
    admin = Usuario(
        email="admin@example.com",
        nome="Admin",
        perfil="admin",
        status="Ativo",
        salt=salt_admin,
        hash=hash_senha_("admin1234", salt_admin),
        criadoEm=datetime.utcnow()
    )

    # Cria cargo
    cargo = Cargo(
        id="cargo-001",
        nome="Gerente",
        area="RH",
        pessoa="João",
        status="publicado",
        missao="Gerenciar"
    )

    # Cria colaborador
    salt_colab = "salt-colab"
    colaborador = Usuario(
        email="colab@example.com",
        nome="Colaborador",
        perfil="colaborador",
        cargoId="cargo-001",
        status="Ativo",
        salt=salt_colab,
        hash=hash_senha_("colab1234", salt_colab),
        criadoEm=datetime.utcnow()
    )

    db.add(admin)
    db.add(cargo)
    db.add(colaborador)
    db.commit()

    # Carrega dados
    D = carregar_(db)

    # Cria sessão de colaborador
    u_colab = {"email": "colab@example.com", "nome": "Colaborador", "perfil": "colaborador", "cargo": "cargo-001", "status": "Ativo"}

    # Gera retrato do colaborador
    retrato = retrato_(D, u_colab)

    # Verifica que colaborador NÃO tem 'entrevistas'
    assert "entrevistas" not in retrato, "Colaborador não deve receber 'entrevistas'"

    # Verifica que colaborador NÃO tem 'diag'
    assert "diag" not in retrato, "Colaborador não deve receber 'diag'"

    # Admin deve ter ambos
    u_admin = {"email": "admin@example.com", "nome": "Admin", "perfil": "admin", "cargo": None, "status": "Ativo"}
    retrato_admin = retrato_(D, u_admin)
    assert "entrevistas" in retrato_admin, "Admin deve receber 'entrevistas'"
    assert "diag" in retrato_admin, "Admin deve receber 'diag'"


def test_ciclo_organograma_rejeitado(db):
    """Teste 3: Ciclo no organograma é rejeitado sem gravar nada."""
    # Cria 3 cargos: A -> B -> C
    cargo_a = Cargo(id="a", nome="A", area="Area1", pessoa="")
    cargo_b = Cargo(id="b", nome="B", area="Area1", pessoa="", pai="a")
    cargo_c = Cargo(id="c", nome="C", area="Area1", pessoa="", pai="b")

    db.add(cargo_a)
    db.add(cargo_b)
    db.add(cargo_c)
    db.commit()

    # Testa fazCiclo_
    paiDe = {"a": "", "b": "a", "c": "b"}

    # Sem ciclo: C -> D é válido
    assert not fazCiclo_("c", "d", paiDe)

    # Com ciclo: B -> C criaria B -> C -> B
    assert fazCiclo_("b", "c", paiDe)

    # Com ciclo: A -> B criaria A -> B -> A
    assert fazCiclo_("a", "b", paiDe)

    # Testa salvarCargos com tentativa de ciclo
    salt = "salt"
    admin = Usuario(
        email="admin@test.com",
        nome="Admin",
        perfil="admin",
        status="Ativo",
        salt=salt,
        hash=hash_senha_("pass1234", salt),
        criadoEm=datetime.utcnow()
    )
    db.add(admin)
    db.commit()

    # Token de sessão válido (sem passar pelo fluxo completo de login_)
    token = criar_token("admin@test.com", "test-secret")

    # Tenta criar ciclo: A passaria a responder a B, mas B já está abaixo de A (A -> B -> A)
    lista_ciclo = [{"id": "a", "nome": "A", "area": "Area1", "pessoa": "", "pai": "b"}]

    with pytest.raises(ErroNegocio, match="cargo não pode ficar abaixo"):
        salvarCargos_(token, lista_ciclo, db, "test-secret")

    # Nada foi gravado: o pai de "a" continua vazio (nada mudou por causa do ciclo rejeitado)
    cargo_a_check = db.query(Cargo).filter(Cargo.id == "a").first()
    assert not cargo_a_check.pai


def test_tobe_fluxo_basico(db):
    """Teste 4 (TO BE): iniciar, editar com personalização, conflito com o AS IS,
    resolver o conflito, justificar, publicar e visualizarComo_."""
    salt = "salt"
    admin = Usuario(
        email="admin@test.com", nome="Admin", perfil="admin", status="Ativo",
        salt=salt, hash=hash_senha_("pass1234", salt), criadoEm=datetime.utcnow(),
    )
    cargo = Cargo(id="x1", nome="Analista", area="TI", pessoa="", missao="Missão original", status="publicado")
    db.add(admin)
    db.add(cargo)
    db.commit()

    token = criar_token("admin@test.com", "test-secret")
    u = tobeAdmin_(token, "ver o TO BE", db, "test-secret")

    # Iniciar copia o AS IS inteiro
    tobe_x1 = db.query(Tobe).filter(Tobe.id == "x1").first()
    assert tobe_x1 is not None
    assert tobe_x1.origem == "asis"

    # Editar nome e missão no TO BE -> personaliza os dois campos
    r = tobeSalvar_(u, {"alteracoes": [
        {"id": "x1", "nome": "Analista Sênior", "area": "TI", "pessoa": "",
         "conteudo": {"missao": "Nova missão personalizada no TO BE"}}
    ]}, db)
    assert r["n"] == 1
    lote1 = r["lote"]
    db.commit()

    tobe_x1 = db.query(Tobe).filter(Tobe.id == "x1").first()
    import json as _json
    assert "nome" in _json.loads(tobe_x1.personalizado)
    assert "missao" in _json.loads(tobe_x1.personalizado)
    assert tobe_x1.nome == "Analista Sênior"

    pendentes = db.query(TobeHistorico).filter(TobeHistorico.lote == lote1).all()
    assert len(pendentes) == 2
    assert all(h.status == "Pendente de justificativa" for h in pendentes)

    # Justificar o lote
    rj = tobeJustificar_(u, {"lote": lote1}, "Ajuste combinado com a diretoria.", db)
    assert rj["n"] == 2
    db.commit()
    assert all(h.status == "Justificada" for h in db.query(TobeHistorico).filter(TobeHistorico.lote == lote1).all())

    # AS IS muda o MESMO campo personalizado ("nome") -> gera conflito, não sobrescreve
    cargo_as_is = db.query(Cargo).filter(Cargo.id == "x1").first()
    cargo_as_is.nome = "Analista Pleno (AS IS)"
    db.commit()
    sincronizarTobe_("Admin", db)
    db.commit()

    tobe_x1 = db.query(Tobe).filter(Tobe.id == "x1").first()
    conflitos = _json.loads(tobe_x1.conflito)
    assert any(c["campo"] == "nome" for c in conflitos)
    # o valor do TO BE não foi sobrescrito pela sincronização
    assert tobe_x1.nome == "Analista Sênior"

    # Resolve o conflito aceitando o valor do AS IS
    assert tobeResolver_(u, "x1", "nome", "aceitar", "", db) is True
    db.commit()
    tobe_x1 = db.query(Tobe).filter(Tobe.id == "x1").first()
    assert tobe_x1.nome == "Analista Pleno (AS IS)"
    assert "nome" not in _json.loads(tobe_x1.personalizado)
    assert not any(c["campo"] == "nome" for c in _json.loads(tobe_x1.conflito))

    # Publicar versão 1
    rp = tobePublicar_(u, {"confirmar": True, "nota": "Primeira versão"}, db)
    assert rp["versao"] == 1
    db.commit()
    assert db.query(TobeVersao).count() == 1

    # Publicar de novo sem mudanças -> erro
    with pytest.raises(ErroNegocio, match="Nada mudou desde a última versão."):
        tobePublicar_(u, {"confirmar": True}, db)

    # visualizarComo_ colaborador do mesmo cargo: não deve ter entrevistas/diag
    vc = visualizarComo_({"perfil": "colaborador", "cargoId": "x1"}, db)
    assert vc["perfil"] == "colaborador"
    assert "entrevistas" not in vc["retrato"]
    assert "diag" not in vc["retrato"]
    assert vc["cargo"]["id"] == "x1"


def test_validarConteudo_exige_ao_menos_uma_funcao():
    """validarConteudo (.gs linha 1273) precisa recusar conteúdo sem nenhuma função."""
    with pytest.raises(ErroNegocio, match="Inclua pelo menos uma função."):
        validarConteudo({"missao": "Teste", "funcoes": [], "rotinas": []})


def test_salvar_entrevista_e_publicar(db):
    """Teste 5: salvar entrevista (texto já estruturado), publicar e checar visibilidade."""
    salt = "salt"
    admin = Usuario(
        email="admin@test.com", nome="Admin", perfil="admin", status="Ativo",
        salt=salt, hash=hash_senha_("pass1234", salt), criadoEm=datetime.utcnow(),
    )
    cargo = Cargo(id="x2", nome="Conferente", area="Logística", pessoa="Fulano")
    db.add(admin)
    db.add(cargo)
    db.commit()

    token = criar_token("admin@test.com", "test-secret")

    d = {
        "cargoId": "x2",
        "pessoa": "Fulano",
        "data": "01/01/2026",
        "missao": "Conferir as mercadorias recebidas para garantir a exatidão do estoque.",
        "funcoes": ["Conferir o ponto", "Receber as mercadorias"],
        "rotinas": [{"f": "Diária", "t": "Confirmar o recebimento no sistema"}],
        "publicar": False,
    }
    r = salvarEntrevista_(token, d, db, "test-secret")
    assert r == {"id": "x2"}
    db.commit()

    cargo_bd = db.query(Cargo).filter(Cargo.id == "x2").first()
    assert cargo_bd.status == "revisao"
    assert cargo_bd.revisao == 0

    # Publicar exige missão (já tem) e estilo sem violação (funções já no infinitivo)
    assert publicar_(token, "x2", True, db, "test-secret") is True
    db.commit()
    cargo_bd = db.query(Cargo).filter(Cargo.id == "x2").first()
    assert cargo_bd.status == "publicado"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
