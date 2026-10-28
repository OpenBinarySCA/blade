import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  message,
  Typography,
  Tag,
  Modal,
  Form,
  Input,
  InputNumber,
  Switch,
  Tooltip,
  Spin,
} from 'antd';
import {
  ReloadOutlined,
  EditOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import { settingsAPI } from '../services/api';
import type { SystemSetting } from '../types/api';

const { Title, Text } = Typography;

// Runtime settings configuration for display
const RUNTIME_SETTINGS_CONFIG: Record<string, {
  label: string;
  description: string;
  inputType: 'number' | 'boolean' | 'string';
  min?: number;
  max?: number;
}> = {
  auth_token_expire_hours: {
    label: 'Token Expiration (Hours)',
    description: 'JWT token expiration time in hours. Default is 168 hours (7 days).',
    inputType: 'number',
    min: 1,
    max: 8760, // 1 year
  },
  guest_analysis_limit: {
    label: 'Guest Analysis Limit',
    description: 'Maximum number of analyses allowed for guest users.',
    inputType: 'number',
    min: 0,
    max: 100,
  },
  cleanup_analysis_files: {
    label: 'Cleanup Analysis Files',
    description: 'Whether to automatically clean up temporary analysis files after completion.',
    inputType: 'boolean',
  },
  allow_direct_discovery: {
    label: 'Allow Direct Discovery',
    description: 'Allow reporting libraries not in the recalled candidate list when identity markers clearly reveal them. On = production discovery; Off = strict paper mode.',
    inputType: 'boolean',
  },
  batch_refresh_concurrency: {
    label: 'Batch Refresh Concurrency',
    description: 'Number of concurrent tasks when batch refreshing library status.',
    inputType: 'number',
    min: 1,
    max: 20,
  },
  celery_task_timeout: {
    label: 'Celery Task Timeout (Seconds)',
    description: 'Celery task timeout in seconds. Default is 6000 seconds (100 minutes).',
    inputType: 'number',
    min: 60,
    max: 36000,
  },
  redis_session_ttl: {
    label: 'Redis Session TTL (Seconds)',
    description: 'Redis session expiration time in seconds. Default is 1800 seconds (30 minutes).',
    inputType: 'number',
    min: 60,
    max: 86400,
  },
  enable_reanalyze_button: {
    label: 'Enable Reanalyze Button',
    description: 'Whether to show the Reanalyze button on the result page.',
    inputType: 'boolean',
  },
};

const SystemSettings: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [settings, setSettings] = useState<SystemSetting[]>([]);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingSetting, setEditingSetting] = useState<SystemSetting | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const data = await settingsAPI.getAllSettings();
      setSettings(data);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (setting: SystemSetting) => {
    setEditingSetting(setting);

    // Parse value based on type
    let formValue = setting.value;
    if (setting.value_type === 'bool') {
      formValue = setting.value === true || setting.value === 'true' || setting.value === '1';
    } else if (setting.value_type === 'int') {
      formValue = typeof setting.value === 'number' ? setting.value : parseInt(String(setting.value), 10);
    }

    form.setFieldsValue({
      value: formValue,
    });
    setEditModalVisible(true);
  };

  const handleSave = async () => {
    if (!editingSetting) return;

    try {
      const values = await form.validateFields();
      setSaving(true);

      // Convert value to string for API
      let stringValue: string;
      if (editingSetting.value_type === 'bool') {
        stringValue = values.value ? 'true' : 'false';
      } else {
        stringValue = String(values.value);
      }

      await settingsAPI.updateSetting(editingSetting.key, {
        value: stringValue,
      });

      message.success('Setting updated successfully');
      setEditModalVisible(false);
      loadSettings();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to update setting');
    } finally {
      setSaving(false);
    }
  };

  const handleRefreshCache = async () => {
    try {
      await settingsAPI.refreshCache();
      message.success('Cache refreshed successfully');
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || 'Failed to refresh cache');
    }
  };

  const getDisplayValue = (setting: SystemSetting) => {
    if (setting.value_type === 'bool') {
      const boolValue = setting.value === true || setting.value === 'true' || setting.value === '1';
      return boolValue ? <Tag color="green">Enabled</Tag> : <Tag color="default">Disabled</Tag>;
    }
    return <Text code>{String(setting.value)}</Text>;
  };

  const getSettingConfig = (key: string) => {
    return RUNTIME_SETTINGS_CONFIG[key] || {
      label: key,
      description: '',
      inputType: 'string' as const,
    };
  };

  const columns = [
    {
      title: 'Setting',
      dataIndex: 'key',
      key: 'key',
      render: (key: string) => {
        const config = getSettingConfig(key);
        return (
          <Space direction="vertical" size={0}>
            <Text strong>{config.label}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {key}
            </Text>
          </Space>
        );
      },
    },
    {
      title: 'Value',
      dataIndex: 'value',
      key: 'value',
      render: (_: unknown, record: SystemSetting) => getDisplayValue(record),
    },
    {
      title: 'Description',
      dataIndex: 'key',
      key: 'description',
      render: (key: string, record: SystemSetting) => {
        const config = getSettingConfig(key);
        return (
          <Text type="secondary">
            {record.description || config.description || '-'}
          </Text>
        );
      },
    },
    {
      title: 'Last Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (date: string | null) => {
        if (!date) return '-';
        return new Date(date).toLocaleString();
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_: unknown, record: SystemSetting) => (
        <Button
          type="link"
          icon={<EditOutlined />}
          onClick={() => handleEdit(record)}
        >
          Edit
        </Button>
      ),
    },
  ];

  const renderEditFormItem = () => {
    if (!editingSetting) return null;

    const config = getSettingConfig(editingSetting.key);

    if (config.inputType === 'boolean' || editingSetting.value_type === 'bool') {
      return (
        <Form.Item
          name="value"
          label="Value"
          valuePropName="checked"
        >
          <Switch checkedChildren="Enabled" unCheckedChildren="Disabled" />
        </Form.Item>
      );
    }

    if (config.inputType === 'number' || editingSetting.value_type === 'int') {
      return (
        <Form.Item
          name="value"
          label="Value"
          rules={[{ required: true, message: 'Please enter a value' }]}
        >
          <InputNumber
            style={{ width: '100%' }}
            min={config.min}
            max={config.max}
          />
        </Form.Item>
      );
    }

    return (
      <Form.Item
        name="value"
        label="Value"
        rules={[{ required: true, message: 'Please enter a value' }]}
      >
        <Input />
      </Form.Item>
    );
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>System Settings</Title>
          <Text type="secondary">
            Configure runtime settings for the application
          </Text>
        </div>
        <Space>
          <Tooltip title="Refresh settings cache">
            <Button
              icon={<ReloadOutlined />}
              onClick={handleRefreshCache}
            >
              Refresh Cache
            </Button>
          </Tooltip>
        </Space>
      </div>

      <Card>
        <div style={{ marginBottom: 16 }}>
          <Space>
            <InfoCircleOutlined style={{ color: '#1890ff' }} />
            <Text type="secondary">
              These settings can be modified at runtime without restarting the application.
              Changes take effect immediately after saving.
            </Text>
          </Space>
        </div>

        <Table
          columns={columns}
          dataSource={settings}
          rowKey="key"
          pagination={false}
          loading={loading}
        />
      </Card>

      <Modal
        title={editingSetting ? `Edit: ${getSettingConfig(editingSetting.key).label}` : 'Edit Setting'}
        open={editModalVisible}
        onOk={handleSave}
        onCancel={() => setEditModalVisible(false)}
        confirmLoading={saving}
      >
        <Form form={form} layout="vertical">
          {editingSetting && (
            <div style={{ marginBottom: 16 }}>
              <Text type="secondary">
                {editingSetting.description || getSettingConfig(editingSetting.key).description}
              </Text>
            </div>
          )}
          {renderEditFormItem()}
        </Form>
      </Modal>
    </div>
  );
};

export default SystemSettings;
