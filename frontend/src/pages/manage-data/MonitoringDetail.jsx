import React, { useState, useEffect, useMemo } from "react";
import "./style.scss";
import {
  Row,
  Col,
  Divider,
  Table,
  Typography,
  ConfigProvider,
  Empty,
  Modal,
  Button,
  Space,
  Dropdown,
} from "antd";
import {
  LeftCircleOutlined,
  DownCircleOutlined,
  DeleteOutlined,
  ArrowLeftOutlined,
  FormOutlined,
} from "@ant-design/icons";
import { useParams, useNavigate } from "react-router-dom";
import { api, config, store, uiText } from "../../lib";
import DataDetail from "./DataDetail";
import { Breadcrumbs, DescriptionPanel } from "../../components";
import { useNotification } from "../../util/hooks";

const { Title } = Typography;

const MonitoringDetail = () => {
  const { notify } = useNotification();
  const [loading, setLoading] = useState(false);
  const [dataset, setDataset] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [updateRecord, setUpdateRecord] = useState(false);
  const [deleteData, setDeleteData] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [editedRecord, setEditedRecord] = useState({});
  const [editable, setEditable] = useState(false);
  const { form, parentId } = useParams();
  const navigate = useNavigate();

  const { language, selectedFormData, forms } = store.useState((s) => s);
  const { active: activeLang } = language;
  const childrenForms = forms.filter((f) => `${f.content?.parent}` === form);

  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

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
      title: text.monitoringDataTitle,
    },
  ];

  const { questionGroups, user: authUser } = store.useState((state) => state);

  useEffect(() => {
    const currentUser = config.roles.find(
      (role) => role.name === authUser?.role_detail?.name
    );
    setEditable(!currentUser?.delete_data);
  }, [authUser]);

  const columns = [
    {
      title: "Last Updated",
      dataIndex: "updated",
      render: (cell, row) => cell || row.created,
    },
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
    },
    {
      title: "Form",
      dataIndex: "form",
      render: (formId) => forms.find((f) => f.id === formId)?.name || "N/A",
    },
    {
      title: "User",
      dataIndex: "created_by",
    },
    Table.EXPAND_COLUMN,
  ];

  const handleChange = (e) => {
    setCurrentPage(e.current);
  };

  const handleDeleteData = () => {
    if (deleteData?.id) {
      setDeleting(true);
      api
        .delete(`data/${deleteData.id}`)
        .then(() => {
          notify({
            type: "success",
            message: `${deleteData.name} deleted`,
          });
          setDataset(dataset.filter((d) => d.id !== deleteData.id));
          setDeleteData(null);
        })
        .catch((err) => {
          notify({
            type: "error",
            message: "Could not delete datapoint",
          });
          console.error(err.response);
        })
        .finally(() => {
          setDeleting(false);
        });
    }
  };

  const goToMonitoringForm = async (form) => {
    const { uuid } = selectedFormData;
    navigate(`/control-center/form/${form}/${uuid}`);
  };

  useEffect(() => {
    if (form && !updateRecord) {
      setLoading(true);
      const url = `/form-data/${form}/?page=${currentPage}&parent=${parentId}`;
      api
        .get(url)
        .then((res) => {
          setDataset(res.data.data);
          setTotalCount(res.data.total);
          setUpdateRecord(null);
          setLoading(false);
        })
        .catch(() => {
          setDataset([]);
          setTotalCount(0);
          setLoading(false);
        });
    }
  }, [form, currentPage, updateRecord, parentId]);

  useEffect(() => {
    if (questionGroups.length === 0 && dataset.length > 0) {
      store.update((s) => {
        s.questionGroups = window.forms.find(
          (f) => f.id === dataset[0]?.form
        ).content.question_group;
        s.selectedFormData = dataset[0];
      });
    }
  }, [questionGroups, dataset]);

  return (
    <div id="manageData">
      <div className="description-container">
        <Row justify="space-between">
          <Col>
            <Breadcrumbs pagePath={pagePath} />
            <DescriptionPanel
              description={text.monitoringDataDescription}
              title={text.monitoringDataTitle}
            />
          </Col>
        </Row>
      </div>

      <div className="table-section">
        <div className="table-wrapper">
          <Row justify={"space-between"} align={"middle"}>
            <Col span={6}>
              <Button
                shape="round"
                onClick={() => navigate("/control-center/data")}
                icon={<ArrowLeftOutlined />}
              >
                {text.backManageData}
              </Button>
            </Col>
            <Col span={6} style={{ textAlign: "right" }}>
              <Dropdown
                trigger={["click"]}
                menu={{
                  items: childrenForms.map((form) => ({
                    key: form.id,
                    label: form.name,
                  })),
                  onClick: (e) => goToMonitoringForm(e.key),
                }}
              >
                <Button type="primary" shape="round" icon={<FormOutlined />}>
                  {text.updateDataButton}
                </Button>
              </Dropdown>
            </Col>
          </Row>
          <Divider />
          <Title>{selectedFormData?.name || dataset?.[0]?.name}</Title>
          <div
            style={{ padding: "16px 0 0", minHeight: "40vh" }}
            bodystyle={{ padding: 0 }}
          >
            <ConfigProvider
              renderEmpty={() => <Empty description={text.noFormText} />}
            >
              <Table
                columns={columns}
                dataSource={dataset}
                loading={loading}
                onChange={handleChange}
                pagination={{
                  current: currentPage,
                  total: totalCount,
                  pageSize: 10,
                  showSizeChanger: false,
                  showTotal: (total, range) =>
                    `Results: ${range[0]} - ${range[1]} of ${total} data`,
                }}
                rowKey="id"
                expandable={{
                  expandedRowRender: (record) => (
                    <DataDetail
                      record={record}
                      updateRecord={updateRecord}
                      updater={setUpdateRecord}
                      setDeleteData={setDeleteData}
                      setEditedRecord={setEditedRecord}
                      editedRecord={editedRecord}
                      isPublic={editable}
                    />
                  ),
                  expandIcon: ({ expanded, onExpand, record }) =>
                    expanded ? (
                      <DownCircleOutlined
                        onClick={(e) => onExpand(record, e)}
                        style={{ color: "#1651B6", fontSize: "19px" }}
                      />
                    ) : (
                      <LeftCircleOutlined
                        onClick={(e) => onExpand(record, e)}
                        style={{ color: "#1651B6", fontSize: "19px" }}
                      />
                    ),
                }}
                rowClassName={(record) => {
                  const rowEdited = editedRecord[record.id]
                    ? "row-edited"
                    : "row-normal sticky";
                  return `expandable-row ${rowEdited}`;
                }}
                expandRowByClick
              />
            </ConfigProvider>
          </div>
        </div>
      </div>
      <Modal
        open={deleteData}
        onCancel={() => setDeleteData(null)}
        centered
        width="575px"
        footer={
          <Row justify="center" align="middle">
            <Col span={14}>&nbsp;</Col>
            <Col span={10}>
              <Button
                className="light"
                disabled={deleting}
                onClick={() => {
                  setDeleteData(null);
                }}
              >
                {text.cancelButton}
              </Button>
              <Button
                type="primary"
                danger
                loading={deleting}
                onClick={handleDeleteData}
              >
                {text.deleteText}
              </Button>
            </Col>
          </Row>
        }
        bodystyle={{ textAlign: "center" }}
      >
        <Space direction="vertical">
          <DeleteOutlined style={{ fontSize: "50px" }} />
          <p>
            You are about to delete <i>{`${deleteData?.name}`}</i> data.{" "}
            <b>Delete a datapoint also will delete the history</b>. Are you sure
            want to delete this datapoint?
          </p>
        </Space>
      </Modal>
    </div>
  );
};

export default React.memo(MonitoringDetail);
