from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    # The fields to be used in displaying the User model in the admin interface
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('name', 'surname', 'phone_number', 'address', 'department', 'gender')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    # Add fields for adding/editing in the admin interface
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'surname', 'password1', 'password2', 'is_active', 'is_staff', 'is_superuser')}
        ),
    )

    # Define the list of displayed fields in the user listing
    list_display = ('email', 'name', 'surname', 'is_staff', 'is_active')
    search_fields = ('email', 'name', 'surname')
    ordering = ('email',)

# Register the custom admin class with the CustomUser model
admin.site.register(CustomUser, CustomUserAdmin)
