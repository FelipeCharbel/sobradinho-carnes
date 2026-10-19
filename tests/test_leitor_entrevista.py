"""
Testes para leitor.py - leitura de entrevista colada (lerTexto) e leitura por link do Docs
(lerEntrevista_ em handlers_admin.py).
"""

import urllib.error
from unittest.mock import patch, MagicMock

import pytest
from server.leitor import lerTexto, norm


TEXTO_WELL = """Roteiro de Entrevista

Nome: Well
Cargo: Gestor de Compras
Tempo de empresa: 9 anos
Dia/horário de trabalho: Segunda a sexta, das 8h às 18h
Data da entrevista: 15/01/2026

1. Qual é o objetivo final do seu cargo? Por que ele existe?
Garantir o melhor abastecimento de carnes com o menor custo e alta qualidade.

3. Quais são as funções atuais do seu cargo?
Negociar preços com frigoríficos; Acompanhar cotações do boi gordo; Gerir equipe de compras.

4. Quais são as rotinas do seu cargo?
Diárias: Verificar estoque e cotações do dia.
Semanais: Reunião com fornecedores.
Mensais: Fechamento das compras do mês.
"""


class TestNorm:
    """A causa raiz do bug relatado: norm() chamava .normalize() como se fosse método de str
    (JavaScript), que não existe em Python. O correto é unicodedata.normalize("NFD", s)."""

    def test_norm_nao_quebra_com_acento(self):
        assert norm("Gestão") == "gestao"

    def test_norm_minusculo_sem_espaco(self):
        assert norm("  Gestor de Compras  ") == "gestor de compras"

    def test_norm_aceita_none(self):
        assert norm(None) == ""


class TestLerTextoCasoReal:
    """Caso real relatado pelo usuário: entrevista do Well, Gestor de Compras."""

    def test_le_sem_lancar_excecao(self):
        # Antes da correção, qualquer chamada aqui disparava
        # AttributeError: 'str' object has no attribute 'normalize'
        r = lerTexto(TEXTO_WELL, [])
        assert r is not None

    def test_pessoa_e_cargo(self):
        r = lerTexto(TEXTO_WELL, [])
        assert r["pessoa"] == "Well"
        assert r["cargoNome"] == "Gestor de Compras"

    def test_tempo_de_empresa(self):
        r = lerTexto(TEXTO_WELL, [])
        assert "9 anos" in r["tempoEmpresa"]

    def test_missao_formalizada(self):
        r = lerTexto(TEXTO_WELL, [])
        assert "abastecimento de carnes" in r["missao"]

    def test_funcoes_populadas(self):
        r = lerTexto(TEXTO_WELL, [])
        assert len(r["funcoes"]) == 3
        assert any("frigor" in f.lower() for f in r["funcoes"])

    def test_rotinas_populadas_por_frequencia(self):
        r = lerTexto(TEXTO_WELL, [])
        freqs = {x["f"] for x in r["rotinas"]}
        assert "Diária" in freqs
        assert "Semanal" in freqs
        assert "Mensal" in freqs
        assert len(r["rotinas"]) == 3

    def test_sugestao_casa_cargo_existente(self):
        cargos = [{"id": "c1", "nome": "Gestor de Compras", "pessoa": "Welington"}]
        r = lerTexto(TEXTO_WELL, cargos)
        assert r["sugestao"] == "c1"


class TestLerEntrevistaDocsLink:
    """lerEntrevista_ deve aceitar um link do Google Docs, extrair o doc_id e
    tentar baixar o texto via export público antes de reclamar de texto vazio."""

    def test_link_invalido_da_mensagem_clara(self):
        from server.handlers_admin import _baixarTextoDocs_
        from server.auth import ErroNegocio

        with pytest.raises(ErroNegocio):
            _baixarTextoDocs_("https://exemplo.com/nao-e-docs")

    def test_link_sem_acesso_anonimo_da_mensagem_clara(self):
        from server.handlers_admin import _baixarTextoDocs_
        from server.auth import ErroNegocio

        # Sem acesso anônimo (403/404/timeout): deve falhar com mensagem amigável,
        # nunca com AttributeError ou traceback cru.
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            "url", 403, "Forbidden", {}, None
        )):
            with pytest.raises(ErroNegocio) as exc:
                _baixarTextoDocs_("https://docs.google.com/document/d/abc123XYZ/edit")
        assert "cole" in str(exc.value).lower() or "texto" in str(exc.value).lower()

    def test_link_com_acesso_baixa_e_le_texto(self):
        from server.handlers_admin import _baixarTextoDocs_

        resp = MagicMock()
        resp.read.return_value = TEXTO_WELL.encode("utf-8")
        resp.__enter__.return_value = resp
        with patch("urllib.request.urlopen", return_value=resp):
            texto = _baixarTextoDocs_("https://docs.google.com/document/d/abc123XYZ/edit")
        r = lerTexto(texto, [])
        assert r["pessoa"] == "Well"
