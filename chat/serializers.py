from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Message, Contact


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class ContactSerializer(serializers.ModelSerializer):
    contact_user = UserSerializer(read_only=True)
    contact_user_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Contact
        fields = ['id', 'contact_user', 'contact_user_id']

    def create(self, validated_data):
        contact_user_id = validated_data.pop('contact_user_id')
        user = self.context['request'].user
        contact_user = User.objects.get(id=contact_user_id)
        contact, created = Contact.objects.get_or_create(user=user, contact_user=contact_user)
        return contact


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'sender', 'text', 'timestamp', 'is_deleted']