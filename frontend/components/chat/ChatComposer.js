import { Button, TextArea } from '@douyinfe/semi-ui';

function ChatComposer({ value, onChange, onSend, isLoading }) {
  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      onSend();
    }
  };

  return (
    <div className="chat-composer">
      <TextArea
        value={value}
        onChange={onChange}
        onKeyDown={handleKeyDown}
        autosize
        placeholder="描述你的目的地、人数和偏好，例如：安排一个5天巴黎艺术之旅。"
      />
      <Button
        type="primary"
        theme="solid"
        onClick={onSend}
        loading={isLoading}
        disabled={!value.trim()}
      >
        生成行程
      </Button>
    </div>
  );
}

ChatComposer.defaultProps = {
  value: '',
  isLoading: false,
  onChange: () => {},
  onSend: () => {},
};

export default ChatComposer;
