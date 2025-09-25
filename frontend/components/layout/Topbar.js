import { Avatar, Button, Input, Space, Typography } from '@douyinfe/semi-ui';
import { IconBell, IconCalendar, IconSearch } from '@douyinfe/semi-icons';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from '@components/common/LanguageSwitcher';

function Topbar() {
  const { t } = useTranslation();

  return (
    <div className="topbar">
      <Typography.Title heading={4} style={{ margin: 0 }}>
        {t('layout.appTitle')}
      </Typography.Title>
      <Space align="center" spacing={16}>
        <Input
          prefix={<IconSearch />}
          placeholder={t('layout.searchPlaceholder')}
          className="topbar__search"
        />
        <Button icon={<IconCalendar />} theme="borderless" />
        <Button icon={<IconBell />} theme="borderless" />
        <LanguageSwitcher />
        <Avatar color="green">Y</Avatar>
      </Space>
    </div>
  );
}

export default Topbar;
