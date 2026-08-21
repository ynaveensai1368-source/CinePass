from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Serves as the primary identity entity across CinePass.
    Supports email-based authentication and role-based authorization.
    """
    ROLE_CHOICES = (
        ('CUSTOMER', 'Customer'),
        ('THEATER_ADMIN', 'Theater Manager'),
        ('SITE_ADMIN', 'System Administrator'),
    )

    email = models.EmailField(
        unique=True,
        verbose_name="Email Address",
        help_text="Primary email address used for login and electronic ticket delivery."
    )
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name="Phone Number",
        help_text="User mobile number for SMS notifications and booking confirmations."
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='CUSTOMER',
        db_index=True,
        verbose_name="User Role",
        help_text="Role determining access permissions across customer portal and management dashboards."
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        default='avatars/default.png',
        blank=True,
        null=True,
        verbose_name="Profile Avatar",
        help_text="User profile picture stored in media directory."
    )
    city_preference = models.CharField(
        max_length=100,
        blank=True,
        default='Hyderabad',
        verbose_name="Preferred City",
        help_text="Default city used to filter showtimes and theater listings."
    )
    bio = models.TextField(
        max_length=500,
        blank=True,
        verbose_name="User Bio",
        help_text="Brief profile bio or user status message."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Account Created At",
        help_text="Timestamp when the account was registered."
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Account Updated At",
        help_text="Timestamp when user details were last updated."
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        full_name = self.get_full_name()
        return f"{full_name} ({self.email})" if full_name else self.email

    @property
    def is_theater_admin(self):
        return self.role in ['THEATER_ADMIN', 'SITE_ADMIN'] or self.is_superuser
