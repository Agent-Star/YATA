import { Card, Skeleton, Typography } from '@douyinfe/semi-ui';

function ChatMessage({ role, content }) {
  const isUser = role === 'user';

  return (
    <div className={`chat-message ${isUser ? 'chat-message--user' : 'chat-message--assistant'}`}>
      <Card className="chat-message__card" bordered={false} style={{ maxWidth: '70%' }}>
        <Typography.Text strong={isUser}>
          {isUser ? '你' : 'YATA AI'}
        </Typography.Text>
        <Typography.Paragraph style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>
          {content}
        </Typography.Paragraph>
      </Card>
    </div>
  );
}

function ChatHistory({ messages, isLoading }) {
  return (
    <div className="chat-history">
      {messages.map((message) => (
        <ChatMessage key={message.id} role={message.role} content={message.content} />
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
