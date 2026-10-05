from rest_framework.routers import SimpleRouter

from .views import QuoteViewSet, SaleViewSet

router = SimpleRouter(trailing_slash=False)
router.register("quotes", QuoteViewSet, basename="quotes")
router.register("sales", SaleViewSet, basename="sales")
urlpatterns = router.urls
