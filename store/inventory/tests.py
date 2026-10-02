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
