from rest_framework.routers import SimpleRouter

from .views import LaborViewSet, MaintenancePlanViewSet, WorkOrderViewSet

router = SimpleRouter(trailing_slash=False)
router.register("work-orders", WorkOrderViewSet, basename="work-orders")
router.register("labor", LaborViewSet, basename="labor")
router.register("maintenance-plans", MaintenancePlanViewSet, basename="maintenance-plans")
urlpatterns = router.urls
