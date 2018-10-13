from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('add', views.TransactionView.as_view(), name='Transaction'),
]