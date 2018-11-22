from django.shortcuts import render
from django.http import *
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import View
from django.db.models import Q
import datetime
import math

from .models import Association, UserMemberships
from CreditManagement.models import Transaction



class CreditsOverview(View):
    context = {}
    template = "accounts/association_overview.html"

    @method_decorator(login_required)
    def get(self, request, association=None, page=1):
        length = 5
        lower_bound = length * (page - 1)
        upper_bound = length * page

        association = Association.objects.get(associationdetails__shorthand=association)
        self.context['association'] = association

        transactions = Transaction.objects\
            .filter(Q(source_association=association) | Q(target_association=association))\
            .order_by('-date')

        self.context['entries'] = transactions[lower_bound:upper_bound]
        self.context['page'] = page
        self.context['pages'] = math.ceil(len(transactions) / length)
        self.context['target'] = association
        if self.context['pages'] > 1:
            self.context['show_page_navigation'] = True
            self.context['pages'] = range(1, self.context['pages']+1)

        self.context['balance'] = association.get_credit_containing_instance()

        return render(request, self.template, self.context)


class MembersOverview(View):
    context = {}
    template = "accounts/association_members.html"

    @method_decorator(login_required)
    def get(self, request, association=None, page=1):
        length = 3
        lower_bound = length * (page - 1)
        upper_bound = length * page

        association = Association.objects.get(associationdetails__shorthand=association)
        self.context['association'] = association

        memberships = UserMemberships.objects \
            .filter(Q(association=association)) \
            .order_by('is_verified', 'created_on')

        self.context['entries'] = memberships[lower_bound:upper_bound]
        self.context['page'] = page
        self.context['pages'] = math.ceil(len(memberships) / length)
        self.context['target'] = association
        if self.context['pages'] > 1:
            self.context['show_page_navigation'] = True
            self.context['pages'] = range(1, self.context['pages']+1)

        return render(request, self.template, self.context)
    # d[i] for i in d if b in i
    # request.POST[i]

    @method_decorator(login_required)
    def post(self, request, association=None, page=1):
        for i in request.POST:
            # Seek if any of the validate buttons is pressed and change that state.
            if "validate" in i:
                string = i.split("-")
                self.alter_state(string[1], string[2])

        return self.get(request, association, page)


    def alter_state(self, verified, id=None):
        print(verified)
        memberschip = UserMemberships.objects.get(id=id)
        if verified == "yes":
            if memberschip.is_verified:
                # Todo: message that this was already verified, an error occured
                return
            memberschip.is_verified = True
            memberschip.verified_on = datetime.datetime.now().date()
            memberschip.save()
        elif verified == "no":
            if not memberschip.is_verified and memberschip.verified_on is not None:
                # Todo: message that this was already verified, an error occured
                return
            memberschip.is_verified = False
            memberschip.verified_on = datetime.datetime.now().date()
            memberschip.save()