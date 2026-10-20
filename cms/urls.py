from django.urls import path

from . import views

urlpatterns = [
    path("slides/", views.PublishedSlideList.as_view(), name="cms-slides"),
    path("home-sections/", views.VisibleHomeSectionList.as_view(), name="cms-home-sections"),
]
