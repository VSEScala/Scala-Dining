from django import forms
from django.db.models import OuterRef, Exists


from UserDetails.models import Association, User
from .models import DiningList



class CreateSlotForm(forms.ModelForm):
    class Meta:
        model = DiningList
        fields = ('dish', 'association', 'max_diners', 'serve_time')

    def __init__(self, user, date, *args, **kwargs):
        super(CreateSlotForm, self).__init__(*args, **kwargs)

        # Filter dining lists on the current date
        dining_lists = DiningList.objects.filter(date=date, association=OuterRef('pk'))
        # Filter associations that the user is a member of and that do not have a dining list on the current date
        association_set = Association.objects.annotate(occupied=Exists(dining_lists)).filter(
            usermemberships__related_user=user, occupied=False)

        self.fields['association'] = forms.ModelChoiceField(queryset=association_set)
        self.user = user
        self.date = date

        if len(association_set) == 1:
            self.fields['association'].disabled = True
            self.fields['association'].initial = association_set[0].pk

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.claimed_by = self.user
        instance.date = self.date

        if commit:
            instance.save()

        return instance


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
