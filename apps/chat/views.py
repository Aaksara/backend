from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .models import Conversation
from .serializers import ConversationSerializer, MessageSerializer


class ConversationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Buyer/seller conversations. Starting one that already exists returns it."""

    serializer_class = ConversationSerializer
    filterset_fields = ["listing"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Conversation.objects.none()
        user = self.request.user
        unread = Q(messages__read_at__isnull=True) & ~Q(messages__sender=user)
        return (
            Conversation.objects.filter(Q(buyer=user) | Q(seller=user))
            .select_related("listing__book", "buyer", "seller", "last_message")
            .annotate(unread_count=Count("messages", filter=unread))
            .order_by("-updated_at")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = serializer.validated_data["listing"]
        conversation, created = Conversation.objects.get_or_create(
            listing=listing, buyer=request.user, defaults={"seller": listing.seller}
        )
        data = self.get_serializer(self.get_queryset().get(pk=conversation.pk)).data
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(methods=["GET"], responses=MessageSerializer(many=True))
    @extend_schema(methods=["POST"], request=MessageSerializer, responses=MessageSerializer)
    @action(detail=True, methods=["get", "post"], serializer_class=MessageSerializer)
    def messages(self, request, pk=None):
        """GET: message history, newest first. POST: send a message."""
        conversation = self.get_object()
        if request.method == "POST":
            serializer = MessageSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            message = services.send_message(
                conversation, request.user, serializer.validated_data["body"]
            )
            return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)

        page = self.paginate_queryset(conversation.messages.all())
        return self.get_paginated_response(MessageSerializer(page, many=True).data)

    @extend_schema(request=None, responses={200: dict})
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        """Mark the other participant's messages as read."""
        marked = services.mark_read(self.get_object(), request.user)
        return Response({"marked_read": marked})
