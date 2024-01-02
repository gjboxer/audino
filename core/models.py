import os

from django.db import models
from users.models import User
from django.utils.text import slugify
from enum import Enum
from organizations.models import Organization
from typing import Any, Dict, Optional, Sequence
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction

def get_upload_path(instance, filename):
    return os.path.join("%s" % instance.task.name, filename)

class StageChoice(str, Enum):
    ANNOTATION = 'annotation'
    VALIDATION = 'validation'
    ACCEPTANCE = 'acceptance'

    @classmethod
    def choices(cls):
        return tuple((x.value, x.name) for x in cls)

    def __str__(self):
        return self.value

class StateChoice(str, Enum):
    NEW = 'new'
    IN_PROGRESS = 'in progress'
    COMPLETED = 'completed'
    REJECTED = 'rejected'

    @classmethod
    def choices(cls):
        return tuple((x.value, x.name) for x in cls)

    def __str__(self):
        return self.value

class JobType(str, Enum):
    ANNOTATION = 'annotation'
    GROUND_TRUTH = 'ground_truth'

    @classmethod
    def choices(cls):
        return tuple((x.value, x.name) for x in cls)

    def __str__(self):
        return self.value

class Storage(models.Model):
    STORAGE_CHOICES = (("local", "local"), ("cloud", "cloud"))
    location = models.CharField(
        max_length=255, choices=STORAGE_CHOICES, default="local"
    )
    cloud_storage_id = models.IntegerField(default=1)

    def __str__(self) -> str:
        return str(self.location)
        

class Project(models.Model):
    name = models.CharField(max_length=255)
    source_storage = models.ForeignKey(
        Storage, on_delete=models.CASCADE, null=True, related_name="source"
    )
    target_storage = models.ForeignKey(
        Storage, on_delete=models.CASCADE, null=True, related_name="target"
    )
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="owner"
    )
    organization = models.ForeignKey(Organization, null=True, default=None,
                                     blank=True, on_delete=models.SET_NULL, related_name="projects")
    assignee = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="assignee"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_labels(self):
        return self.labels.filter(project=self.id)


class Task(models.Model):
    SUBSET_CHOICES = (
        ("Test", "Test"),
        ("Train", "Train"),
        ("Validation", "Validation"),
    )
    name = models.CharField(max_length=200, null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, related_name="tasks",
                                related_query_name="task")
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="owners")
    subset = models.CharField(
        max_length=64, choices=SUBSET_CHOICES, default="train")
    assignee = models.ForeignKey(User, null=True,  blank=True,
                                 on_delete=models.SET_NULL, related_name="assignees")
    # labels = models.ManyToManyField(Label, default=None, blank=True)
    source_storage = models.ForeignKey(
        Storage,
        on_delete=models.CASCADE,
        null=True,
        related_name="source_stg",
    )
    target_storage = models.ForeignKey(
        Storage,
        on_delete=models.CASCADE,
        null=True,
        related_name="target_stg",
    )
    created_at = models.DateTimeField(auto_now_add=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True)
    organization = models.ForeignKey(Organization, null=True, default=None,
                                     blank=True, on_delete=models.SET_NULL, related_name="tasks")

    def __str__(self):
        return self.name

    def get_labels(self):
        project = self.project
        if project:
            return project.get_labels()
        return self.label


class Label(models.Model):
    LABEL_TYPE_CHOICES = (("any", "any"),)
    project = models.ForeignKey(
        Project,
        verbose_name="Projects",
        on_delete=models.CASCADE,
        null=True,
        related_name="labels",
    )
    name = models.CharField(max_length=65, blank=True, null=True)
    # color = models.CharField(max_length=20, default='#FF0000')
    attributes = models.ManyToManyField(
        "Attribute", default=None, related_name="labels", blank=True
    )
    label_type = models.CharField(
        max_length=255, choices=LABEL_TYPE_CHOICES, default="any"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    task = models.ForeignKey(
        Task, null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.id)

    @property
    def organization_id(self):
        if self.project is not None:
            return self.project.organization_id
        if self.task is not None:
            return self.task.organization_id
        return None


class Attribute(models.Model):
    INPUT_CHOICES = (("select", "select"), ("radio", "radio"))
    label = models.ForeignKey(
        Label, on_delete=models.CASCADE, default=None, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    mutable = models.BooleanField(default=False)
    input_type = models.CharField(
        max_length=10, choices=INPUT_CHOICES, default="select"
    )
    default_value = models.CharField(
        max_length=20, default="", blank=True, null=True)
    values = models.CharField(null=True, blank=True)

    def __str__(self):
        return str(self.id)

class Data(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        null=True,
        related_name="associated_task",
    )
    filename = models.CharField(max_length=500, blank=True, null=True)
    size = models.IntegerField(default=0)
    file = models.FileField(upload_to=get_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.filename

class JobType(str, Enum):
    ANNOTATION = 'annotation'
    GROUND_TRUTH = 'ground_truth'

    @classmethod
    def choices(cls):
        return tuple((x.value, x.name) for x in cls)

    def __str__(self):
        return self.value

class StatusChoice(str, Enum):
    """Deprecated. Use StageChoice and StateChoice instead"""

    ANNOTATION = 'annotation'
    VALIDATION = 'validation'
    COMPLETED = 'completed'

    @classmethod
    def choices(cls):
        return tuple((x.value, x.name) for x in cls)

    @classmethod
    def list(cls):
        return list(map(lambda x: x.value, cls))

    def __str__(self):
        return self.value

class Job(models.Model):
    task_id = models.ForeignKey(Task, on_delete=models.CASCADE, null=True)
    project_id = models.ForeignKey(
        Project, on_delete=models.CASCADE, null=True)
    assignee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="job_assignee",
    )
    guide_id = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="guide"
    )
    stage = models.CharField(max_length=32, choices=StageChoice.choices(),
        default=StageChoice.ANNOTATION)
    state = models.CharField(max_length=32, choices=StateChoice.choices(),
        default=StateChoice.NEW)
    status = models.CharField(max_length=32, choices=StatusChoice.choices(),
        default=StatusChoice.ANNOTATION)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    type = models.CharField(max_length=32, choices=JobType.choices(),
        default=JobType.ANNOTATION)
    
    def get_target_storage(self) -> Optional[Storage]:
        return self.task_id.target_storage

    def get_source_storage(self) -> Optional[Storage]:
        return self.task_id.source_storage
    

    @transaction.atomic
    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        return super().save(*args, **kwargs)

    def get_labels(self):
        task=self.task_id
        project = self.task_id.project
        return project.get_labels() if project else task.get_labels()

    @property
    def organization_id(self):
        return self.task_id.organization_id
    
    def get_organization_slug(self):
        return self.task_id.organization.slug

    def get_task_id(self):
        task = self.task_id
        return task.id if task else None

    def delete(self, using=None, keep_parents=False):
        super().delete(using, keep_parents)

    class Meta:
        default_permissions = ()


class AnnotationAttribute(models.Model):
    attribute = models.ForeignKey(
        Attribute, on_delete=models.CASCADE, blank=True, null=True
    )
    values = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return str(self.id)


class AnnotationData(models.Model):
    label = models.ForeignKey(
        Label, on_delete=models.CASCADE, null=True, related_name="annotation_label"
    )
    name = models.CharField(max_length=200, blank=True, null=True)
    attributes = models.ManyToManyField(
        AnnotationAttribute, blank=True, related_name="annotation_attribute"
    )

    def __str__(self):
        return str(self.id)


class Annotation(models.Model):
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="annotation_job",
        null=True,
    )
    start = models.CharField(max_length=200, blank=True, null=True)
    end = models.CharField(max_length=200, blank=True, null=True)
    color = models.CharField(max_length=200, blank=True, null=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    transcription = models.TextField(blank=True, null=True)
    labels = models.ManyToManyField(
        AnnotationData, blank=True, related_name="annotation_data"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.name
