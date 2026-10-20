from django.contrib.auth import get_user_model
from rest_framework import serializers

from books.models import Listing
from cms.models import Banner, PageSection
from exchanges.models import MeetupLocation
from utilities.validators import validate_image_size

User = get_user_model()


class StudentSerializer(serializers.ModelSerializer):
    listing_count = serializers.IntegerField(read_only=True)
    active_listing_count = serializers.IntegerField(read_only=True)
    request_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "student_id",
            "department",
            "phone",
            "is_email_verified",
            "is_active",
            "date_joined",
            "last_login",
            "listing_count",
            "active_listing_count",
            "request_count",
        ]


class StudentListingSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="book.title")

    class Meta:
        model = Listing
        fields = ["id", "title", "course_code", "condition", "listing_type", "price", "status"]


class StudentDetailSerializer(StudentSerializer):
    recent_listings = serializers.SerializerMethodField()

    class Meta(StudentSerializer.Meta):
        fields = [*StudentSerializer.Meta.fields, "recent_listings"]

    def get_recent_listings(self, student):
        listings = student.listings.select_related("book").order_by("-created_at")[:5]
        return StudentListingSerializer(listings, many=True).data


class DirectorySummarySerializer(serializers.Serializer):
    students = serializers.IntegerField()
    verified = serializers.IntegerField()
    suspended = serializers.IntegerField()
    joined_this_week = serializers.IntegerField()
    active_sellers = serializers.IntegerField()
    active_buyers = serializers.IntegerField()


class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = [
            "id",
            "title",
            "target_url",
            "image",
            "image_width",
            "image_height",
            "alt_text",
            "placement",
            "status",
            "position",
            "updated_at",
        ]
        read_only_fields = ["id", "image_width", "image_height", "position", "updated_at"]
        extra_kwargs = {"image": {"validators": [validate_image_size]}}


class BannerOrderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)


class PageSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageSection
        fields = ["id", "kind", "display_title", "anchor_id", "is_enabled", "variant"]
        read_only_fields = ["id"]
        # Uniqueness is checked across the whole submitted list in LayoutPublishSerializer.
        extra_kwargs = {"anchor_id": {"validators": []}}


class LayoutSerializer(serializers.Serializer):
    platform = serializers.CharField()
    version = serializers.IntegerField()
    published_at = serializers.DateTimeField(allow_null=True)
    published_by = serializers.CharField(allow_null=True)
    sections = PageSectionSerializer(many=True)


class LayoutPublishSerializer(serializers.Serializer):
    base_version = serializers.IntegerField(min_value=0)
    sections = PageSectionSerializer(many=True)

    def validate_sections(self, sections):
        anchors = [section["anchor_id"] for section in sections]
        repeated = sorted({anchor for anchor in anchors if anchors.count(anchor) > 1})
        if repeated:
            raise serializers.ValidationError(f"Anchor IDs must be unique: {', '.join(repeated)}.")
        return sections


class MeetupLocationAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetupLocation
        fields = ["id", "name", "description", "is_active"]
