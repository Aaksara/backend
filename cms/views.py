from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import HomeSection, Slide
from .serializers import PublicSlideSerializer


class PublishedSlideList(generics.ListAPIView):
    """Published slides in display order. Pick one slider with `?slider=home_hero`."""

    serializer_class = PublicSlideSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["slider"]
    queryset = Slide.objects.filter(is_published=True)


class VisibleHomeSectionList(APIView):
    """The kinds of the home page's visible sections, top to bottom, e.g. ["hero", ...]."""

    permission_classes = [AllowAny]

    def get(self, request):
        kinds = HomeSection.objects.filter(is_enabled=True).values_list("kind", flat=True)
        return Response(list(kinds))


class HomeContentView(APIView):
    """The text the admin has saved for each section, e.g. {"hero": {...}}. Sections left
    out use the site's built-in text."""

    permission_classes = [AllowAny]

    def get(self, request):
        saved = HomeSection.objects.exclude(content={}).values_list("kind", "content")
        return Response(dict(saved))
