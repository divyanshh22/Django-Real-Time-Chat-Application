from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, ProfilePic


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('username', 'email', 'is_staff', 'is_active', 'is_online', 'last_seen')
    search_fields = ('username', 'email')
    list_filter = ('is_staff', 'is_active', 'is_online')
    fieldsets = UserAdmin.fieldsets + (
        ('Extra Fields', {'fields': ('is_online', 'last_seen')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Extra Fields', {'fields': ('is_online', 'last_seen')}),
    )


@admin.register(ProfilePic)
class ProfilePicAdmin(admin.ModelAdmin):
    list_display = ('user', 'profile_pic', 'joined_date')
    search_fields = ('user__username',)
