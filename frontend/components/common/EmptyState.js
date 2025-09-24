import { Button, Typography } from '@douyinfe/semi-ui';
import { IllustrationConstruction } from '@douyinfe/semi-illustrations';

function EmptyState({ title, description, actionText, onAction }) {
  return (
    <div className="empty-state">
      <IllustrationConstruction style={{ width: 120, height: 120 }} />
      <Typography.Title heading={4} style={{ marginTop: 24 }}>
        {title}
      </Typography.Title>
      <Typography.Text type="tertiary" style={{ marginTop: 8 }}>
        {description}
      </Typography.Text>
      {actionText ? (
        <Button type="primary" theme="solid" style={{ marginTop: 20 }} onClick={onAction}>
          {actionText}
        </Button>
      ) : null}
    </div>
  );
}

EmptyState.defaultProps = {
  description: '',
  actionText: '',
  onAction: () => {},
};

export default EmptyState;
