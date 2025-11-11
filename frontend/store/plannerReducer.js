import { sidebarGroups } from '@data/sidebarSections';
import { quickActions } from '@data/quickActions';

export const initialPlannerState = {
  activeSection: 'ai-planner',
  sidebarGroups,
  quickActions,
  messages: [],
  favorites: [],
  pendingFavoriteSyncQueue: [],
  isLoading: false,
  hasInitializedHistory: false,
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
    case 'SET_MESSAGES':
      return {
        ...state,
        messages: Array.isArray(action.payload) ? action.payload : [],
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
    case 'UPDATE_MESSAGE':
      return {
        ...state,
        messages: state.messages.map((message) =>
          message.id === action.payload.id
            ? { ...message, ...action.payload.updates }
            : message
        ),
      };
    case 'SET_HISTORY_INITIALIZED':
      return {
        ...state,
        hasInitializedHistory: true,
      };
    case 'SET_FAVORITES': {
      const favorites = Array.isArray(action.payload) ? action.payload : [];
      const favoriteIds = new Set(favorites.map((item) => item.messageId));

      return {
        ...state,
        favorites,
        messages: state.messages.map((message) => {
          const key = message.serverMessageId || message.id;
          const shouldBeFavorited = favoriteIds.has(key);

          if (!!message.isFavorited !== shouldBeFavorited) {
            return { ...message, isFavorited: shouldBeFavorited };
          }

          return message;
        }),
      };
    }
    case 'TOGGLE_FAVORITE': {
      const { messageId, favorite, isFavorited } = action.payload;
      const exists = state.favorites.some((item) => item.messageId === messageId);
      let updatedFavorites = state.favorites;

      if (isFavorited) {
        if (favorite) {
          updatedFavorites = exists
            ? state.favorites.map((item) =>
                item.messageId === messageId ? favorite : item
              )
            : [...state.favorites, favorite];
        }
      } else if (exists) {
        updatedFavorites = state.favorites.filter((item) => item.messageId !== messageId);
      }

      return {
        ...state,
        favorites: updatedFavorites,
        messages: state.messages.map((message) => {
          const key = message.serverMessageId || message.id;

          if (key === messageId) {
            return { ...message, isFavorited };
          }

          return message;
        }),
      };
    }
    case 'QUEUE_FAVORITE_SYNC': {
      const queue = Array.isArray(action.payload) ? action.payload : [];
      return {
        ...state,
        pendingFavoriteSyncQueue: queue,
      };
    }
    default:
      return state;
  }
}
