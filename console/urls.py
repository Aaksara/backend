from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("students", views.StudentViewSet, basename="admin-student")
router.register("banners", views.BannerViewSet, basename="admin-banner")
router.register("meetup-locations", views.MeetupLocationViewSet, basename="admin-meetup-location")

urlpatterns = [
    path("layouts/<str:platform>/", views.LayoutView.as_view(), name="admin-layout"),
    path("campus/", views.CampusView.as_view(), name="admin-campus"),
    *router.urls,
]
