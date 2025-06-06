import requests
from django.db.models import Sum
from django.utils import timezone
from django_q.tasks import async_task
from django.db.models import Q

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.v1.v1_data.constants import DataApprovalStatus
from api.v1.v1_data.models import (
    FormData,
    Answers,
    PendingDataApproval,
    PendingDataBatch,
    PendingDataBatchComments,
    AnswerHistory,
)
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import (
    Questions,
    Forms,
    FormApprovalAssignment,
)
from api.v1.v1_profile.constants import UserRoleTypes
from api.v1.v1_profile.models import Administration, EntityData, Levels
from api.v1.v1_users.models import SystemUser, Organisation
from utils.custom_serializer_fields import (
    CustomPrimaryKeyRelatedField,
    UnvalidatedField,
    CustomListField,
    CustomCharField,
    CustomChoiceField,
    CustomBooleanField,
    CustomIntegerField,
)
from utils.default_serializers import CommonDataSerializer
from utils.email_helper import send_email, EmailTypes
from utils.functions import update_date_time_format, get_answer_value
from utils.functions import get_answer_history
from mis.settings import APP_NAME


class SubmitFormDataSerializer(serializers.ModelSerializer):
    administration = CustomPrimaryKeyRelatedField(
        queryset=Administration.objects.none()
    )
    name = CustomCharField()
    geo = CustomListField(required=False, allow_null=True)
    submitter = CustomCharField(required=False)
    duration = CustomIntegerField(required=False)
    uuid = serializers.CharField(required=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get(
            "administration"
        ).queryset = Administration.objects.all()

    class Meta:
        model = FormData
        fields = [
            "name",
            "geo",
            "administration",
            "submitter",
            "duration",
            "uuid",
        ]


class SubmitFormDataAnswerSerializer(serializers.ModelSerializer):
    value = UnvalidatedField(allow_null=False)
    question = CustomPrimaryKeyRelatedField(queryset=Questions.objects.none())
    index = CustomIntegerField(required=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("question").queryset = Questions.objects.all()

    def validate_value(self, value):
        return value

    def validate(self, attrs):
        if attrs.get("value") == "":
            raise ValidationError(
                "Value is required for Question:{0}".format(
                    attrs.get("question").id
                )
            )

        if (
            isinstance(attrs.get("value"), list)
            and len(attrs.get("value")) == 0
        ):
            raise ValidationError(
                "Value is required for Question:{0}".format(
                    attrs.get("question").id
                )
            )

        if not isinstance(attrs.get("value"), list) and attrs.get(
            "question"
        ).type in [
            QuestionTypes.geo,
            QuestionTypes.option,
            QuestionTypes.multiple_option,
        ]:
            raise ValidationError(
                "Valid list value is required for Question:{0}".format(
                    attrs.get("question").id
                )
            )
        elif not isinstance(attrs.get("value"), str) and attrs.get(
            "question"
        ).type in [
            QuestionTypes.text,
            QuestionTypes.photo,
            QuestionTypes.date,
            QuestionTypes.attachment,
            QuestionTypes.signature,
        ]:
            raise ValidationError(
                "Valid string value is required for Question:{0}".format(
                    attrs.get("question").id
                )
            )
        elif not (
            isinstance(attrs.get("value"), int)
            or isinstance(attrs.get("value"), float)
        ) and attrs.get("question").type in [
            QuestionTypes.number,
            QuestionTypes.administration,
            QuestionTypes.cascade,
        ]:
            raise ValidationError(
                "Valid number value is required for Question:{0}".format(
                    attrs.get("question").id
                )
            )

        if attrs.get("question").type == QuestionTypes.administration:
            attrs["value"] = int(float(attrs.get("value")))

        return attrs

    class Meta:
        model = Answers
        fields = ["question", "value", "index"]


class SubmitFormSerializer(serializers.Serializer):
    data = SubmitFormDataSerializer()
    answer = SubmitFormDataAnswerSerializer(many=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        data = validated_data.get("data")
        data["form"] = self.context.get("form")
        data["created_by"] = self.context.get("user")
        data["updated_by"] = self.context.get("user")
        obj_data = self.fields.get("data").create(data)
        # Answer value based on Question type
        # - geo = 1 #option
        # - administration = 2 #value
        # - text = 3 #name
        # - number = 4 #value
        # - option = 5 #option
        # - multiple_option = 6 #option
        # - cascade = 7 #option
        # - photo = 8 #name
        # - date = 9 #name
        # - autofield = 10 #name
        # - attachment = 11 #name

        for answer in validated_data.get("answer"):
            name = None
            value = None
            option = None

            if answer.get("question").type in [
                QuestionTypes.geo,
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ]:
                option = answer.get("value")
            elif answer.get("question").type in [
                QuestionTypes.text,
                QuestionTypes.photo,
                QuestionTypes.date,
                QuestionTypes.autofield,
                QuestionTypes.attachment,
                QuestionTypes.signature,
            ]:
                name = answer.get("value")
            elif answer.get("question").type == QuestionTypes.cascade:
                id = answer.get("value")
                ep = answer.get("question").api.get("endpoint")
                val = None
                if "organisation" in ep:
                    val = Organisation.objects.filter(pk=id).first()
                    val = val.name
                if "entity-data" in ep:
                    val = EntityData.objects.filter(pk=id).first()
                    val = val.name
                if "entity-data" not in ep and "organisation" not in ep:
                    ep = ep.split("?")[0]
                    ep = f"{ep}?id={id}"
                    val = requests.get(ep).json()
                    val = val[0].get("name")
                name = val
            else:
                # for administration,number question type
                value = answer.get("value")

            Answers.objects.create(
                data=obj_data,
                question=answer.get("question"),
                name=name,
                value=value,
                options=option,
                created_by=self.context.get("user"),
            )
        obj_data.save_to_file

        return object


class AnswerHistorySerializer(serializers.Serializer):
    value = serializers.FloatField()
    created = CustomCharField()
    created_by = CustomCharField()


class ListDataAnswerSerializer(serializers.ModelSerializer):
    history = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()

    @extend_schema_field(AnswerHistorySerializer(many=True))
    def get_history(self, instance):
        answer_history = AnswerHistory.objects.filter(
            data=instance.data, question=instance.question
        ).all()
        history = []
        for h in answer_history:
            history.append(get_answer_history(h))
        return history if history else None

    @extend_schema_field(OpenApiTypes.ANY)
    def get_value(self, instance: Answers):
        return get_answer_value(instance)

    class Meta:
        model = Answers
        fields = ["history", "question", "value", "index"]


class FormDataSerializer(serializers.ModelSerializer):
    answers = serializers.SerializerMethodField()

    @extend_schema_field(ListDataAnswerSerializer(many=True))
    def get_answers(self, instance):
        return ListDataAnswerSerializer(
            instance=instance.data_answer.all(), many=True
        ).data

    class Meta:
        model = FormData
        fields = [
            "id",
            "uuid",
            "name",
            "form",
            "administration",
            "geo",
            "created_by",
            "updated_by",
            "created",
            "updated",
            "submitter",
            "duration",
            "answers",
        ]


class ListFormDataRequestSerializer(serializers.Serializer):
    administration = CustomPrimaryKeyRelatedField(
        queryset=Administration.objects.none(), required=False
    )
    questions = CustomListField(
        child=CustomPrimaryKeyRelatedField(queryset=Questions.objects.none()),
        required=False,
    )
    parent = serializers.CharField(required=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get(
            "administration"
        ).queryset = Administration.objects.all()
        self.fields.get("questions").child.queryset = Questions.objects.all()


class ListFormDataSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()
    updated = serializers.SerializerMethodField()
    administration = serializers.SerializerMethodField()
    pending_data = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_created_by(self, instance: FormData):
        return instance.created_by.get_full_name()

    @extend_schema_field(OpenApiTypes.STR)
    def get_updated_by(self, instance: FormData):
        if instance.updated_by:
            return instance.updated_by.get_full_name()
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_created(self, instance: FormData):
        return update_date_time_format(instance.created)

    @extend_schema_field(OpenApiTypes.STR)
    def get_updated(self, instance: FormData):
        return update_date_time_format(instance.updated)

    @extend_schema_field(
        inline_serializer(
            "HasPendingData",
            fields={
                "id": serializers.IntegerField(),
                "created_by": serializers.CharField(),
            },
        )
    )
    def get_pending_data(self, instance: FormData):
        # Check if there's a pending version of this data point
        batch = None
        pending_data = FormData.objects.select_related(
            "created_by"
        ).filter(uuid=instance.uuid, is_pending=True).first()
        if pending_data:
            batch = PendingDataBatch.objects.filter(
                pk=pending_data.batch_id
            ).first()
        if pending_data and (not batch or not batch.approved):
            return {
                "id": pending_data.id,
                "created_by": pending_data.created_by.get_full_name(),
            }
        return None

    def get_administration(self, instance: FormData):
        return " - ".join(instance.administration.full_name.split("-")[1:])

    class Meta:
        model = FormData
        fields = [
            "id",
            "uuid",
            "name",
            "form",
            "administration",
            "geo",
            "created_by",
            "updated_by",
            "created",
            "updated",
            "pending_data",
            "submitter",
        ]


class ListOptionsChartCriteriaSerializer(serializers.Serializer):
    question = CustomPrimaryKeyRelatedField(queryset=Questions.objects.none())
    option = CustomListField()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("question").queryset = Questions.objects.all()


class ListPendingDataAnswerSerializer(serializers.ModelSerializer):
    history = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()
    last_value = serializers.SerializerMethodField()

    @extend_schema_field(AnswerHistorySerializer(many=True))
    def get_history(self, instance):
        answer_history = AnswerHistory.objects.filter(
            data=instance.data, question=instance.question
        ).all()
        history = []
        for h in answer_history:
            history.append(get_answer_history(h))
        return history if history else None

    @extend_schema_field(OpenApiTypes.ANY)
    def get_value(self, instance: Answers):
        return get_answer_value(instance)

    @extend_schema_field(OpenApiTypes.ANY)
    def get_last_value(self, instance: Answers):
        if self.context["last_data"]:
            parent_question = None
            if instance.question.form.parent:
                # If the question is from a parent form,
                # get the parent question from the parent form
                qg = instance.question.form.parent \
                    .form_question_group.filter(
                        name=instance.question.question_group.name
                    ).first()
                if qg:
                    parent_question = qg.question_group_question.filter(
                        name=instance.question.name
                    ).first()
            answer = (
                self.context["last_data"]
                .data_answer.filter(
                    Q(
                        question=instance.question,
                        index=instance.index,
                    ) |
                    Q(
                        question=parent_question,
                        index=instance.index,
                    )
                )
                .first()
            )
            if answer:
                return get_answer_value(answer=answer)
        return None

    class Meta:
        model = Answers
        fields = ["history", "question", "value", "last_value", "index"]


class PendingBatchDataFilterSerializer(serializers.Serializer):
    approved = CustomBooleanField(default=False)
    subordinate = CustomBooleanField(default=False)


class ListPendingDataBatchSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()
    approver = serializers.SerializerMethodField()
    form = serializers.SerializerMethodField()
    administration = serializers.SerializerMethodField()
    total_data = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_created_by(self, instance: PendingDataBatch):
        return instance.user.get_full_name()

    @extend_schema_field(OpenApiTypes.INT)
    def get_total_data(self, instance: PendingDataBatch):
        return instance.batch_form_data.count()

    @extend_schema_field(CommonDataSerializer)
    def get_form(self, instance: PendingDataBatch):
        return {
            "id": instance.form.id,
            "name": instance.form.name,
            "approval_instructions": instance.form.approval_instructions,
        }

    @extend_schema_field(CommonDataSerializer)
    def get_administration(self, instance: PendingDataBatch):
        return {
            "id": instance.administration_id,
            "name": instance.administration.name,
        }

    @extend_schema_field(OpenApiTypes.STR)
    def get_created(self, instance: PendingDataBatch):
        return update_date_time_format(instance.created)

    @extend_schema_field(
        inline_serializer(
            "PendingBatchApprover",
            fields={
                "id": serializers.IntegerField(),
                "name": serializers.CharField(),
                "status": serializers.IntegerField(),
                "status_text": serializers.CharField(),
                "allow_approve": serializers.BooleanField(),
            },
        )
    )
    def get_approver(self, instance: PendingDataBatch):
        user: SystemUser = self.context.get("user")
        approved: bool = self.context.get("approved")
        next_level = (
            user.user_access.administration.level.level - 1
            if approved
            else user.user_access.administration.level.level + 1
        )
        approval = (
            instance.batch_approval.filter(
                level__level=next_level, status=DataApprovalStatus.pending
            )
            .order_by("-level__level")
            .first()
        )
        rejected: PendingDataApproval = instance.batch_approval.filter(
            status=DataApprovalStatus.rejected
        ).first()
        lowest_level = Levels.objects.order_by("-id")[1:2].first()
        data = {}
        if rejected:
            data["id"] = rejected.user.pk
            data["status"] = rejected.status
            data["status_text"] = DataApprovalStatus.FieldStr.get(
                rejected.status
            )
            if rejected.user.user_access.administration.level == lowest_level:
                data["name"] = instance.user.get_full_name()
            else:
                prev_level = (
                    rejected.user.user_access.administration.level.level + 1
                )
                waiting_on = instance.batch_approval.filter(
                    level__level=prev_level
                ).first()
                data["name"] = waiting_on.user.get_full_name()
        if not rejected and approval:
            data["id"] = approval.user.pk
            data["name"] = approval.user.get_full_name()
            data["status"] = approval.status
            data["status_text"] = DataApprovalStatus.FieldStr.get(
                approval.status
            )
            if approval.status == DataApprovalStatus.approved:
                data["allow_approve"] = True
            else:
                data["allow_approve"] = False
        if not approval and not rejected:
            approval = instance.batch_approval.get(user=user)
            data["id"] = approval.user.pk
            data["name"] = approval.user.get_full_name()
            data["status"] = approval.status
            data["status_text"] = DataApprovalStatus.FieldStr.get(
                approval.status
            )
            data["allow_approve"] = True
        final_approved = instance.batch_approval.filter(
            status=DataApprovalStatus.approved, level__level=1
        ).count()
        if final_approved:
            data["name"] = "-"
        return data

    class Meta:
        model = PendingDataBatch
        fields = [
            "id",
            "name",
            "form",
            "administration",
            "created_by",
            "created",
            "approver",
            "approved",
            "total_data",
        ]


class ListPendingFormDataSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()
    administration = serializers.ReadOnlyField(source="administration.name")
    answer_history = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_created_by(self, instance: FormData):
        return instance.created_by.get_full_name()

    @extend_schema_field(OpenApiTypes.STR)
    def get_created(self, instance: FormData):
        return update_date_time_format(instance.created)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_answer_history(self, instance: FormData):
        # Check for history in answer_history table
        history = AnswerHistory.objects.filter(
            data=instance
        ).count()
        return True if history > 0 else False

    class Meta:
        model = FormData
        fields = [
            "id",
            "uuid",
            "name",
            "form",
            "administration",
            "geo",
            "submitter",
            "duration",
            "created_by",
            "created",
            "answer_history",
        ]


class ApprovePendingDataRequestSerializer(serializers.Serializer):
    batch = CustomPrimaryKeyRelatedField(
        queryset=PendingDataBatch.objects.none()
    )
    status = CustomChoiceField(
        choices=[DataApprovalStatus.approved, DataApprovalStatus.rejected]
    )
    comment = CustomCharField(required=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        user: SystemUser = self.context.get("user")
        if user:
            self.fields.get(
                "batch"
            ).queryset = PendingDataBatch.objects.filter(
                batch_approval__user=user, approved=False
            )

    def create(self, validated_data):
        batch: PendingDataBatch = validated_data.get("batch")
        user = self.context.get("user")
        comment = validated_data.get("comment")
        user_level = user.user_access.administration.level
        approval = PendingDataApproval.objects.get(user=user, batch=batch)
        approval.status = validated_data.get("status")
        approval.save()
        # Get the first form data in the batch to get submitter email
        first_data = FormData.objects.filter(
            batch=batch, is_pending=True
        ).first()
        data_count = FormData.objects.filter(
            batch=batch, is_pending=True
        ).count()
        data = {
            "send_to": [first_data.created_by.email],
            "batch": batch,
            "user": user,
        }
        listing = [
            {
                "name": "Batch Name",
                "value": batch.name,
            },
            {
                "name": "Number of Records",
                "value": data_count,
            },
            {
                "name": "Questionnaire",
                "value": batch.form.name,
            },
        ]
        if approval.status == DataApprovalStatus.approved:
            listing.append(
                {
                    "name": "Approver",
                    "value": f"{user.name}",
                }
            )
            if comment:
                listing.append({"name": "Comment", "value": comment})
            data.update(
                {
                    "listing": listing,
                    "extend_body": (
                        "Further approvals may be required "
                        "before data is finalised."
                        "You can also track your data approval in the "
                        f"{APP_NAME} platform "
                        "[Data > Manage Submissions > Pending Approval]"
                    ),
                }
            )
            send_email(context=data, type=EmailTypes.batch_approval)
        else:
            listing.append(
                {
                    "name": "Rejector",
                    "value": f"{user.name}",
                }
            )
            if comment:
                listing.append({"name": "Comment", "value": comment})
            # rejection request change to user
            data.update(
                {
                    "listing": listing,
                    "extend_body": (
                        "You can also access the rejected data "
                        f"in the {APP_NAME} platform "
                        "[My Profile > Data uploads > Rejected]"
                    ),
                }
            )
            send_email(context=data, type=EmailTypes.batch_rejection)
            # send email to lower approval
            lower_approvals = PendingDataApproval.objects.filter(
                batch=batch, level__level__gt=user_level.level
            ).all()
            # filter --> send email only to lower approval
            lower_approval_user_ids = [u.user_id for u in lower_approvals]
            lower_approval_users = SystemUser.objects.filter(
                id__in=lower_approval_user_ids, deleted_at=None
            ).all()
            lower_approval_emails = [
                u.email for u in lower_approval_users if u.email != user.email
            ]
            if lower_approval_emails:
                inform_data = {
                    "send_to": lower_approval_emails,
                    "listing": listing,
                    "extend_body": """
                    The data submitter has also been notified.
                    They can modify the data and submit again for approval
                    """,
                }
                send_email(
                    context=inform_data,
                    type=EmailTypes.inform_batch_rejection_approver,
                )
        if validated_data.get("comment"):
            PendingDataBatchComments.objects.create(
                user=user, batch=batch, comment=validated_data.get("comment")
            )
        if not PendingDataApproval.objects.filter(
            batch=batch,
            status__in=[
                DataApprovalStatus.pending,
                DataApprovalStatus.rejected,
            ],
        ).count():
            # Get all pending data for this batch
            form_data_list = FormData.objects.filter(
                batch=batch, is_pending=True
            ).all()
            # Seed data via Async Task
            for data in form_data_list:
                async_task("api.v1.v1_data.tasks.seed_approved_data", data)
            batch.approved = True
            batch.updated = timezone.now()
            batch.save()
        return object

    def update(self, instance, validated_data):
        pass


class ListBatchSerializer(serializers.ModelSerializer):
    form = serializers.SerializerMethodField()
    administration = serializers.SerializerMethodField()
    file = serializers.SerializerMethodField()
    total_data = serializers.SerializerMethodField()
    status = serializers.ReadOnlyField(source="approved")
    approvers = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()
    updated = serializers.SerializerMethodField()

    @extend_schema_field(CommonDataSerializer)
    def get_form(self, instance: PendingDataBatch):
        return {
            "id": instance.form.id,
            "name": instance.form.name,
            "approval_instructions": instance.form.approval_instructions,
        }

    @extend_schema_field(CommonDataSerializer)
    def get_administration(self, instance: PendingDataBatch):
        return {
            "id": instance.administration_id,
            "name": instance.administration.name,
        }

    @extend_schema_field(
        inline_serializer(
            "BatchFile",
            fields={
                "name": serializers.CharField(),
                "file": serializers.URLField(),
            },
        )
    )
    def get_file(self, instance: PendingDataBatch):
        if instance.file:
            path = instance.file
            first_pos = path.rfind("/")
            last_pos = len(path)
            return {
                "name": path[first_pos + 1: last_pos],
                "file": instance.file,
            }
        return None

    @extend_schema_field(OpenApiTypes.INT)
    def get_total_data(self, instance: PendingDataBatch):
        return instance.batch_form_data.all().count()

    @extend_schema_field(
        inline_serializer(
            "BatchApprover",
            fields={
                "name": serializers.CharField(),
                "administration": serializers.CharField(),
                "status": serializers.IntegerField(),
                "status_text": serializers.CharField(),
            },
            many=True,
        )
    )
    def get_approvers(self, instance: PendingDataBatch):
        data = []
        approvers = instance.batch_approval.order_by(
            "level"
        ).all()
        for approver in approvers:
            approver_administration = approver.user.user_access.administration
            data.append(
                {
                    "name": approver.user.get_full_name(),
                    "administration": approver_administration.name,
                    "status": approver.status,
                    "status_text": DataApprovalStatus.FieldStr.get(
                        approver.status
                    ),
                }
            )
        return data

    @extend_schema_field(OpenApiTypes.DATE)
    def get_created(self, instance):
        return update_date_time_format(instance.created)

    @extend_schema_field(OpenApiTypes.DATE)
    def get_updated(self, instance):
        return update_date_time_format(instance.updated)

    class Meta:
        model = PendingDataBatch
        fields = [
            "id",
            "name",
            "form",
            "administration",
            "file",
            "total_data",
            "created",
            "updated",
            "status",
            "approvers",
        ]


class ListBatchSummarySerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source="question.id")
    question = serializers.ReadOnlyField(source="question.label")
    type = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()

    @extend_schema_field(
        CustomChoiceField(
            choices=[QuestionTypes.FieldStr[d] for d in QuestionTypes.FieldStr]
        )
    )
    def get_type(self, instance):
        return QuestionTypes.FieldStr.get(instance.question.type)

    @extend_schema_field(OpenApiTypes.ANY)
    def get_value(self, instance):
        batch = self.context.get("batch")
        if instance.question.type == QuestionTypes.number:
            val = Answers.objects.filter(
                data__batch=batch,
                data__is_pending=True,
                question_id=instance.question.id
            ).aggregate(Sum("value"))
            return val.get("value__sum")
        elif instance.question.type == QuestionTypes.administration:
            return (
                Answers.objects.filter(
                    data__batch=batch,
                    data__is_pending=True,
                    question_id=instance.question.id
                )
                .distinct("value")
                .count()
            )
        else:
            data = []
            for option in instance.question.options.all():
                val = Answers.objects.filter(
                    data__batch=batch,
                    data__is_pending=True,
                    question_id=instance.question.id,
                    options__contains=option.value,
                ).count()
                data.append({"type": option.label, "total": val})
            return data

    class Meta:
        model = Answers
        fields = ["id", "question", "type", "value"]


class ListBatchCommentSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()

    @extend_schema_field(
        inline_serializer(
            "BatchUserComment",
            fields={
                "name": serializers.CharField(),
                "email": serializers.CharField(),
            },
        )
    )
    def get_user(self, instance: PendingDataBatchComments):
        return {
            "name": instance.user.get_full_name(),
            "email": instance.user.email,
        }

    @extend_schema_field(OpenApiTypes.DATE)
    def get_created(self, instance: PendingDataBatchComments):
        return update_date_time_format(instance.created)

    class Meta:
        model = PendingDataBatchComments
        fields = ["user", "comment", "created"]


class BatchListRequestSerializer(serializers.Serializer):
    approved = CustomBooleanField(default=False)
    form = CustomPrimaryKeyRelatedField(
        queryset=Forms.objects.filter(parent__isnull=True).all(),
        required=False
    )


class CreateBatchSerializer(serializers.Serializer):
    name = CustomCharField()
    comment = CustomCharField(required=False)
    data = CustomListField(
        child=CustomPrimaryKeyRelatedField(
            queryset=FormData.objects.none()
        ),
        required=False,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("data").child.queryset = FormData.objects.filter(
            is_pending=True
            )

    def validate_name(self, name):
        if PendingDataBatch.objects.filter(name__iexact=name).exists():
            raise ValidationError("name has already been taken")
        return name

    def validate_data(self, data):
        if len(data) == 0:
            raise ValidationError("No data found for this batch")
        return data

    def validate(self, attrs):
        if len(attrs.get("data")) == 0:
            raise ValidationError(
                {"data": "No form found for this batch"}
            )
        form = attrs.get("data")[0].form
        # Get the list of administrations that the user has access to
        adms = [
            ac.pk
            for ac in self.context.get("user")
            .user_access.administration.ancestors
        ]
        adms += [
            self.context.get("user").user_access.administration.pk
        ]
        # Check if the form has any approvers in the user's administration
        form_approval = form.form_data_approval.filter(
            administration__pk__in=adms
        ).exists()
        # If no direct form approval exists,
        # check if any parent form has approvers
        if not form_approval and hasattr(form, 'parent') and form.parent:
            # Get all parent forms up the hierarchy
            parent_forms = []
            current_form = form.parent
            while current_form:
                parent_forms.append(current_form.id)
                current_form = current_form.parent
            # Check if any parent form has approval assignments
            if parent_forms:
                for parent_id in parent_forms:
                    parent_approval = FormApprovalAssignment.objects.filter(
                        form_id=parent_id,
                        administration__pk__in=adms
                    ).exists()
                    if parent_approval:
                        form_approval = True
                        break
        if not form_approval:
            raise ValidationError(
                {"data": "No approvers found for this batch"}
            )
        for pending in attrs.get("data"):
            if pending.form_id != form.id:
                raise ValidationError({
                    "data": (
                        "Mismatched form ID for one or more"
                        " pending data items."
                    )
                })
        return attrs

    def create(self, validated_data):
        form_id = validated_data.get("data")[0].form_id
        user: SystemUser = validated_data.get("user")
        path = "{0}{1}".format(
            user.user_access.administration.path,
            user.user_access.administration_id,
        )
        obj = PendingDataBatch.objects.create(
            form_id=form_id,
            administration_id=user.user_access.administration_id,
            user=user,
            name=validated_data.get("name"),
        )
        for data in validated_data.get("data"):
            data.batch = obj
            data.save()
        for administration in Administration.objects.filter(
            id__in=path.split(".")
        ):
            assignment = FormApprovalAssignment.objects.filter(
                form_id=form_id, administration=administration
            ).first()
            if assignment:
                level = assignment.user.user_access.administration.level_id
                PendingDataApproval.objects.create(
                    batch=obj, user=assignment.user, level_id=level
                )
                number_of_records = obj.batch_form_data.count()
                data = {
                    "send_to": [assignment.user.email],
                    "listing": [
                        {"name": "Batch Name", "value": obj.name},
                        {"name": "Questionnaire", "value": obj.form.name},
                        {
                            "name": "Number of Records",
                            "value": number_of_records,
                        },
                        {
                            "name": "Submitter",
                            "value": f"""{obj.user.name}""",
                        },
                    ],
                }
                send_email(context=data, type=EmailTypes.pending_approval)
        if validated_data.get("comment"):
            PendingDataBatchComments.objects.create(
                user=user, batch=obj, comment=validated_data.get("comment")
            )
        return obj


class SubmitPendingFormSerializer(serializers.Serializer):
    data = SubmitFormDataSerializer()
    answer = SubmitFormDataAnswerSerializer(many=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def create(self, validated_data):
        data = validated_data.get("data")
        data["form"] = self.context.get("form")
        data["created_by"] = self.context.get("user")

        # check user role and form type
        user = self.context.get("user")
        is_super_admin = user.user_access.role == UserRoleTypes.super_admin

        direct_to_data = is_super_admin
        # Check if the form has any approvers in the user's administration
        # If no approvers found, save directly to
        # form data without pending status
        if not direct_to_data:
            adms = [user.user_access.administration.pk]
            if user.user_access.administration.parent:
                adms = [
                    ac.pk
                    for ac in user.user_access.administration.ancestors
                ] + adms
            form_approval = FormApprovalAssignment.objects.filter(
                form=data["form"],
                administration__pk__in=adms
            ).exists()
            # If no direct approval assignment exists,
            # check if it's a child form
            if (
                not form_approval and
                hasattr(data["form"], 'parent') and
                data["form"].parent
            ):
                # Get all parent forms up the hierarchy
                parent_forms = []
                current_form = data["form"].parent
                while current_form:
                    parent_forms.append(current_form.id)
                    current_form = current_form.parent
                # Check if any parent form has approval assignments
                if parent_forms:
                    form_approval = FormApprovalAssignment.objects.filter(
                        form_id__in=parent_forms,
                        administration__pk__in=adms
                    ).exists()
            if not form_approval:
                direct_to_data = True

        obj_data = self.fields.get("data").create(data)
        if data.get("uuid"):
            obj_data.uuid = data["uuid"]
            # find parent data by uuid and parent form
            parent_data = FormData.objects.filter(
                uuid=data["uuid"],
                form__parent__isnull=True,
            ).first()
            if parent_data:
                # if parent data exists, link the child data
                obj_data.parent = parent_data
            obj_data.save()

        if not direct_to_data:
            # If not direct to data, set pending status
            obj_data.is_pending = True
            obj_data.save()

        answers = []

        for answer in validated_data.get("answer"):
            question = answer.get("question")
            name = None
            value = None
            option = None

            if question.type in [
                QuestionTypes.geo,
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ]:
                option = answer.get("value")
            elif question.type in [
                QuestionTypes.text,
                QuestionTypes.photo,
                QuestionTypes.date,
                QuestionTypes.autofield,
                QuestionTypes.attachment,
                QuestionTypes.signature,
            ]:
                name = answer.get("value")
            elif question.type == QuestionTypes.cascade:
                id = answer.get("value")
                val = None
                if question.api:
                    ep = question.api.get("endpoint")
                    if "organisation" in ep:
                        name = Organisation.objects.filter(pk=id).values_list(
                            'name', flat=True).first()
                        val = name
                    if "entity-data" in ep:
                        name = EntityData.objects.filter(pk=id).values_list(
                            'name', flat=True).first()
                        val = name
                    if "entity-data" not in ep and "organisation" not in ep:
                        ep = ep.split("?")[0]
                        ep = f"{ep}?id={id}"
                        val = requests.get(ep).json()
                        val = val[0].get("name")

                if question.extra:
                    cs_type = question.extra.get("type")
                    if cs_type == "entity":
                        name = EntityData.objects.filter(pk=id).values_list(
                            'name', flat=True).first()
                        val = name
                name = val
            else:
                # for administration,number question type
                value = answer.get("value")

            answers.append(Answers(
                data=obj_data,
                question=question,
                name=name,
                value=value,
                options=option,
                created_by=self.context.get("user"),
                index=answer.get("index", 0)
            ))

        Answers.objects.bulk_create(answers)

        if direct_to_data and not obj_data.parent and not obj_data.is_pending:
            # Only save to file if the data is not pending
            # and does not have a parent
            obj_data.save_to_file

        return obj_data
