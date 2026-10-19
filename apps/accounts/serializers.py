from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.core.validators import validate_image_size

from .tokens import email_verification_token
from .validators import validate_university_email

User = get_user_model()


def _check_password_strength(password, user, field):
    try:
        password_validation.validate_password(password, user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({field: exc.messages}) from None


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "student_id", "department", "phone", "password"]
        read_only_fields = ["id"]

    def validate_email(self, value):
        value = value.lower().strip()
        validate_university_email(value)
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        candidate = User(email=attrs["email"], full_name=attrs.get("full_name", ""))
        _check_password_strength(attrs["password"], candidate, "password")
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    """The authenticated user's own profile."""

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "student_id",
            "department",
            "phone",
            "avatar",
            "is_email_verified",
            "date_joined",
        ]
        read_only_fields = ["id", "email", "is_email_verified", "date_joined"]

    def validate_avatar(self, avatar):
        return validate_image_size(avatar)


class PublicUserSerializer(serializers.ModelSerializer):
    """What other students can see about a user."""

    class Meta:
        model = User
        fields = ["id", "full_name", "department", "avatar", "date_joined"]


class _UidTokenSerializer(serializers.Serializer):
    """Validates a `uid` + `token` pair from an emailed link and resolves the user."""

    uid = serializers.CharField()
    token = serializers.CharField()
    token_generator = None  # set by subclasses

    def validate(self, attrs):
        try:
            pk = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=pk)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError("Invalid or expired link.") from None
        if not self.token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError("Invalid or expired link.")
        attrs["user"] = user
        return attrs


class VerifyEmailSerializer(_UidTokenSerializer):
    token_generator = email_verification_token


class PasswordResetConfirmSerializer(_UidTokenSerializer):
    token_generator = default_token_generator
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        _check_password_strength(attrs["new_password"], attrs["user"], "new_password")
        return attrs


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value


class LoginSerializer(TokenObtainPairSerializer):
    """JWT login that also refuses accounts whose email is not yet verified."""

    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.is_email_verified:
            raise AuthenticationFailed(
                {
                    "detail": "Please verify your email address before logging in.",
                    "code": "email_not_verified",
                }
            )
        data["user"] = UserSerializer(self.user, context=self.context).data
        return data
