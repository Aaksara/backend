from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import HomeSection, Slide
from .serializers import PublicSlideSerializer


class PublishedSlideList(generics.ListAPIView):
    """The home page's published slides, in display order."""

    serializer_class = PublicSlideSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    filter_backends = []
    queryset = Slide.objects.filter(is_published=True)


class VisibleHomeSectionList(APIView):
    """The kinds of the home page's visible sections, top to bottom, e.g. ["hero", ...]."""

    permission_classes = [AllowAny]

    def get(self, request):
        kinds = HomeSection.objects.filter(is_enabled=True).values_list("kind", flat=True)
        return Response(list(kinds))
