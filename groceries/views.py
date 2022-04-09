from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from django.views.generic.detail import DetailView, SingleObjectMixin

from creditmanagement.models import Transaction
from dining.models import DiningList
from dining.views import DiningListMixin
from general.mail_control import send_templated_mail
from groceries.forms import PaymentCreateForm
from groceries.models import Payment, PaymentEntry


class PaymentsView(LoginRequiredMixin, TemplateView):
    template_name = 'groceries/payment_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Only pick payments not older than a month
        if 'all' not in self.request.GET:
            payments = Payment.objects.filter(created_at__gt=timezone.now() - timedelta(days=31))
        else:
            payments = Payment.objects.all()

        context.update({
            'pay_entries': PaymentEntry.objects.filter(
                user=self.request.user,
                external_name="",
                payment__in=payments).exclude(payment__receiver=self.request.user).order_by('-payment__created_at'),
            'receive_payments': payments.filter(receiver=self.request.user).order_by('-created_at'),
        })
        return context


class PaymentCreateView(LoginRequiredMixin, UserPassesTestMixin, DiningListMixin, TemplateView):
    template_name = 'groceries/payment_create.html'

    def test_func(self):
        # Business-rule: a dining list owner can always create a reimbursement,
        # even if the dining list is no longer adjustable.
        #
        # This is fine because the payer (not the receiver) always has to
        # initiate the payment.
        dining_list = self.get_object()  # type: DiningList
        return dining_list.is_owner(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dining_list = self.get_object()

        # Use earlier payment for initial info
        previous = Payment.objects.filter(receiver=self.request.user).order_by('created_at').last()
        if previous:
            initial = {
                'payment_link': previous.payment_link,
                'remarks': previous.remarks,
            }
        else:
            initial = None

        context.update({
            'form': PaymentCreateForm(instance=Payment(dining_list=dining_list, receiver=self.request.user),
                                      initial=initial),
        })
        return context

    def post(self, request, *args, **kwargs):
        form = PaymentCreateForm(data=request.POST,
                                 instance=Payment(dining_list=self.get_object(), receiver=self.request.user))
        if form.is_valid():
            with transaction.atomic():
                payment = form.save()  # type: Payment

                # Send mail to all internal users
                internals = [e.user for e in payment.entries.filter(external_name="")]
                send_templated_mail('mail/payment_entry_created', internals, {'payment': payment}, request)

                # Send different mail to externals
                for e in payment.entries.exclude(external_name=""):
                    send_templated_mail(
                        'mail/payment_entry_created_external',
                        e.user,
                        {'payment': payment, 'entry': e},
                        request)
            return redirect('groceries:payment-detail', pk=payment.pk)

        context = self.get_context_data()
        context['form'] = form
        return self.render_to_response(context)


class PaymentDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Payment

    def test_func(self):
        # Can only use this page if user is receiver
        payment = self.get_object()  # type: Payment
        return payment.receiver == self.request.user

    def post(self, request, *args, **kwargs):
        payment = self.get_object()
        entry = get_object_or_404(PaymentEntry,
                                  id=request.POST.get('entry_id'),
                                  payment=payment,  # Can only get entry for this payment
                                  transaction=None)  # And there should be no transaction (bc then paid is always True)
        paid = request.POST.get('paid')
        if paid == 'true':
            entry.paid = True
        elif paid == 'false':
            entry.paid = False
        entry.save()
        # Jump to table
        return redirect(reverse('groceries:payment-detail', kwargs={'pk': payment.pk}) + '#dinerTable')


class PayView(LoginRequiredMixin, SingleObjectMixin, View):
    """POSTing to this view will create a payment transaction for the current user for given Payment.

    Does not allow GET method.
    """
    model = Payment

    def post(self, request, *args, **kwargs):
        payment = self.get_object()  # type: Payment

        # Check if transactions are allowed
        if not payment.allow_transaction:
            return HttpResponseForbidden("Automatic transactions not allowed")

        # Find the entry on the payment for current user, make sure that it has paid=False and no transaction
        entry = get_object_or_404(PaymentEntry, payment=payment, user=request.user, external_name="", paid=False,
                                  transaction=None)

        # Check balance
        #
        # This has a race condition but that's probably not an issue in practice
        if request.user.account.balance < payment.cost_pp:
            return HttpResponseForbidden("Balance insufficient")

        with transaction.atomic():
            # Create payment transaction
            tx = Transaction.objects.create(source=request.user.account,
                                            target=payment.receiver.account,
                                            amount=payment.cost_pp,
                                            description="Groceries payment for {}".format(payment.dining_list),
                                            created_by=request.user)
            # Update entry
            entry.paid = True
            entry.transaction = tx
            entry.save()

            # Send mail to receiver to notify them that diner paid
            send_templated_mail('mail/payment_tx_created',
                                payment.receiver,
                                {'payment': payment, 'entry': entry},
                                request)
        return redirect('groceries:overview')
