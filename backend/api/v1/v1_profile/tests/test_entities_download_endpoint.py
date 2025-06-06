import typing

# import pandas as pd
from django.test import TestCase
from django.test.utils import override_settings
from django.core.management import call_command
from django.http import HttpResponse

# from django.utils import timezone
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_profile.models import Entity, Administration


@override_settings(USE_TZ=False, TEST_ENV=True)
class EntitiesDownloadEndpointTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self) -> None:
        super().setUp()
        call_command("administration_seeder", "--test")
        self.user = self.create_user("test@akvo.org", self.IS_ADMIN)
        call_command("entities_seeder", "--test", True)
        self.token = self.get_auth_token(self.user.email)

    def test_download_entities_no_filter(self):
        response = typing.cast(
            HttpResponse,
            self.client.get(
                "/api/v1/export/entity-data",
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            ),
        )
        self.assertEqual(response.status_code, 200)

    def test_download_entities_with_selected_entity(self):
        entity = Entity.objects.first()
        response = typing.cast(
            HttpResponse,
            self.client.get(
                f"/api/v1/export/entity-data?entity_ids={entity.id}",
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            ),
        )
        self.assertEqual(response.status_code, 200)

    def test_download_entities_with_selected_entities(self):
        entities = Entity.objects.all()
        entities = ",".join([str(e["id"]) for e in entities.values("id")])
        response = typing.cast(
            HttpResponse,
            self.client.get(
                f"/api/v1/export/entity-data?entity_ids={entities}",
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            ),
        )
        self.assertEqual(response.status_code, 200)

    def test_download_entities_with_selected_administration(self):
        administration = Administration.objects.last()
        response = typing.cast(
            HttpResponse,
            self.client.get(
                f"/api/v1/export/entity-data?adm_id={administration.id}",
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            ),
        )
        self.assertEqual(response.status_code, 200)
