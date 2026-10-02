"""
Tests de acceso: quien puede entrar a que.

Como correrlos (parado en store/):   python manage.py test core

Regla del sistema (core/middleware.py):
  - Sin iniciar sesion solo se abre el login (y el admin, que tiene el suyo).
  - Los superusuarios pueden todo.
  - Cualquier otro usuario solo puede usar la lista blanca del Vendedor.
"""
from decimal import Decimal

from django.contrib.auth.models import Group, Permission, User
from django.test import Client, TestCase
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from core.middleware import PUBLICAS, VENDEDOR_ALLOWED
from customers.models import Cliente, MovimientoCuentaCorriente
from finances.models import MovimientoCaja
from inventory.models import Category, Products
from purchase.models import Purchase, Supplier


def todas_las_urls():
    """Recorre el mapa de URLs del proyecto y devuelve [(view_name, ruta_de_ejemplo)]."""
    resultado = []

    def recorrer(patrones, prefijo='', espacios=()):
        for p in patrones:
            if isinstance(p, URLResolver):
                if p.namespace == 'admin':
                    continue          # el admin tiene su propio control de acceso
                recorrer(p.url_patterns, prefijo + str(p.pattern),
                         espacios + ((p.namespace,) if p.namespace else ()))
            elif isinstance(p, URLPattern) and p.name:
                ruta = prefijo + str(p.pattern)
                # reemplazar <int:pk>, <uidb64>, etc. por valores de ejemplo
                import re
                ruta = re.sub(r'<int:[^>]+>', '1', ruta)
                ruta = re.sub(r'<[^>]+>', 'x', ruta)
                resultado.append((':'.join(espacios + (p.name,)), '/' + ruta))

    recorrer(get_resolver().url_patterns)
    return resultado


class SinIniciarSesionTests(TestCase):

    def test_ninguna_pantalla_se_abre_sin_login(self):
        """Toda URL del sistema, salvo el login, manda al login a quien no inicio sesion."""
        abiertas = []
        urls = todas_las_urls()
        self.assertGreater(len(urls), 90, 'el recorrido deberia encontrar todas las URLs del proyecto')
        for nombre, ruta in urls:
            if nombre in PUBLICAS:
                continue
            for metodo in ('get', 'post'):
                resp = getattr(self.client, metodo)(ruta)
                if not (resp.status_code == 302 and resp['Location'].startswith('/login')):
                    abiertas.append(f'{metodo.upper()} {ruta} ({nombre}) -> {resp.status_code}')
        self.assertEqual(abiertas, [], 'URLs accesibles sin login:\n' + '\n'.join(abiertas))

    def test_el_login_si_se_abre(self):
        self.assertEqual(self.client.get(reverse('login')).status_code, 200)

    def test_no_existe_el_registro_de_usuarios_ni_el_reseteo_de_clave(self):
        """Sacados el 02/10/2026: cualquiera podia crearse un usuario o cambiarle la clave al dueño."""
        for ruta in ('/register/', '/password_reset/', '/reset/MQ/abc-123/'):
            self.assertEqual(self.client.get(ruta).status_code, 404, ruta)
            self.assertEqual(self.client.post(ruta, {'email': 'a@a.com', 'username': 'x',
                                                     'password': 'x', 'confirm_password': 'x'}).status_code, 404, ruta)
        self.assertEqual(User.objects.count(), 0)
        html = self.client.get(reverse('login')).content.decode()
        self.assertFalse('Register' in html)
        self.assertFalse('Reiniciar la Contrase' in html)

    def test_un_anonimo_no_puede_saldar_la_deuda_de_un_cliente(self):
        cliente = Cliente.objects.create(name='Pablo')
        MovimientoCuentaCorriente.objects.create(cliente=cliente, tipo='venta', monto=Decimal('50000'))
        anonimo = Client(enforce_csrf_checks=False)
        resp = anonimo.post(reverse('customers:registrar_pago', args=[cliente.pk]),
                            {'monto': '50000', 'forma_pago': 'efectivo'})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp['Location'].startswith('/login'))
        self.assertEqual(MovimientoCuentaCorriente.objects.filter(cliente=cliente).count(), 1)
        self.assertEqual(MovimientoCaja.objects.count(), 0)

    def test_un_anonimo_no_puede_marcar_una_compra_como_pagada(self):
        compra = Purchase.objects.create(supplier=Supplier.objects.create(name='Prov'), total=Decimal('1000'))
        url = reverse('purchase:purchase_pagar', args=[compra.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.post(url, {'forma_pago': 'efectivo', 'monto_efectivo': '0', 'monto_banco': '0'})
        compra.refresh_from_db()
        self.assertFalse(compra.pagado)

    def test_un_anonimo_no_descarga_reportes(self):
        for nombre in ('report:generate_pdf_sales', 'report:profit_pdf', 'report:supplier_pdf',
                       'report:product_excel', 'report:lista_precios'):
            resp = self.client.get(reverse(nombre))
            self.assertEqual(resp.status_code, 302, nombre)
            self.assertTrue(resp['Location'].startswith('/login'), nombre)

    def test_la_planilla_de_emergencia_sin_sesion_ni_token_esta_prohibida(self):
        self.assertEqual(self.client.get(reverse('inventory:planilla_emergencia')).status_code, 403)

    def test_el_admin_pide_su_propio_login(self):
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 302)
        self.assertTrue('/admin/login/' in resp['Location'])


class UsuarioSinRolTests(TestCase):
    """Un usuario que no es superusuario ni esta en un grupo no puede hacer nada sensible."""

    def setUp(self):
        self.user = User.objects.create_user('suelto', password='clave-test')
        self.client.force_login(self.user)
        cat = Category.objects.create(name='Cat', description='x')
        self.producto = Products.objects.create(code='T001', name='TOMATE', category=cat, cost=Decimal('100'))

    def test_no_entra_a_caja_precios_clientes_ni_reportes(self):
        prohibidas = []
        for nombre, ruta in todas_las_urls():
            if nombre in VENDEDOR_ALLOWED or nombre in PUBLICAS or nombre == 'home-page':
                continue
            resp = self.client.get(ruta)
            if resp.status_code != 403:
                prohibidas.append(f'{ruta} ({nombre}) -> {resp.status_code}')
        self.assertEqual(prohibidas, [], 'URLs que un usuario sin rol puede abrir:\n' + '\n'.join(prohibidas))

    def test_no_puede_cambiar_precios(self):
        import json
        resp = self.client.post(reverse('inventory:guardar_cambios_precios'),
                                data=json.dumps({'cambios': [{'id': self.producto.pk, 'cost': '1',
                                                              'porc_minorista': '1', 'porc_mayorista': '1'}]}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 403)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cost, Decimal('100.00'))

    def test_no_puede_registrar_retiros_ni_cierres(self):
        for nombre in ('finances:registrar_retiro', 'finances:cierre_caja', 'finances:registrar_gasto', 'finances:transferir_dinero'):
            try:
                url = reverse(nombre)
            except Exception:
                continue
            self.assertEqual(self.client.post(url, {'monto': '1000'}).status_code, 403, nombre)
        self.assertEqual(MovimientoCaja.objects.count(), 0)

    def test_sin_permisos_tampoco_puede_vender(self):
        # El POS esta en la lista blanca, pero ademas exige el permiso del grupo.
        self.assertEqual(self.client.get(reverse('pos:pos-page')).status_code, 403)


class VendedorTests(TestCase):
    """El grupo Vendedor sigue funcionando igual que antes."""

    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name='Vendedor')
        for app, codigo in [('pos', 'view_sales'), ('pos', 'add_sales'), ('inventory', 'view_products'),
                            ('customers', 'view_cliente'), ('pedidos', 'view_pedido'), ('pedidos', 'add_pedido')]:
            grupo.permissions.add(Permission.objects.get(content_type__app_label=app, codename=codigo))
        self.user = User.objects.create_user('vendedora', password='clave-test')
        self.user.groups.add(grupo)
        self.client.force_login(self.user)

    def test_puede_usar_pos_ventas_pedidos_y_clientes(self):
        for nombre in ('pos:pos-page', 'pos:sales-page', 'pedidos:pedido_list', 'customers:customer_list'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200, nombre)

    def test_el_inicio_lo_lleva_al_pos(self):
        resp = self.client.get(reverse('home-page'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], reverse('pos:pos-page'))

    def test_no_entra_a_productos_compras_caja_ni_admin(self):
        for ruta in (reverse('inventory:product_list'), reverse('purchase:purchase_list'),
                     reverse('inventory:edicion_rapida_precios'), '/finances/', '/admin/'):
            self.assertEqual(self.client.get(ruta).status_code, 403, ruta)


class SuperusuarioTests(TestCase):

    def test_el_dueno_entra_a_todo_lo_principal(self):
        self.client.force_login(User.objects.create_superuser('dueno', 'd@d.com', 'clave-test'))
        for ruta in ('/', reverse('inventory:product_list'), reverse('purchase:purchase_list'),
                     reverse('pos:pos-page'), reverse('pos:sales-page'), reverse('customers:customer_list'),
                     reverse('inventory:edicion_rapida_precios'), '/finances/'):
            self.assertEqual(self.client.get(ruta).status_code, 200, ruta)
