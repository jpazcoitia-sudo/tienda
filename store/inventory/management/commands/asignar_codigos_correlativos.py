from django.core.management.base import BaseCommand
from django.db import transaction
from inventory.models import Products


class Command(BaseCommand):
    help = "Asigna codigos internos correlativos (0001, 0002, ...) ordenados por nombre. Usar --dry-run para previsualizar."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Muestra los cambios sin guardarlos.')
        parser.add_argument('--digitos', type=int, default=4, help='Cantidad de digitos (default 4).')

    def handle(self, *args, **options):
        dry = options['dry_run']
        dig = options['digitos']
        productos = list(Products.objects.all().order_by('name', 'id'))
        total = len(productos)
        self.stdout.write(f"Productos a renumerar: {total}")

        with transaction.atomic():
            for i, p in enumerate(productos, start=1):
                nuevo = str(i).zfill(dig)
                self.stdout.write(f"  {str(p.code):>10}  ->  {nuevo}   {p.name}")
                if not dry:
                    Products.objects.filter(pk=p.pk).update(code=nuevo)

        if dry:
            self.stdout.write(self.style.WARNING("DRY-RUN: no se guardo nada."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Listo: {total} codigos reasignados."))