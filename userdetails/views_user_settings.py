from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import redirect
from django.views.generic import TemplateView

from userdetails.forms import AssociationLinkForm, UserForm


class SettingsProfileView(LoginRequiredMixin, TemplateView):
    template_name = "account/settings/settings_account.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "form": UserForm(instance=self.request.user),
                "association_links_form": AssociationLinkForm(self.request.user),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        user_form = UserForm(request.POST, instance=self.request.user)
        membership_form = AssociationLinkForm(self.request.user, request.POST)

        if user_form.is_valid() and membership_form.is_valid():
            with transaction.atomic():
                user_form.save()
                membership_form.save()
            return redirect("settings_account")

        # A form was not valid.
        context = self.get_context_data()
        context.update(
            {
                "form": user_form,
                "association_links_form": membership_form,
            }
        )
        return self.render_to_response(context)
