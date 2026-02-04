from rest_framework.filters import SearchFilter

class MinimalSearchFilter(SearchFilter):
    min_length = 3
    def filter_queryset(self, request, queryset, view):
        search = request.query_params.get(self.search_param, None)
        if search and len(search) < self.min_length:
            return queryset.none()
        return super().filter_queryset(request, queryset, view)