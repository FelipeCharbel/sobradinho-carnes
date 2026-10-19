"""
Port LITERAL para Python do motor de redação do Codigo.gs (linhas ~1290-1854). Fidelidade total:
nenhuma regra nova, nenhuma simplificação. As regex JS com lookbehind/regex patterns devem usar o
módulo `regex` (nao o `re` built-in).

Expor publicamente (outros modulos importam estes nomes EXATOS, ver CONTRATOS.md secao 7/8):
FREQS, PARES, ajustaFuncao, ajustaRotina, violacoesEstilo, mensagemEstilo, formalizar,
formalizarMissao, missaoFormal, formalizarJornada, recorreItens, recorreNormaliza,
capitalizaNomes2, defineNomes, resumoAjuste, avisoAjuste, ajustaFuncoes, ajustaRotinas.

Cada funcao abaixo cita a linha do .gs correspondente.
"""

import regex
import unicodedata
from typing import Optional, Any

# .gs linha 1272: Object.keys(FREQ_INFO)
FREQS = ["Diária", "Semanal", "Quinzenal", "Mensal", "Trimestral", "Semestral", "Anual", "Sob demanda"]

# .gs linha 1294: Lista PARES [verbo, substantivo, preposição, mantemPreposicao?]
PARES = [
    ["Verificar","Verificação","de"],["Conferir","Conferência","de"],["Registrar","Registro","de"],["Emitir","Emissão","de"],["Lançar","Lançamento","de"],["Receber","Recebimento","de"],
    ["Pagar","Pagamento","de"],["Agendar","Agendamento","de"],["Cobrar","Cobrança","de"],["Orientar","Orientação","de"],["Treinar","Treinamento","de"],["Analisar","Análise","de"],
    ["Apurar","Apuração","de"],["Classificar","Classificação","de"],["Entregar","Entrega","de"],["Programar","Programação","de"],["Preencher","Preenchimento","de"],["Coletar","Coleta","de"],
    ["Esclarecer","Esclarecimento","de"],["Fechar","Fechamento","de"],["Abrir","Abertura","de"],["Monitorar","Monitoramento","de"],["Distribuir","Distribuição","de"],["Comprar","Compra","de"],
    ["Vender","Venda","de"],["Investigar","Investigação","de"],["Criar","Criação","de"],["Levantar","Levantamento","de"],["Representar","Representação","de"],["Elaborar","Elaboração","de"],
    ["Organizar","Organização","de"],["Definir","Definição","de"],["Aprovar","Aprovação","de"],["Coordenar","Coordenação","de"],["Conduzir","Condução","de"],["Acompanhar","Acompanhamento","de"],
    ["Controlar","Controle","de"],["Planejar","Planejamento","de"],["Manter","Manutenção","de"],["Garantir","Garantia","de"],["Negociar","Negociação","de"],["Realizar","Realização","de"],
    ["Executar","Execução","de"],["Atender","Atendimento","a"],["Apoiar","Apoio","a"],["Auxiliar","Auxílio","a"],["Visitar","Visita","a"],["Enviar","Envio","de"],["Atualizar","Atualização","de"],
    ["Arquivar","Arquivo","de"],["Conciliar","Conciliação","de"],["Antecipar","Antecipação","de"],["Acionar","Acionamento","de"],["Solicitar","Solicitação","de"],["Cadastrar","Cadastro","de"],
    ["Autorizar","Autorização","de"],["Fiscalizar","Fiscalização","de"],["Cotar","Cotação","de"],["Higienizar","Higienização","de"],["Inspecionar","Inspeção","de"],["Publicar","Publicação","de"],
    ["Triar","Triagem","de"],["Recrutar","Recrutamento","de"],["Selecionar","Seleção","de"],["Contratar","Contratação","de"],["Admitir","Admissão","de"],["Desligar","Desligamento","de"],
    ["Integrar","Integração","de"],["Repor","Reposição","de"],["Separar","Separação","de"],["Etiquetar","Etiquetagem","de"],["Embalar","Embalagem","de"],["Desossar","Desossa","de"],
    ["Prospectar","Prospecção","de"],["Gerir","Gestão","de"],["Avaliar","Avaliação","de"],["Corrigir","Correção","de"],["Substituir","Substituição","de"],["Renovar","Renovação","de"],
    ["Elaborar","Elaboração","de"],["Gerar","Geração","de"],["Informar","Informação","de"],["Comunicar-se","Comunicação","com",1],["Responder","Responsabilidade","por",1],["Dar baixa","Baixa","em"],
    ["Fazer a gestão","Gestão","de"],["Fazer o controle","Controle","de"],["Efetuar","Efetivação","de"],["Providenciar","Providência","de"],["Tratar","Tratamento","de"],["Atuar","Atuação","em"],
    ["Estruturar","Estruturação","de"],["Implantar","Implantação","de"],["Resolver","Resolução","de"],["Medir","Medição","de"],["Consolidar","Consolidação","de"],["Cumprir","Cumprimento","de"],["Cuidar","Cuidado","com"],["Alterar","Alteração","de"],["Reunir","Reunião","de"],["Liberar","Liberação","de"],["Pesar","Pesagem","de"],["Apresentar","Apresentação","de"],["Combinar","Combinação","de"],
    ["Montar","Montagem","de"],["Pedir","Pedido","de"],["Digitar","Digitação","de"],["Administrar","Administração","de"],["Instalar","Instalação","de"],["Configurar","Configuração","de"],["Trocar","Troca","de"],
    ["Produzir","Produção","de"],["Marcar","Marcação","de"],["Revisar","Revisão","de"],["Projetar","Projeção","de"],["Lavar","Lavagem","de"],["Limpar","Limpeza","de"],["Abrir","Abertura","de"],["Responsabilizar-se","Responsabilização","por",1]
]

def sem(s: str) -> str:
    """Remove acentos e converte para minúsculo."""
    if not s:
        return ""
    s = unicodedata.normalize("NFD", str(s or ""))
    s = regex.sub(r"[\p{M}]", "", s, flags=regex.UNICODE)
    return s.lower().strip()

def maiuscula(s: str) -> str:
    """Primeira letra maiúscula."""
    if not s:
        return s
    return s[0].upper() + s[1:] if len(s) > 1 else s.upper()

# .gs linha 1314-1316: Mapas de PARES
_MAPA_V = {}
_MAPA_N = {}

for p in PARES:
    v, n, prep = p[0], p[1], p[2]
    k_sem_v = sem(v)
    k_sem_n = sem(n)
    if k_sem_v not in _MAPA_V:
        _MAPA_V[k_sem_v] = {"v": v, "n": n, "p": prep, "k": bool(len(p) > 3 and p[3])}
    if k_sem_n not in _MAPA_N or len(v.split()) == 1:
        _MAPA_N[k_sem_n] = {"v": v, "n": n, "p": prep, "k": bool(len(p) > 3 and p[3])}

# .gs linha 1317: VERBOS_COMUNS
VERBOS_COMUNS = ["Fazer","Ir","Ligar","Mandar","Buscar","Pegar","Ajudar","Anotar","Avisar","Ver","Falar","Passar","Procurar","Responder","Separar","Somar","Subir","Baixar","Imprimir","Assinar","Contar","Entrar","Sair","Cuidar","Usar","Lembrar","Chamar","Cobrar","Deixar","Mostrar","Entender","Resolver","Atender","Participar","Acompanhar","Ler","Escrever","Contratar","Pagar","Receber","Conferir","Anexar","Digitalizar","Escanear","Reservar","Solicitar","Aprovar","Cancelar","Devolver","Guardar","Fiscalizar","Orientar","Planejar"]

# .gs linha 1319: PRESENTE_IRREG
PRESENTE_IRREG = {"faz":"fazer", "vai":"ir", "da":"dar", "tem":"ter", "ve":"ver", "vem":"vir", "poe":"pôr", "le":"ler", "sai":"sair", "ouve":"ouvir", "pede":"pedir", "mede":"medir", "diz":"dizer", "traz":"trazer", "repoe":"repor"}

# .gs linha 1320-1321: PRESENTE3 map (construído dinamicamente)
_PRESENTE3 = {}

def _inicializa_presente3():
    """Constrói PRESENTE3 a partir de infinitivos conhecidos."""
    for v in _infinitivos_conhecidos():
        b = sem(v)
        if len(b) >= 3 and (b.endswith("ar") or b.endswith("er") or b.endswith("ir")):
            stem = b[:-2]
            pres = stem + "a" if b.endswith("ar") else stem + "e"
            if pres not in _NAO_PRESENTE and pres not in _MAPA_N:
                _PRESENTE3[pres] = v
    for p, v in PRESENTE_IRREG.items():
        _PRESENTE3[p] = v

# .gs linha 1321: NAO_PRESENTE
_NAO_PRESENTE = set(["data","venda","compra","conta","carga","entrega","baixa","troca","cobranca","busca","ajuda","soma","falta","passa","chamada","avisa","pega","lembra","guarda","reserva","usa","marca","entrada","saida","ligacao"])

def _infinitivos_conhecidos():
    """Retorna lista de verbos conhecidos do PARES + VERBOS_COMUNS que terminam em ar/er/ir."""
    verbos = set()
    for p in PARES:
        v = p[0].split()[0]
        if regex.search(r"(ar|er|ir)$", v):
            verbos.add(v)
    for v in VERBOS_COMUNS:
        if regex.search(r"(ar|er|ir)$", v):
            verbos.add(v)
    return verbos

# .gs linha 1323: NAO_VERBOS
_NAO_VERBOS = set(["lugar","mulher","colher","dever","poder","prazer","mister","ar","mar","par","bar","jantar","altar","cartaz","setor","valor","calor","fator","gestor","motor","contador","comprador","vendedor","senhor","favor","amor","cursor","painel","carter","dor","cor","flor","pior","melhor","maior","menor","superior","inferior","interior","exterior"])

# .gs linha 1324: VERBOS_OR
_VERBOS_OR = set(["repor","compor","dispor","propor","expor","supor","impor","opor","depor","pospor"])

# .gs linha 1326: VERBOS_CURTOS
_VERBOS_CURTOS = set(["dar", "ter", "ver", "ler", "ir", "vir", "ser", "pôr", "por"])

def ehVerboInf(w: str) -> bool:
    """.gs linha 1327: verifica se w é um verbo no infinitivo."""
    n = sem(w)
    if not n or n in _NAO_VERBOS:
        return False
    if n in _VERBOS_CURTOS:
        return str(w)[0] == str(w)[0].upper()
    if regex.search(r"^.{2,}(ar|er|ir)(-se)?$", n):
        return True
    if n in _VERBOS_OR:
        return True
    return False

# .gs linha 1328: SUF_SUBST
_SUF_SUBST = regex.compile(r"(ção|ções|são|sões|mento|mentos|ência|ências|ância|âncias|agem|agens|idade|idades|ismo|ura|eza|aria)$", regex.IGNORECASE)

# .gs linha 1329: ARTIGOS
_ARTIGOS = regex.compile(r"^(o|a|os|as|um|uma|de|do|da|dos|das|no|na|nos|nas|ao|aos|à|às)$", regex.IGNORECASE)

def _parecesubst(w: str) -> bool:
    """.gs linha 1330: verifica se w parece ser um substantivo."""
    n = sem(w)
    if _ARTIGOS.search(w):
        return True
    if _buscaN(n) or _chaveCompleta(n):
        return True
    if _SUF_SUBST.search(w) and not ehVerboInf(w):
        return True
    return False

# .gs linha 1332: COMPLETA
_COMPLETA = {"relatorio":"Elaborar", "reuniao":"Realizar", "planilha":"Preencher", "anuncio":"Publicar", "ligacao":"Realizar", "conversa":"Ter", "rescisao":"Realizar", "visita":"Realizar", "obrigacao":"Cumprir"}

def _singular(n: str) -> str:
    """.gs linha 1334: converte plural para singular."""
    n = str(n or "")
    n = regex.sub(r"oes$", "ao", n)
    n = regex.sub(r"aes$", "ao", n)
    n = regex.sub(r"ns$", "m", n)
    n = regex.sub(r"(?<=[aeiou])s$", "", n)
    return n

# .gs linha 1336: ERRO_N
_ERRO_N = {"colhimento":"coleta", "colhimentos":"coleta"}

def _buscaN(n: str) -> Optional[dict]:
    """.gs linha 1337: busca no mapa de substantivos."""
    if n in _MAPA_N:
        return _MAPA_N[n]
    sing = _singular(n)
    if sing in _MAPA_N:
        return _MAPA_N[sing]
    if n in _ERRO_N and _ERRO_N[n] in _MAPA_N:
        return _MAPA_N[_ERRO_N[n]]
    return None

def _chaveCompleta(n: str) -> Optional[str]:
    """.gs linha 1338: verifica COMPLETA."""
    if n in _COMPLETA:
        return n
    sing = _singular(n)
    if sing in _COMPLETA:
        return sing
    return None

# .gs linha 1339-1340: DIA_INICIO e PARTIR_INICIO
_DIA_INICIO = regex.compile(r"^((toda|todo)\s+)?(segunda|terça|terca|quarta|quinta|sexta|sábado|sabado|domingo)(-feira)?\s*:\s*(.+)$", regex.IGNORECASE)
_PARTIR_INICIO = regex.compile(r"^a partir (de|da|do)\s+([^:]+):\s*(.+)$", regex.IGNORECASE)

def _primeiraPalavra(t: str) -> str:
    """.gs linha 1325: primeira palavra (até espaço ou fim)."""
    match = regex.search(r"^[\p{L}][\p{L}-]*", t or "", flags=regex.UNICODE)
    return match.group(0) if match else ""

# .gs linha 1342: infinitivoDoPresente
def _infinitivoDoPresente(w: str) -> str:
    """.gs linha 1344: converte 3ª pessoa do presente para infinitivo."""
    return _PRESENTE3.get(sem(w), "")

# .gs linha 1346-1350: CONTR (contrações com preposições)
_CONTR = {
    "de": {"o":"do", "a":"da", "os":"dos", "as":"das", "um":"de um", "uma":"de uma", "_":"de"},
    "a": {"o":"ao", "a":"à", "os":"aos", "as":"às", "um":"a um", "uma":"a uma", "_":"a"},
    "por": {"o":"pelo", "a":"pela", "os":"pelos", "as":"pelas", "um":"por um", "uma":"por uma", "_":"por"},
    "com": {"o":"com o", "a":"com a", "os":"com os", "as":"com as", "um":"com um", "uma":"com uma", "_":"com"},
    "em": {"o":"no", "a":"na", "os":"nos", "as":"nas", "um":"em um", "uma":"em uma", "_":"em"}
}

# .gs linha 1351: SOLTA
_SOLTA = {"do":"o", "da":"a", "dos":"os", "das":"as", "ao":"o", "à":"a", "aos":"os", "às":"as", "pelo":"o", "pela":"a", "pelos":"os", "pelas":"as"}

# .gs linha 1352: MANTEM_PREP
_MANTEM_PREP = regex.compile(r"^(no|na|nos|nas|em|com|por)$", regex.IGNORECASE)

# .gs linha 1354: FAZER_GC
_FAZER_GC = regex.compile(r"^fazer\s+(?:a|o)\s+(gest[aã]o|controle)(?=\s|$)\s*(.*)$", regex.IGNORECASE)

# .gs linha 1356: IRREGULAR (infinitivo → imperativo)
_IRREGULAR = {
    "fazer":"faça", "dar":"dê", "ter":"tenha", "ver":"veja", "vir":"venha", "ir":"vá", "ler":"leia", "saber":"saiba", "trazer":"traga", "dizer":"diga", "sair":"saia", "ouvir":"ouça", "pedir":"peça", "medir":"meça", "pôr":"ponha", "por":"ponha", "repor":"reponha", "compor":"componha", "dispor":"disponha", "propor":"proponha", "expor":"exponha", "supor":"suponha", "impor":"imponha", "requerer":"requeira", "cobrir":"cubra", "descobrir":"descubra", "encobrir":"encubra", "rir":"ria", "crer":"creia", "poder":"possa", "querer":"queira"
}

def _imperativoDe(inf: str) -> str:
    """.gs linha 1357: converte infinitivo para imperativo."""
    se = bool(regex.search(r"-se$", inf, regex.IGNORECASE))
    p = regex.sub(r"-se$", "", inf, flags=regex.IGNORECASE)
    b = p.lower()
    r = None

    if b in _IRREGULAR:
        r = _IRREGULAR[b]
    elif regex.search(r"ferir$", b):
        r = regex.sub(r"ferir$", "fira", b)
    elif regex.search(r"gerir$", b):
        r = regex.sub(r"gerir$", "gira", b)
    elif regex.search(r"(sentir|mentir)$", b):
        r = regex.sub(r"entir$", "inta", b)
    elif regex.search(r"(vestir|servir|repetir)$", b):
        r = regex.sub(r"estir$", "ista", b)
        r = regex.sub(r"ervir$", "irva", r)
        r = regex.sub(r"epetir$", "epita", r)
    elif regex.search(r"seguir$", b):
        r = regex.sub(r"seguir$", "siga", b)
    elif regex.search(r"çar$", b):
        r = regex.sub(r"çar$", "ce", b)
    elif regex.search(r"car$", b):
        r = regex.sub(r"car$", "que", b)
    elif regex.search(r"gar$", b):
        r = regex.sub(r"gar$", "gue", b)
    elif regex.search(r"ear$", b):
        r = regex.sub(r"ear$", "eie", b)
    elif regex.search(r"ar$", b):
        r = regex.sub(r"ar$", "e", b)
    elif regex.search(r"(cer)$", b):
        r = regex.sub(r"cer$", "ça", b)
    elif regex.search(r"(ger|gir)$", b):
        r = regex.sub(r"g(er|ir)$", "ja", b)
    elif regex.search(r"guir$", b):
        r = regex.sub(r"guir$", "ga", b)
    elif regex.search(r"(er|ir)$", b):
        r = regex.sub(r"(er|ir)$", "a", b)
    else:
        r = b

    if se:
        r += "-se"
    return maiuscula(r) if p and p[0] == p[0].upper() else r

# .gs linha 1379-1380: IMPERATIVO_INF (mapa)
_IMPERATIVO_INF = {}

def _inicializa_imperativo():
    """Constrói mapa de imperativo → infinitivo."""
    for v in _infinitivos_conhecidos():
        if not regex.search(r"-se$", v):
            k = sem(_imperativoDe(v))
            if len(k) > 2 and k not in _IMPERATIVO_INF:
                _IMPERATIVO_INF[k] = v

def _infDoImperativo(w: str) -> str:
    """.gs linha 1381: imperativo → infinitivo."""
    return _IMPERATIVO_INF.get(sem(w), "")

# .gs linha 1382: INF_CONHECIDO
_INF_CONHECIDO = {}

def _inicializa_inf_conhecido():
    """Constrói mapa de infinitivos conhecidos."""
    for v in _infinitivos_conhecidos():
        _INF_CONHECIDO[sem(v)] = v

def _infDoGerundio(w: str) -> str:
    """.gs linha 1384: gerúndio → infinitivo."""
    m = regex.search(r"^(.{2,})(ando|endo|indo)$", sem(w))
    if not m:
        return ""
    suffix = {"ando": "ar", "endo": "er", "indo": "ir"}[m.group(2)]
    key = m.group(1) + suffix
    return _INF_CONHECIDO.get(key, "")

def _imperativoValido(s: str, w: str) -> bool:
    """.gs linha 1386: verifica se é imperativo válido (com artigo definido depois)."""
    e = _buscaN(sem(w))
    if not e:
        return False
    prox = (s[len(w):].strip().split()[0] if s[len(w):].strip() else "")
    return sem(_imperativoDe(e["v"].split()[0])) == sem(w) and regex.search(r"^(o|a|os|as)$", prox, regex.IGNORECASE)

# .gs linha 1388: PREP_SEGUE
_PREP_SEGUE = regex.compile(r"^\s+(de|do|da|dos|das|em|no|na|nos|nas|com|para|por|ao|aos|às|pelo|pela|pelos|pelas)\b", regex.IGNORECASE)

def _coordVerbos(s: str) -> str:
    """.gs linha 1389: coordena verbos ligados por "e"/"ou"."""
    def repl(m):
        c, v, off, str_full = m.group(1), m.group(2), m.start(), s
        if ehVerboInf(v) or (_buscaN(sem(v)) and _PREP_SEGUE.search(str_full[off + len(m.group(0)):])):
            return m.group(0)
        i = _infDoImperativo(v) or _infinitivoDoPresente(v)
        return c + i.lower() if i else m.group(0)

    return regex.sub(r"(\s(?:e|ou)\s)(\p{L}+)(?=\s|$|,)", repl, s, flags=regex.UNICODE)

def _verboConjugadoInf(t: str) -> str:
    """.gs linha 1391: verbo conjugado no começo → infinitivo."""
    w = _primeiraPalavra(t)
    e = _buscaN(sem(w))

    if regex.search(r"^dê$", w, regex.IGNORECASE):
        return _coordVerbos("Dar" + t[len(w):])

    inf = ""
    if _infDoImperativo(w) and (not e or _imperativoValido(t, w)):
        inf = _infDoImperativo(w)
    else:
        inf = _infinitivoDoPresente(w) or _infDoGerundio(w)

    if not inf:
        return ""

    r = _coordVerbos(maiuscula(inf) + t[len(w):])
    return _nucleoInf(r) if _FAZER_GC.search(r) else r

def _complementoInf(e: dict, resto: str) -> Optional[str]:
    """.gs linha 1403: complemento após preposição."""
    if not resto:
        return ""

    pm = regex.search(r"^(de|do|da|dos|das|ao|aos|à|às|pelo|pela|pelos|pelas|no|na|nos|nas|com|por|a|em)\s+(.*)$", resto, regex.IGNORECASE)
    if not pm:
        return None

    prep = pm.group(1).lower()
    cauda = pm.group(2)

    if e.get("k"):
        return resto
    if _MANTEM_PREP.search(prep):
        return resto
    if e.get("p") == "em" and regex.search(r"^(de|do|da|dos|das)$", prep, regex.IGNORECASE):
        solta_prep = _SOLTA.get(prep)
        return (_CONTR["em"][solta_prep] if solta_prep else "em") + " " + cauda
    if prep == "de":
        return cauda
    if prep == "a" and e.get("p") == "a":
        return cauda
    if prep == "a":
        return "a " + cauda

    solta = _SOLTA.get(prep)
    return (solta + " " if solta else "") + cauda

def _coordMeio(s: str) -> str:
    """.gs linha 1415: substantivo ligado por 'e' também vira verbo."""
    s = _coordVerbos(s)
    m = regex.search(r"^(.*?)(\s(?:e|ou)\s)(\p{L}+)(?:\s+(.*))?$", s, flags=regex.UNICODE)

    if not m or not m.group(4) or ehVerboInf(m.group(3)):
        return s

    e2 = _buscaN(sem(m.group(3)))
    if not e2:
        return s

    c = _complementoInf(e2, m.group(4).strip())
    if c is None:
        return s

    return m.group(1) + m.group(2) + e2["v"].lower() + (" " + c if c else "")

# .gs linha 1424: PLACEHOLDER_F
_PLACEHOLDER_F = set(["nao ha", "nenhuma", "nenhum", "ainda nao", "nao possui", "n/a", "-", "nada", "nao tem", "nao", "não"])

def _ehPlaceholder(t: str) -> bool:
    """.gs linha 1426: verifica se é placeholder (não é atividade)."""
    s = sem(str(t or "").rstrip(".;:,"))
    return s in _PLACEHOLDER_F

# .gs linha 1428: COMUNS_MIN
_COMUNS_MIN = set(["ponto", "relatorio", "planilha", "folha", "estoque", "produto", "produtos", "loja", "lojas", "fornecedor", "fornecedores", "cliente", "clientes", "pagamento", "pagamentos", "boleto", "boletos", "nota", "notas", "fiscal", "fiscais", "caixa", "compra", "compras", "venda", "vendas", "conta", "contas", "reuniao", "reunioes", "ferias", "documento", "documentos", "contrato", "contratos", "vaga", "vagas", "escala", "escalas", "mercadoria", "mercadorias", "extrato", "banco", "cheque", "cheques", "entrega", "entregas", "pedido", "pedidos", "funcionario", "funcionarios", "colaborador", "colaboradores", "atestado", "atestados", "registro", "registros", "desconto", "descontos", "salario", "salarios", "comissao", "comissoes", "dia", "dias", "semana", "mes"])

# Estado global de nomes de pessoas (inicializado por defineNomes)
_NOMES_PES = []

# .gs linha 1423: NOMES_COMUNS
_NOMES_COMUNS = set(["mar","rosa","sol","paz","luz","rio","dia","bem","sim","nao","não","vaga","caixa","loja","lojas","gerente","gestor","analista","fiscal","compras","vendas","pessoas","ponto","area","área","equipe","setor","cliente","fornecedor"])

# .gs linha 1424: CLASSE_LETRA (para reconhecimento flexível de nomes com variações de acentuação)
_CLASSE_LETRA = {
    "a": "aáàâãä", "e": "eéèêë", "i": "iíìîï", "o": "oóòôõö", "u": "uúùûü", "c": "cç", "n": "nñ"
}

def _limpaItem(t: str) -> str:
    """.gs linha 1430: limpa espaços, pontuação final e maiúsculas internas comuns."""
    t = regex.sub(r"\s+", " ", str(t or "")).strip().rstrip(".;,")

    def repl(m):
        sp, w = m.group(1), m.group(2)
        if sem(w) in _COMUNS_MIN and not any(sem(p.get("nome")) == sem(w) for p in _NOMES_PES):
            return sp + w.lower()
        return m.group(0)

    return regex.sub(r"(\s)(\p{Lu}\p{Ll}+)(?=\s|$|[,.;:!?)])", repl, t, flags=regex.UNICODE)

# .gs linha 1433-1436: Regex para narrativa
_FREQ_PAL_F = r"(?:segunda|ter[çc]a|quarta|quinta|sexta|s[áa]bado|domingo)(?:-feira)?|dia|semana|m[êe]s|quinzena|ano|trimestre|semestre"
_FREQ_INI_F = regex.compile(r"^(toda|todo|todas|todos|cada)\s+(" + _FREQ_PAL_F + r")\s*[,:]?\s+(?=\p{L})", regex.IGNORECASE | regex.UNICODE)
_FREQ_FIM_F = regex.compile(r"\s+(toda|todo|todas|todos|cada)\s+(" + _FREQ_PAL_F + r")\\.?$", regex.IGNORECASE | regex.UNICODE)
_SUJEITO_F = regex.compile(r"^(ele|ela|eles|elas|a pessoa|o colaborador|a colaboradora|o gestor|a gestora|o respons[áa]vel|a respons[áa]vel)\s+", regex.IGNORECASE)
_AUX_F = regex.compile(r"^(vai|v[ãa]o|costuma|costumam|deve|devem|precisa|precisam|pode|podem|tem que|t[êe]m que)\s+", regex.IGNORECASE)

def _freqTexto(f: str) -> str:
    """.gs linha 1438: formata frequência."""
    return regex.sub(r"\s+(segunda|ter[çc]a|quarta|quinta|sexta)$", r" \1-feira", f.lower(), flags=regex.IGNORECASE)

def _narrativaInf(t: str) -> Optional[str]:
    """.gs linha 1439: extrai narrativa do texto (frequência + verbo)."""
    s = t
    freq = ""

    m = _FREQ_INI_F.search(s)
    if m:
        freq = m.group(1) + " " + m.group(2)
        s = s[m.end():]
    else:
        m = _FREQ_FIM_F.search(s)
        if m and s[:m.start()].strip():
            freq = m.group(1) + " " + m.group(2)
            s = s[:m.start()]

    suj = _SUJEITO_F.search(s)
    if suj:
        s = s[suj.end():]

    aux = _AUX_F.search(s)
    if aux:
        s = s[aux.end():]

    if not freq and not suj and not aux:
        return None

    s = s.strip()
    w = _primeiraPalavra(s)
    inf = s if ehVerboInf(w) else _verboConjugadoInf(s)

    if not inf:
        return None

    inf = _coordVerbos(inf)
    return inf + (" (" + _freqTexto(freq) + ")" if freq else "")

# .gs linha 1451: PARA_DESTINO_F
_PARA_DESTINO_F = set(["Entregar", "Enviar", "Distribuir", "Vender", "Comprar", "Repor", "Apresentar"])

def _nucleoInf(t: str) -> Optional[str]:
    """.gs linha 1453: núcleo: frase que começa com substantivo/verbo/infinitivo → infinitivo."""
    t = str(t or "").strip()
    if not t:
        return ""

    w = _primeiraPalavra(t)
    n = sem(w)
    resto = t[len(w):].strip()

    # Testa narrativa primeiro
    nar = _narrativaInf(t)
    if nar:
        return nar

    # Caso especial: "se tudo está anotado"
    if n == "se" and resto and not regex.search(r"[,;]", resto):
        return "Verificar se " + resto

    # "Quantos foram pagos..." → "Controlar quantos foram pagos..."
    if regex.search(r"^quant(os|as)$", n, flags=regex.IGNORECASE) and regex.search(r"\b(foi|foram|for|forem)\b", sem(resto)):
        return "Controlar " + t[0].lower() + t[1:]

    # "Ajuda o X a fazer..."
    if n == "ajuda" and regex.search(r"^(o|a|os|as)\s", resto, flags=regex.IGNORECASE):
        return _coordMeio("Ajudar " + resto)

    # "Fazer a gestão..." → "Gerir..."
    fg = _FAZER_GC.search(t)
    if fg:
        e = _buscaN(sem(fg.group(1)))
        c = _complementoInf(e, fg.group(2).strip()) if e else None
        return None if c is None else _coordMeio(e["v"] + (" " + c if c else ""))

    # Já começa com verbo no infinitivo
    if ehVerboInf(w):
        return _coordMeio(_coordVerbos(t))

    # Verbo conjugado
    v = _verboConjugadoInf(t)
    if v:
        return _coordMeio(v)

    # Chave completa (ex: "Relatório" → "Elaborar relatório")
    ck = _chaveCompleta(n)
    if ck and not regex.search(r"^(e|ou)\s", resto, flags=regex.IGNORECASE):
        return _COMPLETA[ck] + " " + w.lower() + (" " + resto if resto else "")

    # Busca no mapa de substantivos
    e = _buscaN(n)
    if not e:
        return None

    if not resto:
        return e["v"]

    # "e controle das férias" → "e controlar as férias"
    if regex.search(r"^(e|ou)\s", resto, flags=regex.IGNORECASE):
        r = _coordMeio(e["v"] + " " + resto)
        return None if r == (e["v"] + " " + resto) else r

    # "se tudo foi debitado" → "se tudo foi debitado"
    if regex.search(r"^se\s", resto, flags=regex.IGNORECASE):
        return _coordMeio(e["v"] + " " + resto)

    # "Agendamento para o pagamento" → "Agendar o pagamento"
    pp = regex.search(r"^para\s+((?:o|a|os|as)\s.+)$", resto, flags=regex.IGNORECASE)
    if pp and e.get("p") == "de" and e["v"] not in _PARA_DESTINO_F:
        return _coordMeio(e["v"] + " " + pp.group(1))

    c = _complementoInf(e, resto)
    if c is None:
        return None

    return _coordMeio(e["v"] + (" " + c if c else ""))

def _pendenteCoord(s: str) -> bool:
    """.gs linha 1476: verifica se ainda há coordenações pendentes."""
    return _coordMeio(_coordVerbos(s)) != s

def _problemaFuncao(t: str) -> bool:
    """.gs linha 1477: verifica se a função está fora do padrão."""
    s = str(t or "").strip()
    w = _primeiraPalavra(s)
    return bool(s and not _ehPlaceholder(s) and (not w or not ehVerboInf(w) or _FAZER_GC.search(s) or _pendenteCoord(s)))

def _problemaRotina(t: str) -> bool:
    """.gs linha 1504: verifica se a rotina está fora do padrão."""
    s = str(t or "").strip()
    w = _primeiraPalavra(s)
    return bool(s and not _ehPlaceholder(s) and (_DIA_INICIO.search(s) or _PARTIR_INICIO.search(s) or not w or not ehVerboInf(w) or _FAZER_GC.search(s) or _pendenteCoord(s)))

# .gs linha 1479-1481: Regex para fallback
_SUFIXO_NOME = regex.compile(r"(ção|ções|mento|mentos|agem|agens|ência|ências|dade|dades|ura|ise)$", flags=regex.IGNORECASE)
_PLURAL_NOME = regex.compile(r"(es|as|is|ios|ns|ais)$")
_NAO_INICIO_NOME = regex.compile(r"^(se|quando|quantos|quantas|n[aã]o|pela|pelo|pelas|pelos|toda|todo|tudo|que|como)$", flags=regex.IGNORECASE)

def _fallbackRealizar(t: str) -> str:
    """.gs linha 1482: sintagma nominal sem verbo → "Realizar X"."""
    s = str(t or "").strip().rstrip(".;:,")
    w = _primeiraPalavra(s)

    if not w or _NAO_INICIO_NOME.search(w) or regex.search(r"\s(se|quando|porque|pois)\s", s, flags=regex.IGNORECASE):
        return ""

    if not _SUFIXO_NOME.search(w.lower()) and not (len(sem(w)) >= 5 and _PLURAL_NOME.search(sem(w))):
        return ""

    return "Realizar " + (s if regex.search(r"\p{Lu}", s[1], flags=regex.UNICODE) else s[0].lower() + s[1:])

def _converteNucleo(t: str) -> Optional[str]:
    """.gs linha 1489: converte núcleo ou fallback."""
    # "Pela tarde realizar o pagamento" → "Realizar o pagamento (pela tarde)"
    pa = regex.search(r"^(pel[ao]s?\s+\p{L}+)\s+(\p{L}.*)$", t, flags=regex.UNICODE | regex.IGNORECASE)
    if pa:
        w2 = _primeiraPalavra(pa.group(2))
        if ehVerboInf(w2) or sem(w2) in _INF_CONHECIDO:
            b = _nucleoInf(pa.group(2))
            if b:
                return b + " (" + pa.group(1).lower() + ")"

    return _nucleoInf(t) or _fallbackRealizar(t) or None

def ajustaFuncao(t: str) -> str:
    """.gs linha 1495: ajusta função para o padrão (verbo infinitivo)."""
    t = _limpaItem(t)
    if _ehPlaceholder(t):
        return ""
    if not _problemaFuncao(t):
        return t

    # "Responsável pelo..."
    m = regex.search(r"^respons[aá]vel\s+(?:pel[oa]s?|por)\s+(.+)$", t, flags=regex.IGNORECASE)
    if m:
        r = _nucleoInf(m.group(1))
    else:
        # "Responsabilidade..."
        m = regex.search(r"^responsabilidade\s+(?:(integral|total)\s+)?(pel[oa]s?|por)\s+(.+)$", t, flags=regex.IGNORECASE)
        if m:
            prefix = ("integralmente " if m.group(1) == "integral" else "totalmente " if m.group(1) == "total" else "")
            r = "Responder " + prefix + m.group(2).lower() + " " + m.group(3)
        else:
            r = _converteNucleo(t)

    r = maiuscula(r) if r else ""
    return r if (r and not _problemaFuncao(r)) else t

def ajustaRotina(t: str) -> str:
    """.gs linha 1506: ajusta rotina para o padrão."""
    t = _limpaItem(t)
    if _ehPlaceholder(t):
        return ""
    if not _problemaRotina(t):
        return t

    base = t
    sufixo = ""

    m = _DIA_INICIO.search(t)
    if m:
        base = m.group(5).strip()
        sufixo = " (" + _freqTexto((m.group(2) or "") + " " + m.group(3) + (m.group(4) or "")) + ")"
    else:
        m = _PARTIR_INICIO.search(t)
        if m:
            base = m.group(3).strip()
            sufixo = " (a partir " + m.group(1).lower() + " " + m.group(2).strip().lower() + ")"

    r = _converteNucleo(base)
    if not r:
        return t

    out = maiuscula(r) + sufixo
    return out if not _problemaRotina(out) else t

def violacoesEstilo(funcoes: list, rotinas: list) -> list:
    """.gs linha 1517: lista de violações de estilo."""
    v = []
    if funcoes:
        for t in funcoes:
            if _problemaFuncao(t):
                v.append({"tipo": "funcao", "t": t})
    if rotinas:
        for r in rotinas:
            if _problemaRotina(r.get("t", "")):
                v.append({"tipo": "rotina", "t": r.get("t", ""), "f": r.get("f", "")})
    return v

def mensagemEstilo(violacoes: list) -> str:
    """.gs linha 1523: mensagem de erro de estilo."""
    examples = ", ".join([""" + v["t"][:50] + """ for v in violacoes[:3]])
    msg = 'Para publicar, ajuste o padrão: função e rotina começam com verbo no infinitivo. Exemplo: "Conferir o ponto". Revise: ' + examples
    if len(violacoes) > 3:
        msg += " e mais " + str(len(violacoes) - 3)
    msg += "."
    return msg

def ajustaFuncoes(lista: list) -> list:
    """.gs linha 1524: map ajustaFuncao + filtra vazios."""
    return [ajustaFuncao(t) for t in (lista or []) if ajustaFuncao(t)]

def ajustaRotinas(lista: list) -> list:
    """.gs linha 1525: map ajustaRotina + filtra vazios."""
    result = []
    for r in (lista or []):
        t_ajustado = ajustaRotina(r.get("t", ""))
        if t_ajustado:
            result.append({**r, "t": t_ajustado})
    return result

def resumoAjuste(funcoes: list, rotinas: list) -> dict:
    """.gs linha 1527: resumo do ajuste automático."""
    fo = [t for t in (funcoes or []) if not _ehPlaceholder(t)]
    ro = [r for r in (rotinas or []) if not _ehPlaceholder(r.get("t", ""))]

    mudadas = sum(1 for t in fo if ajustaFuncao(t) != t) + sum(1 for r in ro if ajustaRotina(r.get("t", "")) != r.get("t", ""))
    removidas = len(funcoes or []) - len(fo) + len(rotinas or []) - len(ro)

    return {
        "mudadas": mudadas,
        "removidas": removidas,
        "fora": violacoesEstilo(ajustaFuncoes(funcoes), ajustaRotinas(rotinas))
    }

def avisoAjuste(r: dict) -> str:
    """.gs linha 1534: texto amigável do resumoAjuste."""
    parts = []

    if r.get("mudadas"):
        n = r["mudadas"]
        parts.append(str(n) + (" frase ajustada" if n == 1 else " frases ajustadas") + " automaticamente ao padrão, com função e rotina no infinitivo")

    if r.get("removidas"):
        n = r["removidas"]
        parts.append(str(n) + (" item sem atividade retirado" if n == 1 else " itens sem atividade retirados"))

    fora = r.get("fora", [])
    if fora:
        n = len(fora)
        msg = str(n) + (" frase precisa ser reescrita por você" if n == 1 else " frases precisam ser reescritas por você") + ": "
        examples = ", ".join([""" + v["t"][:40] + """ for v in fora[:3]])
        msg += examples
        if len(fora) > 3:
            msg += " e mais " + str(len(fora) - 3)
        parts.append(msg)

    return "; ".join(parts) + (". Confira." if parts else "")

# .gs linhas 1566-1572: Abreviações, siglas, acentos
_ABREV_F = {
    "vc":"você", "vcs":"vocês", "pq":"porque", "q":"que", "tb":"também", "tbm":"também",
    "td":"tudo", "qdo":"quando", "obs":"observação", "dps":"depois", "hj":"hoje", "msg":"mensagem",
    "pra":"para", "pras":"para as", "pro":"para o", "sab":"sábado"
}

_SIGLAS_F = {
    "dp":"DP", "rh":"RH", "ti":"TI", "nf":"NF", "cpd":"CPD", "epi":"EPI", "clt":"CLT",
    "inss":"INSS", "fgts":"FGTS", "cnpj":"CNPJ", "cpf":"CPF", "rg":"RG", "ctps":"CTPS",
    "dre":"DRE", "pdv":"PDV", "esocial":"eSocial"
}

_ACENTOS_F = {
    "nao": "não", "voce": "você", "voces": "vocês", "horario": "horário", "horarios": "horários",
    "uteis": "úteis", "sabado": "sábado", "terca": "terça", "sexa": "sexta",
    "relatorio": "relatório", "relatorios": "relatórios", "funcionario": "funcionário",
    "funcionarios": "funcionários", "conferencia": "conferência", "conferencias": "conferências",
    "reuniao": "reunião", "reunioes": "reuniões", "informacao": "informação",
    "informacoes": "informações", "orientacao": "orientação", "orientacoes": "orientações",
    "acao": "ação", "acoes": "ações", "gestao": "gestão", "solicitacao": "solicitação",
    "solicitacoes": "solicitações", "producao": "produção", "obrigacao": "obrigação",
    "obrigacoes": "obrigações", "avaliacao": "avaliação", "avaliacoes": "avaliações",
    "documentacao": "documentação", "operacao": "operação", "operacoes": "operações",
    "comunicacao": "comunicação", "supervisao": "supervisão", "aprovacao": "aprovação",
    "devolucao": "devolução", "emissao": "emissão", "cobranca": "cobrança",
    "fiscalizacao": "fiscalização", "atualizacao": "atualização", "verificacao": "verificação",
    "lancamento": "lançamento", "lancamentos": "lançamentos", "admissao": "admissão",
    "demissao": "demissão", "rescisao": "rescisão", "funcao": "função", "funcoes": "funções",
    "atribuicao": "atribuição", "atribuicoes": "atribuições", "codigo": "código",
    "codigos": "códigos", "padrao": "padrão", "padroes": "padrões", "tecnico": "técnico",
    "tecnica": "técnica", "tecnicos": "técnicos", "decisao": "decisão", "decisoes": "decisões",
    "sessao": "sessão", "secao": "seção", "referencia": "referência", "ocorrencia": "ocorrência",
    "ocorrencias": "ocorrências", "pendencia": "pendência", "pendencias": "pendências",
    "inconsistencia": "inconsistência", "divergencia": "divergência", "divergencias": "divergências",
    "competencia": "competência", "urgencia": "urgência", "tolerancia": "tolerância",
    "substituicao": "substituição", "reposicao": "reposição", "separacao": "separação",
    "distribuicao": "distribuição", "validacao": "validação", "conciliacao": "conciliação",
    "possivel": "possível", "possiveis": "possíveis", "responsavel": "responsável",
    "responsaveis": "responsáveis", "necessario": "necessário", "necessaria": "necessária",
    "necessarios": "necessários", "necessarias": "necessárias", "proximo": "próximo",
    "proxima": "próxima", "proximos": "próximos", "proximas": "próximas", "ultimo": "último",
    "ultima": "última", "ultimos": "últimos", "ultimas": "últimas", "tambem": "também",
    "ja": "já", "so": "só", "sera": "será", "ate": "até", "apos": "após", "alem": "além",
    "mes": "mês", "mao": "mão", "maos": "mãos", "sao": "são", "estao": "estão",
    "pagina": "página", "paginas": "páginas", "area": "área", "areas": "áreas",
    "numero": "número", "numeros": "números", "basico": "básico", "basica": "básica",
    "servico": "serviço", "servicos": "serviços", "promocao": "promoção", "vinculo": "vínculo",
    "atencao": "atenção", "medio": "médio", "politica": "política", "politicas": "políticas",
    "exigencia": "exigência", "frequencia": "frequência", "experiencia": "experiência",
    "experiencias": "experiências", "auxilio": "auxílio", "descricao": "descrição",
    "prestacao": "prestação", "emergencia": "emergência", "inventario": "inventário",
    "cartao": "cartão", "cartoes": "cartões", "relacao": "relação", "relacoes": "relações",
    "orcamento": "orçamento", "orcamentos": "orçamentos", "comissao": "comissão",
    "comissoes": "comissões", "resolucao": "resolução", "conteudo": "conteúdo"
}

def _fzCaixa(orig: str, novo: str) -> str:
    """.gs linha 1573: mantém caixa original."""
    if len(orig) > 1 and orig == orig.upper():
        return novo.upper()
    if orig and orig[0] == orig[0].upper():
        return maiuscula(novo)
    return novo

def formalizar(t: str, sem_ponto: bool = False) -> str:
    """.gs linha 1576: acabamento final do texto."""
    s = str(t or "").strip()
    if not s:
        return s

    # Normaliza espaços
    s = s.replace(" ", " ").replace("\t", " ")
    s = regex.sub(r" {2,}", " ", s)

    # Remove "kkk"
    s = regex.sub(r"\s*\bk{3,}\b\.?", "", s, flags=regex.IGNORECASE)
    s = regex.sub(r" +\n", "\n", s)
    s = regex.sub(r"\n +", "\n", s)

    # Pontuação
    s = regex.sub(r" +([,.;:!?)\]])", r"\1", s)
    s = regex.sub(r"([\(\[]) +", r"\1", s)
    s = regex.sub(r"([,;:])(?=[\p{L}(])", r"\1 ", s, flags=regex.UNICODE)
    s = regex.sub(r"([,;])(?:\s*\1)+", r"\1", s)
    s = regex.sub(r"\.{4,}", "...", s)
    s = regex.sub(r"(?<!\.)\.\.(?!\.)", ".", s)

    # Abreviações, siglas, acentos
    def replace_word(m):
        w = m.group(0)
        k = sem(w)
        if k in _SIGLAS_F:
            return _SIGLAS_F[k]
        if k in _ABREV_F:
            return _fzCaixa(w, _ABREV_F[k])
        if k in _ACENTOS_F:
            return _fzCaixa(w, _ACENTOS_F[k])
        return w

    s = regex.sub(r"[\p{L}\p{N}]+", replace_word, s, flags=regex.UNICODE)
    s = regex.sub(r"\bas vezes\b", lambda m: _fzCaixa(m.group(0), "às vezes"), s, flags=regex.IGNORECASE)

    # Parênteses
    s = _semParenteses(s)

    # Maiúscula inicial
    s = regex.sub(r"^(\p{L})", lambda m: m.group(1).upper(), s, flags=regex.UNICODE)

    # Ponto final (se 6+ palavras)
    if not sem_ponto and len(s.split()) >= 6 and regex.search(r"[\p{L}\p{N}]$", s, flags=regex.UNICODE):
        s += "."

    return s

# .gs linhas 1596-1613: Parênteses
_DIA_TEXTO_F = regex.compile(r"^(segunda|ter[çc]a|quarta|quinta|sexta|s[áa]bado|domingo|dias?\b|di[áa]ri|semanal|quinzenal|mensal|trimestral|semestral|anual)", flags=regex.IGNORECASE)

def _titulo(x: str) -> str:
    """.gs linha 1618: capitaliza títulos."""
    if _TEMPO_F.search(x.strip()):
        return x

    if len(x.strip().split()) > 4 or regex.search(r"\b(n[aã]o|sabe|sei|sim)\b", x, flags=regex.IGNORECASE):
        return maiuscula(x)

    def repl(m):
        w = m.group(0)
        lw = w.lower()
        return lw if (lw in _PARTIC_F and m.start() > 0) else (w if w != lw else maiuscula(w))

    return regex.sub(r"[\p{L}]+", repl, x, flags=regex.UNICODE)

# .gs linha 1617: TEMPO_F
_TEMPO_F = regex.compile(r"^(toda|todo|todas|todos|cada|pela|pelo|de manh|de tarde|de noite)\b|\b(segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo|diari|semanal|mensal)", flags=regex.IGNORECASE)

# .gs linha 1615: PARTIC_F
_PARTIC_F = set(["de", "do", "da", "dos", "das", "e", "ou", "em", "para", "com", "a", "o", "no", "na", "nos", "nas", "ao", "aos", "por", "sem", "pelo", "pela"])

def _capitalizaNomes(x: str) -> str:
    """.gs linha 1620: capitaliza nomes entre parênteses."""
    parts = regex.split(r"(\([^()]*\))", x)
    result = []
    for i, p in enumerate(parts):
        if p.startswith("(") and p.endswith(")"):
            result.append("(" + _titulo(p[1:-1]) + ")")
        else:
            result.append(p)
    return "".join(result)

def defineNomes(lista_nomes: list) -> None:
    """.gs linha 1626: define nomes de pessoas conhecidas para capitalizar."""
    global _NOMES_PES

    nomes = {}
    for x in (lista_nomes or []):
        parts = regex.split(r"\s+e\s+|\s+ou\s+|,|[/]", regex.sub(r"\([^()]*\)", " ", str(x or "")))
        for n_raw in parts:
            n = n_raw.strip()
            if len(n) < 3 or regex.search(r"^(vaga|n[aã]o|sem|nenhum[a]?|a definir|pendente)\b", n, flags=regex.IGNORECASE):
                continue

            pr = n.split()[0]
            for k in [n] + ([pr] if len(pr) >= 3 and sem(pr) not in _NOMES_COMUNS else []):
                if sem(k) not in nomes:
                    nomes[sem(k)] = _titulo(k)

    # Constrói regex para cada nome
    _NOMES_PES = []
    for nome_titulo in sorted(nomes.values(), key=len, reverse=True):
        nome_padrao = _padrao_nome(nome_titulo)
        try:
            regex_obj = regex.compile(r"(?<![\\p{L}])" + nome_padrao + r"(?![\\p{L}])", flags=regex.UNICODE | regex.IGNORECASE)
            _NOMES_PES.append({"nome": nome_titulo, "re": regex_obj})
        except:
            pass

def _padrao_nome(n: str) -> str:
    """.gs linha 1625: cria padrão regex flexível para nome."""
    result = []
    for ch in n:
        if ch == " ":
            result.append(r"\s+")
        elif sem(ch) in _CLASSE_LETRA:
            result.append("[" + _CLASSE_LETRA[sem(ch)] + "]")
        else:
            result.append(regex.escape(ch))
    return "".join(result)

def capitalizaNomes2(t: str) -> str:
    """.gs linha 1636: substitui nomes pelas variações de capitalização."""
    s = str(t or "")
    for p in _NOMES_PES:
        s = p["re"].sub(p["nome"], s)
    return s

def _semParenteses(t: str) -> str:
    """.gs linhas 1597-1613: remove parênteses e converte para forma prosa."""
    s = str(t or "")
    if "(" not in s and ")" not in s:
        return s

    def repl_paren(m):
        c = m.group(1)
        if not c:
            return ""
        c = regex.sub(r"\s+", " ", c).strip()
        fim = regex.search(r"^\s*[.;:!?]*\s*$", m.string[m.end():])

        if regex.search(r"^a partir\b", c, flags=regex.IGNORECASE):
            x = regex.sub(r"^a partir\s+(?!de\b)", "a partir de ", c, flags=regex.IGNORECASE)
        elif regex.search(r"^\d{1,2}(:\d{2}|h)", c, flags=regex.IGNORECASE):
            x = "das " + c
        elif regex.search(r"^(das?|de|at[ée]|às?)\s", c, flags=regex.IGNORECASE):
            x = c
        elif _DIA_TEXTO_F.search(c):
            x = "em " + c
        else:
            is_cargo_or_sigla = regex.search(r"^[A-Z]{2,}$", c) or (2 <= len(c.split()) <= 4)
            x = _titulo(c) if is_cargo_or_sigla else c

        return ", " + x + ("" if fim else ",")

    s = regex.sub(r"\(([^()]*)\)", repl_paren, s)
    s = s.replace("(", "").replace(")", "")
    s = regex.sub(r"\s+([,.;:!?])", r"\1", s)
    s = regex.sub(r",\s*,", ",", s)
    s = regex.sub(r",\s*([.;:!?])", r"\1", s)
    s = regex.sub(r"\s{2,}", " ", s)

    return s

# .gs linhas 1638-1775: Jornada
# .gs linhas 1638-1643: JORNADA_DIA
_JORNADA_DIA = [
    (regex.compile(r"(?:\bde\s+)?\b(?:segunda|seg)(?:-?feira)?\s*(?:a|ate|-)\s*(?:sabado|sab)\b", regex.IGNORECASE), "Segunda a sábado"),
    (regex.compile(r"(?:\bde\s+)?\b(?:segunda|seg)(?:-?feira)?\s*(?:a|ate|-)\s*(?:sexta|sexa|sex)(?:-?feira)?\b", regex.IGNORECASE), "Segunda a sexta-feira"),
    (regex.compile(r"(?:\bde\s+)?\bdias?\s+uteis\b", regex.IGNORECASE), "Segunda a sexta-feira"),
    (regex.compile(r"\bsabados?\s+alternados?\b", regex.IGNORECASE), "Sábados alternados")
]

# .gs linha 1644: JORNADA_HORA (com lookbehind para não pegar datas como "2003h")
_JORNADA_HORA = regex.compile(r"(?:\b(?:das?|de)\s+)?(?<!\d)(\d{1,2})(?:(?::|h)(\d{2}))?h?\s*(?:as|a|-|ate)\s*(\d{1,2})(?:(?::|h)(\d{2}))?h?(?!\d)", regex.IGNORECASE)

# .gs linha 1646: JORNADA_CARGA
_JORNADA_CARGA = regex.compile(r"\b\d{1,2}\s*(?:h|horas?)\s*(?:semanais?|diarias?|por\s+(?:dia|semana))\b", regex.IGNORECASE)

# .gs linha 1647: JORNADA_ROTULO
_JORNADA_ROTULO = regex.compile(r"^(dias|hor[aá]rio|carga\s+hor[aá]ria|observa[cç][õo]es)\s*:\s*", regex.IGNORECASE)

# .gs linha 1661-1663: Avisos e lixo
_AV_ALMOCO = "Confirmar o horário de almoço com o gestor."
_AV_INCONS = "Horário inconsistente: confirmar com o gestor."
_OBS_LIXO = regex.compile(r"entre\s+entrada\s+e\s+sa[ií]da|carga\s+hor[aá]ria", regex.IGNORECASE)

# .gs linhas 1666-1667: Regex para almoço
_ALMOCO_ANTES = regex.compile(r"\b(?:com\s+)?(meia|uma|um|duas|\d{1,2})\s*(horas?|h|minutos?|min)?\s*(?:de\s+)?(?:intervalo\s+(?:de\s+)?)?almoco\b", regex.IGNORECASE)
_ALMOCO_DEPOIS = regex.compile(r"\balmoco\s*(?:de\s+|:\s*)?(meia|uma|um|duas|\d{1,2})\s*(horas?|h|minutos?|min)\b", regex.IGNORECASE)

def _hora_f(h: int, m: int) -> str:
    """.gs linha 1645: formata hora."""
    return str(h) + "h" + (str(m).zfill(2) if m else "")

def _duracao_texto(m: int) -> str:
    """.gs linha 1665: texto de duração (30 min = "meia hora", 60 = "uma hora")."""
    if m == 60:
        return "uma hora"
    elif m == 30:
        return "meia hora"
    else:
        h = m // 60
        r = m % 60
        txt = ""
        if h > 0:
            txt += str(h) + (" hora" if h == 1 else " horas")
        if r > 0:
            if h > 0:
                txt += " e "
            txt += str(r) + (" minuto" if r == 1 else " minutos")
        return txt

def _duracao_almoco(b: str) -> Optional[dict]:
    """.gs linha 1669: extrai duração de almoço."""
    m = _ALMOCO_ANTES.search(b) or _ALMOCO_DEPOIS.search(b)
    if not m:
        return None

    n = m.group(1)
    u = m.group(2) or ""

    min_val = None
    if n == "meia":
        min_val = 30
    elif n in ("uma", "um"):
        min_val = 60
    elif n == "duas":
        min_val = 120
    elif regex.match(r"^min", u):
        min_val = int(n)
    elif u:
        if int(n) > 4:
            return None
        min_val = int(n) * 60
    else:
        n_int = int(n)
        min_val = n_int * 60 if n_int <= 4 else n_int

    return {"min": min_val, "pos": m.start(), "len": len(m.group(0))}

def _sem_ac_min(s: str) -> str:
    """.gs linha 1658: minúsculo sem acento (mesmo tamanho do texto original)."""
    s = str(s or "")
    s = unicodedata.normalize("NFD", s)
    s = regex.sub(r"[\p{M}]", "", s, flags=regex.UNICODE)
    return s.lower()

def _mmin(q: Optional[int]) -> int:
    """.gs linha 1659: converte para int (ou 0)."""
    return int(q) if q else 0

def jornadaCalc(b: str, dias: str, orig: str) -> dict:
    """.gs linha 1684: calcula carga horária."""
    r = {"horario": "", "carga": "", "avisos": [], "incons": False, "spans": [], "raw": ""}
    ivs = []

    # Encontra todos os horários
    for mh in _JORNADA_HORA.finditer(b):
        groups = mh.groups()
        v = [_mmin(groups[i]) for i in range(4)]
        a = v[0] * 60 + v[1]
        z = v[2] * 60 + v[3]
        ok = v[1] < 60 and v[3] < 60 and v[0] < 24 and v[2] <= 24
        ivs.append({
            "a": mh.start(),
            "z": mh.end(),
            "ini": a,
            "fim": z,
            "dur": z - a,
            "h": v,
            "ok": ok
        })
        r["spans"].append([mh.start(), mh.end()])

    # Raw horário
    r["raw"] = " e ".join([orig[iv["a"]:iv["z"]].strip() if orig else "" for iv in ivs])

    # Detecta "e" entre turnos
    for k in range(1, len(ivs)):
        between = b[ivs[k-1]["z"]:ivs[k]["a"]]
        if regex.match(r"^[\s,]*e[\s,]*$", between):
            r["spans"].append([ivs[k-1]["z"], ivs[k]["a"]])

    # Detecta almoço
    al = _duracao_almoco(b)
    if al:
        r["spans"].append([al["pos"], al["pos"] + al["len"]])

    # Detecta "X horas entre entrada e saída"
    ent_match = regex.search(r"\(?\s*\d{1,2}\s*(?:h|horas?)\s+entre\s+entrada\s+e\s+saida\s*\)?", b)
    if ent_match:
        r["spans"].append([ent_match.start(), ent_match.end()])

    # Detecta intervalo de almoço junto ("com almoço das 12h às 13h")
    pos = b.find("almoco")
    brk = None
    if pos >= 0 and len(ivs) >= 2:
        perto = [x for x in ivs if 0 < x["dur"] <= 180 and min(abs(x["ini"] - pos), abs(x["fim"] - pos)) < 40]
        if perto:
            brk = min(perto, key=lambda x: x["dur"])
            ivs.remove(brk)

    # Sem horários
    if not ivs:
        if regex.search(r"\d{1,2}\s*(?::|h)", b):
            r["incons"] = True
        return r

    # Múltiplos turnos ou inválidos
    if len(ivs) > 2 or any(not x["ok"] or x["dur"] <= 0 for x in ivs):
        r["incons"] = True
        return r

    # Um turno
    if len(ivs) == 1:
        x = ivs[0]
        almo = brk["dur"] if brk else (al["min"] if al else 60)
        if x["dur"] > 720 or almo >= x["dur"]:
            r["incons"] = True
            return r

        trabalho = x["dur"] - almo
        texto = "das " + _hora_f(x["h"][0], x["h"][1]) + " às " + _hora_f(x["h"][2], x["h"][3])

        if brk:
            texto += ", com almoço das " + _hora_f(brk["h"][0], brk["h"][1]) + " às " + _hora_f(brk["h"][2], brk["h"][3])
        elif al:
            texto += ", com " + _duracao_texto(al["min"]) + " de almoço"
        else:
            r["avisos"].append(_AV_ALMOCO)
    else:
        # Dois turnos
        p = ivs[0]
        q = ivs[1]
        if q["ini"] < p["fim"] or q["fim"] - p["ini"] > 720:
            r["incons"] = True
            return r

        trabalho = p["dur"] + q["dur"]
        texto = ("das " + _hora_f(p["h"][0], p["h"][1]) + " às " + _hora_f(p["h"][2], p["h"][3]) +
                 " e das " + _hora_f(q["h"][0], q["h"][1]) + " às " + _hora_f(q["h"][2], q["h"][3]))

    # Calcula semana
    d = _sem_ac_min(dias or "")
    if regex.search(r"escala|alternad", d):
        n = 0
    elif regex.search(r"segunda a sexta", d):
        n = 5
    elif regex.search(r"segunda a sabado", d):
        n = 6
    else:
        n = 0

    r["horario"] = texto
    r["carga"] = _duracao_texto(trabalho) + " por dia" + (", " + _duracao_texto(trabalho * n) + " por semana" if n else "")
    return r

def _jornadaObs(t: str) -> str:
    """.gs linha 1736: processa observações."""
    s = str(t or "").replace(" ", " ").replace("\t", " ")
    s = regex.sub(r"\s+", " ", s).strip()

    # Parênteses viram frases
    s = regex.sub(r"\(([^()]*)\)", lambda m: ". " + m.group(1) + ". ", s)

    # Separadores viram pontos
    s = regex.sub(r"\s+[-–—]\s+|;", ".", s)

    # Aplica transformações de frases (do .gs linha 1650-1654)
    # Mantém padrões simples sem tentar ser genérico
    s = regex.sub(r"(?<!\p{L})(ficam|fica)\s+devendo\s+horas(?!\p{L})", "há horas pendentes de compensação", s, flags=regex.UNICODE | regex.IGNORECASE)
    s = regex.sub(r"(?<!\p{L})com\s+horario\s+estendido(?!\p{L})", "horário estendido", s, flags=regex.UNICODE | regex.IGNORECASE)
    s = regex.sub(r"(?<!\p{L})(as\s+vezes|de\s+vez\s+em\s+quando|eventualmente|eventual)\s+(ao|aos)\s+sabados?(?!\p{L})", "eventualmente, aos sábados", s, flags=regex.UNICODE | regex.IGNORECASE)

    # Processa frases
    frases = []
    for x in s.split("."):
        x = regex.sub(r"^[\s,:\-–—]+|[\s,:\-–—]+$", "", x).strip()
        if x and not _OBS_LIXO.search(x):
            # Adiciona ponto se necessário
            if not regex.search(r"[\p{L}\p{N})]$", x, regex.UNICODE):
                x = x + "."
            frases.append(formalizar(x, sem_ponto=True))

    return " ".join(frases)

def jornadaFecha(dias: str, horTxt: str, obsTxt: str, cal: Optional[dict]) -> dict:
    """.gs linha 1728: fecha jornada."""
    c = cal or jornadaCalc(_sem_ac_min(horTxt), dias, horTxt)
    obs = _jornadaObs(str(obsTxt or "").split(_AV_ALMOCO)[0].split(_AV_INCONS)[0])

    avisos = [obs] if obs else []
    if c["incons"]:
        avisos.append(_AV_INCONS)
    else:
        avisos.extend(c["avisos"])

    txt = " ".join([x for x in avisos if x])

    if c["incons"]:
        return {
            "dias": maiuscula((dias or "").replace(" ", " ").replace("\t", " ").strip()),
            "horario": maiuscula((horTxt or "").replace(" ", " ").replace("\t", " ").strip()),
            "carga": "",
            "obs": txt
        }

    return {
        "dias": maiuscula((dias or "").replace(" ", " ").replace("\t", " ").strip()),
        "horario": maiuscula(c["horario"] or horTxt).replace(" ", " ").replace("\t", " ").strip(),
        "carga": c["carga"],
        "obs": txt
    }

def jornadaMonta(p: Optional[dict]) -> str:
    """.gs linha 1770: monta texto canônico da jornada."""
    x = p or {}
    parts = []

    v_dias = str(x.get("dias", "") or "").replace(" ", " ").replace("\t", " ").strip()
    if v_dias:
        parts.append("Dias: " + v_dias)

    v_horario = str(x.get("horario", "") or "").replace(" ", " ").replace("\t", " ").strip()
    if v_horario:
        parts.append("Horário: " + v_horario)

    v_carga = str(x.get("carga", "") or "").replace(" ", " ").replace("\t", " ").strip()
    if v_carga:
        parts.append("Carga horária: " + v_carga)

    v_obs = str(x.get("obs", "") or "").replace(" ", " ").replace("\t", " ").strip()
    if v_obs:
        parts.append("Observações: " + v_obs)

    return " | ".join(parts)

def jornadaPartes(t: str) -> dict:
    """.gs linha 1741: separa jornada em partes."""
    s = unicodedata.normalize("NFC", str(t or "")).replace(" ", " ").replace("\t", " ")
    s = regex.sub(r"\s+", " ", s).strip()

    if not s:
        return {"dias": "", "horario": "", "carga": "", "obs": ""}

    # Com rótulos
    if _JORNADA_ROTULO.search(s):
        p = {"dias": [], "horario": [], "obs": []}

        # Separa por rótulo
        parts = regex.split(r"\s*\|\s*(?=(?:dias|hor[aá]rio|carga\s+hor[aá]ria|observa[cç][õo]es)\s*:)", s, flags=regex.IGNORECASE)

        for pc in parts:
            m = _JORNADA_ROTULO.match(pc)
            v = pc[m.end():].strip() if m else pc.strip()

            if not m:
                p["obs"].append(v)
            elif regex.match(r"^dias", m.group(1), regex.IGNORECASE):
                p["dias"].append(v)
            elif regex.match(r"^hor", m.group(1), regex.IGNORECASE):
                p["horario"].append(v)
            elif not regex.match(r"^carga", m.group(1), regex.IGNORECASE):
                p["obs"].append(v)

        return jornadaFecha(" ".join(p["dias"]), " ".join(p["horario"]), " ".join(p["obs"]), None)

    # Sem rótulos
    b = _sem_ac_min(s)

    # Busca dias
    dia = ""
    for re_pat, nome in _JORNADA_DIA:
        m = re_pat.search(b)
        if m:
            dia = nome
            break

    # Busca escala (5x1, 6x1)
    me = regex.search(r"\b(?:escala\s+)?([56])\s*x\s*1\b", b)
    escala = ("Escala " + me.group(1) + "x1") if me else ""

    dias = (", ".join([x for x in [escala, dia] if x]) if escala or dia else "")

    cal = jornadaCalc(b, dias, s)

    # Sem dia nem horário: tudo vai para obs
    if not dias and not cal["horario"] and not cal["incons"]:
        return {
            "dias": "",
            "horario": "",
            "carga": "",
            "obs": formalizar(_jornadaObs(s), sem_ponto=True) + ("." if not regex.search(r"[.!?]$", formalizar(_jornadaObs(s), sem_ponto=True)) else "")
        }

    # Reconstruir observações removendo os trechos principais (dias, horários, carga)
    # Estratégia simples: remover padrões conhecidos do texto original
    res = s

    # Remove dias (texto original)
    if dia:
        # Remove a menção do dia no texto (heurística simples)
        for pattern in [r"dias?\s+úteis\b", r"segunda\s+a\s+(?:sáb|sexta)", r"s[áa]bados?\s+alternados?"]:
            res = regex.sub(pattern, "", res, flags=regex.IGNORECASE)

    # Remove escala
    if me:
        res = regex.sub(r"\b(?:escala\s+)?[56]\s*x\s*1\b", "", res, flags=regex.IGNORECASE)

    # Remove carga (heurística)
    res = regex.sub(r"\b\d{1,2}\s*(?:h|horas?)\s*(?:semanais?|diarias?|por\s+(?:dia|semana))\b", "", res, flags=regex.IGNORECASE)

    # Remove horários
    for m in _JORNADA_HORA.finditer(b):
        # Encontrar e remover no texto original (aproximado)
        pass

    res = regex.sub(r"\bda?s?\s*\d{1,2}(?::?\d{2})?h?\s*(?:às?|a|-|ate)\s*\d{1,2}(?::?\d{2})?h?\b", "", res, flags=regex.IGNORECASE)

    # Limpa espaços extras
    res = regex.sub(r"\s+", " ", res).strip()

    return jornadaFecha(dias, cal["raw"], res, cal)

def formalizarJornada(t: str) -> str:
    """.gs linha 1775: formaliza jornada (completo)."""
    return jornadaMonta(jornadaPartes(t))

# .gs linhas 1776-1828: Recorre
# .gs linha 1777: CONDICAO_F
_CONDICAO_F = regex.compile(r"^(em|quando|para|com|sobre|nos|nas|no|na|por|se|caso|ao|aos|às|à|pelo|pela)\s", regex.IGNORECASE)

# .gs linha 1778: SITUACAO_F
_SITUACAO_F = regex.compile(r"^([^:()]{3,80}):\s*(.+)$")

def _rotulo_situacao(x: str) -> str:
    """.gs linha 1779: normaliza rótulo de situação."""
    y = str(x or "").replace(" ", " ").replace("\t", " ")
    y = regex.sub(r"\s+", " ", y).strip()

    if regex.search(r"pr[óo]pria\s+[áa]rea", y, regex.IGNORECASE):
        return "Própria área"
    if regex.search(r"fora\s+da\s+[áa]rea", y, regex.IGNORECASE):
        return "Fora da área"
    if regex.match(r"^em caso de problema$", y, regex.IGNORECASE):
        return "Em caso de problema"

    z = regex.sub(r"^em\s+", "", y, flags=regex.IGNORECASE)
    return maiuscula(z)

def _nome_recorre(n: str) -> str:
    """.gs linha 1788: processa nome com siglas e parênteses."""
    s = str(n or "").replace(" ", " ").replace("\t", " ")
    s = regex.sub(r"\s+", " ", s).strip()

    # Siglas entre parênteses viram ", do RH"
    s = regex.sub(r"\(\s*([A-Z]{2,6})\s*\)", r", do \1", s)

    # Outros parênteses
    s = regex.sub(r"\(([^()]*)\)", lambda m: ", " + (maiuscula(m.group(1).strip())), s)

    s = capitalizaNomes2(formalizar(s, sem_ponto=True))
    s = regex.sub(r"^[\s,;.:\-]+|[\s,;:\-]+$", "", s).strip()
    return s

def recorreItens(t: str) -> list:
    """.gs linha 1793: identifica pares situação+nome do texto."""
    s = str(t or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", ";")
    s = regex.sub(r"[ \t]+", " ", s).strip()

    # Remove prefixos
    s = regex.sub(r"^(em caso de problema,?\s*)?(recorre|recorro|procure|procuro)\s+(?:(?:a|ao|à|com)\s+)?", "", s, flags=regex.IGNORECASE)

    # Escapa caracteres especiais em parênteses
    def protege(x):
        def repl_paren(m):
            c = m.group(1)
            c = c.replace(",", "\x01").replace(";", "\x02").replace("/", "\x03").replace(" ", "\x05")
            return "(" + c + ")"
        return regex.sub(r"\(([^()]*)\)", repl_paren, x)

    def restaura(x):
        x = x.replace("\x01", ",").replace("\x02", ";").replace("\x03", "/").replace("\x05", " ")
        x = regex.sub(r"^[\s.\-–—]+|[\s.\-–—]+$", "", x).strip()
        return x

    itens = []
    s_prot = protege(s)

    for g in s_prot.split(";"):
        grupo = g.strip()
        if not grupo:
            continue

        # Tenta padrão "Situação: Nome"
        sit_match = _SITUACAO_F.match(grupo)
        if sit_match:
            itens.append({
                "sit": _rotulo_situacao(restaura(sit_match.group(1))),
                "nome": restaura(sit_match.group(2))
            })
            continue

        # Tenta padrão "Fora da área, ..."
        m = regex.match(r"^fora da [áa]rea\s*,?\s*(.*)$", grupo, regex.IGNORECASE)
        fora = bool(m)
        partes_str = m.group(1) if m else grupo

        # Separa por vírgula, barra, "e"
        partes = []
        for p in regex.split(r"[,\/]|\se\s", partes_str, flags=regex.IGNORECASE):
            p_rest = restaura(p)
            if p_rest:
                if partes and _CONDICAO_F.match(p_rest):
                    # Continua a parte anterior
                    partes[-1] += ", " + p_rest
                else:
                    partes.append(p_rest)

        for p in partes:
            # Tenta extrair "Nome, em caso de X"
            c_match = regex.match(r"^(.*?),\s*(em|quando|caso|se)\s+(.+)$", p, regex.IGNORECASE)
            if c_match:
                sit_word = c_match.group(2).lower()
                sit_rest = c_match.group(3)
                sit_name = "" if sit_word == "em" else sit_word + " " + sit_rest
                if not sit_name:
                    sit_name = sit_rest
                itens.append({
                    "sit": _rotulo_situacao(sit_name),
                    "nome": c_match.group(1)
                })
            else:
                itens.append({
                    "sit": ("Fora da área" if fora else None),
                    "nome": p
                })

    # Filtra vazios e deduplicados
    algum_fora = any(i.get("sit") == "Fora da área" for i in itens)
    vistos = set()
    out = []

    for i in itens:
        if regex.match(r"^(n[aã]o recorre|n[aã]o h[aá]|ningu[eé]m|nenhum[a]?$|n\/a$)", i.get("nome", ""), regex.IGNORECASE):
            continue

        nome = _nome_recorre(i.get("nome", ""))
        sit = i.get("sit") or ("Própria área" if algum_fora else "Em caso de problema")

        if nome and not vistos.__contains__(sem(sit + nome)):
            vistos.add(sem(sit + nome))
            out.append({"sit": sit, "nome": nome})

    return out

def recorreNormaliza(t: str) -> str:
    """.gs linha 1825: formata recorre como "Sit: Nome; Sit: Nome"."""
    itens = recorreItens(t)
    return "; ".join([item.get("sit", "") + ": " + item.get("nome", "") for item in itens]) if itens else ""

# .gs linhas 1829-1854: Missão
# .gs linha 1830: CARGO_PAL
_CARGO_PAL = regex.compile(r"(gerente|gestor|analista|assistente|auxiliar|supervis|coordena|diretor|s[oó]cio|respons|l[ií]der|conferente|operador|fiscal|financeir|administra|recursos|departamento|compras|vendas|loja|caixa|contab|advogad|cl[ií]nica|lumi|excel|mrm|grupo|empresa|sobradinho|ger[êe]nc|diretori|[aá]rea|equipe|setor|cliente|fornecedor)", regex.IGNORECASE)

# .gs linha 1831: EXCLUI_NOME
_EXCLUI_NOME = regex.compile(r"^(Lumi|Excel|Sobradinho|Grupo|MRM|Google|Lojas?|Financeiro|Contabilidade|Cl[ií]nica|Recursos|Departamento|Diretoria|S[oó]cios?|Fornecedores?|Gerentes?|Funcion[áa]rios?|Colaboradores?|Clientes?|Sistema|Plataforma|Empresa|Brasil|Segunda|Ter[çc]a|Quarta|Quinta|Sexta|S[áa]bado|Domingo|Janeiro|Fevereiro|Mar[çc]o|Abril|Maio|Junho|Julho|Agosto|Setembro|Outubro|Novembro|Dezembro)$")

def _esc_re(x: str) -> str:
    """.gs linha 1832: escapa caracteres especiais de regex."""
    return regex.escape(x)

def missaoFormal(t: str, nomes: list) -> str:
    """.gs linha 1834: remove nome da pessoa entrevistada, formaliza."""
    defineNomes(nomes)
    orig = formalizar(str(t or "").strip())

    s = unicodedata.normalize("NFC", str(t or "")).replace(" ", " ").replace("\t", " ")
    s = regex.sub(r"\s+", " ", s).strip()

    if not s:
        return orig

    # Remove "finalidade do cargo: ..."
    s = regex.sub(r"^finalidade do cargo\s*:\s*", "", s, flags=regex.IGNORECASE)

    # "um pouco menos/mais de" → "com menos/mais"
    s = regex.sub(r"\bum pouco menos de\b", "com menos", s, flags=regex.IGNORECASE)
    s = regex.sub(r"\bum pouco mais de\b", "com mais", s, flags=regex.IGNORECASE)
    s = regex.sub(r"\bum pouco\s+", "", s, flags=regex.IGNORECASE)

    # Gírias informais saem
    s = regex.sub(r"(^|\s)(né|tipo|tá)(?=[\s,.;:!?]|$)", r"\1", s, flags=regex.IGNORECASE)

    # Pontuação
    s = regex.sub(r"\s+([,.;:!?])", r"\1", s)
    s = regex.sub(r",\s*,", ",", s)

    # Extrai nomes próprios
    pessoas = []
    for n in (nomes or []):
        n_str = str(n or "")
        for parte in regex.split(r"\s+e\s+|\s+ou\s+|,|[\/]", n_str):
            parte = parte.strip()
            if len(parte) >= 3:
                pessoas.append(parte)

    # Remove parênteses com só nomes próprios
    def nome_proprio(c):
        # Teste se é nome próprio capitalizado
        if not regex.match(r"^\p{Lu}\p{Ll}+(?:\s+\p{Lu}\p{Ll}+){0,2}(?:\s+(?:e|ou)\s+\p{Lu}\p{Ll}+(?:\s+\p{Lu}\p{Ll}+){0,2})?$", c, regex.UNICODE):
            return False
        return not _CARGO_PAL.search(c)

    antes_nome = s
    s = regex.sub(
        r"\s*\(([^()]*)\)",
        lambda m: "" if (nome_proprio(m.group(1).strip()) or any(sem(p) == sem(m.group(1).strip()) for p in pessoas)) else m.group(0),
        s
    )

    # Remove nomes das pessoas (variações de preposição)
    if pessoas:
        # Constrói padrão simples para cada nome
        for p in sorted(pessoas, key=len, reverse=True):
            p_escaped = _esc_re(p)
            # Remove "a Nome", "o Nome", etc.
            s = regex.sub(r"\b(?:a|o|ao|à|aos|às|com|para|pelo|pela)\s+" + p_escaped + r"\b", "", s, flags=regex.IGNORECASE)
            # Remove só o nome
            s = regex.sub(r"\b" + p_escaped + r"\b", "", s, flags=regex.IGNORECASE)

    # Remove "para Fulana" etc., mas não "para RH"
    s = regex.sub(
        r"(^|\s)(a|ao|à|com|para|aos|às)\s+(\p{Lu}\p{Ll}+)(?=[\s.,;:!?]|$)",
        lambda m: m.group(0) if (_EXCLUI_NOME.match(m.group(3)) or _CARGO_PAL.search(m.group(3))) else m.group(1),
        s,
        flags=regex.UNICODE
    )

    # Ajustes finais
    s = regex.sub(r"\bmeu cargo\b", "o cargo", s, flags=regex.IGNORECASE)
    s = regex.sub(r"\bminha fun[çc][ãa]o\b", "a função", s, flags=regex.IGNORECASE)
    s = regex.sub(r"\s*\(\s*\)", "", s)

    # Preposição solta no fim
    s = regex.sub(r"(^|\s)(a|o|ao|à|aos|às|com|para|de|do|da|pelo|pela|e|ou|em|por|sobre)\s*(?=[.,;:!?]|$)", r"\1", s, flags=regex.IGNORECASE)

    # Pontuação final
    s = regex.sub(r"\s+([.,;:!?])", r"\1", s)
    s = regex.sub(r"\s{2,}", " ", s)
    s = regex.sub(r"^[\s,;:-]+", "", s).strip()

    r = formalizar(s, sem_ponto=True).replace(" ", " ").strip()

    # Se ficou muito curto, volta original
    if len(r.split()) < 3:
        return orig

    # Adiciona ponto se necessário (checa o FIM da string -- regex.match ancora no início,
    # por isso usa regex.search aqui, igual ao /[.!?]$/.test(r) do .gs)
    if not regex.search(r"[.!?]$", r):
        r += "."

    return r

def formalizarMissao(t: str, nomes: list) -> str:
    """.gs linha 1833: formaliza missão."""
    defineNomes(nomes)
    return capitalizaNomes2(missaoFormal(t, nomes))

# Inicializar estruturas globais
_inicializa_presente3()
_inicializa_imperativo()
_inicializa_inf_conhecido()
