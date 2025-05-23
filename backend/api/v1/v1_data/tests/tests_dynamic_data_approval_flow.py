import re
import random
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_mobile.tests.mixins import AssignmentTokenTestHelperMixin
from api.v1.v1_profile.models import Levels, Administration
from api.v1.v1_forms.models import FormApprovalAssignment, Forms
from api.v1.v1_forms.constants import (
    QuestionTypes, FormAccessTypes
)
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_data.models import (
    PendingFormData, PendingDataApproval, PendingDataBatch,
)
from api.v1.v1_data.constants import DataApprovalStatus
from api.v1.v1_data.tasks import seed_approved_data


@override_settings(USE_TZ=False)
class DynamicDataApprovalFlowTestCase(
    TestCase,
    ProfileTestHelperMixin,
    AssignmentTokenTestHelperMixin,
):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("fake_organisation_seeder")
        call_command("demo_approval_flow", "--test", True)

        self.form = Forms.objects.get(pk=1)
        # Get the last level
        self.last_level = Levels.objects.last()
        # Get the first level
        self.first_level = Levels.objects.first()

    def set_answers(self, form: Forms, adm: Administration):
        questions = [
            q
            for qg in form.form_question_group.all()
            for q in qg.question_group_question.all()
        ]
        answers = {}
        for question in questions:
            if question.type == QuestionTypes.option:
                answers[question.pk] = [
                    o.value
                    for o in question.options.all()[:1]
                ]
            elif question.type == QuestionTypes.multiple_option:
                answers[question.pk] = [
                    o.value
                    for o in question.options.all()[:2]
                ]
            elif question.type == QuestionTypes.number:
                answers[question.pk] = 12
            elif question.type == QuestionTypes.geo:
                answers[question.pk] = [0, 0]
            elif question.type == QuestionTypes.date:
                answers[question.pk] = "2021-01-01T00:00:00.000Z"
            elif question.type == QuestionTypes.photo:
                answers[question.pk] = "https://picsum.photos/200/300"
            elif question.type == QuestionTypes.administration:
                answers[question.pk] = adm.id
            else:
                answers[question.pk] = "testing"
        return answers

    def create_user_and_mobile_assignment(
        self,
        adm: Administration,
        passcode: str = "passcode1234",
    ):
        adm_name = re.sub("[^A-Za-z0-9]+", "", adm.name.lower())
        email = ("{0}.{1}@test.com").format(adm_name, random.randint(1, 10))
        user = self.create_user(
            email=email,
            role_level=self.IS_ADMIN,
            administration=adm,
        )
        # Assign form access to user with read access
        user_form = user.user_form.create(
            form=self.form,
        )
        user_form.user_form_access.create(
            access_type=FormAccessTypes.read,
        )
        user_form.save()

        mobile_assignment = MobileAssignment.objects.create_assignment(
            user=user,
            name="mobile.{0}.{1}".format(
                adm_name,
                random.randint(10, 20),
            ),
            passcode=passcode,
        )
        mobile_assignment.forms.add(self.form)
        mobile_assignment.administrations.add(adm)
        return user, mobile_assignment

    def test_complete_approval_flow(self):
        # Get all levels exclude first and last
        levels = Levels.objects.exclude(
            id__in=[
                self.first_level.id,
                self.last_level.id,
            ]
        ).all()
        # Get all assignments for each level
        for level in levels:
            assignments = FormApprovalAssignment.objects.filter(
                administration__level=level,
                form=self.form,
            ).all()
            # Check if the assignments are not empty
            self.assertTrue(assignments.exists())

        # Get the user from the last level administration
        adm = Administration.objects.filter(level=self.last_level).first()
        user, mobile_assignment = self.create_user_and_mobile_assignment(
            adm=adm,
            passcode="complete1234",
        )

        # Sync datapoint from mobile app
        token = self.get_assignmen_token("complete1234")
        answers = self.set_answers(
            form=self.form,
            adm=adm,
        )
        payload = {
            "formId": self.form.id,
            "name": "testing datapoint",
            "duration": 3000,
            "submittedAt": "2021-01-01T00:00:00.000Z",
            "geo": [0, 0],
            "answers": answers,
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Create a new batch
        t = RefreshToken.for_user(user)
        header = {"HTTP_AUTHORIZATION": f"Bearer {t.access_token}"}
        pending_form_data = PendingFormData.objects.filter(
            form=self.form,
            created_by=user,
            submitter=mobile_assignment.name,
        ).all()
        values = list(pending_form_data.values_list("id", flat=True))
        payload = {
            "name": "Complete Batch",
            "comment": "Test comment",
            "data": values,
        }
        response = self.client.post(
            "/api/v1/batch",
            payload,
            content_type="application/json",
            **header
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        approvers = PendingDataApproval.objects.filter(
            batch__user=user,
            batch__name="Complete Batch",
        ).all()
        # Check if the approvers are not empty
        self.assertEqual(approvers.count(), len(levels))

        # Check if the approvers are assigned to the correct level
        first_approver = FormApprovalAssignment.objects.filter(
            administration=adm.parent,
            form=self.form,
        ).first()
        self.assertEqual(
            approvers.last().user.email,
            first_approver.user.email,
        )

    def test_bypass_first_approval(self):
        levels = Levels.objects.exclude(
            id__in=[
                self.first_level.id,
                self.last_level.id,
            ]
        )
        # Get the user from the second level from the last level administration
        adm = Administration.objects.filter(
            level__level=levels.last().level - 1
        ).first()
        user, mobile_assignment = self.create_user_and_mobile_assignment(
            adm=adm,
            passcode="bypass1st",
        )

        # Sync datapoint from mobile app
        token = self.get_assignmen_token("bypass1st")
        adm_list = Administration.objects.filter(
            path__startswith=adm.path
        ).all()

        answers = self.set_answers(
            form=self.form,
            adm=adm_list.last(),
        )
        payload = {
            "formId": self.form.id,
            "name": "testing bypass first approval",
            "duration": 3000,
            "submittedAt": "2021-01-01T00:00:00.000Z",
            "geo": [0, 0],
            "answers": answers,
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Create a new batch
        t = RefreshToken.for_user(user)
        header = {"HTTP_AUTHORIZATION": f"Bearer {t.access_token}"}
        pending_form_data = PendingFormData.objects.filter(
            form=self.form,
            created_by=user,
            submitter=mobile_assignment.name,
        ).all()
        values = list(pending_form_data.values_list("id", flat=True))
        payload = {
            "name": "Bypass 1st batch",
            "comment": "Test comment",
            "data": values,
        }
        response = self.client.post(
            "/api/v1/batch",
            payload,
            content_type="application/json",
            **header
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        approvers = PendingDataApproval.objects.filter(
            batch__user=user,
            batch__name="Bypass 1st batch",
        ).all()

        # Check if the number of approvers is not equal to the number of levels
        self.assertNotEqual(approvers.count(), levels.count())
        # Check if the number of approvers is equal to the number of levels - 1
        # because the first level is bypassed
        self.assertEqual(approvers.count(), levels.count() - 1)
        # Check if the approvers are assigned to the correct level
        first_approver = FormApprovalAssignment.objects.filter(
            administration=adm,
            form=self.form,
        ).first()
        self.assertEqual(
            approvers.last().user.email,
            first_approver.user.email,
        )

    def test_bypass_middle_approval(self):
        # Get all levels exclude first and last
        levels = Levels.objects.exclude(
            id__in=[
                self.first_level.id,
                self.last_level.id,
            ]
        )
        # Delete assignment for the middle level
        middle_level = levels[1]
        FormApprovalAssignment.objects.filter(
            administration__level=middle_level,
            form=self.form,
        ).delete()

        # Check if the assignment is deleted
        assignments = FormApprovalAssignment.objects.filter(
            administration__level=middle_level,
            form=self.form,
        ).first()
        self.assertIsNone(assignments)

        # Get the user from the last level administration
        adm = Administration.objects.filter(level=self.last_level).first()
        user, mobile_assignment = self.create_user_and_mobile_assignment(
            adm=adm,
            passcode="bypass2nd",
        )

        assignments = FormApprovalAssignment.objects.filter(
            administration__pk__in=adm.ancestors.values_list("pk", flat=True),
            form=self.form,
        ).all()

        # Sync datapoint from mobile app
        token = self.get_assignmen_token("bypass2nd")
        answers = self.set_answers(
            form=self.form,
            adm=adm,
        )
        payload = {
            "formId": self.form.id,
            "name": "bypass middle approval",
            "duration": 3000,
            "submittedAt": "2021-01-01T00:00:00.000Z",
            "geo": [0, 0],
            "answers": answers,
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Create a new batch
        t = RefreshToken.for_user(user)
        header = {"HTTP_AUTHORIZATION": f"Bearer {t.access_token}"}
        pending_form_data = PendingFormData.objects.filter(
            form=self.form,
            created_by=user,
            submitter=mobile_assignment.name,
        ).all()
        values = list(pending_form_data.values_list("id", flat=True))
        payload = {
            "name": "Bypass 2nd batch",
            "comment": "Test comment",
            "data": values,
        }
        response = self.client.post(
            "/api/v1/batch",
            payload,
            content_type="application/json",
            **header
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        batch = PendingDataBatch.objects.filter(
            user=user,
            name="Bypass 2nd batch",
        ).first()

        # First approver approved
        payload = {
            "batch": batch.id,
            "status": DataApprovalStatus.approved,
            "comment": "Good Job!"
        }
        lower_approver = assignments.last().user
        la_token = RefreshToken.for_user(lower_approver)
        header = {"HTTP_AUTHORIZATION": f"Bearer {la_token.access_token}"}
        response = self.client.post(
            "/api/v1/pending-data/approve",
            payload,
            content_type="application/json",
            **header
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Final approver gets the batch
        higher_approver = assignments.first().user
        ha_token = RefreshToken.for_user(higher_approver)
        header = {"HTTP_AUTHORIZATION": f"Bearer {ha_token.access_token}"}
        response = self.client.get(
            "/api/v1/form-pending-batch",
            content_type="application/json",
            **header
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["total"],
            1,
        )
        self.assertEqual(
            response.data["batch"][0]["id"],
            batch.id,
        )

    def test_bypass_final_approval(self):
        # Get all levels exclude first and last
        levels = Levels.objects.exclude(
            id__in=[
                self.first_level.id,
                self.last_level.id,
            ]
        )
        # Delete assignment for the last level
        first_level = levels.first()
        FormApprovalAssignment.objects.filter(
            administration__level=first_level
        ).delete()
        # Check if the assignment is deleted
        assignment = FormApprovalAssignment.objects.filter(
            administration__level=first_level
        ).first()
        self.assertIsNone(assignment)

        # Get the administration from the next first level
        adm = Administration.objects.filter(
            level__level=first_level.level + 1
        ).first()
        user, mobile_assignment = self.create_user_and_mobile_assignment(
            adm=adm,
            passcode="bypass3rd",
        )
        # Sync datapoint from mobile app
        token = self.get_assignmen_token("bypass3rd")
        answers = self.set_answers(
            form=self.form,
            adm=adm,
        )
        payload = {
            "formId": self.form.id,
            "name": "bypass final approval",
            "duration": 3000,
            "submittedAt": "2021-01-01T00:00:00.000Z",
            "geo": [0, 0],
            "answers": answers,
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Create a new batch
        t = RefreshToken.for_user(user)
        header = {"HTTP_AUTHORIZATION": f"Bearer {t.access_token}"}
        pending_form_data = PendingFormData.objects.filter(
            form=self.form,
            created_by=user,
            submitter=mobile_assignment.name,
        ).all()
        values = list(pending_form_data.values_list("id", flat=True))
        payload = {
            "name": "Bypass 3rd batch",
            "comment": "Test comment",
            "data": values,
        }
        response = self.client.post(
            "/api/v1/batch",
            payload,
            content_type="application/json",
            **header
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check if the batch is created
        batch = PendingDataBatch.objects.filter(
            user=user,
            name="Bypass 3rd batch",
        ).first()
        self.assertIsNotNone(batch)

        approvers = batch.batch_approval.all()
        # Check if the batch is not approved
        self.assertFalse(batch.approved)

        # Check if the number of approvers is not equal to the number of levels
        self.assertNotEqual(approvers.count(), levels.count())
        # Check if the number of approvers is 1
        # because same level as the user's level
        self.assertEqual(approvers.count(), 1)

        # First approver approved
        payload = {
            "batch": batch.id,
            "status": DataApprovalStatus.approved,
            "comment": "Good Job!"
        }
        first_approver = FormApprovalAssignment.objects.filter(
            administration=adm,
            form=self.form,
        ).first()
        fa_token = RefreshToken.for_user(first_approver.user)
        header = {"HTTP_AUTHORIZATION": f"Bearer {fa_token.access_token}"}
        response = self.client.post(
            "/api/v1/pending-data/approve",
            payload,
            content_type="application/json",
            **header
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check if the batch is approved
        batch.refresh_from_db()
        self.assertTrue(batch.approved)

        for d in batch.batch_pending_data_batch.all():
            seed_approved_data(d)

        # Check the datapoint is available in the Routine Data
        t = RefreshToken.for_user(user)
        header = {"HTTP_AUTHORIZATION": f"Bearer {t.access_token}"}
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}",
            content_type="application/json",
            **header
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["total"],
            1,
        )

    def test_bypass_all_approvals(self):
        # Delete all assignments
        FormApprovalAssignment.objects.all().delete()
        # Check if the assignments are deleted
        assignments = FormApprovalAssignment.objects.all()
        self.assertFalse(assignments.exists())

        # Get the user from the last level administration
        adm = Administration.objects.filter(level=self.last_level).first()
        user, mobile_assignment = self.create_user_and_mobile_assignment(
            adm=adm,
            passcode="bypassall",
        )
        # Sync datapoint from mobile app
        token = self.get_assignmen_token("bypassall")
        answers = self.set_answers(
            form=self.form,
            adm=adm,
        )
        payload = {
            "formId": self.form.id,
            "name": "bypass all approvals",
            "duration": 3000,
            "submittedAt": "2021-01-01T00:00:00.000Z",
            "geo": [0, 0],
            "answers": answers,
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check if datapoint is available in the Routine Data
        t = RefreshToken.for_user(user)
        header = {"HTTP_AUTHORIZATION": f"Bearer {t.access_token}"}
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}",
            content_type="application/json",
            **header
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["total"],
            1,
        )
        self.assertEqual(
            response.data["data"][0]["name"],
            "bypass all approvals",
        )

        # Check if we keep create a new batch
        t = RefreshToken.for_user(user)
        header = {"HTTP_AUTHORIZATION": f"Bearer {t.access_token}"}
        pending_form_data = PendingFormData.objects.filter(
            form=self.form,
            created_by=user,
            submitter=mobile_assignment.name,
        ).all()
        values = list(pending_form_data.values_list("id", flat=True))
        payload = {
            "name": "Bypass all batch",
            "comment": "Test comment",
            "data": values,
        }
        response = self.client.post(
            "/api/v1/batch",
            payload,
            content_type="application/json",
            **header
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["message"],
            "No data found for this batch",
        )
