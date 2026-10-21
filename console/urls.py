from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("students", views.StudentViewSet, basename="admin-student")
router.register("slides", views.SlideViewSet, basename="admin-slide")

urlpatterns = [
    path("home-sections/", views.HomeSectionsView.as_view(), name="admin-home-sections"),
    path(
        "home-sections/<str:kind>/content/",
        views.HomeSectionContentView.as_view(),
        name="admin-home-section-content",
    ),
    path("campus/", views.CampusView.as_view(), name="admin-campus"),
    *router.urls,
]
