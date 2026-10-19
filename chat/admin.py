from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["sender", "body", "created_at", "read_at"]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "listing", "buyer", "seller", "updated_at"]
    raw_id_fields = ["listing", "buyer", "seller", "last_message"]
    inlines = [MessageInline]
