from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AiReportViewSet, GenerateReportView,
    ProducerUpdateReportViewSet, GenerateProducerUpdateView,
    BrandSituationReportViewSet, GenerateBrandSituationView,
    AiOperationsListView, AiOperationsDetailView,
    AiOperationsRunNowView, AiOperationsPublicStatusView,
    AiOperationsDeadEndedView,
)

router = DefaultRouter()
router.register(r'ai-reports',         AiReportViewSet,             basename='ai-report')
router.register(r'producer-updates',   ProducerUpdateReportViewSet, basename='producer-update')
router.register(r'brand-situation',    BrandSituationReportViewSet, basename='brand-situation')

urlpatterns = [
    path('ai-reports/generate/',         GenerateReportView.as_view(),         name='ai-report-generate'),
    path('producer-updates/generate/',   GenerateProducerUpdateView.as_view(), name='producer-update-generate'),
    path('brand-situation/generate/',    GenerateBrandSituationView.as_view(), name='brand-situation-generate'),

    # AI Operations control panel
    path('ai-operations/',                       AiOperationsListView.as_view(),         name='ai-ops-list'),
    path('ai-operations/dead-ended/',            AiOperationsDeadEndedView.as_view(),    name='ai-ops-dead-ended'),
    path('ai-operations/<str:job_id>/',          AiOperationsDetailView.as_view(),       name='ai-ops-detail'),
    path('ai-operations/<str:job_id>/run-now/',  AiOperationsRunNowView.as_view(),       name='ai-ops-run-now'),
    path('ai-operations/<str:job_id>/status/',   AiOperationsPublicStatusView.as_view(), name='ai-ops-status'),

    path('', include(router.urls)),
]
