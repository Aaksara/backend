from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.emails import EmailNotSent, send_verification_email
from accounts.tokens import revoke_refresh_tokens
from books.models import Listing
from cms import services as cms_services
from cms.models import HomeSection, Slide
from exchanges.models import ExchangeRequest, MeetupLocation
from utilities.permission import IsSuperAdmin

from . import serializers
from .exports import students_csv

User = get_user_model()

OPEN_LISTING_STATUSES = [Listing.Status.AVAILABLE, Listing.Status.RESERVED]


class SuperAdminMixin:
    permission_classes = [IsSuperAdmin]


class StudentViewSet(SuperAdminMixin, viewsets.ReadOnlyModelViewSet):
    """Every student account. Staff accounts are not students and are left out."""

    search_fields = ["full_name", "email", "student_id", "department"]
    filterset_fields = ["is_email_verified", "is_active"]
    ordering_fields = ["date_joined", "full_name", "last_login"]
    ordering = ["-date_joined"]

    def get_queryset(self):
        # distinct=True: the two joins would otherwise multiply each other's rows.
        return User.objects.filter(is_staff=False, is_superuser=False).annotate(
            listing_count=Count("listings", distinct=True),
            active_listing_count=Count(
                "listings", filter=Q(listings__status__in=OPEN_LISTING_STATUSES), distinct=True
            ),
            request_count=Count("exchange_requests", distinct=True),
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers.StudentDetailSerializer
        return serializers.StudentSerializer

    @action(detail=False)
    def summary(self, request):
        students = User.objects.filter(is_staff=False, is_superuser=False)
        week_ago = timezone.now() - timedelta(days=7)
        data = {
            "students": students.count(),
            "verified": students.filter(is_email_verified=True).count(),
            "suspended": students.filter(is_active=False).count(),
            "joined_this_week": students.filter(date_joined__gte=week_ago).count(),
            "active_sellers": students.filter(listings__status__in=OPEN_LISTING_STATUSES)
            .distinct()
            .count(),
            "active_buyers": students.filter(
                exchange_requests__status__in=ExchangeRequest.ACTIVE_STATUSES
            )
            .distinct()
            .count(),
        }
        return Response(serializers.DirectorySummarySerializer(data).data)

    @action(detail=False)
    def export(self, request):
        """The filtered roster as a CSV file, ignoring pagination."""
        students = self.filter_queryset(self.get_queryset())
        date = timezone.localdate().isoformat()
        response = HttpResponse(students_csv(students), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="students-{date}.csv"'
        return response

    def _set_active(self, is_active):
        student = self.get_object()
        student.is_active = is_active
        student.save(update_fields=["is_active"])
        if not is_active:
            # Signs the student out everywhere; access tokens expire within minutes.
            revoke_refresh_tokens(student)
        return Response(serializers.StudentDetailSerializer(self.get_object()).data)

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        return self._set_active(False)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        return self._set_active(True)

    @action(detail=True, methods=["post"], url_path="verify-email")
    def verify_email(self, request, pk=None):
        """Marks the email verified, e.g. after checking a student's ID in person."""
        student = self.get_object()
        student.is_email_verified = True
        student.save(update_fields=["is_email_verified"])
        return Response(serializers.StudentDetailSerializer(self.get_object()).data)

    @action(detail=True, methods=["post"], url_path="resend-verification")
    def resend_verification(self, request, pk=None):
        student = self.get_object()
        if student.is_email_verified:
            raise ValidationError("This student's email is already verified.")
        if not send_verification_email(student):
            raise EmailNotSent()
        return Response({"detail": f"Verification email sent to {student.email}."})


class SlideViewSet(SuperAdminMixin, viewsets.ModelViewSet):
    queryset = Slide.objects.all()
    serializer_class = serializers.SlideSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = None
    filter_backends = []

    def perform_create(self, serializer):
        # New slides go last, so they never jump ahead of ones already ordered.
        last = Slide.objects.aggregate(last=Max("position"))["last"]
        serializer.save(position=0 if last is None else last + 1)

    def perform_update(self, serializer):
        old_image = serializer.instance.image
        slide = serializer.save()
        if "image" in serializer.validated_data and old_image.name != slide.image.name:
            old_image.delete(save=False)

    def perform_destroy(self, instance):
        image = instance.image
        instance.delete()
        # Only remove the file once the row is gone for good.
        transaction.on_commit(lambda: image.delete(save=False))

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        """Saves the display order. Send `{"ids": [...]}` with every slide id."""
        serializer = serializers.SlideOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cms_services.reorder_slides(serializer.validated_data["ids"])
        return Response(self.get_serializer(self.get_queryset(), many=True).data)


class HomeSectionsView(SuperAdminMixin, APIView):
    """GET every home page section in order; PUT the full list to change order and visibility."""

    def get(self, request):
        sections = HomeSection.objects.all()
        return Response(serializers.HomeSectionSerializer(sections, many=True).data)

    def put(self, request):
        serializer = serializers.HomeSectionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cms_services.save_home_sections(serializer.validated_data["sections"])
        return self.get(request)


class MeetupLocationViewSet(
    SuperAdminMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """All meetup spots, including retired ones. Spots are retired, never deleted,
    because past exchanges still point at them."""

    serializer_class = serializers.MeetupLocationAdminSerializer
    pagination_class = None
    filter_backends = []
    queryset = MeetupLocation.objects.order_by("-is_active", "name")


class CampusView(SuperAdminMixin, APIView):
    """Campus-wide settings that come from the server configuration."""

    def get(self, request):
        return Response({"email_domains": settings.UNIVERSITY_EMAIL_DOMAINS})
