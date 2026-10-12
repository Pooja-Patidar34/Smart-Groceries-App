from rest_framework import serializers
from accounts.models import User
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound
from .helper import get_client_ip
import stripe
from django.conf import settings
stripe.api_key = settings.STRIPE_SECRET_KEY


class LoginAPIViewSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)  

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("Email field is required.")
        return value
    

class SignUpSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        
        email = attrs.get("email")
        password = attrs.get("password")
        confirm_password = attrs.get("confirm_password")

        if not email:
            raise serializers.ValidationError("Email is required.")

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("Email already exists.")

        if password != confirm_password:
            raise serializers.ValidationError("Passwords do not match.")

        return attrs

    def create(self, validated_data):
        # Remove confirm_password (not stored in DB)
        validated_data.pop('confirm_password', None)
        
        # Ensure email exists
        email = validated_data.get('email')
        if not email:
            raise serializers.ValidationError({"email": "Email is required."})
        
        # Set username from email
        validated_data['username'] = email.split('@')[0]

        # Add client IP
        request = self.context.get('request')
        ip = get_client_ip(request) if request else None
        if ip:
            validated_data['ip_address'] = ip

        # Create user
        user = User.objects.create_user(**validated_data)

        # Create Stripe connected account
        account = stripe.Account.create(
            type="express",   
            country="IT",   
            email=user.email,
            capabilities={
                "transfers": {"requested": True},
                "card_payments": {"requested": True},  

            },
        )

        # Save connected account ID
        user.connected_id = account.id
        user.save()

        return user



class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, email):
        if not email:
            raise serializers.ValidationError('email is required.')
        
        return email


class VerifyForgotOtpSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField()

    def validate_email(self, email):
        if not email:
            raise serializers.ValidationError('email is required.')
        return email


    def validate_otp(self, otp):
        if not otp:
            raise serializers.ValidationError('otp is required.')
        return otp


class ForgotPasswordConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_new_password = serializers.CharField(write_only=True, required=True)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email not registered.")
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return attrs

    def create(self, validated_data):
        user = User.objects.get(email=validated_data['email'])
        user.set_password(validated_data['new_password'])
        user.save()
        return user

from .models import StaticData

class StaticDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaticData
        fields = ['id', 'title', 'type', 'content', 'created_at']
