from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User, RolePermission, CRMSettings


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['full_name'] = user.get_full_name() or user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['role'] = self.user.role
        data['full_name'] = self.user.get_full_name() or self.user.username
        data['user_id'] = self.user.id
        return data


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'role']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class MeSerializer(UserSerializer):
    permissions = serializers.SerializerMethodField()
    is_restricted_operator = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ['permissions', 'is_restricted_operator']

    def get_permissions(self, obj):
        return RolePermission.get_for_role(obj.role)

    def get_is_restricted_operator(self, obj):
        return obj.role == 'operator' and not obj.is_staff


class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = RolePermission
        fields = ['role', 'permissions']


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model  = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'password']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6, required=False, allow_blank=True)

    class Meta:
        model  = User
        fields = ['first_name', 'last_name', 'email', 'role', 'password']

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class CRMSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CRMSettings
        fields = ['product_info', 'evaluation_prompt', 'updated_at']
        read_only_fields = ['updated_at']
