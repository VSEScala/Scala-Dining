from django.urls import path
from . import views


urlpatterns = [
    # ex: /dining/today/
    path('', views.IndexView.as_view(), name='index'),
    path('<int:day>/<int:month>/<int:year>/', views.IndexView.as_view(), name='day_view'),
    path('<int:day>/<int:month>/<int:year>/add', views.NewSlotView.as_view(), name='new_slot'),
    path('<int:day>/<int:month>/<int:year>/<identifier>/', views.SlotInfoView.as_view(), name='slot_details'),
    path('<int:day>/<int:month>/<int:year>/<identifier>/list', views.SlotListView.as_view(), name='slot_list'),
    path('<int:day>/<int:month>/<int:year>/<identifier>/allergy', views.SlotAllergyView.as_view(), name='slot_allergy'),
    path('<int:day>/<int:month>/<int:year>/<identifier>/remove/',
         views.EntryRemoveView.as_view(), name='entry_remove'),
    path('<int:day>/<int:month>/<int:year>/<identifier>/remove/<id>',
         views.EntryRemoveView.as_view(), name='entry_remove'),
    path('<int:day>/<int:month>/<int:year>/<identifier>/add', views.EntryAddView.as_view(), name='entry_add'),
    path('<int:day>/<int:month>/<int:year>/<identifier>/add/<search>', views.EntryAddView.as_view(), name='entry_add'),
    path('<int:day>/<int:month>/<int:year>/<identifier>/join', views.SlotJoinView.as_view(), name='entry_join'),
    path('<identifier>', views.SlotListView.as_view(), name='new_slot'),
]