from django.db import migrations

# (app_label, codename) de los permisos minimos del grupo Vendedor
PERMISOS = [
    ('pos', 'view_sales'),
    ('pos', 'add_sales'),
    ('inventory', 'view_products'),
    ('customers', 'view_cliente'),
    ('pedidos', 'view_pedido'),
    ('pedidos', 'add_pedido'),
]


def crear_grupo(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    grupo, _ = Group.objects.get_or_create(name='Vendedor')
    for app_label, codename in PERMISOS:
        try:
            p = Permission.objects.get(content_type__app_label=app_label, codename=codename)
            grupo.permissions.add(p)
        except Permission.DoesNotExist:
            # Si el permiso aun no existe, se omite (no rompe la migracion)
            pass


def borrar_grupo(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='Vendedor').delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('pos', '0004_alter_salesitems_qty'),
        ('inventory', '0008_alter_products_codigo_tipo'),
        ('customers', '0002_movimientocuentacorriente'),
        ('pedidos', '0002_alter_pedido_estado'),
    ]

    operations = [
        migrations.RunPython(crear_grupo, borrar_grupo),
    ]
