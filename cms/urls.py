from django.urls import path

from . import views

urlpatterns = [
    path("banners/", views.PublishedBannerList.as_view(), name="cms-banners"),
    path("layouts/<str:platform>/", views.LivePageSectionList.as_view(), name="cms-layout"),
]
