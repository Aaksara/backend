from django.conf import settings
from rest_framework import serializers


def validate_image_size(image):
    if image and image.size > settings.MAX_IMAGE_UPLOAD_BYTES:
        limit_mb = settings.MAX_IMAGE_UPLOAD_BYTES // (1024 * 1024)
        raise serializers.ValidationError(f"Images must be at most {limit_mb} MB.")
    return image
