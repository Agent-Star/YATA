import { useEffect, useMemo, useRef, useState } from 'react';
import { Card, Typography, Button, Toast } from '@douyinfe/semi-ui';
import {
  IconArrowUp,
  IconArrowDown,
  IconHeartStroked,
  IconLikeHeart,
  IconCopy,
} from '@douyinfe/semi-icons';
import ReactMarkdown from 'react-markdown';
import { useTranslation } from 'react-i18next';

function ChatMessage({ message, onToggleFavorite }) {
  const { t } = useTranslation();
  const { role, content, contentKey, contentParams, isStreaming, isFavorited } = message;
  const isUser = role === 'user';
  const displayContent = contentKey ? t(contentKey, contentParams) : content;
  const handleFavoriteClick = () => {
    if (onToggleFavorite) {
      onToggleFavorite(message);
    }
  };
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(displayContent || '');
      Toast.success(t('chat.copySuccess'));
    } catch (error) {
      Toast.error(t('chat.copyFailed'));
    }
  };
  return (
    <div
      className={`chat-message ${isUser ? 'chat-message--user' : 'chat-message--assistant'}${isStreaming && !isUser ? ' chat-message--streaming' : ''
        }`}
    >
      <div className="chat-message__inner">
        <Card className="chat-message__card" bordered={false} style={{ maxWidth: '70%' }}>
          <Typography.Text strong={isUser}>
            {isUser ? t('chat.you') : t('chat.assistant')}
          </Typography.Text>
          <div
            className={`chat-message__content${isStreaming && !isUser ? ' chat-message__content--streaming' : ''
              }`}
          >
            <div className="chat-message__markdown">
              <ReactMarkdown>{displayContent}</ReactMarkdown>
            </div>
          </div>
        </Card>
        <div className="chat-message__actions">
          <Button
            icon={<IconCopy />}
            theme="borderless"
            type="tertiary"
            className="chat-message__favorite"
            onClick={handleCopy}
            aria-label={t('chat.copyMessage')}
          />
          <Button
            icon={isFavorited ? <IconLikeHeart /> : <IconHeartStroked />}
            theme="borderless"
            type="tertiary"
            className={`chat-message__favorite${isFavorited ? ' is-active' : ''}`}
            onClick={handleFavoriteClick}
            aria-label={
              isFavorited ? t('chat.removeFromFavorites') : t('chat.saveToFavorites')
            }
          />
        </div>
      </div>
    </div>
  );
}

function ChatHistory({ messages, isLoading, onToggleFavorite }) {
  const { t } = useTranslation();
  const historyRef = useRef(null);
  const touchStartYRef = useRef(null);
  const wasLoadingRef = useRef(false);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);
  const [isAtTop, setIsAtTop] = useState(true);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [autoScrollDisabledManually, setAutoScrollDisabledManually] = useState(
    false,
  );

  const handleScroll = () => {
    if (!historyRef.current) {
      return;
    }

    const { scrollTop, scrollHeight, clientHeight } = historyRef.current;
    const atTop = scrollTop <= 8;
    const atBottom = scrollHeight - (scrollTop + clientHeight) <= 40;

    setIsAtTop(atTop);
    setIsAtBottom(atBottom);
    if (!autoScrollDisabledManually) {
      setAutoScrollEnabled(atBottom);
    }
  };

  const lastMessageSignature = useMemo(() => {
    if (!messages.length) {
      return `empty-${isLoading ? 'loading' : 'idle'}`;
    }

    const lastMessage = messages[messages.length - 1];
    const contentLength = lastMessage.content ? lastMessage.content.length : 0;
    return `${lastMessage.id || 'no-id'}-${contentLength}-${lastMessage.isStreaming ? 'stream' : 'static'}`;
  }, [messages, isLoading]);

  useEffect(() => {
    if (!historyRef.current || !autoScrollEnabled) {
      return;
    }

    const container = historyRef.current;
    container.scrollTo({
      top: container.scrollHeight,
      behavior: 'smooth',
    });
  }, [lastMessageSignature, isLoading, autoScrollEnabled]);

  const disableAutoScroll = () => {
    setAutoScrollEnabled(false);
    setAutoScrollDisabledManually(true);
  };

  const handleWheel = (event) => {
    if (event.deltaY < 0) {
      disableAutoScroll();
    }
  };

  const handleTouchStart = (event) => {
    if (event.touches.length > 0) {
      touchStartYRef.current = event.touches[0].clientY;
    }
  };

  const handleTouchMove = (event) => {
    if (touchStartYRef.current == null || event.touches.length === 0) {
      return;
    }

    const currentY = event.touches[0].clientY;
    const deltaY = currentY - touchStartYRef.current;

    if (deltaY < 0) {
      disableAutoScroll();
      touchStartYRef.current = currentY;
    }
  };

  const handleTouchEnd = () => {
    touchStartYRef.current = null;
  };

  const scrollToTop = () => {
    if (!historyRef.current) {
      return;
    }

    historyRef.current.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const scrollToBottom = () => {
    if (!historyRef.current) {
      return;
    }

    historyRef.current.scrollTo({
      top: historyRef.current.scrollHeight,
      behavior: 'smooth',
    });
    setAutoScrollEnabled(true);
    setAutoScrollDisabledManually(false);
  };

  const hasMessages = messages.length > 0;

  useEffect(() => {
    if (isLoading && !wasLoadingRef.current) {
      setAutoScrollDisabledManually(false);
      setAutoScrollEnabled(true);
    }

    wasLoadingRef.current = isLoading;
  }, [isLoading]);

  return (
    <div
      className="chat-history"
      ref={historyRef}
      onScroll={handleScroll}
      onWheel={handleWheel}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onTouchCancel={handleTouchEnd}
    >
      {messages.map((message) => (
        <ChatMessage
          key={message.id}
          message={message}
          onToggleFavorite={onToggleFavorite}
        />
      ))}
      {hasMessages ? (
        <div className="chat-history__controls">
          <Button
            icon={<IconArrowUp />}
            theme="solid"
            type="primary"
            className="chat-history__control-button"
            onClick={scrollToTop}
            disabled={isAtTop}
            aria-label={t('chat.scrollToTop')}
          />
          <Button
            icon={<IconArrowDown />}
            theme="solid"
            type="primary"
            className="chat-history__control-button"
            onClick={scrollToBottom}
            disabled={isAtBottom}
            aria-label={t('chat.scrollToBottom')}
          />
        </div>
      ) : null}
    </div>
  );
}

export default ChatHistory;
