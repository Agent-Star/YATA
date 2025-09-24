import { Typography } from '@douyinfe/semi-ui';

function ChatHeader() {
  return (
    <div className="chat-header">
      <Typography.Title heading={2}>今天想去哪里旅行？</Typography.Title>
      <Typography.Text type="tertiary">
        输入你的旅行目标、日期、预算或期待的体验，我会为你制定个性化的行程。
      </Typography.Text>
    </div>
  );
}

export default ChatHeader;
