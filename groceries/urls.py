from django.urls import path

from groceries import views

app_name = 'groceries'
urlpatterns = [
    path('', views.PaymentsView.as_view(), name='overview'),
    path('create/<int:pk>/', views.PaymentCreateView.as_view(), name='payment-create'),
    path('<int:pk>/', views.PaymentDetailView.as_view(), name='payment-detail'),
    path('pay/<int:pk>/', views.PayView.as_view(), name='pay'),
]
