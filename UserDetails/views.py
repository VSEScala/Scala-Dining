from django.shortcuts import render
from django.http import *
from django.contrib.auth import login, logout
from django.views import View
from .models import User
from .forms import RegisterUserForm, RegisterUserDetails, RegisterAssociationLinks
from django.urls import reverse


class RegisterView(View):
    def get(self, request):
        account_form = RegisterUserForm()
        account_detail_form = RegisterUserDetails()
        associationlink_form = RegisterAssociationLinks()

        context = {
            'account_form': account_form,
            'account_detail_form': account_detail_form,
            'associationlink_form': associationlink_form,
        }
        return render(request, 'accounts/register.html', context)

    def post(self, request, *args, **kwargs):
        account_form = RegisterUserForm(request.POST)
        account_detail_form = RegisterUserDetails(request.POST)
        associationlink_form = RegisterAssociationLinks(request.POST)

        context = {
            'account_form': account_form,
            'account_detail_form': account_detail_form,
            'associationlink_form': associationlink_form,
        }

        if not account_form.is_valid():
            return render(request, 'accounts/register.html', context)
        if not account_detail_form.is_valid():
            return render(request, 'accounts/register.html', context)
        if not associationlink_form.is_valid():
            return render(request, 'accounts/register.html', context)

        # User is valid, safe it to the server
        user = account_form.save()
        user = User.objects.get(pk=user.pk)
        account_detail_form.save_as(user)
        associationlink_form.create_links_for(user)
        
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        return HttpResponseRedirect(reverse('index'))
