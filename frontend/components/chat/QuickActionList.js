import { Button, Space, Typography } from '@douyinfe/semi-ui';

function QuickActionList({ actions, onSelect }) {
  if (!actions || actions.length === 0) {
    return null;
  }

  return (
    <div className="quick-actions">
      <Typography.Text type="tertiary">快速开始</Typography.Text>
      <Space wrap spacing={12} style={{ marginTop: 12 }}>
        {actions.map((action) => (
          <Button
            key={action.key}
            theme="light"
            onClick={() => onSelect(action)}
          >
            {action.label}
          </Button>
        ))}
      </Space>
    </div>
  );
}

export default QuickActionList;
