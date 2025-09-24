import { Avatar, Button, Input, Space, Typography } from '@douyinfe/semi-ui';
import { IconBell, IconCalendar, IconSearch } from '@douyinfe/semi-icons';

function Topbar() {
  return (
    <div className="topbar">
      <Typography.Title heading={4} style={{ margin: 0 }}>
        AI 旅行规划
      </Typography.Title>
      <Space align="center" spacing={16}>
        <Input
          prefix={<IconSearch />}
          placeholder="搜索目的地、主题或旅行人群"
          className="topbar__search"
        />
        <Button icon={<IconCalendar />} theme="borderless" />
        <Button icon={<IconBell />} theme="borderless" />
        <Avatar color="green">Y</Avatar>
      </Space>
    </div>
  );
}

export default Topbar;
