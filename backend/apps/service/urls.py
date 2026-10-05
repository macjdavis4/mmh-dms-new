from rest_framework.routers import SimpleRouter

from .views import LaborViewSet, WorkOrderViewSet

router = SimpleRouter(trailing_slash=False)
router.register("work-orders", WorkOrderViewSet, basename="work-orders")
router.register("labor", LaborViewSet, basename="labor")
urlpatterns = router.urls
