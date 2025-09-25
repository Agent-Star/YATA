const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const extractEnglishCity = (prompt) => {
  return prompt.match(/to\s+([A-Z][A-Za-z\s]+)/i)?.[1]?.trim();
};

const isChinesePrompt = (prompt) => /[\u4e00-\u9fa5]/.test(prompt);

export async function requestPlan(prompt) {
  await delay(600);

  const englishCity = extractEnglishCity(prompt);
  const fallbackCity = isChinesePrompt(prompt) ? '你的目的地' : 'your destination';
  const city = englishCity || fallbackCity;

  return {
    city,
    headlineKey: 'chat.plan.headline',
    itinerary: [
      { day: 1, highlightKey: 'chat.plan.highlights.1' },
      { day: 2, highlightKey: 'chat.plan.highlights.2' },
      { day: 3, highlightKey: 'chat.plan.highlights.3' },
    ],
    tips: [
      'chat.plan.tips.1',
      'chat.plan.tips.2',
      'chat.plan.tips.3',
    ],
  };
}
