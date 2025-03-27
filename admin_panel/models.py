from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']
    
class Channel(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.category.name}"
    
    class Meta:
        verbose_name = 'Channel'
        verbose_name_plural = 'Channels'
        ordering = ['name']
    
class Message(models.Model):
    text = models.TextField()
    media = models.FileField(upload_to='messages/', null=True, blank=True)
    media_type = models.CharField(max_length=255, null=True, blank=True)
    telegram_message_id = models.CharField(max_length=255)
    telegram_channel_id = models.CharField(max_length=255)
    telegram_link = models.URLField(max_length=255)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.telegram_message_id} - {self.text[:10]}"
    
    class Meta:
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        ordering = ['created_at']
