from django.contrib.admin import AdminSite


class MyAdminSite(AdminSite):
    """Custom admin site.

    See https://docs.djangoproject.com/en/2.1/ref/contrib/admin/#overriding-the-default-admin-site.
    """

    site_header = "Scala app administration"
    # site_title = "Scala app admin panel"
    # index_title = "Site administration"

    def has_permission(self, request):
        """Whether the request user has access to the admin site."""
        # Need to check for anonymous user because she doesn't have the has_admin_site_access method
        return not request.user.is_anonymous and request.user.has_admin_site_access()
