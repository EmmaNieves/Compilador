"""
pdf_exporter.py - Exportacion de analisis a PDF
Usa ReportLab para generar documentos PDF con la tabla de tokens y el arbol AST.
"""

import os
from datetime import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, Image, PageBreak)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


class ExportadorPDF:
    """Genera archivos PDF con los resultados del analisis."""

    # Colores del documento
    COLOR_HEADER    = colors.HexColor('#2E4057')
    COLOR_ACENTO    = colors.HexColor('#048A81')
    COLOR_FILA_PAR  = colors.HexColor('#F8F9FA')
    COLOR_ERROR_BG  = colors.HexColor('#F8D7DA')

    def __init__(self):
        self.estilos = getSampleStyleSheet()
        self._init_estilos()

    def _init_estilos(self):
        """Configura los estilos de parrafo del documento."""
        self.s_titulo = ParagraphStyle(
            'Titulo', parent=self.estilos['Title'],
            fontSize=18, textColor=self.COLOR_HEADER,
            spaceAfter=6, alignment=TA_CENTER, fontName='Helvetica-Bold'
        )
        self.s_subtitulo = ParagraphStyle(
            'Subtitulo', parent=self.estilos['Heading2'],
            fontSize=13, textColor=self.COLOR_ACENTO,
            spaceBefore=12, spaceAfter=6, fontName='Helvetica-Bold'
        )
        self.s_normal = ParagraphStyle(
            'Normal2', parent=self.estilos['Normal'],
            fontSize=9, fontName='Helvetica'
        )
        self.s_codigo = ParagraphStyle(
            'Codigo', parent=self.estilos['Code'],
            fontSize=8, fontName='Courier',
            backColor=colors.HexColor('#F4F4F4'),
            leftIndent=10
        )

    def _encabezado(self, titulo, codigo):
        """Genera la seccion de encabezado del PDF."""
        elems = []
        elems.append(Paragraph('Analizador Lexico y Sintactico', self.s_titulo))
        elems.append(Paragraph(titulo, self.s_subtitulo))
        fecha = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        elems.append(Paragraph('Generado el: ' + fecha, self.s_normal))
        elems.append(Spacer(1, 0.3 * cm))
        elems.append(Paragraph('Codigo analizado:', self.s_subtitulo))
        for linea in codigo.split('\n'):
            texto = linea if linea.strip() else ' '
            texto = texto.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            elems.append(Paragraph(texto, self.s_codigo))
        elems.append(Spacer(1, 0.5 * cm))
        return elems

    def _estilo_tabla(self, num_filas):
        """Retorna el estilo para la tabla de tokens."""
        estilo = [
            ('BACKGROUND',    (0, 0), (-1, 0),  self.COLOR_HEADER),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
            ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, 0),  9),
            ('ALIGN',         (0, 0), (-1, 0),  'CENTER'),
            ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE',      (0, 1), (-1, -1), 8),
            ('ALIGN',         (4, 1), (-1, -1), 'CENTER'),
            ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING',   (0, 0), (-1, -1), 5),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
        ]
        # Filas pares con fondo alternado
        for i in range(2, num_filas, 2):
            estilo.append(('BACKGROUND', (0, i), (-1, i), self.COLOR_FILA_PAR))
        return TableStyle(estilo)

    def exportar_lexico(self, tokens, errores, codigo, ruta_salida):
        """
        Exporta el analisis lexico a PDF como tabla de tokens.
        
        Parametros:
            tokens      : lista de Token
            errores     : lista de errores lexicos
            codigo      : codigo fuente analizado
            ruta_salida : ruta del PDF a crear
        """
        doc = SimpleDocTemplate(
            ruta_salida, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )
        elems = self._encabezado('Analisis Lexico - Tabla de Tokens', codigo)
        elems.append(Paragraph(
            'Total tokens: <b>%d</b>   Errores lexicos: <b>%d</b>' % (len(tokens), len(errores)),
            self.s_normal
        ))
        elems.append(Spacer(1, 0.3 * cm))

        if tokens:
            datos = [['#', 'Token (Valor)', 'Tipo Interno', 'Categoria', 'Linea', 'Col.']]
            for i, t in enumerate(tokens, 1):
                datos.append([str(i), t.valor, t.tipo, t.categoria, str(t.linea), str(t.columna)])
            tabla = Table(datos, colWidths=[1.0*cm, 3.5*cm, 4.5*cm, 4.0*cm, 1.5*cm, 1.5*cm])
            tabla.setStyle(self._estilo_tabla(len(datos)))
            elems.append(tabla)
        else:
            elems.append(Paragraph('No se encontraron tokens.', self.s_normal))

        if errores:
            elems.append(Spacer(1, 0.5 * cm))
            elems.append(Paragraph('Errores Lexicos Detectados', self.s_subtitulo))
            datos_err = [['Caracter', 'Linea', 'Columna', 'Descripcion']]
            for e in errores:
                datos_err.append([e['caracter'], str(e['linea']), str(e['columna']), e['mensaje']])
            tabla_err = Table(datos_err, colWidths=[2*cm, 1.5*cm, 2*cm, 10.5*cm])
            tabla_err.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0),  colors.HexColor('#C0392B')),
                ('TEXTCOLOR',  (0, 0), (-1, 0),  colors.white),
                ('FONTNAME',   (0, 0), (-1, 0),  'Helvetica-Bold'),
                ('FONTSIZE',   (0, 0), (-1, -1), 8),
                ('BACKGROUND', (0, 1), (-1, -1), self.COLOR_ERROR_BG),
                ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
                ('TOPPADDING',    (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING',   (0, 0), (-1, -1), 5),
            ]))
            elems.append(tabla_err)

        doc.build(elems)
        return ruta_salida

    def exportar_sintactico(self, ruta_img, codigo, errores_sint, ruta_salida):
        """
        Exporta el arbol sintactico a PDF como imagen.
        
        Parametros:
            ruta_img     : ruta de la imagen PNG del arbol
            codigo       : codigo fuente analizado
            errores_sint : lista de errores sintacticos
            ruta_salida  : ruta del PDF a crear
        """
        doc = SimpleDocTemplate(
            ruta_salida, pagesize=landscape(A4),
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )
        elems = self._encabezado('Analisis Sintactico - Arbol AST', codigo)

        if ruta_img and os.path.exists(ruta_img):
            elems.append(Paragraph('Arbol de Sintaxis Abstracta:', self.s_subtitulo))
            elems.append(Spacer(1, 0.2 * cm))
            img = Image(ruta_img)
            ancho_max, alto_max = 24*cm, 14*cm
            ratio = img.imageWidth / img.imageHeight
            if img.imageWidth > ancho_max:
                img.drawWidth  = ancho_max
                img.drawHeight = ancho_max / ratio
            if img.drawHeight > alto_max:
                img.drawHeight = alto_max
                img.drawWidth  = alto_max * ratio
            elems.append(img)
        else:
            elems.append(Paragraph('No se pudo generar la imagen del arbol.', self.s_normal))

        if errores_sint:
            elems.append(Spacer(1, 0.5 * cm))
            elems.append(Paragraph('Advertencias Sintacticas:', self.s_subtitulo))
            for e in errores_sint:
                elems.append(Paragraph('- ' + str(e), self.s_normal))

        doc.build(elems)
        return ruta_salida

    def exportar_completo(self, tokens, errores_lex, codigo,
                          ruta_img, errores_sint, ruta_salida):
        """
        Exporta ambos analisis en un solo PDF.
        Pagina 1: tabla de tokens. Pagina 2: arbol AST.
        """
        doc = SimpleDocTemplate(
            ruta_salida, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )
        elems = self._encabezado('Analisis Completo - Lexico y Sintactico', codigo)

        # Tabla de tokens
        elems.append(Paragraph('1. Analisis Lexico', self.s_subtitulo))
        elems.append(Paragraph(
            'Tokens: <b>%d</b>   Errores: <b>%d</b>' % (len(tokens), len(errores_lex)),
            self.s_normal
        ))
        elems.append(Spacer(1, 0.2 * cm))
        if tokens:
            datos = [['#', 'Valor', 'Tipo', 'Categoria', 'L', 'C']]
            for i, t in enumerate(tokens, 1):
                datos.append([str(i), t.valor, t.tipo, t.categoria, str(t.linea), str(t.columna)])
            tabla = Table(datos, colWidths=[0.8*cm, 3*cm, 4*cm, 3.5*cm, 1*cm, 1*cm])
            tabla.setStyle(self._estilo_tabla(len(datos)))
            elems.append(tabla)

        # Arbol AST en nueva pagina
        elems.append(PageBreak())
        elems.append(Paragraph('2. Analisis Sintactico - Arbol AST', self.s_subtitulo))
        if ruta_img and os.path.exists(ruta_img):
            img = Image(ruta_img)
            ancho_max, alto_max = 16*cm, 20*cm
            ratio = img.imageWidth / img.imageHeight
            if img.imageWidth > ancho_max:
                img.drawWidth  = ancho_max
                img.drawHeight = ancho_max / ratio
            if img.drawHeight > alto_max:
                img.drawHeight = alto_max
                img.drawWidth  = alto_max * ratio
            elems.append(img)
        if errores_sint:
            elems.append(Spacer(1, 0.3 * cm))
            for e in errores_sint:
                elems.append(Paragraph('- ' + str(e), self.s_normal))

        doc.build(elems)
        return ruta_salida
