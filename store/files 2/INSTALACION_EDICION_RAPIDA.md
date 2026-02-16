# INSTALACIÓN: EDICIÓN RÁPIDA DE PRECIOS

## ARCHIVOS GENERADOS:
1. edicion_rapida_views.py - Vistas y lógica backend
2. edicion_rapida_precios.html - Template con tabla editable

---

## PASO 1: Agregar vistas en inventory/views.py

```bash
nano ~/Library/CloudStorage/OneDrive-Personal/python/mysite/tienda/store/inventory/views.py
```

**Agregar AL FINAL del archivo el contenido de `edicion_rapida_views.py`**

---

## PASO 2: Agregar URLs en inventory/urls.py

```bash
nano ~/Library/CloudStorage/OneDrive-Personal/python/mysite/tienda/store/inventory/urls.py
```

**Agregar en urlpatterns:**

```python
path('edicion-rapida-precios/', views.edicion_rapida_precios, name='edicion_rapida_precios'),
path('guardar-cambios-precios/', views.guardar_cambios_precios, name='guardar_cambios_precios'),
path('actualizacion-masiva-proveedor/', views.actualizacion_masiva_proveedor, name='actualizacion_masiva_proveedor'),
```

---

## PASO 3: Copiar template

```bash
cp ~/Downloads/edicion_rapida_precios.html ~/Library/CloudStorage/OneDrive-Personal/python/mysite/tienda/store/inventory/templates/inventory/edicion_rapida_precios.html
```

---

## PASO 4: Agregar link en navigation.html

```bash
nano ~/Library/CloudStorage/OneDrive-Personal/python/mysite/tienda/store/templates/navigation.html
```

**Agregar DESPUÉS de "Lista de Productos":**

```html
<div class="mdc-list-item mdc-drawer-item">
    <a class="mdc-drawer-link" href="{% url 'inventory:edicion_rapida_precios' %}">
        <i class="material-icons mdc-list-item__start-detail mdc-drawer-item-icon" aria-hidden="true">edit</i> Actualizar Precios
    </a>
</div>
```

---

## PASO 5: Reiniciar servidor

```bash
python manage.py runserver
```

---

## FUNCIONALIDADES:

### EDICIÓN INDIVIDUAL:
1. Filtrar/buscar productos
2. Click en campos de Costo, % Minorista, % Mayorista
3. Modificar valores
4. Ver precios calculados en tiempo real
5. Guardar cambios

### ACTUALIZACIÓN MASIVA:
1. Click "Actualizar Masivamente"
2. Seleccionar proveedor
3. Elegir acción:
   - Aumentar/disminuir costos X%
   - Recalcular porcentajes de ganancia
4. Aplicar → Actualiza todos los productos del proveedor

### FILTROS:
- 🔍 Buscar por nombre
- Filtrar por proveedor (último usado)
- Ordenar: Alfabético, Costo, Stock

### CARACTERÍSTICAS:
- ✅ Edición in-line (click y modificar)
- ✅ Cálculo automático de precios en tiempo real
- ✅ Indica qué productos están modificados (fondo amarillo)
- ✅ Muestra último proveedor de cada producto
- ✅ Contador de productos modificados
- ✅ Actualización masiva por proveedor
- ✅ Solo envía productos modificados al servidor

---

## NOTAS TÉCNICAS:

**Último proveedor:**
- Se obtiene de la tabla `PurchaseProduct`
- Muestra "Sin proveedor registrado" si no hay compras

**Cálculo de precios:**
```
precio_minorista = costo × (1 + % / 100)
precio_mayorista = costo × (1 + % / 100)
```

**Validación:**
- Costo debe ser mayor a 0
- Porcentajes deben ser ≥ 0

---

¡Listo para usar! 💰
