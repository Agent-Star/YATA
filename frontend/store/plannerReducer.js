import { sidebarGroups } from '@data/sidebarSections';
import { quickActions } from '@data/quickActions';

export const initialPlannerState = {
  activeSection: 'ai-planner',
  sidebarGroups,
  quickActions,
  messages: [
    {
      id: 'welcome',
      role: 'assistant',
      content:
        '你好，我是你的AI旅行助手。告诉我你想去的地方、出行天数和偏好，我会帮你拟定行程计划。',
    },
  ],
  isLoading: false,
};

export function plannerReducer(state, action) {
  switch (action.type) {
    case 'SET_ACTIVE_SECTION':
      return {
        ...state,
        activeSection: action.payload,
      };
    case 'ADD_MESSAGE':
      return {
        ...state,
        messages: [...state.messages, action.payload],
      };
    case 'SET_LOADING':
      return {
        ...state,
        isLoading: action.payload,
      };
    case 'PREPEND_QUICK_ACTION':
      if (state.quickActions.some((item) => item.key === action.payload.key)) {
        return state;
      }

      return {
        ...state,
        quickActions: [action.payload, ...state.quickActions],
      };
    default:
      return state;
  }
}
