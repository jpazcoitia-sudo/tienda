from inventory.models import Products, Category
from purchase.models import Purchase, PurchaseProduct, Supplier

PurchaseProduct.objects.all().delete()
Purchase.objects.all().delete()
Products.objects.all().delete()
Category.objects.all().delete()
Supplier.objects.all().delete()
print("✅ Productos, categorías y proveedores eliminados")