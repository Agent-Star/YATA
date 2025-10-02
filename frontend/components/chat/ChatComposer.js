import { Button, TextArea } from '@douyinfe/semi-ui';
import { useTranslation } from 'react-i18next';

function ChatComposer({ value, onChange, onSend, isLoading }) {
  const { t } = useTranslation();

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
        placeholder={t('chat.composerPlaceholder')}
        disabled={isLoading}
      />
      <Button
        type="primary"
        theme="solid"
        onClick={onSend}
        loading={isLoading}
        disabled={isLoading || !value.trim()}
      >
        {t('chat.sendButton')}
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
