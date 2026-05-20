from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import BadHeaderError, send_mail
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
import json

from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from datetime import date, datetime
from inventory.models import *
from pickle import FALSE
from pos.models import *
from django.db.models import Count, Sum
    
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.shortcuts import render

from django.utils import timezone
from django.db.models import Sum, Count, Q, F
from decimal import Decimal
import datetime
import calendar
from finances.models import Caja
from customers.models import Cliente, MovimientoCuentaCorriente
from inventory.models import Products

User = get_user_model()

from.forms import *

def login_user(request):
    logout(request)
    resp = {"status":'failed','msg':''}
    username = ''
    password = ''
    if request.POST:
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                resp['status']='success'
            else:
                resp['msg'] = "Incorrect username or password"
        else:
            resp['msg'] = "Incorrect username or password"
        return HttpResponse(json.dumps(resp),content_type='application/json')

    
def logoutuser(request):
    logout(request)
    return redirect('/')


@login_required
def home(request):
    hoy = timezone.now().date()
    now = timezone.now()

    # ── VENTAS HOY ──────────────────────────────────────────
    ventas_hoy = Sales.objects.filter(date_added__date=hoy)
    total_ventas_hoy = Decimal(str(ventas_hoy.aggregate(t=Sum('grand_total'))['t'] or 0))
    cantidad_ventas_hoy = ventas_hoy.count()
    ticket_promedio = (total_ventas_hoy / cantidad_ventas_hoy) if cantidad_ventas_hoy else Decimal('0')

    # ── ESTADO CAJA ─────────────────────────────────────────
    caja = Caja.get_instance()

    # ── CUENTA CORRIENTE ────────────────────────────────────
    clientes_con_deuda = []
    total_deuda = Decimal('0')
    for cliente in Cliente.objects.filter(activo=True):
        saldo = cliente.get_saldo_cuenta_corriente()
        if saldo < 0:
            clientes_con_deuda.append({'cliente': cliente, 'saldo': saldo})
            total_deuda += abs(saldo)
    clientes_con_deuda.sort(key=lambda x: x['saldo'])

    # ── PUNTO DE PEDIDO ─────────────────────────────────────
    productos_bajo_stock = Products.objects.filter(
        punto_pedido__gt=0,
        quantity__lte=F('punto_pedido')
    ).order_by('quantity')

    # ── COMPARATIVA MENSUAL ─────────────────────────────────
    primer_dia_mes = hoy.replace(day=1)
    dia_del_mes = hoy.day

    if hoy.month == 1:
        mes_ant = hoy.replace(year=hoy.year - 1, month=12, day=1)
    else:
        mes_ant = hoy.replace(month=hoy.month - 1, day=1)

    ultimo_dia_mes_ant = calendar.monthrange(mes_ant.year, mes_ant.month)[1]
    dia_corte_mes_ant = min(dia_del_mes, ultimo_dia_mes_ant)
    fin_periodo_mes_ant = mes_ant.replace(day=dia_corte_mes_ant)

    ventas_mes_actual = Decimal(str(Sales.objects.filter(
        date_added__date__gte=primer_dia_mes,
        date_added__date__lte=hoy
    ).aggregate(t=Sum('grand_total'))['t'] or 0))

    ventas_mes_anterior = Decimal(str(Sales.objects.filter(
        date_added__date__gte=mes_ant,
        date_added__date__lte=fin_periodo_mes_ant
    ).aggregate(t=Sum('grand_total'))['t'] or 0))

    diferencia_meses = ventas_mes_actual - ventas_mes_anterior
    if ventas_mes_anterior > 0:
        porcentaje_cambio = (diferencia_meses / ventas_mes_anterior) * 100
    else:
        porcentaje_cambio = Decimal('100') if ventas_mes_actual > 0 else Decimal('0')

    context = {
        'page_title': 'Home',
        'total_ventas_hoy': total_ventas_hoy,
        'cantidad_ventas_hoy': cantidad_ventas_hoy,
        'ticket_promedio': ticket_promedio,
        'caja': caja,
        'clientes_con_deuda': clientes_con_deuda[:5],
        'total_clientes_deuda': len(clientes_con_deuda),
        'total_deuda': total_deuda,
        'productos_bajo_stock': productos_bajo_stock[:8],
        'total_productos_alerta': productos_bajo_stock.count(),
        'ventas_mes_actual': ventas_mes_actual,
        'ventas_mes_anterior': ventas_mes_anterior,
        'diferencia_meses': diferencia_meses,
        'porcentaje_cambio': porcentaje_cambio,
        'dia_del_mes': dia_del_mes,
        'nombre_mes_actual': now.strftime('%B'),
        'nombre_mes_anterior': mes_ant.strftime('%B'),
    }
    return render(request, 'home.html', context)


def about(request):
    context = {
        'page_title':'About',
    }
    return render(request, 'about.html',context)



def register_user(request):
    if request.method == 'POST':
        resp = {"status": 'failed', 'msg': ''}
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        email = request.POST.get('email', '').strip()

        if username and password and confirm_password and email:
            if password != confirm_password:
                resp['msg'] = 'Passwords do not match'
            elif User.objects.filter(username=username).exists():
                resp['msg'] = 'Username already exists'
            elif User.objects.filter(email=email).exists():
                resp['msg'] = 'Email already exists'
            else:
                user = User.objects.create_user(username=username, password=password, email=email)
                user.save()
                resp['status'] = 'success'
        else:
            resp['msg'] = 'Please fill out all fields'
        
        return HttpResponse(json.dumps(resp), content_type='application/json')

    return render(request, 'core/register.html')



def password_reset_request(request):
    if request.method == 'POST':
        form = PasswordResetEmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            if '@' in email:
                associated_users = User.objects.filter(email=email)
                if associated_users.exists():
                    for user in associated_users:
                        subject = "Reset Your Password"
                        email_template_name = "core/password_reset_email.txt"
                        c = {
                            "email": email,
                            "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                            "user": user,
                            'token': default_token_generator.make_token(user),
                        }
                        email_content = render_to_string(email_template_name, c)
                        
                        try:
                            
                            print("Simulated Email Content:")
                            print(email_content)
                            
                            
                            messages.success(request, 'Se ha enviado un correo con instrucciones para resetear tu contraseña.')
                            return redirect('password_reset_confirm', uidb64=c['uid'], token=c['token'])
                        except BadHeaderError:
                            messages.error(request, 'Hubo un problema al enviar el correo. Por favor, intenta nuevamente más tarde.')
                            return redirect('password_reset_request')
                else:
                    messages.error(request, 'No hay usuarios asociados a este correo electrónico.')
            else:
                messages.error(request, 'Por favor, introduce un correo electrónico válido.')  
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
    else:
        form = PasswordResetEmailForm()
    return render(request=request, template_name="core/password_reset.html", context={"form": form})



def password_reset_confirm(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Tu contraseña ha sido actualizada con éxito.')
                return redirect('login')  # Redirigir al login después de cambiar la contraseña
        else:
            form = SetPasswordForm(user)
        
        # Aquí pasamos el nombre de usuario y el correo electrónico como contexto al template
        context = {
            'form': form,
            'username': user.username,
            'email': user.email,
        }
        return render(request, 'core/password_reset_confirm.html', context)
    else:
        messages.error(request, 'El enlace de reseteo de contraseña es inválido o ha expirado.')
        return redirect('password_reset_request')  # Redirigir de nuevo a la solicitud de reseteo de contraseña

