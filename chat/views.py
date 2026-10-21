from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
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
        return services.conversations_for(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation, created = services.open_conversation(
            serializer.validated_data["listing"], request.user
        )
        data = self.get_serializer(self.get_queryset().get(pk=conversation.pk)).data
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

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

    @action(detail=False, methods=["get"])
    def unread(self, request):
        """How many messages from others the user has not read, across all conversations."""
        return Response({"unread": services.unread_total(request.user)})

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        """Mark the other participant's messages as read."""
        marked = services.mark_read(self.get_object(), request.user)
        return Response({"marked_read": marked})
