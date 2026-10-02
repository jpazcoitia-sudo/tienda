"""
Tests de Inventario.

Como correrlos (parado en store/):   python manage.py test inventory
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from inventory.models import Category, Products


class AsignarCodigoDeBarrasTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser('admin_test', 'a@a.com', 'clave-test')
        self.client.force_login(self.user)
        cat = Category.objects.create(name='Cat Test', description='x')
        self.queso = Products.objects.create(code='T001', name='QUESO RALLADO', category=cat, cost=Decimal('100'))
        self.salame = Products.objects.create(code='T002', name='SALAME', category=cat, cost=Decimal('100'))
        self.url = reverse('inventory:asignar_codigo_barras')

    def test_asigna_el_codigo(self):
        resp = self.client.post(self.url, {'producto_id': self.queso.pk, 'codigo': '7790001112223'})
        self.assertEqual(resp.json()['status'], 'ok')
        self.queso.refresh_from_db()
        self.assertEqual(self.queso.codigo_barras, '7790001112223')

    def test_asignar_no_cambia_precio_ni_stock(self):
        self.queso.refresh_from_db()
        antes = (self.queso.cost, self.queso.precio_minorista, self.queso.precio_mayorista, self.queso.quantity)
        self.client.post(self.url, {'producto_id': self.queso.pk, 'codigo': '7790001112223'})
        self.queso.refresh_from_db()
        despues = (self.queso.cost, self.queso.precio_minorista, self.queso.precio_mayorista, self.queso.quantity)
        self.assertEqual(antes, despues)

    def test_rechaza_un_codigo_que_ya_usa_otro_producto(self):
        self.client.post(self.url, {'producto_id': self.queso.pk, 'codigo': '7790001112223'})
        resp = self.client.post(self.url, {'producto_id': self.salame.pk, 'codigo': '7790001112223'})
        self.assertEqual(resp.json()['status'], 'error')
        self.assertIn('QUESO RALLADO', resp.json()['mensaje'])
        self.salame.refresh_from_db()
        self.assertFalse(self.salame.codigo_barras)

    def test_rechaza_codigo_vacio(self):
        resp = self.client.post(self.url, {'producto_id': self.queso.pk, 'codigo': '   '})
        self.assertEqual(resp.json()['status'], 'error')

    def test_la_lista_de_productos_carga(self):
        resp = self.client.get(reverse('inventory:product_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('QUESO RALLADO' in resp.content.decode())


class ActualizarPreciosTests(TestCase):
    """Pantalla "Actualizar Precios" (edicion rapida) y actualizacion masiva por proveedor."""

    def setUp(self):
        import json
        self.json = json
        self.user = User.objects.create_superuser('admin_test', 'a@a.com', 'clave-test')
        self.client.force_login(self.user)
        cat = Category.objects.create(name='Cat Test', description='x')
        self.tomate = Products.objects.create(
            code='T001', name='TOMATE', category=cat, cost=Decimal('100'),
            margen_minorista=Decimal('50'), margen_mayorista=Decimal('40'))

    def guardar(self, costo, minorista, mayorista):
        resp = self.client.post(
            reverse('inventory:guardar_cambios_precios'),
            data=self.json.dumps({'cambios': [{'id': self.tomate.pk, 'name': 'TOMATE', 'cost': costo,
                                               'porc_minorista': minorista, 'porc_mayorista': mayorista}]}),
            content_type='application/json')
        self.assertTrue(resp.json()['success'], resp.json())
        self.assertEqual(resp.json()['errores'], [])
        self.tomate.refresh_from_db()

    def test_guarda_costo_y_precios(self):
        self.guardar('105', '80', '60')
        self.assertEqual(self.tomate.cost, Decimal('105.00'))
        self.assertEqual(self.tomate.precio_minorista, Decimal('189.00'))
        self.assertEqual(self.tomate.precio_mayorista, Decimal('168.00'))

    def test_guarda_el_margen(self):
        """BUG 02/10/2026: el margen no se guardaba; la compra siguiente volvia al margen viejo."""
        self.guardar('105', '80', '60')
        self.assertEqual(self.tomate.margen_minorista, Decimal('80.00'))
        self.assertEqual(self.tomate.margen_mayorista, Decimal('60.00'))

    def test_una_compra_posterior_respeta_el_margen_nuevo(self):
        self.guardar('105', '80', '60')
        self.tomate.update_cost(Decimal('110'))      # lo que hace una compra a $110
        self.tomate.refresh_from_db()
        self.assertEqual(self.tomate.precio_minorista, Decimal('198.00'))   # 110 * 1,80
        self.assertEqual(self.tomate.precio_mayorista, Decimal('176.00'))   # 110 * 1,60

    def test_margen_con_muchos_decimales_se_redondea_a_dos(self):
        self.guardar('100', '33.3333', '25.5555')
        self.assertEqual(self.tomate.margen_minorista, Decimal('33.33'))
        self.assertEqual(self.tomate.precio_minorista, Decimal('133.33'))

    def test_no_deja_un_producto_en_costo_cero(self):
        """BUG 02/10/2026: un producto editado que no estaba a la vista al guardar llegaba
        con costo 0 y margenes 0, y quedaba con precio $0."""
        resp = self.client.post(
            reverse('inventory:guardar_cambios_precios'),
            data=self.json.dumps({'cambios': [{'id': self.tomate.pk, 'name': 'TOMATE', 'cost': 0,
                                               'porc_minorista': 0, 'porc_mayorista': 0}]}),
            content_type='application/json')
        self.assertEqual(resp.json()['actualizados'], 0)
        self.assertEqual(len(resp.json()['errores']), 1)
        self.tomate.refresh_from_db()
        self.assertEqual(self.tomate.cost, Decimal('100.00'))
        self.assertEqual(self.tomate.margen_minorista, Decimal('50.00'))
        self.assertEqual(self.tomate.precio_minorista, Decimal('150.00'))


class ActualizacionMasivaPorProveedorTests(TestCase):

    def setUp(self):
        import json
        from purchase.models import Purchase, Supplier
        self.json = json
        self.user = User.objects.create_superuser('admin_test', 'a@a.com', 'clave-test')
        self.client.force_login(self.user)
        cat = Category.objects.create(name='Cat Test', description='x')
        self.tomate = Products.objects.create(
            code='T001', name='TOMATE', category=cat, cost=Decimal('50'),
            margen_minorista=Decimal('50'), margen_mayorista=Decimal('40'))
        self.proveedor = Supplier.objects.create(name='Proveedor Test')
        compra = Purchase.objects.create(supplier=self.proveedor)
        compra.guardar_renglones([(self.tomate, Decimal('100'), Decimal('10'))])
        self.tomate.refresh_from_db()   # costo 100, activo, con stock

    def enviar(self, **datos):
        datos['proveedor_id'] = self.proveedor.pk
        resp = self.client.post(reverse('inventory:actualizacion_masiva_proveedor'),
                                data=self.json.dumps(datos), content_type='application/json')
        self.assertTrue(resp.json()['success'], resp.json())
        self.tomate.refresh_from_db()
        return resp.json()

    def test_aumentar_costo_un_porcentaje(self):
        r = self.enviar(accion='aumentar_costo', porcentaje=10.5)
        self.assertEqual(r['actualizados'], 1)
        self.assertEqual(self.tomate.cost, Decimal('110.50'))
        self.assertEqual(self.tomate.precio_minorista, Decimal('165.75'))   # mantiene el margen 50%

    def test_disminuir_costo_un_porcentaje(self):
        self.enviar(accion='disminuir_costo', porcentaje=10)
        self.assertEqual(self.tomate.cost, Decimal('90.00'))

    def test_cambiar_los_margenes_del_proveedor(self):
        self.enviar(accion='recalcular_porcentajes', porcentaje=0, porc_minorista=80, porc_mayorista=60)
        self.assertEqual(self.tomate.margen_minorista, Decimal('80.00'))
        self.assertEqual(self.tomate.margen_mayorista, Decimal('60.00'))
        self.assertEqual(self.tomate.precio_minorista, Decimal('180.00'))
        self.assertEqual(self.tomate.precio_mayorista, Decimal('160.00'))


class BorradoLogicoTests(TestCase):
    """
    Eliminar un producto lo OCULTA, no lo borra de la base (decision de Juan, 02/10/2026).
    Motivo: borrarlo de verdad eliminaba en silencio sus renglones de venta.
    """

    def setUp(self):
        from pos.models import Sales, salesItems
        self.Sales, self.salesItems = Sales, salesItems
        self.user = User.objects.create_superuser('admin_test', 'a@a.com', 'clave-test')
        self.client.force_login(self.user)
        self.cat = Category.objects.create(name='Cat Test', description='x')
        self.queso = Products.objects.create(code='0195', name='QUESO RALLADO', category=self.cat,
                                             cost=Decimal('100'), codigo_barras='7790001112223')
        self.queso2 = Products.objects.create(code='0196', name='QUESO RALLADO', category=self.cat,
                                              cost=Decimal('100'))
        for p in (self.queso, self.queso2):
            p.quantity = Decimal('10'); p.save(update_fields=['quantity']); p.update_status()

    def vender(self, producto, qty='2', precio=150):
        venta = self.Sales.objects.create(code='T-%s' % self.Sales.objects.count(), grand_total=float(qty) * precio)
        self.salesItems.objects.create(sale=venta, product=producto, qty=Decimal(qty), price=precio, total=float(qty) * precio)
        return venta

    def eliminar_desde_la_pantalla(self, producto):
        return self.client.post(reverse('inventory:product_delete', args=[producto.pk]), follow=True)

    # ---- lo central: las ventas no se pierden ----
    def test_eliminar_un_producto_conserva_sus_renglones_de_venta(self):
        venta = self.vender(self.queso)
        self.eliminar_desde_la_pantalla(self.queso)
        self.assertEqual(venta.salesitems_set.count(), 1, 'el renglon de venta tiene que seguir existiendo')
        self.assertEqual(venta.salesitems_set.get().product.name, 'QUESO RALLADO')

    def test_la_lista_de_ventas_sigue_mostrando_el_producto_eliminado(self):
        self.vender(self.queso)
        self.eliminar_desde_la_pantalla(self.queso)
        resp = self.client.get(reverse('pos:sales-page'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('QUESO RALLADO' in resp.content.decode())

    def test_no_se_puede_borrar_de_la_base_un_producto_con_ventas(self):
        from django.db.models import ProtectedError
        venta = self.vender(self.queso)
        with self.assertRaises(ProtectedError):
            Products.todos.get(pk=self.queso.pk).delete()      # borrado REAL (ej. desde el admin)
        self.assertEqual(venta.salesitems_set.count(), 1)

    # ---- el producto desaparece para el usuario ----
    def test_eliminado_no_aparece_en_los_listados(self):
        self.eliminar_desde_la_pantalla(self.queso)
        self.assertFalse(Products.objects.filter(pk=self.queso.pk).exists())
        self.assertTrue(Products.todos.filter(pk=self.queso.pk, eliminado=True).exists())
        html = self.client.get(reverse('inventory:product_list')).content.decode()
        self.assertFalse('0195' in html)
        self.assertTrue('0196' in html)

    def test_eliminado_no_aparece_en_el_pos_ni_en_compras(self):
        self.eliminar_desde_la_pantalla(self.queso)
        self.assertFalse('0195 - QUESO RALLADO' in self.client.get(reverse('purchase:purchase_create')).content.decode())
        self.assertFalse(str(self.queso.pk) in self.client.get(reverse('purchase:api_productos_compra')).json())
        resp = self.client.get(reverse('pos:pos-page'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self.queso.pk in [p.pk for p in resp.context['products']])

    def test_el_mensaje_avisa_que_las_ventas_se_conservan(self):
        resp = self.eliminar_desde_la_pantalla(self.queso)
        mensajes = ' | '.join(str(m) for m in resp.context['messages'])
        self.assertTrue('se conservan' in mensajes, mensajes)

    def test_la_confirmacion_explica_que_pasa(self):
        html = self.client.get(reverse('inventory:product_delete', args=[self.queso.pk])).content.decode()
        self.assertTrue('se conservan' in html)
        self.assertTrue('tiene stock cargado' in html)

    # ---- codigos ----
    def test_el_codigo_de_barras_queda_libre_para_otro_producto(self):
        self.eliminar_desde_la_pantalla(self.queso)
        resp = self.client.post(reverse('inventory:asignar_codigo_barras'),
                                {'producto_id': self.queso2.pk, 'codigo': '7790001112223'})
        self.assertEqual(resp.json()['status'], 'ok', resp.json())
        self.queso2.refresh_from_db()
        self.assertEqual(self.queso2.codigo_barras, '7790001112223')

    def test_el_codigo_interno_de_un_eliminado_no_se_reutiliza(self):
        from django.core.exceptions import ValidationError
        from inventory.views import siguiente_codigo_correlativo
        Products.objects.create(code='0300', name='ULTIMO', category=self.cat, cost=Decimal('10')).eliminar()
        self.assertEqual(siguiente_codigo_correlativo(), '0301')
        with self.assertRaises(ValidationError):
            Products.objects.create(code='0300', name='OTRO', category=self.cat, cost=Decimal('10'))

    # ---- restaurar ----
    def test_restaurar_vuelve_a_mostrarlo(self):
        self.queso.eliminar()
        Products.todos.get(pk=self.queso.pk).restaurar()
        self.assertTrue(Products.objects.filter(pk=self.queso.pk).exists())
        self.queso.refresh_from_db()
        self.assertEqual(self.queso.status, Products.STATUS_ACTIVE)   # tiene stock y precio

    # ---- operaciones sobre historia con productos eliminados ----
    def test_borrar_una_venta_de_un_producto_eliminado_no_falla(self):
        venta = self.vender(self.queso, qty='2')
        self.eliminar_desde_la_pantalla(self.queso)
        resp = self.client.post(reverse('pos:delete-sale'), {'id': venta.pk})
        self.assertEqual(resp.json()['status'], 'success', resp.json())
        self.assertEqual(Products.todos.get(pk=self.queso.pk).quantity, Decimal('10'))   # 10 - 2 + 2


class ComprasConProductoEliminadoTests(TestCase):

    def setUp(self):
        from purchase.models import Purchase, Supplier
        self.user = User.objects.create_superuser('admin_test', 'a@a.com', 'clave-test')
        self.client.force_login(self.user)
        cat = Category.objects.create(name='Cat Test', description='x')
        self.tomate = Products.objects.create(code='T001', name='TOMATE', category=cat, cost=Decimal('10'))
        self.pickles = Products.objects.create(code='T002', name='PICKLES', category=cat, cost=Decimal('10'))
        self.proveedor = Supplier.objects.create(name='Proveedor Test')
        self.compra = Purchase.objects.create(supplier=self.proveedor, numero_comprobante='TEST-1')
        self.compra.guardar_renglones([(self.tomate, Decimal('100'), Decimal('10')),
                                       (self.pickles, Decimal('300'), Decimal('5'))])
        Products.objects.get(pk=self.pickles.pk).eliminar()

    def test_ver_la_compra_muestra_el_producto_eliminado(self):
        html = self.client.get(reverse('purchase:purchase_detail', args=[self.compra.pk])).content.decode()
        self.assertTrue('PICKLES' in html and 'TOMATE' in html)

    def test_editar_la_compra_conserva_el_renglon_del_producto_eliminado(self):
        import json
        resp = self.client.get(reverse('purchase:purchase_update', args=[self.compra.pk]))
        items = json.loads(resp.context['items_json'])
        self.assertEqual(len(items), 2, 'la pantalla tiene que traer los dos renglones')
        productos = json.loads(resp.context['products_json'])
        self.assertTrue('(eliminado)' in productos[str(self.pickles.pk)]['name'])
        # el eliminado no se ofrece en el desplegable para renglones nuevos
        self.assertFalse('T002 - PICKLES' in resp.content.decode())

        resp = self.client.post(reverse('purchase:purchase_update', args=[self.compra.pk]), {
            'supplier': self.proveedor.pk, 'numero_comprobante': 'TEST-1',
            'product[]': [it['product_id'] for it in items],
            'cost[]': [it['cost'] for it in items],
            'qty[]': [it['qty'] for it in items],
            'iva_pct': '0', 'perc_pct': '0', 'accion': 'guardar',
        })
        self.assertEqual(resp.status_code, 302)
        self.compra.refresh_from_db()
        self.assertEqual(self.compra.items.count(), 2)
        self.assertEqual(self.compra.total, Decimal('2500.00'))
        self.tomate.refresh_from_db()
        self.assertEqual(self.tomate.quantity, Decimal('10'))

    def test_borrar_la_compra_no_falla(self):
        resp = self.client.post(reverse('purchase:purchase_delete', args=[self.compra.pk]))
        self.assertEqual(resp.status_code, 302)
        self.tomate.refresh_from_db()
        self.assertEqual(self.tomate.quantity, Decimal('0'))
        # el eliminado sigue eliminado e inactivo
        p = Products.todos.get(pk=self.pickles.pk)
        self.assertTrue(p.eliminado)
        self.assertEqual(p.status, Products.STATUS_INACTIVE)

    def test_no_se_puede_borrar_de_la_base_un_producto_con_compras(self):
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            Products.todos.get(pk=self.tomate.pk).delete()


class RecuperarBorradosTests(TestCase):
    """Comando recuperar_borrados: repone la historia perdida al eliminar productos (02/10/2026)."""

    def setUp(self):
        import json, os, tempfile
        from pos.models import Sales, salesItems
        from purchase.models import Purchase, PurchaseProduct, Supplier
        self.Sales, self.salesItems, self.PurchaseProduct = Sales, salesItems, PurchaseProduct
        cat = Category.objects.create(name='Cat Test', description='x')
        self.viejo = Products.objects.create(code='0080', name='DULCE DE LECHE', category=cat, cost=Decimal('100'),
                                             codigo_barras='7790001112223')
        self.vigente = Products.objects.create(code='0081', name='MAYONESA', category=cat, cost=Decimal('50'))
        for p in (self.viejo, self.vigente):
            p.quantity = Decimal('20'); p.save(update_fields=['quantity']); p.update_status()

        # Una compra y una venta con los dos productos
        prov = Supplier.objects.create(name='Proveedor Test')
        self.compra = Purchase.objects.create(supplier=prov)
        self.compra.guardar_renglones([(self.viejo, Decimal('100'), Decimal('5')), (self.vigente, Decimal('50'), Decimal('5'))])
        self.venta = Sales.objects.create(code='T-1', grand_total=700)
        self.r1 = salesItems.objects.create(sale=self.venta, product=self.viejo, qty=Decimal('2'), price=200, total=400)
        self.r2 = salesItems.objects.create(sale=self.venta, product=self.vigente, qty=Decimal('3'), price=100, total=300)
        self.vigente.refresh_from_db()
        self.stock_vigente = self.vigente.quantity
        self.renglon_compra = self.compra.items.get(product=self.viejo)

        # El plan, con el formato que arma armar_plan.py (todo texto, como en el backup)
        v = Products.todos.filter(pk=self.viejo.pk).values().get()
        plan = {
            'generado': 'test',
            'productos': [dict({k: (None if val is None else str(val)) for k, val in v.items()}, _backup='backup_test.sql')],
            'renglones_venta': [{'id': str(self.r1.pk), 'price': '200', 'costo_unitario': '100', 'qty': '2.000',
                                 'total': '400', 'product_id': str(self.viejo.pk), 'sale_id': str(self.venta.pk),
                                 '_backup': 'backup_test.sql'}],
            'vinculos_compra': [{'id': self.renglon_compra.pk, 'product_id': self.viejo.pk, '_backup': 'backup_test.sql'}],
        }
        for campo in ('eliminado', 'fecha_eliminado'):      # los backups viejos no tienen estas columnas
            plan['productos'][0].pop(campo, None)
        # En el backup de PostgreSQL las fechas vienen con zona horaria
        plan['productos'][0]['date_added'] = '2026-05-10 09:30:15.123456-03'
        plan['productos'][0]['date_updated'] = '2026-09-29 18:03:50.5-03'
        fd, self.archivo = tempfile.mkstemp(suffix='.json')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(plan, f)
        self.addCleanup(os.remove, self.archivo)

        # Simular el daño que hacia el borrado viejo: se fue el producto, su renglon de venta
        # y el renglon de compra quedo sin producto.
        salesItems.objects.filter(pk=self.r1.pk).delete()
        PurchaseProduct.objects.filter(pk=self.renglon_compra.pk).update(product=None)
        Products.todos.filter(pk=self.viejo.pk).delete()
        self.assertEqual(self.venta.salesitems_set.count(), 1)

    def correr(self, *args):
        from io import StringIO
        from django.core.management import call_command
        salida = StringIO()
        call_command('recuperar_borrados', '--archivo', self.archivo, *args, stdout=salida)
        return salida.getvalue()

    def test_sin_aplicar_solo_simula(self):
        salida = self.correr()
        self.assertTrue('SIMULACION' in salida)
        self.assertTrue('1 -> 0' in salida, salida)                       # ventas descuadradas: antes -> despues
        self.assertFalse(Products.todos.filter(pk=self.viejo.pk).exists())
        self.assertEqual(self.venta.salesitems_set.count(), 1)

    def test_aplicar_repone_el_renglon_y_el_producto_vuelve_oculto(self):
        salida = self.correr('--aplicar')
        self.assertTrue('LISTO' in salida)
        p = Products.todos.get(pk=self.viejo.pk)
        self.assertTrue(p.eliminado)
        self.assertEqual(p.name, 'DULCE DE LECHE')
        self.assertEqual(p.code, '0080')
        self.assertIsNone(p.codigo_barras, 'vuelve sin codigo de barras')
        self.assertEqual(p.date_added.strftime('%Y-%m-%d %H:%M'), '2026-05-10 09:30')   # hora local, sin zona
        self.assertFalse(Products.objects.filter(pk=self.viejo.pk).exists(), 'no aparece en los listados')
        # la venta recupera su detalle, con el mismo numero de renglon
        renglon = self.salesItems.objects.get(pk=self.r1.pk)
        self.assertEqual(renglon.product_id, self.viejo.pk)
        self.assertEqual(renglon.total, 400)
        self.assertEqual(sum(i.total for i in self.venta.salesitems_set.all()), 700)
        # la compra vuelve a saber que producto era
        self.assertEqual(self.PurchaseProduct.objects.get(pk=self.renglon_compra.pk).product_id, self.viejo.pk)

    def test_aplicar_no_toca_el_stock_ni_el_costo_de_los_productos_vigentes(self):
        self.vigente.refresh_from_db()
        antes = (self.vigente.quantity, self.vigente.cost, self.vigente.precio_minorista)
        self.correr('--aplicar')
        self.vigente.refresh_from_db()
        self.assertEqual(antes, (self.vigente.quantity, self.vigente.cost, self.vigente.precio_minorista))

    def test_se_puede_correr_dos_veces(self):
        self.correr('--aplicar')
        salida = self.correr('--aplicar')
        self.assertTrue('ya existe' in salida)
        self.assertEqual(self.salesItems.objects.filter(sale=self.venta).count(), 2)
        self.assertEqual(Products.todos.filter(code='0080').count(), 1)


# ---------------------------------------------------------------------------
# Estado del producto con la regla nueva (02/10/2026): el stock no decide.
# ---------------------------------------------------------------------------
class EstadoDelProductoTests(TestCase):

    def setUp(self):
        self.cat = Category.objects.create(name='Cat', description='x')

    def test_por_unidad_sin_stock_queda_activo(self):
        p = Products.objects.create(code='E001', name='SIN STOCK', category=self.cat, cost=Decimal('100'))
        p.refresh_from_db()
        self.assertEqual(p.quantity, Decimal('0'))
        self.assertEqual(p.status, Products.STATUS_ACTIVE)

    def test_stock_negativo_tambien_queda_activo(self):
        p = Products.objects.create(code='E002', name='NEGATIVO', category=self.cat, cost=Decimal('100'), quantity=Decimal('1'))
        p.update_quantity_on_sale(Decimal('3'))
        p.refresh_from_db()
        self.assertEqual(p.quantity, Decimal('-2.00'))
        self.assertEqual(p.status, Products.STATUS_ACTIVE)

    def test_sin_costo_queda_inactivo_aunque_tenga_stock(self):
        p = Products.objects.create(code='E003', name='SIN COSTO', category=self.cat, cost=Decimal('0'), quantity=Decimal('10'))
        p.refresh_from_db()
        self.assertEqual(p.status, Products.STATUS_INACTIVE)

    def test_eliminado_sigue_inactivo(self):
        p = Products.objects.create(code='E004', name='ELIMINADO', category=self.cat, cost=Decimal('100'), quantity=Decimal('5'))
        p.eliminar()
        p = Products.todos.get(pk=p.pk)
        p.update_status()
        self.assertEqual(Products.todos.get(pk=p.pk).status, Products.STATUS_INACTIVE)


# ---------------------------------------------------------------------------
# Conteo de stock
# ---------------------------------------------------------------------------
from inventory.models import ConteoStock, ConteoStockRenglon
from django.core.exceptions import ValidationError


class ConteoDeStockTests(TestCase):

    def setUp(self):
        import json
        self.json = json
        self.user = User.objects.create_superuser('admin_test', 'a@a.com', 'clave-test')
        self.client.force_login(self.user)
        cat = Category.objects.create(name='Quesos', description='x')
        self.queso = Products.objects.create(code='C001', name='QUESO CREMOSO', category=cat,
                                             cost=Decimal('1000'), quantity=Decimal('200'))
        self.tybo = Products.objects.create(code='C002', name='TYBO', category=cat, cost=Decimal('8000'),
                                            quantity=Decimal('200'), tipo_venta=Products.TIPO_VENTA_FRACCIONABLE)
        self.mani = Products.objects.create(code='C003', name='MANI', category=cat,
                                            cost=Decimal('500'), quantity=Decimal('200'))

    def iniciar(self):
        self.client.post(reverse('inventory:conteo_stock'), {'accion': 'iniciar', 'nota': 'general'})
        return ConteoStock.el_abierto()

    def cargar(self, producto, contado):
        return self.client.post(reverse('inventory:conteo_guardar'),
                                data=self.json.dumps({'producto_id': producto.pk, 'contado': contado}),
                                content_type='application/json').json()

    def stock(self, producto):
        return Products.todos.get(pk=producto.pk).quantity

    # --- empezar ---
    def test_empezar_un_conteo(self):
        conteo = self.iniciar()
        self.assertIsNotNone(conteo)
        self.assertEqual(conteo.iniciado_por, self.user)
        self.assertEqual(conteo.nota, 'general')

    def test_no_se_abren_dos_conteos_a_la_vez(self):
        self.iniciar()
        self.iniciar()
        self.assertEqual(ConteoStock.objects.count(), 1)

    def test_empezar_no_cambia_ningun_stock(self):
        self.iniciar()
        self.assertEqual(self.stock(self.queso), Decimal('200.00'))

    # --- cargar ---
    def test_cargar_pone_el_stock_contado_y_anota_lo_que_habia(self):
        conteo = self.iniciar()
        resp = self.cargar(self.queso, 12)
        self.assertTrue(resp['ok'], resp)
        self.assertEqual(self.stock(self.queso), Decimal('12.00'))
        r = ConteoStockRenglon.objects.get(conteo=conteo, product=self.queso)
        self.assertEqual(r.stock_sistema, Decimal('200.00'))
        self.assertEqual(r.contado, Decimal('12.00'))
        self.assertEqual(r.diferencia, Decimal('-188.00'))
        self.assertEqual(r.usuario, self.user)

    def test_no_toca_costo_precios_ni_los_otros_productos(self):
        self.iniciar()
        self.cargar(self.queso, 12)
        self.queso.refresh_from_db()
        self.assertEqual(self.queso.cost, Decimal('1000.00'))
        self.assertEqual(self.queso.precio_minorista, Decimal('1350.00'))
        self.assertEqual(self.stock(self.mani), Decimal('200.00'))

    def test_pesable_con_decimales(self):
        self.iniciar()
        self.cargar(self.tybo, 3.85)
        self.assertEqual(self.stock(self.tybo), Decimal('3.85'))

    def test_mas_de_dos_decimales_se_redondea_a_centesimos(self):
        self.iniciar()
        self.cargar(self.tybo, '3.846')
        self.assertEqual(self.stock(self.tybo), Decimal('3.85'))

    def test_contar_cero_deja_stock_cero_y_el_producto_sigue_activo(self):
        self.iniciar()
        self.cargar(self.queso, 0)
        self.queso.refresh_from_db()
        self.assertEqual(self.queso.quantity, Decimal('0.00'))
        self.assertEqual(self.queso.status, Products.STATUS_ACTIVE)

    def test_corregir_un_producto_ya_cargado(self):
        """Si se cargo mal (12 en vez de 21) se vuelve a cargar: queda un solo renglon."""
        conteo = self.iniciar()
        self.cargar(self.queso, 12)
        self.cargar(self.queso, 21)
        self.assertEqual(self.stock(self.queso), Decimal('21.00'))
        self.assertEqual(conteo.renglones.count(), 1)
        r = conteo.renglones.get()
        self.assertEqual(r.stock_sistema, Decimal('200.00'), 'se conserva lo que decia el sistema la primera vez')
        self.assertEqual(r.contado, Decimal('21.00'))

    def test_rechaza_negativos_texto_y_productos_inexistentes(self):
        self.iniciar()
        self.assertFalse(self.cargar(self.queso, -5)['ok'])
        self.assertFalse(self.cargar(self.queso, 'doce')['ok'])
        self.assertFalse(self.cargar(self.queso, None)['ok'])
        self.assertFalse(self.cargar(self.queso, 'NaN')['ok'])
        self.assertFalse(self.cargar(self.queso, 1000000)['ok'])
        resp = self.client.post(reverse('inventory:conteo_guardar'),
                                data=self.json.dumps({'producto_id': 99999, 'contado': 1}),
                                content_type='application/json').json()
        self.assertFalse(resp['ok'])
        self.assertEqual(self.stock(self.queso), Decimal('200.00'))
        self.assertEqual(ConteoStockRenglon.objects.count(), 0)

    def test_sin_conteo_abierto_no_se_puede_cargar(self):
        resp = self.cargar(self.queso, 12)
        self.assertFalse(resp['ok'])
        self.assertEqual(self.stock(self.queso), Decimal('200.00'))

    def test_un_producto_eliminado_no_se_puede_contar(self):
        self.iniciar()
        self.mani.eliminar()
        self.assertFalse(self.cargar(self.mani, 5)['ok'])

    def test_guardar_exige_post(self):
        self.iniciar()
        self.assertEqual(self.client.get(reverse('inventory:conteo_guardar')).status_code, 405)

    # --- ventas durante el conteo ---
    def test_una_venta_despues_de_contar_descuenta_del_valor_contado(self):
        self.iniciar()
        self.cargar(self.queso, 12)
        self.queso.update_quantity_on_sale(Decimal('2'))
        self.assertEqual(self.stock(self.queso), Decimal('10.00'))

    # --- cerrar ---
    def test_cerrar_sin_tildar_deja_como_estan_los_no_contados(self):
        conteo = self.iniciar()
        self.cargar(self.queso, 12)
        self.client.post(reverse('inventory:conteo_cerrar'), {})
        conteo.refresh_from_db()
        self.assertFalse(conteo.abierto)
        self.assertEqual(conteo.cerrado_por, self.user)
        self.assertEqual(self.stock(self.mani), Decimal('200.00'))
        self.assertEqual(conteo.renglones.count(), 1)

    def test_cerrar_tildando_deja_en_cero_los_no_contados(self):
        conteo = self.iniciar()
        self.cargar(self.queso, 12)
        self.client.post(reverse('inventory:conteo_cerrar'), {'poner_en_cero': '1'})
        self.assertEqual(self.stock(self.queso), Decimal('12.00'))
        self.assertEqual(self.stock(self.mani), Decimal('0.00'))
        self.assertEqual(self.stock(self.tybo), Decimal('0.00'))
        automaticos = conteo.renglones.filter(automatico=True)
        self.assertEqual(automaticos.count(), 2)
        self.assertEqual(automaticos.get(product=self.mani).stock_sistema, Decimal('200.00'))

    def test_cerrar_no_pone_en_cero_los_eliminados(self):
        conteo = self.iniciar()
        self.mani.eliminar()
        self.client.post(reverse('inventory:conteo_cerrar'), {'poner_en_cero': '1'})
        self.assertEqual(self.stock(self.mani), Decimal('200.00'))
        self.assertFalse(conteo.renglones.filter(product=self.mani).exists())

    def test_despues_de_cerrar_no_se_puede_cargar_y_se_puede_empezar_otro(self):
        conteo = self.iniciar()
        self.client.post(reverse('inventory:conteo_cerrar'), {})
        self.assertFalse(self.cargar(self.queso, 5)['ok'])
        with self.assertRaises(ValidationError):
            ConteoStock.objects.get(pk=conteo.pk).cargar(self.queso, Decimal('5'))
        self.assertNotEqual(self.iniciar().pk, conteo.pk)

    # --- pantallas ---
    def test_pantallas_abren(self):
        self.assertEqual(self.client.get(reverse('inventory:conteo_stock')).status_code, 200)
        conteo = self.iniciar()
        self.cargar(self.queso, 12)
        resp = self.client.get(reverse('inventory:conteo_stock'))
        self.assertEqual(resp.status_code, 200)
        datos = {p['code']: p for p in resp.context['productos']}
        self.assertEqual(datos['C001']['contado'], 12.0)
        self.assertEqual(datos['C001']['antes'], 200.0)
        self.assertIsNone(datos['C002']['contado'])
        html = self.client.get(reverse('inventory:conteo_detalle', args=[conteo.pk])).content.decode()
        self.assertTrue('QUESO CREMOSO' in html and 'C001' in html)
        self.client.post(reverse('inventory:conteo_cerrar'), {})
        self.assertEqual(self.client.get(reverse('inventory:conteo_detalle', args=[conteo.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('inventory:conteo_stock')).status_code, 200)

    def test_un_nombre_con_comillas_o_etiquetas_no_rompe_la_pantalla(self):
        Products.objects.create(code='C009', name='QUESO "LA PAULINA" </script><b>x', category=self.queso.category, cost=Decimal('1'))
        self.iniciar()
        html = self.client.get(reverse('inventory:conteo_stock')).content.decode()
        self.assertFalse('</script><b>x' in html)

    def test_el_vendedor_no_entra(self):
        from django.contrib.auth.models import Group
        grupo, _ = Group.objects.get_or_create(name='Vendedor')
        vendedor = User.objects.create_user('vendedora', password='clave-test')
        vendedor.groups.add(grupo)
        self.iniciar()
        self.client.force_login(vendedor)
        self.assertEqual(self.client.get(reverse('inventory:conteo_stock')).status_code, 403)
        resp = self.client.post(reverse('inventory:conteo_guardar'),
                                data=self.json.dumps({'producto_id': self.queso.pk, 'contado': 1}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.stock(self.queso), Decimal('200.00'))
