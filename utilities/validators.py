from django.conf import settings
from rest_framework import serializers


def validate_image_size(image):
    if image and image.size > settings.MAX_IMAGE_UPLOAD_BYTES:
        limit_mb = settings.MAX_IMAGE_UPLOAD_BYTES // (1024 * 1024)
        raise serializers.ValidationError(f"Images must be at most {limit_mb} MB.")
    return image


# What browsers can all show. Pillow reads more formats, e.g. TIFF, that would show as broken.
WEB_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")


def validate_web_image(image):
    # ImageField sets content_type from the format Pillow detects, not from the upload's header.
    if image and getattr(image, "content_type", None) not in WEB_IMAGE_TYPES:
        raise serializers.ValidationError("Upload a JPEG, PNG or WebP image.")
    return image
