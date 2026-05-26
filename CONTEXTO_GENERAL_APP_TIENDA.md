# 🏪 CONTEXTO GENERAL - APP TIENDA (Fiambrería Yanina)

> **PARA NUEVO CHAT:** Este archivo es el contexto histórico completo del proyecto. Léelo todo antes de responder. Para operaciones del día a día usar CONTEXTO_PROYECTO.md

---

## 1. QUÉ ES ESTE PROYECTO

Sistema de punto de venta (POS) para una fiambrería/almacén administrada por Yanina. Desarrollado por su esposo Juan Pablo desde cero usando Django. El sistema reemplaza planillas Excel y una caja registradora básica.

**URL producción:** https://yanizallocco.com.ar
**Repositorio:** https://github.com/jpazcoitia-sudo/tienda

---

## 2. INFRAESTRUCTURA COMPLETA

### Servidor VPS:
- **IP:** 66.97.37.224
- **SSH:** `ssh -i ~/.ssh/sshjpa -p 5758 jpazcoitia@66.97.37.224`
- **OS:** Ubuntu 22.04
- **Web server:** Nginx (proxy reverso)
- **App server:** Gunicorn (proceso manual con --daemon, NO systemd)
- **Puerto:** 8000

### Base de datos producción:
- **Motor:** PostgreSQL (**CRÍTICO: NO es SQLite**)
- **DB:** tienda_db
- **Usuario:** tienda_user
- **Password:** Ajunito2215Golf$
- **Host:** localhost / Puerto: 5432

### Base de datos local:
- SQLite (db.sqlite3) - en .gitignore, nunca sube a GitHub

### Rutas:
- **VPS:** `~/tienda/store` (entorno virtual: `~/tienda/.venv`)
- **Mac local:** `~/Projects/tienda/store`
- **Estáticos VPS:** `/var/www/tienda/static/`

### Settings.py VPS (config local, NO en GitHub):
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'tienda_db',
        'USER': 'tienda_user',
        'PASSWORD': 'Ajunito2215Golf$',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
ALLOWED_HOSTS = ['yanizallocco.com.ar', 'www.yanizallocco.com.ar', '66.97.37.224', 'localhost', '127.0.0.1']
STATIC_ROOT = '/var/www/tienda/static/'
```

---

## 3. ARQUITECTURA DJANGO

### Apps instaladas:
- **core** - Vista home, configuración base
- **inventory** - Productos, categorías, stock
- **pos** - Punto de venta, ventas, tickets
- **purchase** - Compras, proveedores, pagos
- **customers** - Clientes, cuenta corriente
- **finances** - Caja, banco, movimientos, cierre de caja
- **report** - Reportes PDF y Excel
- **pedidos** - Módulo de pedidos/órdenes

### Stack tecnológico:
- Django 5.x
- PostgreSQL (producción) / SQLite (desarrollo)
- Bootstrap + Material Design
- DataTables para listados
- jQuery para interactividad
- xhtml2pdf + reportlab para PDFs
- openpyxl para Excel

---

## 4. MÓDULOS Y FUNCIONALIDADES IMPLEMENTADAS

### 📦 INVENTARIO (inventory)
- CRUD de productos con: nombre, costo, stock, punto de pedido, márgenes minorista/mayorista
- Precio minorista y mayorista calculados automáticamente desde márgenes
- Campo `punto_pedido`: alerta cuando stock <= este valor
- Importador masivo desde Excel: `python manage.py import_products ~/lista.xlsx`
- Formato Excel: Proveedor | Nombre | Cantidad | Costo | %Mayorista | %Minorista

### 🛒 POS - PUNTO DE VENTA (pos)
- Carrito de compras con productos y cantidades decimales (kg)
- Lista de precios: minorista o mayorista (cambia precios automáticamente)
- Cliente opcional (si hay cliente, habilita cuenta corriente)
- Precio editable por producto en el carrito (click en el precio)
- Mismo producto puede agregarse varias veces (ventas fraccionadas)
- Descuento global con % calculado en tiempo real

**Modal "Verificar" al procesar:**
- Forma de pago: Efectivo / Transferencia / Mixto
- En Mixto: campo efectivo + campo transferencia independientes
- Check "Monto exacto": llena automáticamente con el total
- Check "Cargar a Cuenta Corriente" (solo si hay cliente seleccionado)
- Botón Confirmar bloqueado hasta que haya monto válido O se tilde CC
- Vuelto calculado sobre el efectivo

**Movimientos de caja al vender:**
- Efectivo → `venta_efectivo` → suma a saldo efectivo
- Banco → `venta_banco` → suma a saldo banco
- Mixto → crea DOS movimientos (efectivo + banco) con montos respectivos
- Cuenta corriente → NO crea movimiento de caja

**Al eliminar una venta:** revierte automáticamente todos los movimientos de caja

**Ticket térmico:**
- Impresora: Gadnic IT1050 (58mm)
- Driver: POS-58 (de sistemas360.ar)
- CSS: `@page size: 48mm`, `#outprint width: 46mm`
- Conectada a PC Windows del negocio

### 🏪 COMPRAS (purchase)
- Carga de compras con múltiples productos
- **Descuento por producto** (% aplicado al costo unitario)
- **IVA (monto fijo)**: se ingresa el monto que figura en la factura
- **Percepción IVA (monto fijo)**: ídem
- IVA + Percepción se distribuyen proporcionalmente entre productos según participación en subtotal
- El costo final de cada producto en inventario se actualiza con la proporción asignada
- Campos guardados en Purchase: `subtotal_productos`, `iva_monto`, `perc_monto`, `total`

**Pago de compras:**
- Botón "Guardar" (solo guarda) y "Guardar y Pagar" (redirige a pago)
- Desde lista de compras pendientes: botón Pagar
- Formas de pago: Efectivo / Banco / Mixto
- Mixto: campo efectivo + campo banco independientes
- Botón "Omitir pago" → vuelve a lista de pagos pendientes

**Tipos de movimiento caja al pagar compra:**
- `compra_efectivo` y/o `compra_banco`

**Edición de compras:** reescrita para mostrar todos los items de la compra correctamente

### 👥 CLIENTES (customers)
- CRUD completo con: nombre, DNI/CUIT, teléfono, email, dirección, tipo (minorista/mayorista), notas
- Tipo de cliente determina lista de precios por defecto en POS

**Cuenta corriente:**
- Se genera cuando una venta se carga como "Cuenta Corriente"
- Modelo: `MovimientoCuentaCorriente` (tipo: venta/pago, monto, forma_pago, venta relacionada)
- Método `get_saldo_cuenta_corriente()` en modelo Cliente
- Pantalla cliente muestra: saldo actual + historial de movimientos

**Registrar pago de CC:**
- Desde pantalla del cliente → botón "Registrar Pago"
- Formas de pago: Efectivo o Transferencia
- **Crea movimiento de caja** correspondiente (venta_efectivo o venta_banco)

### 💰 FINANZAS (finances)
- Modelo `Caja` (singleton): saldo_efectivo + saldo_banco
- Modelo `MovimientoCaja`: tipo, monto, concepto, afecta_efectivo, afecta_banco, es_ingreso

**Tipos de movimiento:**
- Ventas: `venta_efectivo`, `venta_banco`
- Compras: `compra_efectivo`, `compra_banco`
- Retiros: `retiro_efectivo`, `retiro_banco`
- Gastos: `gasto` (con flags afecta_efectivo/afecta_banco)
- Transferencias: `transferencia_caja_banco`, `transferencia_banco_caja`

**Cierre de caja diario:**
- Solo uno por día (verifica duplicados)
- Muestra resumen del día: ventas, compras, retiros, gastos (efectivo y banco)
- Operador ingresa: efectivo contado físicamente
- Calcula saldo esperado vs real → muestra diferencia
- Saldo inicial = saldo_real del cierre anterior (no esperado)
- Primer cierre: calcula saldo inicial restando movimientos del día
- **NO ajusta automáticamente diferencias** (solo registra)

**Historial de cierres:** /finances/cierres/

### 🏠 HOME (core)
5 métricas en tiempo real:
1. **Ventas del día**: total AR$, cantidad, ticket promedio
2. **Estado de caja**: saldo efectivo + banco
3. **Cuenta corriente pendiente**: clientes que deben + total adeudado
4. **Punto de pedido**: productos con stock ≤ punto_pedido (muestra stock actual / mínimo)
5. **Comparativa mensual**: ventas hasta hoy vs mismo período mes anterior

### 📊 REPORTES (report)
- Reporte de ventas (PDF y Excel)
- Reporte de compras (PDF y Excel)
- Reporte de ganancias (PDF y Excel)
- Miscelánea

### 📋 PEDIDOS (pedidos)
- Gestión de pedidos/órdenes
- Conversión de pedido a venta

---

## 5. MODELOS IMPORTANTES

### Products (inventory):
```python
cost, precio_minorista, precio_mayorista
margen_minorista, margen_mayorista
quantity (stock), punto_pedido
status, marca
```

### Sales (pos):
```python
code, sub_total, tax, tax_amount, grand_total
tendered_amount, amount_change
cliente (FK), tipo_lista, forma_pago
```

### Purchase (purchase):
```python
supplier (FK), numero_comprobante
total, subtotal_productos, iva_monto, perc_monto
forma_pago, fecha_pago, pagado
```

### MovimientoCuentaCorriente (customers):
```python
cliente (FK), tipo (venta/pago)
monto, forma_pago, venta (FK nullable)
notas, fecha
```

### MovimientoCaja (finances):
```python
tipo, monto, concepto
afecta_efectivo, afecta_banco, es_ingreso
venta (FK nullable), usuario (FK)
fecha
```

### CierreCaja (finances):
```python
fecha (unique), saldo_inicial_efectivo, saldo_inicial_banco
total_ventas_efectivo, total_ventas_banco
total_compras_efectivo, total_compras_banco
total_retiros_efectivo, total_retiros_banco
total_gastos_efectivo, total_gastos_banco
saldo_esperado_efectivo, saldo_esperado_banco
saldo_real_efectivo, diferencia_efectivo
notas, cerrado_por (FK User)
```

---

## 6. DEPLOY - PROCEDIMIENTO EXACTO

```bash
# 1. Conectar
ssh -i ~/.ssh/sshjpa -p 5758 jpazcoitia@66.97.37.224

# 2. Activar entorno
cd ~/tienda && source .venv/bin/activate && cd store

# 3. Verificar PostgreSQL ANTES
grep -A 3 "DATABASES" store/settings.py

# 4. Pull limpio
git pull origin main
# Si falla por .pyc: git ls-files --unmerged | awk '{print $4}' | sort -u | xargs git rm --cached && git add -A && git commit -m "Fix pyc" && git pull

# 5. Verificar PostgreSQL DESPUÉS
grep -A 3 "DATABASES" store/settings.py

# 6. Migrate
python manage.py migrate

# 7. Estáticos
python manage.py collectstatic --noinput

# 8. Reiniciar Gunicorn
ps aux | grep gunicorn | grep tienda
kill -HUP [PID_PRINCIPAL]
# Si no corre: gunicorn --workers 3 --bind 127.0.0.1:8000 store.wsgi:application --daemon
```

### Comandos prohibidos en VPS:
```
git reset --hard
git rm --cached
git checkout -- .
sudo systemctl restart tienda-gunicorn.service  ← NO EXISTE
```

---

## 7. OPERACIONES COMUNES

### Limpiar base de datos:
```bash
python manage.py shell < borrar_movimientos.py   # ventas/compras/finanzas
python manage.py shell < borrar_productos.py     # productos/proveedores
```

### Importar productos:
```bash
scp -i ~/.ssh/sshjpa -P 5758 ~/Downloads/lista.xlsx jpazcoitia@66.97.37.224:~/
python manage.py import_products ~/lista.xlsx
```

### Backup PostgreSQL:
```bash
sudo -u postgres pg_dump tienda_db > ~/backup_$(date +%Y%m%d_%H%M%S).sql
```

---

## 8. BUGS CONOCIDOS / PENDIENTES

### Pendientes de implementar:
- 🖨️ Probar ticket térmico con impresora Gadnic en Windows (driver instalado)
- 📄 PDF estado de cuenta corriente por cliente
- 💸 Acceso rápido a "Retiro de dinero" desde home
- 🏠 Botón "Ver más" en home para cuenta corriente y punto de pedido
- 🔧 Ordenar y limpiar menú izquierdo
- 🐛 En historial de venta de cliente, dice "efectivo" aunque sea cuenta corriente (cosmético)

### Verificaciones pendientes:
- Reportes PDF/Excel (no verificados en sesión de revisión)

---

## 9. PROCESO DE DESARROLLO - REGLAS IMPORTANTES

### Antes de cualquier modificación, preguntar:
1. ¿Qué modelos toca? → ¿hay migración?
2. ¿Qué flujos impacta?
   - Carga → ¿se guarda bien?
   - Edición → ¿muestra datos correctos?
   - Listados → ¿valores actualizados?
   - Caja → ¿movimientos correctos?
   - Home → ¿métricas actualizadas?
3. ¿Qué pasa aguas abajo?

### Checklist post-implementación:
- [ ] Dato guardado correctamente en BD
- [ ] Listado muestra valor correcto
- [ ] Edición/detalle muestra bien
- [ ] Totales y cálculos derivados correctos
- [ ] Movimientos de caja generados correctamente
- [ ] Home actualizada si corresponde

---

## 10. CONTEXTO DEL NEGOCIO

- **Rubro:** Fiambrería/almacén
- **Particularidad:** Productos con precios por kg/unidad, ventas fraccionadas
- **Impuestos:** IVA 21% + Percepción IVA (montos fijos en factura, no %)
- **Clientes:** Mayoristas que llevan mercadería fiada (cuenta corriente)
- **Proveedores:** Muy informales, pueden dar descuentos por producto y mezclar IVA
- **Impresora:** Ticket térmico Gadnic IT1050 58mm conectada a PC Windows

---

**Última actualización:** 26 de mayo de 2026
**Sesiones de desarrollo:** ~30+ sesiones desde febrero 2026
