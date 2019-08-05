from django.http import HttpResponseRedirect
from django.shortcuts import reverse

from allauth.account.adapter import DefaultAccountAdapter


class ScalaAppAdapter(DefaultAccountAdapter):
    """
    A custom adapter that takes banned accounts into account
    """

    def respond_user_inactive(self, request, user):
        request.session['inactive_user_pk'] = user.pk

        return HttpResponseRedirect(
            reverse('account_inactive'))
