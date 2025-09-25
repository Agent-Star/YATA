export async function requestPlan(prompt) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ prompt }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.message || 'Failed to fetch plan from assistant');
  }

  const data = await response.json();

  if (!data?.content) {
    throw new Error('Assistant response is empty');
  }

  return data.content;
}
