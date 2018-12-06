from django import forms
from .models import DiningList, DiningEntry
from UserDetails.models import Association, User


def create_slot_form(user, info=None, date=None):
    """
    Return the slot form class specefied for the specific user
    :param date:
    :param info:
    :param user: The current user
    :return: The form
    """

    association_set = Association.objects.filter(usermemberships__related_user=user)

    class CreateSlotForm(forms.ModelForm):
        association = forms.ModelChoiceField(queryset=association_set)

        class Meta:
            model = DiningList
            fields = ('dish', 'association', 'max_diners', 'serve_time')

        def __init__(self, *args, **kwargs):
            super(CreateSlotForm, self).__init__(*args, **kwargs)

            if len(association_set) == 1:
                self.fields['association'].disabled = True
                self.fields['association'].initial = association_set[0].pk

        def save(self):
            data = self.cleaned_data
            dinner_list = DiningList(dish=data['dish'],
                                     claimed_by=user,
                                     association=data['association'],
                                     max_diners=data['max_diners'],
                                     date=date, )
            dinner_list.save()
            DiningEntry(dining_list=dinner_list,
                        user=user).save()

    return CreateSlotForm(info)


class DiningInfoForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        dining_list = kwargs.get("instance")
        super(DiningInfoForm, self).__init__(*args, **kwargs)

        query = User.objects.filter(diningentry__in=dining_list.diningentry_set.all())
        self.fields['purchaser'].queryset = query

    class Meta:
        model = DiningList
        fields = ['serve_time', 'min_diners', 'max_diners', 'sign_up_deadline', 'purchaser']

    def save(self):
        self.instance.save(update_fields=self.Meta.fields)


class DiningPaymentForm(forms.ModelForm):
    class Meta:
        model = DiningList
        fields = ['dish', 'dinner_cost_total', 'dinner_cost_single', 'tikkie_link']

    def __init__(self, *args, **kwargs):
        super(DiningPaymentForm, self).__init__(*args, **kwargs)

    def save(self):
        print("Save function")
        print(self.instance.dish)
        print(self.instance.dinner_cost_total)
        # If the single value has been added, recompute the total amount
        # also check if it has changed from earlier status
        old_list = DiningList.objects.get(id=self.instance.id)

        if 0 < self.instance.dinner_cost_single != old_list.dinner_cost_single:
            self.instance.dinner_cost_total = self.instance.dinner_cost_single * self.instance.diners

        print(self.instance.dinner_cost_single)
        print(self.instance.dinner_cost_total)
        self.instance.save(update_fields=self.Meta.fields)
