from django.urls import path, include

from . import views
from .views import DayView, index

urlpatterns = [
    path('', index, name='index'),
    path('<int:day>/<int:month>/<int:year>/', include([
        path('', DayView.as_view(), name='day_view'),
        path('add/', views.NewSlotView.as_view(), name='new_slot'),
        path('<slug:identifier>/', include([
            path('', views.SlotInfoView.as_view(), name='slot_details'),
            path('list/', views.SlotListView.as_view(), name='slot_list'),
            path('allergy/', views.SlotAllergyView.as_view(), name='slot_allergy'),
            path('remove/', views.EntryRemoveView.as_view(), name='entry_remove'),
            path('remove/<id>/', views.EntryRemoveView.as_view(), name='entry_remove'),
            path('add/', views.EntryAddView.as_view(), name='entry_add'),
            path('join/', views.SlotJoinView.as_view(), name='entry_join'),
            path('change/', views.SlotInfoChangeView.as_view(), name='slot_change'),
        ])),
    ])),
]
