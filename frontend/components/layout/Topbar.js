import { Avatar, Button, Input, Space, Typography } from '@douyinfe/semi-ui';
import { IconBell, IconCalendar, IconSearch } from '@douyinfe/semi-icons';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from '@components/common/LanguageSwitcher';
import { useAuth } from '@lib/hooks/useAuth';
import Image from 'next/image';

function Topbar() {
  const { t } = useTranslation();
  const {
    state: { user, isAuthenticated },
    logout,
  } = useAuth();

  const displayName = user?.account || t('auth.guest');
  const avatarLabel = displayName.slice(0, 2);

  return (
    <div className="topbar">
      <div className="topbar__branding">
        <span className="sr-only">{t('layout.appTitle')}</span>
      </div>
      <Space align="center" spacing={16}>
        <Button icon={<IconBell />} theme="borderless" />
        <LanguageSwitcher />
        <Space align="center" spacing={8}>
          <Avatar
            color="green"
            size="default"
            shape="circle"
            className="topbar__avatar"
            title={displayName}
          >
            {avatarLabel}
          </Avatar>
          {user?.account ? <Typography.Text strong>{displayName}</Typography.Text> : null}
          {isAuthenticated ? (
            <Button
              theme="borderless"
              type="primary"
              onClick={logout}
            >
              {t('auth.logout')}
            </Button>
          ) : null}
        </Space>
      </Space>
    </div>
  );
}

export default Topbar;
