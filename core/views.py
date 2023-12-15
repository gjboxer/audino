from django.db.models import Q
from django.db import transaction

from rest_framework import viewsets, mixins, status, serializers
from rest_framework.decorators import api_view, authentication_classes, parser_classes, permission_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import *
from .models import Annotation as AnnotationModel
from .models import AnnotationData as AnnotationDataModel
from .models import AnnotationAttribute as AnnotationAttributeModel
from .models import Attribute as AttributeModel
from .models import Data as DataModel
from .models import Job as JobModel
from .models import Label as LabelModel
from .models import Project as ProjectModel
from .models import Task as TaskModel
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

        # After saving the serializer (creating a new object), the line retrieves the saved instance from the database
        serializer.instance = self.get_queryset().get(pk=serializer.instance.pk)




# @api_view(["GET", "POST"])
# @authentication_classes([TokenAuthentication])
# @permission_classes([IsAuthenticated])
# def get_add_project(request, format=None):
#     if request.method == "POST":
#         organization = request.iam_context['organization']

#         data = JSONParser().parse(request)

#         if organization:
#             try:
#                 data["organization"] = organization.id
#             except Organization.DoesNotExist:
#                 return Response(
#                     {"message": "Organization does not exist."},
#                     status=status.HTTP_404_NOT_FOUND,
#                 )

#         source_serializer = StorageSerializer(data=data["source_storage"])
#         target_serializer = StorageSerializer(data=data["target_storage"])

#         if source_serializer.is_valid() and target_serializer.is_valid():
#             src = source_serializer.save()
#             tgt = target_serializer.save()
#             data["source_storage"] = src.id
#             data["target_storage"] = tgt.id

#         data["owner"] = request.user.id
#         data["assignee"] = data.pop("assignee_id")
#         serializer = ProjectWriteSerializer(data=data)
#         if serializer.is_valid():
#             project_obj = serializer.save()
#             for each_label in data["labels"]:
#                 label_object = {
#                     "project": project_obj.id,
#                     "name": each_label["name"],
#                     "label_type": each_label["label_type"],
#                 }
#                 label_serializer = LabelWriteSerializer(data=label_object)
#                 if label_serializer.is_valid():
#                     label_obj = label_serializer.save()
#                     for each_attribute in each_label["attributes"]:
#                         attribute_obj = {
#                             "label": label_obj.id,
#                             "name": each_attribute["name"],
#                             "input_type": each_attribute["input_type"],
#                             "default_value": each_attribute["default_value"],
#                             "values": str(each_attribute["values"]),
#                         }
#                         attribute_serializer = AttributeSerializer(
#                             data=attribute_obj
#                         )
#                         if attribute_serializer.is_valid():
#                             attribute_obj = attribute_serializer.save()
#                             label_obj.attributes.add(attribute_obj)
#                         else:
#                             return Response(
#                                 attribute_serializer.errors,
#                                 status=status.HTTP_400_BAD_REQUEST,
#                             )

#                 else:
#                     return Response(
#                         label_serializer.errors, status=status.HTTP_400_BAD_REQUEST
#                     )

#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     search_query = request.GET.get("search", None)
#     # page = request.GET.get("page", 1)
#     # page_size = request.GET.get("page_size", 10)

#     organization = request.iam_context['organization']

#     if organization is None:
#         projects = ProjectModel.objects.filter(
#             organization__isnull=True).order_by("created_at")

#     else:
#         projects = ProjectModel.objects.select_related(
#             'assignee', 'owner', 'target_storage', 'source_storage').prefetch_related('tasks').all()

#     perm = ProjectPermission.create_scope_list(request)
#     projects = perm.filter(projects)

#     if search_query:
#         projects = projects.filter(Q(name__icontains=search_query))

#     # paginator = get_paginator(page, page_size)
#     paginator = PageNumberPagination()
#     paginated_queryset = paginator.paginate_queryset(projects, request)
#     serializer = ProjectReadSerializer(paginated_queryset, many=True)
#     return paginator.get_paginated_response(serializer.data)


# @api_view(["GET", "PATCH", "DELETE"])
# @authentication_classes([TokenAuthentication])
# @permission_classes([IsAuthenticated])
# def update_project(request, id, format=None):
#     try:
#         project = ProjectModel.objects.get(id=id)
#     except ProjectModel.DoesNotExist:
#         return Response(
#             {"message": "Project not found"}, status=status.HTTP_404_NOT_FOUND
#         )

#     if request.method == "DELETE":
#         serializer = ProjectReadSerializer(project)
#         project.delete()
#         return Response(serializer.data, status=status.HTTP_200_OK)

#     if request.method == "PATCH":
#         data = JSONParser().parse(request)

#         source_serializer = StorageSerializer(
#             project.source_storage, data=data["source_storage"]
#         )
#         target_serializer = StorageSerializer(
#             project.target_storage, data=data["target_storage"]
#         )

#         if source_serializer.is_valid() and target_serializer.is_valid():
#             src = source_serializer.save()
#             tgt = target_serializer.save()
#             data["source_storage"] = src.id
#             data["target_storage"] = tgt.id

#         serializer = ProjectWriteSerializer(project, data=data)
#         if serializer.is_valid():
#             serializer.save()
#             for each_label in data["labels"]:
#                 label_object = {
#                     "project": id,
#                     "name": each_label["name"],
#                     "label_type": each_label["label_type"],
#                 }
#                 if "id" in each_label:
#                     label = LabelModel.objects.get(id=each_label["id"])
#                     label_serializer = LabelWriteSerializer(
#                         label, data=label_object)
#                 else:
#                     label_serializer = LabelWriteSerializer(data=label_object)

#                 if label_serializer.is_valid():
#                     label_obj = label_serializer.save()
#                     for each_attribute in each_label["attributes"]:
#                         attribute_obj = {
#                             "label": label_obj.id,
#                             "name": each_attribute["name"],
#                             "input_type": each_attribute["input_type"],
#                             "default_value": each_attribute["default_value"],
#                             "values": str(each_attribute["values"]),
#                         }
#                         if "id" in each_attribute:
#                             attribute = AttributeModel.objects.get(
#                                 id=each_attribute["id"]
#                             )
#                             attribute_serializer = AttributeSerializer(
#                                 attribute, data=attribute_obj
#                             )
#                         else:
#                             attribute_serializer = AttributeSerializer(
#                                 data=attribute_obj
#                             )

#                         if attribute_serializer.is_valid():
#                             attribute_obj = attribute_serializer.save()
#                             label_obj.attributes.add(attribute_obj)
#                         else:
#                             return Response(
#                                 attribute_serializer.errors,
#                                 status=status.HTTP_400_BAD_REQUEST,
#                             )

#                 else:
#                     return Response(
#                         label_serializer.errors, status=status.HTTP_400_BAD_REQUEST
#                     )

#             return Response(serializer.data, status=status.HTTP_200_OK)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     serializer = ProjectReadSerializer(project)
#     return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_labels(request, format=None):
    project_id = request.query_params["project_id"]

    labels = LabelModel.objects.filter(
        project=project_id
    ).order_by("-created_at")

    serializer = LabelReadSerializer(labels, many=True)
    temp_serializer = convert_string_lists_to_lists(serializer.data)

    return Response(temp_serializer, status=status.HTTP_200_OK)


@api_view(["GET", "PATCH", "DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_label_by_id(request, id, format=None):
    try:
        label = LabelModel.objects.get(id=id)
    except LabelModel.DoesNotExist:
        return Response(
            {"message": "Label object not found"}, status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "DELETE":
        serializer = LabelReadSerializer(label)
        temp_serializer = convert_string_lists_to_lists(serializer.data)
        label.delete()
        return Response(temp_serializer, status=status.HTTP_200_OK)

    if request.method == "PATCH":
        data = JSONParser().parse(request)
        label_object = {
            "project": data["project"],
            "name": data["name"],
            "label_type": data["label_type"],
        }

        label_serializer = LabelWriteSerializer(label, data=label_object)
        if label_serializer.is_valid():
            label_obj = label_serializer.save()
            for each_attribute in data["attributes"]:
                attribute_obj = {
                    "label": label_obj.id,
                    "name": each_attribute["name"],
                    "mutable": each_attribute["mutable"],
                    "input_type": each_attribute["input_type"],
                    "default_value": each_attribute["default_value"],
                    "values": str(each_attribute["values"]),
                }
                if "id" in each_attribute:
                    attribute = AttributeModel.objects.get(
                        id=each_attribute["id"])
                    attribute_serializer = AttributeSerializer(
                        attribute, data=attribute_obj
                    )
                else:
                    attribute_serializer = AttributeSerializer(
                        data=attribute_obj)

                if attribute_serializer.is_valid():
                    attribute_obj = attribute_serializer.save()
                    label_obj.attributes.add(attribute_obj)
                else:
                    return Response(
                        attribute_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                    )

            return Response(label_serializer.data, status=status.HTTP_200_OK)
        return Response(label_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer = LabelReadSerializer(label)
    temp_serializer = convert_string_lists_to_lists(serializer.data)
    return Response(temp_serializer, status=status.HTTP_200_OK)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def jobs(request, format=None):
    if request.method == "POST":
        job_serializer = PostJobSerializer(data=request.data)
        if job_serializer.is_valid():
            job_serializer.save()
            return Response(job_serializer.data, status=status.HTTP_201_CREATED)
        return Response(job_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    search_query = request.GET.get("search", None)
    page = request.GET.get("page", 1)
    page_size = request.GET.get("page_size", 10)

    organization = request.iam_context['organization']
    if organization:
        try:
            jobs = JobModel.objects.filter(
                Q(project_id__organization__slug=organization.slug) &
                (Q(guide_id=request.user) | Q(assignee=request.user))
            ).order_by("created_at")

            # not using JobPermission as it is not working
            # perm = JobPermission.create_scope_list(request)
            # jobs = perm.filter(jobs)
        except Organization.DoesNotExist:
            return Response(
                {"message": "Organization does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

    else:
        jobs = JobModel.objects.filter(Q(task_id__project_id__organization__isnull=True) &
                                       (Q(guide_id=request.user) |
                                        Q(assignee=request.user))
                                       ).order_by("created_at")
    # not using JobPermission as it is not working
    # perm = JobPermission.create_scope_list(request)
    # jobs = perm.filter(jobs)

    if search_query:
        jobs = jobs.filter(Q(task_id__name__icontains=search_query))

    paginator = get_paginator(page, page_size)
    result = paginator.paginate_queryset(jobs, request)
    serializer = GetJobSerializer(result, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(["GET", "DELETE", "PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_job_by_id(request, job_id, format=None):
    try:
        job = JobModel.objects.get(id=job_id)
    except JobModel.DoesNotExist:
        return Response(
            {"message": "Job does not exists."}, status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "DELETE":
        serializer = GetJobSerializer(job)
        job.delete()
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == "PATCH":
        data = JSONParser().parse(request)
        serializer = PostJobSerializer(job, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer = GetJobSerializer(job)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def tasks(request, format=None):
    if request.method == "POST":
        data = JSONParser().parse(request)
        organization = request.iam_context['organization']

        if organization:
            data["organization"] = organization.id

        source_serializer = StorageSerializer(data=data["source_storage"])
        target_serializer = StorageSerializer(data=data["target_storage"])

        if source_serializer.is_valid() and target_serializer.is_valid():
            src = source_serializer.save()
            tgt = target_serializer.save()
            data["source_storage"] = src.id
            data["target_storage"] = tgt.id

        data["project"] = data.pop("project_id")
        data["owner"] = request.user.id
        data["assignee"] = data.pop("assignee_id")
        serializer = PostTaskSerializer(data=data)
        if serializer.is_valid():
            task_obj = serializer.save()
            job_data = {
                "assignee": task_obj.assignee.id if task_obj.assignee else None,
                "stage": "annotation",
                "state": "new",
                "project_id": task_obj.project.id,
                "guide_id": task_obj.owner.id,
                "task_id": task_obj.id,
            }

            # creating job for the task created
            job_serializer = PostJobSerializer(data=job_data)
            if job_serializer.is_valid():
                job_serializer.save()

            job_data = {
                "count": len(JobModel.objects.filter(task_id=task_obj.id)),
                "completed": len(
                    JobModel.objects.filter(
                        task_id=task_obj.id, state="completed")
                ),
                "validation": len(
                    JobModel.objects.filter(
                        task_id=task_obj.id, stage="validation")
                ),
            }
            project_labels = LabelModel.objects.filter(
                project=task_obj.project.id)
            for each_project_label in project_labels:
                task_obj.labels.add(each_project_label)

            final_data = dict(serializer.data)
            final_data["jobs"] = job_data
            return Response(final_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    search_query = request.GET.get("search", None)
    page = request.GET.get("page", 1)
    page_size = request.GET.get("page_size", 10)

    organization = request.iam_context['organization']
    if organization:
        try:
            tasks = Task.objects.select_related(
                'assignee', 'owner', 'target_storage', 'source_storage'
            ).filter(
                Q(organization=organization) & (Q(
                    owner=request.user) | Q(assignee=request.user)))

            perm = TaskPermission.create_scope_list(request)
            tasks = perm.filter(tasks)
        except Organization.DoesNotExist:
            return Response(
                {"message": "Organization does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

    else:
        tasks = TaskModel.objects.select_related(
            'assignee', 'owner', 'target_storage', 'source_storage'
        ).filter(
            (Q(owner=request.user) | Q(assignee=request.user)) & Q(
                organization__isnull=True)
        ).order_by("created_at")

        perm = TaskPermission.create_scope_list(request)
        tasks = perm.filter(tasks)

    if search_query:
        tasks = tasks.filter(Q(name__icontains=search_query))

    paginator = get_paginator(page, page_size)
    temp = paginator.paginate_queryset(tasks, request)

    serializer = GetTaskSerializer(temp, many=True)
    temp_serializer = serializer.data
    result = []

    for each_serializer in temp_serializer:
        each_serializer = dict(each_serializer)
        job_data = {
            "count": len(JobModel.objects.filter(task_id=each_serializer["id"])),
            "completed": len(
                JobModel.objects.filter(
                    task_id=each_serializer["id"], state="completed"
                )
            ),
            "validation": len(
                JobModel.objects.filter(
                    task_id=each_serializer["id"], stage="validation"
                )
            ),
        }
        each_serializer["jobs"] = job_data
        result.append(each_serializer)

    return paginator.get_paginated_response(result)


@api_view(["GET", "DELETE", "PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_task_by_id(request, task_id, format=None):
    try:
        task = TaskModel.objects.get(id=task_id)
    except TaskModel.DoesNotExist:
        return Response(
            {"message": "Task does not exist."}, status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "DELETE":
        serializer = GetTaskSerializer(task)
        task.delete()
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == "PATCH":
        data = JSONParser().parse(request)

        source_serializer = StorageSerializer(
            task.source_storage, data=data["source_storage"]
        )
        target_serializer = StorageSerializer(
            task.target_storage, data=data["target_storage"]
        )

        if source_serializer.is_valid() and target_serializer.is_valid():
            src = source_serializer.save()
            tgt = target_serializer.save()
            data["source_storage"] = src.id
            data["target_storage"] = tgt.id

        data["project"] = data.pop("project_id")
        data["owner"] = request.user.id
        data["assignee"] = data.pop("assignee_id")
        serializer = PostTaskSerializer(task, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer = GetTaskSerializer(task)
    temp_serializer = dict(serializer.data)
    job_data = {
        "count": len(JobModel.objects.filter(task_id=temp_serializer["id"])),
        "completed": len(
            JobModel.objects.filter(
                task_id=temp_serializer["id"], state="completed")
        ),
        "validation": len(
            JobModel.objects.filter(
                task_id=temp_serializer["id"], stage="validation")
        ),
    }
    temp_serializer["jobs"] = job_data
    return Response(temp_serializer, status=status.HTTP_200_OK)


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


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def job_annotation(request, job_id, format=None):
    if request.method == "POST" and JobModel.objects.filter(id=job_id).exists():
        data = JSONParser().parse(request)
        data["job"] = job_id

        serializer = PostAnnotationSerializer(data=data)
        if serializer.is_valid():
            annotation_obj = serializer.save()
            for each_label in data["label"]:
                ann_data = {
                    "label": each_label["id"],
                    "name": LabelModel.objects.get(id=each_label["id"]).name,
                }
                ann_data_serializer = AnnotationDataSerializer(data=ann_data)
                if ann_data_serializer.is_valid():
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
                        if ann_attribute_serializer.is_valid():
                            ann_att_obj = ann_attribute_serializer.save()
                            ann_obj.attributes.add(ann_att_obj)
                        else:
                            return Response(
                                ann_attribute_serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                else:
                    return Response(
                        ann_data_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                    )

            final_data = dict(GetAnnotationSerializer(annotation_obj).data)
            final_data = convert_string_lists_to_lists(final_data)
            return Response(final_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    annotations = AnnotationModel.objects.filter(job=job_id)
    if len(annotations) == 0:
        return Response([], status=status.HTTP_200_OK)

    serializer = GetAnnotationSerializer(annotations, many=True)
    temp_serializer = convert_string_lists_to_lists(serializer.data)
    return Response(temp_serializer, status=status.HTTP_200_OK)


@api_view(["GET", "DELETE", "PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def annotations(request, job_id, a_id, format=None):
    try:
        annotation = AnnotationModel.objects.get(id=a_id)
    except AnnotationModel.DoesNotExist:
        return Response(
            {"message": "Annotation with given Id does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "DELETE":
        annotation.delete()
        return Response(
            {"message": f"Annotation with {a_id} deleted successfully"},
            status=status.HTTP_200_OK,
        )

    if request.method == "PATCH":
        data = JSONParser().parse(request)

        labels = annotation.labels.values()
        for each_label in labels:
            label_obj = AnnotationDataModel.objects.get(id=each_label['id'])
            for each_annotation in label_obj.attributes.values():
                AnnotationAttributeModel.objects.get(
                    id=each_annotation['id']).delete()

            label_obj.delete()

        serializer = PostAnnotationSerializer(annotation, data=data)
        if serializer.is_valid():
            ann = serializer.save()
            for each_label in data["label"]:
                ann_data = {
                    "label": each_label["id"],
                    "name": LabelModel.objects.get(id=each_label["id"]).name,
                }
                ann_data_serializer = AnnotationDataSerializer(data=ann_data)
                if ann_data_serializer.is_valid():
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
                        if ann_attribute_serializer.is_valid():
                            ann_att_obj = ann_attribute_serializer.save()
                            ann_obj.attributes.add(ann_att_obj)
                        else:
                            return Response(
                                ann_attribute_serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                else:
                    return Response(
                        ann_data_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                    )

            final_data = dict(GetAnnotationSerializer(ann).data)
            final_data = convert_string_lists_to_lists(final_data)
            return Response(final_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    final_data = dict(GetAnnotationSerializer(annotation).data)
    final_data = convert_string_lists_to_lists(final_data)
    return Response(final_data, status=status.HTTP_200_OK)
