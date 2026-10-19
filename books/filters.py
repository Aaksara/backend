import django_filters

from .isbn import InvalidISBN, to_isbn13
from .models import Listing


class ListingFilter(django_filters.FilterSet):
    isbn = django_filters.CharFilter(method="filter_isbn")
    condition = django_filters.MultipleChoiceFilter(choices=Listing.Condition.choices)
    listing_type = django_filters.MultipleChoiceFilter(choices=Listing.ListingType.choices)
    status = django_filters.MultipleChoiceFilter(choices=Listing.Status.choices)
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    course_code = django_filters.CharFilter(lookup_expr="iexact")
    author = django_filters.CharFilter(field_name="book__authors", lookup_expr="icontains")
    title = django_filters.CharFilter(field_name="book__title", lookup_expr="icontains")

    class Meta:
        model = Listing
        fields = ["book", "seller", "preferred_location"]

    def filter_isbn(self, queryset, name, value):
        try:
            return queryset.filter(book__isbn_13=to_isbn13(value))
        except InvalidISBN:
            return queryset.none()
