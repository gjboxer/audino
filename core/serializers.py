from django.db import transaction
from rest_framework import serializers
from users.serializers import UserSerializer
from typing import Any, Dict, Iterable, Optional, OrderedDict, Union
from datetime import datetime
from .models import *
from rest_framework.permissions import SAFE_METHODS
import ast
from django.contrib.auth import get_user_model
from iam.permissions import *
from .models import StageChoice, StateChoice, StatusChoice

class AttributeSerializer(serializers.ModelSerializer):
    # values = serializers.CharField(max_length=4096, allow_blank=True)

    class Meta:
        model = Attribute
        fields = "__all__"

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.values:
            representation['values'] = ast.literal_eval(instance.values)
        return representation

    def to_internal_value(self, data):
        data['values'] = str(data['values'])
        return super().to_internal_value(data)

    def create(self, validated_data):
        return super().create(validated_data)


class LabelWriteSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    attributes = AttributeSerializer(many=True, required=False)

    class Meta:
        model = Label
        fields = (
            "id",
            "name",
            "attributes",
            "label_type",
            "project",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at",)

    @transaction.atomic
    def create(self, validated_data):
        attributes_data = validated_data.pop('attributes', [])
        label = super().create(validated_data)
        self.create_attributes(label, attributes_data)
        return label

    @transaction.atomic
    def create_attributes(self, label, attributes_data):

        for attribute_data in attributes_data:
            attribute_obj = {
                "label": label.id,
                **attribute_data
            }
            attribute_serializer = AttributeSerializer(
                data=attribute_obj
            )
            attribute_serializer.is_valid(raise_exception=True)
            attribute_serializer.save()
            label.attributes.add(attribute_serializer.instance)

    @classmethod
    @transaction.atomic
    def update_attributes(self, label, attributes_data):
        # Collect existing attribute IDs for the specific label
        existing_attribute_ids = set(
            attribute.id for attribute in label.attributes.all())

        for attribute_data in attributes_data:
            attribute_id = attribute_data.get('id', None)

            # Check if the attribute ID is present and it exists in the existing set
            if attribute_id is not None and attribute_id in existing_attribute_ids:
                attribute_instance = Attribute.objects.get(id=attribute_id)
                attribute_serializer = AttributeSerializer(
                    attribute_instance, data=attribute_data)
                attribute_serializer.is_valid(raise_exception=True)
                attribute_serializer.save()

                # Remove the ID from the set as it's been processed
                existing_attribute_ids.remove(attribute_id)
            else:
                attribute_obj = {
                    **attribute_data,
                    "label": label.id
                }
                attribute_serializer = AttributeSerializer(data=attribute_obj)
                attribute_serializer.is_valid(raise_exception=True)
                attribute_serializer.save()
                label.attributes.add(attribute_serializer.instance)

        # Delete attributes that were not present in the updated data
        if existing_attribute_ids:
            label.attributes.filter(id__in=existing_attribute_ids).delete()

    @classmethod
    @transaction.atomic
    def update_label(self, label, label_instance):
        label_object = {
            "project": label.get("project", label_instance.project).id,
            "name": label.get("name", label_instance.name),
            "label_type": label.get("label_type", label_instance.label_type),
            "updated_at": datetime.now(),
        }

        attributes_data = label.pop('attributes', [])
        label_serializer = LabelWriteSerializer(
            label_instance, data=label_object, partial=True)
        label_serializer.is_valid(raise_exception=True)
        label = label_serializer.save()
        if len(attributes_data) > 0:
            self.update_attributes(label, attributes_data)

        return label


class LabelReadSerializer(serializers.ModelSerializer):
    attributes = AttributeSerializer(many=True, read_only=True)

    class Meta:
        model = Label
        fields = (
            "id",
            "name",
            "attributes",
            "label_type",
            "project",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
        extra_kwargs = {
            'project_id': {'required': False, 'allow_null': False},
            'task_id': {'required': False, 'allow_null': False},
        }


class StorageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Storage
        fields = "__all__"


def _configure_related_storages(validated_data: Dict[str, Any]) -> Dict[str, Optional[Storage]]:
    storages = {
        'source_storage': None,
        'target_storage': None,
    }

    for i in storages:
        if storage_conf := validated_data.get(i):
            storage_instance = Storage(**storage_conf)
            storage_instance.save()
            storages[i] = storage_instance
    return storages


class ProjectReadSerializer(serializers.ModelSerializer):
    source_storage = StorageSerializer()
    target_storage = StorageSerializer()
    owner = UserSerializer()
    assignee = UserSerializer()

    class Meta:
        model = Project
        fields = "__all__"
        read_only_fields = ("owner", "assignee",)
        extra_kwargs = {'organization': {'allow_null': True}}


class ProjectWriteSerializer(serializers.ModelSerializer):
    labels = LabelWriteSerializer(many=True, partial=True, default=[])
    assignee_id = serializers.IntegerField(
        write_only=True, allow_null=True, required=False)
    target_storage = StorageSerializer(required=False)
    source_storage = StorageSerializer(required=False)

    class Meta:
        model = Project
        fields = ("name", "source_storage", "target_storage",
                  "owner", "assignee_id", "organization", "labels")

    def to_representation(self, instance):
        serializer = ProjectReadSerializer(instance, context=self.context)
        return serializer.data

    @transaction.atomic
    def create(self, validated_data):
        labels_data = validated_data.pop('labels', [])
        storages = _configure_related_storages({
            'source_storage': validated_data.pop('source_storage', None),
            'target_storage': validated_data.pop('target_storage', None),
        })

        project = Project.objects.create(**storages, **validated_data)
        self.create_labels(project, labels_data)
        return project

    @transaction.atomic
    def create_labels(self, project, labels_data):
        for label_data in labels_data:
            label_object = {
                "project": project.id,
                **label_data
            }
            label_instance = LabelWriteSerializer(data=label_object)
            label_instance.is_valid(raise_exception=True)
            label_instance.save()

    @transaction.atomic
    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.assignee_id = validated_data.get(
            'assignee_id', instance.assignee_id)
        labels = validated_data.get('labels', [])
        storages = _configure_related_storages({
            'source_storage': validated_data.pop('source_storage', None),
            'target_storage': validated_data.pop('target_storage', None),
        })
        instance.source_storage = storages['source_storage']
        instance.target_storage = storages['target_storage']

        for label in labels:
            label_id = label.get('id', None)
            if label_id is not None:
                label_instance = Label.objects.get(id=label_id)
                LabelWriteSerializer.update_label(
                    label, label_instance)
            else:
                label_object = {
                    "project": instance.id,
                    "name": label.get("name"),
                    "label_type": label.get("label_type"),
                    **label,
                }
                label_instance = LabelWriteSerializer(data=label_object)
                label_instance.is_valid(raise_exception=True)
                label_instance.save()

        instance.save()

        # TODO: update Tasks and Jobs objects on labels update
        if 'labels' in validated_data:
            self.update_child_objects_on_labels_update(instance)

        return instance

    @transaction.atomic
    def update_child_objects_on_labels_update(self, instance: Project):
        Task.objects.filter(
            updated_at__lt=instance.updated_at, project=instance
        ).update(updated_at=instance.updated_at)
        Job.objects.filter(
            updated_at__lt=instance.updated_at
        ).update(updated_at=instance.updated_at)


class PostTaskSerializer(serializers.ModelSerializer):
    assignee_id = serializers.IntegerField(
        write_only=True, allow_null=True, required=False)
    project_id = serializers.IntegerField(
        write_only=True, allow_null=True, required=False)
    source_storage = StorageSerializer(required=False)
    target_storage = StorageSerializer(required=False)


    class Meta:
        model = Task
        fields = "__all__"

    def update_child_objects_on_labels_update(self, instance: Task):
        Job.objects.filter(
            updated_at__lt=instance.updated_date
        ).update(updated_at=instance.updated_date)
    
    @transaction.atomic
    def create(self, validated_data):
       
        project_id = validated_data.get("project_id")
        if not (validated_data.get("label_set") or project_id):
            raise serializers.ValidationError(
                'Label set or project_id must be present')
        if validated_data.get("label_set") and project_id:
            raise serializers.ValidationError(
                'Project must have only one of Label set or project_id')

        if project_id:
            try:
                project = Project.objects.get(id=project_id)
            except models.Project.DoesNotExist:
                raise serializers.ValidationError(
                    f'The specified project #{project_id} does not exist.')

            if project.organization != validated_data.get('organization'):
                raise serializers.ValidationError(
                    f'The task and its project should be in the same organization.')
            validated_data['project'] = project

        assignee_id = validated_data.pop('assignee_id', None)
        if assignee_id:
            try:
                assignee = User.objects.get(id=assignee_id)
            except models.User.DoesNotExist:
                raise serializers.ValidationError(
                    f'The specified assignee #{assignee_id} does not exist.')
            validated_data['assignee'] = assignee


        # configure source/target storages for import/export
        storages = _configure_related_storages({
            'source_storage': validated_data.pop('source_storage', None),
            'target_storage': validated_data.pop('target_storage', None),
        })

        db_task = Task.objects.create(
            **storages,
            **validated_data)

        db_task.save()
        return db_task


    @transaction.atomic
    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.assignee_id = validated_data.get(
            'assignee_id', instance.assignee_id)
        instance.project_id = validated_data.get(
            'project_id', instance.project_id)
        instance.subset = validated_data.get('subset', instance.subset)

        # configure source/target storages for import/export
        storages = _configure_related_storages({
            'source_storage': validated_data.pop('source_storage', None),
            'target_storage': validated_data.pop('target_storage', None),
        })
        instance.source_storage = storages['source_storage']
        instance.target_storage = storages['target_storage']

        instance.save()
        return instance


class GetTaskSerializer(serializers.ModelSerializer):
    source_storage = StorageSerializer()
    target_storage = StorageSerializer()
    owner = UserSerializer()
    assignee = UserSerializer()

    class Meta:
        model = Task
        fields = "__all__"
        extra_kwargs = {
            'organization': {'allow_null': True},
            'overlap': {'allow_null': True},
        }



class GetJobSerializer(serializers.ModelSerializer):
    assignee = UserSerializer()
    organization = serializers.ReadOnlyField(
        source='task_id.organization.id', allow_null=True)
    task = serializers.SerializerMethodField()

    class Meta:
        model = Job
        # fields = '__all__'
        exclude = ["task_id"]

    def get_task(self, obj):
        if obj.task_id:
            task_serializer = GetTaskSerializer(obj.task_id)
            return task_serializer.data
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
    
        if request := self.context.get('request'):
            perm = TaskPermission.create_scope_view(
                request, instance.task_id)
            result = perm.check_access()
            if result.allow:
                if task_source_storage := instance.get_source_storage():
                    data['source_storage'] = StorageSerializer(
                        task_source_storage).data
                if task_target_storage := instance.get_target_storage():
                    data['target_storage'] = StorageSerializer(
                        task_target_storage).data

        return data


class PostJobSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(choices=JobType.choices())

    class Meta:
        model = Job
        fields = "__all__"

    def to_representation(self, instance):
        serializer = GetJobSerializer(instance, context=self.context)
        return serializer.data

    def update(self, instance, validated_data):
        state = validated_data.get('state')
        stage = validated_data.get('stage')
        if stage:
            if stage == StageChoice.ANNOTATION:
                status = StatusChoice.ANNOTATION
            elif stage ==StageChoice.ACCEPTANCE and state == StateChoice.COMPLETED:
                status = StatusChoice.COMPLETED
            else:
                status = StatusChoice.VALIDATION

            validated_data['status'] = status
            if stage != instance.stage and not state:
                validated_data['state'] = StateChoice.NEW

        assignee = validated_data.get('assignee')
        if assignee is not None:
            validated_data['assignee'] = assignee

        instance = super().update(instance, validated_data)

        return instance


class AnnotationAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnotationAttribute
        fields = "__all__"


class DataSerializer(serializers.ModelSerializer):
    class Meta:
        model = Data
        fields = "__all__"


class AnnotationDataSerializer(serializers.ModelSerializer):
    attributes = AnnotationAttributeSerializer(many=True, read_only=True)

    class Meta:
        model = AnnotationData
        fields = "__all__"


class GetAnnotationSerializer(serializers.ModelSerializer):
    labels = AnnotationDataSerializer(many=True, read_only=True)

    class Meta:
        model = Annotation
        fields = "__all__"


class PostAnnotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Annotation
        fields = "__all__"
