from django.contrib.auth import get_user_model
from rest_framework import serializers

from books.models import Listing
from cms.models import HomeSection, Slide
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


class SlideSerializer(serializers.ModelSerializer):
    class Meta:
        model = Slide
        fields = [
            "id",
            "caption",
            "link",
            "image",
            "alt_text",
            "is_published",
            "position",
            "updated_at",
        ]
        read_only_fields = ["id", "position", "updated_at"]
        extra_kwargs = {"image": {"validators": [validate_image_size]}}


class SlideOrderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)


class HomeSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomeSection
        fields = ["kind", "is_enabled"]
        # Each kind is sent once on purpose; HomeSectionsSerializer checks the whole list.
        extra_kwargs = {"kind": {"validators": []}}


class HomeSectionsSerializer(serializers.Serializer):
    sections = HomeSectionSerializer(many=True)

    def validate_sections(self, sections):
        kinds = [section["kind"] for section in sections]
        if sorted(kinds) != sorted(HomeSection.Kind.values):
            raise serializers.ValidationError("Send every home page section exactly once.")
        return sections


class MeetupLocationAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetupLocation
        fields = ["id", "name", "description", "is_active"]
