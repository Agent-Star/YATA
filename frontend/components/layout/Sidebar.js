import { Avatar, Button, Typography } from '@douyinfe/semi-ui';
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
  return (
    <div className="sidebar">
      <div className="sidebar__workspace">
        <Avatar size="small" color="indigo">旅</Avatar>
        <Typography.Title heading={5} style={{ margin: 0 }}>
          YATA Travel
        </Typography.Title>
      </div>
      <div className="sidebar__actions">
        <Button theme="light" block icon={<IconApps />}>新建栏目</Button>
      </div>
      <div className="sidebar__nav">
        {groups.map((group) => (
          <div className="sidebar__section" key={group.title}>
            <Typography.Text type="tertiary" className="sidebar__section-title">
              {group.title.toUpperCase()}
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
                    {item.label}
                  </Button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <div className="sidebar__footer">
        <Typography.Text type="tertiary">Personal Workspace</Typography.Text>
      </div>
    </div>
  );
}

export default Sidebar;
