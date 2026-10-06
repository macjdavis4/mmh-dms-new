from rest_framework.routers import SimpleRouter

from .invoice_api import InvoiceLineViewSet, InvoiceViewSet
from .views import BinViewSet, PartViewSet, StockMovementViewSet

router = SimpleRouter(trailing_slash=False)
router.register("parts", PartViewSet, basename="parts")
router.register("bins", BinViewSet, basename="bins")
router.register("stock-movements", StockMovementViewSet, basename="stock-movements")
router.register("parts-invoices", InvoiceViewSet, basename="parts-invoices")
router.register("parts-invoice-lines", InvoiceLineViewSet, basename="parts-invoice-lines")
urlpatterns = router.urls
