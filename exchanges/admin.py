from django.contrib import admin

from .models import ExchangeRequest, MeetupLocation


@admin.register(MeetupLocation)
class MeetupLocationAdmin(admin.ModelAdmin):
    list_display = ["name", "description", "is_active"]
    list_editable = ["is_active"]
    search_fields = ["name"]


@admin.register(ExchangeRequest)
class ExchangeRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "listing", "requester", "status", "meetup_location", "meetup_time"]
    list_filter = ["status", "meetup_location"]
    raw_id_fields = ["listing", "requester", "offered_listing"]
