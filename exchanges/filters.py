import django_filters

from .models import ExchangeRequest


class ExchangeRequestFilter(django_filters.FilterSet):
    role = django_filters.ChoiceFilter(
        choices=[("requester", "Requester"), ("seller", "Seller")],
        method="filter_role",
        help_text="Only exchanges where the current user has this role.",
    )
    status = django_filters.MultipleChoiceFilter(choices=ExchangeRequest.Status.choices)

    class Meta:
        model = ExchangeRequest
        fields = ["listing"]

    def filter_role(self, queryset, name, value):
        user = self.request.user
        if value == "seller":
            return queryset.filter(listing__seller=user)
        return queryset.filter(requester=user)
