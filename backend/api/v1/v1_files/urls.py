from django.urls import re_path
from .views import upload_images, UploadAttachmentsView

urlpatterns = [
    re_path(r"^(?P<version>(v1))/upload/images", upload_images),
    re_path(
        r"^(?P<version>(v1))/upload/attachments",
        UploadAttachmentsView.as_view(),
        name="upload_attachments"
    )
]
