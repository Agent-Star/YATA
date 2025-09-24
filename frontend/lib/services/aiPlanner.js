const sampleDailyPlan = (day, city, highlight) => {
  return `Day ${day} in ${city}: ${highlight}.`;
};

export async function requestPlan(prompt) {
  await new Promise((resolve) => setTimeout(resolve, 600));

  const city = prompt.match(/to\s([A-Z][A-Za-z\s]+)/i)?.[1]?.trim() || 'your destination';

  return {
    headline: `Here is a tailored itinerary for ${city}.`,
    itinerary: [
      sampleDailyPlan(1, city, 'Arrive, explore the historic center and enjoy local cuisine'),
      sampleDailyPlan(2, city, 'Immerse in signature cultural experiences and hidden highlights'),
      sampleDailyPlan(3, city, 'Relax, shop for souvenirs, and wrap up with a memorable dinner'),
    ],
    tips: [
      'Adjust the pace of each day depending on your energy levels and interests.',
      'Reserve popular experiences in advance to secure your spot.',
      'Bring a reusable bottle and stay hydrated during excursions.',
    ],
  };
}
