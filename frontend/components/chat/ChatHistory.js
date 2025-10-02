import { Card, Spin, Typography } from '@douyinfe/semi-ui';
import ReactMarkdown from 'react-markdown';
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
        <div className="chat-message__content chat-message__markdown">
          <ReactMarkdown>{displayContent}</ReactMarkdown>
        </div>
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
            <div className="chat-message__loading">
              <Spin size="middle" tip={null} />
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}

export default ChatHistory;
