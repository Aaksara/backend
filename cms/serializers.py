from rest_framework import serializers

from .models import Slide


class PublicSlideSerializer(serializers.ModelSerializer):
    class Meta:
        model = Slide
        fields = ["id", "slider", "caption", "link", "image", "alt_text"]
