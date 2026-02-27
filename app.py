import os, json, math, base64
from datetime import date
from flask import Flask, request, render_template, send_file, session, jsonify
import anthropic

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "lucky-tour-secret-2024")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# ── TABLAS ──
FEE_TABLE = [
    (0, 599, 25), (600, 999, 30), (1000, 1499, 35),
    (1500, 1999, 40), (2000, 2999, 50), (3000, 3999, 55),
    (4000, 5499, 60), (5500, float('inf'), 80),
]
DESCUENTO_TABLE = [
    (0, 50, 0), (51, 80, 10), (81, 100, 20), (101, 140, 30),
    (141, 180, 40), (181, 220, 50), (221, 260, 60), (261, float('inf'), 70),
]
CONTACTOS = {
    "guido":   {"nombre": "Guido Finkelstein",   "mail": "Guido@luckytourviajes.com",    "tel": "+54 9 11 6846 3892"},
    "julieta": {"nombre": "Julieta Zubeldia",     "mail": "Julietaz@luckytourviajes.com", "tel": "+54 9 11 3295 5404"},
    "ruthy":   {"nombre": "Ruthy Tuchsznajder",   "mail": "Ventas@luckytourviajes.com",   "tel": "+54 9 11 6847 0985"},
}

def get_fee(neto):
    for low, high, fee in FEE_TABLE:
        if low <= neto <= high:
            return fee
    return 80

def get_descuento(comision):
    for low, high, desc in DESCUENTO_TABLE:
        if low <= comision <= high:
            return desc
    return 70

def redondear_arriba(p):
    return int(math.ceil(p / 5) * 5) if p % 5 != 0 else int(p)

def redondear_abajo(p):
    return int(math.floor(p / 5) * 5)

def calcular_precio(neto, tipo_tarifa='PUB', comision_over=0):
    if tipo_tarifa == 'PNEG' or comision_over <= 50:
        return redondear_arriba(neto + get_fee(neto))
    else:
        return redondear_abajo(neto - get_descuento(comision_over))

def armar_linea_precio(precio, tipo, cantidad, total_pasajeros, hay_multiples_tipos):
    if total_pasajeros == 1:
        return f"USD {precio:,}"
    elif not hay_multiples_tipos:
        return f"USD {precio:,} cada {tipo}"
    else:
        return f"USD {precio:,} cada {tipo}" if cantidad > 1 else f"USD {precio:,} {tipo}"

def analizar_capturas_con_claude(imagenes_b64):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    content = []
    for img_b64, media_type in imagenes_b64:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": img_b64}
        })

    content.append({
        "type": "text",
        "text": """Analizá estas capturas de Sabre o Amadeus y extraé los datos de vuelo y tarifas.
Respondé SOLO con un JSON válido con esta estructura exacta, sin texto adicional ni markdown:

{
  "opciones": [
    {
      "aerolinea": "nombre de la aerolínea",
      "vuelos": [
        {
          "fecha": "10/05",
          "origen": "Buenos Aires (EZE)",
          "destino": "Dubai (DXB)",
          "salida": "22.40",
          "llegada": "00.30",
          "numero_vuelo": "EK 0248"
        }
      ],
      "detalle_vuelo": "Económica",
      "pasajeros": [
        {
          "tipo": "adulto",
          "neto": 1562.37,
          "tipo_tarifa": "PNEG",
          "comision_over": 0
        }
      ]
    }
  ]
}

Reglas importantes:
- Cada tramo del vuelo es una entrada separada en "vuelos"
- NUNCA incluir duración del vuelo
- NUNCA poner "Con escala en X" en detalle_vuelo
- El campo "salida" y "llegada" usan punto en vez de dos puntos (ej: 22.40)
- tipo_tarifa es "PUB" o "PNEG"
- comision_over es la suma de comisión + over en USD (número, no string)
- neto es el Total de la tabla de tarifas (número, no string)
- Si hay múltiples opciones de vuelo en las capturas, incluirlas todas
- No incluir "cantidad" de pasajeros (eso lo preguntamos por separado)"""
    })

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": content}]
    )

    texto = response.content[0].text.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    return json.loads(texto.strip())


def generar_pdf_bytes(opciones_vuelo, vendedor, adultos, menores, infantes):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     HRFlowable, Image, Table, TableStyle, PageBreak)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    import io

    NAVY     = colors.HexColor('#1B3A5C')
    LOGO_PATH = os.path.join(os.path.dirname(__file__), 'static', 'logo.png')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
        rightMargin=22*mm, leftMargin=22*mm, topMargin=5*mm, bottomMargin=35*mm)

    fecha_s  = ParagraphStyle('f',   fontName='Helvetica',      fontSize=9,  textColor=colors.HexColor('#666666'), alignment=TA_RIGHT)
    title_s  = ParagraphStyle('t',   fontName='Helvetica-Bold', fontSize=16, textColor=NAVY, alignment=TA_CENTER, spaceAfter=2*mm)
    sec_s    = ParagraphStyle('sec', fontName='Helvetica-Bold', fontSize=9,  textColor=NAVY, spaceBefore=3*mm, spaceAfter=1.5*mm)
    vuelo_s  = ParagraphStyle('v',   fontName='Helvetica-Bold', fontSize=10, textColor=colors.black, spaceAfter=0.5*mm)
    det_s    = ParagraphStyle('d',   fontName='Helvetica',      fontSize=8,  textColor=colors.HexColor('#555555'), spaceAfter=1.5*mm)
    precio_s = ParagraphStyle('p',   fontName='Helvetica-Bold', fontSize=10, textColor=NAVY, spaceAfter=1.5*mm)

    def cabecera():
        elems = [Paragraph(date.today().strftime("%d/%m/%Y"), fecha_s)]
        if os.path.exists(LOGO_PATH):
            img = Image(LOGO_PATH, width=55*mm, height=46*mm)
            img.hAlign = 'CENTER'
            elems.append(img)
        elems.append(Paragraph("Cotización", title_s))
        elems.append(Spacer(1, 2*mm))
        elems.append(HRFlowable(width="100%", thickness=2, color=NAVY, spaceAfter=4*mm))
        return elems

    story = []
    es_multiple = len(opciones_vuelo) > 1

    for i, opcion in enumerate(opciones_vuelo, 1):
        if i > 1:
            story.append(PageBreak())
        story.extend(cabecera())

        vuelos    = opcion['vuelos']
        detalle   = opcion['detalle_vuelo']
        aerolinea = opcion.get('aerolinea', '')

        # Armar pasajeros con cantidades
        pasajeros_raw = opcion['pasajeros']
        pasajeros = []
        cantidades = {"adulto": adultos, "menor": menores, "infante": infantes}
        tipo_map   = {"adulto": "adulto", "niño": "menor", "infante": "infante",
                      "nino": "menor", "menor": "menor"}
        for pax in pasajeros_raw:
            tipo_orig = pax['tipo'].lower()
            tipo_norm = tipo_map.get(tipo_orig, tipo_orig)
            cant = cantidades.get(tipo_norm, 1)
            if cant > 0:
                pasajeros.append({**pax, "tipo": tipo_norm, "cantidad": cant})

        if es_multiple:
            label = Paragraph(f"  OPCIÓN {i}", ParagraphStyle('op', fontName='Helvetica-Bold', fontSize=10, textColor=colors.white))
            t = Table([[label]], colWidths=[155*mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), NAVY),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(t)
            story.append(Spacer(1, 2*mm))

        titulo_itin = f"✈  ITINERARIO - {aerolinea}" if aerolinea else "✈  ITINERARIO"
        story.append(Paragraph(titulo_itin, sec_s))

        for v in vuelos:
            linea = f"<b>{v['fecha']}</b> &nbsp; {v['origen']} → {v['destino']} &nbsp;&nbsp; {v['salida']} → {v['llegada']}"
            story.append(Paragraph(linea, vuelo_s))
            if v.get('numero_vuelo'):
                story.append(Paragraph(v['numero_vuelo'], det_s))

        story.append(Paragraph(detalle, det_s))

        total_pasajeros     = sum(p['cantidad'] for p in pasajeros)
        hay_multiples_tipos = len(pasajeros) > 1
        story.append(Paragraph("💰  PRECIO" if total_pasajeros == 1 else "💰  PRECIOS", sec_s))
        for pax in pasajeros:
            precio = calcular_precio(pax['neto'], pax.get('tipo_tarifa', 'PUB'), pax.get('comision_over', 0))
            story.append(Paragraph(
                armar_linea_precio(precio, pax['tipo'], pax['cantidad'], total_pasajeros, hay_multiples_tipos),
                precio_s))

    contacto = CONTACTOS[vendedor.lower()]
    def footer(canvas, doc):
        canvas.saveState()
        x, y = 22*mm, 18*mm
        canvas.setLineWidth(1.5)
        canvas.setStrokeColor(NAVY)
        canvas.line(x, y + 3*mm, doc.width + x, y + 3*mm)
        canvas.setFont('Helvetica-Bold', 9)
        canvas.setFillColor(NAVY)
        canvas.drawString(x, y, "Contacto:")
        canvas.drawString(x + 55, y, contacto['nombre'])
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.HexColor('#333333'))
        canvas.drawString(x, y - 11, contacto['mail'])
        canvas.drawString(x, y - 22, contacto['tel'])
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analizar", methods=["POST"])
def analizar():
    archivos = request.files.getlist("capturas")
    if not archivos:
        return jsonify({"error": "No se recibieron imágenes"}), 400

    imagenes_b64 = []
    for archivo in archivos:
        datos = archivo.read()
        b64 = base64.standard_b64encode(datos).decode("utf-8")
        media_type = archivo.content_type or "image/jpeg"
        imagenes_b64.append((b64, media_type))

    try:
        resultado = analizar_capturas_con_claude(imagenes_b64)
        session["opciones_vuelo"] = resultado["opciones"]
        return jsonify({"ok": True, "opciones": len(resultado["opciones"])})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/generar", methods=["POST"])
def generar():
    opciones_vuelo = session.get("opciones_vuelo")
    if not opciones_vuelo:
        return jsonify({"error": "No hay datos de vuelo en sesión"}), 400

    vendedor = request.form.get("vendedor", "guido")
    adultos  = int(request.form.get("adultos", 1))
    menores  = int(request.form.get("menores", 0))
    infantes = int(request.form.get("infantes", 0))

    try:
        pdf_buffer = generar_pdf_bytes(opciones_vuelo, vendedor, adultos, menores, infantes)
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="cotizacion_lucky_tour.pdf"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
