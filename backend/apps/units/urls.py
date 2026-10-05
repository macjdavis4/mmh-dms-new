from rest_framework.routers import SimpleRouter

from .views import (
    HourReadingViewSet,
    OwnershipRecordViewSet,
    UnitChangeViewSet,
    UnitFileViewSet,
    UnitViewSet,
)

router = SimpleRouter(trailing_slash=False)
router.register("units", UnitViewSet, basename="units")
router.register("unit-files", UnitFileViewSet, basename="unit-files")
router.register("hour-readings", HourReadingViewSet, basename="hour-readings")
router.register("ownership-records", OwnershipRecordViewSet, basename="ownership-records")
router.register("unit-changes", UnitChangeViewSet, basename="unit-changes")
urlpatterns = router.urls
