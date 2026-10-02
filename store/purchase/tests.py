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

    def editar_compra(self, compra, renglones, iva=None, perc=None):
        """
        Guarda la edicion. Los costos son los de FACTURA (sin impuestos), como en la pantalla.
        Si no se indica IVA/percepcion, se reenvian los que la compra ya tenia
        (que es lo que hace la pantalla: los trae precargados).
        """
        compra.refresh_from_db()
        resp = self.client.post(reverse('purchase:purchase_update', args=[compra.pk]), {
            'supplier': self.proveedor.pk,
            'numero_comprobante': 'TEST-1',
            'product[]': [p.pk for p, _, _ in renglones],
            'cost[]': [str(c) for _, c, _ in renglones],
            'qty[]': [str(q) for _, _, q in renglones],
            'iva_pct': str(compra.iva_monto if iva is None else iva),
            'perc_pct': str(compra.perc_monto if perc is None else perc),
            'accion': 'guardar',
        })
        self.assertEqual(resp.status_code, 302, 'editar compra deberia redirigir')
        compra.refresh_from_db()
        return compra

    def renglones_actuales(self, compra):
        """Los renglones como los muestra la pantalla de editar: con el costo de factura."""
        return [(it.product, it.get_costo_neto(), it.qty) for it in compra.items.order_by('id')]

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
    """Prueba el circuito real: abrir la pantalla de editar y guardar lo que ella misma trae."""

    def abrir(self, compra):
        resp = self.client.get(reverse('purchase:purchase_update', args=[compra.pk]))
        self.assertEqual(resp.status_code, 200)
        return resp

    def guardar_lo_que_trae_la_pantalla(self, compra, resp):
        import json
        items = json.loads(resp.context['items_json'])
        compra.refresh_from_db()
        return self.client.post(reverse('purchase:purchase_update', args=[compra.pk]), {
            'supplier': self.proveedor.pk,
            'numero_comprobante': 'TEST-1',
            'product[]': [it['product_id'] for it in items],
            'cost[]': [it['cost'] for it in items],
            'qty[]': [it['qty'] for it in items],
            'iva_pct': str(compra.iva_monto),
            'perc_pct': str(compra.perc_monto),
            'accion': 'guardar',
        })

    def test_abrir_y_guardar_sin_tocar_nada_no_cambia_stock_ni_costo(self):
        compra = self.crear_compra([(self.tomate, '1260', '64'), (self.pickles, '9000.50', '8')])
        resp = self.abrir(compra)
        html = resp.content.decode()

        # La pantalla muestra el codigo interno del producto (pedido de Juan, 01/10/2026).
        self.assertTrue('T001 - TOMATE TRITURADO' in html)

        resp = self.guardar_lo_que_trae_la_pantalla(compra, resp)
        self.assertEqual(resp.status_code, 302)

        self.assertEqual(self.stock(self.tomate), Decimal('64'))
        self.assertEqual(self.stock(self.pickles), Decimal('8'))
        self.assertEqual(self.costo(self.tomate), Decimal('1260.00'))
        self.assertEqual(self.costo(self.pickles), Decimal('9000.50'))
        compra.refresh_from_db()
        self.assertEqual(compra.total, Decimal('152644.00'))   # 64*1260 + 8*9000,50

    def test_abrir_y_guardar_una_compra_con_iva_y_percepcion_no_cambia_nada(self):
        compra = self.crear_compra([(self.tomate, '100', '10'), (self.pickles, '300', '10')], iva='420', perc='80')
        costo_tomate, costo_pickles, total = self.costo(self.tomate), self.costo(self.pickles), compra.total
        resp = self.guardar_lo_que_trae_la_pantalla(compra, self.abrir(compra))
        self.assertEqual(resp.status_code, 302)
        compra.refresh_from_db()
        self.assertEqual(self.costo(self.tomate), costo_tomate)
        self.assertEqual(self.costo(self.pickles), costo_pickles)
        self.assertEqual(compra.total, total)
        self.assertEqual(self.stock(self.tomate), Decimal('10'))

    def test_es_la_misma_pantalla_que_nueva_compra_con_los_datos_precargados(self):
        import json
        compra = self.crear_compra([(self.tomate, '100', '10')], iva='210', perc='30')
        resp = self.abrir(compra)
        html = resp.content.decode()
        self.assertTrue(f'Editar Compra #{compra.pk}' in html)
        self.assertTrue('id="iva-pct"' in html and 'value="210.00"' in html, 'el IVA viene precargado')
        self.assertTrue('value="30.00"' in html, 'la percepcion viene precargada')
        self.assertTrue('Guardar Cambios' in html)
        self.assertFalse('Guardar y Pagar' in html)
        # El renglon trae el costo de FACTURA (100), no el final con impuestos (124).
        items = json.loads(resp.context['items_json'])
        self.assertEqual(len(items), 1)
        self.assertEqual(Decimal(items[0]['cost']), Decimal('100'))
        self.assertEqual(Decimal(items[0]['qty']), Decimal('10'))

    def test_compra_pagada_muestra_aviso(self):
        compra = self.crear_compra([(self.tomate, '100', '10')])
        self.assertFalse('ya está pagada' in self.abrir(compra).content.decode())
        compra.marcar_como_pagado('efectivo')
        compra.pagado = True
        compra.save()
        self.assertTrue('ya está pagada' in self.abrir(compra).content.decode())


class EditarCompraConImpuestosTests(ComprasBase):
    """Editar reparte IVA y percepcion igual que Nueva compra (pedido de Juan, 02/10/2026)."""

    def test_crear_guarda_el_costo_de_factura_y_el_final(self):
        compra = self.crear_compra([(self.tomate, '100', '10')], iva='210')
        item = compra.items.get()
        self.assertEqual(item.costo_neto, Decimal('100'))
        self.assertEqual(item.cost, Decimal('121'))

    def test_agregar_un_renglon_al_editar_reparte_el_impuesto_entre_todos(self):
        # Antes: el renglon agregado en Editar entraba SIN impuesto.
        compra = self.crear_compra([(self.tomate, '100', '10')], iva='210')
        compra = self.editar_compra(compra, [(self.tomate, '100', '10'), (self.pickles, '100', '10')])
        # subtotal 2000, IVA 210 -> cada unidad lleva 10,50 de impuesto
        self.assertEqual(self.costo(self.tomate), Decimal('110.50'))
        self.assertEqual(self.costo(self.pickles), Decimal('110.50'))
        self.assertEqual(compra.total, Decimal('2210.00'))
        self.assertEqual(compra.subtotal_productos, Decimal('2000.00'))
        self.assertEqual(self.stock(self.tomate), Decimal('10'))
        self.assertEqual(self.stock(self.pickles), Decimal('10'))

    def test_quitar_un_renglon_al_editar_vuelve_a_repartir(self):
        compra = self.crear_compra([(self.tomate, '100', '10'), (self.pickles, '100', '10')], iva='210')
        compra = self.editar_compra(compra, [(self.tomate, '100', '10')])
        self.assertEqual(self.costo(self.tomate), Decimal('121.00'))   # ahora todo el IVA va al tomate
        self.assertEqual(compra.total, Decimal('1210.00'))
        self.assertEqual(self.stock(self.pickles), Decimal('0'))

    def test_cambiar_el_iva_al_editar(self):
        compra = self.crear_compra([(self.tomate, '100', '10')], iva='210')
        compra = self.editar_compra(compra, self.renglones_actuales(compra), iva='420')
        self.assertEqual(self.costo(self.tomate), Decimal('142.00'))
        self.assertEqual(compra.total, Decimal('1420.00'))
        self.assertEqual(compra.iva_monto, Decimal('420.00'))

    def test_agregar_percepcion_al_editar(self):
        compra = self.crear_compra([(self.tomate, '100', '10')], iva='210')
        compra = self.editar_compra(compra, self.renglones_actuales(compra), perc='30')
        self.assertEqual(self.costo(self.tomate), Decimal('124.00'))
        self.assertEqual(compra.total, Decimal('1240.00'))
        self.assertEqual(compra.perc_monto, Decimal('30.00'))

    def test_cambiar_cantidad_en_compra_con_iva(self):
        compra = self.crear_compra([(self.tomate, '100', '10')], iva='210')
        compra = self.editar_compra(compra, [(self.tomate, '100', '20')])
        self.assertEqual(self.stock(self.tomate), Decimal('20'))
        self.assertEqual(self.costo(self.tomate), Decimal('110.50'))   # 2000 + 210 = 2210 / 20
        self.assertEqual(compra.total, Decimal('2210.00'))

    def test_si_un_renglon_es_invalido_no_se_guarda_nada(self):
        compra = self.crear_compra([(self.tomate, '100', '10')], iva='210')
        resp = self.client.post(reverse('purchase:purchase_update', args=[compra.pk]), {
            'supplier': self.proveedor.pk, 'numero_comprobante': 'TEST-1',
            'product[]': [self.tomate.pk, self.pickles.pk],
            'cost[]': ['100', '100'],
            'qty[]': ['10', '0'],          # cantidad 0: invalido
            'iva_pct': '210', 'perc_pct': '0',
        })
        self.assertEqual(resp.status_code, 302)
        compra.refresh_from_db()
        self.assertEqual(compra.items.count(), 1, 'la compra queda como estaba')
        self.assertEqual(self.stock(self.tomate), Decimal('10'))
        self.assertEqual(self.stock(self.pickles), Decimal('0'))
        self.assertEqual(self.costo(self.tomate), Decimal('121.00'))


class MigracionCostoNetoTests(ComprasBase):

    def test_la_migracion_recupera_el_costo_de_factura_de_compras_viejas(self):
        import importlib
        from django.apps import apps
        self.crear_compra([(self.tomate, '100', '10'), (self.pickles, '333.33', '3')], iva='210', perc='15.50')
        self.crear_compra([(self.aceituna, '13500', '8'), (self.tomate, '1260.5', '64')])          # sin impuestos
        self.crear_compra([(self.pickles, '8999.9975', '7.5')], iva='1417.50')                      # costo con 4 decimales
        originales = {it.pk: it.costo_neto for it in PurchaseProduct.objects.all()}
        self.assertEqual(len(originales), 5)

        # Simular compras viejas: sin costo de factura guardado.
        PurchaseProduct.objects.update(costo_neto=None)
        importlib.import_module('purchase.migrations.0008_costo_neto').completar_costo_neto(apps, None)

        for it in PurchaseProduct.objects.all():
            self.assertEqual(it.costo_neto, originales[it.pk], f'renglon de {it.product}')


class CostoNetoHistoricoTests(TestCase):
    """La cuenta que usa la migracion 0008 para recuperar el costo de factura de compras viejas."""

    def setUp(self):
        import importlib
        self.f = importlib.import_module('purchase.migrations.0008_costo_neto').costo_neto_historico

    def test_compra_sin_impuestos(self):
        self.assertEqual(self.f(Decimal('6500'), Decimal('78000'), Decimal('78000'), Decimal('0')), Decimal('6500'))

    def test_compra_con_iva(self):
        # 10 x 100 = 1000 + IVA 210 -> costo final 121. Factura: 100.
        self.assertEqual(self.f(Decimal('121'), Decimal('1210'), Decimal('1000'), Decimal('210')), Decimal('100.0000'))

    def test_compra_con_decimales(self):
        # 3 x 33,33 = 99,99 + IVA 21 -> costo final 40,33 (redondeado a 4 decimales)
        final = (Decimal('33.33') + Decimal('21') / 3).quantize(Decimal('0.0001'))
        self.assertEqual(self.f(final, final * 3, Decimal('99.99'), Decimal('21')), Decimal('33.3300'))

    def test_compra_editada_con_la_pantalla_vieja_usa_los_renglones(self):
        # subtotal guardado desactualizado (500) pero los renglones suman 1210 con IVA 210
        self.assertEqual(self.f(Decimal('121'), Decimal('1210'), Decimal('500'), Decimal('210')), Decimal('100.00'))


class PantallaNuevaCompraTests(ComprasBase):

    def test_la_pantalla_muestra_el_codigo_del_producto(self):
        """Hay productos con el mismo nombre (duplicados): el codigo permite distinguirlos."""
        resp = self.client.get(reverse('purchase:purchase_create'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('T001 - TOMATE TRITURADO', resp.content.decode())

    def test_compra_nueva_no_trae_renglones_y_ofrece_guardar_y_pagar(self):
        resp = self.client.get(reverse('purchase:purchase_create'))
        html = resp.content.decode()
        self.assertEqual(resp.context['items_json'], '[]')
        self.assertTrue('Crear Compra' in html)
        self.assertTrue('Guardar y Pagar' in html)

    def test_la_lista_actualizable_trae_el_codigo(self):
        resp = self.client.get(reverse('purchase:api_productos_compra'))
        self.assertEqual(resp.json()[str(self.tomate.pk)]['code'], 'T001')


class VerCompraTests(ComprasBase):
    """Pantalla de solo lectura para ver una compra (pedido de Juan, 02/10/2026)."""

    def test_muestra_los_renglones_y_los_totales(self):
        compra = self.crear_compra([(self.tomate, '100', '10'), (self.pickles, '300', '10')], iva='420', perc='80')
        resp = self.client.get(reverse('purchase:purchase_detail', args=[compra.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        for texto in ('T001', 'TOMATE TRITURADO', 'T002', 'PICKLES 2 KG', 'Proveedor Test', 'TEST-1',
                      '$4.000,00', '$420,00', '$80,00', '$4.500,00'):
            self.assertTrue(texto in html, f'falta "{texto}" en la pantalla de ver compra')

    def test_ver_no_modifica_nada(self):
        compra = self.crear_compra([(self.tomate, '100', '10')], iva='210')
        antes = (self.stock(self.tomate), self.costo(self.tomate), compra.total, compra.date_updated)
        self.client.get(reverse('purchase:purchase_detail', args=[compra.pk]))
        compra.refresh_from_db()
        self.assertEqual(antes, (self.stock(self.tomate), self.costo(self.tomate), compra.total, compra.date_updated))

    def test_la_lista_de_compras_tiene_el_boton_ver(self):
        compra = self.crear_compra([(self.tomate, '100', '10')])
        html = self.client.get(reverse('purchase:purchase_list')).content.decode()
        self.assertTrue(reverse('purchase:purchase_detail', args=[compra.pk]) in html)


class PantallaBorrarCompraTests(ComprasBase):
    """Cartel al borrar: el stock se descuenta, el costo NO cambia (decision de Juan, 02/10/2026)."""

    def test_la_confirmacion_avisa_que_pasa_con_stock_y_costo(self):
        compra = self.crear_compra([(self.tomate, '1260', '64')])
        html = self.client.get(reverse('purchase:purchase_delete', args=[compra.pk])).content.decode()
        self.assertTrue('T001' in html and 'TOMATE TRITURADO' in html)
        self.assertTrue('NO cambian' in html, 'falta el aviso de que el costo no cambia')
        self.assertTrue('se descuenta' in html)
        self.assertFalse('ya está pagada' in html)

    def test_si_la_compra_esta_pagada_avisa_que_el_pago_no_se_revierte(self):
        compra = self.crear_compra([(self.tomate, '1260', '64')])
        compra.pagado = True
        compra.save()
        html = self.client.get(reverse('purchase:purchase_delete', args=[compra.pk])).content.decode()
        self.assertTrue('ya está pagada' in html)

    def test_despues_de_borrar_avisa_que_productos_revisar(self):
        compra = self.crear_compra([(self.tomate, '1260', '64'), (self.pickles, '9000', '8')])
        resp = self.client.post(reverse('purchase:purchase_delete', args=[compra.pk]), follow=True)
        mensajes = ' | '.join(str(m) for m in resp.context['messages'])
        self.assertTrue('T001 - TOMATE TRITURADO' in mensajes and 'T002 - PICKLES 2 KG' in mensajes, mensajes)
        self.assertTrue('NO se modificaron' in mensajes)
        # y el efecto real: stock devuelto, costo igual
        self.assertEqual(self.stock(self.tomate), Decimal('0'))
        self.assertEqual(self.costo(self.tomate), Decimal('1260.00'))
