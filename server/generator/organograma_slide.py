"""
Gera o slide de organograma do Modo A (manual completo) usando formas geométricas do
python-pptx -- NÃO existe no template T2 original (a skill não gera organograma, ver
references/padrao-visual.md: "Organograma: fora do escopo" -- isso é uma extensão desta Fase 2,
autorizada explicitamente pelo prompt da Fase 2, seção 1.2 "Regra Especial").

Ver docs/CONTRATOS_FASE2.md §8 para a posição exata do slide no deck e o ajuste da numeração do
sumário que a inserção exige.
"""
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import colorsys


def _pick_text(bg_hex: str) -> str:
    """Escolhe branco ou preto para o texto conforme o contraste com o fundo."""
    def lum(h):
        def c(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * c(int(h[0:2], 16)) + 0.7152 * c(int(h[2:4], 16)) + 0.0722 * c(int(h[4:6], 16))

    def contrast(a, b):
        la, lb = lum(a), lum(b)
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    INK = "1A1A1A"
    return "FFFFFF" if contrast("FFFFFF", bg_hex) >= contrast(INK, bg_hex) else INK


def _darken(hexc: str, f=0.5) -> str:
    """Calcula tom mais escuro de uma cor (usada se dark_hex não for fornecido)."""
    r, g, b = [int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    h, l, s_ = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb(h, l * f, s_)
    return "%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def inserir_slide_organograma(prs, estrutura: list, brand_hex: str, dark_hex: str):
    """Cria UM slide novo (via prs.slides.add_slide, que sempre anexa ao FINAL da lista de
    slides) e devolve o objeto slide criado, para quem chamar fazer `add(slide, ...)` na mesma
    sequência das outras páginas (ver CONTRATOS_FASE2.md §8). NÃO reordena `_sldIdLst` aqui:
    quem chama DEVE invocar esta função no ponto exato da sequência de clonagem (logo depois das
    4 páginas explicativas de "Descrição dos Cargos" e antes da divisória "Cargos") -- mover o
    slide depois de criado, via remoção/inserção manual em `_sldIdLst`, corrompe a alocação de
    nomes de parte do python-pptx (gera dois slides com o mesmo nome físico no .pptx final).

    `estrutura`: lista de dicts {id, nome, area, nivel, pai} -- mesmo formato de
    retrato_().estrutura da Fase 1 (server/modelo.py). `nivel` 1 = topo.

    Desenho (formas python-pptx, sem template):
    - Um retângulo (pptx.util.Inches + shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, ...)) por
      cargo, com o nome do cargo (e, se couber, a área) como texto.
    - Posição: organizar por nível (nivel 1 no topo, crescendo para baixo) e, dentro do mesmo
      nível, agrupar por área lado a lado -- um layout simples em grade já resolve (não precisa de
      algoritmo de layout de árvore sofisticado; dado o volume de cargos típico de uma PME, uma
      grade por nível com os cargos de cada 'pai' centralizados abaixo dele já comunica a hierarquia).
    - Cor de fundo dos retângulos: `brand_hex` para nível 1, `dark_hex` para os demais níveis (ou
      alternando por nível) -- reaproveitar a MESMA paleta já calculada pelo slide_engine (cor do
      cliente + tom escuro), não introduzir nenhuma cor nova (mesma regra de padrao-visual.md para
      as divisórias). Cor do texto: branco ou preto, o que tiver mais contraste (replicar a lógica
      de `pick_text()` do build_manual.py original -- pode importar/duplicar essa função aqui, é
      pequena e autocontida).
    - Linhas de reporte: um conector (shapes.add_connector ou uma linha reta) de cada cargo até o
      seu `pai` (quando houver), na cor neutra (cinza escuro, não a cor do cliente -- as linhas são
      estrutura, não destaque).
    - Título do slide: "Organograma" (mesmo estilo de cabeçalho que `chrome()`/`set_header()` usa
      nas outras páginas do slide_engine -- se for mais simples, um TextBox simples com o mesmo
      tamanho/posição do cabeçalho das demais páginas já é suficiente; não precisa reusar a função
      `chrome()` literalmente se isso acoplar demais este módulo ao slide_engine).

    Não precisa ser bonito como o InDesign de um designer: precisa ser CORRETO (toda ligação
    pai->filho desenhada, nenhum cargo faltando, texto legível) e usar só a paleta de cores já
    definida. Mantenha os objetos do python-pptx simples (retângulos + linhas + texto) -- nada de
    imagem renderizada externamente."""

    if not estrutura:
        return None

    # Se dark_hex não foi fornecido, calcula a partir de brand_hex
    if dark_hex is None:
        dark_hex = _darken(brand_hex)

    # Cria um novo slide em branco na posição especificada
    blank_layout = prs.slide_layouts[6]  # Blank layout
    slide = prs.slides.add_slide(blank_layout)

    # Adiciona título "Organograma" no topo
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.5))
    title_frame = title_box.text_frame
    title_frame.text = "Organograma"
    title_para = title_frame.paragraphs[0]
    title_para.font.bold = True
    title_para.font.size = Pt(32)
    title_para.font.color.rgb = RGBColor.from_string(brand_hex)

    # Agrupa cargos por nível
    cargos_por_nivel = {}
    por_id = {c["id"]: c for c in estrutura}
    for cargo in estrutura:
        nivel = cargo.get("nivel", 1)
        if nivel not in cargos_por_nivel:
            cargos_por_nivel[nivel] = []
        cargos_por_nivel[nivel].append(cargo)

    # Layout: coloca cada nível em uma linha, com margin/spacing
    nivel_y = {}
    y_pos = Inches(1.2)
    padding = Inches(0.1)
    item_height = Inches(0.8)
    item_width = Inches(2.0)
    line_height = Inches(1.2)

    # Guarda posição (center_x, center_y) de cada cargo para desenhar linhas depois
    cargo_positions = {}

    for nivel in sorted(cargos_por_nivel.keys()):
        nivel_y[nivel] = y_pos
        cargos_neste_nivel = cargos_por_nivel[nivel]

        # Distribuir cargos horizontalmente com espaço igual
        total_width = len(cargos_neste_nivel) * item_width
        start_x = (Inches(10) - total_width) / 2  # Centralizar na página
        if start_x < Inches(0.5):
            start_x = Inches(0.5)

        for idx, cargo in enumerate(cargos_neste_nivel):
            x_pos = start_x + idx * item_width
            cargo_id = cargo["id"]

            # Cor: brand para nível 1, dark para demais
            if nivel == 1:
                box_color = brand_hex
            else:
                box_color = dark_hex
            text_color = _pick_text(box_color)

            # Adiciona retângulo
            shape = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                x_pos, y_pos, item_width, item_height
            )
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor.from_string(box_color)
            shape.line.color.rgb = RGBColor.from_string("CCCCCC")

            # Adiciona texto (nome do cargo)
            text_frame = shape.text_frame
            text_frame.word_wrap = True
            p = text_frame.paragraphs[0]
            p.text = cargo.get("nome", "")
            p.font.size = Pt(9)
            p.font.bold = True
            p.font.color.rgb = RGBColor.from_string(text_color)
            p.alignment = PP_ALIGN.CENTER

            # Vertically center the text
            text_frame.vertical_anchor = 1  # MSO_ANCHOR.MIDDLE

            # Guarda posição para desenhar linhas
            center_x = x_pos + item_width / 2
            center_y = y_pos + item_height / 2
            cargo_positions[cargo_id] = (center_x, center_y)

        y_pos += line_height

    # Desenha linhas de reporte (pai -> filho)
    LINE_COLOR = "999999"  # Cinza escuro neutro
    for cargo in estrutura:
        cargo_id = cargo["id"]
        pai_id = cargo.get("pai")

        if not pai_id or cargo_id not in cargo_positions or pai_id not in cargo_positions:
            continue

        # Posição do cargo (filho) e do pai
        x1, y1 = cargo_positions[cargo_id]
        x2, y2 = cargo_positions[pai_id]

        # Desenha uma linha vertical simples: sobe do filho até o meio, depois vai para o pai
        connector = slide.shapes.add_connector(1, x1, y1, x2, y2)  # 1 = linha reta
        connector.line.color.rgb = RGBColor.from_string(LINE_COLOR)
        connector.line.width = Pt(1)

    return slide
