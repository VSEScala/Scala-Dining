from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import TemplateView

from userdetails.forms import UserForm, DiningProfileForm, AssociationLinkForm


class SettingsProfileView(LoginRequiredMixin, TemplateView):
    template_name = "account/settings/settings_account.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'user_form': UserForm(instance=self.request.user),
            'dining_form': DiningProfileForm(instance=self.request.user.userdiningsettings),
            'association_links_form': AssociationLinkForm(self.request.user),
        })
        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data()

        context.update({
            'user_form': UserForm(request.POST, instance=self.request.user),
            'dining_form': DiningProfileForm(request.POST, instance=self.request.user.userdiningsettings),
            'association_links_form': AssociationLinkForm(self.request.user, request.POST),
        })

        forms = context['user_form'], context['dining_form'], context['association_links_form']
        if all(form.is_valid() for form in forms):
            for form in forms:
                form.save()
            messages.success(request, "Account saved")

            return redirect('settings_account')

        return self.render_to_response(context)
