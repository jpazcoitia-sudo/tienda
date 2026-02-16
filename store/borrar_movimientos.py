from pos.models import Sales, salesItems
from purchase.models import Purchase, PurchaseProduct
from pedidos.models import Pedido, PedidoItem
from finances.models import Caja, MovimientoCaja, CierreCaja

# 1. Borrar ventas
salesItems.objects.all().delete()
Sales.objects.all().delete()
print("✅ Ventas eliminadas")

# 2. Borrar compras
PurchaseProduct.objects.all().delete()
Purchase.objects.all().delete()
print("✅ Compras eliminadas")

# 3. Borrar pedidos
PedidoItem.objects.all().delete()
Pedido.objects.all().delete()
print("✅ Pedidos eliminados")

# 4. Resetear finanzas
MovimientoCaja.objects.all().delete()
CierreCaja.objects.all().delete()
print("✅ Movimientos y cierres eliminados")

# 5. Resetear saldos de caja
caja = Caja.get_instance()
caja.saldo_efectivo = 0
caja.saldo_banco = 0
caja.save()
print("✅ Saldos de caja reseteados a 0")

print("\n🎉 Base limpia! Stock de productos preservado")
