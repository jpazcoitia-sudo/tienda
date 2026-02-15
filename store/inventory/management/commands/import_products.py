"""
Comando Django para importar productos desde Excel/CSV

Uso:
    python manage.py import_products archivo.csv
    python manage.py import_products archivo.xlsx
"""

from django.core.management.base import BaseCommand
from inventory.models import Products, Category
from decimal import Decimal
import csv
import os


class Command(BaseCommand):
    help = 'Importa productos desde un archivo CSV o Excel'

    def add_arguments(self, parser):
        parser.add_argument('archivo', type=str, help='Ruta al archivo CSV/Excel')
        parser.add_argument(
            '--actualizar',
            action='store_true',
            help='Actualizar productos existentes por nombre'
        )

    def handle(self, *args, **options):
        archivo = options['archivo']
        actualizar = options.get('actualizar', False)

        if not os.path.exists(archivo):
            self.stdout.write(self.style.ERROR(f'El archivo {archivo} no existe'))
            return

        # Determinar formato
        if archivo.endswith('.csv'):
            productos = self.leer_csv(archivo)
        elif archivo.endswith('.xlsx'):
            productos = self.leer_excel(archivo)
        else:
            self.stdout.write(self.style.ERROR('Solo se soportan archivos .csv y .xlsx'))
            return

        # Procesar productos
        creados = 0
        actualizados = 0
        errores = 0

        for row_num, producto_data in enumerate(productos, start=2):
            try:
                resultado = self.crear_o_actualizar_producto(producto_data, actualizar)
                if resultado == 'creado':
                    creados += 1
                    self.stdout.write(f"✅ Fila {row_num}: {producto_data['nombre']} creado")
                elif resultado == 'actualizado':
                    actualizados += 1
                    self.stdout.write(f"🔄 Fila {row_num}: {producto_data['nombre']} actualizado")
                else:
                    self.stdout.write(f"⏭️  Fila {row_num}: {producto_data['nombre']} ya existe (usar --actualizar)")
            except Exception as e:
                errores += 1
                self.stdout.write(self.style.ERROR(f"❌ Fila {row_num}: Error - {str(e)}"))

        # Resumen
        self.stdout.write(self.style.SUCCESS('\n=== RESUMEN ==='))
        self.stdout.write(self.style.SUCCESS(f'✅ Creados: {creados}'))
        if actualizar:
            self.stdout.write(self.style.SUCCESS(f'🔄 Actualizados: {actualizados}'))
        self.stdout.write(self.style.ERROR(f'❌ Errores: {errores}'))
        self.stdout.write(self.style.SUCCESS(f'📊 Total procesados: {creados + actualizados + errores}'))

    def leer_csv(self, archivo):
        """Lee archivo CSV y retorna lista de productos"""
        productos = []
        
        with open(archivo, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Aceptar columnas con y sin tildes
                categoria = row.get('Categoría', row.get('Categoria', '')).strip()
                nombre = row.get('Nombre Producto', '').strip()
                costo = row.get('Costo', '0').strip()
                cantidad = row.get('Cantidad', '0').strip()
                porc_min = row.get('% Minorista', '0').strip()
                porc_may = row.get('% Mayorista', '0').strip()
                desc = row.get('Descripción', row.get('Descripcion', '')).strip()
                
                productos.append({
                    'categoria': categoria,
                    'nombre': nombre,
                    'costo': costo,
                    'cantidad': cantidad,
                    'porcentaje_minorista': porc_min,
                    'porcentaje_mayorista': porc_may,
                    'descripcion': desc,
                })
        
        return productos

    def leer_excel(self, archivo):
        """Lee archivo Excel y retorna lista de productos"""
        try:
            import openpyxl
        except ImportError:
            self.stdout.write(self.style.ERROR(
                'Para leer archivos Excel instala: pip install openpyxl --break-system-packages'
            ))
            return []

        productos = []
        wb = openpyxl.load_workbook(archivo)
        ws = wb.active

        # Leer encabezados
        headers = [cell.value for cell in ws[1]]

        # Leer datos
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(row):  # Saltar filas vacías
                continue
            
            data = dict(zip(headers, row))
            
            # Aceptar columnas con y sin tildes
            categoria = str(data.get('Categoría', data.get('Categoria', ''))).strip()
            nombre = str(data.get('Nombre Producto', '')).strip()
            costo = str(data.get('Costo', '0')).strip()
            cantidad = str(data.get('Cantidad', '0')).strip()
            porc_min = str(data.get('% Minorista', '0')).strip()
            porc_may = str(data.get('% Mayorista', '0')).strip()
            desc = str(data.get('Descripción', data.get('Descripcion', ''))).strip()
            
            productos.append({
                'categoria': categoria,
                'nombre': nombre,
                'costo': costo,
                'cantidad': cantidad,
                'porcentaje_minorista': porc_min,
                'porcentaje_mayorista': porc_may,
                'descripcion': desc,
            })

        return productos

    def crear_o_actualizar_producto(self, data, actualizar=False):
        """Crea o actualiza un producto"""
        
        # Validar datos obligatorios
        if not data['nombre']:
            raise ValueError('Nombre de producto es obligatorio')
        if not data['categoria']:
            raise ValueError('Categoría es obligatoria')

        # Obtener o crear categoría
        categoria, _ = Category.objects.get_or_create(
            name=data['categoria'],
            defaults={'status': 1}
        )

        # Calcular precios
        costo = Decimal(data['costo'].replace(',', '.'))
        porc_minorista = Decimal(data['porcentaje_minorista'].replace(',', '.'))
        porc_mayorista = Decimal(data['porcentaje_mayorista'].replace(',', '.'))
        
        precio_minorista = costo * (1 + porc_minorista / 100)
        precio_mayorista = costo * (1 + porc_mayorista / 100)
        
        cantidad = int(float(data['cantidad'].replace(',', '.')))

        # Verificar si existe
        producto_existente = Products.objects.filter(name=data['nombre']).first()

        if producto_existente:
            if actualizar:
                # Actualizar
                producto_existente.category = categoria
                producto_existente.cost = costo
                producto_existente.precio_minorista = precio_minorista
                producto_existente.precio_mayorista = precio_mayorista
                producto_existente.quantity = cantidad
                producto_existente.description = data.get('descripcion', '')
                producto_existente.save()
                return 'actualizado'
            else:
                return 'existe'
        else:
            # Generar código único
            import random
            import string
            while True:
                codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                if not Products.objects.filter(code=codigo).exists():
                    break
            
            # Crear nuevo
            Products.objects.create(
                code=codigo,
                category=categoria,
                name=data['nombre'],
                cost=costo,
                precio_minorista=precio_minorista,
                precio_mayorista=precio_mayorista,
                quantity=cantidad,
                description=data.get('descripcion', ''),
                status=1
            )
            return 'creado'
