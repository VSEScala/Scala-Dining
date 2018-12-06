from django import forms
from django.db.models import OuterRef, Exists

from UserDetails.models import Association
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
