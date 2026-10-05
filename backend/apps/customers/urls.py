from rest_framework.routers import SimpleRouter

from .views import AddressViewSet, ContactViewSet, CustomerViewSet

router = SimpleRouter(trailing_slash=False)
router.register("customers", CustomerViewSet, basename="customers")
router.register("contacts", ContactViewSet, basename="contacts")
router.register("addresses", AddressViewSet, basename="addresses")
urlpatterns = router.urls
