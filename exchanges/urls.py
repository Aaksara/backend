from rest_framework.routers import DefaultRouter

from .views import ExchangeRequestViewSet

router = DefaultRouter()
router.register("exchanges", ExchangeRequestViewSet, basename="exchange")

urlpatterns = router.urls
