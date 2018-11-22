from django.urls import path
from . import views_association


urlpatterns = [
    path('credits', views_association.CreditsOverview.as_view(), name='association_credits'),
    path('credits/<int:page>', views_association.CreditsOverview.as_view(), name='association_credits'),
    path('members', views_association.MembersOverview.as_view(), name='association_members'),
    path('members/<int:page>', views_association.MembersOverview.as_view(), name='association_members'),
]
