from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import services
from .filters import ExchangeRequestFilter
from .models import ExchangeRequest, MeetupLocation
from .serializers import (
    AcceptExchangeSerializer,
    ExchangeRequestSerializer,
    MeetupLocationSerializer,
)


class MeetupLocationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MeetupLocation.objects.filter(is_active=True)
    serializer_class = MeetupLocationSerializer
    pagination_class = None
    search_fields = ["name", "description"]


class ExchangeRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ExchangeRequestSerializer
    filterset_class = ExchangeRequestFilter
    ordering_fields = ["created_at", "meetup_time"]

    def get_queryset(self):
        user = self.request.user
        return (
            ExchangeRequest.objects.filter(Q(requester=user) | Q(listing__seller=user))
            .select_related(
                "requester",
                "listing__book",
                "listing__seller",
                "offered_listing__book",
                "offered_listing__seller",
                "meetup_location",
            )
            .prefetch_related("listing__images", "offered_listing__images")
        )

    def perform_create(self, serializer):
        # The serializer checks for an active request, but two concurrent posts can both
        # pass that check; the database constraint is the final word.
        try:
            with transaction.atomic():
                serializer.save(requester=self.request.user)
        except IntegrityError:
            raise ValidationError(
                {"listing": "You already have an active request for this listing."}
            ) from None

    def _respond(self, exchange):
        """Serialize a freshly transitioned exchange with all related data loaded."""
        exchange = self.get_queryset().get(pk=exchange.pk)
        return Response(self.get_serializer(exchange).data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        serializer = AcceptExchangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exchange = services.accept(self.get_object().pk, request.user, **serializer.validated_data)
        return self._respond(exchange)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._respond(services.reject(self.get_object().pk, request.user))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._respond(services.cancel(self.get_object().pk, request.user))

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return self._respond(services.complete(self.get_object().pk, request.user))
