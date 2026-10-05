from rest_framework.routers import SimpleRouter

from .views import BinViewSet, PartViewSet

router = SimpleRouter(trailing_slash=False)
router.register("parts", PartViewSet, basename="parts")
router.register("bins", BinViewSet, basename="bins")
urlpatterns = router.urls
