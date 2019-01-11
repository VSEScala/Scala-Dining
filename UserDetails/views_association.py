from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import View
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.db.models import prefetch_related_objects
import datetime

from .models import Association, UserMemberships, User
from CreditManagement.models import Transaction
from General.views import PageListView


class AssociationBaseView(View):
    context = {}

    def get(self, request, association_name=None):
        self.check_access(request, association_name)

    def post(self, request, association_name=None):
        self.check_access(request, association_name)

    @method_decorator(login_required)
    def check_access(self, request, association_name):
        """
        Check whether the logged in user has permissions to access the association page data.
        Raises 404 if association does not exist or 403 if not a boardmember of that association
        """
        self.association = get_object_or_404(Association, associationdetails__shorthand=association_name)
        # Check if user has access to this board
        if not request.user.groups.filter(id=self.association.id):
            raise PermissionDenied("You are not on the board of this association")

        self.context['association_name'] = association_name


class CreditsOverview(AssociationBaseView, PageListView):
    template = "accounts/association_overview.html"
    length = 4

    def get(self, request, association_name=None, page=1):
        super(CreditsOverview, self).get(request, association_name)

        # Set up the list display
        entries = Transaction.objects\
            .filter(Q(source_association=self.association) | Q(target_association=self.association))\
            .order_by('-date')
        super(CreditsOverview, self).set_up_list(entries, page)

        # Retrieve the current balance
        self.context['balance'] = self.association.get_credit_containing_instance()
        self.context['target'] = self.association
        self.context['tab'] = "credits"

        return render(request, self.template, self.context)


class MembersOverview(AssociationBaseView, PageListView):
    template = "accounts/association_members.html"

    def get(self, request, association_name=None, page=1):
        super(MembersOverview, self).get(request, association_name)

        # Set up the list display
        entries = User.objects \
            .filter(Q(usermemberships__association=self.association) & Q(usermemberships__is_verified=True))\


        super(MembersOverview, self).set_up_list(entries, page)
        prefetch_related_objects(self.context['entries'], 'usercredit')


        self.context['tab'] = "members"
        return render(request, self.template, self.context)


class MembersOverviewEdit(AssociationBaseView, PageListView):
    template = "accounts/association_members_edit.html"
    length = 5

    def get(self, request, association_name=None, page=1):
        super(MembersOverviewEdit, self).get(request, association_name)

        # Set up the list display
        entries = UserMemberships.objects \
            .filter(Q(association=self.association)) \
            .order_by('is_verified', 'verified_on', 'created_on')
        super(MembersOverviewEdit, self).set_up_list(entries, page)

        self.context['tab'] = "members"
        return render(request, self.template, self.context)

    def post(self, request, association_name=None, page=1):
        super(MembersOverviewEdit, self).post(request, association_name)

        for i in request.POST:
            # Seek if any of the validate buttons is pressed and change that state.
            if "validate" in i:
                string = i.split("-")
                self.alter_state(string[1], string[2])

        return self.get(request, association_name, page)


    def alter_state(self, verified, id=None):
        """
        Alter the state of the given usermembership
        :param verified: yes/no(!) if it should be verified or not.
        :param id: The id of the usermembershipobject
        """
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