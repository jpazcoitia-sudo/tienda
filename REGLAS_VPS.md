# ⚠️ REGLAS CRÍTICAS - LEER ANTES DE TOCAR EL VPS

## 🧠 IMPORTANTE: Claude no recuerda todo entre sesiones
Recordarle al inicio de cada sesión donde se vayan a hacer cambios en el VPS:
- Que usamos **PostgreSQL** en producción (no SQLite)
- Que el VPS tiene configuración local que NO está en GitHub
- Que hay datos reales de producción que no se pueden perder

---

## 🔴 COMANDOS PROHIBIDOS EN EL VPS

```
git reset --hard        ← NUNCA. Borra archivos locales del VPS
git rm --cached         ← NUNCA en VPS. Solo desde la Mac
git checkout -- .       ← NUNCA. Descarta cambios locales del VPS
git stash + git pull    ← Con mucho cuidado, puede generar conflictos
```

---

## ✅ ÚNICOS COMANDOS GIT SEGUROS EN EL VPS

```bash
git pull origin main    # Traer cambios de GitHub
kill -HUP [PID]         # Reiniciar Gunicorn
```

---

## 💾 BASE DE DATOS

### Configuración actual:
- **Motor:** PostgreSQL (NO SQLite)
- **Base de datos:** tienda_db
- **Usuario:** tienda_user
- **Contraseña:** Ajunito2215Golf$
- **Host:** localhost
- **Puerto:** 5432

### Reglas:
- **NUNCA** tocar db.sqlite3 en el VPS (no se usa)
- **SIEMPRE** hacer backup antes de operaciones riesgosas:
```bash
sudo -u postgres pg_dump tienda_db > ~/backup_$(date +%Y%m%d_%H%M%S).sql
```
- **db.sqlite3 está en .gitignore** → nunca debe subirse a GitHub

---

## 🔧 SETTINGS.PY DEL VPS

El `settings.py` del VPS tiene configuración especial que NO está en GitHub:
- DATABASES apunta a PostgreSQL
- ALLOWED_HOSTS incluye el dominio real

**Si el pull sobreescribe el settings.py:**
```bash
nano ~/tienda/store/store/settings.py
```

Restaurar manualmente:
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

ALLOWED_HOSTS = [
    'yanizallocco.com.ar',
    'www.yanizallocco.com.ar',
    '66.97.37.224',
    'localhost',
    '127.0.0.1'
]
```

---

## 🚀 PROCEDIMIENTO SEGURO PARA ACTUALIZAR EL VPS

```bash
# 1. Conectar
ssh -i ~/.ssh/sshjpa -p 5758 jpazcoitia@66.97.37.224

# 2. Ir al proyecto
cd ~/tienda && source .venv/bin/activate && cd store

# 3. Verificar settings.py antes del pull
grep -A 5 "DATABASES" store/settings.py  # Debe decir postgresql

# 4. Hacer pull
git pull origin main

# 5. Verificar settings.py después del pull (por si se sobreescribió)
grep -A 5 "DATABASES" store/settings.py

# 6. Reiniciar Gunicorn
kill -HUP $(ps aux | grep "gunicorn.*tienda" | grep -v grep | awk '{print $2}' | head -1)
```

---

## 🏗️ INFRAESTRUCTURA

```
Mac local:
  - SQLite (db.sqlite3) para desarrollo
  - Puerto 8000 o 8001

VPS (66.97.37.224):
  - PostgreSQL para producción
  - Gunicorn en puerto 8000 (tienda)
  - Gunicorn en puerto 8003 (karting) - DESACTIVADO
  - Nginx como proxy reverso
  - SSL con Let's Encrypt
```

---

## 🔄 REINICIAR GUNICORN CORRECTAMENTE

```bash
# Buscar PID
ps aux | grep gunicorn | grep tienda

# Reinicio suave (recarga configuración)
kill -HUP [PID_PRINCIPAL]

# Si no funciona, reinicio completo
pkill -f "gunicorn.*tienda"
cd ~/tienda/store
gunicorn --workers 3 --bind 127.0.0.1:8000 store.wsgi:application --daemon
```

---

## 📋 CHECKLIST ANTES DE CADA SESIÓN CON EL VPS

- [ ] Recordarle a Claude que usamos PostgreSQL en producción
- [ ] Recordarle que el settings.py del VPS tiene configuración local
- [ ] Hacer backup de la BD si vamos a hacer cambios importantes
- [ ] Nunca usar comandos git destructivos en el VPS

---

**Última actualización:** 10 de mayo de 2026
