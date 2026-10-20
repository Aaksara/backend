from django.contrib import admin

from .models import HomeSection, Slide


@admin.register(Slide)
class SlideAdmin(admin.ModelAdmin):
    list_display = ["caption", "slider", "is_published", "position", "updated_at"]
    list_filter = ["slider", "is_published"]
    search_fields = ["caption", "link"]


@admin.register(HomeSection)
class HomeSectionAdmin(admin.ModelAdmin):
    list_display = ["kind", "position", "is_enabled"]

    def has_add_permission(self, request):
        # One row per kind, created by migrations.
        return False

    def has_delete_permission(self, request, obj=None):
        return False
