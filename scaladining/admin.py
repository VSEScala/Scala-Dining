from django.contrib.admin import AdminSite


class MyAdminSite(AdminSite):
    """Custom admin site for some minor branding."""
    site_header = "Scala app administration"

    # site_title = "Scala app admin panel"
    # index_title = "Site administration"

    def has_permission(self, request):
        """Whether the request user has access to the admin site.

        We don't use the staff/permissions system, instead a user simply has
        access whenever they are superuser.
        """
        return request.user.is_active and request.user.is_superuser
