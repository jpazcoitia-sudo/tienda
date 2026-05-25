# 📚 CONTEXTO PROYECTO - TIENDA & KARTING

> **INSTRUCCIÓN PARA NUEVO CHAT:** Leer este archivo completo antes de responder cualquier consulta. Contiene decisiones técnicas críticas que si se ignoran pueden causar pérdida de datos o errores graves en producción.

---

## 1. ARQUITECTURA GENERAL

### Dos proyectos Django en el mismo VPS:

| Proyecto | Descripción | Dominio | Puerto Gunicorn |
|----------|-------------|---------|-----------------|
| **Tienda** | POS para fiambrería de Yanina | yanizallocco.com.ar | 8000 |
| **Karting** | App de gestión de tandas/eventos | karting.com.ar | 8003 (PAUSADO) |

### Desarrollador:
- Trabaja en **Mac** (local) - tiene Mac mini y MacBook
- Usa **Git/GitHub** para versionar
- Deploy manual via `git pull` en VPS
- Accede al VPS via SSH

---

## 2. INFRAESTRUCTURA VPS

**IP:** 66.97.37.224
**SSH:** `ssh -i ~/.ssh/sshjpa -p 5758 jpazcoitia@66.97.37.224`

### Tienda:
- **Ruta VPS:** `~/tienda/store`
- **Entorno virtual:** `~/tienda/.venv`
- **Base de datos:** PostgreSQL (**NO SQLite**)
- **Estáticos:** `/var/www/tienda/static/`
- **Nginx config:** `/etc/nginx/sites-available/tienda`

### Karting:
- **Ruta VPS:** `~/karting`
- **Entorno virtual:** `~/karting/.venv`
- **Base de datos:** SQLite
- **Estado:** Servicio PAUSADO (`karting-gunicorn.service` deshabilitado)
- **Nginx config:** `/etc/nginx/sites-available/karting`

### Base de datos PostgreSQL (Tienda):
```
Motor:    postgresql
DB:       tienda_db
Usuario:  tienda_user
Password: Ajunito2215Golf$
Host:     localhost
Puerto:   5432
```

---

## 3. REGLAS DE DEPLOY - CRÍTICAS

### ⚠️ COMANDOS PROHIBIDOS EN EL VPS:
```
git reset --hard     ← NUNCA. Puede borrar la BD
git rm --cached      ← NUNCA en VPS
git checkout -- .    ← NUNCA. Descarta cambios locales
sudo systemctl restart tienda-gunicorn.service  ← NO EXISTE, no usar
```

### ✅ DEPLOY SEGURO TIENDA (paso a paso exacto):
```bash
# 1. Conectar
ssh -i ~/.ssh/sshjpa -p 5758 jpazcoitia@66.97.37.224

# 2. Ir al proyecto y activar entorno
cd ~/tienda && source .venv/bin/activate && cd store

# 3. Verificar PostgreSQL ANTES del pull
grep -A 3 "DATABASES" store/settings.py

# 4. Pull (puede requerir stash si hay conflictos en .pyc)
git pull origin main
# Si falla: git stash && git pull origin main && git stash pop

# 5. Si hay conflicto en settings.py (línea con <<<<<<):
# nano store/settings.py → buscar <<<<<< → dejar solo STATIC_ROOT = '/var/www/tienda/static/'

# 6. Verificar PostgreSQL DESPUÉS del pull
grep -A 3 "DATABASES" store/settings.py

# 7. Migraciones
python manage.py migrate

# 8. Estáticos
python manage.py collectstatic --noinput

# 9. Reiniciar Gunicorn
ps aux | grep gunicorn | grep tienda
kill -HUP [PID_PRINCIPAL]
# Si no está corriendo: gunicorn --workers 3 --bind 127.0.0.1:8000 store.wsgi:application --daemon
```

### ⚠️ IMPORTANTE - Reinicio de Gunicorn:
**NUNCA usar:** `sudo systemctl restart tienda-gunicorn.service` (no existe)
**SIEMPRE usar:** `kill -HUP [PID]`

### ⚠️ CONFLICTOS EN SETTINGS.PY - RESUELTO:
El STATIC_ROOT ya está en GitHub con el valor correcto `/var/www/tienda/static/`.
Si aparece conflicto, quedarse siempre con:
```python
STATIC_ROOT = '/var/www/tienda/static/'
DATABASES → postgresql
```

### Si settings.py se sobreescribió con el pull:
```bash
nano ~/tienda/store/store/settings.py
```
Restaurar:
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

### 📋 En cada deploy, analizar si hay algo relevante para agregar a este archivo.

---

## 4. RUTAS LOCALES (Mac)

```
Tienda:  ~/Projects/tienda/store
Karting: ~/Projects/karting
```

**Entorno virtual tienda local:** `source .venv/bin/activate`
**Correr servidor local:** `python manage.py runserver 8001`
**Correr para acceso desde celular:** `python manage.py runserver 0.0.0.0:8001`

---

## 5. ESTADO ACTUAL - TIENDA

### Funcionalidades implementadas:
- ✅ POS completo con carrito
- ✅ Productos con cantidades decimales (kg)
- ✅ Precio editable por producto en carrito
- ✅ Descuento con % calculado en tiempo real
- ✅ Mismo producto puede agregarse varias veces (ventas fraccionadas)
- ✅ Forma de pago en modal "Verificar" (Efectivo/Transferencia)
- ✅ Check "Monto exacto" en modal de pago
- ✅ Botón Confirmar bloqueado hasta ingresar monto o tildar cuenta corriente
- ✅ Cuenta corriente de clientes (ventas en cta cte + registrar pagos)
- ✅ Pantalla cliente reorganizada (datos → cuenta corriente → historial)
- ✅ Campo `punto_pedido` en productos
- ✅ Home rediseñada con 5 métricas
- ✅ Módulo finanzas (Caja/Banco)
- ✅ Cierre de caja diario con resumen del día
- ✅ Pago al registrar compra (Efectivo/Banco/Mixto)
- ✅ Edición de compras corregida
- ✅ IVA y Percepción en carga de compras (montos fijos distribuidos proporcionalmente)
- ✅ Descuento por producto en carga de compras
- ✅ Reportes PDF/Excel
- ✅ Importador de productos desde Excel
- ✅ Módulo de pedidos
- ✅ Ticket térmico 48mm (impresora Gadnic IT1050)

### Pendiente:
- 🖨️ Probar ticket con impresora Gadnic IT1050 en Windows
- 📄 PDF estado de cuenta corriente por cliente
- 💸 Retiro de dinero - acceso rápido desde home
- 🏠 Pulir home (Ver más + vista stock bajo punto de pedido)
- 🔧 Ordenar menú izquierdo

---

## 6. ESTADO ACTUAL - KARTING

### Funcionalidades implementadas:
- ✅ Gestión de eventos y tandas
- ✅ Cronómetros múltiples (3 simultáneos) con LAP
- ✅ Auth Fase 1: login/registro Django
- ✅ Eventos asociados al usuario

### Pendiente:
- 🔐 Proteger vistas de tandas con @login_required
- 🌐 Dominio karting.com.ar configurado pero servicio pausado
- 📱 Google OAuth (Fase 2)

---

## 7. DECISIONES TÉCNICAS IMPORTANTES

### Base de datos:
- **Tienda local:** SQLite
- **Tienda producción:** PostgreSQL ← CRÍTICO NO CONFUNDIR
- **Karting:** SQLite en ambos entornos
- **db.sqlite3 está en .gitignore** → nunca sube a GitHub

### Gunicorn:
- Tienda corre como proceso manual con `--daemon`
- Karting tenía systemd pero está deshabilitado
- Para reactivar karting: `sudo systemctl enable karting-gunicorn && sudo systemctl start karting-gunicorn`

### Tipos de movimiento de caja:
- Ventas: `venta_efectivo`, `venta_banco`
- Compras: `compra_efectivo`, `compra_banco`
- Retiros: `retiro_efectivo`, `retiro_banco`
- Gastos: `gasto` (con `afecta_efectivo` o `afecta_banco`)

### Modelo Purchase - campos importantes:
- `total`: total final incluyendo IVA y Percepción
- `subtotal_productos`: subtotal sin impuestos
- `iva_monto`: monto de IVA ingresado en la factura
- `perc_monto`: monto de Percepción IVA ingresado en la factura

### Git workflow:
- Desarrollar en Mac → commit → push → pull en VPS
- Formato: `Feat:`, `Fix:`, `Refactor:`

### Impresora térmica:
- Modelo: Gadnic IT1050 (58mm)
- Driver: POS-58 (de sistemas360.ar)
- Configuración CSS: `@page size: 48mm`, `#outprint width: 46mm`

---

## 8. COMANDOS ÚTILES

### Limpiar base de datos:
```bash
python manage.py shell < borrar_movimientos.py
python manage.py shell < borrar_productos.py
```

### Subir Excel al VPS:
```bash
scp -i ~/.ssh/sshjpa -P 5758 ~/Downloads/lista.xlsx jpazcoitia@66.97.37.224:~/
```

### Importar productos:
```bash
python manage.py import_products ~/lista.xlsx
```

### Backup PostgreSQL:
```bash
sudo -u postgres pg_dump tienda_db > ~/backup_$(date +%Y%m%d_%H%M%S).sql
```
---

## 9. PROCESO DE DESARROLLO - ANÁLISIS DE IMPACTO

Antes de implementar cualquier modificación, analizar y verificar:

### ¿Qué preguntar antes de codear?

1. **¿Qué modelos toca esta modificación?**
   - ¿Hay campos nuevos? → migración obligatoria
   - ¿Cambia la lógica de cálculo? → verificar que todos los que usan ese dato se actualicen

2. **¿Qué flujos impacta?**
   - Carga → ¿se guarda correctamente en la BD?
   - Edición → ¿se muestran los datos correctos?
   - Listados → ¿muestran los valores actualizados?
   - Reportes → ¿siguen siendo correctos?
   - Home → ¿las métricas se actualizan?

3. **¿Qué pasa aguas abajo?**
   Ejemplo: modificar el costo en una compra impacta en:
   - El costo del producto en inventario
   - Los reportes de compras
   - El total de la compra
   - Los movimientos de caja si se pagó

### Checklist de verificación post-implementación:

- [ ] El dato se guarda correctamente en la BD
- [ ] Se muestra bien en el listado correspondiente
- [ ] Se muestra bien en la pantalla de edición/detalle
- [ ] Los totales y cálculos derivados son correctos
- [ ] Los reportes siguen funcionando
- [ ] La home muestra datos actualizados si corresponde

---

**Última actualización:** 25 de mayo de 2026
