from django import forms
from django.contrib.auth.forms import  UserChangeForm
from .models import CustomUser



class CustomUserChangeForm(UserChangeForm):
    gender = forms.ChoiceField(choices=CustomUser.GENDER_CHOICES, widget=forms.RadioSelect)

    class Meta:
        model = CustomUser
        fields = ['name', 'surname', 'phone_number',  'department']


class CustomPasswordChangeForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label="Old Password")
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label="New Password")
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label="Confirm New Password")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old_password = self.cleaned_data.get("old_password")
        if not self.user.check_password(old_password):
            raise forms.ValidationError("Old password is incorrect.")
        return old_password

    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get("new_password1")
        new_password2 = cleaned_data.get("new_password2")

        if new_password1 and new_password2 and new_password1 != new_password2:
            raise forms.ValidationError("The new passwords do not match.")
        
        return cleaned_data

    def save(self, commit=True):
        new_password = self.cleaned_data.get("new_password1")
        self.user.set_password(new_password)
        if commit:
            self.user.save()
        return self.user
