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
