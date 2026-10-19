from django.contrib import admin

from .models import Book, Listing, ListingImage


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ["title", "authors", "isbn_13", "published_year"]
    search_fields = ["title", "authors", "isbn_13", "isbn_10"]


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 0


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ["book", "seller", "listing_type", "price", "condition", "status", "created_at"]
    list_filter = ["status", "listing_type", "condition"]
    search_fields = ["book__title", "book__isbn_13", "seller__email", "course_code"]
    raw_id_fields = ["book", "seller"]
    inlines = [ListingImageInline]
