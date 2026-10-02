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
