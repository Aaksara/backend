from django.contrib import admin

from .models import ExchangeRequest


@admin.register(ExchangeRequest)
class ExchangeRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "listing", "requester", "status", "responded_at", "completed_at"]
    list_filter = ["status"]
    raw_id_fields = ["listing", "requester", "offered_listing"]
