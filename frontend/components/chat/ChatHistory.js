import { Card, Skeleton, Typography } from '@douyinfe/semi-ui';
import { useTranslation } from 'react-i18next';

function ChatMessage({ message }) {
  const { t } = useTranslation();
  const { role, content, contentKey, contentParams } = message;
  const isUser = role === 'user';
  const displayContent = contentKey ? t(contentKey, contentParams) : content;

  return (
    <div className={`chat-message ${isUser ? 'chat-message--user' : 'chat-message--assistant'}`}>
      <Card className="chat-message__card" bordered={false} style={{ maxWidth: '70%' }}>
        <Typography.Text strong={isUser}>
          {isUser ? t('chat.you') : t('chat.assistant')}
        </Typography.Text>
        <Typography.Paragraph style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>
          {displayContent}
        </Typography.Paragraph>
      </Card>
    </div>
  );
}

function ChatHistory({ messages, isLoading }) {
  return (
    <div className="chat-history">
      {messages.map((message) => (
        <ChatMessage key={message.id} message={message} />
      ))}
      {isLoading ? (
        <div className="chat-message chat-message--assistant">
          <Card className="chat-message__card" bordered={false} style={{ maxWidth: '70%' }}>
            <Skeleton.Paragraph rows={3} />
          </Card>
        </div>
      ) : null}
    </div>
  );
}

export default ChatHistory;
