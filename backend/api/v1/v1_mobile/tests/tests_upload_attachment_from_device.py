import os
from api.v1.v1_mobile.tests.mixins import AssignmentTokenTestHelperMixin
from mis.settings import STORAGE_PATH
from django.test import TestCase
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.models import Administration
from django.core.management import call_command
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_forms.models import Forms
from utils import storage


def generate_file(filename: str):
    f = open(filename, "a")
    f.write("This is a test file!")
    f.close()
    return filename


class MobileUploadAttachmentTestCase(TestCase, AssignmentTokenTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = SystemUser.objects.create_user(
            email="test@test.org",
            password="test1234",
            first_name="test",
            last_name="testing",
        )
        self.administration = Administration.objects.filter(
            parent__isnull=True
        ).first()
        self.form = Forms.objects.get(pk=4)
        self.passcode = "passcode1234"
        MobileAssignment.objects.create_assignment(
            user=self.user, name="test", passcode=self.passcode
        )
        self.mobile_assignment = MobileAssignment.objects.get(user=self.user)
        self.mobile_assignment.forms.add(self.form)
        self.administration_children = Administration.objects.filter(
            parent=self.administration
        ).all()
        self.mobile_assignment.administrations.add(
            *self.administration_children
        )
        self.image_file = generate_file(filename="test_image.jpg")
        self.document_file = generate_file(filename="test_document.pdf")

    # Delete Images after all finish
    def tearDown(self):
        os.remove(self.image_file)
        os.remove(self.document_file)

    def test_upload_image(self):
        token = self.get_assignmen_token(self.passcode)

        allowed_file_types = [
            "jpg",
            "jpeg",
            "png",
        ]
        params = "&".join(
            f"allowed_file_types={ext}" for ext in allowed_file_types
        )
        response = self.client.post(
            f"/api/v1/device/attachments/?{params}",
            {"file": open(self.image_file, "rb")},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.json()), ["message", "file"])
        uploaded_filename = response.json().get("file")
        uploaded_filename = uploaded_filename.split("/")[-1]
        self.assertTrue(
            storage.check(f"/attachments/{uploaded_filename}"),
            "File exists",
        )
        os.remove(f"{STORAGE_PATH}/attachments/{uploaded_filename}")

    def test_upload_document(self):
        token = self.get_assignmen_token(self.passcode)

        allowed_file_types = [
            "pdf",
            "docx",
            "doc",
        ]
        params = "&".join(
            f"allowed_file_types={ext}" for ext in allowed_file_types
        )
        response = self.client.post(
            f"/api/v1/device/attachments/?{params}",
            {"file": open(self.document_file, "rb")},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.json()), ["message", "file"])
        uploaded_filename = response.json().get("file")
        uploaded_filename = uploaded_filename.split("/")[-1]
        self.assertTrue(
            storage.check(f"/attachments/{uploaded_filename}"),
            "File exists",
        )
        os.remove(f"{STORAGE_PATH}/attachments/{uploaded_filename}")

    def test_file_upload_with_no_extension(self):
        token = self.get_assignmen_token(self.passcode)

        filename = generate_file(filename="test")
        allowed_file_types = [
            "pdf",
            "docx",
            "doc",
        ]
        params = "&".join(
            f"allowed_file_types={ext}" for ext in allowed_file_types
        )
        response = self.client.post(
            f"/api/v1/device/attachments/?{params}",
            {"file": open(filename, "rb")},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            "File extension “” is not allowed. Allowed extensions are: pdf, docx, doc.",  # noqa
        )
        os.remove(filename)

    def test_file_upload_with_no_file(self):
        token = self.get_assignmen_token(self.passcode)

        allowed_file_types = [
            "pdf",
            "docx",
            "doc",
        ]
        params = "&".join(
            f"allowed_file_types={ext}" for ext in allowed_file_types
        )
        response = self.client.post(
            f"/api/v1/device/attachments/?{params}",
            {},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            "No file was submitted in file.",
        )

    def test_file_upload_with_invalid_file_type(self):
        token = self.get_assignmen_token(self.passcode)

        filename = generate_file(filename="test.txt")
        allowed_file_types = [
            "pdf",
            "docx",
            "doc",
        ]
        params = "&".join(
            f"allowed_file_types={ext}" for ext in allowed_file_types
        )
        response = self.client.post(
            f"/api/v1/device/attachments/?{params}",
            {"file": open(filename, "rb")},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            "File extension “txt” is not allowed. Allowed extensions are: pdf, docx, doc.",  # noqa
        )
        os.remove(filename)

    def test_file_upload_with_no_allowed_file_types(self):
        token = self.get_assignmen_token(self.passcode)

        params = "&".join(
            f"allowed_file_types={ext}" for ext in []
        )
        response = self.client.post(
            f"/api/v1/device/attachments/?{params}",
            {"file": open(self.document_file, "rb")},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.json()), ["message", "file"])
        uploaded_filename = response.json().get("file")
        uploaded_filename = uploaded_filename.split("/")[-1]
        self.assertTrue(
            storage.check(f"/attachments/{uploaded_filename}"),
            "File exists",
        )
        os.remove(f"{STORAGE_PATH}/attachments/{uploaded_filename}")

    def test_upload_file_without_credentials(self):
        response = self.client.post(
            "/api/v1/device/attachments",
            {"file": open(self.image_file, "rb")},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json().get("detail"),
            "Authentication credentials were not provided.",
        )
