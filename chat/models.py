from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import os
import secrets

def get_upload_path(instance, filename):
    """ Helper function to determine upload path for files. """
    if instance.recipient_group:
        return os.path.join('group_files', str(instance.recipient_group.id), filename)
    if instance.recipient_channel:
        return os.path.join('channel_files', str(instance.recipient_channel.id), filename)
    if instance.recipient_user:
        user_ids = sorted([instance.sender.id, instance.recipient_user.id])
        return os.path.join('dm_files', f"{user_ids[0]}_{user_ids[1]}", filename)
    return os.path.join('misc_files', filename)

class Contact(models.Model):
    user = models.ForeignKey(User, related_name='contacts', on_delete=models.CASCADE)
    contact_user = models.ForeignKey(User, related_name='contact_of', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('user', 'contact_user')

class Bot(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bots')
    user_account = models.OneToOneField(User, on_delete=models.CASCADE, related_name='bot_profile')
    token = models.CharField(max_length=64, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_hex(32)
        super().save(*args, **kwargs)
    def __str__(self):
        return self.user_account.username

class BotScript(models.Model):
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name='scripts')
    trigger = models.CharField(max_length=255)
    response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class Group(models.Model):
    name = models.CharField(max_length=100)
    creator = models.ForeignKey(User, related_name='created_groups', on_delete=models.CASCADE)
    members = models.ManyToManyField(User, through='GroupMember', related_name='chat_groups')
    bots = models.ManyToManyField(Bot, related_name='groups', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Channel(models.Model):
    name = models.CharField(max_length=100)
    creator = models.ForeignKey(User, related_name='created_channels', on_delete=models.CASCADE)
    members = models.ManyToManyField(User, through='ChannelMember', related_name='chat_channels')
    bots = models.ManyToManyField(Bot, related_name='channels', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class MemberPermissions(models.Model):
    can_add_users = models.BooleanField(default=False)
    can_delete_messages = models.BooleanField(default=False)
    can_manage_item = models.BooleanField(default=False) # Edit name, etc.
    can_promote_members = models.BooleanField(default=False)
    class Meta:
        abstract = True

class GroupMember(MemberPermissions):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_admin = models.BooleanField(default=False)
    class Meta:
        unique_together = ('group', 'user')

class ChannelMember(MemberPermissions):
    can_send_messages = models.BooleanField(default=False)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_admin = models.BooleanField(default=False)
    class Meta:
        unique_together = ('channel', 'user')

class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', null=True, blank=True)
    recipient_group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    recipient_channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    text = models.TextField(null=True, blank=True)
    file = models.FileField(upload_to=get_upload_path, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    class Meta:
        ordering = ['timestamp']