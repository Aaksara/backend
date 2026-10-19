from rest_framework.routers import DefaultRouter

from .views import ExchangeRequestViewSet, MeetupLocationViewSet

router = DefaultRouter()
router.register("meetup-locations", MeetupLocationViewSet, basename="meetup-location")
router.register("exchanges", ExchangeRequestViewSet, basename="exchange")

urlpatterns = router.urls
