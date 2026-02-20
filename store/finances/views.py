from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import datetime, date, timedelta
from decimal import Decimal

from .models import Caja, MovimientoCaja, CierreCaja
from .forms import (
    TransferenciaForm, RetiroForm, GastoForm, 
    AjusteManualForm, CierreCajaForm, FiltroMovimientosForm
)


@login_required
def dashboard_caja(request):
    """Dashboard principal de Caja mostrando saldos y resumen del día"""
    
    caja = Caja.get_instance()
    hoy = date.today()
    
    # Movimientos de hoy
    movimientos_hoy = MovimientoCaja.objects.filter(fecha__date=hoy)
    
    # Calcular totales del día
    ventas_efectivo_hoy = movimientos_hoy.filter(
        tipo='venta_efectivo'
    ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
    
    ventas_banco_hoy = movimientos_hoy.filter(
        tipo='venta_banco'
    ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
    
    compras_efectivo_hoy = movimientos_hoy.filter(
        tipo='compra_efectivo'
    ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
    
    compras_banco_hoy = movimientos_hoy.filter(
        tipo='compra_banco'
    ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
    
    retiros_efectivo_hoy = movimientos_hoy.filter(
        tipo='retiro_efectivo'
    ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
    
    retiros_banco_hoy = movimientos_hoy.filter(
        tipo='retiro_banco'
    ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
    
    gastos_efectivo_hoy = movimientos_hoy.filter(
        tipo='gasto',
        afecta_efectivo=True
    ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
    
    gastos_banco_hoy = movimientos_hoy.filter(
        tipo='gasto',
        afecta_banco=True
    ).aggregate(Sum('monto'))['monto__sum'] or Decimal('0')
    
    # Balance del día
    ingresos_efectivo_hoy = ventas_efectivo_hoy
    egresos_efectivo_hoy = compras_efectivo_hoy + retiros_efectivo_hoy + gastos_efectivo_hoy
    balance_efectivo_hoy = ingresos_efectivo_hoy - egresos_efectivo_hoy
    
    ingresos_banco_hoy = ventas_banco_hoy
    egresos_banco_hoy = compras_banco_hoy + retiros_banco_hoy + gastos_banco_hoy
    balance_banco_hoy = ingresos_banco_hoy - egresos_banco_hoy
    
    # Últimos movimientos
    ultimos_movimientos = MovimientoCaja.objects.all()[:10]
    
    # Verificar si ya hay cierre de caja para hoy
    cierre_hoy = CierreCaja.objects.filter(fecha=hoy).first()
    
    context = {
        'page_title': 'Dashboard de Caja',
        'caja': caja,
        'ventas_efectivo_hoy': ventas_efectivo_hoy,
        'ventas_banco_hoy': ventas_banco_hoy,
        'compras_efectivo_hoy': compras_efectivo_hoy,
        'compras_banco_hoy': compras_banco_hoy,
        'retiros_efectivo_hoy': retiros_efectivo_hoy,
        'retiros_banco_hoy': retiros_banco_hoy,
        'gastos_efectivo_hoy': gastos_efectivo_hoy,
        'gastos_banco_hoy': gastos_banco_hoy,
        'balance_efectivo_hoy': balance_efectivo_hoy,
        'balance_banco_hoy': balance_banco_hoy,
        'ultimos_movimientos': ultimos_movimientos,
        'cierre_hoy': cierre_hoy,
    }
    
    return render(request, 'finances/dashboard.html', context)


@login_required
def transferir_dinero(request):
    """Vista para transferir dinero entre Caja y Banco"""
    
    caja = Caja.get_instance()
    
    if request.method == 'POST':
        form = TransferenciaForm(request.POST)
        if form.is_valid():
            from decimal import Decimal
            
            direccion = form.cleaned_data['direccion']
            monto = form.cleaned_data['monto']
            concepto = form.cleaned_data.get('concepto', '')
            
            if direccion == 'caja_banco':
                # Depositar: Caja → Banco (crear DOS movimientos)
                
                # 1. Salida de efectivo
                MovimientoCaja.objects.create(
                    tipo='transferencia_caja_banco',
                    monto=Decimal(str(monto)),
                    concepto=concepto or f'Depósito en banco de AR$ {monto}',
                    afecta_efectivo=True,
                    afecta_banco=False,
                    es_ingreso=False,  # Sale de efectivo
                    usuario=request.user
                )
                caja.saldo_efectivo -= Decimal(str(monto))
                
                # 2. Entrada a banco
                MovimientoCaja.objects.create(
                    tipo='transferencia_caja_banco',
                    monto=Decimal(str(monto)),
                    concepto=concepto or f'Depósito en banco de AR$ {monto}',
                    afecta_efectivo=False,
                    afecta_banco=True,
                    es_ingreso=True,  # Entra al banco
                    usuario=request.user
                )
                caja.saldo_banco += Decimal(str(monto))
                caja.save()
                
                messages.success(
                    request,
                    f'✅ Transferencia exitosa: AR$ {monto} depositado en Banco.'
                )
            else:
                # Retirar: Banco → Caja (crear DOS movimientos)
                
                # 1. Salida de banco
                MovimientoCaja.objects.create(
                    tipo='transferencia_banco_caja',
                    monto=Decimal(str(monto)),
                    concepto=concepto or f'Retiro de banco a caja de AR$ {monto}',
                    afecta_efectivo=False,
                    afecta_banco=True,
                    es_ingreso=False,  # Sale del banco
                    usuario=request.user
                )
                caja.saldo_banco -= Decimal(str(monto))
                
                # 2. Entrada a efectivo
                MovimientoCaja.objects.create(
                    tipo='transferencia_banco_caja',
                    monto=Decimal(str(monto)),
                    concepto=concepto or f'Retiro de banco a caja de AR$ {monto}',
                    afecta_efectivo=True,
                    afecta_banco=False,
                    es_ingreso=True,  # Entra a efectivo
                    usuario=request.user
                )
                caja.saldo_efectivo += Decimal(str(monto))
                caja.save()
                
                messages.success(
                    request,
                    f'✅ Transferencia exitosa: AR$ {monto} retirado del Banco a Caja.'
                )
            
            return redirect('finances:dashboard')
    else:
        form = TransferenciaForm()
    
    context = {
        'page_title': 'Transferir Dinero',
        'form': form,
        'caja': caja,
    }
    
    return render(request, 'finances/transferir.html', context)


@login_required
def registrar_retiro(request):
    """Vista para registrar retiros de efectivo o banco"""
    
    caja = Caja.get_instance()
    
    if request.method == 'POST':
        form = RetiroForm(request.POST)
        if form.is_valid():
            origen = form.cleaned_data['origen']
            monto = form.cleaned_data['monto']
            concepto = form.cleaned_data['concepto']
            
            if origen == 'efectivo':
                MovimientoCaja.objects.create(
                    tipo='retiro_efectivo',
                    monto=monto,
                    concepto=concepto,
                    afecta_efectivo=True,
                    afecta_banco=False,
                    es_ingreso=False,
                    usuario=request.user
                )
                messages.success(
                    request,
                    f'✅ Retiro de Efectivo registrado: AR$ {monto} - {concepto}'
                )
            else:  # banco
                MovimientoCaja.objects.create(
                    tipo='retiro_banco',
                    monto=monto,
                    concepto=concepto,
                    afecta_efectivo=False,
                    afecta_banco=True,
                    es_ingreso=False,
                    usuario=request.user
                )
                messages.success(
                    request,
                    f'✅ Retiro de Banco registrado: AR$ {monto} - {concepto}'
                )
            
            return redirect('finances:dashboard')
    else:
        form = RetiroForm()
    
    context = {
        'page_title': 'Registrar Retiro',
        'form': form,
        'caja': caja,
    }
    
    return render(request, 'finances/retiro.html', context)


@login_required
def registrar_gasto(request):
    """Vista para registrar gastos/egresos"""
    
    caja = Caja.get_instance()
    
    if request.method == 'POST':
        form = GastoForm(request.POST)
        if form.is_valid():
            pagar_con = form.cleaned_data['pagar_con']
            monto = form.cleaned_data['monto']
            concepto = form.cleaned_data['concepto']
            
            if pagar_con == 'efectivo':
                MovimientoCaja.objects.create(
                    tipo='gasto',
                    monto=monto,
                    concepto=concepto,
                    afecta_efectivo=True,
                    afecta_banco=False,
                    es_ingreso=False,
                    usuario=request.user
                )
            else:  # banco
                MovimientoCaja.objects.create(
                    tipo='gasto',
                    monto=monto,
                    concepto=concepto,
                    afecta_efectivo=False,
                    afecta_banco=True,
                    es_ingreso=False,
                    usuario=request.user
                )
            
            messages.success(
                request,
                f'✅ Gasto registrado: AR$ {monto} - {concepto[:50]}'
            )
            
            return redirect('finances:dashboard')
    else:
        form = GastoForm()
    
    context = {
        'page_title': 'Registrar Gasto',
        'form': form,
        'caja': caja,
    }
    
    return render(request, 'finances/gasto.html', context)


@login_required
@permission_required('finances.add_movimientocaja', raise_exception=True)
def ajuste_manual(request):
    """Vista para ajustes manuales (solo administradores)"""
    
    caja = Caja.get_instance()
    
    if request.method == 'POST':
        form = AjusteManualForm(request.POST)
        if form.is_valid():
            cuenta = form.cleaned_data['cuenta']
            tipo_ajuste = form.cleaned_data['tipo_ajuste']
            monto = form.cleaned_data['monto']
            concepto = form.cleaned_data['concepto']
            
            es_ingreso = (tipo_ajuste == 'incremento')
            
            if cuenta == 'efectivo':
                MovimientoCaja.objects.create(
                    tipo='ajuste_efectivo',
                    monto=monto,
                    concepto=f'AJUSTE MANUAL: {concepto}',
                    afecta_efectivo=True,
                    afecta_banco=False,
                    es_ingreso=es_ingreso,
                    usuario=request.user
                )
            else:  # banco
                MovimientoCaja.objects.create(
                    tipo='ajuste_banco',
                    monto=monto,
                    concepto=f'AJUSTE MANUAL: {concepto}',
                    afecta_efectivo=False,
                    afecta_banco=True,
                    es_ingreso=es_ingreso,
                    usuario=request.user
                )
            
            signo = '+' if es_ingreso else '-'
            messages.warning(
                request,
                f'⚠️ Ajuste manual registrado: {signo}AR$ {monto} en {cuenta.upper()}'
            )
            
            return redirect('finances:dashboard')
    else:
        form = AjusteManualForm()
    
    context = {
        'page_title': 'Ajuste Manual',
        'form': form,
        'caja': caja,
    }
    
    return render(request, 'finances/ajuste.html', context)


@login_required
def historial_movimientos(request):
    """Vista para ver el historial completo de movimientos con filtros"""
    
    movimientos = MovimientoCaja.objects.all()
    
    # Aplicar filtros si hay
    form = FiltroMovimientosForm(request.GET or None)
    if form.is_valid():
        if form.cleaned_data.get('tipo'):
            movimientos = movimientos.filter(tipo=form.cleaned_data['tipo'])
        
        if form.cleaned_data.get('fecha_desde'):
            movimientos = movimientos.filter(
                fecha__date__gte=form.cleaned_data['fecha_desde']
            )
        
        if form.cleaned_data.get('fecha_hasta'):
            movimientos = movimientos.filter(
                fecha__date__lte=form.cleaned_data['fecha_hasta']
            )
        
        if form.cleaned_data.get('cuenta'):
            cuenta = form.cleaned_data['cuenta']
            if cuenta == 'efectivo':
                movimientos = movimientos.filter(afecta_efectivo=True)
            elif cuenta == 'banco':
                movimientos = movimientos.filter(afecta_banco=True)
    
    # Paginación simple
    movimientos = movimientos[:100]  # Limitar a 100 por ahora
    
    context = {
        'page_title': 'Historial de Movimientos',
        'movimientos': movimientos,
        'form': form,
    }
    
    return render(request, 'finances/historial.html', context)


@login_required
def detalle_movimiento(request, pk):
    """Vista de detalle de un movimiento específico"""
    
    movimiento = get_object_or_404(MovimientoCaja, pk=pk)
    
    context = {
        'page_title': f'Movimiento #{movimiento.pk}',
        'movimiento': movimiento,
    }
    
    return render(request, 'finances/detalle_movimiento.html', context)


@login_required
def cierre_caja(request):
    """Vista para realizar el cierre de caja diario"""
    
    hoy = date.today()
    caja = Caja.get_instance()
    
    # Verificar si ya existe un cierre para hoy
    cierre_existente = CierreCaja.objects.filter(fecha=hoy).first()
    if cierre_existente:
        messages.warning(request, f'Ya existe un cierre de caja para hoy ({hoy})')
        return redirect('finances:detalle_cierre', pk=cierre_existente.pk)
    
    if request.method == 'POST':
        form = CierreCajaForm(request.POST)
        if form.is_valid():
            cierre = form.save(commit=False)
            cierre.cerrado_por = request.user
            
            # Obtener saldos iniciales (del cierre anterior o saldos actuales)
            cierre_anterior = CierreCaja.objects.filter(
                fecha__lt=hoy
            ).order_by('-fecha').first()
            
            if cierre_anterior:
                cierre.saldo_inicial_efectivo = cierre_anterior.saldo_esperado_efectivo
                cierre.saldo_inicial_banco = cierre_anterior.saldo_esperado_banco
            else:
                # Primer cierre, usar saldos actuales menos movimientos de hoy
                cierre.saldo_inicial_efectivo = Decimal('0')
                cierre.saldo_inicial_banco = Decimal('0')
            
            # Calcular totales del día
            cierre.calcular_totales()
            
            # Calcular diferencia
            cierre.calcular_diferencia()
            
            cierre.save()
            
            if cierre.diferencia_efectivo == 0:
                messages.success(request, '✅ Cierre de caja realizado. Caja cuadrada!')
            elif cierre.diferencia_efectivo > 0:
                messages.warning(
                    request,
                    f'⚠️ Cierre de caja realizado. Sobrante: AR$ {cierre.diferencia_efectivo}'
                )
            else:
                messages.error(
                    request,
                    f'❌ Cierre de caja realizado. Faltante: AR$ {abs(cierre.diferencia_efectivo)}'
                )
            
            return redirect('finances:detalle_cierre', pk=cierre.pk)
    else:
        form = CierreCajaForm()
    
    # Calcular saldo esperado para mostrar
    cierre_anterior = CierreCaja.objects.filter(fecha__lt=hoy).order_by('-fecha').first()
    
    context = {
        'page_title': 'Cierre de Caja',
        'form': form,
        'caja': caja,
        'cierre_anterior': cierre_anterior,
    }
    
    return render(request, 'finances/cierre_caja.html', context)


@login_required
def lista_cierres(request):
    """Vista para listar todos los cierres de caja"""
    
    cierres = CierreCaja.objects.all()[:30]  # Últimos 30 cierres
    
    context = {
        'page_title': 'Historial de Cierres de Caja',
        'cierres': cierres,
    }
    
    return render(request, 'finances/lista_cierres.html', context)


@login_required
def detalle_cierre(request, pk):
    """Vista de detalle de un cierre de caja específico"""
    
    cierre = get_object_or_404(CierreCaja, pk=pk)
    
    # Obtener movimientos de ese día
    movimientos_dia = MovimientoCaja.objects.filter(
        fecha__date=cierre.fecha
    )
    
    context = {
        'page_title': f'Cierre de Caja - {cierre.fecha}',
        'cierre': cierre,
        'movimientos_dia': movimientos_dia,
    }
    
    return render(request, 'finances/detalle_cierre.html', context)


@login_required
def reportes_financieros(request):
    """Vista de reportes financieros"""
    
    context = {
        'page_title': 'Reportes Financieros',
    }
    
    return render(request, 'finances/reportes.html', context)


@login_required
def reporte_flujo_caja(request):
    """Reporte de flujo de caja por período"""
    
    # Por ahora placeholder
    context = {
        'page_title': 'Reporte de Flujo de Caja',
    }
    
    return render(request, 'finances/reporte_flujo.html', context)
