from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from accounts.models import RolePermission
from .models import Task, TaskComment
from .serializers import TaskSerializer, TaskCommentSerializer


def _is_operator(user):
    return getattr(user, 'role', '') == 'operator' and not user.is_staff


class TaskViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = TaskSerializer
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields   = ['partner', 'assigned_to', 'status', 'priority']
    search_fields      = ['title', 'description']
    ordering_fields    = ['due_date', 'priority', 'status', 'created_at', 'updated_at']
    ordering           = ['due_date', '-created_at']

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if _is_operator(request.user):
            if instance.created_by_id != request.user.id:
                return Response(
                    {'detail': 'Operators can only delete tasks they created.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif not RolePermission.has_perm(request.user, 'tasks', 'delete'):
            return Response({'detail': 'You do not have permission to delete.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if _is_operator(request.user):
            is_creator = instance.created_by_id == request.user.id
            is_assignee = instance.assigned_to_id == request.user.id
            if not is_creator:
                # Non-creator operators can only toggle the status of tasks
                # assigned to them, nothing else.
                submitted = set(request.data.keys())
                if not is_assignee or submitted - {'status'}:
                    return Response(
                        {'detail': 'Operators can only edit tasks they created.'},
                        status=status.HTTP_403_FORBIDDEN,
                    )
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        new_status = serializer.validated_data.get('status', instance.status)
        extra = {}
        if new_status == Task.STATUS_DONE and instance.status != Task.STATUS_DONE:
            extra['completed_by'] = self.request.user
            extra['completed_at'] = timezone.now()
        elif new_status != Task.STATUS_DONE and instance.status == Task.STATUS_DONE:
            extra['completed_by'] = None
            extra['completed_at'] = None
        serializer.save(**extra)

    def get_queryset(self):
        return (
            Task.objects
            .select_related('partner', 'assigned_to', 'created_by', 'completed_by')
            .prefetch_related('comments__author')
            .all()
        )

    @action(detail=True, methods=['post'], url_path='comments')
    def add_comment(self, request, pk=None):
        task = self.get_object()
        serializer = TaskCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(task=task, author=request.user)
        # Return updated full task so frontend can refresh in one shot
        return Response(TaskSerializer(task, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path=r'comments/(?P<comment_pk>\d+)')
    def delete_comment(self, request, pk=None, comment_pk=None):
        task    = self.get_object()
        comment = TaskComment.objects.filter(pk=comment_pk, task=task).first()
        if not comment:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if comment.author_id != request.user.pk and not request.user.is_staff and getattr(request.user, 'role', '') != 'admin':
            return Response({'detail': 'Not allowed.'}, status=status.HTTP_403_FORBIDDEN)
        comment.delete()
        return Response(TaskSerializer(task, context={'request': request}).data)

    @action(detail=False, methods=['get'], url_path='open-count')
    def open_count(self, request):
        qs = Task.objects.filter(status__in=['open', 'in_progress'])
        # Operators see only their assigned tasks
        if not request.user.is_staff and getattr(request.user, 'role', '') != 'admin':
            qs = qs.filter(assigned_to=request.user)
        return Response({'count': qs.count()})
