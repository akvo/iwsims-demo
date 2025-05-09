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

  const onFinish = async ({ datapoint, ...values }, refreshForm) => {
    const qs = forms.question_group.flatMap((group) => group.question);
    // get all questions ids from values
    const questionIds = Object.keys(values).map((id) => parseInt(id, 10));
    const requiredQuestions = qs
      .filter((q) => questionIds.includes(q?.id))
      .filter((q) => q.required);
    const hasEmptyRequired = requiredQuestions.some((q) => {
      const questionId = q.id;
      const questionValue = values[questionId];
      const isEmptyValue =
        questionValue === null ||
        typeof questionValue === "undefined" ||
        (typeof questionValue === "string" && questionValue.trim() === "");
      if (isEmptyValue) {
        webformRef.current.setFields([
          {
            name: questionId,
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
    // Get all Files objects to upload from values
    const files = Object.entries(values)
      .map(([key, val]) => {
        const questionId = parseInt(key, 10);
        if (isNaN(questionId)) {
          return null;
        }
        const question = forms.question_group
          .flatMap((group) => group.question)
          .find((q) => q.id === questionId);
        return question?.type === QUESTION_TYPES.attachment &&
          val instanceof File
          ? { question_id: questionId, file: val }
          : null;
      })
      .filter(Boolean);

    if (files.length) {
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

      const uploadedFiles = results
        .filter((result) => result.status === "fulfilled")
        .map((result) => result.value.data);

      values = {
        ...values,
        ...uploadedFiles.reduce((acc, data) => {
          acc[data.question_id] = data.file;
          return acc;
        }, {}),
      };
    }
    setSubmit(true);

    const questions = forms.question_group.flatMap((group) => group.question);

    // Process entity cascade questions
    // Step 1: Filter out cascade questions of type entity where the value is a string
    const entityQuestions = questions.filter(
      (q) =>
        q.type === QUESTION_TYPES.cascade &&
        q.extra?.type === QUESTION_TYPES.entity &&
        typeof values[q.id] === "string"
    );

    if (entityQuestions.length) {
      // Step 2: Map each filtered question to a promise to retrieve the entity ID
      const entityPromises = entityQuestions.map((q) => {
        const parent = questions.find((subq) => subq.id === q.extra.parentId);
        const parentVal = values[parent?.id];
        const pid = Array.isArray(parentVal)
          ? parentVal.slice(-1)[0]
          : parentVal;
        return getEntityByName({
          id: q.id,
          value: values[q.id],
          apiURL: `${q.api.endpoint}${pid}`,
        });
      });
      // Wait for all promises to settle and update the form values accordingly
      const settledEntities = await Promise.allSettled(entityPromises);
      // Step 3: Update the values object with the resolved entity IDs
      settledEntities.forEach(({ value: entity }) => {
        if (entity?.value && values[entity.id]) {
          values[entity.id] = entity.value;
        }
      });
    }
    // EOL Process entity cascade questions

    // Build answers array
    const answers = Object.entries(values)
      .filter(([key, val]) => {
        const questionId = parseInt(key, 10);
        const question = questions?.find((q) => q.id === questionId);
        if (question?.type === QUESTION_TYPES.date) {
          return typeof val !== "undefined" && moment(val).isValid();
        }
        // Check hidden questions
        if (hiddenQIds.includes(questionId)) {
          return false;
        }
        // Check if the question is not required and the value is empty
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
        const qid = parseInt(key, 10);
        const question = questions.find((q) => q.id === qid);
        let answerValue = val;
        if (question.type === QUESTION_TYPES.option) {
          answerValue = [val];
        } else if (question.type === QUESTION_TYPES.geo) {
          answerValue = [val.lat, val.lng];
        } else if (
          question.type === QUESTION_TYPES.cascade &&
          !question.extra
        ) {
          answerValue = Array.isArray(val) ? val.slice(-1)[0] : val;
        }
        return {
          question: qid,
          type:
            question?.source?.file === "administrator.sqlite"
              ? QUESTION_TYPES.administration
              : question.type,
          value: answerValue,
          meta: question.meta,
        };
      });

    const names = answers
      .filter(
        (x) =>
          x.meta &&
          ![QUESTION_TYPES.geo, QUESTION_TYPES.cascade].includes(x.type)
      )
      .map((x) => x.value)
      .flat()
      .join(" - ");
    const geo = answers.find(
      (x) => x.type === QUESTION_TYPES.geo && x.meta
    )?.value;
    const administration = answers.find(
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

    const data = {
      data: dataPayload,
      answer: answers.map((x) => pick(x, ["question", "value"])),
    };

    if (uuid) {
      window?.localStorage?.setItem("submitted", uuid);
    }

    try {
      await api.post(`form-pending-data/${formId}`, data);
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

  const transformValue = (type, value) => {
    if (
      type === QUESTION_TYPES.option &&
      Array.isArray(value) &&
      value.length
    ) {
      return value[0];
    }
    if (type === "geo" && Array.isArray(value) && value.length === 2) {
      const [lat, lng] = value;
      return { lat, lng };
    }
    return typeof value === "undefined" ? "" : value;
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
        const initialValue = questions
          .map((q) => {
            let value = Object.keys(cascadeValues).includes(`${q?.id}`)
              ? cascadeValues[q.id]
              : transformValue(q?.type, answers?.[q.id]);
            // if question required is false and value is empty then return false
            if (
              !q?.required &&
              (value === null ||
                typeof value === "undefined" ||
                (typeof value === "string" && value.trim() === ""))
            ) {
              return false;
            }

            // set default answer by default_value for new_or_monitoring question
            if (
              q?.default_value &&
              q?.default_value?.submission_type?.monitoring
            ) {
              value = q.default_value.submission_type.monitoring;
            }
            // EOL set default answer by default_value for new_or_monitoring question

            // remove hidden question init value
            if (
              q?.hidden?.submission_type &&
              !isEmpty(q?.hidden?.submission_type) &&
              q.hidden.submission_type.includes(submissionType)
            ) {
              return false;
            }
            // EOL remove hidden question init value

            // convert date string to date object for date question
            if (q?.type === "date" && typeof value === "string") {
              value = moment(value);
            }
            // EOL convert date string to date object for date question
            return {
              question: q?.id,
              value: value,
            };
          })
          .filter((x) => x);
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
                onFinish={onFinish}
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
