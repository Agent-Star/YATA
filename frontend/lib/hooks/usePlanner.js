import { useCallback } from 'react';
import { usePlannerContext } from '@store/plannerContext';
import { requestPlan } from '@lib/services/aiPlanner';

function formatPlanResponse(plan) {
  const itinerary = plan.itinerary.map((line, index) => `${index + 1}. ${line}`).join('\n');
  const tips = plan.tips.map((tip) => `- ${tip}`).join('\n');

  return `${plan.headline}\n\n行程安排：\n${itinerary}\n\n旅行贴士：\n${tips}`;
}

export function usePlanner() {
  const { state, dispatch } = usePlannerContext();

  const setActiveSection = useCallback(
    (sectionKey) => {
      dispatch({ type: 'SET_ACTIVE_SECTION', payload: sectionKey });
    },
    [dispatch]
  );

  const addAssistantError = useCallback(() => {
    dispatch({
      type: 'ADD_MESSAGE',
      payload: {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: '抱歉，暂时无法生成计划，请稍后再试。',
      },
    });
  }, [dispatch]);

  const sendMessage = useCallback(
    async (content) => {
      const trimmed = content.trim();

      if (!trimmed) {
        return;
      }

      const userMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: trimmed,
      };

      dispatch({ type: 'ADD_MESSAGE', payload: userMessage });
      dispatch({ type: 'SET_LOADING', payload: true });

      try {
        const plan = await requestPlan(trimmed);
        const assistantMessage = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: formatPlanResponse(plan),
        };

        dispatch({ type: 'ADD_MESSAGE', payload: assistantMessage });
      } catch (error) {
        addAssistantError();
      } finally {
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    },
    [addAssistantError, dispatch]
  );

  const triggerQuickAction = useCallback(
    async (action) => {
      dispatch({ type: 'PREPEND_QUICK_ACTION', payload: action });
      await sendMessage(action.prompt);
    },
    [dispatch, sendMessage]
  );

  return {
    state,
    sendMessage,
    triggerQuickAction,
    setActiveSection,
  };
}
