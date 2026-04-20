from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ContactViewSet, OperatorFeedbackView,
    OperatorFeedbackAcknowledgeView, GenerateFeedbackView,
)

router = DefaultRouter()
router.register(r'contacts', ContactViewSet, basename='contact')

urlpatterns = [
    path('', include(router.urls)),
    path('operator-feedback/', OperatorFeedbackView.as_view(), name='operator-feedback-list'),
    path('operator-feedback/<int:pk>/acknowledge/', OperatorFeedbackAcknowledgeView.as_view(), name='operator-feedback-ack'),
    path('operator-feedback/generate/', GenerateFeedbackView.as_view(), name='operator-feedback-generate'),
]
