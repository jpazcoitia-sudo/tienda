"""
recuperar_borrados — Reconstruye historia que se perdio al eliminar productos.

Hasta el 02/10/2026, eliminar un producto borraba en silencio sus renglones de
venta y dejaba sin producto sus renglones de compra. Este comando los repone a
partir de un plan armado con los backups (tienda-datos/recuperacion/armar_plan.py).

Que hace:
  1. Vuelve a crear los productos borrados, pero como ELIMINADOS (ocultos):
     no aparecen en ningun listado, solo sostienen el historial.
  2. Vuelve a crear los renglones de venta borrados, con su mismo numero.
  3. Vuelve a vincular los renglones de compra que quedaron sin producto.

NO toca stock, costos, precios ni caja de los productos vigentes: escribe
directo en la base, sin pasar por la logica de ventas/compras.

Uso:
    python manage.py recuperar_borrados --archivo plan_recuperacion.json            (solo muestra)
    python manage.py recuperar_borrados --archivo plan_recuperacion.json --aplicar  (lo hace)

Se puede correr mas de una vez: lo que ya esta recuperado se saltea.
"""
import datetime
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from inventory.models import Category, Products
from pos.models import Sales, salesItems
from purchase.models import PurchaseProduct


def convertir(campo, valor):
    """
    Convierte un valor de texto del backup al tipo del campo.
    Las fechas del backup traen zona horaria (ej. "...-03"); este proyecto guarda
    fechas SIN zona (USE_TZ = False), asi que se pasan a hora local.
    """
    if valor is None:
        return None
    v = campo.to_python(valor)
    if isinstance(v, datetime.datetime) and timezone.is_aware(v) and not settings.USE_TZ:
        v = timezone.make_naive(v, timezone.get_default_timezone())
    return v


def ventas_descuadradas():
    """Cantidad de ventas donde los renglones no suman el total (tolerancia $1)."""
    sumas = dict(salesItems.objects.values_list('sale_id').annotate(s=Sum('total')))
    return sum(1 for v in Sales.objects.all() if abs((v.grand_total or 0) - (sumas.get(v.pk) or 0)) > 1)


class Command(BaseCommand):
    help = 'Recupera renglones de venta y vinculos de compra perdidos al eliminar productos.'

    def add_arguments(self, parser):
        parser.add_argument('--archivo', required=True, help='plan_recuperacion.json')
        parser.add_argument('--aplicar', action='store_true', help='Sin esto solo muestra lo que haria.')

    def handle(self, *args, **opciones):
        try:
            with open(opciones['archivo'], encoding='utf-8') as f:
                plan = json.load(f)
        except (OSError, ValueError) as e:
            raise CommandError(f'No se pudo leer el plan: {e}')

        aplicar = opciones['aplicar']
        self.stdout.write(f"Plan generado el {plan.get('generado', '?')}")
        self.stdout.write('MODO: ' + ('APLICAR (modifica la base)' if aplicar else 'SIMULACION (no modifica nada)'))
        antes = ventas_descuadradas()

        with transaction.atomic():
            n_prod, salt_prod = self._productos(plan.get('productos', []))
            n_item, salt_item = self._renglones(plan.get('renglones_venta', []))
            n_link, salt_link = self._vinculos(plan.get('vinculos_compra', []))
            despues = ventas_descuadradas()
            if not aplicar:
                transaction.set_rollback(True)     # simulacion: se deshace todo

        self.stdout.write('')
        self.stdout.write(f'Productos repuestos como eliminados: {n_prod}   (salteados: {len(salt_prod)})')
        self.stdout.write(f'Renglones de venta repuestos:        {n_item}   (salteados: {len(salt_item)})')
        self.stdout.write(f'Renglones de compra re-vinculados:   {n_link}   (salteados: {len(salt_link)})')
        for motivo in salt_prod + salt_item + salt_link:
            self.stdout.write('   salteado: ' + motivo)
        self.stdout.write(f'Ventas donde los renglones no suman el total: {antes} -> {despues}')
        if aplicar:
            self.stdout.write(self.style.SUCCESS('LISTO: cambios guardados.'))
        else:
            self.stdout.write(self.style.WARNING('SIMULACION: no se guardo nada. Agregar --aplicar para hacerlo.'))

    # ------------------------------------------------------------------
    def _productos(self, filas):
        campos = {f.attname: f for f in Products._meta.concrete_fields}
        existentes = set(Products.todos.values_list('pk', flat=True))
        codigos = set(Products.todos.values_list('code', flat=True))
        categorias = set(Category.objects.values_list('pk', flat=True))
        ahora = timezone.now()
        nuevos, salteados = [], []
        for fila in filas:
            pk = int(fila['id'])
            if pk in existentes:
                salteados.append(f"producto {pk} ({fila.get('name')}): ya existe")
                continue
            if fila['code'] in codigos:
                salteados.append(f"producto {pk} ({fila.get('name')}): el codigo {fila['code']} ya esta en uso")
                continue
            datos = {}
            for nombre, valor in fila.items():
                if nombre.startswith('_') or nombre not in campos:
                    continue
                datos[nombre] = convertir(campos[nombre], valor)
            if datos.get('category_id') not in categorias:
                datos['category_id'] = None
            if datos.get('producto_origen_id') not in existentes:
                datos['producto_origen_id'] = None
            # Vuelve oculto: sin codigo de barras ni PLU (pueden estar usados por otro producto)
            datos.update(eliminado=True, fecha_eliminado=ahora, codigo_barras=None, plu=None,
                         status=Products.STATUS_INACTIVE)
            nuevos.append(Products(**datos))
            existentes.add(pk)
            codigos.add(fila['code'])
        # bulk_create NO llama a save(): no recalcula precios ni valida, copia tal cual
        Products.todos.bulk_create(nuevos)
        return len(nuevos), salteados

    def _renglones(self, filas):
        existentes = set(salesItems.objects.values_list('pk', flat=True))
        ventas = set(Sales.objects.values_list('pk', flat=True))
        productos = set(Products.todos.values_list('pk', flat=True))
        campos = {f.attname: f for f in salesItems._meta.concrete_fields}
        nuevos, salteados = [], []
        for fila in filas:
            pk, venta, producto = int(fila['id']), int(fila['sale_id']), int(fila['product_id'])
            if pk in existentes:
                salteados.append(f'renglon de venta {pk}: ya existe')
            elif venta not in ventas:
                salteados.append(f'renglon de venta {pk}: la venta {venta} no existe')
            elif producto not in productos:
                salteados.append(f'renglon de venta {pk}: el producto {producto} no existe')
            else:
                datos = {n: convertir(campos[n], v) for n, v in fila.items() if n in campos}
                nuevos.append(salesItems(**datos))
                existentes.add(pk)
        # bulk_create NO llama a save(): no descuenta stock
        salesItems.objects.bulk_create(nuevos)
        return len(nuevos), salteados

    def _vinculos(self, filas):
        productos = set(Products.todos.values_list('pk', flat=True))
        hechos, salteados = 0, []
        for fila in filas:
            pk, producto = int(fila['id']), int(fila['product_id'])
            if producto not in productos:
                salteados.append(f'renglon de compra {pk}: el producto {producto} no existe')
                continue
            # update() NO llama a save(): no suma stock ni cambia costos
            n = PurchaseProduct.objects.filter(pk=pk, product__isnull=True).update(product_id=producto)
            if n:
                hechos += 1
            else:
                salteados.append(f'renglon de compra {pk}: no existe o ya tiene producto')
        return hechos, salteados
