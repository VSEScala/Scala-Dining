from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError, BadRequest
from django.db import transaction
from django.forms import DecimalField
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView
from django.views.generic.detail import DetailView

from dining.views import DiningListMixin
from groceries.forms import PaymentCreateForm
from groceries.models import Payment, PaymentEntry


class PaymentsView(LoginRequiredMixin, TemplateView):
    template_name = 'groceries/payment_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'pay_entries': PaymentEntry.objects.filter(user=self.request.user, external_name="").exclude(
                payment__receiver=self.request.user).order_by('-payment__created_at'),
            'receive_payments': Payment.objects.filter(receiver=self.request.user).order_by('-created_at'),
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

    def has_cost(self) -> bool:
        """Returns if a total cost value is provided by the user."""
        return 'total_cost' in self.request.GET

    def get_total_cost(self) -> Decimal:
        """Validates and returns the total cost from the GET parameters."""
        # Use a DecimalField to let Django do the validation for us
        field = DecimalField(min_value=Decimal('0.01'), max_digits=8, decimal_places=2)
        try:
            return field.clean(self.request.GET['total_cost'])
        except ValidationError as e:
            raise BadRequest(e)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dining_list = self.get_object()

        if self.has_cost():
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
                'form': PaymentCreateForm(instance=Payment(dining_list=dining_list, receiver=self.request.user,
                                                           total_cost=self.get_total_cost()), initial=initial),
                'entries': dining_list.entries.order_by('external_name', 'user__first_name', 'user__last_name')
            })
        return context

    def post(self, request, *args, **kwargs):
        if not self.has_cost():
            raise BadRequest("Cost unknown")
        form = PaymentCreateForm(data=request.POST,
                                 instance=Payment(dining_list=self.get_object(), receiver=self.request.user,
                                                  total_cost=self.get_total_cost()))
        if form.is_valid():
            with transaction.atomic():
                payment = form.save()
                # TODO: send mail
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
        return redirect('groceries:payment-detail', pk=payment.pk)
