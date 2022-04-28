from django.urls import path, include

from . import views
from .views import DayView, index

urlpatterns = [
    path('', index, name='index'),
    path('csv/', views.DailyDinersCSVView.as_view(), name="diners_csv"),
    path('<int:year>/<int:month>/<int:day>/', include([
        path('', DayView.as_view(), name='day_view'),
        path('add/', views.NewSlotView.as_view(), name='new_slot'),
    ])),
    path('lists/<int:pk>/', include([
        path('', views.SlotInfoView.as_view(), name='slot_details'),
        path('diners/', views.SlotListView.as_view(), name='slot_list'),
        path('allergies/', views.SlotAllergyView.as_view(), name='slot_allergy'),
        path('entry/add/', views.EntryAddView.as_view(), name='entry_add'),
        path('change/', views.DiningListChangeView.as_view(), name='slot_change'),
        path('delete/', views.DiningListDeleteView.as_view(), name='slot_delete'),
    ])),
    path('entries/<int:pk>/delete/', views.EntryDeleteView.as_view(), name='entry_delete'),
]
