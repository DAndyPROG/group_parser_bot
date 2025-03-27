from django import forms
from .models import Channel, Category, Message

class ChannelForm(forms.ModelForm):
    class Meta:
        model = Channel
        fields = ['name', 'url', 'category', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'url': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'category': forms.Select(attrs={'class': 'form-control', 'required': True}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Channel name',
            'url': 'Channel link',
            'category': 'Category',
            'is_active': 'Status',
        }
        help_texts = {
            'is_active': 'Check if the channel should be active',
        }
        error_messages = {
            'name': {
                'required': "This field is required.",
                'max_length': 'Channel name is too long.'
            },
            'url': {
                'required': "This field is required.",
                'invalid': 'Enter a valid URL.'
            },
            'category': {
                'required': "This field is required.",
            },
        }

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
        }   
        labels = {
            'name': 'Category name',
        }
        help_texts = {
            'name': 'Enter the category name',
        }
        error_messages = {
            'name': {
                'required': "This field is required.",
                'max_length': 'Category name is too long.'
            },
        }

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['text', 'media', 'channel']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'media': forms.FileInput(attrs={'class': 'form-control'}),
            'channel': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'text': 'Message text',
            'media': 'Media',   
            'channel': 'Channel',
        }
        help_texts = {
            'text': 'Enter the message text',
            'media': 'Add media file',
            'channel': 'Select the channel',
        }   
        error_messages = {
            'text': {
                'required': "This field is required.",
            },
            'channel': {
                'required': "This field is required.",
            },
        }

