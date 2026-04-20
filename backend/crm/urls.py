from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import (
    CustomTokenObtainPairView, MeView, UserListView, UserDetailView,
    OperatorStatsView, AnalyticsView, AnalyticsAIChatView,
    OperatorUtilizationView,
    RolePermissionView, SectionsMetaView, CRMSettingsView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/me/', MeView.as_view(), name='me'),
    path('api/users/', UserListView.as_view(), name='user-list'),
    path('api/users/<int:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('api/operators/stats/', OperatorStatsView.as_view(), name='operator-stats'),
    path('api/analytics/', AnalyticsView.as_view(), name='analytics'),
    path('api/analytics/operator-utilization/', OperatorUtilizationView.as_view(), name='analytics-operator-utilization'),
    path('api/analytics/ai-chat/', AnalyticsAIChatView.as_view(), name='analytics-ai-chat'),
    path('api/role-permissions/', RolePermissionView.as_view(), name='role-permissions-list'),
    path('api/role-permissions/<str:role>/', RolePermissionView.as_view(), name='role-permissions-detail'),
    path('api/role-permissions/<str:role>/reset/', RolePermissionView.as_view(), name='role-permissions-reset'),
    path('api/sections-meta/', SectionsMetaView.as_view(), name='sections-meta'),
    path('api/crm-settings/', CRMSettingsView.as_view(), name='crm-settings'),
    path('api/', include('partners.urls')),
    path('api/', include('contacts.urls')),
    path('api/', include('tasks.urls')),
    path('api/', include('reports.urls')),
    path('api/', include('producers.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
