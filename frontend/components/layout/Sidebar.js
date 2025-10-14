import { Button, Typography } from '@douyinfe/semi-ui';
import Image from 'next/image';
import {
  IconApps,
  IconBookmark,
  IconHelpCircle,
  IconHome,
  IconImage,
  IconMapPin,
  IconSend,
  IconSetting,
} from '@douyinfe/semi-icons';
import { useTranslation } from 'react-i18next';

const iconMap = {
  IconApps,
  IconBookmark,
  IconHelpCircle,
  IconHome,
  IconImage,
  IconMapPin,
  IconSend,
  IconSetting,
};

function Sidebar({ groups, activeKey, onSelect }) {
  const { t } = useTranslation();

  return (
    <div className="sidebar">
      <div className="sidebar__workspace">
        <div className="sidebar__workspace-brand">
          <Image
            src="/logo.png"
            alt={t('layout.workspaceName')}
            width={65}
            height={65}
            priority
          />
          <Typography.Title heading={5} style={{ margin: 0 }}>
            {t('layout.workspaceName')}
          </Typography.Title>
        </div>
      </div>
      <div className="sidebar__actions">
        <Button theme="light" block icon={<IconApps />}>{t('layout.newBoard')}</Button>
      </div>
      <div className="sidebar__nav">
        {groups.map((group) => (
          <div className="sidebar__section" key={group.key}>
            <Typography.Text type="tertiary" className="sidebar__section-title">
              {t(group.titleKey)}
            </Typography.Text>
            <div className="sidebar__section-items">
              {group.items.map((item) => {
                const IconComponent = iconMap[item.icon] || IconApps;

                return (
                  <Button
                    key={item.key}
                    theme="borderless"
                    icon={<IconComponent />}
                    className={`sidebar__nav-btn ${activeKey === item.key ? 'is-active' : ''}`}
                    onClick={() => onSelect(item.key)}
                    block
                  >
                    {t(item.labelKey)}
                  </Button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <div className="sidebar__footer">
        <Typography.Text type="tertiary">{t('layout.personalWorkspace')}</Typography.Text>
      </div>
    </div>
  );
}

export default Sidebar;
