import React, {
  useEffect,
  useState,
  useMemo,
  useRef,
  useCallback,
} from "react";
import { Webform } from "akvo-react-form";
import "akvo-react-form/dist/index.css";
import { v4 as uuidv4 } from "uuid";
import "./style.scss";
import { useParams, useNavigate } from "react-router-dom";
import {
  Row,
  Col,
  Space,
  Progress,
  Result,
  Button,
  notification,
  Modal,
} from "antd";
import axios from "axios";
import {
  api,
  config,
  IS_ADMIN,
  QUESTION_TYPES,
  store,
  uiText,
} from "../../lib";
import { pick, isEmpty } from "lodash";
import { PageLoader, Breadcrumbs, DescriptionPanel } from "../../components";
import { useNotification } from "../../util/hooks";
import moment from "moment";

const Forms = () => {
  const navigate = useNavigate();
  const { user: authUser } = store.useState((s) => s);
  const { formId, uuid } = useParams();
  const [loading, setLoading] = useState(true);
  const [preload, setPreload] = useState(true);
  const [forms, setForms] = useState({});
  const [percentage, setPercentage] = useState(0);
  const [submit, setSubmit] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const { notify } = useNotification();
  const { language, initialValue } = store.useState((s) => s);
  const { active: activeLang } = language;
  const [hiddenQIds, setHiddenQIds] = useState([]);

  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

  const redirectToBatch = authUser.role.id === IS_ADMIN;

  const pagePath = [
    {
      title: text.controlCenter,
      link: "/control-center",
    },
    {
      title: text.manageDataTitle,
      link: "/control-center/data",
    },
    {
      title: forms.name,
    },
  ];

  const webformRef = useRef();

  const getEntityByName = async ({ id, value, apiURL }) => {
    try {
      const { data: apiData } = await axios.get(apiURL);
      const findData = apiData?.find((d) => d?.name === value);
      return { id, value: findData?.id };
    } catch {
      return null;
    }
  };

  const processFileUploads = async (questions = [], values) => {
    const files = Object.entries(values)
      .filter(([key, val]) => {
        // Parse the key to handle both standard and repeatable question formats
        // For repeatable questions, key format is "questionID-repeatIndex"
        const [baseKey] = key.split("-");
        const questionId = parseInt(baseKey, 10);

        if (isNaN(questionId)) {
          return false;
        }
        const question = questions.find((q) => q.id === questionId);
        return (
          question?.type === QUESTION_TYPES.attachment && val instanceof File
        );
      })
      .map(([key, val]) => {
        // Keep the original key format to maintain the repeatable structure
        const [baseKey] = key.split("-");
        const questionId = parseInt(baseKey, 10);
        return {
          question_id: questionId,
          file: val,
          original_key: key, // Preserve the original key for mapping back
        };
      });

    if (!files.length) {
      return values;
    }

    const uploadPromises = files.map(({ question_id, file }) => {
      const formData = new FormData();
      formData.append("file", file);
      return api.post(
        `upload/attachments?question_id=${question_id}`,
        formData
      );
    });

    const results = await Promise.allSettled(uploadPromises);

    if (results.some((result) => result.status === "rejected")) {
      notification.error({
        message: text.errorSomething,
        description: text.errorFileUpload,
      });
      setSubmit(false);
      return;
    }

    // Create a new values object with the uploaded files
    const updatedValues = { ...values };

    // Process each successfully uploaded file
    results.forEach((result, index) => {
      if (result.status === "fulfilled") {
        const data = result.value.data;
        const originalKey = files[index].original_key;
        updatedValues[originalKey] = data.file;
      }
    });

    return updatedValues;
  };

  const processEntityCascades = async (questions, values) => {
    // Find entity cascade questions
    const entityQuestions = questions.filter(
      (q) =>
        q.type === QUESTION_TYPES.cascade &&
        q.extra?.type === QUESTION_TYPES.entity &&
        typeof values[q.id] === "string"
    );

    if (!entityQuestions.length) {
      return values;
    }

    const entityPromises = entityQuestions.map((q) => {
      const parent = questions.find((subq) => subq.id === q.extra.parentId);
      const parentVal = values[parent?.id];
      const pid = Array.isArray(parentVal) ? parentVal.slice(-1)[0] : parentVal;
      return getEntityByName({
        id: q.id,
        value: values[q.id],
        apiURL: `${q.api.endpoint}${pid}`,
      });
    });

    const settledEntities = await Promise.allSettled(entityPromises);

    // Process successfully resolved entities
    const updatedValues = { ...values };
    settledEntities.forEach(({ status, value: entity }) => {
      if (status === "fulfilled" && entity?.value && values[entity.id]) {
        updatedValues[entity.id] = entity.value;
      }
    });

    return updatedValues;
  };

  const processRepeatableQuestions = (values, repeatableQuestions) => {
    // Group repeatable question values (e.g., "12345", "12345-1", "12345-2")
    const repeatableAnswers = [];
    const processedQuestionIds = new Set();

    // Extract base IDs and their variants
    const repeatableMap = {};

    // Get all valid repeatable question IDs for validation
    const validQuestionIds = new Set(repeatableQuestions.map((q) => q.id));

    // Extract and group repeatable questions by base ID
    Object.entries(values).forEach(([key, value]) => {
      // Skip non-numeric keys that don't match our pattern
      if (!/^\d+(-\d+)?$/.test(key)) {
        return;
      }

      // Parse the key to get question ID and repetition index
      const [baseId, repetitionIndex] = key.includes("-")
        ? key.split("-")
        : [key, "0"];

      const baseIdNum = parseInt(baseId, 10);

      // Skip if this is not a valid repeatable question ID
      if (!validQuestionIds.has(baseIdNum)) {
        return;
      }

      // Initialize array for this question if it doesn't exist
      if (!repeatableMap[baseId]) {
        repeatableMap[baseId] = [];
      }

      // Store the value with its repetition index for sorting later
      repeatableMap[baseId].push({
        index: parseInt(repetitionIndex || "0", 10),
        value,
      });

      // Mark this question ID as processed
      processedQuestionIds.add(baseId);
    });

    // Process each question ID and format its answers
    processedQuestionIds.forEach((baseId) => {
      const questionId = parseInt(baseId, 10);
      const question = repeatableQuestions.find((q) => q.id === questionId);

      // Skip if question not found in repeatable questions
      if (!question) {
        return;
      }

      // Sort by repetition index to maintain order
      repeatableMap[baseId]
        .sort((a, b) => a.index - b.index)
        .forEach((item) => {
          // Use our enhanced transformValue function with forApi=true
          repeatableAnswers.push(transformValue(question, item.value, true));
        });
    });

    return repeatableAnswers;
  };

  const submitFormData = async ({ datapoint, ...values }, refreshForm) => {
    // Get non-repeatable questions
    const nonRepeatableQuestions = forms.question_group
      .filter((group) => !group?.repeatable)
      .flatMap((group) => group.question);

    // Get repeatable questions
    const repeatableQuestions = forms.question_group
      .filter((group) => group?.repeatable)
      .flatMap((group) => group.question);

    // Validate required fields
    const questionIds = Object.keys(values).map((id) => parseInt(id, 10));
    const requiredQuestions = nonRepeatableQuestions.filter(
      (q) => questionIds.includes(q?.id) && q.required
    );

    const hasEmptyRequired = requiredQuestions.some((q) => {
      const questionValue = values[q.id];
      const isEmptyValue =
        questionValue === null ||
        typeof questionValue === "undefined" ||
        (typeof questionValue === "string" && questionValue.trim() === "");

      if (isEmptyValue) {
        webformRef.current.setFields([
          {
            name: q.id,
            errors: [text.requiredError.replace("{{field}}", q.label)],
          },
        ]);
        return true;
      }
      return false;
    });

    if (hasEmptyRequired) {
      setSubmit(false);
      return;
    }

    setSubmit(true);

    // Process non-repeatable File Uploads
    values = await processFileUploads(nonRepeatableQuestions, values);
    if (!values) {
      return; // Upload failed, function already showed error
    }
    // Process repeatable File Uploads
    values = await processFileUploads(repeatableQuestions, values);
    if (!values) {
      return; // Upload failed, function already showed error
    }

    // Process entity cascade questions
    values = await processEntityCascades(nonRepeatableQuestions, values);

    // Build answers array for non-repeatable questions
    const answers = Object.entries(values)
      .filter(([key, val]) => {
        // Skip keys that look like repeatable questions (contain a hyphen)
        if (key.includes("-")) {
          return false;
        }

        const questionId = parseInt(key, 10);
        const question = nonRepeatableQuestions?.find(
          (q) => q.id === questionId
        );
        if (!question) {
          return false;
        }

        if (question?.type === QUESTION_TYPES.date) {
          return typeof val !== "undefined" && moment(val).isValid();
        }

        // Skip hidden questions
        if (hiddenQIds.includes(questionId)) {
          return false;
        }

        // Skip empty non-required fields
        if (
          !question?.required &&
          (val === null ||
            typeof val === "undefined" ||
            (typeof val === "string" && val.trim() === ""))
        ) {
          return false;
        }

        return !isNaN(key);
      })
      .map(([key, val]) => {
        const questionId = parseInt(key, 10);
        const question = nonRepeatableQuestions.find(
          (q) => q.id === questionId
        );
        return transformValue(question, val, true);
      });

    // Process repeatable questions and add them to answers
    const repeatableAnswers = processRepeatableQuestions(
      values,
      repeatableQuestions
    );

    // Combine both answer sets
    const allAnswers = [...answers, ...repeatableAnswers];

    // Create datapoint name from meta fields or use default
    const names = allAnswers
      .filter(
        (x) =>
          x.meta &&
          ![QUESTION_TYPES.geo, QUESTION_TYPES.cascade].includes(x.type)
      )
      .map((x) => x.value)
      .flat()
      .join(" - ");

    const geo = allAnswers.find(
      (x) => x.type === QUESTION_TYPES.geo && x.meta
    )?.value;

    const administration = allAnswers.find(
      (x) => x.type === QUESTION_TYPES.administration
    )?.value;

    const datapointName =
      datapoint?.name ||
      (names.length
        ? names
        : `${authUser.administration.name} - ${moment().format("MMM YYYY")}`);

    const dataPayload = {
      administration: administration
        ? Array.isArray(administration)
          ? administration[administration.length - 1]
          : administration
        : authUser.administration.id,
      name: datapointName,
      geo: geo || null,
      submission_type: uuid
        ? config.submissionType.monitoring
        : config.submissionType.registration,
      ...(uuid && { uuid }),
    };

    const payload = {
      data: dataPayload,
      answer: allAnswers.map((x) => pick(x, ["question", "value"])),
    };

    if (uuid) {
      window?.localStorage?.setItem("submitted", uuid);
    }

    try {
      await api.post(`form-pending-data/${formId}`, payload);
      if (uuid) {
        store.update((s) => {
          s.initialValue = [];
        });
      }
      if (refreshForm) {
        refreshForm();
      }
      setHiddenQIds([]);
      setTimeout(() => setShowSuccess(true), 3000);
    } catch (error) {
      notification.error({ message: text.errorSomething });
    } finally {
      setTimeout(() => setSubmit(false), 2000);
    }
  };

  const onFinishFailed = ({ errorFields }) => {
    if (errorFields.length) {
      notify({
        type: "error",
        message: text.errorMandatoryFields,
      });
    }
  };

  const onChange = ({ progress }) => {
    setPercentage(progress.toFixed(0));
  };

  const getCascadeAnswerId = useCallback(
    async (id, questonAPI, value) => {
      const { initial, endpoint, query_params } = questonAPI;
      if (endpoint.includes("organisation")) {
        const res = await fetch(
          `${window.location.origin}${endpoint}${query_params}`
        );
        const apiData = await res.json();
        const findOrg = apiData?.children?.find((c) => c?.name === value);
        return { [id]: [findOrg?.id] };
      }
      if (initial) {
        const cascadeID = value || initial;
        const res = await fetch(
          `${window.location.origin}${endpoint}/${cascadeID}`
        );
        const apiData = await res.json();
        if (endpoint.includes("administration")) {
          const parents = apiData?.path
            ?.split(".")
            ?.filter((a) => a !== "")
            .slice(1);
          const userLevel = authUser?.administration?.level;
          const startLevel = userLevel ? userLevel - 1 : 0;
          const admValues = [...parents, apiData?.id]
            .map((a) => parseInt(a, 10))
            .slice(startLevel);
          return {
            [id]: admValues,
          };
        }
        return { [id]: [apiData?.id] };
      }
      const res = await fetch(window.location.origin + endpoint);
      const apiData = await res.json();
      const findCascade = apiData?.find((d) => d?.name === value);
      return {
        [id]: [findCascade?.id],
      };
    },
    [authUser?.administration?.level]
  );

  const transformValue = (question, value, forApi = false) => {
    // Type can be either a string or an object with type property
    const type = typeof question === "string" ? question : question?.type;
    let transformedValue = value;

    // Handle option type values
    if (type === QUESTION_TYPES.option) {
      if (forApi) {
        // For API submission - always return as array
        transformedValue = Array.isArray(value) ? value : [value];
      } else {
        // For UI display - extract first value from array if it exists
        transformedValue =
          Array.isArray(value) && value.length ? value[0] : value;
      }
    }

    // Handle geo type values
    if (type === QUESTION_TYPES.geo) {
      if (forApi && typeof value === "object") {
        // For API submission - convert {lat, lng} to array
        transformedValue = [value.lat, value.lng];
      }
      if (!forApi && Array.isArray(value) && value.length === 2) {
        // For UI display - convert array to {lat, lng} object
        const [lat, lng] = value;
        transformedValue = { lat, lng };
      }
    }

    // Handle cascade type values
    if (
      type === QUESTION_TYPES.cascade &&
      !forApi &&
      typeof question === "object" &&
      !question.extra &&
      Array.isArray(value)
    ) {
      // For UI display - take last cascaded value
      transformedValue = value.slice(-1)[0];
    }

    if (type === QUESTION_TYPES.cascade && forApi && Array.isArray(value)) {
      // For API submission - take last value from array
      transformedValue = value.slice(-1)[0];
    }

    // Handle date type values
    if (type === QUESTION_TYPES.date && typeof value === "string" && !forApi) {
      // For UI display - convert string to moment object
      transformedValue = moment(value);
    }

    // Default case - handle undefined values
    if (typeof transformedValue === "undefined" && !forApi) {
      transformedValue = "";
    }

    // For API submission, return an object with metadata
    if (forApi && typeof question === "object") {
      return {
        question: question.id,
        type:
          question?.source?.file === "administrator.sqlite"
            ? QUESTION_TYPES.administration
            : question.type,
        value: transformedValue,
        meta: question.meta,
      };
    }

    // For UI display or when question is just a type string, return only the transformed value
    return transformedValue;
  };

  const fetchInitialMonitoringData = useCallback(
    async (response) => {
      try {
        const { data: apiData } = response;
        const questions = apiData?.question_group?.flatMap(
          (qg) => qg?.question
        );
        const res = await fetch(
          `${window.location.origin}/datapoints/${uuid}.json`
        );
        const { answers } = await res.json();
        /**
         * Transform cascade answers
         */
        const cascadeQuestions = questions.filter(
          (q) =>
            q?.type === QUESTION_TYPES.cascade &&
            q?.extra?.type !== QUESTION_TYPES.entity &&
            q?.api?.endpoint
        );

        const cascadePromises = cascadeQuestions.map((q) =>
          getCascadeAnswerId(q.id, q.api, answers?.[q.id])
        );
        const cascadeResponses = await Promise.allSettled(cascadePromises);
        const cascadeValues = cascadeResponses
          .filter(({ status }) => status === "fulfilled")
          .map(({ value }) => value)
          .reduce((prev, curr) => {
            const [key, value] = Object.entries(curr)[0];
            prev[key] = value;
            return prev;
          }, {});
        /**
         * Transform answers to Webform format
         */
        const submissionType = uuid ? "monitoring" : "registration";
        const initialValue = Object.entries(answers)
          .filter(([key, val]) => {
            const questionId = parseInt(key, 10);
            const q = questions?.find((q) => q?.id === questionId);
            // if question required is false and value is empty then return false
            if (
              !q?.required &&
              (val === null ||
                typeof val === "undefined" ||
                (typeof val === "string" && val.trim() === ""))
            ) {
              return false;
            }
            // remove hidden question init value
            if (
              q?.hidden?.submission_type &&
              !isEmpty(q?.hidden?.submission_type) &&
              q.hidden.submission_type.includes(submissionType)
            ) {
              return false;
            }
            return true;
          })
          .map(([key, val]) => {
            const questionId = isNaN(key) ? key : parseInt(key, 10);
            const q = questions?.find((q) => q?.id === questionId);
            const value = Object.keys(cascadeValues).includes(`${q?.id}`)
              ? cascadeValues[q.id]
              : transformValue(q?.type, val);
            return {
              question: questionId,
              value,
            };
          });
        store.update((s) => {
          s.initialValue = initialValue;
        });
      } catch (error) {
        Modal.error({
          title: text.updateDataError,
          content: String(error),
        });
      }
    },
    [getCascadeAnswerId, uuid, text.updateDataError]
  );

  useEffect(() => {
    if (isEmpty(forms) && formId) {
      api.get(`/form/web/${formId}`).then((res) => {
        let defaultValues = [];
        const submissionType = uuid ? "monitoring" : "registration";
        const questionGroups = res.data.question_group.map((qg) => {
          const questions = qg.question
            .map((q) => {
              let qVal = { ...q };
              // set initial value for new_or_monitoring question
              if (
                q?.default_value &&
                q?.default_value?.submission_type?.registration &&
                !uuid
              ) {
                defaultValues = [
                  ...defaultValues,
                  {
                    question: q.id,
                    value: q.default_value.submission_type.registration,
                  },
                ];
              }
              if (!uuid && q?.meta_uuid) {
                defaultValues = [
                  ...defaultValues,
                  {
                    question: q.id,
                    value: uuidv4(),
                  },
                ];
              }
              // eol set initial value for new_or_monitoring question

              // set disabled new_or_monitoring question
              if (
                q?.default_value &&
                !isEmpty(q?.default_value?.submission_type)
              ) {
                qVal = {
                  ...qVal,
                  disabled: true,
                };
              }
              // eol set disabled new_or_monitoring question

              // support disabled question by submission type
              if (
                q?.disabled?.submission_type &&
                !isEmpty(q?.disabled?.submission_type)
              ) {
                qVal = {
                  ...qVal,
                  disabled: q.disabled.submission_type.includes(submissionType),
                };
              }
              // EOL support disabled question by submission type

              // support hidden question by submission type
              if (
                q?.hidden?.submission_type &&
                !isEmpty(q?.hidden?.submission_type)
              ) {
                const hidden =
                  q.hidden.submission_type.includes(submissionType);
                if (hidden) {
                  setHiddenQIds((prev) => [...new Set([...prev, q.id])]);
                }
                qVal = {
                  ...qVal,
                  hidden: hidden,
                };
              }
              // EOL support hidden question by submission type

              if (q?.extra) {
                delete qVal.extra;
                qVal = {
                  ...qVal,
                  ...q.extra,
                };
                if (q.extra?.allowOther) {
                  qVal = {
                    ...qVal,
                    allowOtherText: "Enter any OTHER value",
                  };
                }
                if (qVal?.type === "entity") {
                  qVal = {
                    ...qVal,
                    type: QUESTION_TYPES.cascade,
                    extra: q?.extra,
                  };
                }
              }
              return qVal;
            })
            .filter((x) => !x?.hidden); // filter out hidden questions
          return {
            ...qg,
            question: questions,
            repeatText: qg?.repeat_text,
          };
        });
        setForms({ ...res.data, question_group: questionGroups });
        // INITIAL VALUE FOR NEW DATA
        if (defaultValues.length) {
          setTimeout(() => {
            store.update((s) => {
              s.initialValue = defaultValues;
            });
          }, 1000);
        }
        // INITIAL VALUE FOR MONITORING
        if (uuid) {
          fetchInitialMonitoringData(res);
        }
        // EOL INITIAL VALUE FOR MONITORING
        setLoading(false);
      });
    }
    if (uuid && window?.localStorage?.getItem("submitted")) {
      /**
       * Redirect to the list when localStorage already has submitted item
       */
      window.localStorage.removeItem("submitted");
      navigate("/control-center/data");
    }
    if (
      typeof webformRef?.current === "undefined" &&
      uuid &&
      initialValue?.length &&
      !loading
    ) {
      setPreload(true);
      setLoading(true);
    }

    if (
      webformRef?.current &&
      typeof webformRef?.current?.getFieldsValue()?.[0] === "undefined" &&
      uuid &&
      initialValue?.length
    ) {
      setTimeout(() => {
        initialValue.forEach((v) => {
          webformRef.current.setFieldsValue({ [v?.question]: v?.value });
        });
      }, 1000);
    }
  }, [
    formId,
    uuid,
    forms,
    loading,
    initialValue,
    navigate,
    fetchInitialMonitoringData,
  ]);

  const handleOnClearForm = useCallback((preload, initialValue) => {
    if (
      preload &&
      initialValue.length === 0 &&
      typeof webformRef?.current?.resetFields === "function"
    ) {
      setPreload(false);
      webformRef.current.resetFields();
      webformRef.current;
    }
  }, []);

  useEffect(() => {
    handleOnClearForm(preload, initialValue);
  }, [handleOnClearForm, preload, initialValue]);

  useEffect(() => {
    const handleBeforeUnload = (e) => {
      e.preventDefault();
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, []);

  return (
    <div id="form">
      <div className="description-container">
        <Row justify="center" gutter={[16, 16]}>
          <Col span={24} className="webform">
            <Space>
              <Breadcrumbs
                pagePath={pagePath}
                description={text.formDescription}
              />
            </Space>
            <DescriptionPanel description={text.formDescription} />
          </Col>
        </Row>
      </div>

      <div className="table-section">
        <div className="table-wrapper">
          {loading || isEmpty(forms) ? (
            <PageLoader message={text.fetchingForm} />
          ) : (
            !showSuccess && (
              <Webform
                formRef={webformRef}
                forms={forms}
                onFinish={submitFormData}
                onCompleteFailed={onFinishFailed}
                onChange={onChange}
                submitButtonSetting={{ loading: submit }}
                languagesDropdownSetting={{
                  showLanguageDropdown: false,
                }}
                initialValue={initialValue}
              />
            )
          )}
          {(!loading || !isEmpty(forms)) && !showSuccess && (
            <Progress className="progress-bar" percent={percentage} />
          )}
          {!loading && showSuccess && (
            <Result
              status="success"
              title={text?.formSuccessTitle}
              subTitle={
                redirectToBatch
                  ? text?.formSuccessSubTitle
                  : text?.formSuccessSubTitleForAdmin
              }
              extra={[
                <Button
                  type="primary"
                  key="back-button"
                  onClick={() => {
                    if (
                      typeof webformRef?.current?.resetFields === "function"
                    ) {
                      webformRef.current.resetFields();
                    }
                    setTimeout(() => {
                      setForms({});
                      setShowSuccess(false);
                    }, 500);
                  }}
                >
                  {text.newSubmissionBtn}
                </Button>,
                !redirectToBatch ? (
                  <Button
                    key="manage-button"
                    onClick={() => navigate("/control-center/data")}
                  >
                    {text.finishSubmissionBtn}
                  </Button>
                ) : (
                  <Button
                    key="batch-button"
                    onClick={() => navigate("/control-center/data/submissions")}
                  >
                    {text.finishSubmissionBatchBtn}
                  </Button>
                ),
              ]}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default Forms;
