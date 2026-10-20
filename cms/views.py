from rest_framework import generics
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny

from .models import Banner, PageSection, Platform
from .serializers import PublicBannerSerializer, PublicPageSectionSerializer


class PublishedBannerList(generics.ListAPIView):
    """Published banners in display order. Filter with `?placement=hero`."""

    serializer_class = PublicBannerSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    filterset_fields = ["placement"]
    queryset = Banner.objects.filter(status=Banner.Status.PUBLISHED)


class LivePageSectionList(generics.ListAPIView):
    """The visible sections of a platform's home page, top to bottom."""

    serializer_class = PublicPageSectionSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    filter_backends = []

    def get_queryset(self):
        platform = self.kwargs["platform"]
        if platform not in Platform.values:
            raise NotFound(f"Unknown platform. Use one of: {', '.join(Platform.values)}.")
        return PageSection.objects.filter(platform=platform, is_enabled=True)
