from rest_framework.routers import SimpleRouter

from .views import BinViewSet, PartViewSet, StockMovementViewSet

router = SimpleRouter(trailing_slash=False)
router.register("parts", PartViewSet, basename="parts")
router.register("bins", BinViewSet, basename="bins")
router.register("stock-movements", StockMovementViewSet, basename="stock-movements")
urlpatterns = router.urls
