from rest_framework import serializers

from .models import Banner, PageSection


class PublicBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = ["id", "title", "target_url", "image", "alt_text", "placement"]


class PublicPageSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageSection
        fields = ["kind", "display_title", "anchor_id", "variant"]
