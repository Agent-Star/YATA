import { useMemo, useState } from 'react';
import { Button, TextArea } from '@douyinfe/semi-ui';
import { IconMicrophone, IconSearchStroked } from '@douyinfe/semi-icons';
import { useTranslation } from 'react-i18next';

function ChatComposer({
  value,
  onChange,
  onSend,
  onVoiceInput,
  onClearHistory,
  isLoading,
  isListening,
  isVoiceSupported,
}) {
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
  const voiceButtonClassName = useMemo(() => {
    const classNames = ['chat-composer__voice-button'];

    if (isListening) {
      classNames.push('chat-composer__voice-button--active');
    }

    if (!isVoiceSupported) {
      classNames.push('chat-composer__voice-button--disabled');
    }

    return classNames.join(' ');
  }, [isListening, isVoiceSupported]);

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
          disabled={isLoading || !isVoiceSupported}
          aria-pressed={isListening}
          className={voiceButtonClassName}
          title={
            !isVoiceSupported
              ? t('chat.voiceInputUnsupported')
              : isListening
                ? t('chat.voiceInputRecording')
                : t('chat.voiceInputButton')
          }
        />
      </div>
      <div className="chat-composer__actions">
        {onClearHistory ? (
          <Button
            type="primary"
            theme="solid"
            block
            onClick={onClearHistory}
            disabled={isLoading}
            className="chat-composer__action-button"
          >
            {t('chat.clearHistory')}
          </Button>
        ) : null}
        <Button
          type="primary"
          theme="solid"
          onClick={onSend}
          loading={isLoading}
          disabled={isLoading || !value.trim()}
          block
          className="chat-composer__action-button"
        >
          {t('chat.sendButton')}
        </Button>
      </div>
    </div>
  );
}

ChatComposer.defaultProps = {
  value: '',
  onClearHistory: null,
  isLoading: false,
  onChange: () => { },
  onSend: () => { },
  onVoiceInput: () => { },
  isListening: false,
  isVoiceSupported: true,
};

export default ChatComposer;
