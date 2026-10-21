from django.contrib.auth import get_user_model
from django.db.models import Count
from rest_framework import serializers

from books.models import Listing
from cms.models import HomeSection, Slide
from utilities.validators import validate_image_size

from .activity import Kind, Role

User = get_user_model()

ACTIVITY_PAGE_SIZE = 30
MAX_ACTIVITY = 500


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


def student_listings(student):
    """The student's listings, newest first, in the shape `StudentListingSerializer` needs."""
    return (
        student.listings.select_related("book")
        .annotate(request_count=Count("exchanges"))
        .order_by("-created_at")
    )


class StudentListingSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="book.title")
    authors = serializers.CharField(source="book.authors")
    # Exchange requests the listing has drawn, in any state.
    request_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Listing
        fields = [
            "id",
            "title",
            "authors",
            "course_code",
            "condition",
            "listing_type",
            "price",
            "status",
            "request_count",
            "created_at",
        ]


class StudentListingQuerySerializer(serializers.Serializer):
    # Blank means every status.
    status = serializers.ChoiceField(
        choices=Listing.Status.choices, required=False, allow_blank=True
    )


class ActivityQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(
        min_value=1, max_value=MAX_ACTIVITY, default=ACTIVITY_PAGE_SIZE
    )


class ActivityEventSerializer(serializers.Serializer):
    id = serializers.CharField()
    kind = serializers.ChoiceField(choices=[kind.value for kind in Kind])
    at = serializers.DateTimeField()
    role = serializers.ChoiceField(choices=[role.value for role in Role], allow_blank=True)
    listing_id = serializers.IntegerField(allow_null=True)
    book_title = serializers.CharField()
    counterpart = serializers.CharField()


class StudentDetailSerializer(StudentSerializer):
    recent_listings = serializers.SerializerMethodField()

    class Meta(StudentSerializer.Meta):
        fields = [*StudentSerializer.Meta.fields, "recent_listings"]

    def get_recent_listings(self, student):
        return StudentListingSerializer(student_listings(student)[:5], many=True).data


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
            "slider",
            "caption",
            "link",
            "image",
            "alt_text",
            "is_published",
            "position",
            "updated_at",
        ]
        read_only_fields = ["id", "position", "updated_at"]
        extra_kwargs = {
            "image": {"validators": [validate_image_size]},
            # Each slider has its own slides, so a new one must say where it goes.
            "slider": {"required": True},
        }


class SliderSerializer(serializers.Serializer):
    slider = serializers.ChoiceField(choices=Slide.Slider.choices)


class SlideOrderSerializer(serializers.Serializer):
    slider = serializers.ChoiceField(choices=Slide.Slider.choices)
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)


class HomeSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomeSection
        fields = ["kind", "is_enabled", "content"]
        # Content is saved per section (HomeSectionContentView), not with the order.
        read_only_fields = ["content"]
        # Each kind is sent once on purpose; HomeSectionsSerializer checks the whole list.
        extra_kwargs = {"kind": {"validators": []}}


class HomeSectionsSerializer(serializers.Serializer):
    sections = HomeSectionSerializer(many=True)

    def validate_sections(self, sections):
        kinds = [section["kind"] for section in sections]
        if sorted(kinds) != sorted(HomeSection.Kind.values):
            raise serializers.ValidationError("Send every home page section exactly once.")
        return sections
