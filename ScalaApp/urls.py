from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path('admin/', admin.site.urls),
    path('credit/', include('CreditManagement.urls')),
    path('site/', include('General.urls')),
    path('', include('Dining.urls')),
    # Quadrivium OpenID Connect
    path('oidc/', include('mozilla_django_oidc.urls')),
    path('accounts/', include('UserDetails.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
