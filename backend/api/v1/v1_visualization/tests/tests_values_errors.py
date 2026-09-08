from django.test.utils import override_settings
from rest_framework.test import APITestCase
from api.v1.v1_visualization.tests.mixins import (
    VisualizationValuesTestMixin,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ValuesErrorTestCases(VisualizationValuesTestMixin, APITestCase):
    """Test error handling and input validation for /visualization/values."""

    def test_missing_form_id(self):
        """form_id is required — returns 400."""
        response = self.client.get(f"{self.BASE_URL}")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("message", data)

    def test_invalid_form_id(self):
        """Non-existent form_id — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id=99999"
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_question_id(self):
        """Non-existent question_id — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            "&question_id=99999"
        )
        self.assertEqual(response.status_code, 400)

    def test_question_not_in_form(self):
        """question_id exists but belongs to a different form — returns 400."""
        from api.v1.v1_forms.models import Questions, QuestionGroup
        from api.v1.v1_forms.constants import QuestionTypes
        other_form = self.registration
        other_qg = QuestionGroup.objects.create(
            id=79999, form=other_form, name="other_qg",
        )
        other_q = Questions.objects.create(
            id=7999,
            question_group=other_qg,
            form=other_form,
            name="other_question",
            label="Other",
            type=QuestionTypes.number,
        )
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={other_q.id}"
        )
        self.assertEqual(response.status_code, 400)

    def test_unsupported_question_type(self):
        """Text question type is not supported — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_text.id}"
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_group_by(self):
        """Invalid group_by value — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            "&group_by=invalid_value"
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_monitoring(self):
        """Invalid monitoring value — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            "&monitoring=invalid_value"
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_value_type(self):
        """Invalid value_type value — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            "&value_type=invalid_value"
        )
        self.assertEqual(response.status_code, 400)

    # ── stack_question_id (VIZ-015) ──

    def test_stack_question_requires_stack_by_option(self):
        """A stacking question with no stack_by — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            f"&group_by=option&stack_question_id={self.Q_MULTI_ID}"
        )
        self.assertEqual(response.status_code, 400)

    def test_stack_question_rejected_with_stack_by_parent(self):
        """stack_by=parent_id stacks by site, not by options.

        Ignoring the field would render a chart that is not the one the
        config describes, which is worse than refusing it.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_NUMBER_ID}"
            "&group_by=month&stack_by=parent_id"
            f"&stack_question_id={self.Q_MULTI_ID}"
        )
        self.assertEqual(response.status_code, 400)

    def test_stack_question_rejected_with_option_value(self):
        """option_value returns before stack_by is ever read."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=option&stack_by=option&option_value=active"
            f"&stack_question_id={self.Q_MULTI_ID}"
        )
        self.assertEqual(response.status_code, 400)

    def test_stack_question_must_exist_on_the_form(self):
        """A stacking question from another form — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=option&stack_by=option"
            f"&stack_question_id={self.Q_REG_OPTION_ID}"
        )
        self.assertEqual(response.status_code, 400)

    def test_stack_question_must_be_unknown_id(self):
        """A stacking question that does not exist — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=option&stack_by=option"
            "&stack_question_id=99999"
        )
        self.assertEqual(response.status_code, 400)

    def test_stack_question_must_be_an_option_question(self):
        """A number question has no option set to stack by."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=option&stack_by=option"
            f"&stack_question_id={self.Q_NUMBER_ID}"
        )
        self.assertEqual(response.status_code, 400)

    def test_stack_question_may_not_be_a_date_question(self):
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=option&stack_by=option"
            f"&stack_question_id={self.Q_DATE_ID}"
        )
        self.assertEqual(response.status_code, 400)

    def test_stack_question_requires_group_by_option(self):
        """Cross-tab or nothing.

        Grouped by anything else, every number in the chart comes from
        the stacking question and the measured one is only routing — a
        chart that says something its configuration does not.
        """
        for group_by in ("month", "date", "parent_id"):
            response = self.client.get(
                f"{self.BASE_URL}?form_id={self.monitoring.id}"
                f"&question_id={self.Q_OPTION_ID}"
                f"&group_by={group_by}&stack_by=option"
                f"&stack_question_id={self.Q_MULTI_ID}"
            )
            self.assertEqual(
                response.status_code, 400, f"group_by={group_by}"
            )

    def test_naming_the_measured_question_is_never_rejected(self):
        """It is the self-stack, not the cross-tab, so no rule applies.

        Normalised away before the cross-tab's own rules run, which is
        why it survives a grouping the cross-tab would be refused for.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&group_by=month&stack_by=option"
            f"&stack_question_id={self.Q_OPTION_ID}"
        )
        self.assertEqual(response.status_code, 200)

    # ── value_question_id (VIZ-015.b) ──

    def test_value_question_requires_an_option_question(self):
        """With a number question there are no bars to give a height."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_NUMBER_ID}"
            f"&value_question_id={self.Q_NUMBER_ID}"
            "&group_by=month"
        )
        self.assertEqual(response.status_code, 400)

    def test_value_question_must_be_a_number_question(self):
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            f"&value_question_id={self.Q_MULTI_ID}"
            "&group_by=option"
        )
        self.assertEqual(response.status_code, 400)

    def test_value_question_must_be_on_the_form(self):
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            "&value_question_id=99999&group_by=option"
        )
        self.assertEqual(response.status_code, 400)

    def test_value_question_is_refused_with_percentage(self):
        """A percent of an aggregate needs a denominator nobody has
        chosen yet, and multi-choice attribution compounds it (D-2)."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            f"&value_question_id={self.Q_NUMBER_ID}"
            "&group_by=option&value_type=percentage"
        )
        self.assertEqual(response.status_code, 400)

    def test_sum_is_refused_with_a_multi_choice_split(self):
        """The bar would total more money than exists (D-1).

        A submission selecting three options contributes its full value
        to each, which is right for an average and wrong for a sum.
        """
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            f"&stack_question_id={self.Q_MULTI_ID}"
            f"&value_question_id={self.Q_NUMBER_ID}"
            "&repeat_agg=sum&group_by=option&stack_by=option"
        )
        self.assertEqual(response.status_code, 400)

    def test_average_is_allowed_with_a_multi_choice_split(self):
        """Full attribution is correct for an average."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.Q_OPTION_ID}"
            f"&stack_question_id={self.Q_MULTI_ID}"
            f"&value_question_id={self.Q_NUMBER_ID}"
            "&repeat_agg=average&group_by=option&stack_by=option"
        )
        self.assertEqual(response.status_code, 200)
