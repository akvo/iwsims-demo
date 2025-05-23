from django.test import TestCase
from api.v1.v1_profile.models import Levels
from api.v1.v1_forms.models import Forms
from api.v1.v1_data.models import FormData, PendingFormData
from api.v1.v1_users.models import SystemUser
from django.core.management import call_command
from rest_framework import status
from utils.custom_helper import CustomPasscode


class MobileAssignmentApiSyncRepeatGroupTest(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("demo_approval_flow", "--test", True)

        ward_level = Levels.objects.order_by("-level")[1:2].first()
        self.form = Forms.objects.get(pk=4)
        user = SystemUser.objects.filter(
            user_access__administration__level=ward_level,
            mobile_assignments__forms=self.form,
        ).first()
        self.mobile_user = user.mobile_assignments.first()
        self.code = CustomPasscode().decode(
            encoded_passcode=self.mobile_user.passcode
        )
        res = self.client.post(
            "/api/v1/device/auth",
            {"code": self.code},
            content_type="application/json",
        )
        data = res.json()
        self.token = data["syncToken"]

    def test_success_save_repeated_values(self):
        payload = {
            "formId": self.form.id,
            "name": "data example-4 #1",
            "duration": 1,
            "submittedAt": "2025-05-16T02:38:13.807Z",
            "submitter": self.mobile_user.name,
            "geo": [6.2088, 106.8456],
            "answers": {
                442: "John Doe",
                443: "/attachment/screenshot_likes_uuid23323.jpeg",
                444: "/attachments/my_works_uuid12333.pdf",
                445: "/attachment/application_letter_2024-04-29.pdf",
                551: "data:base64,examplesignature122323",
                661: "Good Job",
                "661-1": "2024-04-29",
                "661-2": "2024-04-29",
            },
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        form_data = FormData.objects.filter(
            form=self.form,
            name=payload["name"],
        ).first()
        self.assertIsNone(form_data)

        pending_form_data = PendingFormData.objects.filter(
            form=self.form,
            name=payload["name"],
            submitter=self.mobile_user.name,
        ).first()

        self.assertIsNotNone(pending_form_data)

        repeat_answers = pending_form_data.pending_data_answer.filter(
            question__pk=661,
        ).count()
        self.assertEqual(repeat_answers, 3)
