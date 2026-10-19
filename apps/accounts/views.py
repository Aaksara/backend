from django.contrib.auth import get_user_model
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .authentication import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from .emails import send_password_reset_email, send_verification_email
from .serializers import (
    ChangePasswordSerializer,
    EmailSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PublicUserSerializer,
    RegisterSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)
from .tokens import revoke_refresh_tokens

User = get_user_model()

GENERIC_EMAIL_RESPONSE = {"detail": "If an account exists for that email, a message has been sent."}


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @transaction.atomic
    def perform_create(self, serializer):
        # If the email cannot be sent, roll back so the student can simply register again.
        user = serializer.save()
        send_verification_email(user)


class LoginView(TokenObtainPairView):
    """Sets the auth cookies and returns the user."""

    serializer_class = LoginSerializer
    throttle_scope = "auth"

    @extend_schema(responses={200: UserSerializer})
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        set_auth_cookies(response, response.data["access"], response.data["refresh"])
        response.data = response.data["user"]
        return response


class RefreshView(APIView):
    """Swaps the refresh cookie for new cookies (the refresh token is rotated)."""

    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        refresh = request.COOKIES.get(REFRESH_COOKIE)
        if not refresh:
            raise NotAuthenticated("You are not signed in.")
        serializer = TokenRefreshSerializer(data={"refresh": refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from None
        response = Response(status=status.HTTP_204_NO_CONTENT)
        set_auth_cookies(
            response, serializer.validated_data["access"], serializer.validated_data["refresh"]
        )
        return response


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=VerifyEmailSerializer, responses={200: dict})
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        return Response({"detail": "Email verified. You can now log in."})


class ResendVerificationView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=EmailSerializer, responses={200: dict})
    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"], is_email_verified=False
        ).first()
        if user:
            send_verification_email(user)
        return Response(GENERIC_EMAIL_RESPONSE)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=EmailSerializer, responses={200: dict})
    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"], is_active=True
        ).first()
        if user:
            send_password_reset_email(user)
        return Response(GENERIC_EMAIL_RESPONSE)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=PasswordResetConfirmSerializer, responses={200: dict})
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        revoke_refresh_tokens(user)
        return Response({"detail": "Password has been reset."})


class ChangePasswordView(APIView):
    @extend_schema(request=ChangePasswordSerializer, responses={200: dict})
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        revoke_refresh_tokens(request.user)
        return Response({"detail": "Password changed."})


class LogoutView(APIView):
    """Revokes the refresh cookie and clears both cookies. Works even if already expired."""

    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        refresh = request.COOKIES.get(REFRESH_COOKIE)
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass  # Already expired or revoked: nothing to do.
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_auth_cookies(response)
        return response


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class PublicUserView(generics.RetrieveAPIView):
    queryset = User.objects.filter(is_active=True)
    serializer_class = PublicUserSerializer
