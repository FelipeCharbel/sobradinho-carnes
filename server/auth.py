"""
Autenticação, hash de senha e sessão (token HMAC stateless). Ver docs/CONTRATOS.md §3 e §4.

Erros de negócio devem ser levantados como ErroNegocio(mensagem) (ou exceção equivalente que
main.py sabe traduzir em {"erro": mensagem}) — nunca deixar vazar stack trace.
"""
import hashlib
import base64
import hmac
import json
import time
import re
import uuid
import os
import random
from datetime import datetime
from sqlalchemy.orm import Session
from server.models import Usuario, Registro, Configuracao

VOLTAS_HASH = 600
SESSAO_SEGUNDOS = 1800
MAX_TENTATIVAS = 5
BLOQUEIO_SEGUNDOS = 900


class ErroNegocio(Exception):
    """Exceção de negócio: a mensagem vai direto para {"erro": str(e)} na resposta HTTP."""


def hash_senha_(senha: str, salt: str) -> str:
    """Port fiel de hashSenha_ (.gs linha 220): h = salt+":"+senha; repetir VOLTAS_HASH=600 vezes
    h = base64(sha256((h+salt).encode("utf-8"))). Devolve h (string base64). Precisa ser
    byte-a-byte compatível para usuários migrados da planilha continuarem entrando."""
    h = salt + ":" + senha
    for _ in range(VOLTAS_HASH):
        h_bytes = hashlib.sha256((h + salt).encode("utf-8")).digest()
        h = base64.b64encode(h_bytes).decode("utf-8")
    return h


def igual_(a: str, b: str) -> bool:
    """Comparação em tempo constante (substitui o XOR manual do .gs linha 225). Usar
    hmac.compare_digest(a, b)."""
    return hmac.compare_digest(a, b)


def email_ok_(email: str) -> bool:
    """Port de emailOk_ (.gs linha 226): regex simples de e-mail."""
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def criar_token(email: str, secret: str) -> str:
    """Token HMAC stateless (CONTRATOS.md §3): payload = {"email": email, "exp": now+1800}
    (SESSAO_SEGUNDOS). Formato "<payload_b64>.<assinatura_b64>", assinatura = HMAC-SHA256(payload_b64,
    secret)."""
    payload = {"email": email, "exp": int(time.time()) + SESSAO_SEGUNDOS}
    payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    payload_b64 = base64.b64encode(payload_json.encode("utf-8")).decode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    signature_b64 = base64.b64encode(signature).decode("utf-8")
    return f"{payload_b64}.{signature_b64}"


def _validar_token_(token: str, secret: str) -> dict:
    """Valida assinatura e expiração do token. Retorna payload dict ou None se inválido."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature_b64 = parts
        # Verifica assinatura
        expected_sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
        expected_sig_b64 = base64.b64encode(expected_sig).decode("utf-8")
        if not igual_(signature_b64, expected_sig_b64):
            return None
        # Decodifica payload
        payload_json = base64.b64decode(payload_b64).decode("utf-8")
        payload = json.loads(payload_json)
        # Verifica expiração
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def sessao_(token: str, db: Session, secret: str) -> dict:
    """Port de sessao_ (.gs linha 275): valida assinatura e expiração do token; busca o usuário
    pelo email do payload; se não existe ou status != "Ativo", raise ErroNegocio("SESSAO"). Devolve
    {"email","nome","perfil","cargo","status"}. 'Renova a cada uso': quem chamar deve pedir um novo
    token (criar_token) para devolver ao cliente (main.py decide onde colocar — ver CONTRATOS.md §3)."""
    if not token:
        raise ErroNegocio("SESSAO")
    payload = _validar_token_(token, secret)
    if not payload:
        raise ErroNegocio("SESSAO")
    email = payload.get("email", "").lower()
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario or usuario.status != "Ativo":
        raise ErroNegocio("SESSAO")
    return {
        "email": usuario.email,
        "nome": usuario.nome,
        "perfil": usuario.perfil,
        "cargo": usuario.cargoId,
        "status": usuario.status
    }


def so_admin_(u: dict, o: str) -> None:
    """Port de soAdmin_ (.gs linha 283): se u['perfil'] != 'admin', registra no Registro
    ("Acesso negado: " + o) e raise ErroNegocio("NEGADO")."""
    if u.get("perfil") != "admin":
        raise ErroNegocio("NEGADO")


def login_(email: str, senha: str, db: Session, secret: str) -> dict:
    """Port de login_ (.gs linha 260): bloqueio após MAX_TENTATIVAS=5 erros (900s = 15min;
    persistir contador em tabela própria, já que não há CacheService — ver CONTRATOS.md §3),
    confere hash com igual_, confere status (Pendente/Inativo têm mensagens próprias), gera
    token, grava ultimoAcesso, registra em Registro ("Entrou na plataforma"). Devolve
    {"token","trocar","u":{email,nome,perfil,cargo,status}}."""
    from server.models import TentativaLogin

    email = email.strip().lower() if email else ""

    # Checa bloqueio por muitas tentativas (persistente)
    tentativa_login = db.query(TentativaLogin).filter(TentativaLogin.email == email).first()
    if tentativa_login and tentativa_login.bloqueado_ate:
        if datetime.utcnow() < tentativa_login.bloqueado_ate:
            raise ErroNegocio("Muitas tentativas. Aguarde 15 minutos e tente de novo.")

    # Verifica credenciais
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    certo = usuario and igual_(hash_senha_(str(senha or ""), usuario.salt), usuario.hash)

    if not certo:
        # Incrementa contador de tentativas
        if not tentativa_login:
            tentativa_login = TentativaLogin(email=email, contador=1, bloqueado_ate=None)
        else:
            tentativa_login.contador += 1

        if tentativa_login.contador >= MAX_TENTATIVAS:
            tentativa_login.bloqueado_ate = datetime.utcnow().replace(microsecond=0) + __import__('datetime').timedelta(seconds=BLOQUEIO_SEGUNDOS)

        db.add(tentativa_login)
        db.commit()
        raise ErroNegocio("E-mail ou senha incorretos.")

    # Credenciais corretas: reseta contador
    if tentativa_login:
        tentativa_login.contador = 0
        tentativa_login.bloqueado_ate = None
        db.add(tentativa_login)

    # Verifica status
    if usuario.status == "Pendente":
        raise ErroNegocio("Seu cadastro ainda aguarda aprovação do administrador.")
    if usuario.status != "Ativo":
        raise ErroNegocio("Seu acesso está desativado. Fale com o administrador.")

    # Gera token e registra
    token = criar_token(usuario.email, secret)
    usuario.ultimoAcesso = datetime.utcnow()
    db.add(usuario)
    db.add(Registro(
        quando=datetime.utcnow(),
        quem=usuario.nome,
        acao="Entrou na plataforma"
    ))
    db.commit()

    return {
        "token": token,
        "trocar": bool(usuario.trocarSenha),
        "u": {
            "email": usuario.email,
            "nome": usuario.nome,
            "perfil": usuario.perfil,
            "cargo": usuario.cargoId,
            "status": usuario.status
        }
    }


def primeiro_acesso_(d: dict, db: Session) -> dict:
    """Port de primeiroAcesso_ (.gs linha 228): valida nome/email/senha, confere código de admin
    de uso único, cria usuário Pendente (ou Ativo+admin se código certo), consome o código. Devolve
    {"admin": bool}."""
    nome = str(d.get("nome") or "").strip()
    email = str(d.get("email") or "").strip().lower()
    codigo = str(d.get("codigo") or "").strip()
    senha = str(d.get("senha") or "")
    senha2 = str(d.get("senha2") or "")

    if len(nome) < 3:
        raise ErroNegocio("Informe seu nome completo.")
    if not email_ok_(email):
        raise ErroNegocio("Informe um e-mail válido.")
    if len(senha) < 8:
        raise ErroNegocio("A senha precisa ter pelo menos 8 caracteres.")
    if senha != senha2:
        raise ErroNegocio("As duas senhas não são iguais.")

    # Checa se já existe usuário
    if db.query(Usuario).filter(Usuario.email == email).first():
        raise ErroNegocio("Não foi possível concluir. Se você já tem cadastro, use \"Entrar\".")

    # Checa código de admin: persistido no banco (não em env var -- não há processo único de
    # longa duração nem env var compartilhada entre invocações serverless, ver Configuracao em models.py)
    config_codigo = db.query(Configuracao).filter(Configuracao.chave == "ADMIN_CODIGO").first()
    admin_codigo = config_codigo.valor if config_codigo else ""
    admin = bool(codigo) and bool(admin_codigo) and igual_(codigo.upper(), admin_codigo)

    if codigo and not admin:
        raise ErroNegocio("Código de administrador inválido.")

    # Cria novo usuário
    salt = uuid.uuid4().hex
    usuario = Usuario(
        email=email,
        nome=nome,
        perfil="admin" if admin else "colaborador",
        cargoId="",
        cargoInformado="",
        cargoSolicitado="",
        status="Ativo" if admin else "Pendente",
        salt=salt,
        hash=hash_senha_(senha, salt),
        criadoEm=datetime.utcnow(),
        trocarSenha=""
    )
    db.add(usuario)
    db.add(Registro(
        quando=datetime.utcnow(),
        quem=nome,
        acao="Criou o acesso de administrador" if admin else "Pediu o primeiro acesso"
    ))

    # Consome código de admin (não pode ser usado novamente)
    if admin and config_codigo:
        db.delete(config_codigo)

    db.commit()
    return {"admin": admin}


def trocar_senha_(token: str, atual: str, nova: str, db: Session, secret: str) -> bool:
    """Port de trocarSenha_ (.gs linha 667). Confere senha atual, exige >=8 chars e diferente da
    atual, grava novo hash/salt e zera trocarSenha. NÃO devolve snapshot (ver CONTRATOS.md §1.2
    nota #18) — api_trocarSenha usa resp_, não mudar_."""
    u = sessao_(token, db, secret)
    usuario = db.query(Usuario).filter(Usuario.email == u["email"]).first()

    if not usuario or not igual_(hash_senha_(str(atual or ""), usuario.salt), usuario.hash):
        raise ErroNegocio("A senha atual não confere.")
    if len(str(nova or "")) < 8:
        raise ErroNegocio("A nova senha precisa ter pelo menos 8 caracteres.")
    if nova == atual:
        raise ErroNegocio("Escolha uma senha diferente da atual.")

    novo_salt = uuid.uuid4().hex
    usuario.salt = novo_salt
    usuario.hash = hash_senha_(str(nova), novo_salt)
    usuario.trocarSenha = ""
    db.add(usuario)
    db.add(Registro(
        quando=datetime.utcnow(),
        quem=usuario.nome,
        acao="Trocou a própria senha"
    ))
    db.commit()
    return True


def redefinir_senha_(token: str, email: str, db: Session, secret: str) -> dict:
    """Port de redefinirSenha_ (.gs linha 676): só admin; gera senha provisória de 10 chars de um
    alfabeto sem ambíguos, marca trocarSenha=1, zera bloqueio de tentativas do e-mail alvo. Devolve
    {"provisoria","nome"}."""
    u = sessao_(token, db, secret)
    so_admin_(u, "redefinir senha")

    alvo = db.query(Usuario).filter(Usuario.email == email.lower()).first()
    if not alvo:
        raise ErroNegocio("Usuário não encontrado.")

    # Gera senha provisória
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    provisoria = "".join(random.choice(alfabeto) for _ in range(10))

    novo_salt = uuid.uuid4().hex
    alvo.salt = novo_salt
    alvo.hash = hash_senha_(provisoria, novo_salt)
    alvo.trocarSenha = "1"
    db.add(alvo)
    db.add(Registro(
        quando=datetime.utcnow(),
        quem=u["nome"],
        acao=f"Redefiniu a senha de {alvo.nome}"
    ))
    db.commit()

    return {"provisoria": provisoria, "nome": alvo.nome}
