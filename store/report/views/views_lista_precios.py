"""
Vista para generar lista de precios en PDF
"""
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from inventory.models import Products, Category
from io import BytesIO
from django.conf import settings
import os


@login_required
def lista_precios_form(request):
    """Formulario para configurar lista de precios"""
    from ..forms import ListaPreciosForm
    
    if request.method == 'POST':
        form = ListaPreciosForm(request.POST)
        if form.is_valid():
            # Generar PDF
            return generar_pdf_lista_precios(request, form.cleaned_data)
    else:
        form = ListaPreciosForm()
    
    context = {
        'page_title': 'Generar Lista de Precios',
        'form': form,
    }
    return render(request, 'report/lista_precios_form.html', context)


def generar_pdf_lista_precios(request, filtros):
    """Genera PDF de lista de precios según filtros"""
    
    # Crear respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="lista_precios_{filtros["tipo_lista"]}.pdf"'
    
    # Crear buffer
    buffer = BytesIO()
    
    # Crear documento PDF
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # Contenedor de elementos
    elements = []
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # ===== ENCABEZADO =====
    # Logo y contacto en tabla
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.jpg')
    
    header_data = []
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=4*cm, height=4*cm)
        contacto_text = f"""
        <b>CONTACTO</b><br/>
        {filtros['nombre_contacto']}<br/>
        Tel: {filtros['telefono_contacto']}
        """
        contacto = Paragraph(contacto_text, styles['Normal'])
        header_data = [[logo, contacto]]
    else:
        # Sin logo
        contacto_text = f"""
        <b>CONTACTO</b><br/>
        {filtros['nombre_contacto']}<br/>
        Tel: {filtros['telefono_contacto']}
        """
        contacto = Paragraph(contacto_text, styles['Normal'])
        header_data = [[contacto]]
    
    header_table = Table(header_data, colWidths=[5*cm, 12*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 1*cm))
    
    # ===== TÍTULO =====
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2c3e50'),
        alignment=TA_CENTER,
        spaceAfter=20
    )
    title = Paragraph('LISTA DE PRECIOS', title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.5*cm))
    
    # ===== FILTRAR PRODUCTOS =====
    productos = Products.objects.filter(status=1)
    
    # Filtro por stock
    if filtros['stock'] == 'con_stock':
        productos = productos.filter(quantity__gt=0)
    
    # Filtro por categorías
    if filtros.get('categorias'):
        productos = productos.filter(category__in=filtros['categorias'])
    
    # Ordenar
    productos = productos.order_by('category__name', 'name')
    
    # ===== TABLA DE PRODUCTOS =====
    # Encabezados
    data = [['PRODUCTO', 'MARCA', 'PRECIO']]
    
    # Datos
    for producto in productos:
        if filtros['tipo_lista'] == 'minorista':
            precio = f"$ {producto.precio_minorista:,.2f}".replace(',', '.')
        else:
            precio = f"$ {producto.precio_mayorista:,.2f}".replace(',', '.')
        
        marca = producto.category.name if producto.category else '-'
        
        data.append([
            producto.name,
            marca,
            precio
        ])
    
    # Crear tabla
    tabla = Table(data, colWidths=[10*cm, 4*cm, 3*cm])
    
    # Estilo de tabla
    tabla.setStyle(TableStyle([
        # Encabezado (fondo negro, letras blancas)
        ('BACKGROUND', (0, 0), (-1, 0), colors.black),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        
        # Datos
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),      # Producto
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),    # Marca
        ('ALIGN', (2, 1), (2, -1), 'RIGHT'),     # Precio
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Bordes
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        
        # Alternancia de colores
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        
        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    
    elements.append(tabla)
    
    # ===== PIE DE PÁGINA =====
    elements.append(Spacer(1, 1*cm))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    
    from datetime import datetime
    fecha = datetime.now().strftime('%d/%m/%Y %H:%M')
    footer = Paragraph(f'Lista generada el {fecha} | Total productos: {len(data)-1}', footer_style)
    elements.append(footer)
    
    # Construir PDF
    doc.build(elements)
    
    # Obtener PDF del buffer
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response
