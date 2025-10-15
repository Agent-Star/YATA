// 模拟api调用，改为调用后端接口后已不再使用
const API_URL = 'https://api.zmon.me/v1/chat/completions';
const API_KEY = '';
const DEFAULT_MODEL = 'DeepSeek-R1';

async function callChatCompletion({ prompt }) {
  const response = await fetch(API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({
      model: DEFAULT_MODEL,
      messages: [
        {
          role: 'system',
          content:
            'You are an experienced travel planner. Respond with detailed, well-structured itineraries and tips based on the user request.',
        },
        { role: 'user', content: prompt },
      ],
    }),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(errorBody || `Upstream request failed with ${response.status}`);
  }

  const data = await response.json();
  const content = data?.choices?.[0]?.message?.content?.trim();

  if (!content) {
    throw new Error('Assistant returned an empty response');
  }

  return content;
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ message: 'Method Not Allowed' });
  }

  if (!API_KEY) {
    return res.status(500).json({ message: 'ZMON_API_KEY is not configured' });
  }

  const { prompt } = req.body || {};

  if (!prompt || typeof prompt !== 'string') {
    return res.status(400).json({ message: 'Prompt is required' });
  }

  try {
    const content = await callChatCompletion({ prompt });
    return res.status(200).json({ content });
  } catch (error) {
    console.error(error);
    return res.status(502).json({ message: error.message || 'Upstream service error' });
  }
}
