import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { usePlannerContext } from '@store/plannerContext';
import { Toast } from '@douyinfe/semi-ui';
import {
  streamPlan,
  fetchHistory,
  saveFavorite,
  deleteFavorite,
} from '@lib/services/aiPlanner';

export function usePlanner() {
  const { t, i18n } = useTranslation();
  const { state, dispatch } = usePlannerContext();
  const { hasInitializedHistory } = state;
  const pendingFavoriteQueue = state.pendingFavoriteSyncQueue || [];

  const setActiveSection = useCallback(
    (sectionKey) => {
      dispatch({ type: 'SET_ACTIVE_SECTION', payload: sectionKey });
    },
    [dispatch]
  );

  const sendMessage = useCallback(
    async (content) => {
      const trimmed = content.trim();

      if (!trimmed) {
        return;
      }

      const timestamp = Date.now();
      const userMessage = {
        id: `user-${timestamp}`,
        role: 'user',
        content: trimmed,
        metadata: null,
        isStreaming: false,
        isFavorited: false,
        serverMessageId: null,
      };

      const conversationHistory = [...state.messages, userMessage].map((message) => ({
        id: message.id,
        role: message.role,
        content:
          message.content ||
          (message.contentKey ? i18n.t(message.contentKey, message.contentParams) : ''),
        metadata: message.metadata || null,
      }));

      dispatch({ type: 'ADD_MESSAGE', payload: userMessage });
      dispatch({ type: 'SET_LOADING', payload: true });

      const assistantMessageId = `assistant-${timestamp}`;
      dispatch({
        type: 'ADD_MESSAGE',
        payload: {
          id: assistantMessageId,
          role: 'assistant',
          content: '',
          metadata: null,
          isStreaming: true,
          isFavorited: false,
          serverMessageId: null,
        },
      });

      let accumulated = '';
      let latestMetadata = null;
      const tokenQueue = [];
      let typingTimer = null;
      let queueDrainResolver = null;

      const splitDelta = (delta) => delta?.match(/(\s+|\S+)/g) || [];

      const getDelay = (chunk) => {
        if (!chunk || chunk.trim() === '') {
          return 15;
        }
        if (chunk.length > 12) {
          return 20;
        }
        if (chunk.includes('\n')) {
          return 80;
        }
        if (/[，。！？,.!?]/.test(chunk)) {
          return 100;
        }
        return 35;
      };

      const resolveQueueIfIdle = () => {
        if (!typingTimer && tokenQueue.length === 0 && queueDrainResolver) {
          queueDrainResolver();
          queueDrainResolver = null;
        }
      };

      const cancelTyping = () => {
        if (typingTimer) {
          clearTimeout(typingTimer);
          typingTimer = null;
        }
        tokenQueue.length = 0;
        resolveQueueIfIdle();
      };

      const flushQueue = () => {
        if (tokenQueue.length === 0) {
          typingTimer = null;
          resolveQueueIfIdle();
          return;
        }

        const nextChunk = tokenQueue.shift();
        accumulated += nextChunk;
        if (process.env.NODE_ENV !== 'production') {
          console.debug('[planner] stream token', nextChunk);
        }
        dispatch({
          type: 'UPDATE_MESSAGE',
          payload: {
            id: assistantMessageId,
            updates: {
              content: accumulated,
            },
          },
        });

        typingTimer = setTimeout(() => {
          typingTimer = null;
          flushQueue();
        }, getDelay(nextChunk));
      };

      const enqueueTokens = (delta) => {
        const pieces = splitDelta(delta);
        if (pieces.length === 0) {
          return;
        }
        tokenQueue.push(...pieces);
        if (!typingTimer) {
          flushQueue();
        }
      };

      const waitForQueueToDrain = () =>
        new Promise((resolve) => {
          if (!typingTimer && tokenQueue.length === 0) {
            resolve();
          } else {
            queueDrainResolver = resolve;
          }
        });

      try {

        const result = await streamPlan({
          prompt: trimmed,
          language: i18n.language,
          history: conversationHistory,
          onToken: (delta) => {
            if (!delta) {
              return;
            }

            enqueueTokens(delta);
          },
          onMetadata: (metadata) => {
            latestMetadata = metadata;
            dispatch({
              type: 'UPDATE_MESSAGE',
              payload: {
                id: assistantMessageId,
                updates: {
                  metadata,
                },
              },
            });
          },
        });

        const finalMetadata = result?.metadata ?? latestMetadata;
        await waitForQueueToDrain();
        cancelTyping();

        dispatch({
          type: 'UPDATE_MESSAGE',
          payload: {
            id: assistantMessageId,
            updates: {
              content: accumulated,
              metadata: finalMetadata || null,
              serverMessageId: result?.messageId || null,
              isStreaming: false,
            },
          },
        });
      } catch (error) {
        cancelTyping();
        dispatch({
          type: 'UPDATE_MESSAGE',
          payload: {
            id: assistantMessageId,
            updates: {
              content: t('chat.errorMessage'),
              metadata: null,
              isStreaming: false,
            },
          },
        });
      } finally {
        cancelTyping();
        dispatch({
          type: 'UPDATE_MESSAGE',
          payload: {
            id: assistantMessageId,
            updates: {
              isStreaming: false,
            },
          },
        });
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    },
    [dispatch, i18n, state.messages, t]
  );

  const triggerQuickAction = useCallback(
    async (action) => {
      dispatch({ type: 'PREPEND_QUICK_ACTION', payload: action });
      const promptValue =
        typeof action.prompt === 'string'
          ? action.prompt
          : action.prompt?.[i18n.language] || action.prompt?.en || '';

      if (promptValue) {
        await sendMessage(promptValue);
      }
    },
    [dispatch, i18n.language, sendMessage]
  );

  const loadHistory = useCallback(async () => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      const history = await fetchHistory();
      const mappedMessages = Array.isArray(history?.messages)
        ? history.messages.map((item) => ({
          id: item.id,
          role: item.role,
          content: item.content,
          contentKey: item.contentKey || null,
          contentParams: item.contentParams || null,
          metadata: item.metadata || null,
          isStreaming: false,
          isFavorited: Boolean(item.isFavorited),
          serverMessageId: item.id,
          createdAt: item.createdAt || null,
          savedAt: item.savedAt || null,
        }))
        : null;

      const fallbackMessage = {
        id: 'assistant-welcome',
        role: 'assistant',
        content: t('chat.initialMessage'),
        metadata: null,
        isStreaming: false,
        isFavorited: false,
        serverMessageId: null,
      };

      const nextMessages =
        mappedMessages && mappedMessages.length > 0 ? mappedMessages : [fallbackMessage];

      dispatch({ type: 'SET_MESSAGES', payload: nextMessages });
      const derivedFavorites = nextMessages
        .filter((message) => message.isFavorited)
        .map((message) => ({
          id: `favorite-${message.serverMessageId || message.id}`,
          messageId: message.serverMessageId || message.id,
          role: message.role,
          content: message.content,
          contentKey: message.contentKey || null,
          contentParams: message.contentParams || null,
          metadata: message.metadata || null,
          savedAt: message.savedAt || message.createdAt || Date.now(),
        }));
      dispatch({ type: 'SET_FAVORITES', payload: derivedFavorites });
      dispatch({ type: 'QUEUE_FAVORITE_SYNC', payload: [] });
    } catch (error) {
      dispatch({
        type: 'SET_MESSAGES',
        payload: [
          {
            id: 'assistant-welcome',
            role: 'assistant',
            content: t('chat.initialMessage'),
            metadata: null,
            isStreaming: false,
            isFavorited: false,
            serverMessageId: null,
          },
        ],
      });
      dispatch({ type: 'SET_FAVORITES', payload: [] });
      dispatch({ type: 'QUEUE_FAVORITE_SYNC', payload: [] });
    } finally {
      dispatch({ type: 'SET_HISTORY_INITIALIZED' });
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [dispatch, t]);

  const flushFavoriteQueue = useCallback(
    async (queueOverride) => {
      const sourceQueue =
        queueOverride !== undefined ? queueOverride : pendingFavoriteQueue;

      if (!sourceQueue.length) {
        return;
      }

      const queueSnapshot = [...sourceQueue];
      let remaining = [];

      for (let i = 0; i < queueSnapshot.length; i += 1) {
        const item = queueSnapshot[i];

        try {
          if (item.isFavorited) {
            await saveFavorite(item.messageId);
          } else {
            await deleteFavorite(item.messageId);
          }
        } catch (error) {
          // eslint-disable-next-line no-console
          console.error('Failed to sync favorite queue item', error);
          remaining = queueSnapshot.slice(i);
          break;
        }
      }

      if (remaining.length !== queueSnapshot.length) {
        dispatch({
          type: 'QUEUE_FAVORITE_SYNC',
          payload: remaining,
        });
      }
    },
    [dispatch, pendingFavoriteQueue]
  );

  const toggleFavoriteMessage = useCallback(
    async (message) => {
      if (!message?.id) {
        return;
      }

      const clientGenerated = /^((user|assistant)-)/.test(message.id);
      const targetId = message.serverMessageId || (clientGenerated ? null : message.id);

      if (!targetId) {
        Toast.error(t('chat.favoriteToggleError'));
        return;
      }

      const resolvedContent =
        message.content ||
        (message.contentKey ? t(message.contentKey, message.contentParams) : '');

      const favoritePayload = {
        id: `favorite-${targetId}`,
        messageId: targetId,
        role: message.role,
        content: resolvedContent,
        contentKey: message.contentKey || null,
        contentParams: message.contentParams || null,
        metadata: message.metadata || null,
        savedAt: Date.now(),
      };

      const willFavorite = !message.isFavorited;

      dispatch({
        type: 'TOGGLE_FAVORITE',
        payload: {
          messageId: targetId,
          favorite: willFavorite ? favoritePayload : null,
          isFavorited: willFavorite,
        },
      });

      try {
        if (willFavorite) {
          await saveFavorite(targetId);
        } else {
          await deleteFavorite(targetId);
        }

        const queueAfterRemoval = pendingFavoriteQueue.filter(
          (item) => item.messageId !== targetId
        );
        dispatch({
          type: 'QUEUE_FAVORITE_SYNC',
          payload: queueAfterRemoval,
        });
        await flushFavoriteQueue(queueAfterRemoval);
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Failed to sync favorite', error);
        Toast.error(t('chat.favoriteSyncError'));
        const filteredQueue = pendingFavoriteQueue.filter((item) => item.messageId !== targetId);
        dispatch({
          type: 'QUEUE_FAVORITE_SYNC',
          payload: [...filteredQueue, { messageId: targetId, isFavorited: willFavorite }],
        });
      }
    },
    [dispatch, flushFavoriteQueue, pendingFavoriteQueue, t]
  );

  const removeFavorite = useCallback(
    async (messageId) => {
      if (!messageId) {
        return;
      }

      dispatch({
        type: 'TOGGLE_FAVORITE',
        payload: {
          messageId,
          favorite: null,
          isFavorited: false,
        },
      });
      try {
        await deleteFavorite(messageId);
        const queueAfterRemoval = pendingFavoriteQueue.filter(
          (item) => item.messageId !== messageId
        );
        dispatch({
          type: 'QUEUE_FAVORITE_SYNC',
          payload: queueAfterRemoval,
        });
        await flushFavoriteQueue(queueAfterRemoval);
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Failed to remove favorite', error);
        Toast.error(t('chat.favoriteSyncError'));
        dispatch({
          type: 'QUEUE_FAVORITE_SYNC',
          payload: [
            ...pendingFavoriteQueue.filter((item) => item.messageId !== messageId),
            { messageId, isFavorited: false },
          ],
        });
      }
    },
    [dispatch, flushFavoriteQueue, pendingFavoriteQueue, t]
  );

  return {
    state,
    sendMessage,
    triggerQuickAction,
    setActiveSection,
    loadHistory,
    hasInitializedHistory,
    toggleFavoriteMessage,
    removeFavorite,
  };
}
