from rest_framework import status, generics, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model, authenticate
from django.utils import timezone
from .serializers import (
    RegisterSerializer, 
    UserSerializer, 
    LoginSerializer,
    VerifyOTPSerializer,
    ResendOTPSerializer,
    AdminUserCreateSerializer,
    AdminUserUpdateSerializer
)
from .models import OTP
from .utils import send_otp_email

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """
    Inscription d'un nouvel utilisateur
    """
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer
    
    def create(self, request, *args, **kwargs):

        incoming_data = request.data if request.method == 'POST' else request.query_params
        if not incoming_data:
            incoming_data = request.query_params

        serializer = self.get_serializer(data=incoming_data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Envoyer l'OTP
        try:
            otp_code = send_otp_email(user)
            return Response({
                'message': 'Inscription réussie. Un code OTP a été envoyé à votre email.',
                'email': user.email,
                # 'otp_code': otp_code  # À retirer en production
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            user.delete()  # Supprimer l'utilisateur si l'envoi échoue
            return Response({
                'error': 'Erreur lors de l\'envoi de l\'email de vérification.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST', 'GET'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Connexion avec email et mot de passe, puis envoi OTP
    """
    incoming_data = request.data if request.method == 'POST' else request.query_params
    if not incoming_data:
        incoming_data = request.query_params
    serializer = LoginSerializer(data=incoming_data)
    serializer.is_valid(raise_exception=True)
    
    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]
    
    # Authentifier l'utilisateur
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({
            'error': 'Email ou mot de passe incorrect.'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    if not user.check_password(password):
        return Response({
            'error': 'Email ou mot de passe incorrect.'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    # Envoyer l'OTP
    try:
        otp_code = send_otp_email(user)
        return Response({
            'message': 'Code OTP envoyé à votre email.',
            'email': user.email,
            # 'otp_code': otp_code  # À retirer en production
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': 'Erreur lors de l\'envoi du code OTP.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST', 'GET'])
@permission_classes([AllowAny])
def verify_otp_view(request):
    """
    Vérification du code OTP et obtention des tokens JWT
    """
    incoming_data = request.data if request.method == 'POST' else request.query_params
    if not incoming_data:
        incoming_data = request.query_params
    serializer = VerifyOTPSerializer(data=incoming_data)
    serializer.is_valid(raise_exception=True)
    
    email = serializer.validated_data["email"]
    otp_code = serializer.validated_data["otp_code"]
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({
            'error': 'Utilisateur non trouvé.'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Vérifier l'OTP
    try:
        otp = OTP.objects.filter(user=user, code=otp_code, is_used=False).latest("created_at")
    except OTP.DoesNotExist:
        return Response({
            'error': 'Code OTP invalide.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not otp.is_valid():
        return Response({
            'error': 'Code OTP expiré ou déjà utilisé.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Marquer l'OTP comme utilisé
    otp.is_used = True
    otp.save()
    
    # Marquer l'utilisateur comme vérifié
    if not user.is_verified:
        user.is_verified = True
        user.save()
    
    # Générer les tokens JWT
    refresh = RefreshToken.for_user(user)
    
    return Response({
        'message': 'Connexion réussie.',
        'user': UserSerializer(user).data,
        'token': str(refresh.access_token),
        'tokens': {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_otp_view(request):
    """
    Renvoyer un code OTP
    """
    incoming_data = request.data if request.method == 'POST' else request.query_params
    if not incoming_data:
        incoming_data = request.query_params

    serializer = ResendOTPSerializer(data=incoming_data)
    serializer.is_valid(raise_exception=True)
    
    email = serializer.validated_data["email"]
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({
            'error': 'Utilisateur non trouvé.'
        }, status=status.HTTP_404_NOT_FOUND)
    
    try:
        otp_code = send_otp_email(user)
        return Response({
            'message': 'Un nouveau code OTP a été envoyé.',
            'otp_code': otp_code  # À retirer en production
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': 'Erreur lors de l\'envoi du code OTP.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile_view(request):
    """
    Obtenir le profil de l'utilisateur connecté
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile_view(request):
    """
    Modifier le profil de l'utilisateur connecté
    """
    user = request.user

    incoming_data = request.data if request.method == 'PUT' else request.query_params
    if not incoming_data:
        incoming_data = request.query_params
    serializer = UserSerializer(user, data=incoming_data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================
# GESTION DES UTILISATEURS PAR L'ADMIN
# ============================================

class AdminUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour que l'admin gère tous les utilisateurs
    CRUD complet : Create, Read, Update, Delete
    """
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = UserSerializer
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AdminUserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return AdminUserUpdateSerializer
        return UserSerializer
    
    @action(detail=True, methods=['post'])
    def toggle_admin(self, request, pk=None):
        """
        Activer/désactiver le statut admin d'un utilisateur
        """
        user = self.get_object()
        
        # Empêcher de se retirer soi-même les droits admin
        if user.id == request.user.id:
            return Response({
                'error': 'Vous ne pouvez pas modifier votre propre statut admin.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user.is_admin = not user.is_admin
        user.save()
        
        return Response({
            'message': f"Utilisateur {'promu admin' if user.is_admin else 'rétrogradé utilisateur normal'}.",
            'user': UserSerializer(user).data
        })
    
    @action(detail=True, methods=['post'])
    def toggle_verified(self, request, pk=None):
        """
        Activer/désactiver la vérification d'un utilisateur
        """
        user = self.get_object()
        user.is_verified = not user.is_verified
        user.save()
        
        return Response({
            'message': f"Utilisateur {'vérifié' if user.is_verified else 'non vérifié'}.",
            'user': UserSerializer(user).data
        })
    
    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        """
        Réinitialiser le mot de passe d'un utilisateur
        """
        user = self.get_object()
        new_password = request.data.get('new_password')
        
        if not new_password:
            return Response({
                'error': 'Le nouveau mot de passe est requis.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(new_password)
        user.save()
        
        return Response({
            'message': 'Mot de passe réinitialisé avec succès.'
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Statistiques des utilisateurs
        """
        total_users = User.objects.count()
        verified_users = User.objects.filter(is_verified=True).count()
        admin_users = User.objects.filter(is_admin=True).count()
        
        return Response({
            'total_users': total_users,
            'verified_users': verified_users,
            'unverified_users': total_users - verified_users,
            'admin_users': admin_users,
            'normal_users': total_users - admin_users
        })
