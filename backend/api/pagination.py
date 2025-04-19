from rest_framework.pagination import PageNumberPagination

class CustomPageNumberPagination(PageNumberPagination):
    """
    Custom pagination class that allows the client to specify the page size
    using the 'limit' query parameter.
    """
    page_size_query_param = 'limit'
    # PAGE_SIZE is set globally in settings.REST_FRAMEWORK['PAGE_SIZE']
    # You could set a default page_size here as well if needed:
    # page_size = 6
    # max_page_size = 100 # Optional: Set a maximum page size