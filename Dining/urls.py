from django.urls import path
from . import views


urlpatterns = [
    # ex: /dining/today/
    path('', views.IndexView.as_view(), name='index'),
    path('<int:day>/<int:month>/<int:year>/', views.IndexView.as_view(), name='day_view'),
    path('<int:day>/<int:month>/<int:year>/add', views.NewSlotView.as_view(), name='new_slot'),
    path('slot/<int:slot_id>/', views.SlotInfoView.as_view(), name='slot_details'),
    path('slot/<int:slot_id>/list', views.SlotListView.as_view(), name='slot_list'),
    path('slot/<int:slot_id>/allergy', views.SlotAllergyView.as_view(), name='slot_allergy'),
    path('slot/<int:slot_id>/remove', views.EntryRemoveView.as_view(), name='entry_remove'),
    path('slot/<int:slot_id>/remove/<id>', views.EntryRemoveView.as_view(), name='entry_remove'),
    path('slot/<int:slot_id>/add', views.EntryAddView.as_view(), name='entry_add'),
    path('slot/<int:slot_id>/add/<search>', views.EntryAddView.as_view(), name='entry_add'),
    path('slot/<int:slot_id>/join', views.SlotJoinView.as_view(), name='entry_join'),
    # This is unsafe and leads to errors e.g. when requesting /favicon.ico
    #path('<identifier>', views.SlotListView.as_view(), name='new_slot'),
]