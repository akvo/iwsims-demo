from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormStatus, FormTypes
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_visualization.dashboard_functions import (
    SLUG_PATTERN,
    validate_dashboard_payload,
)
from api.v1.v1_visualization.models import Dashboard


@override_settings(USE_TZ=False)
class DashboardValidationTestCase(TestCase, ProfileTestHelperMixin):
    """Every VIZ-001 §4.5 rule, asserted through the validator.

    These are function-level tests on purpose: the rules are the
    product of this slice and they are far cheaper to pin down here
    than through 30 HTTP round trips. The view's job — turning the
    returned dict into a 400 — is covered once, in the CRUD tests.
    """

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_validation@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        self.root = Forms.objects.get(pk=6001)
        self.monitoring = Forms.objects.get(pk=6002)
        self.q_option = Questions.objects.get(pk=600203)
        self.q_text = Questions.objects.get(pk=600205)
        self.q_reg_option = Questions.objects.get(pk=600102)
        # multiple_option on the monitoring form: the type a cross-form
        # chart refuses as its measured question.
        self.q_multi = Questions.objects.get(pk=600204)

        # A second family, so "outside the family" has something to
        # point at that is still inside the tenant.
        self.other_root = Forms.objects.create(
            name="Other registration",
            type=FormTypes.registration,
            status=FormStatus.published,
        )
        self.other_monitoring = Forms.objects.create(
            name="Other monitoring",
            type=FormTypes.monitoring,
            parent=self.other_root,
            status=FormStatus.published,
        )

        self.dashboard = Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=self.root,
            created_by=self.user,
        )

    # ── helpers ──

    def widget(self, **overrides):
        payload = {
            "id": None,
            "order": 1,
            "type": "kpi",
            "col_span": 6,
            "title": "Operational",
            "color": "#64A73B",
            "form": self.monitoring.id,
            "question": self.q_option.id,
            "config": {"measure": "current_state"},
        }
        payload.update(overrides)
        return payload

    def check(self, *widgets, **kwargs):
        data = {
            "name": kwargs.get("name", "Water Points"),
            "widgets": list(widgets),
        }
        if "root_form" in kwargs:
            data["root_form"] = kwargs["root_form"]
        return validate_dashboard_payload(
            data, self.user, dashboard=kwargs.get(
                "dashboard", self.dashboard
            )
        )

    # ── the happy path, so every failing test below means something ──

    def test_a_valid_widget_returns_none(self):
        self.assertIsNone(self.check(self.widget()))

    # ── §4.5: config.stack_question (VIZ-015) ──

    def test_a_valid_stack_question_is_accepted(self):
        self.assertIsNone(self.check(self.widget(
            type="bar",
            config={
                "measure": "current_state",
                "group_by": "option",
                "stack_by": "option",
                "stack_question": 600204,
            },
        )))

    def test_stack_question_requires_stack_by(self):
        err = self.check(self.widget(
            type="bar",
            config={
                "measure": "current_state",
                "group_by": "option",
                "stack_question": 600204,
            },
        ))
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "config.stack_question")

    def test_stack_question_requires_stack_by_option(self):
        err = self.check(self.widget(
            type="bar",
            config={
                "measure": "current_state",
                "group_by": "option",
                "stack_by": "parent_id",
                "stack_question": 600204,
            },
        ))
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "config.stack_question")

    def test_stack_question_requires_group_by_option(self):
        # Any other grouping and the measured question contributes
        # nothing, so the saved config describes a chart it does not
        # draw.
        for group_by in ("month", "date", "parent_id"):
            err = self.check(self.widget(
                type="bar",
                config={
                    "measure": "current_state",
                    "group_by": group_by,
                    "stack_by": "option",
                    "stack_question": 600204,
                },
            ))
            self.assertIsNotNone(err, group_by)
            self.assertEqual(err["field"], "config.stack_question")

    def test_stack_question_must_belong_to_the_widgets_form(self):
        # 600102 is on the registration form; the widget is on 6002.
        err = self.check(self.widget(
            type="bar",
            config={
                "measure": "current_state",
                "group_by": "option",
                "stack_by": "option",
                "stack_question": self.q_reg_option.id,
            },
        ))
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "config.stack_question")

    def test_stack_question_must_be_an_option_question(self):
        err = self.check(self.widget(
            type="bar",
            config={
                "measure": "current_state",
                "group_by": "option",
                "stack_by": "option",
                "stack_question": self.q_text.id,
            },
        ))
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "config.stack_question")

    def test_stack_by_without_a_stack_question_still_saves(self):
        # The self-stack, which is what stack_by=option has always
        # meant. Every stored dashboard is this case.
        self.assertIsNone(self.check(self.widget(
            type="bar",
            config={
                "measure": "current_state",
                "group_by": "option",
                "stack_by": "option",
            },
        )))

    # ── §4.5: config.stack_form — cross-form stacking (VIZ-015.a) ──

    def test_a_valid_cross_form_stack_is_accepted(self):
        self.assertIsNone(self.check(self.widget(
            type="bar",
            question=self.q_option.id,
            config={
                "measure": "current_state",
                "group_by": "parent_id",
                "stack_by": "option",
                "stack_form": self.root.id,
                "stack_question": self.q_reg_option.id,
            },
        )))

    def test_cross_form_stack_form_must_exist(self):
        err = self.check(self.widget(
            type="bar",
            question=self.q_option.id,
            config={
                "measure": "current_state",
                "group_by": "parent_id",
                "stack_by": "option",
                "stack_form": 999999,
                "stack_question": self.q_reg_option.id,
            },
        ))
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "config.stack_form")

    def test_cross_form_stack_form_must_be_in_the_family(self):
        err = self.check(self.widget(
            type="bar",
            question=self.q_option.id,
            config={
                "measure": "current_state",
                "group_by": "parent_id",
                "stack_by": "option",
                "stack_form": self.other_root.id,
                "stack_question": self.q_reg_option.id,
            },
        ))
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "config.stack_form")

    def test_cross_form_requires_group_by_parent_id(self):
        # The join keys on the registration datapoint, which is only a
        # key under parent_id. Refused, never silently overridden.
        for group_by in ("option", "month", "date"):
            err = self.check(self.widget(
                type="bar",
                question=self.q_option.id,
                config={
                    "measure": "current_state",
                    "group_by": group_by,
                    "stack_by": "option",
                    "stack_form": self.root.id,
                    "stack_question": self.q_reg_option.id,
                },
            ))
            self.assertIsNotNone(err, group_by)
            self.assertEqual(err["field"], "config.stack_form")

    def test_cross_form_stack_question_must_be_on_the_stack_form(self):
        # 600203 is on the widget's own form, not on the stack form.
        err = self.check(self.widget(
            type="bar",
            question=self.q_option.id,
            config={
                "measure": "current_state",
                "group_by": "parent_id",
                "stack_by": "option",
                "stack_form": self.root.id,
                "stack_question": self.q_option.id,
            },
        ))
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "config.stack_question")

    def test_cross_form_requires_a_single_select_question(self):
        # The join takes one category answer per site, so a multi-select
        # would have everything after the first dropped without a word.
        err = self.check(self.widget(
            type="bar",
            question=self.q_multi.id,
            config={
                "measure": "current_state",
                "group_by": "parent_id",
                "stack_by": "option",
                "stack_form": self.root.id,
                "stack_question": self.q_reg_option.id,
            },
        ))
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "question")

    def test_stack_form_equal_to_the_widget_form_is_same_form(self):
        # And is therefore judged by VIZ-015's rules, which want
        # group_by=option rather than parent_id.
        err = self.check(self.widget(
            type="bar",
            question=self.q_option.id,
            config={
                "measure": "current_state",
                "group_by": "parent_id",
                "stack_by": "option",
                "stack_form": self.monitoring.id,
                "stack_question": 600204,
            },
        ))
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "config.stack_question")

    # ── §4.5: config.value_question (VIZ-015.b) ──

    def test_a_valid_value_question_is_accepted(self):
        self.assertIsNone(self.check(self.widget(
            type="bar",
            question=self.q_option.id,
            config={
                "measure": "current_state",
                "group_by": "option",
                "value_question": 600202,
                "repeat_agg": "sum",
            },
        )))

    def test_value_question_requires_an_option_question(self):
        err = self.check(self.widget(
            type="bar",
            question=600202,
            config={
                "measure": "current_state",
                "group_by": "month",
                "value_question": 600202,
            },
        ))
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "config.value_question")

    def test_value_question_must_be_a_number_question(self):
        err = self.check(self.widget(
            type="bar",
            question=self.q_option.id,
            config={
                "measure": "current_state",
                "group_by": "option",
                "value_question": self.q_multi.id,
            },
        ))
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "config.value_question")

    def test_value_question_is_refused_with_percentage(self):
        err = self.check(self.widget(
            type="bar",
            question=self.q_option.id,
            config={
                "measure": "current_state",
                "group_by": "option",
                "value_question": 600202,
                "value_type": "percentage",
            },
        ))
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "config.value_question")

    def test_value_question_is_refused_with_a_cross_form_stack(self):
        err = self.check(self.widget(
            type="bar",
            question=self.q_option.id,
            config={
                "measure": "current_state",
                "group_by": "parent_id",
                "stack_by": "option",
                "stack_form": self.root.id,
                "stack_question": self.q_reg_option.id,
                "value_question": 600202,
            },
        ))
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "config.value_question")

    def test_sum_is_refused_with_a_multi_choice_split(self):
        err = self.check(self.widget(
            type="bar",
            question=self.q_option.id,
            config={
                "measure": "current_state",
                "group_by": "option",
                "stack_by": "option",
                "stack_question": self.q_multi.id,
                "value_question": 600202,
                "repeat_agg": "sum",
            },
        ))
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "config.repeat_agg")

    # ── §4.5: root_form ──

    def test_root_form_must_be_a_registration_form(self):
        err = validate_dashboard_payload(
            {"name": "X", "root_form": self.monitoring.id, "widgets": []},
            self.user,
        )
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "root_form")
        self.assertNotIn("widget_index", err)

    def test_root_form_must_have_no_parent(self):
        child = Forms.objects.create(
            name="Registration with a parent",
            type=FormTypes.registration,
            parent=self.root,
            status=FormStatus.published,
        )
        err = validate_dashboard_payload(
            {"name": "X", "root_form": child.id, "widgets": []},
            self.user,
        )
        self.assertEqual(err["field"], "root_form")

    def test_root_form_is_immutable_after_create(self):
        err = self.check(root_form=self.other_root.id)
        self.assertIsNotNone(err)
        self.assertEqual(err["field"], "root_form")
        # Dashboard-level failures carry no index: the builder shows a
        # global message rather than highlighting a widget.
        self.assertNotIn("widget_index", err)

    def test_resending_the_same_root_form_on_update_is_fine(self):
        self.assertIsNone(self.check(root_form=self.root.id))

    # ── §4.5: the family rule, all four cases ──

    def test_widget_on_the_root_form_is_allowed(self):
        self.assertIsNone(
            self.check(
                self.widget(
                    form=self.root.id,
                    question=self.q_reg_option.id,
                    config={},
                )
            )
        )

    def test_widget_on_a_monitoring_child_is_allowed(self):
        self.assertIsNone(self.check(self.widget()))

    def test_widget_on_a_monitoring_form_of_another_parent_is_rejected(
        self,
    ):
        err = self.check(
            self.widget(form=self.other_monitoring.id, question=None)
        )
        self.assertEqual(err["widget_index"], 0)
        self.assertEqual(err["field"], "form")

    def test_widget_on_an_unrelated_registration_form_is_rejected(self):
        err = self.check(
            self.widget(form=self.other_root.id, question=None)
        )
        self.assertEqual(err["widget_index"], 0)
        self.assertEqual(err["field"], "form")

    def test_the_offending_index_is_the_widget_index_not_the_first(self):
        # The builder highlights widgets[widget_index]; an off-by-one
        # here points the user at an innocent widget.
        err = self.check(
            self.widget(),
            self.widget(),
            self.widget(form=self.other_root.id, question=None),
        )
        self.assertEqual(err["widget_index"], 2)

    # ── §4.5: question ──

    def test_question_must_belong_to_the_widget_form(self):
        err = self.check(
            self.widget(
                form=self.monitoring.id, question=self.q_reg_option.id
            )
        )
        self.assertEqual(err["widget_index"], 0)
        self.assertEqual(err["field"], "question")

    def test_question_type_must_be_aggregatable(self):
        err = self.check(self.widget(question=self.q_text.id))
        self.assertEqual(err["field"], "question")

    # ── §4.5: measure, stack_by, col_span ──

    def test_current_state_requires_a_monitoring_form(self):
        err = self.check(
            self.widget(
                form=self.root.id,
                question=self.q_reg_option.id,
                config={"measure": "current_state"},
            )
        )
        self.assertEqual(err["field"], "config.measure")

    def test_an_unknown_measure_is_rejected(self):
        err = self.check(self.widget(config={"measure": "whatever"}))
        self.assertEqual(err["field"], "config.measure")

    def test_stack_by_requires_group_by_and_question(self):
        err = self.check(
            self.widget(
                type="bar",
                config={"measure": "current_state", "stack_by": "option"},
            )
        )
        self.assertEqual(err["field"], "config.stack_by")

    def test_stack_by_with_group_by_and_question_is_allowed(self):
        self.assertIsNone(
            self.check(
                self.widget(
                    type="bar",
                    config={
                        "measure": "current_state",
                        "group_by": "option",
                        "stack_by": "option",
                    },
                )
            )
        )

    def test_col_span_out_of_range_is_rejected(self):
        for bad in (0, 25, -1):
            err = self.check(self.widget(col_span=bad))
            self.assertEqual(err["field"], "col_span", bad)

    def test_an_unknown_widget_type_is_rejected(self):
        err = self.check(self.widget(type="sparkline"))
        self.assertEqual(err["field"], "type")

    # ── config vocabularies (spec D-5) ──

    def test_group_by_outside_the_shared_vocabulary_is_rejected(self):
        # "administration" reads plausibly and is not a group_by the
        # values endpoint knows. Saving it would 400 at render time.
        err = self.check(
            self.widget(
                type="bar",
                config={
                    "measure": "current_state",
                    "group_by": "administration",
                },
            )
        )
        self.assertEqual(err["field"], "config.group_by")

    def test_value_type_and_repeat_agg_are_checked(self):
        err = self.check(self.widget(config={"value_type": "ratio"}))
        self.assertEqual(err["field"], "config.value_type")
        err = self.check(self.widget(config={"repeat_agg": "median"}))
        self.assertEqual(err["field"], "config.repeat_agg")

    def test_table_column_sources_and_criteria_types_are_checked(self):
        err = self.check(
            self.widget(
                type="table",
                question=None,
                config={"columns": [{"key": "a", "source": "magic"}]},
            )
        )
        self.assertEqual(err["field"], "config.columns")
        err = self.check(
            self.widget(
                type="table",
                question=None,
                config={
                    "criteria": [{"type": "vibes", "question": 1}],
                },
            )
        )
        self.assertEqual(err["field"], "config.criteria")

    def test_unknown_config_keys_are_left_alone(self):
        # VIZ-008 owns config expansion; this slice must not become a
        # schema language.
        self.assertIsNone(
            self.check(
                self.widget(
                    config={
                        "measure": "current_state",
                        "something_viz_008_adds": True,
                    }
                )
            )
        )

    # ── widget ids ──

    def test_a_widget_id_from_another_dashboard_is_rejected(self):
        other = Dashboard.objects.create(
            name="Other", slug="other", root_form=self.root,
        )
        stolen = other.widgets.create(
            order=1, type=1, col_span=6, config={},
        )
        err = self.check(self.widget(id=stolen.id))
        self.assertEqual(err["widget_index"], 0)
        self.assertEqual(err["field"], "id")

    def test_two_widgets_sharing_one_id_are_rejected(self):
        # Not reachable from today's builder, but VIZ-007's "duplicate
        # dashboard" is exactly the feature that would introduce it:
        # both ids are live, so nothing else here would catch it, and
        # apply_widgets would silently collapse the pair to one row.
        live = self.dashboard.widgets.create(
            order=1, type=1, col_span=6, config={}
        )
        err = self.check(
            self.widget(id=live.id), self.widget(id=live.id)
        )
        self.assertEqual(err["widget_index"], 1)
        self.assertEqual(err["field"], "id")

    # ── F1: shapes and lengths, so ordinary input 400s instead of
    # raising ──

    def test_a_non_dict_payload_is_rejected(self):
        err = validate_dashboard_payload(["not", "a", "dict"], self.user)
        self.assertIsNotNone(err)
        self.assertNotIn("widget_index", err)

    def test_a_numeric_name_is_rejected(self):
        err = self.check(self.widget(), name=12345)
        self.assertEqual(err["field"], "name")

    def test_a_300_character_name_is_rejected(self):
        err = self.check(self.widget(), name="A" * 300)
        self.assertEqual(err["field"], "name")

    def test_a_non_string_description_is_rejected(self):
        err = validate_dashboard_payload(
            {"name": "X", "description": 123, "widgets": []},
            self.user,
            dashboard=self.dashboard,
        )
        self.assertEqual(err["field"], "description")

    def test_widgets_that_is_not_a_list_is_rejected(self):
        err = validate_dashboard_payload(
            {"name": "X", "widgets": "not-a-list"},
            self.user,
            dashboard=self.dashboard,
        )
        self.assertIsNotNone(err)
        self.assertNotIn("widget_index", err)

    def test_a_non_dict_widget_is_rejected(self):
        err = self.check("not-a-widget")
        self.assertEqual(err["widget_index"], 0)

    def test_a_non_dict_config_is_rejected(self):
        err = self.check(self.widget(config=["measure"]))
        self.assertEqual(err["field"], "config")

    def test_a_title_over_255_characters_is_rejected(self):
        err = self.check(self.widget(title="A" * 256))
        self.assertEqual(err["widget_index"], 0)
        self.assertEqual(err["field"], "title")

    def test_a_color_over_32_characters_is_rejected(self):
        err = self.check(self.widget(color="A" * 33))
        self.assertEqual(err["widget_index"], 0)
        self.assertEqual(err["field"], "color")

    def test_a_null_order_is_rejected(self):
        # The column is NOT NULL; apply_widgets only defaults `order`
        # when the key is absent, not when it is explicitly null.
        err = self.check(self.widget(order=None))
        self.assertEqual(err["field"], "order")

    def test_columns_that_is_not_a_list_is_rejected(self):
        err = self.check(
            self.widget(
                type="table",
                question=None,
                config={"columns": {"a": 1}},
            )
        )
        self.assertEqual(err["field"], "config.columns")

    def test_a_criteria_entry_that_is_not_a_dict_is_rejected(self):
        err = self.check(
            self.widget(
                type="table",
                question=None,
                config={"criteria": ["not-a-dict"]},
            )
        )
        self.assertEqual(err["field"], "config.criteria")

    def test_slug_pattern_rejects_a_trailing_newline(self):
        # $ (without re.MULTILINE) matches just before a trailing "\n",
        # so the naive pattern would accept "water-points\n" and let it
        # through to storage with an embedded newline no URL can reach.
        self.assertIsNone(SLUG_PATTERN.match("water-points\n"))

    # ── F9: section_title is the one widget type with no form/question
    # ──

    def test_a_section_title_widget_with_no_form_or_question_is_valid(
        self,
    ):
        self.assertIsNone(
            self.check(
                self.widget(
                    type="section_title",
                    form=None,
                    question=None,
                    config={},
                )
            )
        )
