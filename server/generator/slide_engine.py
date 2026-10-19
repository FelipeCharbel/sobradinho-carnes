"""
Port do script da skill `build_manual.py`
(C:/Users/Felipe Charbel/.claude/skills/manual-cargos-funcoes/scripts/build_manual.py, 527 linhas)
para operar como biblioteca em memória. Ver docs/CONTRATOS_FASE2.md §0 (como trocar arquivo por
BytesIO, passo a passo) e §8 (onde inserir o slide de organograma e como ajustar a numeração do
sumário).

COMO TRABALHAR: leia o build_manual.py inteiro primeiro. A lógica (clonagem de slides via
`clone()`, preenchimento de texto via `fill_box()`/`place_pairs()`, recolor via `recolor_roles()`,
divisórias via `darken()`/`tinted_seal()`, troca de cor no tema via manipulação de ZIP no final)
NÃO muda. Só muda: (1) de onde vem o SPEC (parâmetro dict, não argv), (2) onde fica T2 (caminho
fixo para assets/T2.pptx, não relativo ao script), (3) para onde vai o resultado (io.BytesIO, não
um caminho de arquivo em disco), (4) a inserção do slide de organograma no modo "completo".

Assets: os caminhos T2/SEAL devem apontar para `sobradinho-carnes/assets/T2.pptx` e
`sobradinho-carnes/assets/selo-circular-preto.png` (já copiados pelo coordenador).
"""
import copy, hashlib, io, math, os, re, sys, zipfile
from xml.sax.saxutils import escape
from PIL import Image
from lxml import etree
from pptx import Presentation
from pptx.util import Inches
from pptx.enum.text import MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.opc.package import Part
from pptx.opc.packuri import PackURI
from pptx.dml.color import RGBColor
import colorsys


def _gerar(spec: dict) -> io.BytesIO:
    """Função interna que replica o corpo inteiro do build_manual.py (linhas 18-526), recebendo
    `spec` como dict em vez de ler de arquivo, e devolvendo io.BytesIO em vez de escrever em OUT.
    Chamada por gerar_slide_cargo (spec com modo="cargo") e gerar_manual_completo (spec sem modo,
    ou modo="completo"). Quando MODE != "cargo" (ver variável MODE do script original, baseada em
    spec.get("modo","completo")), inserir o slide de organograma ANTES de remover os slides
    originais do T2 e ANTES do bloco de recolor/divisórias (ver CONTRATOS_FASE2.md §8 para a
    posição exata e o ajuste dos offsets `3+EXTRA`/`5+EXTRA`/`10+EXTRA`/`11+EXTRA+5*ci` do
    sumário) -- chamar server.generator.organograma_slide.inserir_slide_organograma aqui, passando
    a 'estrutura' (lista de cargos com id/nome/area/nivel/pai) que deve vir dentro do spec como
    spec["estrutura"] (acrescentar essa chave em construir_spec_manual, do spec_builder.py)."""

    # Constantes
    HERE = os.path.dirname(os.path.abspath(__file__))
    # Subir até sobradinho-carnes/
    PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))
    T2 = os.path.join(PROJECT_ROOT, "assets", "T2.pptx")
    SEAL = os.path.join(PROJECT_ROOT, "assets", "selo-circular-preto.png")

    BRAND = spec["cor"].lstrip("#").upper()
    T2_PURPLE = "6F12FF"
    CLIENT = spec["cliente"]
    DOC = "Manual de Cargos, Funções e Rotinas"
    EMAILS = spec.get("emails", [])
    MODE = spec.get("modo", "completo")
    CARGOS = [] if MODE == "base" else spec.get("cargos", [])
    for _i, _c in enumerate(CARGOS):
        _c.setdefault("n", "3.XX" if MODE == "cargo" else "3.%d" % (_i + 1))
        _c["rotinas"] = [(p, it) for p, it in _c["rotinas"]]

    prs = Presentation(T2)
    orig = list(prs.slides)
    IN = 914400

    # ---------- clonagem de slides ----------
    def clone(src):
        new = prs.slides.add_slide(src.slide_layout)
        for shp in list(new.shapes):
            shp._element.getparent().remove(shp._element)
        rmap = {}
        # Itera sobre rels de forma robusta - python-pptx pode variar
        try:
            # Tenta acessar o dict interno _rels
            rels_dict = src.part.rels._rels if hasattr(src.part.rels, '_rels') else {}
            for rId, rel in rels_dict.items():
                if rel.reltype.endswith("/image") and not rel.is_external:
                    rmap[rId] = new.part.relate_to(rel.target_part, rel.reltype)
        except (AttributeError, TypeError):
            # Fallback: iterar pelos rIds conhecidos
            for rId in list(src.part.rels.keys()) if hasattr(src.part.rels, 'keys') else []:
                rel = src.part.rels[rId]
                if rel.reltype.endswith("/image") and not rel.is_external:
                    rmap[rId] = new.part.relate_to(rel.target_part, rel.reltype)

        tree = new.shapes._spTree
        for el in src.shapes._spTree:
            if el.tag in (qn("p:sp"), qn("p:pic"), qn("p:grpSp"), qn("p:cxnSp"), qn("p:graphicFrame")):
                e = copy.deepcopy(el)
                for node in e.iter():
                    for att in (qn("r:embed"), qn("r:link"), qn("r:id")):
                        v = node.get(att)
                        if v in rmap:
                            node.set(att, rmap[v])
                tree.append(e)
        bg = src._element.cSld.find(qn("p:bg"))
        if bg is not None:
            new._element.cSld.insert(0, copy.deepcopy(bg))
        return new

    def S(slide, num):
        for sh in slide.shapes:
            if ";%d;" % num in sh.name:
                return sh
        raise KeyError(num)

    # ---------- texto ----------
    def pars(shape):
        return shape.text_frame._txBody.findall(qn("a:p"))

    def runs_of(p):
        return p.findall(qn("a:r"))

    def set_run(r, text):
        r.find(qn("a:t")).text = text

    def set_par_text(p, text):
        rs = runs_of(p)
        set_run(rs[0], text)
        for r in rs[1:]:
            p.remove(r)

    def make_runs(p, segments, base):
        for r in runs_of(p):
            p.remove(r)
        end = p.find(qn("a:endParaRPr"))
        for text, bold in segments:
            r = copy.deepcopy(base)
            rPr = r.find(qn("a:rPr"))
            if rPr is not None:
                if bold:
                    rPr.set("b", "1")
                elif "b" in rPr.attrib:
                    del rPr.attrib["b"]
            r.find(qn("a:t")).text = text
            if end is not None:
                end.addprevious(r)
            else:
                p.append(r)

    def segments(text):
        return [(t, i % 2 == 1) for i, t in enumerate(text.split("**")) if t]

    def fill_box(shape, items, proto=0, keep=0, markup=False, italic=False, size=None):
        body = shape.text_frame._txBody
        ps = body.findall(qn("a:p"))
        proto_el = copy.deepcopy(ps[proto])
        for p in ps[keep:]:
            body.remove(p)
        for t in items:
            p = copy.deepcopy(proto_el)
            if markup:
                make_runs(p, segments(t), runs_of(proto_el)[0])
            else:
                set_par_text(p, t)
            for r in runs_of(p):
                rPr = r.find(qn("a:rPr"))
                if rPr is not None:
                    if italic:
                        rPr.set("i", "1")
                    if size:
                        rPr.set("sz", str(int(size * 100)))
            body.append(p)

    def set_header(slide, section):
        for sh in slide.shapes:
            if sh.has_text_frame and sh.top < Inches(0.5) and sh.text_frame.text.strip():
                rs = runs_of(pars(sh)[0])
                set_run(rs[0], DOC + " ")
                if len(rs) > 1:
                    set_run(rs[1], "/ " + section)
                return

    def set_footer(slide):
        for sh in slide.shapes:
            if sh.has_text_frame and sh.top > Inches(11) and abs(sh.left - Inches(0.76)) < Inches(0.05) and sh.text_frame.text.strip():
                rs = runs_of(pars(sh)[0])
                if len(rs) >= 2:
                    set_run(rs[0], DOC + " / ")
                    set_run(rs[1], CLIENT)
                    for r in rs[2:]:
                        pars(sh)[0].remove(r)
                else:
                    set_run(rs[0], DOC + " / " + CLIENT)
                return

    def chrome(slide, section):
        set_header(slide, section)
        set_footer(slide)

    # ---------- reflow de pares rótulo | texto ----------
    def est_h(items, width_in, size):
        cpl = (width_in - 0.5) * 72 / (size * 0.58)
        total = sum(max(1, math.ceil(len(t) / cpl)) * size * 1.45 + 5 for t in items)
        return total / 72 + 0.2

    def place_pairs(slide, pairs, y0, gap=0.22, size=12, limit=10.6, xs=None):
        """pairs: (rótulo_shape, texto_shape, rótulo, itens). Ajusta o tamanho se passar do limite."""
        for sz in (size, size - 1, size - 2):
            y = y0
            heights = []
            for lab, txt, name, items in pairs:
                h = est_h(items, txt.width / IN, sz)
                heights.append(h)
                y += max(h, 0.45) + gap
            if y <= limit or sz == size - 2:
                break
        y = y0
        for (lab, txt, name, items), h in zip(pairs, heights):
            set_par_text(pars(lab)[0], name)
            fill_box(txt, items, proto=0, keep=0, italic=(items == ["A confirmar."]), size=sz)
            lab.top = Inches(y)
            txt.top = Inches(y)
            txt.height = Inches(h)
            if xs:
                lab.left, txt.left = Inches(xs[0]), Inches(xs[1])
            y += max(h, 0.45) + gap
        return y

    built = []   # (slide, chave)
    DIVS = []    # divisórias (fundo na cor do cliente, alternando com tom escuro)

    def add(slide, key=None):
        built.append((slide, key))
        return slide

    # ---------- 1 capa ----------
    add(clone(orig[0]), "capa")

    # ---------- 2 sumário (fonte fixa; se não couber, continua em outra página) ----------
    FIRST_MAX, NEXT_MAX = 13, 22
    rest = max(0, len(CARGOS) - FIRST_MAX)
    EXTRA = math.ceil(rest / NEXT_MAX) if rest else 0      # páginas de sumário além da primeira

    def with_page(text, pg):
        m = re.search(r"p.g\s*x\s*$", text)
        dots = text[:m.start()].rstrip()[:-3]          # menos pontos, para o número caber na mesma linha
        return dots + " pág " + pg

    def pg2(n):
        return "XX" if MODE == "cargo" else "%02d" % n

    def build_sumario(chunk, first):
        s = clone(orig[2])
        left, right = S(s, 83), S(s, 84)
        lp, rp = pars(left), pars(right)
        sub = copy.deepcopy(lp[3])
        rsub = copy.deepcopy(rp[3])
        for p in lp[(0 if not first else 3):]:
            left.text_frame._txBody.remove(p)
        for p in rp[(0 if not first else 3):]:
            right.text_frame._txBody.remove(p)
        if first:
            for p, t in zip(pars(left)[:3], ["Introdução", "Descrição dos Cargos", "Cargos"]):
                set_par_text(p, t)
            # CONTRATOS_FASE2.md §8: com organograma, "Descrição dos Cargos" fica em 5+EXTRA (não muda)
            # "Cargos" vira 11+EXTRA (era 10+EXTRA)
            for p, pg in zip(pars(right)[:3], [pg2(3 + EXTRA), pg2(5 + EXTRA), pg2(11 + EXTRA)]):
                r = runs_of(p)[0]
                set_run(r, with_page(r.find(qn("a:t")).text, pg))
        for ci, c in chunk:
            p = copy.deepcopy(sub)
            rs = runs_of(p)
            for r in rs[1:-1]:
                p.remove(r)
            set_run(rs[0], c["n"] + "   ")
            set_run(rs[-1], c["nome"])
            left.text_frame._txBody.append(p)
            q = copy.deepcopy(rsub)
            r = runs_of(q)[0]
            # CONTRATOS_FASE2.md §8: cada cargo vira 12+EXTRA+5*ci (era 11+EXTRA+5*ci)
            set_run(r, with_page(r.find(qn("a:t")).text, pg2(12 + EXTRA + 5 * ci)))
            right.text_frame._txBody.append(q)
        for box in (left, right):                       # sem autoajuste: o tamanho da letra nunca diminui
            bp = box.text_frame._txBody.find(qn("a:bodyPr"))
            for ch in list(bp):
                if ch.tag in (qn("a:normAutofit"), qn("a:spAutoFit"), qn("a:noAutofit")):
                    bp.remove(ch)
            etree.SubElement(bp, qn("a:noAutofit"))
            box.height = Inches(7.8)
        chrome(s, "Sumário")
        return add(s)

    idx = list(enumerate(CARGOS))
    build_sumario(idx[:FIRST_MAX], True)
    for k in range(EXTRA):
        build_sumario(idx[FIRST_MAX + k * NEXT_MAX: FIRST_MAX + (k + 1) * NEXT_MAX], False)

    # ---------- 3-4 introdução ----------
    s = clone(orig[3])
    add(s)
    DIVS.append(s)
    s = clone(orig[4])
    box = S(s, 102)
    bp = pars(box)
    body_proto = copy.deepcopy(bp[3])
    base_run = copy.deepcopy(runs_of(bp[3])[0])
    keep = [bp[0], bp[2]]
    for p in bp:
        if p not in keep:
            box.text_frame._txBody.remove(p)
    intro = spec.get("introducao", [])
    for t in intro:
        p = copy.deepcopy(body_proto)
        make_runs(p, segments(t), base_run)
        box.text_frame._txBody.append(p)
    chrome(s, "Introdução")
    add(s)

    # ---------- 5 divisória 2 + páginas explicativas ----------
    s = clone(orig[8])
    set_par_text(pars(S(s, 141))[0], "2.")
    set_par_text(pars(S(s, 140))[0], "Descrição dos Cargos")
    add(s)
    DIVS.append(s)

    s = clone(orig[10])      # Missão / Funções
    fill_box(S(s, 163), ["\"A missão do cargo indica, essencialmente, o que a empresa espera deste colaborador e quais os resultados que ele deve entregar dentro de suas atividades.\""])
    fill_box(S(s, 164), ["Conjunto de atividades que, diante de habilidades requisitadas, são responsabilidade do cargo, vistas como atribuições a serem realizadas durante a rotina."], proto=1, keep=1)
    chrome(s, "Descrição do Cargo")
    add(s)

    s = clone(orig[11])      # Rotinas
    place_pairs(s, [(S(s, 178), S(s, 179), "Diariamente", ["Atividades realizadas todos os dias."]),
                    (S(s, 184), S(s, 185), "Semanalmente", ["Atividades realizadas com frequência semanal."]),
                    (S(s, 180), S(s, 181), "Mensalmente", ["Atividades realizadas com frequência mensal."]),
                    (S(s, 182), S(s, 183), "Sob demanda", ["Atividades sem periodicidade específica, realizadas somente quando surge uma demanda."])], 2.3, xs=(0.58, 2.2))
    chrome(s, "Descrição das Atividades")
    add(s)

    s = clone(orig[12])
    chrome(s, "Especificações do Cargo")
    add(s)
    s = clone(orig[13])
    chrome(s, "Especificações do Cargo")
    add(s)

    # ---------- INSERIR ORGANOGRAMA (MODO COMPLETO) ----------
    # Posição exata: depois das 4 páginas explicativas (orig[10-13]), antes da divisória 3
    # "Cargos". Criado e adicionado a `built` AQUI, na ordem natural de construção -- nunca
    # reordenar _sldIdLst depois (add_slide() já apendoa no lugar certo porque chamamos no
    # momento certo da sequência; reordenar depois corrompe a alocação de nomes de parte do
    # python-pptx, ver organograma_slide.py).
    if MODE != "cargo":
        from server.generator.organograma_slide import inserir_slide_organograma
        estrutura = spec.get("estrutura", [])
        organo_slide = inserir_slide_organograma(prs, estrutura, BRAND, None)
        if organo_slide is not None:
            add(organo_slide, "organograma")

    # ---------- divisória 3 Cargos ----------
    s = clone(orig[14])
    set_par_text(pars(S(s, 231))[0], "3.")
    set_par_text(pars(S(s, 230))[0], "Cargos")
    add(s)
    DIVS.append(s)

    # ---------- cargos ----------
    def cargo_divider(num, name):
        s = clone(orig[14])
        n = S(s, 231)
        rs = runs_of(pars(n)[0])
        set_run(rs[0], num)
        for r in rs[1:]:
            pars(n)[0].remove(r)
        n.width = Inches(1.15)
        n.text_frame._txBody.find(qn("a:bodyPr")).set("wrap", "none")      # o número nunca quebra em duas linhas
        for r in runs_of(pars(n)[0]):
            rPr = r.find(qn("a:rPr"))
            if rPr is not None:
                rPr.set("sz", "3200" if len(num) <= 3 else "2400")          # "3.10" e "3.XX" cabem na caixa
        t = S(s, 230)
        set_par_text(pars(t)[0], name)
        if len(name) > 18:
            for r in runs_of(pars(t)[0]):
                r.find(qn("a:rPr")).set("sz", "2800")
        t.left = Inches(1.6)
        t.width = Inches(2.15)
        t.height = Inches(2.6)
        t.top = n.top + n.height - t.height
        t.text_frame.vertical_anchor = MSO_ANCHOR.BOTTOM
        return s

    FRONT_N = len(built)      # slides antes dos cargos (usado no modo "cargo")
    for ci, c in enumerate(CARGOS):
        _d = cargo_divider(c["n"], c["nome"])
        add(_d)
        DIVS.append(_d)

        s = clone(orig[10])
        fill_box(S(s, 163), ["\"%s\"" % c["missao"]])
        fill_box(S(s, 164), c["funcoes"], proto=1, keep=1)
        chrome(s, "Descrição do Cargo")
        add(s, (ci, "desc"))

        s = clone(orig[11])
        r = c["rotinas"]
        order = [(178, 179), (184, 185), (180, 181), (182, 183)]
        place_pairs(s, [(S(s, l), S(s, t), per, items) for (l, t), (per, items) in zip(order, r)], 2.3, xs=(0.58, 2.2))
        chrome(s, "Descrição das Atividades")
        add(s, (ci, "ativ"))

        s = clone(orig[12])
        place_pairs(s, [(S(s, 197), S(s, 195), "Formação acadêmica", c["formacao"]),
                        (S(s, 199), S(s, 198), "Experiência profissional", c["experiencia"]),
                        (S(s, 201), S(s, 200), "Habilidades", c["habilidades"]),
                        (S(s, 203), S(s, 202), "Competências", c["competencias"])], 2.5, size=11)
        chrome(s, "Especificações do Cargo")
        add(s, (ci, "espec"))

        s = clone(orig[13])
        place_pairs(s, [(S(s, 216), S(s, 215), "Relacionamentos", c["relacionamentos"]),
                        (S(s, 218), S(s, 217), "Autonomia", c["autonomia"]),
                        (S(s, 220), S(s, 219), "Supervisão exercida", c["supervisao"]),
                        (S(s, 224), S(s, 225), "Processos", c["processos"])], 2.6, size=11)
        chrome(s, "Especificações do Cargo")
        add(s, (ci, "rel"))

    # ---------- última página ----------
    s = clone(orig[15])
    box = S(s, 241)
    fill_box(box, EMAILS, proto=0, keep=0)
    box.height = Inches(1.8)
    add(s)

    # ---------- remove os slides originais do T2 ----------
    lst = prs.slides._sldIdLst
    ids = list(lst)
    drop = ids[:len(orig)]
    if MODE == "cargo":      # tira capa, sumário, introdução, divisórias e a última página
        new_ids = ids[len(orig):]
        drop += new_ids[:FRONT_N] + new_ids[-1:]
        keep_idx = set(range(FRONT_N, len(built) - 1))
        built = [b for i, b in enumerate(built) if i in keep_idx]
    for sid in drop:
        prs.part.drop_rel(sid.rId)
        lst.remove(sid)

    final = list(prs.slides)
    assert len(final) == len(built), (len(final), len(built))

    # ---------- paleta: cor do cliente + cor secundária + elementos do Grupo Gestão ----------
    _r, _g, _b = [int(BRAND[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    _h, _l, _s = colorsys.rgb_to_hls(_r, _g, _b)
    _nr, _ng, _nb = colorsys.hls_to_rgb((_h + 0.5) % 1.0, 0.17, 0.45)     # complementar, bem escura
    SECOND = "%02X%02X%02X" % (round(_nr * 255), round(_ng * 255), round(_nb * 255))
    NUM = re.compile(r"^\s*\d+(\.\d+)*\.?\s*$")
    A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"

    INK = "1A1A1A"

    def _lum(h):
        def c(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * c(int(h[0:2], 16)) + 0.7152 * c(int(h[2:4], 16)) + 0.0722 * c(int(h[4:6], 16))

    def _contrast(a, b):
        la, lb = _lum(a), _lum(b)
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    def pick_text(bg):
        """branco ou preto, o que tiver mais contraste com o fundo"""
        return "FFFFFF" if _contrast("FFFFFF", bg) >= _contrast(INK, bg) else INK

    TITLES = {"sumário", "introdução", "descrição do cargo", "descrição das atividades", "especificações do cargo"}

    def norm(s):
        return re.sub(r"\s+", " ", s).strip().lower()

    def recolor_roles(slide):
        """roxo do T2 -> títulos grandes de página na cor do cliente; títulos de divisória em preto; rótulos na cor secundária;
        números, marcadores, setas e fundos na cor do cliente"""
        for clr in list(slide._element.iter(A + "srgbClr")):
            if clr.get("val", "").upper() != T2_PURPLE:
                continue
            owner = clr.getparent().getparent() if clr.getparent() is not None else None
            if owner is not None and owner.tag in (A + "rPr", A + "endParaRPr", A + "defRPr"):
                run = owner.getparent()
                txt, ptxt = "", ""
                if run is not None and run.tag == A + "r":
                    t = run.find(A + "t")
                    txt = t.text if t is not None and t.text else ""
                    para = run.getparent()
                    ptxt = "".join((x.text or "") for x in para.iter(A + "t")) if para is not None else ""
                if owner.get("sz") in ("3200", "2800"):
                    clr.set("val", INK)
                elif norm(ptxt) in TITLES:
                    clr.set("val", BRAND)
                elif NUM.match(txt):
                    clr.set("val", BRAND)
                else:
                    clr.set("val", pick_text("F2F2F2"))
            else:
                clr.set("val", BRAND)

    for sl in final:
        recolor_roles(sl)
    # ---------- divisórias: fundo na cor do cliente, alternando com um tom mais escuro da mesma cor ----------
    def darken(hexc, f=0.5):
        r, g, b = [int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        h, l, s_ = colorsys.rgb_to_hls(r, g, b)
        r, g, b = colorsys.hls_to_rgb(h, l * f, s_)
        return "%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))

    DARK = darken(BRAND)
    _in_final = {sl.part for sl in final}

    def tinted_seal(color):
        im = Image.open(SEAL).convert("RGBA")
        rgb = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
        px = im.load()
        for y in range(im.height):
            for x in range(im.width):
                a = px[x, y][3]
                if a:
                    px[x, y] = rgb + (a,)
        out = io.BytesIO()
        im.save(out, "PNG")
        return out.getvalue()

    for k, d in enumerate([x for x in DIVS if x.part in _in_final]):
        bg = BRAND if k % 2 == 0 else DARK
        tc = pick_text(bg)
        for clr in d._element.iter(A + "srgbClr"):                      # setas, número e título: cor contrastante
            if clr.get("val", "").upper() in (BRAND, INK):
                clr.set("val", tc)
        for sh in d.shapes:                                             # selo circular na mesma cor contrastante
            if sh.shape_type == 13:
                _, rid = d.part.get_or_add_image_part(io.BytesIO(tinted_seal(tc)))
                sh._element.find(".//" + A + "blip").set(qn("r:embed"), rid)
        d.background.fill.solid()
        d.background.fill.fore_color.rgb = RGBColor.from_string(bg)

    if MODE != "cargo":
        for para in S(final[0], 57).text_frame.paragraphs:      # título da capa: cor secundária sobre o fundo da marca
            for run in para.runs:
                run.font.color.rgb = RGBColor.from_string(pick_text(BRAND))

    # ---------- Trocar entrada/saída de arquivo para BytesIO (CONTRATOS_FASE2.md §0) ----------
    buffer_tmp = io.BytesIO()
    prs.save(buffer_tmp)

    # ---------- layouts, mestres e tema: cor do cliente; selo e "g6" do Grupo Gestao em tons neutros ----------
    zsrc = zipfile.ZipFile(T2)
    def md5(b): return hashlib.md5(b).hexdigest()
    seal_hash = md5(zsrc.read("ppt/media/image2.png"))
    g6_hash = md5(zsrc.read("ppt/media/image3.png"))
    SEAL_NEUTRAL = open(SEAL, "rb").read()

    def purple_to_dark(data):
        im = Image.open(io.BytesIO(data)).convert("RGBA")
        px = im.load()
        for y in range(im.height):
            for x in range(im.width):
                r, g, b, al = px[x, y]
                if al and b > r + 40 and b > g + 40:
                    px[x, y] = (50, 50, 50, al)
        out = io.BytesIO()
        im.save(out, "PNG")
        return out.getvalue()

    pat = re.compile(T2_PURPLE.encode(), re.I)
    buffer_tmp.seek(0)
    zin = zipfile.ZipFile(buffer_tmp)
    buffer_final = io.BytesIO()
    zout = zipfile.ZipFile(buffer_final, "w", zipfile.ZIP_DEFLATED)
    swapped = 0
    for item in zin.infolist():
        data = zin.read(item.filename)
        n = item.filename
        if n.startswith(("ppt/slideLayouts/", "ppt/slideMasters/", "ppt/theme/")) and n.endswith((".xml", ".rels")):
            data = pat.sub(BRAND.encode(), data)
        if n.startswith("ppt/media/"):
            h = md5(data)
            if h == seal_hash:
                data = SEAL_NEUTRAL
                swapped += 1
            elif h == g6_hash:
                data = purple_to_dark(data)
                swapped += 1
        zout.writestr(item, data)
    zout.close()
    zin.close()

    buffer_final.seek(0)
    return buffer_final


def gerar_slide_cargo(spec: dict) -> io.BytesIO:
    """spec já no modo "cargo" (de spec_builder.construir_spec_um_cargo). Devolve BytesIO do
    .pptx de exatamente 5 páginas (divisória + Descrição do cargo + Atividades + Especificações +
    Relações internas), SEM organograma (regra do Modo B -- CONTRATOS_FASE2.md / prompt §1.1)."""
    return _gerar(spec)


def gerar_manual_completo(spec: dict) -> io.BytesIO:
    """spec no modo "completo" (de spec_builder.construir_spec_manual, deve incluir
    spec["estrutura"] para o organograma). Devolve BytesIO do .pptx institucional inteiro: capa,
    sumário, introdução, descrição dos cargos (4 páginas explicativas + organograma), cargos
    publicados (5 páginas cada), contra-capa com e-mails. COM o slide de organograma (regra do
    Modo A -- CONTRATOS_FASE2.md §8, prompt §1.2)."""
    return _gerar(spec)
