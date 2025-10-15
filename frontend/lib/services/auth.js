import { apiRequest } from './apiClient';

export async function login({ account, password }) {
  const data = await apiRequest('/auth/login', {
    method: 'POST',
    body: { account, password },
  });

  return data;
}

export async function register({ account, password }) {
  const data = await apiRequest('/auth/register', {
    method: 'POST',
    body: { account, password },
  });

  return data;
}

export async function logout() {
  await apiRequest('/auth/logout', {
    method: 'POST',
  });
}

export async function fetchProfile() {
  const data = await apiRequest('/auth/profile', {
    method: 'GET',
  });

  return data;
}
