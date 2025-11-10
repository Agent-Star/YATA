import { useEffect, useRef, useState } from 'react';
import ChatComposer from '@components/chat/ChatComposer';
import ChatHeader from '@components/chat/ChatHeader';
import ChatHistory from '@components/chat/ChatHistory';
import QuickActionList from '@components/chat/QuickActionList';
import { usePlanner } from '@lib/hooks/usePlanner';
import { Toast } from '@douyinfe/semi-ui';
import { useTranslation } from 'react-i18next';

function ChatPanel() {
  const [draft, setDraft] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isVoiceSupported, setIsVoiceSupported] = useState(true);
  const recognitionRef = useRef(null);
  const {
    state: { messages, quickActions, isLoading, hasInitializedHistory },
    sendMessage,
    triggerQuickAction,
    loadHistory,
    toggleFavoriteMessage,
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
      // start() will throw if called multiple times without user gesture
      // Reset local listening state so the user can try again.
      // eslint-disable-next-line no-console
      console.error('Failed to start speech recognition', error);
      setIsListening(false);

      if (error.name === 'NotAllowedError' || error.message === 'not-allowed') {
        Toast.warning(t('chat.voiceInputPermissionDenied'));
      }
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
      />
    </div>
  );
}

export default ChatPanel;
