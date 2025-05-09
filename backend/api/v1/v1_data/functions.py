import re
import base64
from django.core.cache import cache
from datetime import datetime
from uuid import uuid4
from django.utils import timezone
from datetime import timedelta
from api.v1.v1_forms.constants import QuestionTypes, SubmissionTypes
from api.v1.v1_data.models import (
    FormData,
    PendingAnswers,
    Answers,
)
from api.v1.v1_profile.models import Entity, EntityData
from faker import Faker

fake = Faker()


def get_cache(name):
    name = re.sub(r"[\W_]+", "_", name)
    today = datetime.now().strftime("%Y%m%d")
    cache_name = f"{today}-{name}"
    data = cache.get(cache_name)
    if data:
        return data
    return None


def create_cache(name, resp, timeout=None):
    name = re.sub(r"[\W_]+", "_", name)
    today = datetime.now().strftime("%Y%m%d")
    cache_name = f"{today}-{name}"
    cache.add(cache_name, resp, timeout=timeout)


def set_answer_data(data, question):
    name = None
    value = None
    option = None

    if question.type == QuestionTypes.geo:
        option = data.geo
    elif question.type == QuestionTypes.administration:
        name = data.administration.name
        value = data.administration.id
    elif question.type == QuestionTypes.text:
        name = fake.company() if question.meta else fake.sentence(nb_words=3)
    elif question.type == QuestionTypes.number:
        value = fake.random_int(min=10, max=50)
    elif question.type == QuestionTypes.option:
        option = [question.options.order_by("?").first().value]
        if (
            question.default_value and "submission_type"
            in question.default_value
        ):
            st_value = SubmissionTypes.FieldStr.get(
                data.submission_type
            ).lower()
            option = [option[0].replace("submission_type", st_value)]
    elif question.type == QuestionTypes.multiple_option:
        option = list(
            question.options.order_by("?")
            .values_list("value", flat=True)[
                0: fake.random_int(min=1, max=3)
            ]
        )
    elif question.type == QuestionTypes.photo:
        name = fake.image_url()
    elif question.type == QuestionTypes.attachment:
        name = fake.file_name()
    elif question.type == QuestionTypes.signature:
        """Loads an image from the source/images directory and returns it as a
        base64 encoded string."""
        image_path = "./source/images/fake_signature.png"
        with open(image_path, 'rb') as image_file:
            image_bytes = image_file.read()
            base64_encoded = base64.b64encode(image_bytes).decode('utf-8')
            name = base64_encoded
    elif question.type == QuestionTypes.date:
        name = fake.date_between_dates(
            date_start=timezone.datetime.now().date() - timedelta(days=90),
            date_end=timezone.datetime.now().date(),
        ).strftime("%m/%d/%Y")
    elif (
        question.type == QuestionTypes.cascade
        and question.extra
        and question.extra.get("type") == "entity"
    ):
        entity, created = Entity.objects.get_or_create(
            name=question.extra.get("name")
        )
        name = None
        if entity:
            ed = (
                entity.entity_data.filter(administration=data.administration)
                .order_by("?")
                .first()
            )
            if ed:
                name = ed.name
        if not name:
            prefix = "{0}".format(
                entity.name if created else question.extra.get("name")
            )
            entity_adm = data.administration
            name = f"{prefix} {entity_adm.name}"
            EntityData.objects.get_or_create(
                entity=entity,
                name=name,
                administration=entity_adm,
            )
    else:
        pass

    if question.meta_uuid:
        name = uuid4()

    return name, value, option


def add_fake_answers(data):
    form = data.form
    meta_name = []
    for question in form.form_questions.all().order_by(
        "question_group__order", "order"
    ):
        name, value, option = set_answer_data(data, question)
        if question.meta:
            if name:
                meta_name.append(name)
            elif option and question.type != QuestionTypes.geo:
                meta_name.append(",".join(option))
            elif value and question.type != QuestionTypes.administration:
                meta_name.append(str(value))
            else:
                pass

        if question.type == QuestionTypes.administration:
            name = None

        seed = True
        if question.dependency:
            for d in question.dependency:
                if isinstance(data, FormData):
                    prev_answer = Answers.objects.filter(
                        data=data, question_id=d.get("id")
                    ).first()
                else:  # PendingFormData
                    prev_answer = PendingAnswers.objects.filter(
                        pending_data=data, question_id=d.get("id")
                    ).first()
                if prev_answer and prev_answer.options:
                    seed = False
                    for o in prev_answer.options:
                        if o in d.get("options"):
                            seed = True
        if seed:
            if isinstance(data, FormData):
                Answers.objects.create(
                    data=data,
                    question=question,
                    name=name,
                    value=value,
                    options=option,
                    created_by=data.created_by,
                )
            else:  # PendingFormData
                PendingAnswers.objects.create(
                    pending_data=data,
                    question=question,
                    name=name,
                    value=value,
                    options=option,
                    created_by=data.created_by,
                )
    data.name = " - ".join(meta_name)
    data.save()
