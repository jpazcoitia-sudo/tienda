"""
Tests del POS / Ventas.

Como correrlos (parado en store/):   python manage.py test pos
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Cliente
from pos.models import Sales


class ListaDeVentasTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser('admin_test', 'a@a.com', 'clave-test')
        self.client.force_login(self.user)

    def test_muestra_el_nombre_del_cliente(self):
        """BUG 01/10/2026: la columna Clientes salia vacia aunque la venta tuviera cliente."""
        cliente = Cliente.objects.create(name='Pablo Contartese')
        Sales.objects.create(code='T-1', grand_total=170382.55, cliente=cliente)
        html = self.client.get(reverse('pos:sales-page')).content.decode()
        self.assertTrue('Pablo Contartese' in html, 'la lista de ventas no muestra el nombre del cliente')

    def test_venta_sin_cliente_muestra_cliente_general(self):
        Sales.objects.create(code='T-2', grand_total=1000)
        html = self.client.get(reverse('pos:sales-page')).content.decode()
        self.assertTrue('Cliente General' in html, 'la venta sin cliente deberia decir Cliente General')

    def test_muestra_el_vendedor(self):
        Sales.objects.create(code='T-3', grand_total=1000, vendedor=self.user)
        html = self.client.get(reverse('pos:sales-page')).content.decode()
        self.assertTrue('<td class="px-2 py-1 text-center">admin_test</td>' in html, 'la lista de ventas no muestra el vendedor')


# ---------------------------------------------------------------------------
# Regla de stock (decision de Juan, 02/10/2026):
#   la venta NUNCA se frena por falta de stock. Se descuenta siempre y el stock
#   puede quedar negativo (es la senal de que hay que ajustar). Un producto con
#   stock 0 sigue apareciendo en el punto de venta.
# ---------------------------------------------------------------------------
from decimal import Decimal

from finances.models import Caja
from inventory.models import Category, Products
from pos.models import salesItems


class ReglaDeStockTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser('admin_test', 'a@a.com', 'clave-test')
        self.client.force_login(self.user)
        cat = Category.objects.create(name='Quesos', description='x')
        self.queso = Products.objects.create(
            code='Q001', name='QUESO CREMOSO', category=cat, cost=Decimal('1000'),
            quantity=Decimal('2'))
        self.cremac = Products.objects.create(
            code='Q002', name='QUESO CREMAC X KG', category=cat, cost=Decimal('8000'),
            quantity=Decimal('0.39'), tipo_venta=Products.TIPO_VENTA_FRACCIONABLE)

    def vender(self, renglones):
        """renglones: [(producto, cantidad, precio)]. Devuelve el id de la venta."""
        total = sum(float(c) * float(p) for _, c, p in renglones)
        resp = self.client.post(reverse('pos:save-pos'), {
            'product[]': [str(p.pk) for p, _, _ in renglones],
            'qty[]': [str(c) for _, c, _ in renglones],
            'price[]': [str(p) for _, _, p in renglones],
            'sub_total': total, 'grand_total': total, 'tax': 0, 'tax_amount': 0,
            'tendered_amount': total, 'amount_change': 0, 'forma_pago': 'efectivo',
        })
        self.assertEqual(resp.json()['status'], 'success', resp.json())
        return resp.json()['sale']

    def stock(self, producto):
        return Products.todos.get(pk=producto.pk).quantity

    def test_vender_mas_que_el_stock_descuenta_igual(self):
        """Antes: stock 2, se vendian 5 y el stock seguia en 2 (la venta no descontaba nada)."""
        self.vender([(self.queso, 5, 1350)])
        self.assertEqual(self.stock(self.queso), Decimal('-3.00'))

    def test_borrar_esa_venta_devuelve_exactamente_lo_descontado(self):
        """Antes: al borrar la venta el stock pasaba a 7 (2 que nunca se descontaron + 5)."""
        venta = self.vender([(self.queso, 5, 1350)])
        resp = self.client.post(reverse('pos:delete-sale'), {'id': venta})
        self.assertEqual(resp.json()['status'], 'success', resp.json())
        self.assertEqual(self.stock(self.queso), Decimal('2.00'))

    def test_pesable_con_390_gramos_en_sistema_vende_400(self):
        """El ejemplo de Juan: quedan 0,390 kg en el sistema y se venden 0,400 kg."""
        self.vender([(self.cremac, '0.40', 10800)])
        self.assertEqual(self.stock(self.cremac), Decimal('-0.01'))

    def test_venta_normal_sigue_descontando(self):
        self.vender([(self.queso, 1, 1350)])
        self.assertEqual(self.stock(self.queso), Decimal('1.00'))

    def test_producto_por_unidad_con_stock_cero_sigue_activo_y_en_el_pos(self):
        """Antes: con stock 0 pasaba a Inactivo y desaparecia del punto de venta."""
        self.vender([(self.queso, 2, 1350)])
        self.queso.refresh_from_db()
        self.assertEqual(self.queso.quantity, Decimal('0.00'))
        self.assertEqual(self.queso.status, Products.STATUS_ACTIVE)
        html = self.client.get(reverse('pos:pos-page')).content.decode()
        self.assertTrue('QUESO CREMOSO' in html, 'el producto con stock 0 no aparece en el POS')

    def test_el_pos_recibe_el_stock_de_cada_producto(self):
        """Lo usa el cartel que avisa cuando la cantidad supera el stock."""
        import json
        resp = self.client.get(reverse('pos:pos-page'))
        productos = {p['id']: p for p in json.loads(resp.context['product_json'])}
        self.assertEqual(productos[self.queso.pk]['stock'], 2.0)
        self.assertEqual(productos[self.cremac.pk]['stock'], 0.39)

    def test_regrabar_un_renglon_no_descuenta_dos_veces(self):
        """Antes: cada save() de un renglon (por ejemplo desde /admin) volvia a descontar."""
        venta = self.vender([(self.queso, 1, 1350)])
        renglon = salesItems.objects.get(sale_id=venta)
        renglon.save()
        self.assertEqual(self.stock(self.queso), Decimal('1.00'))

    def test_la_caja_no_cambia_por_el_stock(self):
        self.vender([(self.queso, 5, 1350)])
        self.assertEqual(Caja.get_instance().saldo_efectivo, Decimal('6750.00'))
