import { useState } from 'react';
import {
  Button,
  Form,
  Modal,
  Typography,
  Toast,
  Space,
} from '@douyinfe/semi-ui';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@lib/hooks/useAuth';

const modeTitles = {
  login: 'auth.loginTitle',
  register: 'auth.registerTitle',
};

const submitLabels = {
  login: 'auth.loginButton',
  register: 'auth.registerButton',
};

function AuthPrompt() {
  const { t } = useTranslation();
  const {
    state: { isAuthenticated },
    login,
    register,
  } = useAuth();
  const [visible, setVisible] = useState(false);
  const [mode, setMode] = useState('login');
  const [formError, setFormError] = useState('');
  const [loading, setLoading] = useState(false);
  const [formApi, setFormApi] = useState(null);

  if (isAuthenticated) {
    return null;
  }

  const openModal = (nextMode) => {
    setMode(nextMode);
    setVisible(true);
    setFormError('');
    setTimeout(() => {
      formApi?.reset();
    }, 0);
  };

  const closeModal = () => {
    setVisible(false);
    setFormError('');
    setLoading(false);
    formApi?.reset();
  };

  const handleSubmit = async (values) => {
    setFormError('');
    setLoading(true);

    try {
      if (mode === 'login') {
        await login({ account: values.account, password: values.password });
        Toast.success(t('auth.loginSuccess'));
      } else {
        if (values.password !== values.confirmPassword) {
          throw new Error('PASSWORD_MISMATCH');
        }

        await register({ account: values.account, email: values.email, password: values.password });
        Toast.success(t('auth.registerSuccess'));
      }

      closeModal();
    } catch (error) {
      setLoading(false);
      const errorCode = error.code || error.message;
      switch (errorCode) {
        case 'INVALID_CREDENTIALS':
          setFormError(t('auth.errorInvalidCredentials'));
          break;
        case 'ACCOUNT_EXISTS':
          setFormError(t('auth.errorAccountExists'));
          break;
        case 'PASSWORD_MISMATCH':
          setFormError(t('auth.errorPasswordMismatch'));
          break;
        default:
          setFormError(t('auth.errorGeneric'));
      }
      return;
    }
  };

  const renderSwitchAction = () => {
    if (mode === 'login') {
      return (
        <Typography.Text type="secondary">
          {t('auth.switchToRegister')}{' '}
          <Typography.Text
            link
            onClick={() => openModal('register')}
            style={{ cursor: 'pointer' }}
          >
            {t('auth.registerButton')}
          </Typography.Text>
        </Typography.Text>
      );
    }

    return (
      <Typography.Text type="secondary">
        {t('auth.switchToLogin')}{' '}
        <Typography.Text
          link
          onClick={() => openModal('login')}
          style={{ cursor: 'pointer' }}
        >
          {t('auth.loginButton')}
        </Typography.Text>
      </Typography.Text>
    );
  };

  return (
    <div className="auth-prompt">
      <div className="auth-prompt__icons" aria-hidden>
        <span role="img" aria-label="travel heart">
          ❤️
        </span>
        <span role="img" aria-label="travel planet">
          🌍
        </span>
        <span role="img" aria-label="travel plane">
          ✈️
        </span>
      </div>
      <Typography.Title heading={3} className="auth-prompt__title">
        {t('auth.promptTitle')}
      </Typography.Title>
      <Typography.Paragraph className="auth-prompt__description">
        {t('auth.promptDescription')}
      </Typography.Paragraph>
      <Button
        theme="solid"
        type="primary"
        size="large"
        className="auth-prompt__cta"
        onClick={() => openModal('login')}
      >
        {t('auth.loginButton')}
      </Button>

      <Modal
        visible={visible}
        title={t(modeTitles[mode])}
        onCancel={closeModal}
        footer={null}
        maskClosable={false}
      >
        <Form
          layout="vertical"
          onSubmit={handleSubmit}
          getFormApi={setFormApi}
          allowEmpty
        >
          <Form.Input
            field="account"
            label={t('auth.accountLabel')}
            rules={[{ required: true, message: t('auth.accountRequired') }]}
          />
          {mode === 'register' ? (
            <Form.Input
              field="email"
              label={t('auth.emailLabel')}
              rules={[
                { required: true, message: t('auth.emailRequired') },
                { type: 'email', message: t('auth.emailInvalid') },
              ]}
            />
          ) : null}
          <Form.Input
            field="password"
            label={t('auth.passwordLabel')}
            type="password"
            rules={[{ required: true, message: t('auth.passwordRequired') }]}
          />
          {mode === 'register' ? (
            <Form.Input
              field="confirmPassword"
              label={t('auth.confirmPasswordLabel')}
              type="password"
              rules={[{ required: true, message: t('auth.confirmPasswordRequired') }]}
            />
          ) : null}

          {formError ? (
            <Typography.Text type="danger">{formError}</Typography.Text>
          ) : null}

          <Space align="center" style={{ marginTop: 16, width: '100%' }}>
            <Button
              htmlType="submit"
              theme="solid"
              type="primary"
              loading={loading}
              block
            >
              {t(submitLabels[mode])}
            </Button>
          </Space>
        </Form>

        <div className="auth-prompt__switch">{renderSwitchAction()}</div>
      </Modal>
    </div>
  );
}

export default AuthPrompt;
