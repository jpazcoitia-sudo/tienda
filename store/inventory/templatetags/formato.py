"""
Filtros de formato numerico para el sistema.
Criterio unico para toda la app (formato argentino):
  - Montos: $ + miles con punto + coma decimal + 2 decimales  -> $14.250,87
  - Cantidad unidad: entero -> 5
  - Cantidad fraccionable: 2 decimales con coma -> 5,50
"""
from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


def _formato_argentino(valor, decimales=2):
    """Convierte un numero al formato argentino: 14.250,87"""
    try:
        d = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return valor

    # Formatear con separador de miles (,) y decimal (.) al estilo US
    formato_us = f"{d:,.{decimales}f}"  # ej: 14,250.87

    # Intercambiar: coma <-> punto para formato argentino
    formato_ar = formato_us.replace(",", "X").replace(".", ",").replace("X", ".")
    return formato_ar


@register.filter(name="pesos")
def pesos(valor):
    """Monto con simbolo: $14.250,87"""
    if valor is None or valor == "":
        return "$0,00"
    return "$" + _formato_argentino(valor, 2)


@register.filter(name="pesos_sin_simbolo")
def pesos_sin_simbolo(valor):
    """Monto sin simbolo: 14.250,87"""
    if valor is None or valor == "":
        return "0,00"
    return _formato_argentino(valor, 2)


@register.filter(name="cantidad")
def cantidad(valor):
    """
    Cantidad inteligente:
      - Si es entero (5.00) -> '5'
      - Si tiene decimales (5.50) -> '5,50'
    """
    if valor is None or valor == "":
        return "0"
    try:
        d = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return valor

    if d == d.to_integral_value():
        # Es entero: mostrar sin decimales
        return str(int(d))
    else:
        # Tiene decimales: formato argentino con 2 decimales
        return _formato_argentino(d, 2)


@register.filter(name="cantidad_frac")
def cantidad_frac(valor):
    """Cantidad siempre con 2 decimales (para fraccionables): 5,50 / 8,00"""
    if valor is None or valor == "":
        return "0,00"
    return _formato_argentino(valor, 2)