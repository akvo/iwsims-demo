import React, { useState, useEffect, useMemo } from "react";
import "./style.scss";
import {
  Row,
  Col,
  Form,
  Button,
  Input,
  Select,
  Checkbox,
  Modal,
  Table,
  Spin,
} from "antd";
import { AdministrationDropdown } from "../../components";
import { useNavigate, useParams } from "react-router-dom";
import {
  api,
  store,
  config,
  uiText,
  IS_ADMIN,
  IS_SUPER_ADMIN,
  FORM_APPROVER_ACCESS,
} from "../../lib";
import { Breadcrumbs, DescriptionPanel } from "../../components";
import { takeRight, take } from "lodash";
import { useNotification } from "../../util/hooks";
import { FormAccessCheckbox, FormAccessCollapsible } from "./components";

const { Option } = Select;

const descriptionData = (
  <p>
    This page allows you to add users to the RUSH platform.You will only be able
    to add users for regions under your jurisdisction.
    <br />
    Once you have added the user, the user will be notified by email to set
    their password and access the platform
  </p>
);

const AddUser = () => {
  const {
    user: authUser,
    administration,
    forms: allForms,
    language,
    levels,
  } = store.useState((s) => s);
  const NATIONAL_LEVEL = levels?.find((l) => l.level === 0)?.id;
  const { active: activeLang } = language;
  const forms = allForms.map((f) => ({
    ...f,
    access: config.accessFormTypes,
  }));

  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(false);
  const [role, setRole] = useState(null);
  const [selectedLevel, setSelectedLevel] = useState(null);
  const [adminError, setAdminError] = useState(null);
  const [levelError, setLevelError] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const { notify } = useNotification();
  const { id } = useParams();
  const [organisations, setOrganisations] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [modalContent, setModalContent] = useState([]);
  const [isUserFetched, setIsUserFetched] = useState(false);

  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);
  const panelTitle = id ? text.editUser : text.addUser;

  useEffect(() => {
    if (!organisations.length) {
      // filter by 1 for member attribute
      api.get("organisations?filter=1").then((res) => {
        setOrganisations(res.data);
      });
    }
  }, [organisations]);

  const pagePath = [
    {
      title: text.controlCenter,
      link: "/control-center",
    },
    {
      title: text.manageUsers,
      link: "/control-center/users",
    },
    {
      title: id ? text.editUser : text.addUser,
    },
  ];

  const onCloseModal = () => {
    setIsModalVisible(false);
    setModalContent([]);
  };

  const allowedRoles = useMemo(() => {
    const lookUp =
      authUser?.role?.id === IS_SUPER_ADMIN ? IS_SUPER_ADMIN : IS_ADMIN;
    return config.roles.filter((r) => r.id >= lookUp);
  }, [authUser]);

  const setApproverForms = (data = []) => {
    return data
      .filter((d) => d?.checked)
      .map((d) => ({
        ...d,
        access: d.access.map((a) => ({
          ...a,
          value: a.id === FORM_APPROVER_ACCESS,
        })),
      }));
  };

  const onFinish = (values) => {
    if (selectedLevel === null && values.role === IS_ADMIN) {
      setLevelError(true);
      return;
    }
    const admLevel = administration.length;
    if (admLevel !== selectedLevel && values.role === IS_ADMIN) {
      setAdminError(
        `Please select a ${
          window.levels.find((l) => l.id === selectedLevel)?.name
        }`
      );
      return;
    }
    setSubmitting(true);
    const admin = takeRight(administration, 1)?.[0];
    const formsPayload = values?.nationalApprover
      ? setApproverForms(values?.forms)
      : values?.forms || [];
    const access_forms = formsPayload
      .map((f) =>
        f.access
          .filter((f_access) => f_access.value)
          .map((f_access) => ({
            form_id: f.id,
            access_type: f_access.id,
          }))
      )
      .flat();
    const payload = {
      first_name: values.first_name,
      last_name: values.last_name,
      email: values.email,
      administration: admin.id,
      phone_number: values.phone_number,
      role: values.role,
      inform_user: values.inform_user,
      organisation: values.organisation,
      trained: values.trained,
      access_forms: access_forms,
    };
    api[id ? "put" : "post"](id ? `user/${id}` : "user", payload)
      .then(() => {
        notify({
          type: "success",
          message: `User ${id ? "updated" : "added"}`,
        });
        setSubmitting(false);
        navigate("/control-center/users");
      })
      .catch((err) => {
        if (err?.response?.status === 403) {
          setIsModalVisible(true);
          setModalContent(err?.response?.data?.message);
        } else {
          notify({
            type: "error",
            message:
              err?.response?.data?.message ||
              `User could not be ${id ? "updated" : "added"}`,
          });
        }
        setSubmitting(false);
      });
  };

  const onRoleChange = (r) => {
    setRole(r);
    setSelectedLevel(null);
    setLevelError(false);
    setAdminError(null);
    form.setFieldsValue({
      nationalApprover: false,
      forms: allForms.map((f) => ({
        ...f,
        access: config.accessFormTypes,
      })),
    });
    if (r > 1) {
      store.update((s) => {
        s.administration = take(s.administration, 1);
      });
    }
  };

  const onLevelChange = (l) => {
    form.setFieldValue("level", l);
    setSelectedLevel(l);
    setLevelError(false);
    setAdminError(null);
    if (administration.length >= l) {
      store.update((s) => {
        s.administration.length = l;
      });
    }
  };

  const onAdminChange = () => {
    setLevelError(false);
    setAdminError(null);
  };

  useEffect(() => {
    const fetchData = async (adminId, acc, roleRes) => {
      const adm = await config.fn.administration(adminId);
      acc.unshift(adm);
      if (adm.level > 0) {
        fetchData(adm.parent, acc, roleRes);
      } else {
        store.update((s) => {
          s.administration = acc;
        });
      }
    };
    if (id && !isUserFetched) {
      setIsUserFetched(true);
      setLoading(true);
      try {
        api.get(`user/${id}`).then((res) => {
          /**
           * Get the forms that are assigned to the user
           * and map the access to the form access types
           * and set the value to true if the user has access
           * to the form.
           */
          const userForms = res.data?.forms?.map((f) => ({
            ...f,
            access: config.accessFormTypes.map((a) => ({
              ...a,
              value: f.access.some((af) => af.value === a.id),
            })),
          }));
          /**
           * Get the forms that are not in the user forms
           */
          const editForms = forms.map((f) => {
            const editForm = userForms.find((ef) => ef.id === f.id);
            if (editForm) {
              return {
                ...f,
                access: editForm.access,
              };
            }
            return f;
          });
          /**
           * Check if all forms have the approver access
           */
          const allApproverAccess = editForms
            .flatMap((f) => f.access.map((fa) => ({ ...fa, form_id: f.id })))
            .filter((a) => a.id === FORM_APPROVER_ACCESS && a.value);
          const isNationalApprover =
            allApproverAccess.length > 0 && res.data?.role === IS_SUPER_ADMIN;
          form.setFieldsValue({
            administration: res.data?.administration,
            email: res.data?.email,
            first_name: res.data?.first_name,
            last_name: res.data?.last_name,
            phone_number: res.data?.phone_number,
            role: res.data?.role,
            forms: editForms.map((f) => ({
              ...f,
              checked: allApproverAccess.some((a) => a.form_id === f.id),
            })),
            organisation: res.data?.organisation?.id || [],
            trained: res?.data?.trained,
            nationalApprover: isNationalApprover,
            inform_user: !id
              ? true
              : authUser?.email === res.data?.email
              ? false
              : true,
          });
          setRole(res.data?.role);
          setLoading(false);
          fetchData(res.data.administration, [], res.data?.role);
        });
      } catch (error) {
        notify({ type: "error", message: text.errorUserLoad });
        setLoading(false);
      }
    }
    /**
     * If the user is fetched and the administration length is greater than 1
     * and the selected level is not set then
     * set the selected level to the last administration level.
     */
    if (isUserFetched && administration?.length > 1 && selectedLevel === null) {
      // get the last administration level
      const lastAdmin = administration.slice(-1)?.[0];
      const lastAdminLevel = lastAdmin?.level + 1;
      form.setFieldValue("level", lastAdminLevel);
      setSelectedLevel(lastAdminLevel);
    }
  }, [
    id,
    form,
    forms,
    notify,
    text.errorUserLoad,
    authUser?.email,
    isUserFetched,
    selectedLevel,
    administration,
  ]);

  return (
    <div id="add-user">
      <div className="description-container">
        <Row justify="space-between">
          <Col>
            <Breadcrumbs pagePath={pagePath} />
            <DescriptionPanel
              description={descriptionData}
              title={panelTitle}
            />
          </Col>
        </Row>
      </div>
      <div className="table-section">
        <div className="table-wrapper">
          <Spin tip={text.loadingText} spinning={loading}>
            <Form
              name="adm-form"
              form={form}
              labelCol={{ span: 6 }}
              wrapperCol={{ span: 18 }}
              initialValues={{
                first_name: "",
                last_name: "",
                phone_number: "",
                email: "",
                role: null,
                inform_user: true,
                organisation: [],
                forms,
              }}
              onFinish={onFinish}
            >
              {(_, formInstance) => (
                <>
                  <div className="form-row">
                    <Form.Item
                      label={text.userFirstName}
                      name="first_name"
                      rules={[
                        {
                          required: true,
                          message: text.valFirstName,
                        },
                      ]}
                    >
                      <Input />
                    </Form.Item>
                  </div>
                  <div className="form-row">
                    <Form.Item
                      label={text.userLastName}
                      name="last_name"
                      rules={[
                        {
                          required: true,
                          message: text.valLastName,
                        },
                      ]}
                    >
                      <Input />
                    </Form.Item>
                  </div>
                  <div className="form-row">
                    <Form.Item
                      label={text.userEmail}
                      name="email"
                      rules={[
                        {
                          required: true,
                          message: text.valEmail,
                          type: "email",
                        },
                      ]}
                    >
                      <Input />
                    </Form.Item>
                  </div>
                  <div className="form-row">
                    <Form.Item
                      label={text.userPhoneNumber}
                      name="phone_number"
                      rules={[
                        {
                          required: true,
                          message: text.valPhone,
                        },
                      ]}
                    >
                      <Input />
                    </Form.Item>
                  </div>
                  <div className="form-row">
                    <Form.Item
                      name="organisation"
                      label={text.userOrganisation}
                      rules={[
                        { required: true, message: text.valOrganization },
                      ]}
                    >
                      <Select
                        getPopupContainer={(trigger) => trigger.parentNode}
                        placeholder={text.selectOne}
                        allowClear
                        showSearch
                        optionFilterProp="children"
                        filterOption={(input, option) =>
                          option.children
                            .toLowerCase()
                            .indexOf(input.toLowerCase()) >= 0
                        }
                      >
                        {organisations?.map((o, oi) => (
                          <Option key={`org-${oi}`} value={o.id}>
                            {o.name}
                          </Option>
                        ))}
                      </Select>
                    </Form.Item>
                  </div>
                  <Row className="form-row">
                    <Col span={18} offset={6}>
                      <Form.Item name="trained" valuePropName="checked">
                        <Checkbox>{text.userTrained}</Checkbox>
                      </Form.Item>
                    </Col>
                  </Row>
                  <div className="form-row">
                    <Form.Item
                      name="role"
                      label="Role"
                      rules={[{ required: true, message: text.valRole }]}
                    >
                      <Select
                        getPopupContainer={(trigger) => trigger.parentNode}
                        placeholder={text.selectOne}
                        onChange={onRoleChange}
                      >
                        {allowedRoles.map((r, ri) => (
                          <Option key={ri} value={r.id}>
                            {r.name}
                          </Option>
                        ))}
                      </Select>
                    </Form.Item>
                  </div>
                  <Row justify="center" align="middle">
                    <Col span={18} offset={6}>
                      {role && (
                        <span className="role-description">
                          {config.roles.find((r) => r.id === role)?.description}
                        </span>
                      )}
                    </Col>
                  </Row>
                  {role === IS_ADMIN && (
                    <Form.Item
                      label={text.admLevel}
                      name="level"
                      rules={[
                        {
                          required: true,
                          message: text.levelFieldRequired,
                        },
                      ]}
                    >
                      <Select
                        value={selectedLevel}
                        getPopupContainer={(trigger) => trigger.parentNode}
                        placeholder={text.selectOne}
                        onChange={onLevelChange}
                      >
                        {levels.map((l, li) => (
                          <Option key={li} value={l.id}>
                            {l.name}
                          </Option>
                        ))}
                      </Select>
                      {levelError && (
                        <div className="text-error">
                          {text.userSelectLevelRequired}
                        </div>
                      )}
                    </Form.Item>
                  )}
                  {role === IS_ADMIN &&
                    selectedLevel &&
                    selectedLevel !== NATIONAL_LEVEL && (
                      <Row className="form-row">
                        <Col span={6} className=" ant-form-item-label">
                          <label htmlFor="administration">
                            {text.administrationLabel}
                          </label>
                        </Col>
                        <Col span={18}>
                          <AdministrationDropdown
                            withLabel={true}
                            persist={true}
                            size="large"
                            width="100%"
                            onChange={onAdminChange}
                            maxLevel={selectedLevel}
                          />
                          {!!adminError && (
                            <div className="text-error">{adminError}</div>
                          )}
                        </Col>
                      </Row>
                    )}
                  {role === IS_SUPER_ADMIN && (
                    <Row justify="center" align="middle">
                      <Col span={18} offset={6}>
                        <div className="form-row">
                          <Form.Item
                            name="nationalApprover"
                            valuePropName="checked"
                          >
                            <Checkbox>{text.userNationalApprover}</Checkbox>
                          </Form.Item>
                        </div>
                      </Col>
                    </Row>
                  )}

                  {(role === IS_ADMIN ||
                    formInstance.getFieldValue("nationalApprover") ===
                      true) && (
                    <Row
                      justify="start"
                      align="stretch"
                      className="form-row"
                      style={{ marginTop: "24px" }}
                    >
                      <Col span={6} className=" ant-form-item-label">
                        <label htmlFor="forms">
                          {text.questionnairesLabel}
                        </label>
                      </Col>
                      <Col span={18}>
                        <Form.Item
                          name="forms"
                          hasFeedback
                          rules={[
                            () => ({
                              validator(_, value) {
                                const allAccess = value
                                  ?.map((a) => a?.access)
                                  ?.flat();
                                if (
                                  allAccess?.filter((a) => a?.value)?.length >
                                    0 ||
                                  value?.filter((v) => v?.checked)?.length > 0
                                ) {
                                  return Promise.resolve();
                                }
                                return Promise.reject(
                                  new Error(text.questionnairesRequired)
                                );
                              },
                            }),
                          ]}
                        >
                          {role === IS_ADMIN && (
                            <Form.List name="forms">
                              {(fields) => (
                                <FormAccessCollapsible
                                  form={form}
                                  formInstance={formInstance}
                                  fields={fields}
                                />
                              )}
                            </Form.List>
                          )}
                          {formInstance.getFieldValue("nationalApprover") && (
                            <Form.List name="forms">
                              {(fields) => (
                                <FormAccessCheckbox
                                  form={form}
                                  fields={fields}
                                />
                              )}
                            </Form.List>
                          )}
                        </Form.Item>
                      </Col>
                    </Row>
                  )}

                  <Row justify="center" align="middle">
                    <Col span={18} offset={6}>
                      <Form.Item
                        id="informUser"
                        label=""
                        valuePropName="checked"
                        name="inform_user"
                        rules={[{ required: false }]}
                      >
                        <Checkbox
                          disabled={
                            !id
                              ? true
                              : authUser?.email === form.getFieldValue("email")
                              ? true
                              : false
                          }
                        >
                          {text.informUser}
                        </Checkbox>
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row justify="center" align="middle">
                    <Col span={18} offset={6}>
                      <Button
                        type="primary"
                        htmlType="submit"
                        shape="round"
                        loading={submitting}
                      >
                        {id ? text.updateUser : text.addUser}
                      </Button>
                    </Col>
                  </Row>
                </>
              )}
            </Form>
          </Spin>
        </div>
      </div>

      {/* Notification modal */}
      <Modal
        open={isModalVisible}
        onCancel={onCloseModal}
        centered
        width="575px"
        footer={
          <Row justify="center" align="middle">
            <Col>
              <Button className="light" onClick={onCloseModal}>
                {text.cancelButton}
              </Button>
            </Col>
          </Row>
        }
        bodystyle={{ textAlign: "center" }}
      >
        <img src="/assets/user.svg" height="80" />
        <br />
        <br />
        <p>{text.existingApproverTitle}</p>
        <Table
          columns={[
            {
              title: text.formColumn,
              dataIndex: "form",
            },
            {
              title: text.administrationLabel,
              dataIndex: "administration",
            },
          ]}
          dataSource={modalContent}
          rowKey="id"
          pagination={false}
        />
        <br />
        <p>{text.existingApproverDescription}</p>
      </Modal>
    </div>
  );
};

export default AddUser;
