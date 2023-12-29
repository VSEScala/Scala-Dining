from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("credit/", include("creditmanagement.urls")),
    path("site/", include("general.urls")),
    path("reports/", include("reports.urls")),
    path("", include("dining.urls")),
    path("accounts/", include("userdetails.urls")),
    path("accounts/", include("allauth.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
