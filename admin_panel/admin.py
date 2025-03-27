from django.contrib import admin
from .models import Category, Channel, Message

# Register your models here.
admin.site.register(Category)
admin.site.register(Channel)
admin.site.register(Message)

