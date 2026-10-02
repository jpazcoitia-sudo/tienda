"""
Tests de Compras: verifican los EFECTOS de crear / editar / borrar una compra
sobre el stock y el costo de los productos.

Como correrlos (en la Mac, con el entorno activo, parado en store/):
    python manage.py test purchase

Django crea una base de datos de prueba vacia, corre cada test y la borra.
No toca db.sqlite3 ni la base de produccion.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from inventory.models import Category, Products
from purchase.models import Purchase, PurchaseProduct, Supplier


class ComprasBase(TestCase):
    """Datos comunes: un usuario admin, un proveedor y tres productos sin stock."""

    def setUp(self):
        # Superusuario: tiene todos los permisos, asi el test prueba la logica y no los permisos.
        self.user = User.objects.create_superuser('admin_test', 'a@a.com', 'clave-test')
        self.client.force_login(self.user)

        self.proveedor = Supplier.objects.create(name='Proveedor Test')
        self.categoria = Category.objects.create(name='Cat Test', description='x')

        self.tomate = self._producto('T001', 'TOMATE TRITURADO')
        self.pickles = self._producto('T002', 'PICKLES 2 KG')
        self.aceituna = self._producto('T003', 'ACEITUNA VERDE')

    def _producto(self, code, name):
        return Products.objects.create(
            code=code, name=name, category=self.categoria,
            cost=Decimal('100.00'),
            margen_mayorista=Decimal('40'), margen_minorista=Decimal('50'),
        )

    # ---- helpers que imitan lo que manda el navegador ----
    def crear_compra(self, renglones, iva='0', perc='0'):
        """renglones = [(producto, costo, cantidad), ...]. Devuelve la compra creada."""
        resp = self.client.post(reverse('purchase:purchase_create'), {
            'supplier': self.proveedor.pk,
            'numero_comprobante': 'TEST-1',
            'product[]': [p.pk for p, _, _ in renglones],
            'cost[]': [str(c) for _, c, _ in renglones],
            'qty[]': [str(q) for _, _, q in renglones],
            'iva_pct': iva,
            'perc_pct': perc,
            'accion': 'guardar',
        })
        self.assertEqual(resp.status_code, 302, 'crear compra deberia redirigir')
        return Purchase.objects.latest('id')

    def editar_compra(self, compra, renglones):
        resp = self.client.post(reverse('purchase:purchase_update', args=[compra.pk]), {
            'supplier': self.proveedor.pk,
            'numero_comprobante': 'TEST-1',
            'product[]': [p.pk for p, _, _ in renglones],
            'cost[]': [str(c) for _, c, _ in renglones],
            'qty[]': [str(q) for _, _, q in renglones],
        })
        self.assertEqual(resp.status_code, 302, 'editar compra deberia redirigir')

    def renglones_actuales(self, compra):
        """Los renglones tal como estan guardados (lo que la pantalla de editar reenviaria)."""
        return [(it.product, it.cost, it.qty) for it in compra.items.order_by('id')]

    def stock(self, producto):
        producto.refresh_from_db()
        return producto.quantity

    def costo(self, producto):
        producto.refresh_from_db()
        return producto.cost


class CrearCompraTests(ComprasBase):

    def test_crear_suma_stock(self):
        self.crear_compra([(self.tomate, '1260', '64'), (self.pickles, '9000', '8')])
        self.assertEqual(self.stock(self.tomate), Decimal('64'))
        self.assertEqual(self.stock(self.pickles), Decimal('8'))

    def test_crear_actualiza_costo_y_precios(self):
        self.crear_compra([(self.tomate, '1260', '64')])
        self.tomate.refresh_from_db()
        self.assertEqual(self.tomate.cost, Decimal('1260.00'))
        self.assertEqual(self.tomate.precio_minorista, Decimal('1890.00'))   # 1260 * 1,50
        self.assertEqual(self.tomate.precio_mayorista, Decimal('1764.00'))   # 1260 * 1,40

    def test_crear_con_iva_reparte_el_impuesto_en_el_costo(self):
        # 10 unidades a $100 = $1000; IVA $210 -> costo final $121 c/u
        compra = self.crear_compra([(self.tomate, '100', '10')], iva='210')
        self.assertEqual(self.costo(self.tomate), Decimal('121.00'))
        self.assertEqual(compra.total, Decimal('1210.00'))


class EditarCompraTests(ComprasBase):

    def test_editar_sin_cambios_no_cambia_stock(self):
        """BUG 01/10/2026: guardar la edicion sumaba la compra entera otra vez."""
        compra = self.crear_compra([(self.tomate, '1260', '64'), (self.pickles, '9000', '8')])
        self.editar_compra(compra, self.renglones_actuales(compra))
        self.assertEqual(self.stock(self.tomate), Decimal('64'))
        self.assertEqual(self.stock(self.pickles), Decimal('8'))

    def test_editar_dos_veces_no_cambia_stock(self):
        compra = self.crear_compra([(self.tomate, '1260', '64')])
        self.editar_compra(compra, self.renglones_actuales(compra))
        self.editar_compra(compra, self.renglones_actuales(compra))
        self.assertEqual(self.stock(self.tomate), Decimal('64'))

    def test_editar_cambiando_cantidad(self):
        compra = self.crear_compra([(self.pickles, '9000', '8')])
        self.editar_compra(compra, [(self.pickles, '9000', '5')])
        self.assertEqual(self.stock(self.pickles), Decimal('5'))

    def test_editar_reemplazando_un_producto_por_otro(self):
        """El caso de la compra #144: se saca un renglon equivocado y se agrega el correcto."""
        compra = self.crear_compra([(self.tomate, '1260', '64'), (self.pickles, '9000', '8')])
        self.editar_compra(compra, [(self.tomate, '1260', '64'), (self.aceituna, '13500', '8')])
        self.assertEqual(self.stock(self.tomate), Decimal('64'))
        self.assertEqual(self.stock(self.pickles), Decimal('0'), 'el producto quitado vuelve a 0')
        self.assertEqual(self.stock(self.aceituna), Decimal('8'), 'el producto agregado suma')

    def test_editar_respeta_stock_previo_y_ventas(self):
        # Habia 10, compro 8 -> 18. Vendo 3 -> 15. Corrijo la compra a 5 -> 12.
        self.pickles.quantity = Decimal('10')
        self.pickles.save(update_fields=['quantity'])
        compra = self.crear_compra([(self.pickles, '9000', '8')])
        self.pickles.refresh_from_db()
        self.pickles.update_quantity_on_sale(Decimal('3'))
        self.editar_compra(compra, [(self.pickles, '9000', '5')])
        self.assertEqual(self.stock(self.pickles), Decimal('12'))

    def test_editar_despues_de_vender_casi_todo(self):
        # Compro 8, vendo 6 -> 2. Corrijo la compra a 10 -> deberia quedar 4.
        compra = self.crear_compra([(self.pickles, '9000', '8')])
        self.pickles.refresh_from_db()
        self.pickles.update_quantity_on_sale(Decimal('6'))
        self.editar_compra(compra, [(self.pickles, '9000', '10')])
        self.assertEqual(self.stock(self.pickles), Decimal('4'))

    def test_editar_mismo_producto_en_dos_renglones(self):
        compra = self.crear_compra([(self.tomate, '1260', '30'), (self.tomate, '1260', '34')])
        self.editar_compra(compra, self.renglones_actuales(compra))
        self.assertEqual(self.stock(self.tomate), Decimal('64'))

    def test_editar_actualiza_el_costo(self):
        compra = self.crear_compra([(self.pickles, '9000', '8')])
        self.editar_compra(compra, [(self.pickles, '9500', '8')])
        self.assertEqual(self.costo(self.pickles), Decimal('9500.00'))

    def test_editar_sin_cambios_compra_con_iva_no_cambia_costo_ni_total(self):
        compra = self.crear_compra([(self.tomate, '100', '10')], iva='210')
        self.editar_compra(compra, self.renglones_actuales(compra))
        compra.refresh_from_db()
        self.assertEqual(self.costo(self.tomate), Decimal('121.00'))
        self.assertEqual(compra.total, Decimal('1210.00'))
        self.assertEqual(self.stock(self.tomate), Decimal('10'))


class BorrarCompraTests(ComprasBase):

    def test_borrar_compra_resta_el_stock(self):
        compra = self.crear_compra([(self.tomate, '1260', '64'), (self.pickles, '9000', '8')])
        resp = self.client.post(reverse('purchase:purchase_delete', args=[compra.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Purchase.objects.filter(pk=compra.pk).exists())
        self.assertEqual(self.stock(self.tomate), Decimal('0'))
        self.assertEqual(self.stock(self.pickles), Decimal('0'))

    def test_borrar_compra_no_deja_el_costo_en_cero(self):
        compra = self.crear_compra([(self.tomate, '1260', '64')])
        self.client.post(reverse('purchase:purchase_delete', args=[compra.pk]))
        self.assertGreater(self.costo(self.tomate), Decimal('0'))

    def test_borrar_un_renglon_resta_stock_y_no_deja_costo_en_cero(self):
        compra = self.crear_compra([(self.tomate, '1260', '64')])
        PurchaseProduct.objects.get(purchase=compra).delete()
        self.assertEqual(self.stock(self.tomate), Decimal('0'))
        self.assertGreater(self.costo(self.tomate), Decimal('0'))


class PantallaEditarCompraTests(ComprasBase):
    """Prueba el circuito real: abrir la pantalla de editar y guardar lo que ella misma muestra."""

    def test_abrir_y_guardar_sin_tocar_nada_no_cambia_stock_ni_costo(self):
        import re
        compra = self.crear_compra([(self.tomate, '1260', '64'), (self.pickles, '9000.50', '8')])
        resp = self.client.get(reverse('purchase:purchase_update', args=[compra.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()

        # La pantalla muestra el codigo interno del producto (pedido de Juan, 01/10/2026).
        self.assertIn('T001', html)

        # Reenviar exactamente los valores ocultos que la pantalla genero
        # (el [^"$] descarta la plantilla de JavaScript, que tiene ${...}).
        datos = {
            'supplier': self.proveedor.pk,
            'numero_comprobante': 'TEST-1',
            'product[]': re.findall(r'name="product\[\]" value="([^"$]*)"', html),
            'cost[]': re.findall(r'name="cost\[\]" value="([^"$]*)"', html),
            'qty[]': re.findall(r'name="qty\[\]" value="([^"$]*)"', html),
        }
        self.assertEqual(len(datos['product[]']), 2)
        resp = self.client.post(reverse('purchase:purchase_update', args=[compra.pk]), datos)
        self.assertEqual(resp.status_code, 302)

        self.assertEqual(self.stock(self.tomate), Decimal('64'))
        self.assertEqual(self.stock(self.pickles), Decimal('8'))
        self.assertEqual(self.costo(self.tomate), Decimal('1260.00'))
        self.assertEqual(self.costo(self.pickles), Decimal('9000.50'))
        compra.refresh_from_db()
        self.assertEqual(compra.total, Decimal('152644.00'))   # 64*1260 + 8*9000,50


class PantallaNuevaCompraTests(ComprasBase):

    def test_la_pantalla_muestra_el_codigo_del_producto(self):
        """Hay productos con el mismo nombre (duplicados): el codigo permite distinguirlos."""
        resp = self.client.get(reverse('purchase:purchase_create'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('T001 - TOMATE TRITURADO', resp.content.decode())

    def test_la_lista_actualizable_trae_el_codigo(self):
        resp = self.client.get(reverse('purchase:api_productos_compra'))
        self.assertEqual(resp.json()[str(self.tomate.pk)]['code'], 'T001')
