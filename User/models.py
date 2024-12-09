from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group, Permission
from django.db import models
from django.utils import timezone

class CustomUserManager(BaseUserManager):
    def create_user(self, email, surname, **extra_fields):
        if not email:
            raise ValueError('The Email must be set')
        if not surname:
            raise ValueError('The Surname must be set')
        
        extra_fields.setdefault('gender', 'male')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(surname.lower())
        user.save(using=self._db)
        return user

    def create_superuser(self, email, surname, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, surname, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=30)
    surname = models.CharField(max_length=30)
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    address = models.CharField(max_length=255)
    department = models.CharField(max_length=55)
    email = models.EmailField(unique=True)
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]
    gender = models.CharField(max_length=6, choices=GENDER_CHOICES, default='male')
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    groups = models.ManyToManyField(
        Group,
        related_name='customuser_groups',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='customuser_permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['surname']

    def __str__(self):
        return self.name
