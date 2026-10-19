from rest_framework.routers import DefaultRouter

from .views import BookViewSet, ListingViewSet

router = DefaultRouter()
router.register("books", BookViewSet, basename="book")
router.register("listings", ListingViewSet, basename="listing")

urlpatterns = router.urls
