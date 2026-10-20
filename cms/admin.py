from django.contrib import admin

from .models import Banner, LayoutRelease, PageSection


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ["title", "placement", "status", "position", "updated_at"]
    list_filter = ["placement", "status"]
    search_fields = ["title", "target_url"]


@admin.register(PageSection)
class PageSectionAdmin(admin.ModelAdmin):
    list_display = ["display_title", "platform", "kind", "position", "is_enabled", "variant"]
    list_filter = ["platform", "kind", "is_enabled"]


@admin.register(LayoutRelease)
class LayoutReleaseAdmin(admin.ModelAdmin):
    list_display = ["platform", "version", "published_by", "published_at"]
    list_filter = ["platform"]
    readonly_fields = ["platform", "version", "published_by", "published_at"]

    def has_add_permission(self, request):
        # Releases are created by publishing from the admin console.
        return False
