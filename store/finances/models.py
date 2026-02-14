from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from django.db.models import Sum, Q


class Caja(models.Model):
    """
    Modelo único que mantiene los saldos actuales de Caja y Banco.
    Solo debe existir UN registro en esta tabla.
    """
    
    saldo_efectivo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Saldo en Efectivo (Caja)'
    )
    
    saldo_banco = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Saldo en Banco'
    )
    
    ultima_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    
    class Meta:
        verbose_name = 'Caja'
        verbose_name_plural = 'Caja'
    
    def __str__(self):
        return f"Caja - Efectivo: ${self.saldo_efectivo} | Banco: ${self.saldo_banco}"
    
    def total_disponible(self):
        """Retorna el total disponible (efectivo + banco)"""
        return self.saldo_efectivo + self.saldo_banco
    
    def actualizar_saldos(self):
        """
        Recalcula los saldos desde cero basándose en todos los movimientos.
        Útil para corregir inconsistencias.
        """
        # Calcular saldo de efectivo
        movimientos_efectivo = MovimientoCaja.objects.filter(afecta_efectivo=True)
        ingresos_efectivo = movimientos_efectivo.filter(es_ingreso=True).aggregate(
            total=Sum('monto')
        )['total'] or Decimal('0')
        egresos_efectivo = movimientos_efectivo.filter(es_ingreso=False).aggregate(
            total=Sum('monto')
        )['total'] or Decimal('0')
        
        # Calcular saldo de banco
        movimientos_banco = MovimientoCaja.objects.filter(afecta_banco=True)
        ingresos_banco = movimientos_banco.filter(es_ingreso=True).aggregate(
            total=Sum('monto')
        )['total'] or Decimal('0')
        egresos_banco = movimientos_banco.filter(es_ingreso=False).aggregate(
            total=Sum('monto')
        )['total'] or Decimal('0')
        
        self.saldo_efectivo = ingresos_efectivo - egresos_efectivo
        self.saldo_banco = ingresos_banco - egresos_banco
        self.save()
    
    @classmethod
    def get_instance(cls):
        """Obtiene o crea la única instancia de Caja"""
        caja, created = cls.objects.get_or_create(pk=1)
        return caja


class MovimientoCaja(models.Model):
    """
    Registro de cada movimiento financiero del negocio.
    Cada venta, compra, transferencia, retiro, etc. genera un movimiento.
    """
    
    TIPO_CHOICES = [
        ('venta_efectivo', '💵 Venta en Efectivo'),
        ('venta_banco', '🏦 Venta con Banco/Transferencia'),
        ('compra_efectivo', '🛒 Pago de Compra en Efectivo'),
        ('compra_banco', '💳 Pago de Compra con Banco'),
        ('transferencia_caja_banco', '📤 Depósito (Caja → Banco)'),
        ('transferencia_banco_caja', '📥 Retiro Banco (Banco → Caja)'),
        ('retiro_efectivo', '💸 Retiro de Caja'),
        ('retiro_banco', '🏧 Retiro de Banco'),
        ('gasto', '📝 Gasto/Egreso'),
        ('ajuste_efectivo', '⚙️ Ajuste Manual Efectivo'),
        ('ajuste_banco', '⚙️ Ajuste Manual Banco'),
        ('inicial_efectivo', '🔵 Saldo Inicial Efectivo'),
        ('inicial_banco', '🔵 Saldo Inicial Banco'),
    ]
    
    tipo = models.CharField(
        max_length=30,
        choices=TIPO_CHOICES,
        verbose_name='Tipo de Movimiento'
    )
    
    monto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Monto'
    )
    
    concepto = models.TextField(
        verbose_name='Concepto/Descripción',
        help_text='Descripción del movimiento'
    )
    
    fecha = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha y Hora'
    )
    
    # Relaciones opcionales con otras tablas
    venta = models.ForeignKey(
        'pos.Sales',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Venta Asociada',
        related_name='movimientos_caja'
    )
    
    compra = models.ForeignKey(
        'purchase.Purchase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Compra Asociada',
        related_name='movimientos_caja'
    )
    
    # Indicadores de afectación
    afecta_efectivo = models.BooleanField(
        default=False,
        verbose_name='Afecta Efectivo'
    )
    
    afecta_banco = models.BooleanField(
        default=False,
        verbose_name='Afecta Banco'
    )
    
    es_ingreso = models.BooleanField(
        default=True,
        verbose_name='Es Ingreso',
        help_text='True = Ingreso (+), False = Egreso (-)'
    )
    
    # Usuario que registró el movimiento
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Registrado por'
    )
    
    # Metadata
    creado = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Movimiento de Caja'
        verbose_name_plural = 'Movimientos de Caja'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['tipo']),
            models.Index(fields=['fecha']),
            models.Index(fields=['-fecha']),
        ]
    
    def __str__(self):
        signo = '+' if self.es_ingreso else '-'
        return f"{self.get_tipo_display()} - {signo}${self.monto}"
    
    def save(self, *args, **kwargs):
        """Al guardar, actualizar los saldos de Caja"""
        es_nuevo = self.pk is None
        super().save(*args, **kwargs)
        
        if es_nuevo:
            # Actualizar saldos de Caja
            caja = Caja.get_instance()
            
            if self.afecta_efectivo:
                if self.es_ingreso:
                    caja.saldo_efectivo += self.monto
                else:
                    caja.saldo_efectivo -= self.monto
            
            if self.afecta_banco:
                if self.es_ingreso:
                    caja.saldo_banco += self.monto
                else:
                    caja.saldo_banco -= self.monto
            
            caja.save()
    
    def delete(self, *args, **kwargs):
        """Al eliminar, revertir el efecto en Caja"""
        caja = Caja.get_instance()
        
        if self.afecta_efectivo:
            if self.es_ingreso:
                caja.saldo_efectivo -= self.monto
            else:
                caja.saldo_efectivo += self.monto
        
        if self.afecta_banco:
            if self.es_ingreso:
                caja.saldo_banco -= self.monto
            else:
                caja.saldo_banco += self.monto
        
        caja.save()
        super().delete(*args, **kwargs)
    
    @classmethod
    def crear_desde_venta(cls, venta, forma_pago, usuario=None):
        """Crea un movimiento desde una venta"""
        from django.db import transaction
        
        with transaction.atomic():
            caja = Caja.get_instance()
            
            if forma_pago == 'efectivo':
                mov = cls.objects.create(
                    tipo='venta_efectivo',
                    monto=Decimal(str(venta.grand_total)),
                    concepto=f"Venta {venta.code}",
                    fecha=timezone.now(),
                    venta=venta,
                    afecta_efectivo=True,
                    afecta_banco=False,
                    es_ingreso=True,
                    usuario=usuario
                )
                # Actualizar saldo manualmente
                caja.saldo_efectivo += Decimal(str(venta.grand_total))
                caja.save()
                return mov
            else:  # banco
                mov = cls.objects.create(
                    tipo='venta_banco',
                    monto=Decimal(str(venta.grand_total)),
                    concepto=f"Venta {venta.code} (Banco/Transferencia)",
                    fecha=timezone.now(),
                    venta=venta,
                    afecta_efectivo=False,
                    afecta_banco=True,
                    es_ingreso=True,
                    usuario=usuario
                )
                # Actualizar saldo manualmente
                caja.saldo_banco += Decimal(str(venta.grand_total))
                caja.save()
                return mov
    
    @classmethod
    def crear_desde_compra(cls, compra, forma_pago, usuario=None):
        """Crea un movimiento desde una compra"""
        from django.db import transaction
        
        with transaction.atomic():
            caja = Caja.get_instance()
            
            if forma_pago == 'efectivo':
                mov = cls.objects.create(
                    tipo='compra_efectivo',
                    monto=Decimal(str(compra.total)),
                    concepto=f"Pago Compra #{compra.id} - {compra.supplier.name}",
                    fecha=timezone.now(),
                    compra=compra,
                    afecta_efectivo=True,
                    afecta_banco=False,
                    es_ingreso=False,
                    usuario=usuario
                )
                # Actualizar saldo manualmente
                caja.saldo_efectivo -= Decimal(str(compra.total))
                caja.save()
                return mov
            else:  # banco
                mov = cls.objects.create(
                    tipo='compra_banco',
                    monto=Decimal(str(compra.total)),
                    concepto=f"Pago Compra #{compra.id} - {compra.supplier.name} (Banco)",
                    fecha=timezone.now(),
                    compra=compra,
                    afecta_efectivo=False,
                    afecta_banco=True,
                    es_ingreso=False,
                    usuario=usuario
                )
                # Actualizar saldo manualmente
                caja.saldo_banco -= Decimal(str(compra.total))
                caja.save()
                return mov


class CierreCaja(models.Model):
    """
    Registro del cierre de caja diario.
    Permite verificar que el efectivo físico coincida con el sistema.
    """
    
    fecha = models.DateField(
        verbose_name='Fecha del Cierre',
        unique=True
    )
    
    # Saldos iniciales (del día)
    saldo_inicial_efectivo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Saldo Inicial en Efectivo'
    )
    
    saldo_inicial_banco = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Saldo Inicial en Banco'
    )
    
    # Movimientos del día
    total_ventas_efectivo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Ventas en Efectivo'
    )
    
    total_ventas_banco = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Ventas con Banco'
    )
    
    total_compras_efectivo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Compras en Efectivo'
    )
    
    total_compras_banco = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Compras con Banco'
    )
    
    total_retiros_efectivo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Retiros de Efectivo'
    )
    
    total_retiros_banco = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Retiros de Banco'
    )
    
    total_gastos_efectivo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Gastos en Efectivo'
    )
    
    total_gastos_banco = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Gastos con Banco'
    )
    
    total_transferencias_salida = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Transferencias Caja → Banco'
    )
    
    total_transferencias_entrada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Transferencias Banco → Caja'
    )
    
    # Saldos esperados (según sistema)
    saldo_esperado_efectivo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Saldo Esperado en Efectivo'
    )
    
    saldo_esperado_banco = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Saldo Esperado en Banco'
    )
    
    # Conteo real (solo efectivo, banco no se cuenta físicamente)
    saldo_real_efectivo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Saldo Real Contado en Efectivo',
        help_text='Efectivo físicamente contado en caja'
    )
    
    # Diferencias
    diferencia_efectivo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Diferencia en Efectivo',
        help_text='Positivo = Sobrante, Negativo = Faltante'
    )
    
    # Notas y responsable
    notas = models.TextField(
        blank=True,
        verbose_name='Notas del Cierre',
        help_text='Observaciones sobre el cierre'
    )
    
    cerrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Cerrado por'
    )
    
    fecha_hora_cierre = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha y Hora del Cierre'
    )
    
    class Meta:
        verbose_name = 'Cierre de Caja'
        verbose_name_plural = 'Cierres de Caja'
        ordering = ['-fecha']
    
    def __str__(self):
        return f"Cierre de Caja - {self.fecha}"
    
    def calcular_totales(self):
        """Calcula los totales del día desde MovimientoCaja"""
        movimientos = MovimientoCaja.objects.filter(
            fecha__date=self.fecha
        )
        
        # Ventas
        self.total_ventas_efectivo = movimientos.filter(
            tipo='venta_efectivo'
        ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
        
        self.total_ventas_banco = movimientos.filter(
            tipo='venta_banco'
        ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
        
        # Compras
        self.total_compras_efectivo = movimientos.filter(
            tipo='compra_efectivo'
        ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
        
        self.total_compras_banco = movimientos.filter(
            tipo='compra_banco'
        ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
        
        # Retiros
        self.total_retiros_efectivo = movimientos.filter(
            tipo='retiro_efectivo'
        ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
        
        self.total_retiros_banco = movimientos.filter(
            tipo='retiro_banco'
        ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
        
        # Gastos
        self.total_gastos_efectivo = movimientos.filter(
            tipo='gasto',
            afecta_efectivo=True
        ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
        
        self.total_gastos_banco = movimientos.filter(
            tipo='gasto',
            afecta_banco=True
        ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
        
        # Transferencias
        self.total_transferencias_salida = movimientos.filter(
            tipo='transferencia_caja_banco'
        ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
        
        self.total_transferencias_entrada = movimientos.filter(
            tipo='transferencia_banco_caja'
        ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
        
        # Calcular saldos esperados
        self.saldo_esperado_efectivo = (
            self.saldo_inicial_efectivo +
            self.total_ventas_efectivo +
            self.total_transferencias_entrada -
            self.total_compras_efectivo -
            self.total_retiros_efectivo -
            self.total_gastos_efectivo -
            self.total_transferencias_salida
        )
        
        self.saldo_esperado_banco = (
            self.saldo_inicial_banco +
            self.total_ventas_banco +
            self.total_transferencias_salida -
            self.total_compras_banco -
            self.total_retiros_banco -
            self.total_gastos_banco -
            self.total_transferencias_entrada
        )
    
    def calcular_diferencia(self):
        """Calcula la diferencia entre esperado y real"""
        self.diferencia_efectivo = self.saldo_real_efectivo - self.saldo_esperado_efectivo
