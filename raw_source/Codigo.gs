/**
 * PLATAFORMA DE GESTÃO · SOBRADINHO CARNES (Grupo Gestão)
 * Servidor em Google Apps Script. Os dados ficam numa Planilha Google criada por configurar().
 *
 * Como funciona, em uma frase: a tela (Index.html) pede um "retrato" ao servidor; o servidor confere quem é a
 * pessoa e devolve SÓ o que ela pode ver. Quem não tem acesso nunca recebe o conteúdo.
 */

/* ============================== configuração ============================== */
const EMPRESA = "Sobradinho Carnes";
const ABAS = {
  Cargos:      ["id","nome","area","pai","pessoa","missao","funcoes","rotinas","jornada","tempoEmpresa","formacao","experiencia","habilidades","relacoes","recorre","ferramentas","status","entrevistaId","revisao","historico","x","y"],
  Entrevistas: ["id","cargoId","pessoa","data","link","auto","registradoPor","registradoEm","respostas"],
  Usuarios:    ["email","nome","perfil","cargoId","cargoInformado","cargoSolicitado","status","salt","hash","criadoEm","ultimoAcesso","trocarSenha"],
  Propostas:   ["id","tipo","cargoId","nome","area","pai","de","para","motivo","fonte"],   // sem uso desde o TO BE (fica na planilha)
  Solicitacoes:["id","cargoId","origemId","texto","motivo","status","criadoPor","criadoPorEmail","criadoEm","resolvidoPor","resolvidoEm","resposta","tipo","cargoSugerido"],
  Registro:    ["quando","quem","acao"],
  Tobe:        ["id","nome","area","pai","pessoa","missao","funcoes","rotinas","jornada","tempoEmpresa","formacao","experiencia","habilidades","relacoes","recorre","ferramentas","x","y","origem","base","personalizado","conflito","removido"],
  TobeHistorico:["id","quando","quem","origem","cargoId","cargoNome","campo","antes","depois","descricao","justificativa","status","justificadoEm","justificadoPor","lote"],
  TobeVersoes: ["versao","publicadoEm","por","nota","snapshot"]
};
const ESQUEMA = 7;                   // sobe quando as abas mudam: a planilha antiga ganha as colunas novas sozinha
const SIGLA = "SC";                    // prefixo do código dos cargos (SC-RHU-01)
const SESSAO_SEGUNDOS = 1800;          // sessão expira após 30 min sem uso
const VOLTAS_HASH = 600;               // custo da criptografia da senha
const MAX_TENTATIVAS = 5;              // erros de senha antes de bloquear por 15 min
const CACHE_SEGUNDOS = 120;            // cópia da planilha em memória (deixa a plataforma rápida); toda gravação pela plataforma renova
const TEMPLATE_ENTREVISTA = "1-Kw-ufZAD9i20lm3xbA2mz6jesj3IwFIlzOVBVHmMAQ";   // "Template de Entrevista | Sobradinho Carnes" (Drive)

/* O organograma NÃO vem pronto: o administrador monta e corrige em "Editar organograma" (ou na aba "Cargos" da planilha). */

const PERFIS = {
  admin:       {nome:"Administrador", desc:"Equipe Grupo Gestão. Vê e administra tudo, inclusive rascunhos."},
  socio:       {nome:"Sócio",         desc:"Vê todos os cargos da empresa, somente com manuais publicados."},
  gestor:      {nome:"Gestor",        desc:"Vê o próprio cargo e tudo abaixo dele no organograma."},
  colaborador: {nome:"Colaborador",   desc:"Vê o próprio cargo e os colegas do mesmo nível na mesma área."}
};
const AUTO = ["Carga de trabalho","Capacitação","Clareza do que se espera do cargo","Motivação","Ferramentas e recursos","Reconhecimento","Abertura para sugestões","Satisfação geral"];

/* ============================== passo 1: rodar UMA vez ============================== */
function configurar() {
  const props = PropertiesService.getScriptProperties();
  let ss = null, id = props.getProperty("PLANILHA_ID");
  if (id) { try { ss = SpreadsheetApp.openById(id); } catch (e) { ss = null; } }
  if (!ss) { ss = SpreadsheetApp.create("Plataforma de Gestão - " + EMPRESA + ", banco de dados"); props.setProperty("PLANILHA_ID", ss.getId()); }
  Object.keys(ABAS).forEach(nome => {
    let sh = ss.getSheetByName(nome) || ss.insertSheet(nome);
    if (sh.getLastRow() === 0) { sh.getRange(1, 1, 1, ABAS[nome].length).setValues([ABAS[nome]]).setFontWeight("bold").setBackground("#EFEEEB"); sh.setFrozenRows(1); }
  });
  const padrao = ss.getSheetByName("Página1") || ss.getSheetByName("Sheet1"); if (padrao && ss.getSheets().length > 1) ss.deleteSheet(padrao);
  const codigo = novoCodigoAdmin();
  const resumo = "PLANILHA: " + ss.getUrl() + "\nCÓDIGO DO PRIMEIRO ADMINISTRADOR: " + codigo + "\n(use na tela 'Primeiro acesso', em 'Sou do Grupo Gestão'. Vale para um único cadastro.)";
  Logger.log(resumo);
  return resumo;
}
/** Gera (ou renova) o código que transforma o primeiro cadastro em Administrador. Vale uma vez. */
function novoCodigoAdmin() {
  const codigo = Utilities.getUuid().replace(/-/g, "").slice(0, 10).toUpperCase();
  PropertiesService.getScriptProperties().setProperty("ADMIN_CODIGO", codigo);
  Logger.log("CÓDIGO DE ADMINISTRADOR (vale para um único cadastro): " + codigo);
  const ss = planilha_(); let l = ss.getSheetByName("LEIA-ME") || ss.insertSheet("LEIA-ME", 0);
  l.clear(); l.getRange(1, 1, 5, 2).setValues([
    ["Plataforma de Gestão - " + EMPRESA, ""],
    ["Novo administrador", "Quem do Grupo Gestão precisa de acesso faz 'Primeiro acesso' sem código e um administrador aprova em Usuários, com o perfil Administrador."],
    ["Organograma", "Edite a aba 'Cargos', com as colunas id, nome, area, pai e pessoa. Uma linha por cargo. 'pai' = id do cargo acima. O topo fica com 'pai' vazio."],
    ["Atenção", "As colunas depois de 'pessoa' são preenchidas pela plataforma a partir das entrevistas. Não edite as abas Usuarios e Registro à mão."],
    ["Organograma futuro (TO BE)", "Montado pelo administrador na tela TO BE. Não altera a aba 'Cargos'; as abas 'Tobe', 'TobeHistorico' e 'TobeVersoes' guardam o rascunho e o histórico."]
  ]); l.getRange(1, 1).setFontWeight("bold").setFontSize(14); l.setColumnWidth(1, 240); l.setColumnWidth(2, 640);
  return codigo;
}

/* ============================== entrada da página ============================== */
function doGet() {
  return HtmlService.createHtmlOutputFromFile("Index").setTitle("Gestão " + EMPRESA)
    .addMetaTag("viewport", "width=device-width, initial-scale=1").setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/* ============================== funções chamadas pela tela ============================== */
const resp_ = fn => { try { return {dado:fn()}; } catch (e) { return {erro:String(e && e.message || e)}; } };

/* toda alteração devolve o resultado E o retrato novo: uma ida ao servidor em vez de duas (deixa a tela mais rápida) */
const mudar_ = (token, fn) => resp_(() => { const r = escrever_(fn); return {r, snap:retrato_(carregar_(), sessao_(token))}; });

function api_login(email, senha)         { return resp_(() => { const r = login_(email, senha); return {token:r.token, trocar:r.trocar, snap:retrato_(carregar_(), r.u)}; }); }
function api_primeiroAcesso(d)           { return resp_(() => primeiroAcesso_(d)); }
function api_cargosPublicos()            { return resp_(() => ler_("Cargos").map(c => ({id:String(c.id), nome:String(c.nome), area:String(c.area)})).sort((a, b) => a.area.localeCompare(b.area, "pt-BR") || a.nome.localeCompare(b.nome, "pt-BR"))); }
function api_logout(token)               { return resp_(() => { CacheService.getScriptCache().remove("s:" + token); return true; }); }
function api_snapshot(token)             { return resp_(() => { const u = sessao_(token), D = carregar_(); return retrato_(D, u); }); }
function api_lerEntrevista(token, e)     { return resp_(() => lerEntrevista_(token, e)); }
function api_respostas(token, cargoId)   { return resp_(() => respostas_(token, cargoId)); }
function api_salvarEntrevista(token, d)  { return mudar_(token, () => comSync_(token, () => salvarEntrevista_(token, d))); }
function api_novaEntrevista(token, d)    { return mudar_(token, () => novaEntrevista_(token, d)); }
function api_publicar(token, id, ligar)  { return mudar_(token, () => publicar_(token, id, ligar)); }
function api_salvarCargo(token, d)       { return mudar_(token, () => comSync_(token, () => salvarCargo_(token, d))); }
function api_excluirCargo(token, id)     { return mudar_(token, () => comSync_(token, () => excluirCargo_(token, id))); }
function api_salvarUsuario(token, email, dados) { return mudar_(token, () => salvarUsuario_(token, email, dados)); }
function api_salvarPosicoes(token, d)  { return mudar_(token, () => comSync_(token, () => salvarPosicoes_(token, d))); }
function api_definirSuperior(token, id, pai) { return mudar_(token, () => comSync_(token, () => definirSuperior_(token, id, pai))); }
function api_salvarCargos(token, lista)  { return mudar_(token, () => comSync_(token, () => salvarCargos_(token, lista))); }
function api_salvarOrganograma(token, d) { return mudar_(token, () => comSync_(token, () => salvarOrganograma_(token, d))); }
function api_trocarSenha(token, atual, nova) { return resp_(() => escrever_(() => trocarSenha_(token, atual, nova))); }
function api_redefinirSenha(token, email) { return mudar_(token, () => redefinirSenha_(token, email)); }
function api_importarCargos(token, linhas) { return mudar_(token, () => comSync_(token, () => importarCargos_(token, linhas))); }
function api_solicitar(token, d)         { return mudar_(token, () => solicitar_(token, d)); }
function api_resolverSolicitacao(token, id, status, resposta) { return mudar_(token, () => resolverSolicitacao_(token, id, status, resposta)); }
function api_pedirCorrecaoCargo(token, d) { return mudar_(token, () => pedirCorrecaoCargo_(token, d)); }
function api_meusPedidos(token)           { return resp_(() => { const D = carregar_(); return meusPedidosDe_(D, modelo_(D), sessao_(token).email); }); }
function api_resolverCorrecaoCargo(token, id, decisao, resposta, cargoId) { return mudar_(token, () => resolverCorrecaoCargo_(token, id, decisao, resposta, cargoId)); }

/* ---- TO BE (organograma futuro): só administradores. A primeira abertura copia o AS IS. ---- */
function api_tobe(token)                 { return resp_(() => { const u = sessao_(token); soAdmin_(u, "ver o TO BE"); if (!tobeIniciado_()) escrever_(() => { if (!tobeIniciado_()) iniciarTobe_(u); }); return tobeVisao_(); }); }
function api_tobeSalvar(token, d)        { return mudar_(token, () => tobeSalvar_(tobeAdmin_(token, "salvar o TO BE"), d)); }
function api_tobeJustificar(token, ref, texto) { return mudar_(token, () => tobeJustificar_(tobeAdmin_(token, "justificar o TO BE"), ref, texto)); }
function api_tobeResolverConflito(token, cargoId, campo, decisao, justificativa) { return mudar_(token, () => tobeResolver_(tobeAdmin_(token, "resolver conflito do TO BE"), cargoId, campo, decisao, justificativa)); }
function api_tobeSincronizar(token)      { return mudar_(token, () => sincronizarTobe_(tobeAdmin_(token, "sincronizar o TO BE").nome)); }
function api_tobePublicar(token, d)      { return mudar_(token, () => tobePublicar_(tobeAdmin_(token, "publicar o TO BE"), d)); }
/* visão de outro perfil: não cria sessão nem token; só o administrador pede */
function api_visualizarComo(token, d)    { return resp_(() => { soAdmin_(sessao_(token), "visualizar como"); return visualizarComo_(d || {}); }); }

/* ============================== acesso a dados ============================== */
let _SS = null;
function planilha_() {
  if (_SS) return _SS;
  const id = PropertiesService.getScriptProperties().getProperty("PLANILHA_ID");
  if (!id) throw new Error("A plataforma ainda não foi configurada. Rode a função configurar() no Apps Script.");
  _SS = SpreadsheetApp.openById(id);
  const props = PropertiesService.getScriptProperties();
  if (Number(props.getProperty("ESQUEMA") || 1) < ESQUEMA) { esquema_(_SS); props.setProperty("ESQUEMA", String(ESQUEMA)); }
  return _SS;
}
/** Garante que todas as abas existem e têm todas as colunas (planilhas antigas ganham as colunas novas no fim). */
function esquema_(ss) {
  Object.keys(ABAS).forEach(nome => {
    const sh = ss.getSheetByName(nome) || ss.insertSheet(nome), cab = ABAS[nome];
    const atual = sh.getLastColumn() ? sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0].map(String) : [];
    if (!atual.filter(Boolean).length) { sh.getRange(1, 1, 1, cab.length).setValues([cab]).setFontWeight("bold").setBackground("#EFEEEB"); sh.setFrozenRows(1); return; }
    const faltam = cab.filter(c => !atual.includes(c));
    if (faltam.length) sh.getRange(1, atual.length + 1, 1, faltam.length).setValues([faltam]).setFontWeight("bold").setBackground("#EFEEEB");
  });
}
/* Cópia da planilha em memória (CacheService). Ler a planilha é o que mais pesa; com a cópia, abrir telas fica rápido.
   Toda gravação feita pela plataforma apaga a cópia. Edições feitas direto na planilha aparecem em até CACHE_SEGUNDOS. */
const TABS_CACHE_ = ["Cargos", "Entrevistas", "Usuarios", "Propostas", "Solicitacoes"];
let _TABS = null;
function tabelas_() {
  if (_TABS) return _TABS;
  const cache = CacheService.getScriptCache(), n = Number(cache.get("db:n") || 0);
  if (n) { const partes = cache.getAll(Array.from({length:n}, (_, i) => "db:" + i)), txt = Array.from({length:n}, (_, i) => partes["db:" + i]);
    if (txt.every(x => typeof x === "string")) { try { return (_TABS = JSON.parse(txt.join(""))); } catch (e) {} } }
  const ss = planilha_(), t = {};
  TABS_CACHE_.forEach(aba => {
    const v = ss.getSheetByName(aba).getDataRange().getValues(), cab = v.shift().map(String), ir = cab.indexOf("respostas");
    if (ir >= 0) v.forEach(l => { l[ir] = l[ir] ? 1 : ""; });               // a entrevista inteira não vai para a cópia: é lida só quando pedida
    t[aba] = {cab, linhas:v.filter(l => l.some(c => c !== "")).map(l => l.map(c => c instanceof Date ? c.toISOString() : c))};
  });
  const s = JSON.stringify(t), TAM = 90000, partes = {};
  for (let i = 0; i * TAM < s.length; i++) partes["db:" + i] = s.slice(i * TAM, (i + 1) * TAM);
  try { cache.putAll(Object.assign(partes, {"db:n":String(Object.keys(partes).length)}), CACHE_SEGUNDOS); } catch (e) {}
  return (_TABS = t);
}
function invalida_() { _TABS = null; try { CacheService.getScriptCache().remove("db:n"); } catch (e) {} }
function ler_(aba) { const t = tabelas_()[aba]; return t.linhas.map(l => { const o = {}; t.cab.forEach((c, i) => o[c] = l[i]); return o; }); }
const colunas_ = sh => sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0].map(String);
function achar_(aba, chave, valor) {          // linha (1-based) onde a coluna 'chave' vale 'valor'
  const sh = planilha_().getSheetByName(aba), n = sh.getLastRow(), col = colunas_(sh).indexOf(chave) + 1;
  if (n < 2 || !col) return 0;
  const v = sh.getRange(2, col, n - 1, 1).getValues();
  for (let i = 0; i < v.length; i++) if (String(v[i][0]) === String(valor)) return i + 2;
  return 0;
}
/** Atualiza a linha (ou cria) numa gravação só. 'manterCopia' evita apagar a cópia em memória (para dados que ninguém lê, como o último acesso). */
function gravar_(aba, chave, obj, manterCopia) {
  const sh = planilha_().getSheetByName(aba), cab = colunas_(sh), linha = achar_(aba, chave, obj[chave]);
  if (linha) { const r = sh.getRange(linha, 1, 1, cab.length), v = r.getValues()[0]; cab.forEach((c, i) => { if (c in obj) v[i] = obj[c]; }); r.setValues([v]); }
  else sh.appendRow(cab.map(c => c in obj ? obj[c] : ""));
  if (!manterCopia) invalida_();
}
/* utilitários que antes estavam repetidos em várias ações */
const texto_ = (v, max) => String(v || "").trim().slice(0, max);
const proximoIdEntrevista_ = D => Math.max(0, ...D.entrevistas.map(x => x.id)) + 1;
function novoIdCargo_(nome, usados) { let id; do { id = slug_(nome) + "-" + Math.random().toString(36).slice(2, 6); } while (usados.has(id)); usados.add(id); return id; }
/** nome, área e pessoa de um cargo, já limpos e validados (usado ao incluir, editar, importar e na janela da entrevista) */
function dadosCargo_(d, rotulo) {
  const nome = texto_(d.nome, 80), area = texto_(d.area, 60), pessoa = texto_(d.pessoa, 80), r = rotulo ? rotulo + ": " : "";
  if (!nome) throw new Error(r + "falta o nome do cargo.");
  if (!area) throw new Error(r + "falta a área" + (rotulo ? " (" + nome + ")" : "") + ".");
  return {nome, area, pessoa};
}
/** diz se, trocando o superior de 'id' por 'pai', o cargo ficaria abaixo dele mesmo ('paiDe' = mapa id → superior) */
function fazCiclo_(id, pai, paiDe) { for (let p = pai, k = 0; p && k++ < 80; p = paiDe[p]) if (p === id) return true; return false; }
/** código do cargo (SC-RHU-01): a ordem é a dos cargos da mesma área na lista dada (AS IS ou TO BE) */
function codigoDe_(lista, c) { const ar = norm(c.area).replace(/[^a-z]/g, "").slice(0, 3).toUpperCase(); const i = lista.filter(x => x.area === c.area).indexOf(c) + 1; return SIGLA + "-" + ar + "-" + String(i).padStart(2, "0"); }
/** nível (1 = topo) de um cargo, contando os superiores que estão em 'por' (id → cargo) */
function nivelDe_(c, por) { let n = 1, p = c.pai ? por[c.pai] : null; while (p && n < 30) { n++; p = p.pai ? por[p.pai] : null; } return n; }
/** anota no histórico do manual (as últimas 30 entradas) */
const anotaHistorico_ = (hist, rev, u, motivo) => hist.concat([{rev, data:new Date().toISOString(), por:u.nome, motivo}]).slice(-30);
function log_(quem, acao) { planilha_().getSheetByName("Registro").appendRow([new Date(), quem, String(acao).slice(0, 300)]); }
function escrever_(fn) { const lock = LockService.getScriptLock(); lock.waitLock(20000); try { return fn(); } finally { lock.releaseLock(); } }
const J_ = (s, padrao) => { try { return s ? JSON.parse(s) : padrao; } catch (e) { return padrao; } };

function carregar_() {
  const cargos = ler_("Cargos").map(r => ({id:String(r.id), nome:String(r.nome), area:String(r.area), pai:r.pai ? String(r.pai) : null, pessoa:String(r.pessoa),
    conteudo: r.status ? {missao:String(r.missao || ""), funcoes:J_(r.funcoes, []), rotinas:J_(r.rotinas, []), jornada:String(r.jornada || ""), tempoEmpresa:String(r.tempoEmpresa || ""),
      formacao:String(r.formacao || ""), experiencia:String(r.experiencia || ""), habilidades:J_(r.habilidades, []), relacoes:J_(r.relacoes, []), recorre:String(r.recorre || ""),
      ferramentas:J_(r.ferramentas, []), status:String(r.status), entrevistaId:r.entrevistaId || null, revisao:Number(r.revisao) || 0, historico:J_(r.historico, [])} : null,
    x:r.x === "" || r.x == null ? null : Number(r.x), y:r.y === "" || r.y == null ? null : Number(r.y)}));
  const por = {}; cargos.forEach(c => por[c.id] = c);
  cargos.forEach(c => c.nivel = nivelDe_(c, por));
  CARGOS = cargos;                              // o leitor de entrevistas (abaixo) usa esta lista para sugerir o cargo
  return {
    cargos,
    entrevistas: ler_("Entrevistas").map(r => ({id:Number(r.id), cargo:String(r.cargoId), pessoa:String(r.pessoa), data:String(r.data || ""), link:String(r.link || ""), auto:J_(r.auto, null), temRespostas:!!r.respostas})),
    solicitacoes: ler_("Solicitacoes").map(r => ({id:String(r.id), cargoId:String(r.cargoId), origemId:String(r.origemId || ""), texto:String(r.texto || ""), motivo:String(r.motivo || ""), status:String(r.status || "Aberta"),
      criadoPor:String(r.criadoPor || ""), criadoPorEmail:String(r.criadoPorEmail || "").toLowerCase(), criadoEm:String(r.criadoEm || ""), resolvidoPor:String(r.resolvidoPor || ""), resolvidoEm:String(r.resolvidoEm || ""), resposta:String(r.resposta || ""), tipo:String(r.tipo || ""), cargoSugerido:String(r.cargoSugerido || "")})),
    usuarios: ler_("Usuarios").map(r => ({email:String(r.email).toLowerCase(), nome:String(r.nome), perfil:String(r.perfil), cargo:r.cargoId ? String(r.cargoId) : null, cargoInformado:String(r.cargoInformado || ""), cargoSolicitado:r.cargoSolicitado ? String(r.cargoSolicitado) : null, status:String(r.status), salt:String(r.salt), hash:String(r.hash)}))
  };
}

/* ============================== autenticação ============================== */
function hashSenha_(senha, salt) {
  let h = salt + ":" + senha;
  for (let i = 0; i < VOLTAS_HASH; i++) h = Utilities.base64Encode(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, h + salt, Utilities.Charset.UTF_8));
  return h;
}
const igual_ = (a, b) => { if (a.length !== b.length) return false; let r = 0; for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i); return r === 0; };
const emailOk_ = e => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e);

function primeiroAcesso_(d) {
  const nome = String(d.nome || "").trim(), email = String(d.email || "").trim().toLowerCase(), codigo = String(d.codigo || "").trim();
  if (nome.length < 3) throw new Error("Informe seu nome completo.");
  if (!emailOk_(email)) throw new Error("Informe um e-mail válido.");
  if (String(d.senha || "").length < 8) throw new Error("A senha precisa ter pelo menos 8 caracteres.");
  if (d.senha !== d.senha2) throw new Error("As duas senhas não são iguais.");
  return escrever_(() => {
    if (achar_("Usuarios", "email", email)) throw new Error("Não foi possível concluir. Se você já tem cadastro, use “Entrar”.");
    const props = PropertiesService.getScriptProperties(), esperado = props.getProperty("ADMIN_CODIGO");
    const admin = !!(codigo && esperado && igual_(codigo.toUpperCase(), esperado));
    if (codigo && !admin) throw new Error("Código de administrador inválido.");
    /* o cargo escolhido é só um PEDIDO: quem define o cargo de verdade é o administrador (cargoId fica vazio aqui) */
    let pedido = "", informado = "";
    if (!admin) {
      const escolhido = d.cargoId == null ? "" : String(d.cargoId);
      if (escolhido) {
        if (!ler_("Cargos").some(c => String(c.id) === escolhido)) throw new Error("Escolha seu cargo na lista.");
        pedido = escolhido;
      } else if (d.cargoDuvida === true) {
        const txt = String(d.cargo || "").trim();
        if (txt.length < 5) throw new Error("Descreva em poucas palavras qual é o seu cargo ou a sua dúvida.");
        informado = txt.slice(0, 200);
      } else throw new Error("Escolha seu cargo na lista. Se ele não aparecer, marque “Não encontrei meu cargo”.");
    }
    const salt = Utilities.getUuid().replace(/-/g, "");
    gravar_("Usuarios", "email", {email, nome, perfil:admin ? "admin" : "colaborador", cargoId:"", cargoSolicitado:pedido, cargoInformado:informado, status:admin ? "Ativo" : "Pendente",
      salt, hash:hashSenha_(String(d.senha), salt), criadoEm:new Date(), ultimoAcesso:""});
    if (admin) props.deleteProperty("ADMIN_CODIGO");         // o código vale uma vez só
    log_(nome, admin ? "Criou o acesso de administrador" : "Pediu o primeiro acesso");
    return {admin};
  });
}
function login_(email, senha) {
  email = String(email || "").trim().toLowerCase();
  const cache = CacheService.getScriptCache(), chave = "t:" + email, tentativas = Number(cache.get(chave) || 0);
  if (tentativas >= MAX_TENTATIVAS) throw new Error("Muitas tentativas. Aguarde 15 minutos e tente de novo.");
  const u = ler_("Usuarios").find(x => String(x.email).toLowerCase() === email);
  const certo = u && igual_(hashSenha_(String(senha || ""), String(u.salt)), String(u.hash));
  if (!certo) { cache.put(chave, String(tentativas + 1), 900); throw new Error("E-mail ou senha incorretos."); }   // mesma mensagem, de propósito
  if (u.status === "Pendente") throw new Error("Seu cadastro ainda aguarda aprovação do administrador.");
  if (u.status !== "Ativo") throw new Error("Seu acesso está desativado. Fale com o administrador.");
  cache.remove(chave);
  const token = Utilities.getUuid().replace(/-/g, "") + Utilities.getUuid().replace(/-/g, "");
  cache.put("s:" + token, email, SESSAO_SEGUNDOS);
  escrever_(() => { gravar_("Usuarios", "email", {email, ultimoAcesso:new Date()}, true); log_(u.nome, "Entrou na plataforma"); });
  return {token, trocar:!!u.trocarSenha, u:{email, nome:String(u.nome), perfil:String(u.perfil), cargo:u.cargoId ? String(u.cargoId) : null, status:String(u.status)}};
}
function sessao_(token) {
  const cache = CacheService.getScriptCache(), email = token ? cache.get("s:" + token) : null;
  if (!email) throw new Error("SESSAO");
  const r = ler_("Usuarios").find(x => String(x.email).toLowerCase() === email), u = r && {email, nome:String(r.nome), perfil:String(r.perfil), cargo:r.cargoId ? String(r.cargoId) : null, status:String(r.status)};
  if (!u || u.status !== "Ativo") { cache.remove("s:" + token); throw new Error("SESSAO"); }
  cache.put("s:" + token, email, SESSAO_SEGUNDOS);        // renova a cada uso
  return u;
}
const soAdmin_ = (u, o) => { if (u.perfil !== "admin") { log_(u.nome, "Acesso negado: " + o); throw new Error("NEGADO"); } };

/* ============================== regras de acesso (negado por padrão) ============================== */
function modelo_(D) {
  const byId = id => D.cargos.find(c => c.id === id);
  const desc = id => D.cargos.filter(c => c.pai === id).flatMap(f => [f.id, ...desc(f.id)]);
  const scope = u => {
    if (!u || u.status !== "Ativo") return new Set();
    if (u.perfil === "admin" || u.perfil === "socio") return new Set(D.cargos.map(c => c.id));
    const meu = byId(u.cargo); if (!meu) return new Set();
    if (u.perfil === "gestor") return new Set([meu.id, ...desc(meu.id)]);
    if (u.perfil === "colaborador") return new Set(D.cargos.filter(c => c.area === meu.area && c.nivel === meu.nivel).map(c => c.id));
    return new Set();
  };
  const estadoReal = c => !c.conteudo ? "sem" : c.conteudo.status;
  const estadoPublico = c => estadoReal(c) === "publicado" ? "publicado" : "construcao";
  const estadoVisto = (c, u) => u.perfil === "admin" ? estadoReal(c) : estadoPublico(c);
  const mostra = (c, u) => !!c.conteudo && (u.perfil === "admin" || c.conteudo.status === "publicado");
  const codigoDe = c => codigoDe_(D.cargos, c);
  const posicaoDe = c => ({codigo:codigoDe(c), superior:c.pai && byId(c.pai) ? {id:c.pai, nome:byId(c.pai).nome, pessoa:byId(c.pai).pessoa} : null, temSuperior:!!c.pai,
    subordinados:D.cargos.filter(x => x.pai === c.id).map(x => ({id:x.id, nome:x.nome, pessoa:x.pessoa}))});
  const clone = o => JSON.parse(JSON.stringify(o));
  const entrevistaDe = id => D.entrevistas.find(e => e.cargo === id);
  /* o manual como vai para quem não é administrador: sem o id da entrevista e sem o histórico (que cita a origem) */
  const manual_ = (c, u) => { const m = clone(c.conteudo); if (u.perfil !== "admin") { delete m.entrevistaId; delete m.historico; } return m; };
  const ficha = (u, c, s) => {
    const e = entrevistaDe(c.id), ve = s.has(c.id), base = {id:c.id, nome:c.nome, area:c.area, nivel:c.nivel, pessoa:c.pessoa, ...posicaoDe(c)};
    if (!ve) return {...base, estado:estadoPublico(c), conteudo:null, restrito:true};
    const f = {...base, estado:estadoVisto(c, u), conteudo:mostra(c, u) ? manual_(c, u) : null, restrito:false};
    /* a entrevista (data, pessoa, link, notas) é só do administrador: para os demais a chave nem existe */
    if (u.perfil === "admin") { f.dataEntrevista = e ? e.data : ""; f.entrevista = e ? clone(e) : null; }
    return f;
  };
  const media = l => { const v = l.filter(x => x); return v.length ? Math.round(v.reduce((a, b) => a + b, 0) / v.length * 10) / 10 : null; };
  /* autoavaliação: o administrador tem o diagnóstico completo; o sócio recebe diagnosticoAgregado (o retrato não monta para os demais) */
  const diagnostico = (u, area) => {
    const todas = D.entrevistas.filter(e => Array.isArray(e.auto) && e.auto.some(v => v)), cargoDe = e => byId(e.cargo);
    const doArea = a => todas.filter(e => cargoDe(e) && cargoDe(e).area === a);
    const MIN = 3, areas = [...new Set(D.cargos.map(c => c.area))].map(a => ({area:a, n:doArea(a).length, total:D.entrevistas.filter(e => cargoDe(e) && cargoDe(e).area === a).length}));
    const filtro = area && areas.some(x => x.area === area) ? area : "", resp = filtro ? doArea(filtro) : todas, n = resp.length, liberado = u.perfil === "admin" || n >= MIN;
    const itens = AUTO.map((nome, i) => ({nome, media:liberado ? media(resp.map(e => e.auto[i])) : null, invertido:i === 0}));
    const comparativo = !filtro ? areas.filter(a => a.n && (u.perfil === "admin" || a.n >= MIN)).map(a => ({area:a.area, n:a.n, satisfacao:media(doArea(a.area).map(e => e.auto[7])), sobrecarga:media(doArea(a.area).map(e => e.auto[0]))})) : [];
    return {area:filtro, areas:areas.filter(a => a.total), n, total:filtro ? areas.find(a => a.area === filtro).total : D.entrevistas.length, min:MIN, liberado, itens, comparativo};
  };
  /* o sócio: só a média agregada (por área e geral). Nada que identifique pessoa, entrevista, link ou cargo; abaixo de 3 respostas, sem média nem contagem */
  const diagnosticoAgregado = area => {
    const todas = D.entrevistas.filter(e => Array.isArray(e.auto) && e.auto.some(v => v)), cargoDe = e => byId(e.cargo);
    const doArea = a => todas.filter(e => cargoDe(e) && cargoDe(e).area === a);
    const MIN = 3, areas = [...new Set(D.cargos.map(c => c.area))];
    const filtro = area && areas.includes(area) ? area : "", resp = filtro ? doArea(filtro) : todas, n = resp.length, liberado = n >= MIN;
    const itens = AUTO.map((nome, i) => ({nome, media:liberado ? media(resp.map(e => e.auto[i])) : null, invertido:i === 0}));
    const comparativo = !filtro ? areas.filter(a => doArea(a).length >= MIN).map(a => ({area:a, n:doArea(a).length, satisfacao:media(doArea(a).map(e => e.auto[7])), sobrecarga:media(doArea(a).map(e => e.auto[0]))})) : [];
    return {agregado:true, area:filtro, areas:areas.map(a => doArea(a).length >= MIN ? {area:a} : {area:a, poucos:true}), n:liberado ? n : null, min:MIN, liberado, poucos:!liberado, itens, comparativo};
  };
  return {byId, scope, estadoReal, estadoPublico, estadoVisto, mostra, codigoDe, posicaoDe, ficha, diagnostico, diagnosticoAgregado};
}

/** O "retrato": tudo o que ESTA pessoa pode ver, já filtrado. A tela só lê daqui. */
function retrato_(D, u) {
  const M = modelo_(D), s = M.scope(u), admin = u.perfil === "admin", meuCargo = u.cargo ? M.byId(u.cargo) : null;
  const visiveis = D.cargos.filter(c => s.has(c.id)), n = st => visiveis.filter(c => M.estadoReal(c) === st).length;
  const resumo = {total:visiveis.length, publicado:n("publicado")};
  if (admin) { resumo.revisao = n("revisao"); resumo.sem = n("sem"); resumo.pendentes = D.usuarios.filter(x => x.status === "Pendente").length; resumo.semLista = visiveis.filter(c => M.estadoReal(c) === "sem").map(c => ({id:c.id, nome:c.nome})); }
  const fichas = {}; D.cargos.forEach(c => fichas[c.id] = M.ficha(u, c, s));
  const out = {
    me:{nome:u.nome, perfil:u.perfil, perfilNome:PERFIS[u.perfil].nome, regra:PERFIS[u.perfil].desc, cargo:u.cargo, cargoNome:meuCargo ? meuCargo.nome : null, area:meuCargo ? meuCargo.area : null, nVisiveis:s.size, nTotal:D.cargos.length, admin},
    estrutura:D.cargos.map(c => ({id:c.id, nome:c.nome, area:c.area, nivel:c.nivel, pai:c.pai, pessoa:c.pessoa, x:c.x, y:c.y, codigo:M.codigoDe(c), estado:s.has(c.id) ? M.estadoVisto(c, u) : M.estadoPublico(c), acesso:s.has(c.id)})),
    fichas, ordem:D.cargos.slice().sort((a, b) => a.nivel - b.nivel || a.area.localeCompare(b.area)).map(c => c.id), resumo,
    /* solicitações de mudança: o administrador vê todas; os demais, só as que abriram */
    solicitacoes:D.solicitacoes.filter(x => x.tipo !== TIPO_CORRECAO_ && (admin || x.criadoPorEmail === u.email)).map(x => ({...x, criadoPorEmail:undefined,
      cargoNome:M.byId(x.cargoId) ? M.byId(x.cargoId).nome : "Cargo excluído", origemNome:x.origemId && M.byId(x.origemId) ? M.byId(x.origemId).nome : ""})).reverse()
  };
  out.meusPedidos = meusPedidosDe_(D, M, u.email);                       // a pessoa vê só os próprios pedidos de correção de cargo
  if (admin) {
    resumo.solicitacoesAbertas = D.solicitacoes.filter(x => x.tipo !== TIPO_CORRECAO_ && x.status === "Aberta").length;
    resumo.pedidosCargoAbertos = pedidosCorrecao_(D).filter(x => x.status === "Aberta").length;
    out.pedidosCargo = pedidosAdmin_(D, M);                              // só o administrador: abertos e os 20 últimos respondidos
  }
  if (admin) {
    out.entrevistas = D.entrevistas.map(e => { const c = M.byId(e.cargo); return c ? {...e, cargoNome:c.nome, area:c.area, estado:M.estadoReal(c)} : null; }).filter(Boolean);
    out.perfis = Object.keys(PERFIS).map(k => ({k, nome:PERFIS[k].nome, desc:PERFIS[k].desc}));
    out.usuarios = D.usuarios.map(x => { const adm = x.perfil === "admin", cs = adm ? null : x.cargoSolicitado, sol = cs ? M.byId(cs) : null;   // administrador não tem cargo: nada de pedido
      return {email:x.email, nome:x.nome, perfil:x.perfil, cargo:x.cargo, cargoInformado:adm ? "" : x.cargoInformado, cargoSolicitado:cs, cargoSolicitadoNome:sol ? sol.nome + " · " + sol.area : "",
        status:x.status, cargoNome:x.cargo && M.byId(x.cargo) ? M.byId(x.cargo).nome : "—", ve:M.scope({...x, status:"Ativo"}).size}; });
    const sh = planilha_().getSheetByName("Registro"), ult = sh.getLastRow(), de = Math.max(2, ult - 39);
    out.registro = ult < 2 ? [] : sh.getRange(de, 1, ult - de + 1, 3).getValues().reverse().map(r => ({quando:new Date(r[0]).toISOString(), quem:String(r[1]), acao:String(r[2])}));
  }
  /* autoavaliação: o administrador recebe o diagnóstico completo; o sócio, só a média agregada (sem pessoas, entrevistas ou links).
     Colaborador e gestor não recebem nada disso. O TO BE não vem no retrato: tem tela própria (api_tobe). */
  if (admin) {
    out.diag = {"":M.diagnostico(u, "")}; out.opcoesAreas = true;
    [...new Set(D.cargos.map(c => c.area))].forEach(a => out.diag[a] = M.diagnostico(u, a));
  } else if (u.perfil === "socio") {
    out.diag = {"":M.diagnosticoAgregado("")}; out.opcoesAreas = true;
    [...new Set(D.cargos.map(c => c.area))].forEach(a => out.diag[a] = M.diagnosticoAgregado(a));
  }
  return out;
}

/* ============================== ações do administrador ============================== */
function lerEntrevista_(token, entrada) {
  const u = sessao_(token); soAdmin_(u, "ler entrevista");
  carregar_();                                                   // carrega os cargos (o leitor sugere o cargo a partir deles)
  entrada = entrada || {};
  let texto = String(entrada.texto || ""), origem = "texto colado"; NOTAS_DIAG_ = [];
  if (texto.trim().length < 30 && entrada.link) { texto = lerDoc_(String(entrada.link).trim()); origem = "link do Docs"; }
  if (texto.trim().length < 30) throw new Error("Cole o link do Google Docs da entrevista ou o texto dela.");
  if (texto.length > 60000) throw new Error("Texto grande demais.");
  const r = lerTexto(texto);
  if ((r.avisos || []).some(a => /Não consegui ler a nota/.test(a)))
    r.avisos.push(origem === "texto colado" ? "As notas só podem ser lidas pelo LINK do Google Docs: texto colado perde a formatação, como cor, negrito e marca-texto." : "Para suporte, o que o Google informou sobre as opções: " + (NOTAS_DIAG_.join(" | ") || "nenhuma linha de nota com as 5 opções foi encontrada") + ".");
  return r;
}
function lerDoc_(link) {
  const m = link.match(/^https:\/\/docs\.google\.com\/document\/d\/([\w-]+)/);
  if (!m) throw new Error("O link precisa ser de um Google Docs, no formato https://docs.google.com/document/d/...");
  let doc; try { doc = DocumentApp.openById(m[1]); } catch (e) { throw new Error("Não consegui abrir o documento. Confira o link e se a conta que publicou a plataforma tem acesso a ele."); }
  const corpo = doc.getBody(), linhas = [], grupo = [];
  const soltaGrupo = () => { if (grupo.length >= 2) linhasDeOpcoes_(grupo).forEach(l => linhas.push(l)); else grupo.forEach(el => linhas.push(el.editAsText().getText())); grupo.length = 0; };
  const ehOpcaoSozinha = el => { const s = el.editAsText().getText(); return /^\W*\(\s*[1-5]\s*\)/.test(s) && !(/\(\s*1\s*\)/.test(s) && /\(\s*5\s*\)/.test(s)); };
  for (let i = 0; i < corpo.getNumChildren(); i++) {
    const el = corpo.getChild(i), t = el.getType(), texto = t === DocumentApp.ElementType.PARAGRAPH || t === DocumentApp.ElementType.LIST_ITEM;
    if (texto && ehOpcaoSozinha(el)) { grupo.push(el); continue; }
    soltaGrupo();
    if (texto) linhas.push(textoComMarca_(el));
    else if (t === DocumentApp.ElementType.TABLE) {
      const tb = el.asTable();
      for (let r = 0; r < tb.getNumRows(); r++) {
        const row = tb.getRow(r), opcoes = linhaDeTabela_(row); if (opcoes) { linhas.push(opcoes); continue; }
        const cel = []; for (let c = 0; c < row.getNumCells(); c++) cel.push(row.getCell(c).getText().replace(/\s+/g, " ").trim()); linhas.push("| " + cel.join(" | ") + " |");
      }
    }
  }
  soltaGrupo();
  return linhas.join("\n");
}
/* ---------- autoavaliação (perguntas 20 a 27): qual das 5 opções foi MARCADA? ----------
   Regra: a marcada é a opção que está FORMATADA DIFERENTE das outras quatro. Vale qualquer marca: cor da letra, marca-texto, negrito, itálico,
   sublinhado/tracejado, tachado, tamanho, fonte. Compara só as cinco opções entre si (o texto de comentário depois da nota não atrapalha). */
const ATRIBUTOS_ = ["BOLD", "ITALIC", "UNDERLINE", "STRIKETHROUGH", "FOREGROUND_COLOR", "BACKGROUND_COLOR", "FONT_SIZE", "FONT_FAMILY", "LINK_URL"];
const vazioAtrib_ = (k, v) => v === null || v === undefined || v === false || v === "" || (k === "BACKGROUND_COLOR" && String(v).toLowerCase() === "#ffffff") || (k === "FOREGROUND_COLOR" && String(v).toLowerCase() === "#000000");
/* formatação de UM caractere: junta getAttributes() com os leitores diretos (getBackgroundColor, isBold...), que no Google nem sempre dizem a mesma coisa */
const atribDe_ = (tx, i) => {
  const a = Object.assign({}, tx.getAttributes(i) || {});
  [["BACKGROUND_COLOR", "getBackgroundColor"], ["FOREGROUND_COLOR", "getForegroundColor"], ["BOLD", "isBold"], ["ITALIC", "isItalic"], ["UNDERLINE", "isUnderline"], ["STRIKETHROUGH", "isStrikethrough"], ["FONT_SIZE", "getFontSize"], ["FONT_FAMILY", "getFontFamily"], ["LINK_URL", "getLinkUrl"]]
    .forEach(([k, fn]) => { try { if (typeof tx[fn] === "function") { const v = tx[fn](i); if (!vazioAtrib_(k, v)) a[k] = v; } } catch (e) {} });
  return a;
};
const assinatura_ = (tx, i) => { const a = atribDe_(tx, i); return ATRIBUTOS_.map(k => vazioAtrib_(k, a[k]) ? "" : String(a[k]).toLowerCase()).join("|"); };
const atribVistos_ = (tx, de, ate) => { const v = {}; for (let i = de; i < ate; i++) { const a = atribDe_(tx, i); ATRIBUTOS_.forEach(k => { if (!vazioAtrib_(k, a[k])) v[k + "=" + String(a[k]).toLowerCase()] = 1; }); } return Object.keys(v); };
/** Entre as assinaturas das opções, devolve o índice da ÚNICA que difere das outras (ou -1: nenhuma marcada, ou ambíguo). */
function indiceUnico_(sigs) {
  const grupos = {}; sigs.forEach((s, i) => (grupos[s] = grupos[s] || []).push(i));
  const ks = Object.keys(grupos); if (ks.length !== 2) return -1;
  const a = grupos[ks[0]], b = grupos[ks[1]];
  return a.length === 1 && b.length >= 2 ? a[0] : b.length === 1 && a.length >= 2 ? b[0] : -1;
}
/** opcoes = [{sig, dig}]: sig = formatação do que está escrito na opção (parênteses + número); dig = só o número. Tenta com tudo e depois só com o número. */
const marcadaEntre_ = opcoes => { const i = indiceUnico_(opcoes.map(o => o.sig)); return i >= 0 ? i : indiceUnico_(opcoes.map(o => o.dig)); };
const OPCAO_ = /\(\s*([1-5])\s*\)/g;
const sigTrecho_ = (tx, de, ate) => { const l = []; for (let i = de; i < ate; i++) l.push(assinatura_(tx, i)); return l; };
/** Uma linha com as cinco opções juntas: devolve a linha com *** em volta da marcada (o formato que o leitor entende). */
let NOTAS_DIAG_ = [];                       // o que o leitor viu nas linhas de nota sem marca (aparece no aviso quando a nota não é lida)
function textoComMarca_(el) {
  const tx = el.editAsText(), s = tx.getText();
  if (!/\(\s*1\s*\)/.test(s) || !/\(\s*5\s*\)/.test(s)) return s;
  const ops = [...s.matchAll(OPCAO_)].map(m => { const ini = m.index, fim = ini + m[0].length, id = ini + m[0].search(/[1-5]/), vis = []; for (let i = ini; i < fim; i++) if (s[i].trim()) vis.push(i);
    return {ini, fim, sig:vis.map(i => assinatura_(tx, i)).join("/"), dig:assinatura_(tx, id)}; });
  const k = ops.length >= 2 ? marcadaEntre_(ops) : -1;
  if (k < 0 && NOTAS_DIAG_.length < 2 && ops.length) NOTAS_DIAG_.push(ops.length + " opções; marcas vistas: " + (atribVistos_(tx, ops[0].ini, ops[ops.length - 1].fim).join(", ") || "nenhuma"));
  return k < 0 ? s : s.slice(0, ops[k].ini) + "***" + s.slice(ops[k].ini, ops[k].fim) + "***" + s.slice(ops[k].fim);
}
/** Opções em linhas separadas (uma por parágrafo): recebe os parágrafos do grupo e devolve as linhas, com a marcada entre *** */
function linhasDeOpcoes_(els) {
  const itens = els.map(el => { const tx = el.editAsText(), s = tx.getText(), m = s.match(/\(\s*[1-5]\s*\)/), ini = m.index, fim = ini + m[0].length, vis = [];
    for (let i = ini; i < fim; i++) if (s[i].trim()) vis.push(i);
    return {s, ini, fim, sig:vis.map(i => assinatura_(tx, i)).join("/"), dig:assinatura_(tx, ini + m[0].search(/[1-5]/))}; });
  const k = marcadaEntre_(itens);
  return itens.map((o, i) => i === k ? o.s.slice(0, o.ini) + "***" + o.s.slice(o.ini, o.fim) + "***" + o.s.slice(o.fim) : o.s);
}
/** Opções em células de tabela (uma por célula): a marcada é a de formatação OU cor de fundo da célula diferente das outras. */
function linhaDeTabela_(row) {
  const n = row.getNumCells(), cel = []; let numeros = 0;
  for (let c = 0; c < n; c++) { const ce = row.getCell(c), txt = ce.getText().replace(/\s+/g, " ").trim(), m = txt.match(/^\W*\(?\s*([1-5])\s*\)?\W*$/);
    if (m) { numeros++; const tx = ce.editAsText(), vis = []; for (let i = 0; i < txt.length && i < tx.getText().length; i++) if (tx.getText()[i].trim()) vis.push(i);
      let fundo = ""; try { fundo = String(ce.getBackgroundColor() || "").toLowerCase(); if (fundo === "#ffffff") fundo = ""; } catch (e) {}
      cel.push({n:m[1], sig:vis.map(i => assinatura_(tx, i)).join("/") + "#" + fundo, dig:assinatura_(tx, Math.max(0, tx.getText().search(/[1-5]/))) + "#" + fundo}); } }
  if (numeros < 4 || numeros !== n && numeros < n - 1) return null;
  const k = marcadaEntre_(cel);
  return cel.map((o, i) => i === k ? "***(  " + o.n + "  )***" : "(  " + o.n + "  )").join("   ");
}
function salvarEntrevista_(token, d) {
  const u = sessao_(token); soAdmin_(u, "salvar entrevista");
  const D = carregar_(), M = modelo_(D);
  d = d || {}; d.publicar = !!d.publicar;
  const cont = validarConteudo(d);
  if (d.link && !LINK.test(d.link)) throw new Error("O link precisa ser de um Google Docs, no formato https://docs.google.com/document/d/...");
  // A entrevista NUNCA cria cargo: ela se liga a um cargo que já está no organograma.
  const c = M.byId(String(d.cargoId || ""));
  if (!c) throw new Error("Escolha um cargo que já esteja no organograma. Se ele não existe, inclua-o primeiro em “Editar organograma”.");
  // dados do cargo (nome, área, ocupante): só mudam se o administrador editou à mão nesta tela
  if (d.cargo && typeof d.cargo === "object") {
    const {nome, area, pessoa} = dadosCargo_(d.cargo);
    if (nome !== c.nome || area !== c.area || pessoa !== c.pessoa) { gravar_("Cargos", "id", {id:c.id, nome, area, pessoa}); log_(u.nome, "Editou o cargo " + c.nome + (nome !== c.nome ? " → " + nome : "")); }
  }
  let e = D.entrevistas.find(x => x.cargo === c.id);
  const eid = e ? e.id : proximoIdEntrevista_(D);
  const auto = Array.isArray(d.auto) ? d.auto.slice(0, 8).map(v => [1, 2, 3, 4, 5].includes(+v) ? +v : null) : (e ? e.auto : null);
  const ent = {id:eid, cargoId:c.id, pessoa:String(d.pessoa || c.pessoa).trim().slice(0, 80), data:String(d.data || "").slice(0, 20), link:d.link || "", auto:auto ? JSON.stringify(auto) : "", registradoPor:u.nome, registradoEm:new Date()};
  if (Array.isArray(d.respostas)) ent.respostas = cont.respostas.length ? JSON.stringify(cont.respostas).slice(0, 49000) : "";
  gravar_("Entrevistas", "id", ent);
  (Array.isArray(d.solicitacoes) ? d.solicitacoes : []).slice(0, 20).forEach(s => novaSolicitacao_(u, D, {cargoId:s.cargoId, origemId:c.id, texto:s.texto, motivo:s.motivo}));
  // revisão: a primeira emissão é Rev. 00; cada edição de um manual que já existia sobe o número e guarda o motivo
  const rev = c.conteudo ? c.conteudo.revisao + 1 : 0;
  const hist = anotaHistorico_(c.conteudo ? c.conteudo.historico : [], rev, u, c.conteudo ? texto_(d.motivoRevisao, 300) || "Atualização do manual" : "Emissão inicial, a partir de entrevista");
  gravar_("Cargos", "id", {id:c.id, revisao:rev, historico:JSON.stringify(hist), missao:cont.missao, funcoes:JSON.stringify(cont.funcoes), rotinas:JSON.stringify(cont.rotinas), jornada:cont.jornada, tempoEmpresa:cont.tempoEmpresa, formacao:cont.formacao,
    experiencia:cont.experiencia, habilidades:JSON.stringify(cont.habilidades), relacoes:JSON.stringify(cont.relacoes), recorre:cont.recorre, ferramentas:JSON.stringify(cont.ferramentas),
    status:d.publicar ? "publicado" : "revisao", entrevistaId:eid});
  log_(u.nome, (d.publicar ? "Publicou" : "Salvou para revisão") + " o manual: " + c.nome);
  return {id:c.id};
}
function publicar_(token, id, ligar) {
  const u = sessao_(token); soAdmin_(u, "publicar manual");
  const D = carregar_(), c = modelo_(D).byId(String(id));
  if (!c || !c.conteudo) throw new Error("Esse cargo ainda não tem entrevista.");
  if (ligar && !c.conteudo.missao) throw new Error("Falta a missão deste cargo. Clique em Editar e escreva antes de publicar.");
  const v = ligar ? violacoesEstilo(c.conteudo.funcoes, c.conteudo.rotinas) : [];
  if (v.length) throw new Error(mensagemEstilo(v) + " Clique em Editar e use “Ajustar frases”.");
  gravar_("Cargos", "id", {id:c.id, status:ligar ? "publicado" : "revisao"});
  log_(u.nome, (ligar ? "Publicou" : "Tirou do ar") + " o manual: " + c.nome);
  return true;
}
function salvarUsuario_(token, email, dados) {
  const u = sessao_(token); soAdmin_(u, "editar usuário");
  const D = carregar_(), M = modelo_(D), alvo = D.usuarios.find(x => x.email === String(email).toLowerCase());
  if (!alvo) throw new Error("Usuário não encontrado.");
  if (!PERFIS[dados.perfil]) throw new Error("Perfil inválido.");
  if (!["Ativo", "Pendente", "Inativo"].includes(dados.status)) throw new Error("Situação inválida.");
  if (dados.perfil !== "admin" && !M.byId(String(dados.cargo || ""))) throw new Error("Escolha um cargo para este perfil.");
  if (alvo.perfil === "admin" && dados.perfil !== "admin" && D.usuarios.filter(x => x.perfil === "admin" && x.status === "Ativo").length < 2) throw new Error("Não é possível remover o último administrador.");
  if (alvo.email === u.email && dados.status !== "Ativo") throw new Error("Você não pode desativar o próprio acesso.");
  // ao aprovar, o pedido de cargo já foi resolvido: limpa o que a pessoa escreveu no primeiro acesso
  const resolvido = dados.status === "Ativo" ? {cargoSolicitado:"", cargoInformado:""} : {};
  gravar_("Usuarios", "email", {email:alvo.email, perfil:dados.perfil, cargoId:dados.perfil === "admin" ? "" : dados.cargo, status:dados.status, ...resolvido});
  log_(u.nome, "Alterou " + alvo.nome + ": " + PERFIS[dados.perfil].nome + ", " + dados.status);
  return true;
}


/* ---- a entrevista inteira (respostas): lida só quando o administrador pede ---- */
function respostas_(token, cargoId) {
  const u = sessao_(token); soAdmin_(u, "ver entrevista completa");
  const sh = planilha_().getSheetByName("Entrevistas"), linha = achar_("Entrevistas", "cargoId", String(cargoId));
  if (!linha) return [];
  const i = colunas_(sh).indexOf("respostas");
  return i < 0 ? [] : J_(sh.getRange(linha, i + 1).getValue(), []);
}

/* ---- nova entrevista: cria o Doc a partir do template, já com pessoa, cargo e data ---- */
function novaEntrevista_(token, d) {
  const u = sessao_(token); soAdmin_(u, "criar documento de entrevista");
  d = d || {};
  const D = carregar_(), c = modelo_(D).byId(String(d.cargoId || ""));
  if (!c) throw new Error("Escolha o cargo no organograma.");
  const pessoa = String(d.pessoa || c.pessoa || "").trim().slice(0, 80);
  const data = String(d.data || "").trim().slice(0, 20) || Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "dd/MM/yyyy");
  let modelo; try { modelo = DocumentApp.openById(TEMPLATE_ENTREVISTA); } catch (e) { throw new Error("Não consegui abrir o template de entrevista. Confira se a conta que publicou a plataforma tem acesso a ele."); }
  const doc = DocumentApp.create("Entrevista " + (pessoa || c.nome) + " (" + c.nome + ") | " + EMPRESA), corpo = doc.getBody(), orig = modelo.getBody(), T = DocumentApp.ElementType;
  for (let i = 0; i < orig.getNumChildren(); i++) {
    const el = orig.getChild(i).copy(), t = el.getType();
    if (t === T.PARAGRAPH) corpo.appendParagraph(el); else if (t === T.TABLE) corpo.appendTable(el); else if (t === T.LIST_ITEM) corpo.appendListItem(el); else if (t === T.HORIZONTAL_RULE) corpo.appendHorizontalRule();
  }
  if (corpo.getNumChildren() > 1 && corpo.getChild(0).getType() === T.PARAGRAPH && !corpo.getChild(0).asParagraph().getText()) corpo.getChild(0).removeFromParent();
  const preencher = (rotulo, valor) => {                   // escreve o valor ao lado do rótulo, na tabela do cabeçalho
    if (!valor) return;
    for (const tb of corpo.getTables()) for (let r = 0; r < tb.getNumRows(); r++) for (let k = 0; k < tb.getRow(r).getNumCells(); k++) {
      const tx = tb.getRow(r).getCell(k).editAsText(), s = tx.getText(), limpo = norm(s.replace(/\*/g, ""));
      if (limpo === norm(rotulo)) { const ini = s.length; tx.appendText(" " + valor); tx.setBold(ini, ini + valor.length, false); return; }
    }
  };
  preencher("Nome", pessoa); preencher("Cargo", c.nome); preencher("Data da entrevista", data);
  try { if (u.email) doc.addEditor(u.email); } catch (e) {}                 // quem pediu também pode editar (se for o dono, nada muda)
  doc.saveAndClose();
  const link = "https://docs.google.com/document/d/" + doc.getId() + "/edit";
  const e = D.entrevistas.find(x => x.cargo === c.id);
  if (!c.conteudo) gravar_("Entrevistas", "id", {id:e ? e.id : proximoIdEntrevista_(D), cargoId:c.id, pessoa, data, link, registradoPor:u.nome, registradoEm:new Date()});
  log_(u.nome, "Criou o documento de entrevista: " + c.nome);
  return {link, cargoId:c.id, jaTinhaManual:!!c.conteudo};
}

/* ---- solicitações de mudança ("chamados"): o que mudou num cargo e mexe em outro ---- */
function novaSolicitacao_(u, D, s) {
  const alvo = D.cargos.find(c => c.id === String(s.cargoId || ""));
  if (!alvo) throw new Error("Escolha o cargo que precisa mudar.");
  const texto = String(s.texto || "").trim().slice(0, 1000);
  if (texto.length < 5) throw new Error("Descreva o que precisa mudar.");
  const id = "S" + Utilities.getUuid().replace(/-/g, "").slice(0, 10);
  gravar_("Solicitacoes", "id", {id, cargoId:alvo.id, origemId:String(s.origemId || ""), texto, motivo:String(s.motivo || "").trim().slice(0, 600), status:"Aberta",
    criadoPor:u.nome, criadoPorEmail:u.email, criadoEm:new Date()});
  log_(u.nome, "Abriu solicitação de mudança para " + alvo.nome);
  return {id};
}
function solicitar_(token, d) {
  const u = sessao_(token), D = carregar_(); d = d || {};
  if (u.perfil !== "admin" && !modelo_(D).scope(u).has(String(d.cargoId || ""))) { log_(u.nome, "Acesso negado: solicitação"); throw new Error("NEGADO"); }
  return novaSolicitacao_(u, D, d);
}
function resolverSolicitacao_(token, id, status, resposta) {
  const u = sessao_(token); soAdmin_(u, "resolver solicitação");
  if (!["Aberta", "Concluída", "Recusada"].includes(String(status))) throw new Error("Situação inválida.");
  const D = carregar_(), s = D.solicitacoes.find(x => x.id === String(id));
  if (!s) throw new Error("Solicitação não encontrada.");
  const fecha = status !== "Aberta";
  gravar_("Solicitacoes", "id", {id:s.id, status, resposta:String(resposta || "").trim().slice(0, 600), resolvidoPor:fecha ? u.nome : "", resolvidoEm:fecha ? new Date() : ""});
  const alvo = D.cargos.find(c => c.id === s.cargoId);
  if (status === "Concluída" && alvo && alvo.conteudo) gravar_("Cargos", "id", {id:alvo.id, historico:JSON.stringify(anotaHistorico_(alvo.conteudo.historico, alvo.conteudo.revisao, u, "Solicitação concluída: " + s.texto.slice(0, 200)))});
  log_(u.nome, "Solicitação para " + (alvo ? alvo.nome : "?") + ": " + status);
  return true;
}

/* ---- correção de cargo: a pessoa ativa pede; só o administrador aprova ou recusa. Nada muda sozinho ---- */
const TIPO_CORRECAO_ = "correcao-cargo";
const pedidosCorrecao_ = D => D.solicitacoes.filter(x => x.tipo === TIPO_CORRECAO_);
/** o pedido como a tela mostra; o e-mail só sai no retrato do administrador (ver meusPedidosDe_) */
function pedidoVista_(M, x) {
  const atual = x.cargoId ? M.byId(x.cargoId) : null, sug = x.cargoSugerido ? M.byId(x.cargoSugerido) : null;
  return {id:x.id, status:x.status, motivo:x.motivo, resposta:x.resposta, criadoEm:x.criadoEm, resolvidoEm:x.resolvidoEm, resolvidoPor:x.resolvidoPor,
    nome:x.criadoPor, email:x.criadoPorEmail, cargoAtualNome:atual ? atual.nome + " · " + atual.area : "Sem cargo",
    cargoSugerido:x.cargoSugerido || "", cargoSugeridoNome:x.cargoSugerido ? (sug ? sug.nome + " · " + sug.area : "Cargo excluído") : "Meu cargo não está na lista"};
}
/** os pedidos de UMA pessoa (sem o e-mail: ela já é quem pediu) */
function meusPedidosDe_(D, M, email) {
  return pedidosCorrecao_(D).filter(x => x.criadoPorEmail === email).map(x => { const p = pedidoVista_(M, x); delete p.email; return p; }).reverse();
}
/** administrador: os abertos primeiro, depois os 20 últimos respondidos */
function pedidosAdmin_(D, M) {
  const vistos = pedidosCorrecao_(D).map(x => pedidoVista_(M, x)).reverse();
  return [...vistos.filter(p => p.status === "Aberta"), ...vistos.filter(p => p.status !== "Aberta").slice(0, 20)];
}
function pedirCorrecaoCargo_(token, d) {
  const u = sessao_(token); d = d || {};
  if (u.perfil === "admin") throw new Error("O administrador não pede correção de cargo. Os cargos são ajustados em Usuários.");
  const D = carregar_(), M = modelo_(D);
  const motivo = texto_(d.motivo, 600);
  if (motivo.length < 10) throw new Error("Descreva o motivo com pelo menos 10 caracteres.");
  const naoLista = d.naoEstaNaLista === true, sugerido = naoLista ? "" : String(d.cargoSugerido || "");
  if (!naoLista && !sugerido) throw new Error("Escolha o seu cargo correto na lista, ou marque que ele não está na lista.");
  if (sugerido && !M.byId(sugerido)) throw new Error("O cargo escolhido não existe mais. Atualize a página e escolha de novo.");
  if (sugerido && sugerido === (u.cargo || "")) throw new Error("O cargo escolhido já é o seu cargo atual.");
  if (pedidosCorrecao_(D).some(x => x.status === "Aberta" && x.criadoPorEmail === u.email)) throw new Error("Você já tem um pedido aguardando análise. Aguarde a resposta do administrador antes de enviar outro.");
  const atual = u.cargo ? M.byId(u.cargo) : null, alvo = sugerido ? M.byId(sugerido) : null, id = "C" + Utilities.getUuid().replace(/-/g, "").slice(0, 10);
  gravar_("Solicitacoes", "id", {id, tipo:TIPO_CORRECAO_, cargoId:u.cargo || "", cargoSugerido:sugerido, origemId:"",
    texto:"Correção de cargo: de " + (atual ? atual.nome : "sem cargo") + " para " + (alvo ? alvo.nome : "um cargo que não está na lista"),
    motivo, status:"Aberta", criadoPor:u.nome, criadoPorEmail:u.email, criadoEm:new Date(), resolvidoPor:"", resolvidoEm:"", resposta:""});
  log_(u.nome, "Pediu correção de cargo");
  return {id};
}
/** o administrador decide. Aprovada: troca só o cargo do usuário (perfil e situação ficam como estão). Recusada: exige resposta. */
function resolverCorrecaoCargo_(token, id, decisao, resposta, cargoId) {
  const u = sessao_(token); soAdmin_(u, "resolver pedido de cargo");
  const D = carregar_(), M = modelo_(D), s = pedidosCorrecao_(D).find(x => x.id === String(id || ""));
  if (!s) throw new Error("Pedido não encontrado.");
  if (s.status !== "Aberta") throw new Error("Este pedido já foi respondido.");
  const dec = String(decisao || ""), resp = texto_(resposta, 600);
  if (!["Aprovada", "Recusada"].includes(dec)) throw new Error("Escolha aprovar ou recusar o pedido.");
  if (dec === "Recusada") {
    if (resp.length < 5) throw new Error("Escreva a resposta ao solicitante, com pelo menos 5 caracteres.");
  } else {
    const alvo = D.usuarios.find(x => x.email === s.criadoPorEmail);
    if (!alvo) throw new Error("O usuário deste pedido não existe mais.");
    if (alvo.perfil === "admin") throw new Error("Este usuário é administrador e não tem cargo.");
    const novo = s.cargoSugerido || String(cargoId || "");
    if (!novo) throw new Error("Escolha o cargo que será aplicado.");
    if (!M.byId(novo)) throw new Error("O cargo escolhido não existe.");
    gravar_("Usuarios", "email", {email:alvo.email, cargoId:novo});
    log_(u.nome, "Aprovou correção de cargo de " + alvo.nome + ": " + M.byId(novo).nome);
  }
  gravar_("Solicitacoes", "id", {id:s.id, status:dec, resposta:dec === "Aprovada" ? (resp || "Cargo atualizado.") : resp, resolvidoPor:u.nome, resolvidoEm:new Date()});
  if (dec === "Recusada") log_(u.nome, "Recusou correção de cargo de " + s.criadoPor);
  return true;
}

/* ---- senha: trocar a própria; administrador redefine (senha provisória, mostrada uma vez) ---- */
function novaSenhaHash_(senha) { const salt = Utilities.getUuid().replace(/-/g, ""); return {salt, hash:hashSenha_(senha, salt)}; }
function trocarSenha_(token, atual, nova) {
  const u = sessao_(token), reg = ler_("Usuarios").find(x => String(x.email).toLowerCase() === u.email);
  if (!reg || !igual_(hashSenha_(String(atual || ""), String(reg.salt)), String(reg.hash))) throw new Error("A senha atual não confere.");
  if (String(nova || "").length < 8) throw new Error("A nova senha precisa ter pelo menos 8 caracteres.");
  if (nova === atual) throw new Error("Escolha uma senha diferente da atual.");
  gravar_("Usuarios", "email", Object.assign({email:u.email, trocarSenha:""}, novaSenhaHash_(String(nova))));
  log_(u.nome, "Trocou a própria senha");
  return true;
}
function redefinirSenha_(token, email) {
  const u = sessao_(token); soAdmin_(u, "redefinir senha");
  const alvo = ler_("Usuarios").find(x => String(x.email).toLowerCase() === String(email).toLowerCase());
  if (!alvo) throw new Error("Usuário não encontrado.");
  const alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789";
  let provisoria = ""; for (let i = 0; i < 10; i++) provisoria += alfabeto[Math.floor(Math.random() * alfabeto.length)];
  gravar_("Usuarios", "email", Object.assign({email:String(alvo.email).toLowerCase(), trocarSenha:1}, novaSenhaHash_(provisoria)));
  try { CacheService.getScriptCache().remove("t:" + String(alvo.email).toLowerCase()); } catch (e) {}
  log_(u.nome, "Redefiniu a senha de " + alvo.nome);
  return {provisoria, nome:String(alvo.nome)};
}

/* ---- colar o organograma de uma vez: [{nome, area, pessoa, superior}] ; "superior" é o nome (ou id) de um cargo ---- */
function importarCargos_(token, linhas) {
  const u = sessao_(token); soAdmin_(u, "importar organograma");
  if (!Array.isArray(linhas) || !linhas.length) throw new Error("Cole pelo menos um cargo.");
  if (linhas.length > 300) throw new Error("No máximo 300 cargos por vez.");
  const D = carregar_(), novos = [], usados = new Set(D.cargos.map(c => c.id));
  linhas.forEach((l, i) => {
    const dados = dadosCargo_(l, "Linha " + (i + 1));
    novos.push({id:novoIdCargo_(dados.nome, usados), ...dados, sup:texto_(l.superior, 80)});
  });
  const todos = D.cargos.map(c => ({id:c.id, nome:c.nome})).concat(novos.map(n => ({id:n.id, nome:n.nome})));
  novos.forEach((n, i) => {
    if (!n.sup) { n.pai = ""; return; }
    const alvo = norm(n.sup), achados = todos.filter(c => c.id === n.sup || norm(c.nome) === alvo);
    if (!achados.length) throw new Error("Linha " + (i + 1) + ": não achei o cargo superior “" + n.sup + "” (" + n.nome + ").");
    if (achados.length > 1) throw new Error("Linha " + (i + 1) + ": há mais de um cargo chamado “" + n.sup + "”. Use nomes diferentes.");
    if (achados[0].id === n.id) throw new Error("Linha " + (i + 1) + ": o cargo " + n.nome + " não pode responder a ele mesmo.");
    n.pai = achados[0].id;
  });
  const paiDe = {}; D.cargos.forEach(c => paiDe[c.id] = c.pai || ""); novos.forEach(n => paiDe[n.id] = n.pai);
  novos.forEach(n => { if (fazCiclo_(n.id, n.pai, paiDe)) throw new Error("O cargo " + n.nome + " acabou ficando abaixo dele mesmo. Confira a coluna “Reporta a”."); });
  const sh = planilha_().getSheetByName("Cargos"), cab = colunas_(sh);
  sh.getRange(sh.getLastRow() + 1, 1, novos.length, cab.length).setValues(novos.map(n => cab.map(c => c === "id" ? n.id : c === "nome" ? n.nome : c === "area" ? n.area : c === "pai" ? n.pai : c === "pessoa" ? n.pessoa : "")));
  invalida_();
  log_(u.nome, "Importou " + novos.length + " cargos para o organograma");
  return {n:novos.length};
}

/* ============================== TO BE: organograma futuro (só administradores) ==============================
   Regra completa em apps-script/REGRA-SINCRONIZACAO.md. Resumo: o AS IS (aba Cargos) é o oficial e nunca é alterado aqui.
   O TO BE (aba Tobe) começa como cópia do AS IS e acompanha as mudanças dele, exceto o que foi personalizado. */
const CONTEUDO_ = ["missao","funcoes","rotinas","jornada","tempoEmpresa","formacao","experiencia","habilidades","relacoes","recorre","ferramentas"];
const SYNC_CAMPOS_ = ["nome","area","pai","pessoa","x","y", ...CONTEUDO_];
const LISTAS_ = ["funcoes","rotinas","habilidades","relacoes","ferramentas"];
const ROTULO_ = {nome:"Nome", area:"Área", pai:"Superior", pessoa:"Ocupante", x:"Posição", y:"Posição", missao:"Missão", funcoes:"Funções", rotinas:"Rotinas", jornada:"Jornada",
  tempoEmpresa:"Tempo de empresa", formacao:"Formação", experiencia:"Experiência", habilidades:"Habilidades", relacoes:"Relações", recorre:"Recorre a", ferramentas:"Ferramentas"};
const numOuNull_ = v => (v === "" || v == null || !isFinite(Number(v))) ? null : Number(v);
const mesmo_ = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const iso_ = v => { if (!v) return ""; const d = new Date(v); return isNaN(d.getTime()) ? "" : d.toISOString(); };
const novoLote_ = () => "L" + Utilities.getUuid().replace(/-/g, "").slice(0, 10);
const novoIdHist_ = () => "H" + Utilities.getUuid().replace(/-/g, "").slice(0, 10);
const tobeIniciado_ = () => PropertiesService.getScriptProperties().getProperty("TOBE_INICIADO") === "1";
/** o que a planilha guarda de um cargo (AS IS ou TO BE), com os tipos certos */
function campos_(r) {
  return {nome:String(r.nome || ""), area:String(r.area || ""), pai:r.pai ? String(r.pai) : "", pessoa:String(r.pessoa || ""), x:numOuNull_(r.x), y:numOuNull_(r.y),
    missao:String(r.missao || ""), funcoes:J_(r.funcoes, []), rotinas:J_(r.rotinas, []), jornada:String(r.jornada || ""), tempoEmpresa:String(r.tempoEmpresa || ""),
    formacao:String(r.formacao || ""), experiencia:String(r.experiencia || ""), habilidades:J_(r.habilidades, []), relacoes:J_(r.relacoes, []),
    recorre:String(r.recorre || ""), ferramentas:J_(r.ferramentas, [])};
}
/** uma aba inteira como lista de objetos, lida direto da planilha (o TO BE nunca usa a cópia em memória) */
function lerAba_(nome) {
  const v = planilha_().getSheetByName(nome).getDataRange().getValues();
  if (v.length < 2) return [];
  const cab = v[0].map(String);
  return v.slice(1).filter(l => l.some(c => c !== "")).map(l => { const o = {}; cab.forEach((c, i) => o[c] = l[i]); return o; });
}
const asisLista_ = () => lerAba_("Cargos").filter(r => String(r.id || "") !== "").map(r => ({id:String(r.id), ...campos_(r)}));
const tobeDe_ = r => ({...campos_(r), id:String(r.id), origem:String(r.origem || "tobe"), base:J_(r.base, {}), personalizado:J_(r.personalizado, []), conflito:J_(r.conflito, []), removido:Number(r.removido) === 1});
const lerTobe_ = () => lerAba_("Tobe").filter(r => String(r.id || "") !== "").map(tobeDe_);
function baseDe_(a) { const b = {}; SYNC_CAMPOS_.forEach(k => b[k] = a[k]); return b; }
/** superior ativo mais próximo (o próprio 'pai' se não foi excluído; senão sobe pela cadeia; "" se não há) */
const paiAtivo_ = (pai, porId) => { let p = pai, k = 0; while (p && k++ < 80) { const x = porId[p]; if (!x) return ""; if (!x.removido) return p; p = x.pai; } return ""; };
const conteudoDe_ = t => { const o = {}; CONTEUDO_.forEach(k => o[k] = t[k]); return o; };
/** foto do TO BE (cargos não excluídos, com os campos): é o que a versão publicada guarda para comparar */
const fotoTobe_ = T => JSON.stringify(T.filter(t => !t.removido).map(t => { const o = {id:t.id}; SYNC_CAMPOS_.forEach(k => o[k] = t[k]); return o; }).sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
const textoValor_ = v => v == null ? "" : Array.isArray(v) ? v.map(x => x && typeof x === "object" ? [x.f, x.t].filter(Boolean).join(": ") : String(x)).join("; ") : String(v);
/** uma linha do histórico do TO BE (a tela mostra antes/depois e a descrição) */
function histLinha_(lote, quem, origem, status, t, campo, antes, depois, descricao) {
  return {id:novoIdHist_(), quando:new Date(), quem:String(quem || ""), origem, cargoId:t ? t.id : "", cargoNome:t ? t.nome : "", campo:campo || "",
    antes:textoValor_(antes).slice(0, 2000), depois:textoValor_(depois).slice(0, 2000), descricao:descricao || "", justificativa:"", status, justificadoEm:"", justificadoPor:"", lote};
}
/** acrescenta linhas ao fim de uma aba (sem mexer nas que já existem) */
function anexaAba_(nome, linhas) {
  if (!linhas.length) return;
  const sh = planilha_().getSheetByName(nome), cab = colunas_(sh), inicio = Math.max(sh.getLastRow(), 1) + 1;
  sh.getRange(inicio, 1, linhas.length, cab.length).setValues(linhas.map(h => cab.map(c => c in h ? h[c] : "")));
}
const anexaHist_ = linhas => anexaAba_("TobeHistorico", linhas);
/** grava a lista inteira do TO BE de uma vez (cabeçalho fica; sobra de linhas é limpa) */
function gravarTobe_(lista) {
  const sh = planilha_().getSheetByName("Tobe"), cab = colunas_(sh);
  const valor = (t, c) => {
    if (c === "origem") return t.origem;
    if (c === "base") return JSON.stringify(t.base || {});
    if (c === "personalizado") return JSON.stringify(t.personalizado || []);
    if (c === "conflito") return JSON.stringify(t.conflito || []);
    if (c === "removido") return t.removido ? 1 : "";
    const v = t[c];
    return Array.isArray(v) ? JSON.stringify(v) : (v == null ? "" : v);
  };
  const linhas = lista.map(t => cab.map(c => valor(t, c)));
  if (linhas.length) sh.getRange(2, 1, linhas.length, cab.length).setValues(linhas);
  const sobra = sh.getLastRow() - 1 - linhas.length;
  if (sobra > 0) sh.getRange(linhas.length + 2, 1, sobra, cab.length).clearContent();
}
/** primeira abertura: copia o AS IS inteiro para o TO BE (um registro de lote no histórico) */
function iniciarTobe_(u) {
  const asis = asisLista_();
  gravarTobe_(asis.map(a => ({...a, origem:"asis", base:baseDe_(a), personalizado:[], conflito:[], removido:false})));
  anexaHist_([histLinha_(novoLote_(), u.nome, "sync", "Automática", null, "", "", "", "Cópia inicial do AS IS: " + asis.length + " cargos")]);
  PropertiesService.getScriptProperties().setProperty("TOBE_INICIADO", "1");
}
/** só administradores. Usada dentro de mudar_ (já com a trava): abrir o TO BE pela primeira vez copia o AS IS. */
const tobeAdmin_ = (token, o) => { const u = sessao_(token); soAdmin_(u, o); if (!tobeIniciado_()) iniciarTobe_(u); return u; };
/** depois de cada alteração do AS IS, o TO BE acompanha (só se ele já foi iniciado). Roda dentro da mesma trava da gravação. */
const comSync_ = (token, fn) => { const r = fn(); if (tobeIniciado_()) sincronizarTobe_(sessao_(token).nome); return r; };
/** corrige superiores que apontam para cargo excluído no TO BE: sobem para o superior ativo. Devolve as trocas feitas. */
function corrigePais_(T) {
  const porId = {}, trocas = [];
  T.forEach(t => porId[t.id] = t);
  T.forEach(t => {
    if (t.removido || !t.pai || (porId[t.pai] && !porId[t.pai].removido)) return;
    const antes = t.pai, novo = paiAtivo_(t.pai, porId); t.pai = novo; trocas.push({t, antes, novo});
  });
  return trocas;
}
/** o AS IS mudou: cada cargo herdado acompanha, exceto o campo personalizado no TO BE (vira conflito; o TO BE não é sobrescrito) */
function sincronizarTobe_(quem) {
  const asis = asisLista_(), T = lerTobe_(), porId = {}, lote = novoLote_(), hist = [], tocados = new Set();
  let criados = 0, atualizados = 0, conflitos = 0, removidos = 0;
  const agora = new Date().toISOString(), asisIds = new Set(asis.map(a => a.id));
  const registra = (t, campo, antes, depois, descricao) => hist.push(histLinha_(lote, quem, "sync", "Automática", t, campo, antes, depois, descricao));
  T.forEach(t => porId[t.id] = t);
  asis.forEach(a => {
    const t = porId[a.id];
    if (!t) {                                                    // cargo novo no AS IS: entra no TO BE como herdado
      const novo = {...a, origem:"asis", base:baseDe_(a), personalizado:[], conflito:[], removido:false};
      T.push(novo); porId[a.id] = novo; criados++; tocados.add(a.id);
      registra(novo, "cargo", "", a.nome, "Cargo herdado do AS IS");
      return;
    }
    if (t.origem !== "asis") return;
    if (t.removido) {                                            // excluído no TO BE: não ressuscita; registra uma vez a mudança
      if (SYNC_CAMPOS_.some(k => !mesmo_(a[k], t.base[k]))) { registra(t, "cargo", "", "", "Cargo mudou no AS IS, mas segue excluído no TO BE"); t.base = baseDe_(a); tocados.add(t.id); }
      return;
    }
    let houve = false;
    SYNC_CAMPOS_.forEach(k => {
      if (!(k in t.base)) { t.base[k] = a[k]; tocados.add(t.id); return; }
      if (mesmo_(a[k], t.base[k])) return;                       // o AS IS não mexeu neste campo
      const novo = a[k], atual = t[k];
      t.base[k] = novo; tocados.add(t.id);
      if (mesmo_(atual, novo)) { t.personalizado = t.personalizado.filter(c => c !== k); return; }   // convergiu
      if (!t.personalizado.includes(k)) {                        // herda
        t[k] = novo; houve = true;
        registra(t, k, atual, novo, "Herdado do AS IS: " + (ROTULO_[k] || k) + " alterado");
        return;
      }
      t.conflito = t.conflito.filter(c => c.campo !== k).concat([{campo:k, asis:novo, tobe:atual, em:agora}]);
      conflitos++; houve = true;
      registra(t, k, atual, novo, "Conflito: o AS IS mudou, mas este campo foi personalizado no TO BE");
    });
    if (houve) atualizados++;
  });
  T.forEach(t => {                                              // excluído no AS IS
    if (t.origem !== "asis" || t.removido || asisIds.has(t.id)) return;
    if (!t.personalizado.length) { t.removido = true; removidos++; tocados.add(t.id); registra(t, "cargo", t.nome, "", "Excluído no AS IS: marcado como excluído no TO BE"); }
    else if (!t.conflito.some(c => c.campo === "*")) { t.conflito.push({campo:"*", asis:"excluído no AS IS", tobe:"mantido", em:agora}); conflitos++; tocados.add(t.id); registra(t, "cargo", "mantido", "excluído no AS IS", "Conflito: o cargo foi excluído no AS IS, mas foi personalizado no TO BE"); }
  });
  corrigePais_(T).forEach(x => { tocados.add(x.t.id); registra(x.t, "pai", x.antes, x.novo, "Superior excluído: o cargo passou para " + (x.novo && porId[x.novo] ? "o superior " + porId[x.novo].nome : "o topo")); });
  if (tocados.size || hist.length) { gravarTobe_(T); anexaHist_(hist); }
  return {criados, atualizados, conflitos, removidos};
}
/** a visão do TO BE para a tela (só o que a tela precisa; o histórico vem do mais novo para o mais antigo) */
function tobeVisao_() {
  const T = lerTobe_(), ativos = T.filter(t => !t.removido), por = {};
  ativos.forEach(t => por[t.id] = t);
  const H = lerAba_("TobeHistorico"), V = lerAba_("TobeVersoes");
  const ult = V.length ? V.reduce((a, b) => Number(b.versao) > Number(a.versao) ? b : a) : null;
  const hist = H.slice(-300).reverse().map(h => ({id:String(h.id), quando:iso_(h.quando), quem:String(h.quem || ""), origem:String(h.origem || ""), cargoId:String(h.cargoId || ""),
    cargoNome:String(h.cargoNome || ""), campo:String(h.campo || ""), antes:String(h.antes || ""), depois:String(h.depois || ""), descricao:String(h.descricao || ""),
    justificativa:String(h.justificativa || ""), status:String(h.status || ""), justificadoEm:iso_(h.justificadoEm), justificadoPor:String(h.justificadoPor || ""), lote:String(h.lote || "")}));
  return {iniciado:true,
    cargos:ativos.map(t => ({id:t.id, nome:t.nome, area:t.area, pai:t.pai || null, pessoa:t.pessoa, x:t.x, y:t.y, nivel:nivelDe_(t, por), origem:t.origem, personalizado:t.personalizado,
      conflitos:t.conflito, removido:false, codigo:codigoDe_(ativos, t), conteudo:conteudoDe_(t)})),
    historico:hist,
    pendentes:H.filter(h => String(h.status) === "Pendente de justificativa").length,
    conflitos:ativos.reduce((n, t) => n + t.conflito.length, 0),
    versao:ult ? {numero:Number(ult.versao), publicadoEm:iso_(ult.publicadoEm), por:String(ult.por || ""), nota:String(ult.nota || "")} : null,
    rascunhoAlterado:ult ? String(ult.snapshot) !== fotoTobe_(T) : ativos.length > 0};
}
/** texto limpo de um campo de conteúdo vindo da tela */
function normConteudo_(k, v) {
  if (k === "rotinas") return (Array.isArray(v) ? v : []).map(x => ({f:texto_(x && x.f, 60), t:texto_(x && x.t, 300)})).filter(x => x.t).slice(0, 60);
  if (LISTAS_.includes(k)) return (Array.isArray(v) ? v : []).map(x => texto_(x, 300)).filter(Boolean).slice(0, 60);
  return texto_(v, k === "missao" ? 1000 : 300);
}
/** salva alterações no TO BE de uma vez. Confere tudo antes; grava o rascunho e um lote de histórico (uma linha por campo). */
function tobeSalvar_(u, d) {
  d = d || {};
  const alts = Array.isArray(d.alteracoes) ? d.alteracoes : [], posicoes = Array.isArray(d.posicoes) ? d.posicoes : [], ligacoes = Array.isArray(d.ligacoes) ? d.ligacoes : [];
  if (!alts.length && !posicoes.length && !ligacoes.length && d.reset !== true) throw new Error("Nada para salvar.");
  if (alts.length > 300 || posicoes.length > 500 || ligacoes.length > 500) throw new Error("Alterações demais de uma vez. Salve em partes.");
  const just = texto_(d.justificativa, 600), status = just ? "Justificada" : "Pendente de justificativa";
  const T = lerTobe_(), porId = {}, lote = novoLote_(), hist = [], mudados = new Set(), vistos = new Set();
  T.forEach(t => porId[t.id] = t);
  const ativo = id => { const t = porId[String(id || "")]; if (!t || t.removido) throw new Error("Cargo não encontrado."); return t; };
  const personaliza = (t, campo) => { if (t.origem === "asis" && SYNC_CAMPOS_.includes(campo) && !t.personalizado.includes(campo)) t.personalizado.push(campo); };
  const mudaCom = (t, campo, novo, descricao, auto) => {
    const antes = t[campo];
    if (mesmo_(antes, novo)) return;
    t[campo] = novo; mudados.add(t.id); personaliza(t, campo);
    // "auto": só a formatação mudou (o texto de redação foi ajustado pelo sistema, sem edição da pessoa); não exige justificativa
    if (auto) hist.push(histLinha_(lote, u.nome, "ajuste", "Automática", t, campo, antes, novo, (ROTULO_[campo] || campo) + " reformatado(a) automaticamente ao padrão de redação"));
    else hist.push(histLinha_(lote, u.nome, "manual", status, t, campo, antes, novo, descricao || (ROTULO_[campo] || campo) + " alterado(a) no TO BE"));
  };
  const posTxt = t => (t.x == null ? "" : t.x) + ", " + (t.y == null ? "" : t.y);
  const excluiNoTobe_ = t => {
    T.filter(f => !f.removido && f.pai === t.id).forEach(f => mudaCom(f, "pai", t.pai, "Subiu para o superior de " + t.nome + ", que foi excluído no TO BE"));
    t.removido = true; mudados.add(t.id);
    hist.push(histLinha_(lote, u.nome, "manual", status, t, "cargo", t.nome, "", "Cargo excluído no TO BE"));
  };
  alts.forEach(a => {
    a = a || {};
    if (a.novo === true) {
      const dd = dadosCargo_(a);
      let id; do { id = "tb-" + Math.random().toString(36).slice(2, 8); } while (porId[id]);
      const t = {...campos_({}), id, nome:dd.nome, area:dd.area, pessoa:dd.pessoa, pai:a.pai ? String(a.pai) : "", origem:"tobe", base:{}, personalizado:[], conflito:[], removido:false};
      T.push(t); porId[id] = t; mudados.add(id); vistos.add(id);
      hist.push(histLinha_(lote, u.nome, "manual", status, t, "cargo", "", t.nome, "Cargo criado no TO BE"));
      if (a.conteudo && typeof a.conteudo === "object") Object.keys(a.conteudo).filter(k => CONTEUDO_.includes(k)).forEach(k => mudaCom(t, k, normConteudo_(k, a.conteudo[k])));
      return;
    }
    const id = String(a.id || "");
    if (vistos.has(id)) throw new Error("O mesmo cargo aparece mais de uma vez na lista.");
    const t = ativo(id); vistos.add(id);
    if (a.excluir === true) return excluiNoTobe_(t);
    const dd = dadosCargo_(a);
    mudaCom(t, "nome", dd.nome); mudaCom(t, "area", dd.area); mudaCom(t, "pessoa", dd.pessoa);
    if (a.pai !== undefined) mudaCom(t, "pai", String(a.pai || ""));
    const autoCampos = new Set(Array.isArray(a.auto) ? a.auto.map(String) : []);
    if (a.conteudo && typeof a.conteudo === "object") Object.keys(a.conteudo).filter(k => CONTEUDO_.includes(k)).forEach(k => mudaCom(t, k, normConteudo_(k, a.conteudo[k]), undefined, autoCampos.has(k)));
  });
  if (d.reset === true) T.forEach(t => { if (!t.removido && (t.x != null || t.y != null)) { const antes = posTxt(t); t.x = null; t.y = null; mudados.add(t.id); personaliza(t, "x"); personaliza(t, "y");
    hist.push(histLinha_(lote, u.nome, "manual", status, t, "posição", antes, "", "Posições apagadas: organização automática")); } });
  posicoes.forEach(p => {
    p = p || {}; const t = ativo(p.id), x = Math.round(Number(p.x)), y = Math.round(Number(p.y));
    if (!isFinite(x) || !isFinite(y) || Math.abs(x) > 20000 || Math.abs(y) > 20000) throw new Error("Posição inválida.");
    if (t.x === x && t.y === y) return;
    const antes = posTxt(t); t.x = x; t.y = y; mudados.add(t.id); personaliza(t, "x"); personaliza(t, "y");
    hist.push(histLinha_(lote, u.nome, "manual", status, t, "posição", antes, posTxt(t), "Posição no organograma alterada"));
  });
  ligacoes.forEach(l => { l = l || {}; const t = ativo(l.id); mudaCom(t, "pai", String(l.pai || ""), "Superior alterado(a) no TO BE"); });
  /* tudo conferido antes de gravar: superior existente, sem ciclo e sem o próprio cargo */
  const paiDe = {}; T.forEach(t => { if (!t.removido) paiDe[t.id] = t.pai || ""; });
  T.forEach(t => {
    if (t.removido || !mudados.has(t.id) || !t.pai) return;
    if (t.pai === t.id) throw new Error(t.nome + ": um cargo não pode responder a ele mesmo.");
    if (!porId[t.pai] || porId[t.pai].removido) throw new Error(t.nome + ": o cargo superior escolhido não existe.");
    if (fazCiclo_(t.id, t.pai, paiDe)) throw new Error(t.nome + ": um cargo não pode ficar abaixo dele mesmo nem de quem está abaixo dele.");
  });
  if (!mudados.size) return {n:0, lote:""};
  hist.forEach(h => { if (just) { h.justificativa = just; h.justificadoEm = new Date(); h.justificadoPor = u.nome; } });
  gravarTobe_(T.filter(t => !(t.removido && t.origem === "tobe")));
  anexaHist_(hist);
  return {n:mudados.size, lote};
}
/** justifica as linhas PENDENTES de manual, por id ou por lote. Não apaga nada: só preenche a justificativa. */
function tobeJustificar_(u, ref, texto) {
  const txt = texto_(texto, 600);
  if (txt.length < 5) throw new Error("A justificativa precisa ter pelo menos 5 caracteres.");
  ref = ref || {};
  const id = String(ref.id || ""), lote = String(ref.lote || "");
  if (!id && !lote) throw new Error("Escolha o que justificar.");
  const sh = planilha_().getSheetByName("TobeHistorico"), cab = colunas_(sh), v = sh.getDataRange().getValues(), ic = c => cab.indexOf(c);
  let n = 0; const agora = new Date();
  for (let i = 1; i < v.length; i++) {
    const r = v[i];
    if (String(r[ic("origem")]) !== "manual" || String(r[ic("status")]) !== "Pendente de justificativa") continue;
    if (!((id && String(r[ic("id")]) === id) || (lote && String(r[ic("lote")]) === lote))) continue;
    r[ic("justificativa")] = txt; r[ic("status")] = "Justificada"; r[ic("justificadoEm")] = agora; r[ic("justificadoPor")] = u.nome;
    sh.getRange(i + 1, 1, 1, cab.length).setValues([r]); n++;
  }
  if (!n) throw new Error("Nada pendente para justificar.");
  return {n};
}
/** conflito de um campo: "manter" (fica o TO BE) ou "aceitar" (passa a valer o AS IS). Sempre gera histórico manual. */
function tobeResolver_(u, cargoId, campo, decisao, justificativa) {
  const T = lerTobe_(), t = T.find(x => x.id === String(cargoId || "") && !x.removido);
  if (!t) throw new Error("Cargo não encontrado.");
  const i = t.conflito.findIndex(c => c.campo === String(campo || ""));
  if (i < 0) throw new Error("Este cargo não tem conflito neste campo.");
  if (decisao !== "manter" && decisao !== "aceitar") throw new Error("Escolha manter ou aceitar.");
  const c = t.conflito[i], just = texto_(justificativa, 600), status = just ? "Justificada" : "Pendente de justificativa", lote = novoLote_(), hist = [];
  t.conflito.splice(i, 1);
  if (decisao === "aceitar" && c.campo === "*") { t.removido = true; hist.push(histLinha_(lote, u.nome, "manual", status, t, "cargo", t.nome, "", "Conflito resolvido: exclusão do AS IS aceita")); }
  else if (decisao === "aceitar") {
    const antes = t[c.campo]; t[c.campo] = c.asis; t.base[c.campo] = c.asis; t.personalizado = t.personalizado.filter(k => k !== c.campo);
    hist.push(histLinha_(lote, u.nome, "manual", status, t, c.campo, antes, c.asis, "Conflito resolvido: valor do AS IS aceito"));
  } else hist.push(histLinha_(lote, u.nome, "manual", status, t, c.campo, c.tobe, c.tobe, "Conflito resolvido: valor do TO BE mantido"));
  const porId = {}; T.forEach(x => porId[x.id] = x);
  corrigePais_(T).forEach(x => hist.push(histLinha_(lote, u.nome, "sync", "Automática", x.t, "pai", x.antes, x.novo, "Superior excluído: o cargo subiu para o superior ativo")));
  hist.forEach(h => { if (just) { h.justificativa = just; h.justificadoEm = new Date(); h.justificadoPor = u.nome; } });
  gravarTobe_(T.filter(x => !(x.removido && x.origem === "tobe")));
  anexaHist_(hist);
  return true;
}
/** publica uma versão do TO BE (snapshot). Não altera a aba Cargos nem libera o TO BE para outros perfis. */
function tobePublicar_(u, d) {
  d = d || {};
  if (d.confirmar !== true) throw new Error("Confirme a publicação para continuar.");
  const T = lerTobe_(), n = T.filter(t => !t.removido).reduce((s, t) => s + t.conflito.length, 0);

  const V = lerAba_("TobeVersoes"), ult = V.length ? V.reduce((a, b) => Number(b.versao) > Number(a.versao) ? b : a) : null;
  const foto = fotoTobe_(T);
  if (ult && String(ult.snapshot) === foto) throw new Error("Nada mudou desde a última versão.");
  const numero = ult ? Number(ult.versao) + 1 : 1;
  anexaAba_("TobeVersoes", [{versao:numero, publicadoEm:new Date(), por:u.nome, nota:texto_(d.nota, 300), snapshot:foto}]);
  anexaHist_([histLinha_(novoLote_(), u.nome, "publicacao", "Automática", null, "versão", "", "Versão " + numero, "Organograma futuro publicado como versão " + numero)]);
  return {versao:numero};
}
/** tela "Visualizar como": monta o que o perfil veria, sem criar sessão nem token e sem gravar nada */
const MENU_ = {
  admin:["inicio","agenda","organograma","cargos","tobeOrg","tobeCargos","editorg","entrevistas","usuarios"],
  socio:["inicio","organograma","cargos"],
  gestor:["inicio","agenda","organograma","cargos"],
  colaborador:["inicio","agenda","organograma","cargos"]
};
function visualizarComo_(d) {
  const perfil = String(d.perfil || "");
  if (!PERFIS[perfil]) throw new Error("Escolha o perfil que quer ver.");
  const D = carregar_(), M = modelo_(D), cid = String(d.cargoId || "");
  if ((perfil === "gestor" || perfil === "colaborador") && !cid) throw new Error("Escolha um cargo para ver como este perfil.");
  if (cid && !M.byId(cid)) throw new Error("Cargo não encontrado.");
  const cargo = cid ? M.byId(cid) : null;
  const u = {email:"simulado", nome:"Visão simulada", perfil, cargo:cargo ? cargo.id : null, status:"Ativo", simulado:true};
  const s = M.scope(u), r = retrato_(D, u);
  ["entrevistas","diag","opcoesAreas","usuarios","registro","perfis","pedidosCargo"].forEach(k => delete r[k]);
  ["pendentes","semLista","solicitacoesAbertas","pedidosCargoAbertos"].forEach(k => delete r.resumo[k]);
  Object.values(r.fichas).forEach(f => { delete f.entrevista; delete f.dataEntrevista; if (f.conteudo) { delete f.conteudo.historico; delete f.conteudo.entrevistaId; } });
  const visiveis = D.cargos.filter(c => s.has(c.id)), cadeia = [], equipe = cargo ? D.cargos.filter(x => x.pai === cargo.id).map(x => ({id:x.id, nome:x.nome, pessoa:x.pessoa})) : [];
  for (let p = cargo, k = 0; p && k++ < 30; p = p.pai ? M.byId(p.pai) : null) cadeia.push({id:p.id, nome:p.nome, pessoa:p.pessoa});
  return {perfil, perfilNome:PERFIS[perfil].nome, cargo:cargo ? {id:cargo.id, nome:cargo.nome, area:cargo.area, pessoa:cargo.pessoa} : null, menu:MENU_[perfil], retrato:r,
    resumo:{cargosComManual:visiveis.filter(c => !!c.conteudo).length, cargosSoPosicao:visiveis.filter(c => !c.conteudo).length, total:visiveis.length}, cadeia, equipe,
    regras:[PERFIS[perfil].desc, "Entrevistas, autoavaliação e o TO BE não aparecem nesta visão.", "Manuais em construção só aparecem para o administrador."]};
}

/* ---- organograma livre: posição de cada caixa e quem responde a quem (só administrador) ---- */
function salvarPosicoes_(token, d) {
  const u = sessao_(token); soAdmin_(u, "mover cargos no organograma");
  const sh = planilha_().getSheetByName("Cargos"), n = sh.getLastRow(), cab = colunas_(sh), ix = cab.indexOf("x"), ii = cab.indexOf("id");
  if (n < 2) throw new Error("O organograma está vazio.");
  if (ix < 0 || cab.indexOf("y") !== ix + 1) throw new Error("A planilha ainda não tem as colunas de posição x e y. Recarregue a plataforma e tente de novo.");
  const rng = sh.getRange(2, ix + 1, n - 1, 2);
  if (d && d.reset) { rng.clearContent(); invalida_(); log_(u.nome, "Reorganizou o organograma automaticamente"); return {n:0};  }
  const lista = Array.isArray(d) ? d : [];
  if (!lista.length || lista.length > 500) throw new Error("Lista de posições inválida.");
  const ids = sh.getRange(2, ii + 1, n - 1, 1).getValues().map(r => String(r[0])), v = rng.getValues();
  let mudou = 0;
  lista.forEach(p => {
    const i = ids.indexOf(String(p.id)), x = Math.round(Number(p.x)), y = Math.round(Number(p.y));
    if (i < 0 || !isFinite(x) || !isFinite(y) || Math.abs(x) > 20000 || Math.abs(y) > 20000) return;
    v[i] = [x, y]; mudou++;
  });
  if (!mudou) throw new Error("Nenhuma posição válida.");
  rng.setValues(v); invalida_();
  if (lista.length > 1) log_(u.nome, "Fixou as posições do organograma (" + mudou + " cargos)");
  return {n:mudou};
}
function definirSuperior_(token, id, pai) {
  const u = sessao_(token); soAdmin_(u, "ligar cargos no organograma");
  const D = carregar_(), c = D.cargos.find(x => x.id === String(id)); pai = String(pai || "");
  if (!c) throw new Error("Cargo não encontrado.");
  if (pai && !D.cargos.some(x => x.id === pai)) throw new Error("O cargo superior escolhido não existe.");
  if (pai === c.id) throw new Error("Um cargo não pode responder a ele mesmo.");
  const paiDe = {}; D.cargos.forEach(x => paiDe[x.id] = x.pai || "");
  if (pai && fazCiclo_(c.id, pai, paiDe)) throw new Error("Um cargo não pode ficar abaixo dele mesmo nem de quem está abaixo dele.");
  gravar_("Cargos", "id", {id:c.id, pai});
  const sup = D.cargos.find(x => x.id === pai);
  log_(u.nome, sup ? c.nome + " passou a responder a " + sup.nome : c.nome + " ficou no topo do organograma");
  return true;
}

/* ---- editar o organograma (só administrador). A entrevista nunca mexe aqui; só você. ---- */
function slug_(s) { return norm(s).replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 24) || "cargo"; }
function salvarCargo_(token, d) {
  const u = sessao_(token); soAdmin_(u, "editar organograma");
  d = d || {};
  const D = carregar_(), {nome, area, pessoa} = dadosCargo_(d), pai = String(d.pai || "");
  let id = String(d.id || ""); const atual = id ? D.cargos.find(c => c.id === id) : null;
  if (id && !atual) throw new Error("Cargo não encontrado.");
  if (pai && !D.cargos.some(c => c.id === pai)) throw new Error("O cargo superior escolhido não existe.");
  if (atual && pai) { const paiDe = {}; D.cargos.forEach(c => paiDe[c.id] = c.pai || ""); if (fazCiclo_(id, pai, paiDe)) throw new Error("Um cargo não pode ficar abaixo dele mesmo nem de quem está abaixo dele."); }
  if (!atual) id = novoIdCargo_(nome, new Set(D.cargos.map(c => c.id)));
  gravar_("Cargos", "id", {id, nome, area, pai, pessoa});
  log_(u.nome, (atual ? "Editou" : "Incluiu") + " no organograma: " + nome + (pessoa ? " (" + pessoa + ")" : ""));
  return {id};
}
/* altera vários cargos de uma vez (botão "Salvar alterações" de Editar organograma). Confere TODOS antes; se um estiver errado, não grava nenhum. */
function salvarCargos_(token, lista) {
  const u = sessao_(token); soAdmin_(u, "editar organograma");
  if (!Array.isArray(lista) || !lista.length) throw new Error("Nenhuma alteração para salvar.");
  if (lista.length > 300) throw new Error("No máximo 300 cargos por vez.");
  const sh = planilha_().getSheetByName("Cargos"), n = sh.getLastRow(), cab = colunas_(sh), ii = cab.indexOf("id"), ip = cab.indexOf("pai");
  if (n < 2) throw new Error("O organograma está vazio.");
  const v = sh.getRange(2, 1, n - 1, cab.length).getValues(), linhaDe = new Map(), mapa = {};     // mapa: id → superior, como está na planilha
  v.forEach((r, i) => { linhaDe.set(String(r[ii]), i); mapa[String(r[ii])] = String(r[ip] || ""); });
  const nomeDe = id => String(v[linhaDe.get(id)][cab.indexOf("nome")]);
  const vistos = new Set(), itens = lista.map(d => {
    d = d || {}; const id = String(d.id || "");
    if (!linhaDe.has(id)) throw new Error("Cargo não encontrado.");
    if (vistos.has(id)) throw new Error(nomeDe(id) + ": o mesmo cargo aparece mais de uma vez na lista.");
    vistos.add(id);
    const dados = dadosCargo_(d, nomeDe(id)), pai = String(d.pai || "");
    if (pai && !linhaDe.has(pai)) throw new Error(dados.nome + ": o cargo superior escolhido não existe.");
    if (pai === id) throw new Error(dados.nome + ": um cargo não pode responder a ele mesmo.");
    return {id, pai, ...dados};
  });
  itens.forEach(it => mapa[it.id] = it.pai);
  itens.forEach(it => { if (fazCiclo_(it.id, it.pai, mapa)) throw new Error(it.nome + ": um cargo não pode ficar abaixo dele mesmo nem de quem está abaixo dele."); });
  itens.forEach(it => {                                   // tudo conferido: grava numa vez só
    const r = v[linhaDe.get(it.id)], novo = {nome:it.nome, area:it.area, pai:it.pai, pessoa:it.pessoa};
    cab.forEach((c, k) => { if (c in novo) r[k] = novo[c]; });
  });
  sh.getRange(2, 1, n - 1, cab.length).setValues(v);
  invalida_();
  log_(u.nome, "Editou " + itens.length + " cargos no organograma: " + itens.map(i => i.nome).join(", "));
  return {n:itens.length};
}
/* grava de uma vez o que foi arrastado e ligado no organograma. d = {posicoes:[{id,x,y}], ligacoes:[{id,pai}], reset}.
   reset apaga todas as posições antes (organização automática). Confere tudo antes de gravar. */
function salvarOrganograma_(token, d) {
  const u = sessao_(token); soAdmin_(u, "mover cargos no organograma");
  d = d || {};
  const sh = planilha_().getSheetByName("Cargos"), n = sh.getLastRow(), cab = colunas_(sh), ii = cab.indexOf("id"), ip = cab.indexOf("pai"), ix = cab.indexOf("x");
  if (n < 2) throw new Error("O organograma está vazio.");
  if (ix < 0 || cab.indexOf("y") !== ix + 1) throw new Error("A planilha ainda não tem as colunas de posição x e y. Recarregue a plataforma e tente de novo.");
  const posicoes = Array.isArray(d.posicoes) ? d.posicoes : [], ligacoes = Array.isArray(d.ligacoes) ? d.ligacoes : [];
  if (posicoes.length > 500 || ligacoes.length > 500) throw new Error("Alterações demais de uma vez. Salve em partes.");
  if (!d.reset && !posicoes.length && !ligacoes.length) throw new Error("Nada para salvar.");
  const v = sh.getRange(2, 1, n - 1, cab.length).getValues(), linhaDe = new Map(), mapa = {};
  v.forEach((r, i) => { linhaDe.set(String(r[ii]), i); mapa[String(r[ii])] = String(r[ip] || ""); });
  const nomeDe = id => String(v[linhaDe.get(id)][cab.indexOf("nome")]);
  const pos = posicoes.map(p => {
    p = p || {}; const id = String(p.id || ""), x = Math.round(Number(p.x)), y = Math.round(Number(p.y));
    if (!linhaDe.has(id)) throw new Error("Cargo não encontrado.");
    if (!isFinite(x) || !isFinite(y) || Math.abs(x) > 20000 || Math.abs(y) > 20000) throw new Error("Posição inválida.");
    return {id, x, y};
  });
  const lig = ligacoes.map(l => {
    l = l || {}; const id = String(l.id || ""), pai = String(l.pai || "");
    if (!linhaDe.has(id)) throw new Error("Cargo não encontrado.");
    if (pai && !linhaDe.has(pai)) throw new Error("O cargo superior escolhido não existe.");
    if (pai === id) throw new Error(nomeDe(id) + ": um cargo não pode responder a ele mesmo.");
    mapa[id] = pai; return {id, pai};
  });
  lig.forEach(l => { if (l.pai && fazCiclo_(l.id, l.pai, mapa)) throw new Error(nomeDe(l.id) + ": um cargo não pode ficar abaixo dele mesmo nem de quem está abaixo dele."); });
  if (d.reset) v.forEach(r => { r[ix] = ""; r[ix + 1] = ""; });
  pos.forEach(p => { const r = v[linhaDe.get(p.id)]; r[ix] = p.x; r[ix + 1] = p.y; });
  lig.forEach(l => { v[linhaDe.get(l.id)][ip] = l.pai; });
  sh.getRange(2, 1, n - 1, cab.length).setValues(v);      // uma gravação só
  invalida_();
  if (d.reset) log_(u.nome, "Reorganizou o organograma automaticamente");
  if (pos.length || lig.length) log_(u.nome, "Salvou o organograma: " + pos.length + " posições e " + lig.length + " ligações");
  return {n:pos.length, ligacoes:lig.length};
}
function excluirCargo_(token, id) {
  const u = sessao_(token); soAdmin_(u, "excluir cargo do organograma");
  const D = carregar_(), c = D.cargos.find(x => x.id === String(id));
  if (!c) throw new Error("Cargo não encontrado.");
  if (D.cargos.some(x => x.pai === c.id)) throw new Error("Este cargo tem cargos abaixo dele. Mude o superior deles (ou exclua-os) antes.");
  if (D.usuarios.some(x => x.cargo === c.id)) throw new Error("Há usuários ligados a este cargo. Troque o cargo deles em Usuários antes.");
  const ent = planilha_().getSheetByName("Entrevistas"), n = ent.getLastRow();
  if (n >= 2) { const col = ent.getRange(2, colunas_(ent).indexOf("cargoId") + 1, n - 1, 1).getValues(); for (let i = col.length - 1; i >= 0; i--) if (String(col[i][0]) === c.id) ent.deleteRow(i + 2); }
  planilha_().getSheetByName("Cargos").deleteRow(achar_("Cargos", "id", c.id));
  invalida_();
  log_(u.nome, "Excluiu do organograma: " + c.nome);
  return true;
}
/* ============================== leitor de entrevistas (igual ao da prévia) ============================== */
let CARGOS = [];

  /* ---------- leitor de entrevista (lê o texto do Google Docs) ---------- */
  const norm = s => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  const STOP = new Set(["de","da","do","dos","das","e","a","o","para","em"]);
  const tokens = s => norm(s).split(/[^a-z0-9]+/).filter(t => t.length > 1 && !STOP.has(t));
  const pref = (a, b) => a === b || (Math.min(a.length, b.length) >= 5 && (a.startsWith(b) || b.startsWith(a)));
  function casar(texto, minimo = .99) {                     // acha o cargo cujo nome aparece no texto
    const tt = tokens(texto); let best = null, bs = 0;
    for (const c of CARGOS) {
      const ct = tokens(c.nome); if (!ct.length) continue;
      const sc = ct.filter(x => tt.some(y => pref(x, y))).length / ct.length;
      if (sc >= minimo && (sc > bs || (sc === bs && best && ct.length > tokens(best.nome).length))) { best = c; bs = sc; }
    }
    return best ? best.id : null;
  }
  const AJUDA = new Set(["descrevendo a sua missão.","explicar o que é uma função.","defina a pessoa e o cargo.","auxílio, etc.","cite as funções."]);
  const FREQ = [[/^di[aá]ri[ao]s?/i,"Diária"],[/^semana(l|is)/i,"Semanal"],[/^quinzena(l|is)/i,"Quinzenal"],[/^mensa(l|is)/i,"Mensal"],[/^trimestra(l|is)/i,"Trimestral"],
    [/^semestra(l|is)/i,"Semestral"],[/^anua(l|is)/i,"Anual"],[/^(sob demanda|eventua(l|is)|quando necess)/i,"Sob demanda"]];
  /* pedaço que continua a rotina anterior (ex.: "Pagamento de funcionários, prazo: 1-5 do mês") */
  const CONT = /^(prazo|todo|toda|todos|todas|at[eé]|no|na|nos|nas|dia|dias|das|dos|do|da|de|entre|sendo|quando|com|pelo|pela|para|[aà]s|aos|em|sempre|antes|depois|exceto|conforme)\b/i;
  function lerTexto(texto) {
    // aceita texto puro (Word/Docs) e o formato do Google Docs (títulos #, **negrito**, tabela |)
    const linhas = String(texto).replace(/\r/g, "").replace(/ /g, " ").replace(/\\([*_\-#|.])/g, "$1")
      .split("\n").map(l => l.replace(/^#+\s*/, "").replace(/\*+/g, "").replace(/\t+/g, " ").trim());
    const ehNum = l => /^\d{1,2}\.\s+\S/.test(l);
    const i1 = linhas.findIndex(ehNum), cab = linhas.slice(0, i1 < 0 ? linhas.length : i1);
    const ROT = /^(nome|cargo|tempo de empresa|dia\/hor[aá]rio.*|data da entrevista)\b/i;
    const celulas = cab.filter(l => l.includes("|")).flatMap(l => l.split("|")).map(c => c.trim()).filter(c => c && !/^:?-+:?$/.test(c));
    const campo = nome => {
      for (const c of celulas) { const m = c.match(new RegExp("^" + nome + "\\b\\s*:?\\s*(.*)$", "i")); if (m && m[1].trim()) return m[1].trim(); }
      for (let i = 0; i < cab.length; i++) {
        const m = cab[i].match(new RegExp("^" + nome + "\\b\\s*:?\\s*(.*)$", "i")); if (!m) continue;
        if (m[1]) return m[1].trim();
        for (let j = i + 1; j < cab.length; j++) if (cab[j]) return ROT.test(cab[j]) ? "" : cab[j];
      } return "";
    };
    const bloco = re => {
      const i = linhas.findIndex(l => ehNum(l) && re.test(l)); if (i < 0) return [];
      const out = []; for (let j = i + 1; j < linhas.length && !ehNum(linhas[j]); j++) { const l = linhas[j]; if (l && !AJUDA.has(l.toLowerCase())) out.push(l); }
      return out;
    };
    const limpa = s => { s = s.replace(/[.;,\s]+$/, "").trim(); return s.charAt(0).toUpperCase() + s.slice(1); };
    const VAZIO = /^(n[aã]o|ainda n[aã]o|nenhum[a]?|n\/a|-)$/i;                      // respostas que não são conteúdo
    const itens = ls => ls.flatMap(l => l.split(/;|\.\s+/))
      .flatMap(s => s.length > 140 || (s.split(",").length >= 3 && !s.includes(":")) ? s.split(/,\s*/) : [s]).map(limpa).filter(s => s.length > 1 && !VAZIO.test(s));
    const rotinas = []; let atual = null, semFreq = 0;
    const add = t => {                                   // mantém o texto da pessoa: só separa onde ela separou
      const ps = [];
      for (const p of t.split(/;\s*|,\s*|\.\s+/).map(s => s.trim()).filter(Boolean)) { if (ps.length && CONT.test(p)) ps[ps.length - 1] += ", " + p; else ps.push(p); }
      ps.map(limpa).filter(s => s.length > 1 && !VAZIO.test(s)).forEach(s => { if (!atual) semFreq++; rotinas.push({f:atual || "Sob demanda", t:s}); });
    };
    for (const l of bloco(/rotinas/i)) {
      const m = l.match(/^([^:]{3,24}):\s*(.*)$/), f = m && FREQ.find(([re]) => re.test(m[1].trim()));
      if (f) { atual = f[1]; add(m[2]); } else add(l);
    }
    /* a entrevista inteira: as respostas, menos a autoavaliação (perguntas 20 a 27, que viram nota) */
    const respostas = [];
    for (let i = 0; i < linhas.length; i++) {
      const l = linhas[i]; if (!ehNum(l) || !/\?\s*$/.test(l)) continue;
      const n = +l.match(/^(\d{1,2})\./)[1]; if (n >= 20 && n <= 27) continue;
      const r = []; for (let j = i + 1; j < linhas.length && !ehNum(linhas[j]); j++) { const x = linhas[j]; if (x && !AJUDA.has(x.toLowerCase())) r.push(x); }
      respostas.push({n, p:l.replace(/^\d{1,2}\.\s*/, "").slice(0, 300), r:r.join("\n").slice(0, 4000)});
    }
    defineNomes(CARGOS.map(c => c.pessoa).concat([campo("nome")]));          // nomes de pessoas (cargos + entrevistada): sempre com inicial maiúscula
    const out = {
      cargoNome:campo("cargo"), pessoa:campo("nome"), data:campo("data da entrevista"),
      missao:formalizarMissao(bloco(/objetivo final/i).join(" ").trim(), [campo("nome")]), funcoes:itens(bloco(/fun[cç][õo]es atuais/i)), rotinas,
      lidera:bloco(/liderados?\s+por\s+voc/i).join(" ").trim(), reportaA:bloco(/voc[eê]\s+[eé]\s+liderad|te\s+lideram/i).join(" ").trim(), avisos:[],
      jornada:formalizarJornada(campo("dia\\/hor[aá]rio de trabalho")), tempoEmpresa:campo("tempo de empresa"),
      ferramentas:[...new Set((String(texto).match(/\b(Lumi[e]?|Excel|WhatsApp|plano de contas|DRE)\b/gi) || []).map(s => /^lumi/i.test(s) ? "Lumi" : s.charAt(0).toUpperCase() + s.slice(1)))],
      habilidades:itens(bloco(/habilidades exigidas/i)),
      relacoes:[], respostas                                           // pergunta 16 é texto livre: o consultor completa
    };
    const rs = resumoAjuste(out.funcoes, out.rotinas);
    out.funcoes = ajustaFuncoes(out.funcoes).map(capitalizaNomes2); out.rotinas = ajustaRotinas(out.rotinas).map(r => ({...r, t:capitalizaNomes2(r.t)}));
    if (rs.mudadas || rs.removidas || rs.fora.length) out.avisos.push(avisoAjuste(rs));
    if (semFreq) out.avisos.push(plural(semFreq, "rotina sem frequência ficou", "rotinas sem frequência ficaram") + " em “Sob demanda”: confira.");
    // autoavaliação (perguntas 20 a 27): a nota marcada em negrito no Docs, ex. ***( 4 )***, ou um X ao lado
    const cru = String(texto).replace(/\r/g, "").split("\n");
    out.auto = [20, 21, 22, 23, 24, 25, 26, 27].map(q => {
      const i = cru.findIndex(l => new RegExp("^\\W*" + q + "\\.").test(l.replace(/\\/g, ""))); if (i < 0) return null;
      for (const l of cru.slice(i + 1, i + 7)) {
        const m = l.match(/\*{2,3}\s*\(\s*([1-5])\s*\)\s*\*{2,3}/) || l.match(/\(\s*[xX✓]\s*\)\s*([1-5])/) || l.match(/\(\s*([1-5])\s*[xX✓]\s*\)/);
        if (m) return +m[1];
      } return null;
    });
    const perguntasDeNota = [20, 21, 22, 23, 24, 25, 26, 27].filter(q => cru.some(l => new RegExp("^\\W*" + q + "\\.").test(l.replace(/\\/g, "")))).length;
    const semNota = perguntasDeNota - (out.auto ? out.auto.filter(v => v).length : 0);
    if (!out.auto.some(v => v)) out.auto = null;
    if (semNota > 0) out.avisos.push("Não consegui ler a nota de " + semNota + " das " + perguntasDeNota + " perguntas de autoavaliação, de 20 a 27. A nota é a opção formatada diferente das outras (cor, negrito, marca-texto, tachado...): confira no Doc, ou escolha a nota abaixo.");
    const semVazio = s => VAZIO.test(s.trim()) ? "" : s.trim().replace(/[.\s]+$/, "");
    const prob = semVazio(bloco(/quando h[aá] algum problema/i).join(" ")), fora = semVazio(bloco(/n[aã]o (compete|[eé] da sua)/i).join(" "));
    out.recorre = recorreNormaliza([prob, fora && fora !== prob ? "fora da área, " + fora : ""].filter(Boolean).join("; "));
    if (!out.missao) out.avisos.push("Não encontrei a missão (pergunta 1).");
    if (!out.funcoes.length) out.avisos.push("Não encontrei as funções (pergunta 3).");
    if (!out.rotinas.length) out.avisos.push("Não encontrei rotinas (pergunta 4).");
    if (out.avisos.length === 3) throw new Error("Não reconheci esse texto como uma entrevista. Cole o conteúdo do roteiro completo.");
    out.sugestao = casar(out.cargoNome + " " + out.pessoa) || (CARGOS.find(c => out.pessoa && norm(c.pessoa).split(" ")[0] === norm(out.pessoa).split(" ")[0])?.id ?? null);
    const porPessoa = txt => { const tt = tokens(txt); return CARGOS.find(c => { const p = tokens(c.pessoa)[0]; return p && p.length >= 3 && tt.includes(p); })?.id ?? null; };
    out.sugestaoPai = casar(out.reportaA) || porPessoa(out.reportaA);
    /* trechos que falam de OUTRO cargo: viram sugestão de "solicitação de mudança" para aquele cargo */
    out.afeta = []; const vistos = new Set();
    for (const q of respostas.filter(q => [3, 4, 9, 10, 11, 12, 13, 14, 18, 28].includes(q.n))) for (const fr of q.r.split(/(?<=[.!?])\s+|\n/)) {
      const t = fr.trim(); if (t.length < 12 || out.afeta.length >= 12) continue;
      const id = casar(t) || porPessoa(t);
      if (id && !vistos.has(id + "|" + t)) { vistos.add(id + "|" + t); out.afeta.push({cargoId:id, trecho:t.slice(0, 300), pergunta:q.n}); }
    }
    return out;
  }
  const LINK = /^https:\/\/docs\.google\.com\/document\/d\/[\w-]+/;
  const FREQ_INFO = {"Diária":{titulo:"Diariamente", ajuda:"Todo dia"}, "Semanal":{titulo:"Semanalmente", ajuda:"Uma vez por semana (cite o dia, se houver)"}, "Quinzenal":{titulo:"Quinzenalmente", ajuda:"A cada 15 dias"},
  "Mensal":{titulo:"Mensalmente", ajuda:"Uma vez por mês (cite o dia ou prazo)"}, "Trimestral":{titulo:"Trimestralmente", ajuda:"A cada 3 meses"}, "Semestral":{titulo:"Semestralmente", ajuda:"A cada 6 meses"},
  "Anual":{titulo:"Anualmente", ajuda:"Uma vez por ano"}, "Sob demanda":{titulo:"Sob demanda", ajuda:"Quando surge a necessidade"}};
const FREQS = Object.keys(FREQ_INFO);
  function validarConteudo(d) {
    const missao = String(d.missao || "").trim(), funcoes = (d.funcoes || []).map(s => String(s).trim()).filter(Boolean);
    const rotinas = (d.rotinas || []).map(r => ({f:r.f, t:String(r.t).trim()})).filter(r => r.t);
    if (!missao && d.publicar) throw new Error("Escreva a missão do cargo antes de publicar (pode salvar para revisão sem ela).");
    if (missao.length > 800) throw new Error("A missão está muito longa (máximo 800 letras).");
    if (!funcoes.length) throw new Error("Inclua pelo menos uma função.");
    if (funcoes.length > 60 || funcoes.some(f => f.length > 400)) throw new Error("Funções demais ou longas demais.");
    if (rotinas.length > 150 || rotinas.some(r => !FREQS.includes(r.f) || r.t.length > 400)) throw new Error("Rotinas inválidas: cada rotina precisa de uma frequência (" + FREQS.join(", ") + ").");
    const txt = (v, max) => String(v || "").trim().slice(0, max);
    const lst = v => (Array.isArray(v) ? v : String(v || "").split("\n")).map(s => String(s).trim()).filter(Boolean).slice(0, 30).map(s => s.slice(0, 200));
    if (d.publicar) { const v = violacoesEstilo(funcoes, rotinas); if (v.length) throw new Error(mensagemEstilo(v) + " (Você pode salvar para revisão sem ajustar.)"); }
    const respostas = (Array.isArray(d.respostas) ? d.respostas : []).slice(0, 40).map(q => ({n:+q.n || 0, p:txt(q.p, 300), r:txt(q.r, 4000)})).filter(q => q.p);
    return {missao, funcoes, rotinas, respostas, jornada:txt(d.jornada, 400), formacao:txt(d.formacao, 160), experiencia:txt(d.experiencia, 200),
            habilidades:lst(d.habilidades), relacoes:lst(d.relacoes), recorre:txt(d.recorre, 200), ferramentas:lst(d.ferramentas), tempoEmpresa:txt(d.tempoEmpresa, 60)};
  }
  

/* ---------- padrão de redação do manual ----------
   FUNÇÃO e ROTINA começam com VERBO no INFINITIVO ("Realizar as compras", "Conferir o registro de ponto"). Função: "Conferência do ponto" → "Conferir o ponto". Rotina: "Confira o ponto" → "Conferir o ponto".
   Pares [verbo, substantivo, preposição que liga o substantivo ao resto, mantém a preposição ao virar verbo?]. A lista serve para
   sugerir o ajuste sozinha; o que não estiver nela fica sinalizado para o administrador reescrever. */
const PARES = [
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
];
const sem = s => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
const MAPA_V = new Map(), MAPA_N = new Map();
PARES.forEach(p => { const e = {v:p[0], n:p[1], p:p[2], k:!!p[3]}; if (!MAPA_V.has(sem(e.v))) MAPA_V.set(sem(e.v), e); if (!MAPA_N.has(sem(e.n)) || e.v.split(" ").length === 1) MAPA_N.set(sem(e.n), e); });
const VERBOS_COMUNS = ["Fazer","Ir","Ligar","Mandar","Buscar","Pegar","Ajudar","Anotar","Avisar","Ver","Falar","Passar","Procurar","Responder","Separar","Somar","Subir","Baixar","Imprimir","Assinar","Contar","Entrar","Sair","Cuidar","Usar","Lembrar","Chamar","Cobrar","Deixar","Mostrar","Entender","Resolver","Atender","Participar","Acompanhar","Ler","Escrever","Contratar","Pagar","Receber","Conferir","Anexar","Digitalizar","Escanear","Reservar","Solicitar","Aprovar","Cancelar","Devolver","Guardar","Fiscalizar","Orientar","Planejar"];
/* terceira pessoa do presente ("Recebe", "Manda", "Confere", "Faz") → infinitivo, para reconhecer e corrigir quem escreveu "Recebe o espelho" em vez de "Receba o espelho" */
const PRESENTE_IRREG = {faz:"fazer", vai:"ir", da:"dar", tem:"ter", ve:"ver", vem:"vir", poe:"pôr", le:"ler", sai:"sair", ouve:"ouvir", pede:"pedir", mede:"medir", diz:"dizer", traz:"trazer", repoe:"repor"};
const PRESENTE3 = new Map();
const NAO_PRESENTE = new Set(["data","venda","compra","conta","carga","entrega","baixa","troca","cobranca","busca","ajuda","soma","falta","passa","chamada","avisa","pega","lembra","guarda","reserva","usa","marca","entrada","saida","ligacao"]);
const infinitivosConhecidos = () => new Set([...PARES.map(p => p[0].split(" ")[0]), ...VERBOS_COMUNS].filter(v => /(ar|er|ir)$/.test(v)));
const NAO_VERBOS = new Set(["lugar","mulher","colher","dever","poder","prazer","mister","ar","mar","par","bar","jantar","altar","cartaz","setor","valor","calor","fator","gestor","motor","contador","comprador","vendedor","senhor","favor","amor","cursor","painel","carter","dor","cor","flor","pior","melhor","maior","menor","superior","inferior","interior","exterior"]);
const VERBOS_OR = new Set(["repor","compor","dispor","propor","expor","supor","impor","opor","depor","pospor"]);
const primeiraPalavra = t => (String(t).trim().match(/^[\p{L}][\p{L}-]*/u) || [""])[0];
const VERBOS_CURTOS = new Set(["dar", "ter", "ver", "ler", "ir", "vir", "ser", "pôr", "por"]);
const ehVerboInf = w => { const n = sem(w); return !!n && !NAO_VERBOS.has(n) && (VERBOS_CURTOS.has(n) && String(w)[0] === String(w)[0].toUpperCase() || /^.{2,}(ar|er|ir)(-se)?$/.test(n) || VERBOS_OR.has(n)); };
const SUF_SUBST = /(ção|ções|são|sões|mento|mentos|ência|ências|ância|âncias|agem|agens|idade|idades|ismo|ura|eza|aria)$/i;
const ARTIGOS = /^(o|a|os|as|um|uma|de|do|da|dos|das|no|na|nos|nas|ao|aos|à|às)$/i;
const parecesubst = w => { const n = sem(w); return ARTIGOS.test(w) || !!buscaN(n) || !!chaveCompleta(n) || (SUF_SUBST.test(w) && !ehVerboInf(w)); };
/* substantivos que viram "verbo + a própria frase": "Relatório de vendas" → "Elaborar relatório de vendas" */
const COMPLETA = {relatorio:"Elaborar", reuniao:"Realizar", planilha:"Preencher", anuncio:"Publicar", ligacao:"Realizar", conversa:"Ter", rescisao:"Realizar", visita:"Realizar", obrigacao:"Cumprir"};
/* "Pagamentos" → "pagamento", "Rescisões" → "rescisão": procura também o singular */
const singular = n => n.replace(/oes$/, "ao").replace(/aes$/, "ao").replace(/ns$/, "m").replace(/(?<=[aeiou])s$/, "");
/* erros de digitação comuns de substantivos da lista ("colhimento" é "coleta") */
const ERRO_N = {colhimento:"coleta", colhimentos:"coleta"};
const buscaN = n => MAPA_N.get(n) || MAPA_N.get(singular(n)) || (ERRO_N[n] ? MAPA_N.get(ERRO_N[n]) : undefined);
const chaveCompleta = n => COMPLETA[n] ? n : COMPLETA[singular(n)] ? singular(n) : "";
const DIA_INICIO = /^((toda|todo)\s+)?(segunda|terça|terca|quarta|quinta|sexta|sábado|sabado|domingo)(-feira)?\s*:\s*(.+)$/i;
const PARTIR_INICIO = /^a partir (de|da|do)\s+([^:]+):\s*(.+)$/i;
/* monta o mapa "recebe" → "Receber" (só para verbos conhecidos; palavras que também são substantivos ficam de fora) */
infinitivosConhecidos().forEach(v => { const b = sem(v), stem = b.slice(0, -2), pres = b.endsWith("ar") ? stem + "a" : stem + "e"; if (!NAO_PRESENTE.has(pres) && !MAPA_N.has(pres)) PRESENTE3.set(pres, v); });
Object.entries(PRESENTE_IRREG).forEach(([p, v]) => PRESENTE3.set(p, v));
const infinitivoDoPresente = w => PRESENTE3.get(sem(w)) || "";
const maiuscula = s => s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
const CONTR = {
  de:{o:"do", a:"da", os:"dos", as:"das", um:"de um", uma:"de uma", _:"de"}, a:{o:"ao", a:"à", os:"aos", as:"às", um:"a um", uma:"a uma", _:"a"},
  por:{o:"pelo", a:"pela", os:"pelos", as:"pelas", um:"por um", uma:"por uma", _:"por"}, com:{o:"com o", a:"com a", os:"com os", as:"com as", um:"com um", uma:"com uma", _:"com"},
  em:{o:"no", a:"na", os:"nos", as:"nas", um:"em um", uma:"em uma", _:"em"}
};
const SOLTA = {do:"o", da:"a", dos:"os", das:"as", ao:"o", "à":"a", aos:"os", "às":"as", pelo:"o", pela:"a", pelos:"os", pelas:"as"};    // preposição + artigo → só o artigo ("Conferência do ponto" → "Conferir o ponto")
const MANTEM_PREP = /^(no|na|nos|nas|em|com|por)$/i;                                                                                    // essas continuam ("Correção no Lumi" → "Corrigir no Lumi")
/** Função: começa com VERBO no infinitivo ("Conferência do ponto" → "Conferir o ponto"; "Fazer a gestão do estoque" → "Gerir o estoque"). Devolve o texto igual se não souber (fica como violação para o administrador reescrever). */
const FAZER_GC = /^fazer\s+(?:a|o)\s+(gest[aã]o|controle)(?=\s|$)\s*(.*)$/i;
/** Infinitivo → imperativo (você): "Conferir" → "Confira", "Verificar" → "Verifique", "Pagar" → "Pague", "Fazer" → "Faça". */
const IRREGULAR = {fazer:"faça", dar:"dê", ter:"tenha", ver:"veja", vir:"venha", ir:"vá", ler:"leia", saber:"saiba", trazer:"traga", dizer:"diga", sair:"saia", ouvir:"ouça", pedir:"peça", medir:"meça", pôr:"ponha", por:"ponha", repor:"reponha", compor:"componha", dispor:"disponha", propor:"proponha", expor:"exponha", supor:"suponha", impor:"imponha", requerer:"requeira", cobrir:"cubra", descobrir:"descubra", encobrir:"encubra", rir:"ria", crer:"creia", poder:"possa", querer:"queira"};
function imperativoDe(inf) {
  const se = /-se$/i.test(inf), p = inf.replace(/-se$/i, ""), b = p.toLowerCase(); let r;
  if (IRREGULAR[b]) r = IRREGULAR[b];
  else if (/ferir$/.test(b)) r = b.replace(/ferir$/, "fira");
  else if (/gerir$/.test(b)) r = b.replace(/gerir$/, "gira");
  else if (/(sentir|mentir)$/.test(b)) r = b.replace(/entir$/, "inta");
  else if (/(vestir|servir|repetir)$/.test(b)) r = b.replace(/estir$/, "ista").replace(/ervir$/, "irva").replace(/epetir$/, "epita");
  else if (/seguir$/.test(b)) r = b.replace(/seguir$/, "siga");
  else if (/çar$/.test(b)) r = b.replace(/çar$/, "ce");
  else if (/car$/.test(b)) r = b.replace(/car$/, "que");
  else if (/gar$/.test(b)) r = b.replace(/gar$/, "gue");
  else if (/ear$/.test(b)) r = b.replace(/ear$/, "eie");
  else if (/ar$/.test(b)) r = b.replace(/ar$/, "e");
  else if (/(cer)$/.test(b)) r = b.replace(/cer$/, "ça");
  else if (/(ger|gir)$/.test(b)) r = b.replace(/g(er|ir)$/, "ja");
  else if (/guir$/.test(b)) r = b.replace(/guir$/, "ga");
  else if (/(er|ir)$/.test(b)) r = b.replace(/(er|ir)$/, "a");
  else r = b;
  if (se) r += "-se";
  return p.charAt(0) === p.charAt(0).toUpperCase() ? maiuscula(r) : r;
}
/* imperativo → infinitivo, só para verbos da lista ("confira" → "Conferir"); formas de duas letras (de, dê, vá) ficam de fora */
const IMPERATIVO_INF = new Map();
infinitivosConhecidos().forEach(v => { if (!/-se$/.test(v)) { const k = sem(imperativoDe(v)); if (k.length > 2 && !IMPERATIVO_INF.has(k)) IMPERATIVO_INF.set(k, v); } });
const infDoImperativo = w => IMPERATIVO_INF.get(sem(w)) || "";
const INF_CONHECIDO = new Map([...infinitivosConhecidos()].map(v => [sem(v), v]));
/* gerúndio → infinitivo, só se o verbo for conhecido ("Acompanhando" → "Acompanhar") */
const infDoGerundio = w => { const m = sem(w).match(/^(.{2,})(ando|endo|indo)$/); return m ? (INF_CONHECIDO.get(m[1] + {ando:"ar", endo:"er", indo:"ir"}[m[2]]) || "") : ""; };
/* "Controle os prazos" / "Analise o DRE": a palavra também é substantivo, mas com artigo logo depois é o verbo no imperativo */
const imperativoValido = (s, w) => { const e = buscaN(sem(w)); if (!e) return false; const prox = (s.slice(w.length).trim().split(/\s+/)[0] || ""); return sem(imperativoDe(e.v.split(" ")[0])) === sem(w) && /^(o|a|os|as)$/i.test(prox); };
/* "Confira o ponto e lance os atestados" → "Conferir o ponto e lançar os atestados": os verbos ligados por "e"/"ou" também vão ao infinitivo */
const PREP_SEGUE = /^\s+(de|do|da|dos|das|em|no|na|nos|nas|com|para|por|ao|aos|às|pelo|pela|pelos|pelas)\b/i;
const coordVerbos = s => s.replace(/(\s(?:e|ou)\s)(\p{L}+)(?=\s|$|,)/gu, (m, c, v, off, str) => { if (ehVerboInf(v) || (buscaN(sem(v)) && PREP_SEGUE.test(str.slice(off + m.length)))) return m; const i = infDoImperativo(v) || infinitivoDoPresente(v); return i ? c + i.toLowerCase() : m; });   // "e envia para o diretor" → "e enviar para o diretor"; "e controle das férias" fica para o substantivo
/* verbo conjugado no começo (imperativo "Confira", 3.ª pessoa "Recebe", gerúndio "Acompanhando", "Dê") → infinitivo; "" se não for verbo conhecido */
function verboConjugadoInf(t) {
  const w = primeiraPalavra(t), e = buscaN(sem(w));
  if (/^dê$/i.test(w)) return coordVerbos("Dar" + String(t).slice(w.length));
  let inf = "";
  if (infDoImperativo(w) && (!e || imperativoValido(t, w))) inf = infDoImperativo(w);
  else inf = infinitivoDoPresente(w) || infDoGerundio(w);
  if (!inf) return "";
  const r = coordVerbos(maiuscula(inf) + String(t).slice(w.length));
  return FAZER_GC.test(r) ? nucleoInf(r) : r;                       // "Faz a gestão…" → "Fazer a gestão…" → "Gerir…"
}
/* o que vem depois do substantivo, na forma do infinitivo: "de funcionários" → "funcionários"; "do ponto" → "o ponto"; "no Lumi" fica */
const COMPL_PREP = /^(de|do|da|dos|das|ao|aos|à|às|pelo|pela|pelos|pelas|no|na|nos|nas|com|por|a|em)\s+(.*)$/i;
function complementoInf(e, resto) {
  if (!resto) return "";
  const pm = resto.match(COMPL_PREP); if (!pm) return null;
  const prep = pm[1].toLowerCase(), cauda = pm[2];
  if (e.k || MANTEM_PREP.test(prep)) return resto;
  if (e.p === "em" && /^(de|do|da|dos|das)$/.test(prep)) return (SOLTA[prep] ? CONTR.em[SOLTA[prep]] : "em") + " " + cauda;
  if (prep === "de") return cauda;
  if (prep === "a" && e.p === "a") return cauda;                          // "Atendimento a clientes" → "Atender clientes"
  if (prep === "a") return "a " + cauda;                                  // "Vendas a clientes" → "Vender a clientes"
  return (SOLTA[prep] ? SOLTA[prep] + " " : "") + cauda;
}
/* "Acompanhar os indicadores e elaboração de relatórios" → "… e elaborar relatórios": o substantivo ligado por "e" também vira verbo */
function coordMeio(s) {
  s = coordVerbos(s);
  const m = s.match(/^(.*?)(\s(?:e|ou)\s)(\p{L}+)(?:\s+(.*))?$/u);
  if (!m || !m[4] || ehVerboInf(m[3])) return s;                          // sem complemento ("e recebimentos") é objeto: fica como está
  const e2 = buscaN(sem(m[3])); if (!e2) return s;
  const c = complementoInf(e2, m[4].trim()); if (c == null) return s;
  return m[1] + m[2] + e2.v.toLowerCase() + (c ? " " + c : "");
}
/* ---------- ajuste automático: resolve sozinho o que tem regra segura; o que não tem fica como violação ---------- */
const PLACEHOLDER_F = new Set(["nao ha", "nenhuma", "nenhum", "ainda nao", "nao possui", "n/a", "-", "nada", "nao tem"]);
/* "Não há", "Nenhuma", "N/A", "-": não é atividade; sai da lista e não conta como violação */
const ehPlaceholder = t => PLACEHOLDER_F.has(sem(String(t == null ? "" : t).replace(/[\s.;:,]+$/, "")));
/* palavras comuns digitadas com inicial maiúscula no meio da frase ("Conferir Ponto" → "Conferir ponto"); nomes e siglas ficam */
const COMUNS_MIN = new Set(["ponto", "relatorio", "planilha", "folha", "estoque", "produto", "produtos", "loja", "lojas", "fornecedor", "fornecedores", "cliente", "clientes", "pagamento", "pagamentos", "boleto", "boletos", "nota", "notas", "fiscal", "fiscais", "caixa", "compra", "compras", "venda", "vendas", "conta", "contas", "reuniao", "reunioes", "ferias", "documento", "documentos", "contrato", "contratos", "vaga", "vagas", "escala", "escalas", "mercadoria", "mercadorias", "extrato", "banco", "cheque", "cheques", "entrega", "entregas", "pedido", "pedidos", "funcionario", "funcionarios", "colaborador", "colaboradores", "atestado", "atestados", "registro", "registros", "desconto", "descontos", "salario", "salarios", "comissao", "comissoes", "dia", "dias", "semana", "mes"]);
/* limpeza do item: espaços, pontuação final (; : , .) e maiúsculas internas comuns */
const limpaItem = t => String(t == null ? "" : t).replace(/\s+/g, " ").trim().replace(/[\s;:,.]+$/, "")
  .replace(/(\s)(\p{Lu}\p{Ll}+)(?=\s|$|[,.;:!?)])/gu, (m, sp, w) => COMUNS_MIN.has(sem(w)) && !NOMES_PES.some(p => sem(p.nome) === sem(w)) ? sp + w.toLowerCase() : m);
/* narrativa: "Toda segunda ele vai conferir as lojas" → "Conferir as lojas (toda segunda-feira)"; "Faz X toda segunda" → "Fazer X (toda segunda-feira)". Só com verbo reconhecido. */
const FREQ_PAL_F = "(?:segunda|ter[çc]a|quarta|quinta|sexta|s[áa]bado|domingo)(?:-feira)?|dia|semana|m[êe]s|quinzena|ano|trimestre|semestre";
const FREQ_INI_F = new RegExp("^(toda|todo|todas|todos|cada)\\s+(" + FREQ_PAL_F + ")\\s*[,:]?\\s+(?=\\p{L})", "iu");
const FREQ_FIM_F = new RegExp("\\s+(toda|todo|todas|todos|cada)\\s+(" + FREQ_PAL_F + ")\\.?$", "iu");
const SUJEITO_F = /^(ele|ela|eles|elas|a pessoa|o colaborador|a colaboradora|o gestor|a gestora|o respons[áa]vel|a respons[áa]vel)\s+/i;
const AUX_F = /^(vai|v[ãa]o|costuma|costumam|deve|devem|precisa|precisam|pode|podem|tem que|t[êe]m que)\s+/i;
const freqTexto = f => f.toLowerCase().replace(/\s+(segunda|ter[çc]a|quarta|quinta|sexta)$/, " $1-feira");
function narrativaInf(t) {
  let s = t, freq = "", m;
  if ((m = s.match(FREQ_INI_F))) { freq = m[1] + " " + m[2]; s = s.slice(m[0].length); }
  else if ((m = s.match(FREQ_FIM_F)) && s.slice(0, m.index).trim()) { freq = m[1] + " " + m[2]; s = s.slice(0, m.index); }
  const suj = s.match(SUJEITO_F); if (suj) s = s.slice(suj[0].length);
  const aux = s.match(AUX_F); if (aux) s = s.slice(aux[0].length);
  if (!freq && !suj && !aux) return null;
  s = s.trim();
  const inf = ehVerboInf(primeiraPalavra(s)) ? coordVerbos(s) : verboConjugadoInf(s);
  return inf ? inf + (freq ? " (" + freqTexto(freq) + ")" : "") : null;
}
/* destino, não objeto: "Entrega para o cliente" não vira "Entregar o cliente" */
const PARA_DESTINO_F = new Set(["Entregar", "Enviar", "Distribuir", "Vender", "Comprar", "Repor", "Apresentar"]);
/* núcleo: frase que começa com substantivo, forma verbal ou verbo no infinitivo → infinitivo. null se não souber. */
function nucleoInf(t) {
  t = String(t == null ? "" : t).trim(); if (!t) return "";
  const w = primeiraPalavra(t), n = sem(w), resto = t.slice(w.length).trim();
  const nar = narrativaInf(t); if (nar) return nar;
  if (n === "se" && resto && !/[,;]/.test(resto)) return "Verificar se " + resto;                   /* "Se tudo está anotado" → "Verificar se tudo está anotado" */
  if (/^quant(os|as)$/.test(n) && /\b(foi|foram|for|forem)\b/.test(sem(resto))) return "Controlar " + t.charAt(0).toLowerCase() + t.slice(1);   /* "Quantos foram pagos…" → "Controlar quantos foram pagos…" */
  if (n === "ajuda" && /^(o|a|os|as)\s/i.test(resto)) return coordMeio("Ajudar " + resto);   /* "Ajuda o X a fazer a DRE" → "Ajudar o X a fazer a DRE" */
  const fg = t.match(FAZER_GC);
  if (fg) { const e = buscaN(sem(fg[1])), c = e ? complementoInf(e, fg[2].trim()) : null; return c == null ? null : coordMeio(e.v + (c ? " " + c : "")); }
  if (ehVerboInf(w)) return coordMeio(coordVerbos(t));
  const v = verboConjugadoInf(t); if (v) return coordMeio(v);
  const ck = chaveCompleta(n);
  if (ck && !/^(e|ou)\s/i.test(resto)) return COMPLETA[ck] + " " + w.toLowerCase() + (resto ? " " + resto : "");
  const e = buscaN(n); if (!e) return null;
  if (!resto) return e.v;
  if (/^(e|ou)\s/i.test(resto)) { const r = coordMeio(e.v + " " + resto); return r === e.v + " " + resto ? null : r; }   // "Programação e controle das férias" → "Programar e controlar as férias"
  if (/^se\s/i.test(resto)) return coordMeio(e.v + " " + resto);                                                    // "Conferência se tudo foi debitado" → "Conferir se tudo foi debitado"
  const pp = resto.match(/^para\s+((?:o|a|os|as)\s.+)$/i);
  if (pp && e.p === "de" && !PARA_DESTINO_F.has(e.v)) return coordMeio(e.v + " " + pp[1]);                       // "Agendamento para o pagamento de boletos" → "Agendar o pagamento de boletos"
  const c = complementoInf(e, resto); if (c == null) return null;
  return coordMeio(e.v + (c ? " " + c : ""));
}
/* "e lance", "e controle das férias" dentro da frase: ainda precisam ir ao infinitivo */
const pendenteCoord = s => coordMeio(coordVerbos(s)) !== s;
const problemaFuncao = t => { const s = String(t == null ? "" : t).trim(), w = primeiraPalavra(s); return !!s && !ehPlaceholder(s) && (!w || !ehVerboInf(w) || FAZER_GC.test(s) || pendenteCoord(s)); };   // "100% da Rescisão" (sem palavra no início) também é fora do padrão
/* sintagma nominal sem verbo ("Exames admissionais", "Entrevistas de desligamento"): "Realizar" + a frase. Cláusulas ("Se…", "Quando…", "Não há…") e frases com "se" no meio ficam de fora (violação). */
const SUFIXO_NOME = /(ção|ções|mento|mentos|agem|agens|ência|ências|dade|dades|ura|ise)$/;
const PLURAL_NOME = /(es|as|is|ios|ns|ais)$/;
const NAO_INICIO_NOME = /^(se|quando|quantos|quantas|n[aã]o|pela|pelo|pelas|pelos|toda|todo|tudo|que|como)$/i;
const fallbackRealizar = t => {
  const s = String(t == null ? "" : t).trim().replace(/[\s;.:,]+$/, ""), w = primeiraPalavra(s);
  if (!w || NAO_INICIO_NOME.test(w) || /\s(se|quando|porque|pois)\s/i.test(s)) return "";
  if (!SUFIXO_NOME.test(w.toLowerCase()) && !(sem(w).length >= 5 && PLURAL_NOME.test(sem(w)))) return "";
  return "Realizar " + (/\p{Lu}/u.test(s.charAt(1)) ? s : s.charAt(0).toLowerCase() + s.slice(1));
};
/* "Pela tarde realizar o pagamento…" → "Realizar o pagamento… (pela tarde)": o adjunto inicial vai para o fim, só se o resto já começa com verbo */
const converteNucleo = t => {
  const pa = t.match(/^(pel[ao]s?\s+\p{L}+)\s+(\p{L}.*)$/iu);
  if (pa) { const w2 = primeiraPalavra(pa[2]); if (ehVerboInf(w2) || INF_CONHECIDO.has(sem(w2))) { const b = nucleoInf(pa[2]); if (b) return b + " (" + pa[1].toLowerCase() + ")"; } }
  return nucleoInf(t) || fallbackRealizar(t) || null;
};
/** Função: verbo no infinitivo no início. Devolve o texto igual se já estiver no padrão ou se não souber converter com segurança. */
function ajustaFuncao(t) {
  t = limpaItem(t); if (ehPlaceholder(t)) return ""; if (!problemaFuncao(t)) return t;
  let m = t.match(/^respons[aá]vel\s+(?:pel[oa]s?|por)\s+(.+)$/i), r;               // "Responsável pelo acompanhamento dos indicadores" → "Acompanhar os indicadores"
  if (m) r = nucleoInf(m[1]);
  else if ((m = t.match(/^responsabilidade\s+(?:(integral|total)\s+)?(pel[oa]s?|por)\s+(.+)$/i))) r = "Responder " + (m[1] ? {integral:"integralmente", total:"totalmente"}[m[1].toLowerCase()] + " " : "") + m[2].toLowerCase() + " " + m[3];
  else r = converteNucleo(t);
  r = r ? maiuscula(r) : "";
  return r && !problemaFuncao(r) ? r : t;
}
const problemaRotina = t => { const s = String(t == null ? "" : t).trim(), w = primeiraPalavra(s); return !!s && !ehPlaceholder(s) && (DIA_INICIO.test(s) || PARTIR_INICIO.test(s) || !w || !ehVerboInf(w) || FAZER_GC.test(s) || pendenteCoord(s)); };
/** Rotina: verbo no infinitivo no início, com a frequência por extenso no fim quando havia dia ("Visitar as lojas (segunda-feira)"). */
function ajustaRotina(t) {
  t = limpaItem(t); if (ehPlaceholder(t)) return ""; if (!problemaRotina(t)) return t;
  let base = t, sufixo = "", m = t.match(DIA_INICIO);
  if (m) { base = m[5].trim(); sufixo = " (" + freqTexto((m[2] ? m[2] + " " : "") + m[3] + (m[4] || "")) + ")"; }
  else if ((m = t.match(PARTIR_INICIO))) { base = m[3].trim(); sufixo = " (a partir " + m[1].toLowerCase() + " " + m[2].trim().toLowerCase() + ")"; }
  const r = converteNucleo(base);
  if (!r) return t;
  const out = maiuscula(r) + sufixo;
  return problemaRotina(out) ? t : out;
}
/** Lista o que foge do padrão (para avisar na tela e travar a publicação). */
function violacoesEstilo(funcoes, rotinas) {
  const v = [];
  (funcoes || []).forEach(t => { if (problemaFuncao(t)) v.push({tipo:"funcao", t}); });
  (rotinas || []).forEach(r => { if (problemaRotina(r.t)) v.push({tipo:"rotina", t:r.t, f:r.f}); });
  return v;
}
const mensagemEstilo = v => "Para publicar, ajuste o padrão: função e rotina começam com verbo no infinitivo. Exemplo: “Conferir o ponto”. Revise:" + v.slice(0, 3).map(x => "“" + x.t.slice(0, 50) + "”").join(", ") + (v.length > 3 ? " e mais " + (v.length - 3) : "") + ".";
const ajustaFuncoes = l => (l || []).map(t => ajustaFuncao(t)).filter(Boolean);
const ajustaRotinas = l => (l || []).map(r => ({...r, t:ajustaRotina(r.t)})).filter(r => r.t);
/* o que o ajuste faz: frases reescritas, itens sem atividade retirados e as que ainda ficam fora do padrão */
function resumoAjuste(funcoes, rotinas) {
  const fo = (funcoes || []).filter(t => !ehPlaceholder(t)), ro = (rotinas || []).filter(r => !ehPlaceholder(r.t));
  const mudadas = fo.filter(t => ajustaFuncao(t) !== t).length + ro.filter(r => ajustaRotina(r.t) !== r.t).length;
  const removidas = (funcoes || []).length - fo.length + (rotinas || []).length - ro.length;
  return {mudadas, removidas, fora:violacoesEstilo(ajustaFuncoes(funcoes), ajustaRotinas(rotinas))};
}
const plural = (n, um, varios) => n + " " + (n === 1 ? um : varios);
const avisoAjuste = r => [r.mudadas ? plural(r.mudadas, "frase ajustada", "frases ajustadas") + " automaticamente ao padrão, com função e rotina no infinitivo" : "", r.removidas ? plural(r.removidas, "item sem atividade retirado", "itens sem atividade retirados") : "",
  r.fora.length ? plural(r.fora.length, "frase precisa ser reescrita por você", "frases precisam ser reescritas por você") + ": " + r.fora.slice(0, 3).map(x => "“" + x.t.slice(0, 40) + "”").join(", ") + (r.fora.length > 3 ? " e mais " + (r.fora.length - 3) : "") : ""].filter(Boolean).join("; ") + ". Confira.";
/* exibição: o padrão vale também para dados antigos já gravados (idempotente) */
/* lista de chefes em ordem hierárquica, com recuo por nível (usada em "Reporta a") */
function opcoesHierarquia(cs, selecionado) {
  const ids = new Set(cs.map(c => c.id)), por = Object.fromEntries(cs.map(c => [c.id, c])), nivelDe = c => { let n = 0, p = c.pai && ids.has(c.pai) ? por[c.pai] : null; while (p && n < 30) { n++; p = p.pai && ids.has(p.pai) ? por[p.pai] : null; } return n; };
  return ordemHierarquia(cs).map(c => `<option value="${esc(c.id)}" ${c.id === selecionado ? "selected" : ""}>${"\u00a0\u00a0\u00a0".repeat(nivelDe(c))}${nivelDe(c) ? "└ " : ""}${esc(c.nome)}${c.pessoa ? " · " + esc(c.pessoa) : ""}</option>`).join("");
}
/* uma linha de função pode trazer várias ações juntas ("… é com ele Faz X, Faz Y"): separa em itens */
function dividirFuncao(t) {
  return String(t || "").split(/,\s*(?=(?:Faz|Fazer|Realiza|Realizar|Controla|Controlar|Aprova|Aprovar|Confere|Conferir)\s)|\s+(?=(?:Faz|Fazer|Realiza|Realizar|Controla|Controlar|Aprova|Aprovar|Confere|Conferir)\s)/).map(s => s.trim()).filter(Boolean);
}
/* funções de preço e valor ganham um rótulo e o responsável, quando o texto informa quem decide */
function funcaoCartao(t) {
  const txt = apresentaFuncao(t), preco = /pre[çc]o|valor|custo|desconto|percentual|%/i.test(t);
  const resp = (t.match(/\bé com (ele|ela|[\p{Lu}][\p{L}]+)/u) || [])[1];
  const tag = preco ? `<span class="tag-fn">Alteração de preço</span>` : "";
  const quem = resp ? `<small class="fn-resp">Responsável: ${/^(ele|ela)$/i.test(resp) ? "este cargo" : esc(capitalizaNomes2(resp))}</small>` : "";
  return `<span class="fn-txt">${esc(txt)}</span>${tag}${quem}`;
}
/* motivo, em português simples, para uma frase que o ajuste não conseguiu converter */
function motivoFrase(t) {
  const s = String(t || "").trim();
  if (/^(n[aã]o|se|quando|quantos|quantas|pela|pelo|toda|todo|sempre)\b/i.test(s)) return "começa com condição ou tempo; comece pela ação";
  if (/^\p{Lu}\p{Ll}+\s+(e|ou|com|para)\b/u.test(s) || /^[\p{Lu}][\p{Ll}]+(\s|$)/u.test(s) && !ehVerboInf(primeiraPalavra(s))) return "começa com nome ou palavra que não é ação; comece pelo verbo";
  return "não tem verbo de ação claro; comece pelo verbo no infinitivo";
}
function apresentaFuncao(t) { return capitalizaNomes2(formalizar(ajustaFuncao(t), true)); }
function apresentaRotina(t) { return capitalizaNomes2(formalizar(ajustaRotina(t), true)); }


/* ---------- formalização: acabamento do texto (muda a forma, não o sentido; não acrescenta conteúdo) ---------- */
const ABREV_F = new Map(Object.entries({vc:"você", vcs:"vocês", pq:"porque", q:"que", tb:"também", tbm:"também", td:"tudo", qdo:"quando", obs:"observação", dps:"depois", hj:"hoje", msg:"mensagem", pra:"para", pras:"para as", pro:"para o", sab:"sábado"}));
const SIGLAS_F = new Map(Object.entries({dp:"DP", rh:"RH", ti:"TI", nf:"NF", cpd:"CPD", epi:"EPI", clt:"CLT", inss:"INSS", fgts:"FGTS", cnpj:"CNPJ", cpf:"CPF", rg:"RG", ctps:"CTPS", dre:"DRE", pdv:"PDV", esocial:"eSocial"}));
/* palavras inteiras sem acento (lista conservadora: só o que quase nunca significa outra coisa) e erros de digitação comuns */
const ACENTOS_F = new Map();
"nao não voce você voces vocês horario horário horarios horários uteis úteis sabado sábado terca terça sexa sexta relatorio relatório relatorios relatórios funcionario funcionário funcionarios funcionários conferencia conferência conferencias conferências reuniao reunião reunioes reuniões informacao informação informacoes informações orientacao orientação orientacoes orientações acao ação acoes ações gestao gestão solicitacao solicitação solicitacoes solicitações producao produção obrigacao obrigação obrigacoes obrigações avaliacao avaliação avaliacoes avaliações documentacao documentação operacao operação operacoes operações comunicacao comunicação supervisao supervisão aprovacao aprovação devolucao devolução emissao emissão cobranca cobrança fiscalizacao fiscalização atualizacao atualização verificacao verificação lancamento lançamento lancamentos lançamentos admissao admissão demissao demissão rescisao rescisão funcao função funcoes funções atribuicao atribuição atribuicoes atribuições codigo código codigos códigos padrao padrão padroes padrões tecnico técnico tecnica técnica tecnicos técnicos decisao decisão decisoes decisões sessao sessão secao seção referencia referência ocorrencia ocorrência ocorrencias ocorrências pendencia pendência pendencias pendências inconsistencia inconsistência divergencia divergência divergencias divergências competencia competência urgencia urgência tolerancia tolerância substituicao substituição reposicao reposição separacao separação distribuicao distribuição validacao validação conciliacao conciliação possivel possível possiveis possíveis responsavel responsável responsaveis responsáveis necessario necessário necessaria necessária necessarios necessários necessarias necessárias proximo próximo proxima próxima proximos próximos proximas próximas ultimo último ultima última ultimos últimos ultimas últimas tambem também ja já so só sera será ate até apos após alem além mes mês mao mão maos mãos sao são estao estão pagina página paginas páginas area área areas áreas numero número numeros números basico básico basica básica servico serviço servicos serviços promocao promoção vinculo vínculo atencao atenção medio médio politica política politicas políticas exigencia exigência frequencia frequência experiencia experiência experiencias experiências auxilio auxílio descricao descrição prestacao prestação emergencia emergência inventario inventário cartao cartão cartoes cartões relacao relação relacoes relações orcamento orçamento orcamentos orçamentos comissao comissão comissoes comissões resolucao resolução conteudo conteúdo"
  .split(" ").forEach((v, i, l) => { if (i % 2 === 0) ACENTOS_F.set(v, l[i + 1]); });
/* mantém a caixa de quem escreveu: CAIXA ALTA continua em CAIXA ALTA; só a inicial vira maiúscula */
const fzCaixa = (orig, novo) => orig.length > 1 && orig === orig.toUpperCase() ? novo.toUpperCase() : orig.charAt(0) === orig.charAt(0).toUpperCase() ? maiuscula(novo) : novo;
/** Acabamento do texto: espaços e pontuação, abreviações informais, siglas, acentos que faltam, risadas ("kkkk").
    Ponto final só em frase longa (6 palavras ou mais), salvo se semPonto. Não acrescenta conteúdo. */
function formalizar(t, semPonto) {
  let s = String(t == null ? "" : t).normalize("NFC").replace(/[\u00a0\t]/g, " ").replace(/ {2,}/g, " ").trim();
  if (!s) return s;
  s = s.replace(/\s*\bk{3,}\b\.?/gi, "").replace(/ +\n/g, "\n").replace(/\n +/g, "\n")
    .replace(/ +([,.;:!?)\]])/g, "$1").replace(/([(\[]) +/g, "$1")                 // espaço antes de pontuação e depois de "("
    .replace(/([,;:])(?=[\p{L}(])/gu, "$1 ").replace(/([,;])(?:\s*\1)+/g, "$1")     // pontuação colada, vírgulas repetidas
    .replace(/\.{4,}/g, "...").replace(/(?<!\.)\.\.(?!\.)/g, ".");
  s = s.replace(/[\p{L}\p{N}]+/gu, w => {
    const k = w.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
    if (SIGLAS_F.has(k)) return SIGLAS_F.get(k);
    if (ABREV_F.has(k)) return fzCaixa(w, ABREV_F.get(k));
    if (ACENTOS_F.has(k)) return fzCaixa(w, ACENTOS_F.get(k));
    return w;
  }).replace(/\bas vezes\b/gi, m => fzCaixa(m, "às vezes"));
  s = semParenteses(s);
  s = s.replace(/^(\p{L})/u, c => c.toUpperCase());
  if (!semPonto && s.split(/\s+/).length >= 6 && /[\p{L}\p{N}]$/u.test(s)) s += ".";
  return s;
}
/* parênteses não aparecem para o usuário: "A (B)" vira "A, B" (no meio da frase: "A, B, resto"); horário e dia viram parte da frase */
const DIA_TEXTO_F = /^(segunda|ter[çc]a|quarta|quinta|sexta|s[áa]bado|domingo|dias?\b|di[áa]ri|semanal|quinzenal|mensal|trimestral|semestral|anual)/i;
function semParenteses(t) {
  let s = String(t == null ? "" : t);
  if (!/[()]/.test(s)) return s;
  s = s.replace(/\(([^()]*)\)/g, (m, c, pos, todo) => {
    c = c.replace(/\s+/g, " ").trim();
    if (!c) return "";
    const fim = /^\s*[.;:!?]*\s*$/.test(todo.slice(pos + m.length));
    let x;
    if (/^a partir\b/i.test(c)) x = c.replace(/^a partir\s+(?!de\b)/i, "a partir de ");
    else if (/^\d{1,2}(:\d{2}|h)/i.test(c)) x = "das " + c;
    else if (/^(das?|de|at[ée]|às?)\s/i.test(c)) x = c;
    else if (DIA_TEXTO_F.test(c)) x = "em " + c;
    else x = (/^[A-Z]{2,}$/.test(c) || (c.split(" ").length >= 2 && c.split(" ").length <= 4)) ? titulo(c) : c;   // cargo ou sigla: maiúscula; o resto segue como escrito
    return ", " + x + (fim ? "" : ",");
  });
  return s.replace(/[()]/g, "").replace(/\s+([,.;:!?])/g, "$1").replace(/,\s*,/g, ",").replace(/,\s*([.;:!?])/g, "$1").replace(/\s{2,}/g, " ");
}
/* nomes e cargos: inicial maiúscula; preposições ficam em minúscula ("Analista de DP", "Gisele") */
const PARTIC_F = new Set(["de", "do", "da", "dos", "das", "e", "ou", "em", "para", "com", "a", "o", "no", "na", "nos", "nas", "ao", "aos", "por", "sem", "pelo", "pela"]);
/* cargo entre parênteses (até 4 palavras): cada palavra com inicial maiúscula, preposições em minúscula */
const TEMPO_F = /^(toda|todo|todas|todos|cada|pela|pelo|de manh|de tarde|de noite)\b|\b(segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo|diari|semanal|mensal)/i;   // adjunto de tempo não é nome nem cargo: fica como está
const titulo = x => TEMPO_F.test(x.trim()) ? x : x.trim().split(/\s+/).length > 4 || /\b(n[aã]o|sabe|sei|sim)\b/i.test(x) ? maiuscula(x) : x.replace(/[\p{L}]+/gu, (w, pos) => { const lw = w.toLowerCase(); return PARTIC_F.has(lw) && pos > 0 ? lw : w === lw ? maiuscula(w) : w; });
/* "gisele (analista de dp)" → "Gisele (Analista de DP)": o resto da frase fica como está, só com a inicial */
const capitalizaNomes = x => x.split(/(\([^()]*\))/).map(p => p.startsWith("(") && p.endsWith(")") ? "(" + titulo(p.slice(1, -1)) + ")" : p).join("");
/* nomes de pessoas: sempre com inicial maiúscula. A lista vem dos cargos e das entrevistas (defineNomes); casa a palavra inteira, sem caixa nem acento ("auricelia" → "Auricélia"). */
let NOMES_PES = [];
const NOMES_COMUNS = new Set(["mar","rosa","sol","paz","luz","rio","dia","bem","sim","nao","não","vaga","caixa","loja","lojas","gerente","gestor","analista","fiscal","compras","vendas","pessoas","ponto","area","área","equipe","setor","cliente","fornecedor"]);
const CLASSE_LETRA = {a:"aáàâãä", e:"eéèêë", i:"iíìîï", o:"oóòôõö", u:"uúùûü", c:"cç", n:"nñ"};
const padraoNome = n => n.split("").map(ch => ch === " " ? "\\s+" : CLASSE_LETRA[sem(ch)] ? "[" + CLASSE_LETRA[sem(ch)] + "]" : ch.replace(/[.*+?^${}()|[\]\\\/]/g, "\\$&")).join("");
const defineNomes = l => {
  const nomes = new Map();
  [].concat(l || []).flatMap(x => String(x == null ? "" : x).replace(/\([^()]*\)/g, " ").split(/\s+e\s+|\s+ou\s+|,|[\/]/)).forEach(x => {
    const n = x.replace(/\s+/g, " ").trim();
    if (n.length < 3 || /^(vaga|n[aã]o|sem|nenhum[a]?|a definir|pendente)\b/i.test(n)) return;
    const pr = n.split(" ")[0];
    [n, ...(pr.length >= 3 && !NOMES_COMUNS.has(sem(pr)) ? [pr] : [])].forEach(k => { if (!nomes.has(sem(k))) nomes.set(sem(k), titulo(k)); });
  });
  NOMES_PES = [...nomes.values()].sort((a, b) => b.length - a.length).map(nome => ({nome, re:new RegExp("(?<![\\p{L}])" + padraoNome(nome) + "(?![\\p{L}])", "giu")}));
};
const capitalizaNomes2 = t => { let s = String(t == null ? "" : t); NOMES_PES.forEach(p => { s = s.replace(p.re, p.nome); }); return s; };
/* jornada: dias e horário reconhecidos na forma comum (sem acento, com "as", "a", "-" ou "ate") */
const JORNADA_DIA = [
  [/(?:\bde\s+)?\b(?:segunda|seg)(?:-?feira)?\s*(?:a|ate|-)\s*(?:sabado|sab)\b/, "Segunda a sábado"],
  [/(?:\bde\s+)?\b(?:segunda|seg)(?:-?feira)?\s*(?:a|ate|-)\s*(?:sexta|sexa|sex)(?:-?feira)?\b/, "Segunda a sexta-feira"],
  [/(?:\bde\s+)?\bdias?\s+uteis\b/, "Segunda a sexta-feira"],
  [/\bsabados?\s+alternados?\b/, "Sábados alternados"]
];
const JORNADA_HORA = /(?:\b(?:das?|de)\s+)?(?<![\dx])(\d{1,2})(?:(?::|h)(\d{2}))?h?\s*(?:as|a|-|ate)\s*(\d{1,2})(?:(?::|h)(\d{2}))?h?(?!\d)/;
const hora_F = (h, m) => +h + "h" + (+m ? String(+m).padStart(2, "0") : "");
const JORNADA_CARGA = /\b\d{1,2}\s*(?:h|horas?)\s*(?:semanais?|diarias?|por\s+(?:dia|semana))\b/;   // carga escrita no texto antigo (sem acento): sai e é recalculada
const JORNADA_ROTULO = /^(dias|hor[aá]rio|carga\s+hor[aá]ria|observa[cç][õo]es)\s*:\s*/i;
const acento = p => p.replace(/[aeiouc]/g, c => ({a:"[aáàâã]", e:"[eéêè]", i:"[iíî]", o:"[oóôõ]", u:"[uúü]", c:"[cç]"})[c]);   // casa com ou sem acento
/* frases informais das observações → forma cordial (o que não estiver aqui só é formalizado, sem inventar nada) */
const JORNADA_FRASES = [
  [acento("(ficam|fica) devendo horas"), "há horas pendentes de compensação"],
  [acento("com horario estendido"), "horário estendido"],
  [acento("(as vezes|de vez em quando|eventualmente|eventual) (ao|aos) sabados?"), "eventualmente, aos sábados"]
].map(([p, r]) => [new RegExp("(?<!\\p{L})" + p.replace(/ /g, "\\s+") + "(?!\\p{L})", "iu"), r]);     // \b não serve para "às" (letra acentuada)
const fimFrase = x => /[\p{L}\p{N})]$/u.test(x) ? x + "." : x;
const jornadaCap = x => { const s = String(x == null ? "" : x).replace(/\s+/g, " ").trim(); return s.charAt(0).toUpperCase() + s.slice(1); };
const jornadaFrases = x => JORNADA_FRASES.reduce((s, [re, rep]) => s.replace(re, rep), x);
const semAcMin = x => String(x == null ? "" : x).normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();   // mesmo tamanho do texto original
const mmin = q => +(q || 0);
/* avisos fixos da jornada: saem do texto antes de recalcular, para não se repetir */
const AV_ALMOCO = "Confirmar o horário de almoço com o gestor.";
const AV_INCONS = "Horário inconsistente: confirmar com o gestor.";
const OBS_LIXO = /entre\s+entrada\s+e\s+sa[ií]da|carga\s+hor[aá]ria/i;      // a carga nunca vai para as observações
const hmTexto = m => { const h = Math.floor(m / 60), r = m % 60; return (h ? h + (h === 1 ? " hora" : " horas") : "") + (r ? (h ? " e " : "") + r + (r === 1 ? " minuto" : " minutos") : ""); };
const duracaoTexto = m => (m === 60 ? "uma hora" : m === 30 ? "meia hora" : hmTexto(m));
const ALMOCO_ANTES = /\b(?:com\s+)?(meia|uma|um|duas|\d{1,2})\s*(horas?|h|minutos?|min)?\s*(?:de\s+)?(?:intervalo\s+(?:de\s+)?)?almoco\b/;
const ALMOCO_DEPOIS = /\balmoco\s*(?:de\s+|:\s*)?(meia|uma|um|duas|\d{1,2})\s*(horas?|h|minutos?|min)\b/;
/** Duração do almoço escrita no texto ("uma hora de almoço", "almoço de 30 minutos"). Horário ("das 12h de almoço") não conta. */
function duracaoAlmoco(b) {
  const m = ALMOCO_ANTES.exec(b) || ALMOCO_DEPOIS.exec(b);
  if (!m) return null;
  const n = m[1], u = m[2] || "";
  let min;
  if (n === "meia") min = 30;
  else if (n === "uma" || n === "um") min = 60;
  else if (n === "duas") min = 120;
  else if (/^min/.test(u)) min = +n;
  else if (u) { if (+n > 4) return null; min = +n * 60; }
  else min = +n <= 4 ? +n * 60 : +n;
  return {min, pos:m.index, len:m[0].length};
}
/** Núcleo da jornada: lê os horários (b = texto minúsculo, sem acento; orig = texto como foi escrito), desconta o almoço e devolve horário, carga e avisos.
    Horário inconsistente (saída antes da entrada, mais de 12 horas, entrada sem saída) não gera carga. */
function jornadaCalc(b, dias, orig) {
  const r = {horario:"", carga:"", avisos:[], incons:false, spans:[], raw:""};
  const ivs = [], rh = new RegExp(JORNADA_HORA.source, "g"); let mh;
  while ((mh = rh.exec(b))) {
    const v = mh.slice(1).map(mmin), a = v[0] * 60 + v[1], z = v[2] * 60 + v[3];
    ivs.push({a:mh.index, z:mh.index + mh[0].length, ini:a, fim:z, dur:z - a, h:v, ok:v[1] < 60 && v[3] < 60 && v[0] < 24 && v[2] <= 24});
    r.spans.push([mh.index, mh.index + mh[0].length]);
  }
  r.raw = ivs.map(x => (orig ? orig.slice(x.a, x.z) : "").trim()).join(" e ");
  for (let k = 1; k < ivs.length; k++) if (/^[\s,]*e[\s,]*$/.test(b.slice(ivs[k - 1].z, ivs[k].a))) r.spans.push([ivs[k - 1].z, ivs[k].a]);   // o "e" que liga dois turnos
  const al = duracaoAlmoco(b);
  if (al) r.spans.push([al.pos, al.pos + al.len]);
  const ent = /\(?\s*\d{1,2}\s*(?:h|horas?)\s+entre\s+entrada\s+e\s+saida\s*\)?/.exec(b);
  if (ent) r.spans.push([ent.index, ent.index + ent[0].length]);
  const pos = b.indexOf("almoco");
  let brk = null;                                                             // intervalo de almoço escrito junto ("com almoço das 12h às 13h")
  if (pos >= 0 && ivs.length >= 2) {
    const perto = ivs.filter(x => x.dur > 0 && x.dur <= 180 && Math.min(Math.abs(x.a - pos), Math.abs(x.z - pos)) < 40);
    if (perto.length) { brk = perto.reduce((p, c) => (c.dur < p.dur ? c : p)); ivs.splice(ivs.indexOf(brk), 1); }
  }
  if (!ivs.length) { if (/\d{1,2}\s*(?::\d{2}|h)/.test(b)) r.incons = true; return r; }
  if (ivs.length > 2 || ivs.some(x => !x.ok || x.dur <= 0)) { r.incons = true; return r; }
  let trabalho, texto;
  if (ivs.length === 1) {
    const x = ivs[0], almo = brk ? brk.dur : al ? al.min : 60;
    if (x.dur > 720 || almo >= x.dur) { r.incons = true; return r; }
    trabalho = x.dur - almo;
    texto = "das " + hora_F(x.h[0], x.h[1]) + " às " + hora_F(x.h[2], x.h[3]);
    if (brk) texto += ", com almoço das " + hora_F(brk.h[0], brk.h[1]) + " às " + hora_F(brk.h[2], brk.h[3]);
    else if (al) texto += ", com " + duracaoTexto(al.min) + " de almoço";
    else r.avisos.push(AV_ALMOCO);                                            // sem almoço informado: assume 1 hora e pede confirmação
  } else {
    const p = ivs[0], q = ivs[1];                                             // dois turnos explícitos: soma sem desconto
    if (q.ini < p.fim || q.fim - p.ini > 720) { r.incons = true; return r; }
    trabalho = p.dur + q.dur;
    texto = "das " + hora_F(p.h[0], p.h[1]) + " às " + hora_F(p.h[2], p.h[3]) + " e das " + hora_F(q.h[0], q.h[1]) + " às " + hora_F(q.h[2], q.h[3]);
  }
  const d = semAcMin(dias || "");
  const n = /escala|alternad/.test(d) ? 0 : /segunda a sexta/.test(d) ? 5 : /segunda a sabado/.test(d) ? 6 : 0;   // escala só informa a escala: sem semana
  r.horario = texto;
  r.carga = hmTexto(trabalho) + " por dia" + (n ? ", " + hmTexto(trabalho * n) + " por semana" : "");
  return r;
}
/** Fecha a jornada: horário recalculado, carga horária e observações. Avisos antigos não se repetem. */
function jornadaFecha(dias, horTxt, obsTxt, cal) {
  const c = cal || jornadaCalc(semAcMin(horTxt), dias, horTxt);
  const obs = jornadaObs(String(obsTxt == null ? "" : obsTxt).split(AV_ALMOCO).join(" ").split(AV_INCONS).join(" "));
  const txt = [obs].concat(c.incons ? [AV_INCONS] : c.avisos).filter(Boolean).join(" ");
  if (c.incons) return {dias:jornadaCap(dias), horario:jornadaCap(horTxt), carga:"", obs:txt};
  return {dias:jornadaCap(dias), horario:jornadaCap(c.horario) || jornadaCap(horTxt), carga:c.carga, obs:txt};
}
/** Observações: parênteses e trechos depois de " - " ou ";" viram frases; frases informais são trocadas; cada frase é formalizada. A carga horária sai daqui. */
function jornadaObs(t) {
  const s = String(t == null ? "" : t).replace(/\s+/g, " ").trim().replace(/\(([^()]*)\)/g, (m, x) => ". " + x + ". ").replace(/\s+[-–—]\s+|;/g, ". ");
  return jornadaFrases(s).split(".").map(x => x.replace(/^[\s,:\-–—]+|[\s,:\-–—]+$/g, "")).filter(x => x && !OBS_LIXO.test(x)).map(x => fimFrase(formalizar(x, true))).join(" ");
}
/** Separa a jornada em Dias, Horário de trabalho, Carga horária e Observações. Aceita o formato com rótulos (inclusive o de três partes) e texto corrido. */
function jornadaPartes(t) {
  const s = String(t == null ? "" : t).normalize("NFC").replace(/\s+/g, " ").trim();
  if (!s) return {dias:"", horario:"", carga:"", obs:""};
  if (JORNADA_ROTULO.test(s)) {                                               // com rótulos: a carga é sempre recalculada pelo horário
    const p = {dias:[], horario:[], obs:[]};
    for (const pc of s.split(/\s*\|\s*(?=(?:dias|hor[aá]rio|carga\s+hor[aá]ria|observa[cç][õo]es)\s*:)/i)) {
      const m = JORNADA_ROTULO.exec(pc), v = m ? pc.slice(m[0].length).trim() : pc.trim();
      if (!m) p.obs.push(v);
      else if (/^dias/i.test(m[1])) p.dias.push(v);
      else if (/^hor/i.test(m[1])) p.horario.push(v);
      else if (!/^carga/i.test(m[1])) p.obs.push(v);
    }
    return jornadaFecha(p.dias.join(" "), p.horario.join(" "), p.obs.join(" "), null);
  }
  const b = semAcMin(s), spans = [];
  let dia = "";
  for (const [re, nome] of JORNADA_DIA) { const m = re.exec(b); if (m) { dia = nome; spans.push([m.index, m.index + m[0].length]); break; } }
  const me = /\b(?:escala\s+)?([56])\s*x\s*1\b/.exec(b), escala = me ? "Escala " + me[1] + "x1" : "";
  if (me) spans.push([me.index, me.index + me[0].length]);
  const mc = JORNADA_CARGA.exec(b);
  if (mc) spans.push([mc.index, mc.index + mc[0].length]);
  const dias = [escala, dia].filter(Boolean).join(", ");
  const cal = jornadaCalc(b, dias, s);
  if (!dias && !cal.horario && !cal.incons) return {dias:"", horario:"", carga:"", obs:fimFrase(formalizar(jornadaFrases(s), true))};   // sem dia nem horário: o texto inteiro vai para observações
  const todos = spans.concat(cal.spans);
  const res = s.split("").filter((c, i) => !todos.some(([a, z]) => i >= a && i < z)).join("");
  return jornadaFecha(dias, cal.raw, res, cal);
}
/** Texto canônico: "Dias: … | Horário: … | Carga horária: … | Observações: …" (partes vazias saem). */
function jornadaMonta(p) {
  const x = p || {}, v = k => String(x[k] == null ? "" : x[k]).replace(/\s+/g, " ").trim();
  return [v("dias") && "Dias: " + v("dias"), v("horario") && "Horário: " + v("horario"), v("carga") && "Carga horária: " + v("carga"), v("obs") && "Observações: " + v("obs")].filter(Boolean).join(" | ");
}
/** Jornada: "Dias úteis de 8 as 17h" → "Dias: Segunda a sexta-feira | Horário: Das 8h às 17h | Carga horária: 8 horas por dia, 40 horas por semana | Observações: Confirmar o horário de almoço com o gestor.". Idempotente. */
function formalizarJornada(t) { return jornadaMonta(jornadaPartes(t)); }
/** "Em caso de problema": cada orientação vira "Situação: nomes" (ex.: "Própria área: Gisele, Analista de DP"); a ficha mostra uma frase por bullet. */
const CONDICAO_F = /^(em|quando|para|com|sobre|nos|nas|no|na|por|se|caso|ao|aos|às|à|pelo|pela)\s/i;
const SITUACAO_F = /^([^:()]{3,80}):\s*(.+)$/;
const rotuloSituacao = x => {
  const y = String(x == null ? "" : x).replace(/\s+/g, " ").trim();
  if (/pr[óo]pria\s+[áa]rea/i.test(y)) return "Própria área";
  if (/fora\s+da\s+[áa]rea/i.test(y)) return "Fora da área";
  if (/^em caso de problema$/i.test(y)) return "Em caso de problema";
  const z = y.replace(/^em\s+/i, "");
  return z.charAt(0).toUpperCase() + z.slice(1);
};
/** Nome de quem procurar: sigla de área entre parênteses vira ", do RH"; o resto segue a regra geral (vírgula). */
function nomeRecorre(n) {
  const s = String(n == null ? "" : n).replace(/\s+/g, " ").trim().replace(/\(\s*([A-Z]{2,6})\s*\)/g, ", do $1").replace(/\(([^()]*)\)/g, (m, c) => ", " + titulo(c.trim()));
  return capitalizaNomes2(formalizar(s, true)).replace(/^[\s,;.:\-]+|[\s,;:\-]+$/g, "");
}
/** Lê as orientações (texto livre ou já normalizado) e devolve {sit, nome}. Sem situação explícita: "Própria área" se há problema fora da área, senão "Em caso de problema". */
function recorreItens(t) {
  const s = String(t == null ? "" : t).normalize("NFC").replace(/\r?\n+/g, ";").replace(/[ \t]+/g, " ").trim()
    .replace(/^(em caso de problema,?\s*)?(recorre|recorro|procure|procuro)\s+(?:(?:a|ao|à|com)\s+)?/i, "");
  const protege = x => x.replace(/\([^()]*\)/g, m => m.replace(/[,;\/]/g, c => ({",":"\u0001", ";":"\u0002", "/":"\u0003"})[c]).replace(/ /g, "\u0005"));
  const restaura = x => x.replace(/[\u0001-\u0005]/g, c => ({"\u0001":",", "\u0002":";", "\u0003":"/", "\u0005":" "})[c]).replace(/^[\s.\-–—]+|[\s.\-–—]+$/g, "").trim();
  const itens = [];
  for (const g of protege(s).split(";")) {                                    // cada grupo separado por ";"
    const grupo = g.trim();
    if (!grupo) continue;
    const sit = SITUACAO_F.exec(grupo);
    if (sit) { itens.push({sit:rotuloSituacao(restaura(sit[1])), nome:restaura(sit[2])}); continue; }
    const m = grupo.match(/^fora da [áa]rea\s*,?\s*(.*)$/i), fora = !!m, partes = [];
    for (const p of (m ? m[1] : grupo).split(/[,\/]|\se\s/i).map(restaura).filter(Boolean)) {   // "Ana ou Bia" é alternativa: fica num item só
      if (CONDICAO_F.test(p) && partes.length) partes[partes.length - 1] += ", " + p;   // "Ricardo (sócio), em problemas com fornecedores"
      else partes.push(p);
    }
    for (const p of partes) {
      const c = /^(.*?),\s*(em|quando|caso|se)\s+(.+)$/i.exec(p);
      if (c) itens.push({sit:rotuloSituacao((c[2].toLowerCase() === "em" ? "" : c[2] + " ") + c[3]), nome:c[1]});
      else itens.push({sit:fora ? "Fora da área" : null, nome:p});
    }
  }
  const algumFora = itens.some(i => i.sit === "Fora da área"), vistos = new Set(), out = [];
  for (const i of itens) {
    if (/^(n[aã]o recorre|n[aã]o h[aá]|ningu[eé]m|nenhum[a]?$|n\/a$)/i.test(i.nome)) continue;
    const nome = nomeRecorre(i.nome), sit = i.sit || (algumFora ? "Própria área" : "Em caso de problema");
    if (!nome || vistos.has(sem(sit + nome))) continue;
    vistos.add(sem(sit + nome)); out.push({sit, nome});
  }
  return out;
}
/** Forma guardada e editada: uma orientação por item, "Situação: nomes", separadas por ponto e vírgula, sem parênteses. */
const recorreNormaliza = t => recorreItens(t).map(({sit, nome}) => sit + ": " + nome).join("; ");
/** Frases da ficha: uma por orientação, com situação e providência. */
const fraseRecorre = ({sit, nome}) => (sit === "Própria área" ? "Problema da própria área" : sit === "Fora da área" ? "Problema fora da área" : sit) + ": procurar " + nome + ".";
function topicosRecorre(t) { return recorreItens(t).map(fraseRecorre); }
/* missão: fala do CARGO, sem pessoas. Tira parênteses com só nome próprio, os nomes de "nomes" e nomes próprios depois de "a/com/para"; sem completar nem inventar. */
const CARGO_PAL = /(gerente|gestor|analista|assistente|auxiliar|supervis|coordena|diretor|s[oó]cio|respons|l[ií]der|conferente|operador|fiscal|financeir|administra|recursos|departamento|compras|vendas|loja|caixa|contab|advogad|cl[ií]nica|lumi|excel|mrm|grupo|empresa|sobradinho|ger[êe]nc|diretori|[aá]rea|equipe|setor|cliente|fornecedor)/i;
const EXCLUI_NOME = /^(Lumi|Excel|Sobradinho|Grupo|MRM|Google|Lojas?|Financeiro|Contabilidade|Cl[ií]nica|Recursos|Departamento|Diretoria|S[oó]cios?|Fornecedores?|Gerentes?|Funcion[áa]rios?|Colaboradores?|Clientes?|Sistema|Plataforma|Empresa|Brasil|Segunda|Ter[çc]a|Quarta|Quinta|Sexta|S[áa]bado|Domingo|Janeiro|Fevereiro|Mar[çc]o|Abril|Maio|Junho|Julho|Agosto|Setembro|Outubro|Novembro|Dezembro)$/;
const escRe = x => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
function formalizarMissao(t, nomes) { return capitalizaNomes2(missaoFormal(t, nomes)); }
function missaoFormal(t, nomes) {
  const orig = formalizar(t);
  let s = String(t == null ? "" : t).normalize("NFC").replace(/\s+/g, " ").trim();
  if (!s) return orig;
  s = s.replace(/^finalidade do cargo\s*:\s*/i, "").replace(/\bum pouco menos de\b/gi, "com menos").replace(/\bum pouco mais de\b/gi, "com mais").replace(/\bum pouco\s+/gi, "").replace(/(^|\s)(né|tipo|tá)(?=[\s,.;:!?]|$)/gi, "$1").replace(/\s+([,.;:!?])/g, "$1").replace(/,\s*,/g, ",");   // linguagem informal sai; sem acrescentar conteúdo
  const pessoas =[].concat(nomes || []).flatMap(n => String(n == null ? "" : n).split(/\s+e\s+|\s+ou\s+|,|[\/]/)).map(x => x.trim()).filter(x => x.length >= 3);
  const nomeProprio = c => /^\p{Lu}\p{Ll}+(?:\s+\p{Lu}\p{Ll}+){0,2}(?:\s+(?:e|ou)\s+\p{Lu}\p{Ll}+(?:\s+\p{Lu}\p{Ll}+){0,2})?$/u.test(c) && !CARGO_PAL.test(c);
  s = s.replace(/\s*\(([^()]*)\)/g, (m, c) => (nomeProprio(c.trim()) || pessoas.some(p => sem(p) === sem(c.trim()))) ? "" : m);
  const antesNome = s;
  if (pessoas.length) {
    const alt = [...pessoas].sort((a, b) => b.length - a.length).map(escRe).join("|");
    s = s.replace(new RegExp("(?<![\\p{L}])(?:(?:a|o|ao|à|aos|às|com|para|pelo|pela)\\s+)?(?:" + alt + ")(?![\\p{L}])(?:\\s*(?:,|e|ou)\\s*(?:" + alt + ")(?![\\p{L}]))*", "giu"), "");
  }
  s = s.replace(/(^|\s)(a|ao|à|com|para|aos|às)\s+(\p{Lu}\p{Ll}+)(?=[\s.,;:!?]|$)/gu, (m, sp, p, w) => (EXCLUI_NOME.test(w) || CARGO_PAL.test(w)) ? m : sp);   // "para Fulana" → sai o nome
  if (s !== antesNome && /^\p{L}+(ar|er|ir)(\s*[,;]|\s+(de|do|da|dos|das|no|na|nos|nas|em|com|para|a|ao|às|à|pelo|pela|por)\b)/iu.test(s)) return orig;   // "Apoiar a Fulana no fechamento" → "Apoiar no fechamento" perderia o objeto: fica o original
  s = s.replace(/\bmeu cargo\b/gi, "o cargo").replace(/\bminha fun[çc][ãa]o\b/gi, "a função");
  s = s.replace(/\s*\(\s*\)/g, "").replace(/(^|\s)(a|o|ao|à|aos|às|com|para|de|do|da|pelo|pela|e|ou|em|por|sobre)\s*(?=[.,;:!?]|$)/gi, "$1")   // preposição solta no fim
    .replace(/\s+([.,;:!?])/g, "$1").replace(/\s{2,}/g, " ").replace(/^[\s,;:-]+/, "").trim();
  const r = formalizar(s, true).replace(/\s+$/, "");
  if (r.split(/\s+/).filter(Boolean).length < 3) return orig;
  return /[.!?]$/.test(r) ? r : r + ".";
}