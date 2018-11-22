from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import View
from django.db.models import Q
from django.core.exceptions import PermissionDenied
import datetime
import math

from .models import Association, UserMemberships
from CreditManagement.models import Transaction


class AssociationBaseView(View):
    context = {}

    def get(self, request, association=None):
        self.check_access(request, association)

    def post(self, request, association=None):
        self.check_access(request, association)

    @method_decorator(login_required)
    def check_access(self, request, association):
        """
        Check whether the logged in user has permissions to access the association page data.
        Raises 404 if association does not exist or 403 if not a boardmember of that association
        """
        self.association = get_object_or_404(Association, associationdetails__shorthand=association)
        # Check if user has access to this board
        if not request.user.groups.filter(id=self.association.id):
            raise PermissionDenied("You are not on the board of this association")

        self.context['association_short'] = association


class CreditsOverview(AssociationBaseView):
    template = "accounts/association_overview.html"

    def get(self, request, association=None, page=1):
        super(MembersOverview, self).get(request, association)


        length = 5
        lower_bound = length * (page - 1)
        upper_bound = length * page

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


class MembersOverview(AssociationBaseView):
    template = "accounts/association_members.html"

    @method_decorator(login_required)
    def get(self, request, association=None, page=1):
        super(MembersOverview, self).get(request, association)

        length = 3
        lower_bound = length * (page - 1)
        upper_bound = length * page

        memberships = UserMemberships.objects \
            .filter(Q(association=self.association)) \
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