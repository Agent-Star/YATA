import { useState } from 'react';
import ChatComposer from '@components/chat/ChatComposer';
import ChatHeader from '@components/chat/ChatHeader';
import ChatHistory from '@components/chat/ChatHistory';
import QuickActionList from '@components/chat/QuickActionList';
import { usePlanner } from '@lib/hooks/usePlanner';

function ChatPanel() {
  const [draft, setDraft] = useState('');
  const {
    state: { messages, quickActions, isLoading },
    sendMessage,
    triggerQuickAction,
  } = usePlanner();

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

  const handleVoiceInput = () => {
    // Placeholder for voice input integration
  };

  return (
    <div className="chat-panel">
      <ChatHeader />
      <QuickActionList actions={quickActions} onSelect={handleQuickAction} />
      <ChatHistory messages={messages} isLoading={isLoading} />
      <ChatComposer
        value={draft}
        onChange={setDraft}
        onSend={handleSend}
        onVoiceInput={handleVoiceInput}
        isLoading={isLoading}
      />
    </div>
  );
}

export default ChatPanel;
