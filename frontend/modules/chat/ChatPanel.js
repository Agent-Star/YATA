import { useEffect, useRef, useState } from 'react';
import ChatComposer from '@components/chat/ChatComposer';
import ChatHeader from '@components/chat/ChatHeader';
import ChatHistory from '@components/chat/ChatHistory';
import QuickActionList from '@components/chat/QuickActionList';
import { usePlanner } from '@lib/hooks/usePlanner';
import { Modal, Toast, Button } from '@douyinfe/semi-ui';
import { useTranslation } from 'react-i18next';

function ChatPanel() {
  const [draft, setDraft] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isVoiceSupported, setIsVoiceSupported] = useState(true);
  const [isClearModalVisible, setIsClearModalVisible] = useState(false);
  const [isClearingCloud, setIsClearingCloud] = useState(false);
  const recognitionRef = useRef(null);
  const {
    state: { messages, quickActions, isLoading, hasInitializedHistory },
    sendMessage,
    triggerQuickAction,
    loadHistory,
    toggleFavoriteMessage,
    clearLocalHistory,
    deleteRemoteHistory,
  } = usePlanner();
  const { i18n, t } = useTranslation();

  const handleSend = async () => {
    const message = draft.trim();

    if (!message) {
      return;
    }

    setDraft('');
    await sendMessage(message);
  };

  const handleQuickAction = async (action) => {
    setDraft('');
    await triggerQuickAction(action);
  };

  useEffect(() => {
    if (!hasInitializedHistory) {
      loadHistory();
    }
  }, [hasInitializedHistory, loadHistory]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setIsVoiceSupported(false);
      return;
    }

    const recognition = new SpeechRecognition();

    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = i18n?.language || 'en-US';

    recognition.onresult = (event) => {
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];

        if (result.isFinal) {
          finalTranscript += result[0].transcript;
        }
      }

      if (finalTranscript.trim().length > 0) {
        const cleanTranscript = finalTranscript.trim();

        setDraft((prev) => {
          if (!prev) {
            return cleanTranscript;
          }

          const separator = prev.endsWith(' ') ? '' : ' ';
          return `${prev}${separator}${cleanTranscript}`;
        });
      }
    };

    recognition.onstart = () => setIsListening(true);
    recognition.onerror = (event) => {
      setIsListening(false);

      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        Toast.warning(t('chat.voiceInputPermissionDenied'));
      }
    };
    recognition.onend = () => setIsListening(false);

    recognitionRef.current = recognition;
    setIsVoiceSupported(true);

    return () => {
      recognition.onresult = null;
      recognition.onstart = null;
      recognition.onerror = null;
      recognition.onend = null;

      try {
        recognition.stop();
      } catch (error) {
        // SpeechRecognition.stop() may throw if it never started; ignore.
      }

      recognitionRef.current = null;
    };
  }, [i18n?.language, t]);

  const handleVoiceInput = () => {
    if (!recognitionRef.current) {
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
      return;
    }

    try {
      recognitionRef.current.lang = i18n?.language || 'en-US';
      recognitionRef.current.start();
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to start speech recognition', error);
      setIsListening(false);

      if (error.name === 'NotAllowedError' || error.message === 'not-allowed') {
        Toast.warning(t('chat.voiceInputPermissionDenied'));
      }
    }
  };

  const handleClearHistory = () => {
    setIsClearModalVisible(true);
  };

  const handleClearLocalOnly = () => {
    clearLocalHistory();
    Toast.info(t('chat.clearHistoryLocalSuccess'));
    setIsClearModalVisible(false);
  };

  const handleClearCloud = async () => {
    clearLocalHistory();
    setIsClearingCloud(true);
    try {
      await deleteRemoteHistory();
      Toast.success(t('chat.clearHistoryCloudSuccess'));
    } catch (error) {
      Toast.error(t('chat.clearHistoryCloudFailed'));
    } finally {
      setIsClearingCloud(false);
      setIsClearModalVisible(false);
    }
  };

  return (
    <div className="chat-panel">
      <ChatHeader />
      <QuickActionList actions={quickActions} onSelect={handleQuickAction} />
      <ChatHistory
        messages={messages}
        isLoading={isLoading}
        onToggleFavorite={toggleFavoriteMessage}
      />
      <ChatComposer
        value={draft}
        onChange={setDraft}
        onSend={handleSend}
        onVoiceInput={handleVoiceInput}
        isListening={isListening}
        isVoiceSupported={isVoiceSupported}
        isLoading={isLoading}
        onClearHistory={handleClearHistory}
      />
      <Modal
        title={t('chat.clearHistoryPromptTitle')}
        visible={isClearModalVisible}
        onCancel={() => setIsClearModalVisible(false)}
        maskClosable={false}
        footer={[
          <Button key="local" onClick={handleClearLocalOnly}>
            {t('chat.clearHistoryLocalOnly')}
          </Button>,
          <Button
            key="cloud"
            theme="solid"
            loading={isClearingCloud}
            onClick={handleClearCloud}
          >
            {t('chat.clearHistoryCloudConfirm')}
          </Button>,
        ]}
      >
        <p>{t('chat.clearHistoryPrompt')}</p>
        <p>{t('chat.clearHistoryCloud')}</p>
      </Modal>
    </div>
  );
}

export default ChatPanel;
