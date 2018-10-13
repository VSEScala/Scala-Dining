from django.urls import path
from . import views_association


urlpatterns = [
    path('credits', views_association.CreditsOverview.as_view(), name='association_credits'),
    path('credits/<int:page>', views_association.CreditsOverview.as_view(), name='association_credits'),
]
