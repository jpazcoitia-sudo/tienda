# Sistema de Gestion para Fiambreria

## Descripcion del Proyecto
Aplicacion web Django clonada de repositorio para gestion de ventas de fiambreria.
Proyecto en adaptacion y personalizacion para negocio especifico.

## Propietario del Negocio
Sistema para negocio de mi esposa (venta de fiambres).

## Estado Actual
- Sistema base funcionando
- Requiere modificaciones para adaptarse a necesidades especificas
- Proyecto en fase de aprendizaje y desarrollo

---

## Stack Tecnologico

### Backend
- **Python**: 3.10.19 (obligatorio para este proyecto)
- **Framework**: Django
- **ORM**: Django ORM

### Base de Datos
- **Desarrollo local**: SQLite (Mac Mini y MacBook Pro)
- **Produccion**: PostgreSQL (alojado en DonWeb)

### Frontend
- HTML templates de Django

---

## Problemas Actuales a Resolver

### 1. Formato de Moneda (URGENTE)
**Problema**: Los precios se muestran con 8 decimales
**Solucion requerida**: Mostrar solo 2 decimales
**Archivos afectados**: Templates HTML que muestren valores monetarios

### 2. Simbolo de Moneda (URGENTE)
**Problema**: Usa "Bs" como simbolo de moneda
**Solucion requerida**: Cambiar a "AR$"
**Archivos afectados**: Templates y posiblemente settings.py

---

## Modificaciones Principales Requeridas

### 3. Sistema de Precios Multiples (FEATURE PRINCIPAL)

#### Situacion Actual
- URL ejemplo: http://127.0.0.1:8000/inventory/products/edit/65/
- Solo permite ingresar UN precio por producto

#### Requerimiento Nuevo
Cada producto debe tener:

**Campos base:**
- costo (decimal): Costo del producto

**Precios Mayorista:**
- margen_mayorista (porcentaje): Margen de ganancia mayorista
- precio_mayorista (calculado automaticamente): costo + (costo * margen_mayorista / 100)

**Precios Minorista:**
- margen_minorista (porcentaje): Margen de ganancia minorista  
- precio_minorista (calculado automaticamente): costo + (costo * margen_minorista / 100)

**Logica de calculo:**
```
Precio Mayorista = Costo x (1 + Margen_Mayorista / 100)
Precio Minorista = Costo x (1 + Margen_Minorista / 100)
```

### 4. Selector de Lista de Precios en POS

**Ubicacion**: Sistema POS (punto de venta)

**Funcionalidad requerida:**
- Dropdown/selector para elegir lista de precios al iniciar venta
- Opciones: "Mayorista" o "Minorista"
- Lista predeterminada: Minorista
- El sistema debe usar los precios correspondientes a la lista seleccionada

### 5. Impacto en Reportes (CRITICO)

**Modulos afectados:**
- Reporte de ventas
- Reporte de ganancias
- Cualquier calculo que use precio/costo

**Requerimientos:**
- Los calculos de ganancia deben considerar:
  - Ganancia = Precio_Vendido - Costo
  - Respetar el tipo de precio usado en cada venta (mayorista/minorista)
- Los reportes deben mostrar correctamente las ganancias segun lista usada

---

## Estructura del Proyecto
```
/
├── inventory/           # App principal de inventario
│   ├── models.py       # Modelos (Product necesita modificacion)
│   ├── views.py        # Vistas (edicion de productos)
│   ├── forms.py        # Formularios (agregar campos de margenes)
│   └── templates/      # Templates HTML
├── pos/                # App de punto de venta (asumo que existe)
│   ├── views.py        # Logica de ventas
│   └── templates/      # Interface de POS
├── reports/            # Reportes (si existe como app separada)
└── manage.py
```

---

## Convenciones de Codigo

### Python/Django
- Seguir PEP 8
- Nombres de variables y funciones en español cuando sea apropiado
- Comentarios en español
- Docstrings en español

### Modelos
- Usar DecimalField para valores monetarios (max_digits=10, decimal_places=2)
- Usar PositiveIntegerField o DecimalField para porcentajes

### Templates
- Usar filtros de Django para formateo de moneda
- Simbolo de moneda: AR$
- Formato: AR$ 1.234,56 (separador de miles: punto, decimales: coma)

---

## Prioridades de Desarrollo

1. **FASE 1 - Correcciones Basicas** COMPLETADA
   - [x] Corregir formato de decimales (8 a 2)
   - [x] Cambiar simbolo moneda (Bs a AR$)

2. **FASE 2 - Sistema de Precios** (feature principal)
   - [ ] Modificar modelo Product (agregar campos)
   - [ ] Crear/modificar migrations
   - [ ] Actualizar formulario de edicion de productos
   - [ ] Implementar calculo automatico de precios

3. **FASE 3 - POS y Selector**
   - [ ] Agregar selector de lista de precios en POS
   - [ ] Modificar logica de venta para usar precio seleccionado
   - [ ] Guardar informacion de lista usada en cada venta

4. **FASE 4 - Reportes**
   - [ ] Actualizar calculos de ganancias
   - [ ] Verificar todos los reportes existentes
   - [ ] Asegurar consistencia de datos

---

## Notas Importantes

- **Aprendizaje**: Estoy aprendiendo Python, explicar codigo cuando sea complejo
- **Testing**: Probar cambios primero en SQLite local antes de subir a produccion
- **Backup**: Hacer backup de DB antes de migrations importantes
- **Hosting**: Produccion en DonWeb con PostgreSQL

---

## Comandos Utiles
```bash
# Activar entorno virtual
conda activate [nombre-env]

# Migraciones
python manage.py makemigrations
python manage.py migrate

# Servidor desarrollo
python manage.py runserver

# Tests
python manage.py test

# Crear superuser
python manage.py createsuperuser
```

---

## Contacto/Recursos
- Repositorio original: https://github.com/jpazcoitia-sudo/tienda
- Produccion: http://66.97.37.224/
- Desarrollo local: http://127.0.0.1:8000
