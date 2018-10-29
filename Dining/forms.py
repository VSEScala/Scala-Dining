from django import forms
from .models import DiningList, DiningEntry
from UserDetails.models import Association

def create_slot_form(user, info=None, date=None):
    """
    Return the slot form class specefied for the specific user
    :param user: The current user
    :return: The form
    """

    association_set = Association.objects.filter(usermemberships__related_user=user)

    class CreateSlotForm(forms.ModelForm):
        association = forms.ModelChoiceField(queryset=association_set)

        class Meta:
            model = DiningList
            fields = ('dish', 'association', 'max_diners')

        def __init__(self, *args, **kwargs):
            super(CreateSlotForm, self).__init__(*args, **kwargs)

            if len(association_set) == 1:
                self.fields['association'].disabled = True
                self.fields['association'].initial = 1

        def save(self):
            data = self.cleaned_data
            dinner_list = DiningList(dish=data['dish'],
                                     claimed_by=user,
                                     association=data['association'],
                                     max_diners=data['max_diners'],
                                     date=date,)
            dinner_list.save()
            DiningEntry(dining_list=dinner_list,
                        user=user).save()

    return CreateSlotForm(info)
