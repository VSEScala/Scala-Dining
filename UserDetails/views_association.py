from django.shortcuts import render
from django.http import *
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import View
from django.db.models import Q
import math

from .models import Association
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
