import { Avatar, Button, Space, Typography, Dropdown, Badge, Card } from '@douyinfe/semi-ui';
import { IconBell } from '@douyinfe/semi-icons';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from '@components/common/LanguageSwitcher';
import { useAuth } from '@lib/hooks/useAuth';
import { useState } from 'react';

const announcements = [
  {
    id: 'update-dashboard',
    titleKey: 'notifications.dashboardTitle',
    descriptionKey: 'notifications.dashboardDescription',
    time: '2025-01-05',
  },
  {
    id: 'update-voice',
    titleKey: 'notifications.voiceTitle',
    descriptionKey: 'notifications.voiceDescription',
    time: '2025-01-02',
  },
  {
    id: 'update-favorites',
    titleKey: 'notifications.favoritesTitle',
    descriptionKey: 'notifications.favoritesDescription',
    time: '2024-12-30',
  },
];

function Topbar() {
  const { t, i18n } = useTranslation();
  const {
    state: { user, isAuthenticated },
    logout,
  } = useAuth();

  const displayName = user?.account || t('auth.guest');
  const avatarLabel = displayName.slice(0, 2);
  const [readAnnouncements, setReadAnnouncements] = useState([]);
  const handleAnnouncementClick = (id) => {
    setReadAnnouncements((prev) => (prev.includes(id) ? prev : [...prev, id]));
  };
  const unreadCount = announcements.length - readAnnouncements.length;
  const notificationMenu = (
    <Dropdown.Menu style={{ padding: 0 }}>
      <Dropdown.Item disabled>
        <Typography.Text strong>{t('notifications.header')}</Typography.Text>
      </Dropdown.Item>
      <Dropdown.Divider margin="8px 0" />
      <div>
        {announcements.map((item) => (
          <Dropdown.Item
            key={`${item.id}-${i18n.language}`}
            className="topbar__notification-item"
            style={{ width: '100%', padding: 0, margin: 0 }}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              handleAnnouncementClick(item.id);
            }}
          >
            <Card
              bordered={false}
              className={`topbar__notification-card ${readAnnouncements.includes(item.id)
                  ? 'topbar__notification-card--read'
                  : 'topbar__notification-card--unread'
                }`}
            >
              <Typography.Text strong>{t(item.titleKey)}</Typography.Text>
              <Typography.Paragraph type="tertiary" size="small">
                {t(item.descriptionKey)}
              </Typography.Paragraph>
              <Typography.Text type="tertiary" size="small">
                {item.time}
              </Typography.Text>
            </Card>
          </Dropdown.Item>
        ))}
      </div>
    </Dropdown.Menu>
  );

  return (
    <div className="topbar">
      <div className="topbar__branding">
        <span className="sr-only">{t('layout.appTitle')}</span>
      </div>
      <Space align="center" spacing={16}>
        <Dropdown
          trigger="hover"
          position="bottomRight"
          render={notificationMenu}
        >
          <Badge count={unreadCount || null}>
            <Button icon={<IconBell />} theme="borderless" className="topbar__bell" />
          </Badge>
        </Dropdown>
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
