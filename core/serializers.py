from django.db import transaction
from rest_framework import serializers
from users.serializers import UserSerializer
from typing import Any, Dict, Iterable, Optional, OrderedDict, Union
from datetime import datetime
from .models import *



class AttributeSerializer(serializers.ModelSerializer):
    # values = serializers.CharField(max_length=4096, allow_blank=True)

    class Meta:
        model = Attribute
        fields = "__all__"

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
        print("new_label", attributes_data, label)
        self.create_attributes(label, attributes_data)
        return label

    @transaction.atomic
    def create_attributes(self, label, attributes_data):
        print("create new attributes", attributes_data)
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
        print("update-attributes", attributes_data)

        # Collect existing attribute IDs for the specific label
        existing_attribute_ids = set(attribute.id for attribute in label.attributes.all())

        for attribute_data in attributes_data:
            attribute_id = attribute_data.get('id', None)

            # Check if the attribute ID is present and it exists in the existing set
            if attribute_id is not None and attribute_id in existing_attribute_ids:
                attribute_instance = Attribute.objects.get(id=attribute_id)
                attribute_serializer = AttributeSerializer(attribute_instance, data=attribute_data)
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


        # print("update-attributes", attributes_data)
        # for attribute_data in attributes_data:
        #     attribute_id = attribute_data.get('id', None)
        #     if attribute_id is not None:
        #         attribute_instance = Attribute.objects.get(id=attribute_id)
        #         attribute_serializer = AttributeSerializer(
        #             attribute_instance, data=attribute_data)
        #         attribute_serializer.is_valid(raise_exception=True)
        #         attribute_serializer.save()
        #     else:
        #         attribute_obj = {
        #             **attribute_data,
        #             "label": label.id
        #         }
        #         attribute_serializer = AttributeSerializer(
        #             data=attribute_obj
        #         )
        #         attribute_serializer.is_valid(raise_exception=True)
        #         attribute_serializer.save()
        #         # label.attributes.add(attribute_serializer.instance)

    @classmethod
    @transaction.atomic
    def update_label(self, label, label_instance):
        print("update-labels-validated_data", label)
        print("update-labels-instance", label_instance)
        label_object = {
            "project": label.get("project",label_instance.project).id,
            "name": label.get("name", label_instance.name),
            "label_type": label.get("label_type", label_instance.label_type),
            "updated_at": datetime.now(),
        }

        attributes_data = label.pop('attributes', [])
        label_serializer = LabelWriteSerializer(
            label_instance, data=label_object, partial=True)
        label_serializer.is_valid(raise_exception=True)
        label = label_serializer.save()
        if len(attributes_data)>0:
            print("new_label", attributes_data,label)
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
        # read_only_fields = ("owner", "assignee")
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
        # print("create-project-validated_data", validated_data)
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
        # instance.owner_id = validated_data.get('owner_id', instance.owner_id)
        instance.assignee_id = validated_data.get(
            'assignee_id', instance.assignee_id)
        # print("update-project-instance", instance)
        print("update-project-validated_data", validated_data)
        labels = validated_data.get('labels', [])
        print(self)
        for label in labels:
            # update each label
            print("label", label)
            label_id = label.get('id', None)               
            if label_id is not None:
                label_instance = Label.objects.get(id=label_id)
                LabelWriteSerializer.update_label(
                    label,label_instance)
            else:
                label_object = {
                    "project": instance.id,
                    "name": label.get("name"),
                    "label_type": label.get("label_type"),
                }
                label_instance = LabelWriteSerializer(data=label_object)
                label_instance.is_valid(raise_exception=True)
                label_instance.save()

        # TODO: update storages
        # storages = _configure_related_storages({
        #     'source_storage': validated_data.pop('source_storage', None),
        #     'target_storage': validated_data.pop('target_storage', None),
        # })
        # update source and target storages
        # _update_related_storages(instance, validated_data)

        instance.save()

        # TODO: update Tasks and Jobs objects on labels update
        # if 'label_set' in validated_data:
        #     self.update_child_objects_on_labels_update(instance)

        return instance

    # @transaction.atomic
    # def update_child_objects_on_labels_update(self, instance: models.Project):
    #     models.Task.objects.filter(
    #         updated_date__lt=instance.updated_date, project=instance
    #     ).update(updated_date=instance.updated_date)
    #     models.Job.objects.filter(
    #         updated_date__lt=instance.updated_date, segment__task__project=instance
    #     ).update(updated_date=instance.updated_date)

    # @transaction.atomic
    # def update(self, instance, validated_data):
    #     data = validated_data.copy()
    #     print("update-project-validated_data",validated_data)

    #     source_serializer = StorageSerializer(
    #         instance.source_storage, data=data.pop("source_storage", {})
    #     )
    #     target_serializer = StorageSerializer(
    #         instance.target_storage, data=data.pop("target_storage", {})
    #     )

    #     if source_serializer.is_valid() and target_serializer.is_valid():
    #         src = source_serializer.save()
    #         tgt = target_serializer.save()
    #         data["source_storage"] = src
    #         data["target_storage"] = tgt

    #     serializer = ProjectWriteSerializer(instance, data=data)
    #     if serializer.is_valid():
    #         serializer.save()

    #         for each_label in data.get("labels", []):
    #             label_object = {
    #                 "project": instance.id,
    #                 "name": each_label["name"],
    #                 "label_type": each_label["label_type"],
    #             }
    #             if "id" in each_label:
    #                 label = LabelModel.objects.get(id=each_label["id"])
    #                 label_serializer = LabelWriteSerializer(
    #                     label, data=label_object
    #                 )
    #             else:
    #                 label_serializer = LabelWriteSerializer(data=label_object)

    #             if label_serializer.is_valid():
    #                 label_obj = label_serializer.save()
    #                 for each_attribute in each_label.get("attributes", []):
    #                     attribute_obj = {
    #                         "label": label_obj.id,
    #                         "name": each_attribute["name"],
    #                         "input_type": each_attribute["input_type"],
    #                         "default_value": each_attribute["default_value"],
    #                         "values": str(each_attribute["values"]),
    #                     }
    #                     if "id" in each_attribute:
    #                         attribute = AttributeModel.objects.get(
    #                             id=each_attribute["id"]
    #                         )
    #                         attribute_serializer = AttributeSerializer(
    #                             attribute, data=attribute_obj
    #                         )
    #                     else:
    #                         attribute_serializer = AttributeSerializer(
    #                             data=attribute_obj
    #                         )

    #                     if attribute_serializer.is_valid():
    #                         attribute_obj = attribute_serializer.save()
    #                         label_obj.attributes.add(attribute_obj)
    #                     else:
    #                         return attribute_serializer.errors

    #             else:
    #                 return label_serializer.errors

    #         return serializer.data

    #     return serializer.errors


class PostTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = "__all__"


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


class PostJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = "__all__"


class GetJobSerializer(serializers.ModelSerializer):
    assignee = UserSerializer()
    task = serializers.SerializerMethodField()
    # task_id = GetTaskSerializer()

    class Meta:
        model = Job
        # fields = '__all__'
        exclude = ["task_id"]

    def get_task(self, obj):
        if obj.task_id:
            task_serializer = GetTaskSerializer(obj.task_id)
            return task_serializer.data
        return None


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
