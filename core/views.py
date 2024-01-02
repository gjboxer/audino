from rest_framework import viewsets, mixins, status
from rest_framework.decorators import api_view, authentication_classes, parser_classes, permission_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Annotation as AnnotationModel
from .models import AnnotationData as AnnotationDataModel
from .models import AnnotationAttribute as AnnotationAttributeModel
from .models import Data as DataModel
from .models import Job as JobModel
from .models import Label as LabelModel
from .models import Project as ProjectModel
from .serializers import *
from .utils import convert_string_lists_to_lists
from .utils import get_paginator
from users.manager import TokenAuthentication
from iam.permissions import *
from organizations.mixins import PartialUpdateModelMixin


class ProjectViewSet(viewsets.GenericViewSet, mixins.ListModelMixin,
                     mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, PartialUpdateModelMixin
                     ):
    queryset = ProjectModel.objects.select_related(
        'assignee', 'owner', 'target_storage', 'source_storage',
    ).all()

    search_fields = ('name', 'owner', 'assignee')
    filter_fields = list(search_fields) + ['id', 'updated_at']
    simple_filters = list(search_fields)
    ordering_fields = list(filter_fields)
    ordering = "-id"
    lookup_fields = {'owner': 'owner__username',
                     'assignee': 'assignee__username'}
    iam_organization_field = 'organization'

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return ProjectReadSerializer
        else:
            return ProjectWriteSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.action == 'list':
            perm = ProjectPermission.create_scope_list(self.request)
            queryset = perm.filter(queryset)
        return queryset

    @transaction.atomic
    def perform_create(self, serializer, **kwargs):
        serializer.save(
            owner=self.request.user,
            organization=self.request.iam_context['organization']
        )

        serializer.instance = self.get_queryset().get(pk=serializer.instance.pk)

class LabelViewSet(viewsets.GenericViewSet, mixins.ListModelMixin,
                   mixins.RetrieveModelMixin, mixins.DestroyModelMixin, PartialUpdateModelMixin
                   ):
    queryset = Label.objects.prefetch_related(
        'task',
        'task__owner',
        'task__assignee',
        'task__organization',
        'project',
        'project__owner',
        'project__assignee',
        'project__organization'
    ).all()
    iam_organization_field = ('task__organization', 'project__organization')
    search_fields = ('name',)
    filter_fields = list(search_fields) + ['id']
    simple_filters = list(set(filter_fields) - {'id'})
    ordering_fields = list(filter_fields)
    ordering = 'id'
    serializer_class = LabelWriteSerializer
    pagination_class = None
    parser_classes = [JSONParser]

    def get_queryset(self):
        if self.action == 'list':
            job_id = self.request.GET.get('job_id', None)
            task_id = self.request.GET.get('task_id', None)
            project_id = self.request.GET.get('project_id', None)
            if sum(v is not None for v in [job_id, task_id, project_id]) > 1:
                raise ValidationError(
                    "job_id, task_id and project_id parameters cannot be used together",
                    code=status.HTTP_400_BAD_REQUEST
                )

            if job_id:
                # NOTE: This filter is too complex to be implemented by other means
                # It requires the following filter query:
                # (
                #  project__task__segment__job__id = job_id
                #  OR
                #  task__segment__job__id = job_id
                # )
                job = Job.objects.get(id=job_id)
                self.check_object_permissions(self.request, job)
                queryset = job.get_labels()
            elif task_id:
                # NOTE: This filter is too complex to be implemented by other means
                # It requires the following filter query:
                # (
                #  project__task__id = task_id
                #  OR
                #  task_id = task_id
                # )
                task = Task.objects.get(id=task_id)
                self.check_object_permissions(self.request, task)
                queryset = task.get_labels()
            elif project_id:
                # NOTE: this check is to make behavior consistent with other source filters
                project = Project.objects.get(id=project_id)
                self.check_object_permissions(self.request, project)
                queryset = project.get_labels()
            else:
                # In other cases permissions are checked already
                queryset = super().get_queryset()
                perm = LabelPermission.create_scope_list(self.request)
                queryset = perm.filter(queryset)

        else:
            queryset = super().get_queryset()

        return queryset

    def get_serializer(self, *args, **kwargs):
        # kwargs['local']=True
        return super().get_serializer(*args, **kwargs)

    def perform_update(self, serializer):
        label_instance = serializer.instance
        data = self.request.data
        project = Project.objects.get(id=data.get("project"))
        label = {
            "project": project,
            "name": data.get("name", label_instance.name),
            "label_type": data.get("label_type", label_instance.label_type),
            "attributes": data.get("attributes", label_instance.attributes),
        }
        LabelWriteSerializer.update_label(label, label_instance)

    def perform_destroy(self, instance: Label):
        if project := instance.project:
            project.save(update_fields=['updated_at'])
            ProjectWriteSerializer(
                project).update_child_objects_on_labels_update(project)
        elif task := instance.task:
            task.save(update_fields=['updated_at'])
            PostTaskSerializer(
                task).update_child_objects_on_labels_update(task)

        return super().perform_destroy(instance)

class JobViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.CreateModelMixin,
                 mixins.RetrieveModelMixin, PartialUpdateModelMixin, mixins.DestroyModelMixin
                 ):
    queryset = Job.objects.select_related(
        'assignee', 'guide_id', 'task_id', 'project_id').all()

    iam_organization_field = 'task_id__organization'
    search_fields = ('assignee', 'state', 'stage')
    filter_fields = list(search_fields) + [
        'id', 'task_id', 'project_id', 'updated_at'
    ]
    simple_filters = list(set(filter_fields) - {'id', 'updated_at'})
    ordering_fields = list(filter_fields)
    ordering = "-id"
    lookup_fields = {
        'task_id': 'task_id',
        'project_id': 'project_id',
        'task_name': 'task_id__name',
        'project_name': 'project_id__name',
        'assignee': 'assignee__username'
    }

    def get_queryset(self):
        queryset = super().get_queryset()

        # TODO: Add permission check
        # if self.action == 'list':
        #     perm = JobPermission.create_scope_list(self.request)
        #     queryset = perm.filter(queryset)

        return queryset

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return GetJobSerializer
        else:
            return PostJobSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        super().perform_create(serializer)
        serializer.instance = self.get_queryset().get(pk=serializer.instance.pk)

    def perform_destroy(self, instance):
        if instance.type != JobType.GROUND_TRUTH:
            raise ValidationError("Only ground truth jobs can be removed")

        return super().perform_destroy(instance)

class TaskViewSet(viewsets.GenericViewSet, mixins.ListModelMixin,
                  mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin,
                  PartialUpdateModelMixin
                  ):
    queryset = Task.objects.select_related(
        'assignee', 'owner',
        'target_storage', 'source_storage',
    ).all()

    lookup_fields = {
        'project_name': 'project__name',
        'owner': 'owner__username',
        'assignee': 'assignee__username',
    }
    search_fields = (
        'project_name', 'name', 'owner', 'assignee',
    )
    filter_fields = list(search_fields) + ['id', 'project_id', 'updated_date']
    simple_filters = list(search_fields) + ['project_id']
    ordering_fields = list(filter_fields)
    ordering = "-id"
    iam_organization_field = 'organization'

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return GetTaskSerializer
        else:
            return PostTaskSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.action == 'list':

            perm = TaskPermission.create_scope_list(self.request)
            queryset = perm.filter(queryset)

        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        queryset = self.filter_queryset(self.get_queryset())

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        result = []
        for task in queryset:
            job_data = {
                "count": JobModel.objects.filter(task_id=task.id).count(),
                "completed": JobModel.objects.filter(task_id=task.id, state="completed").count(),
                "validation": JobModel.objects.filter(task_id=task.id, stage="validation").count(),
            }
            serialized_task = GetTaskSerializer(task).data
            serialized_task["jobs"] = job_data
            result.append(serialized_task)

        return paginator.get_paginated_response(result)

    @transaction.atomic
    def perform_update(self, serializer):
        super().perform_update(serializer)

    @transaction.atomic
    def perform_create(self, serializer, **kwargs):
        data = self.request.data
        serializer.save(
            owner=self.request.user,
            organization=self.request.iam_context['organization']
        )
        task_obj = serializer.instance
        # creating job for the task created
        job_data = {
            "assignee": task_obj.assignee_id if task_obj.assignee_id else None,
            "stage": "annotation",
            "state": "new",
            "type": "annotation",
            "project_id": task_obj.project_id,
            "guide_id": task_obj.owner_id,
            "task_id": task_obj.id,
        }
        job_serializer = PostJobSerializer(data=job_data)
        job_serializer.is_valid(raise_exception=True)
        job_serializer.save()
        serializer.instance = self.get_queryset().get(pk=serializer.instance.pk)

@api_view(["GET", "POST", "DELETE"])
@parser_classes([MultiPartParser])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def add_data(request, task_id, format=None):
    if request.method == "POST":
        file_data = {
            "task": task_id,
            "filename": request.data["file"].name,
            "size": (request.data["file"].size) // 1024,
            "file": request.data["file"],
        }
        serializer = DataSerializer(data=file_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "DELETE":
        data = DataModel.objects.filter(task=task_id).first()
        if len(data) == 0:
            return Response(
                {"message": "No data are associated with this task."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DataSerializer(data)
        for each_data in data:
            each_data.delete()

        return Response(serializer.data, status=status.HTTP_200_OK)

    task_data = DataModel.objects.filter(task=task_id).first()
    serializer = DataSerializer(task_data)
    return Response(serializer.data, status=status.HTTP_200_OK)

class JobAnnotationViewSet(viewsets.ViewSet):
    def create(self, request, job_id):
        if JobModel.objects.filter(id=job_id).exists():
            data = self.request.data
            data["job"] = job_id
            serializer = PostAnnotationSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            annotation_obj = serializer.save()

            for each_label in data["label"]:
                ann_data = {
                    "label": each_label["id"],
                    "name": LabelModel.objects.get(id=each_label["id"]).name,
                }
                ann_data_serializer = AnnotationDataSerializer(data=ann_data)
                ann_data_serializer.is_valid(raise_exception=True)
                ann_obj = ann_data_serializer.save()
                annotation_obj.labels.add(ann_obj)
                for each_attri in each_label["attributes"]:
                    ann_attribute_data = {
                        "attribute": each_attri["id"],
                        "values": str(each_attri["values"]),
                    }
                    ann_attribute_serializer = AnnotationAttributeSerializer(
                        data=ann_attribute_data
                    )
                    ann_attribute_serializer.is_valid(raise_exception=True)
                    ann_att_obj = ann_attribute_serializer.save()
                    ann_obj.attributes.add(ann_att_obj)

            final_data = dict(GetAnnotationSerializer(annotation_obj).data)
            final_data = convert_string_lists_to_lists(final_data)
            return Response(final_data, status=status.HTTP_201_CREATED)
        
    def list(self, request, job_id):
        annotations = AnnotationModel.objects.filter(job=job_id)
        if len(annotations) == 0:
            return Response([], status=status.HTTP_200_OK)

        serializer = GetAnnotationSerializer(annotations, many=True)
        temp_serializer = convert_string_lists_to_lists(serializer.data)
        return Response(temp_serializer, status=status.HTTP_200_OK)

class AnnotationViewSet(viewsets.ViewSet):
    queryset = AnnotationModel.objects.all()
    search_fields = ('job__id', 'id')
    filter_fields = list(search_fields) + ['id', 'job_id']
    simple_filters = list(set(filter_fields) - {'id'})
    ordering_fields = list(filter_fields)
    ordering = "-id"
    lookup_fields = {'job_id': 'job_id'}

    def get_object_or_404(self, a_id):
        try:
            return self.queryset.get(id=a_id)
        except AnnotationModel.DoesNotExist:
            raise ValidationError(
                f"Annotation with given ID {a_id} does not exist.",
                code=status.HTTP_404_NOT_FOUND,
            )

    def get_serializer_class(self):
        if self.action == 'list':
            return GetAnnotationSerializer
        else:
            return PostAnnotationSerializer

    def list(self, request, job_id, a_id, format=None):
        annotation = self.get_object_or_404(a_id)
        final_data = dict(GetAnnotationSerializer(annotation).data)
        final_data = convert_string_lists_to_lists(final_data)
        return Response(final_data, status=status.HTTP_200_OK)

    @transaction.atomic
    def perform_create(self, serializer):
        super().perform_create(serializer)
        serializer.instance = self.get_queryset().get(pk=serializer.instance.pk)

    @transaction.atomic
    def perform_update(self, serializer, job_id, a_id):
        data = self.request.data
        annotation = self.get_object_or_404(a_id)

        labels = annotation.labels.values()
        for each_label in labels:
            label_obj = AnnotationDataModel.objects.get(id=each_label['id'])
            for each_annotation in label_obj.attributes.values():
                AnnotationAttributeModel.objects.get(
                    id=each_annotation['id']).delete()
            label_obj.delete()

        serializer = PostAnnotationSerializer(annotation, data=data)
        serializer.is_valid(raise_exception=True)
        ann = serializer.save()

        for each_label in data["label"]:
            ann_data = {
                "label": each_label["id"],
                "name": LabelModel.objects.get(id=each_label["id"]).name,
            }
            ann_data_serializer = AnnotationDataSerializer(data=ann_data)
            ann_data_serializer.is_valid(raise_exception=True)
            ann_obj = ann_data_serializer.save()
            ann.labels.add(ann_obj)

            for each_attri in each_label["attributes"]:
                ann_attribute_data = {
                    "attribute": each_attri["id"],
                    "values": str(each_attri["values"]),
                }
                ann_attribute_serializer = AnnotationAttributeSerializer(
                    data=ann_attribute_data
                )
                ann_attribute_serializer.is_valid(raise_exception=True)
                ann_att_obj = ann_attribute_serializer.save()
                ann_obj.attributes.add(ann_att_obj)

        final_data = dict(GetAnnotationSerializer(ann).data)
        final_data = convert_string_lists_to_lists(final_data)
        return Response(final_data, status=status.HTTP_200_OK)

    @transaction.atomic
    def perform_destroy(self, instance, a_id, job_id):
        annotation = self.get_object_or_404(a_id)
        annotation.delete()
        return Response(
            {"message": f"Annotation with {a_id} deleted successfully"},
            status=status.HTTP_200_OK,
        )
