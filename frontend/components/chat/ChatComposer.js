import { useState } from 'react';
import { Button, TextArea } from '@douyinfe/semi-ui';
import { IconMicrophone, IconSearchStroked } from '@douyinfe/semi-icons';
import { useTranslation } from 'react-i18next';

function ChatComposer({ value, onChange, onSend, onVoiceInput, isLoading }) {
  const { t } = useTranslation();
  const [isFocused, setIsFocused] = useState(false);

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      onSend();
    }
  };

  const showPlaceholder = !isFocused && value.length === 0;

  const handleFocus = () => setIsFocused(true);
  const handleBlur = () => setIsFocused(false);

  return (
    <div className="chat-composer">
      <div className="chat-composer__input">
        <IconSearchStroked
          className="chat-composer__search-icon"
          aria-hidden="true"
        />
        {showPlaceholder && (
          <div className="chat-composer__placeholder" aria-hidden="true">
            {t('chat.composerPlaceholder')}
          </div>
        )}
        <TextArea
          value={value}
          onChange={onChange}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          onBlur={handleBlur}
          autosize={{ minRows: 1, maxRows: 3 }}
          placeholder={t('chat.composerPlaceholder')}
          disabled={isLoading}
        />
        <Button
          type="tertiary"
          theme="borderless"
          icon={<IconMicrophone />}
          aria-label={t('chat.voiceInputButton')}
          onClick={onVoiceInput}
          disabled={isLoading}
          className="chat-composer__voice-button"
        />
      </div>
      <div className="chat-composer__actions">
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
    </div>
  );
}

ChatComposer.defaultProps = {
  value: '',
  isLoading: false,
  onChange: () => {},
  onSend: () => {},
  onVoiceInput: () => {},
};

export default ChatComposer;
