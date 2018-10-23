from django.shortcuts import render
from django.http import *
from django.template import loader
from django.contrib.auth import authenticate, login, logout
from django.views import View
from .models import User
from .forms import RegisterUserForm, RegisterUserDetails, RegisterAssociationLinks
from django.urls import reverse

# Create your views here.

class LogInView(View):
    template = 'accounts/login.html'
    context = {}

    def get(self, request):
        if request.GET:
            self.context['next'] = request.GET['next']

        return render(request, self.template, self.context)

    def post(self, request, *args, **kwargs):
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)

                if self.context['next']:
                    return HttpResponseRedirect(self.context['next'])

                return HttpResponseRedirect(reverse('index'))

        self.context['sign_in_error'] = "The username/password did not match"

        return render(request, self.template, context)

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

        return HttpResponseRedirect(reverse('index'))

def log_out(request):
    logout(request)
    return HttpResponseRedirect(reverse('login'))
