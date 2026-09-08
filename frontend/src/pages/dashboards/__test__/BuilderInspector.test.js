import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import BuilderInspector from "../BuilderInspector";
import {
  pruneConfigForForm,
  tableColumnOptions,
  monitoringForms,
  stackByOptions,
  withValidStack,
} from "../builderConstants";

// =========================================================
// Removing a criterion
// =========================================================
//
// The control was there from the start, as a bare `×` reusing the canvas
// card's button class — no accessible name, and no `flex: none`. The
// inspector gives a criterion row 274px (310px pane less its padding) to
// fit a 130px select, a flexible select, a 90px input and the button, with
// 18px of gaps. The button is the only item in that row with no text to
// establish a minimum width, so it absorbed the overflow and shrank to a
// sliver nobody could find or hit.
//
// These tests pin the behaviour; builder.scss keeps it visible.

const SOURCES = {
  forms: [
    { id: 6001, name: "Registration", type: "registration", questions: [] },
    {
      id: 6002,
      name: "Monitoring",
      type: "monitoring",
      questions: [
        { id: 600203, label: "Status", name: "status", type: "option" },
      ],
    },
  ],
};

const CRITERIA = [
  { type: "option_equals", question: 600203, value: "broken" },
  { type: "threshold_gt", question: 600203, value: "5" },
];

const tableWidget = (criteria = CRITERIA) => ({
  id: 1,
  type: "table",
  title: "Sites needing attention",
  col_span: 24,
  form: 6002,
  question: null,
  config: {
    criteria,
    columns: [{ key: "parent_name", source: "parent_name" }],
  },
});

const draw = (widget, onWidgetChange = jest.fn()) => {
  render(
    <BuilderInspector
      widget={widget}
      sources={SOURCES}
      dashboardName="Water access"
      dashboardDesc=""
      defaultFilters={{}}
      onWidgetChange={onWidgetChange}
      onDashboardChange={jest.fn()}
      errorMessage={null}
    />
  );
  return onWidgetChange;
};

describe("criteria rows can be removed", () => {
  test("every criterion offers a named remove control", () => {
    draw(tableWidget());

    expect(
      screen.getAllByRole("button", { name: /remove condition/i })
    ).toHaveLength(2);
  });

  test("removing one leaves the others untouched", () => {
    const onWidgetChange = draw(tableWidget());

    fireEvent.click(
      screen.getAllByRole("button", { name: /remove condition/i })[0]
    );

    expect(onWidgetChange).toHaveBeenCalledTimes(1);
    const next = onWidgetChange.mock.calls[0][0];
    expect(next.config.criteria).toEqual([CRITERIA[1]]);
  });

  test("removing the last one empties the list rather than dropping the key", () => {
    // VizTable keys its "add a filter condition" state off an empty array,
    // so the key has to survive the removal.
    const onWidgetChange = draw(tableWidget([CRITERIA[0]]));

    fireEvent.click(screen.getByRole("button", { name: /remove condition/i }));

    const next = onWidgetChange.mock.calls[0][0];
    expect(next.config.criteria).toEqual([]);
  });
});

// =========================================================
// Switching a widget's form must not leave stale question ids behind
// =========================================================
//
// Changing the form already clears `widget.question`, but table columns and
// criteria carry question ids of their own and were left untouched. A real
// dashboard ended up with a table on form 10001 whose column referenced
// question 102 — a question belonging to form 1 — which the backend rejects
// because a column's question must belong to the widget's form.

describe("pruneConfigForForm", () => {
  const QUESTIONS = [{ id: 600203 }, { id: 600204 }];

  test("drops columns whose question is not in the new form", () => {
    const config = {
      columns: [
        { key: "parent_name", source: "parent_name" },
        { key: "answer_600203", source: "answer", question: 600203 },
        { key: "answer_102", source: "answer", question: 102 },
      ],
    };
    expect(pruneConfigForForm(config, QUESTIONS).columns).toEqual([
      { key: "parent_name", source: "parent_name" },
      { key: "answer_600203", source: "answer", question: 600203 },
    ]);
  });

  test("drops criteria whose question is not in the new form", () => {
    const config = {
      criteria: [
        { type: "option_equals", question: 600204, value: "a" },
        { type: "option_equals", question: 102, value: "b" },
      ],
    };
    expect(pruneConfigForForm(config, QUESTIONS).criteria).toEqual([
      { type: "option_equals", question: 600204, value: "a" },
    ]);
  });

  test("keeps question-free entries, which are form-independent", () => {
    const config = {
      columns: [
        { key: "parent_name", source: "parent_name" },
        { key: "administration", source: "administration" },
      ],
      criteria: [],
    };
    expect(pruneConfigForForm(config, QUESTIONS).columns).toHaveLength(2);
  });

  test("leaves keys it does not own alone", () => {
    const config = { measure: "current_state", page_size: 50 };
    const out = pruneConfigForForm(config, QUESTIONS);
    expect(out.measure).toBe("current_state");
    expect(out.page_size).toBe(50);
  });

  test("an empty form offering drops every question-bound entry", () => {
    const config = {
      columns: [{ key: "answer_1", source: "answer", question: 1 }],
      criteria: [{ type: "option_equals", question: 1, value: "x" }],
    };
    const out = pruneConfigForForm(config, []);
    expect(out.columns).toEqual([]);
    expect(out.criteria).toEqual([]);
  });
});

// =========================================================
// Table columns span two forms, with two different sources
// =========================================================
//
// /escalation is a "registration parent plus its latest monitoring child"
// query, so a table's own form is the MONITORING side. Its columns come
// from both forms and the source differs:
//
//   registration question -> parent_answer   (read off the parent)
//   monitoring question   -> answer          (read off the latest child)
//
// The inspector wrote `answer` for every question it offered, and only
// offered the widget's own form. A dashboard bound to the registration
// form with `answer` columns therefore asked a query that returns count: 0
// no matter what — verified against seeded data.

const FORMS = [
  {
    id: 6001,
    name: "Registration",
    type: "registration",
    questions: [
      { id: 102, label: "Gender" },
      { id: 106, label: "Members" },
    ],
  },
  {
    id: 6002,
    name: "Monitoring",
    type: "monitoring",
    questions: [{ id: 10106, label: "Status" }],
  },
];

describe("tableColumnOptions", () => {
  test("registration questions are read off the parent", () => {
    const opts = tableColumnOptions(FORMS, 6002);
    const gender = opts.find((o) => o.question === 102);
    expect(gender.source).toBe("parent_answer");
  });

  test("monitoring questions are read off the latest submission", () => {
    const opts = tableColumnOptions(FORMS, 6002);
    const status = opts.find((o) => o.question === 10106);
    expect(status.source).toBe("answer");
  });

  test("both forms are offered, not just the widget's own", () => {
    const opts = tableColumnOptions(FORMS, 6002);
    // Numeric sort: the default is lexicographic, which puts 10106 second.
    expect(opts.map((o) => o.question).sort((a, b) => a - b)).toEqual([
      102, 106, 10106,
    ]);
  });

  test("keys distinguish the two sources so they cannot collide", () => {
    // A question id can only appear once, but the key has to say which
    // side of the join it came from — the response is keyed by it.
    const opts = tableColumnOptions(FORMS, 6002);
    expect(opts.find((o) => o.question === 102).key).toBe("parent_answer_102");
    expect(opts.find((o) => o.question === 10106).key).toBe("answer_10106");
  });

  test("no monitoring form selected offers the registration side only", () => {
    const opts = tableColumnOptions(FORMS, null);
    expect(opts.map((o) => o.question)).toEqual([102, 106]);
  });
});

describe("monitoringForms", () => {
  test("a table may only bind to a monitoring form", () => {
    expect(monitoringForms(FORMS).map((f) => f.id)).toEqual([6002]);
  });
});

// =========================================================
// The visibility switch
// =========================================================
//
// Unlike every other field in the settings panel, this one writes
// immediately through its own endpoint rather than joining the dirty
// state the Save button flushes. These tests pin both halves of that:
// a draft cannot be made public at all, and a flip never reaches
// onDashboardChange.

describe("visibility switch", () => {
  it("disables the visibility switch on a draft", () => {
    render(
      <BuilderInspector
        widget={null}
        sources={{ forms: [] }}
        dashboardName="Coverage"
        dashboardDesc=""
        defaultFilters={{}}
        isPublic={false}
        isPublished={false}
        onWidgetChange={jest.fn()}
        onDashboardChange={jest.fn()}
        onVisibilityChange={jest.fn()}
      />
    );
    expect(screen.getByText(/Publish this dashboard first/i)).toBeVisible();
    expect(
      screen.getByRole("switch", { name: /public dashboard/i })
    ).toBeDisabled();
  });

  it("reports a flip without touching dashboard state", () => {
    const onVisibilityChange = jest.fn();
    const onDashboardChange = jest.fn();
    render(
      <BuilderInspector
        widget={null}
        sources={{ forms: [] }}
        dashboardName="Coverage"
        dashboardDesc=""
        defaultFilters={{}}
        isPublic={false}
        isPublished={true}
        onWidgetChange={jest.fn()}
        onDashboardChange={onDashboardChange}
        onVisibilityChange={onVisibilityChange}
      />
    );
    fireEvent.click(screen.getByRole("switch", { name: /public dashboard/i }));
    expect(onVisibilityChange).toHaveBeenCalledWith(true);
    // The switch is not dirty state: it must never reach the Save payload.
    expect(onDashboardChange).not.toHaveBeenCalled();
  });
});

// =========================================================
// Stack by another question (VIZ-015)
// =========================================================
//
// One antd Select writes two config fields. The interesting parts are
// which questions it offers, and that it writes both fields in a single
// update — two `updateConfig` calls would each close over the same
// `widget`, so the second would put the first's field back.

describe("stackByOptions", () => {
  const QUESTIONS = [
    { id: 1, label: "Status", type: "option" },
    { id: 2, label: "Features", type: "multiple_option" },
    { id: 3, label: "Depth", type: "number" },
    { id: 4, label: "Inspected", type: "date" },
  ];
  const values = (...args) => stackByOptions(...args).map((c) => c.value);

  test("nothing can be stacked before a question is picked", () => {
    // stack_by is refused by the values endpoint AND the save
    // validator without a question, so offering it is offering a 400.
    expect(stackByOptions(QUESTIONS, null, "option")).toEqual([
      { value: "", label: "None" },
    ]);
  });

  test("an option question stacks by its own options under any grouping", () => {
    expect(values(QUESTIONS, 1, "month")).toEqual(["", "option"]);
    expect(values(QUESTIONS, 1, "parent_id")).toEqual(["", "option"]);
    expect(values(QUESTIONS, 1, "date")).toEqual(["", "option"]);
  });

  test("another question's options need group_by=option", () => {
    // Grouped by anything else the measured question contributes
    // nothing, and the chart is already spelled by measuring the other
    // question directly.
    expect(values(QUESTIONS, 1, "month")).not.toContain("q:2");
    expect(values(QUESTIONS, 1, "option")).toContain("q:2");
  });

  test("registration site is never offered for an option question", () => {
    // handle_option_question ignores stack_by=parent_id entirely and
    // falls through to the unstacked breakdown.
    expect(values(QUESTIONS, 1, "option")).not.toContain("parent_id");
    expect(values(QUESTIONS, 2, "month")).not.toContain("parent_id");
  });

  test("a number question stacks by site, and only over time", () => {
    // handle_stack_by_parent supports date and month; anything else
    // returns an empty chart.
    expect(values(QUESTIONS, 3, "month")).toEqual(["", "parent_id"]);
    expect(values(QUESTIONS, 3, "date")).toEqual(["", "parent_id"]);
    expect(values(QUESTIONS, 3, "parent_id")).toEqual([""]);
    expect(values(QUESTIONS, 3, "option")).toEqual([""]);
  });

  test("a date question cannot be stacked at all", () => {
    expect(values(QUESTIONS, 4, "option")).toEqual([""]);
  });

  test("number and date questions are never offered as stacks", () => {
    const labels = stackByOptions(QUESTIONS, 1, "option").map((c) => c.label);
    expect(labels).not.toContain("Depth");
    expect(labels).not.toContain("Inspected");
  });

  test("the widget's own question is left out", () => {
    // Stacking by it is already spelled "Option value", and a question
    // cross-tabbed against itself is a diagonal.
    expect(values(QUESTIONS, 1, "option")).not.toContain("q:1");
    expect(values(QUESTIONS, 1, "option")).toContain("q:2");
  });

  test("survives a form with no questions", () => {
    // Called bare, which also pins the defaults: a widget that has not
    // been given a form yet reaches this before /sources answers.
    expect(stackByOptions()).toEqual([{ value: "", label: "None" }]);
  });
});

describe("withValidStack", () => {
  const CHOICES = [
    { value: "", label: "None" },
    { value: "option", label: "Option value" },
    { value: "q:2", label: "Features" },
  ];

  test("keeps a choice the new shape still offers", () => {
    const config = { stack_by: "option", stack_question: 2 };
    expect(withValidStack(config, CHOICES)).toBe(config);
  });

  test("clears one it no longer offers", () => {
    // Regrouping away from group_by=option strands `q:2`, and a
    // stranded value is a guaranteed 400 rather than a cosmetic slip.
    const next = withValidStack(
      { stack_by: "option", stack_question: 2 },
      CHOICES.filter((c) => c.value !== "q:2")
    );
    expect(next.stack_by).toBeNull();
    expect(next.stack_question).toBeNull();
  });

  test("clears a stack the question type cannot draw", () => {
    const next = withValidStack({ stack_by: "parent_id" }, CHOICES);
    expect(next.stack_by).toBeNull();
  });
});

describe("pruneConfigForForm and the stack question", () => {
  test("drops a stack question the new form does not have", () => {
    const next = pruneConfigForForm(
      { stack_by: "option", stack_question: 600204 },
      [{ id: 600101 }]
    );
    expect(next.stack_question).toBeNull();
  });

  test("keeps one the new form does have", () => {
    const next = pruneConfigForForm(
      { stack_by: "option", stack_question: 600204 },
      [{ id: 600204 }]
    );
    expect(next.stack_question).toBe(600204);
  });
});
