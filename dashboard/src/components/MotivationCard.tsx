// dashboard/src/components/MotivationCard.tsx

import React from "react";

const tips = [
  {
    quote: "“The stock market is a device for transferring money from the impatient to the patient.”",
    author: "Warren Buffett",
    color: "from-green-400 via-blue-400 to-purple-400"
  },
  {
    quote: "“Do not save what is left after spending, but spend what is left after saving.”",
    author: "Warren Buffett",
    color: "from-yellow-400 via-pink-400 to-red-400"
  },
  {
    quote: "“An investment in knowledge pays the best interest.”",
    author: "Benjamin Franklin",
    color: "from-indigo-400 via-sky-400 to-emerald-400"
  }
];

const randomTip = tips[Math.floor(Math.random() * tips.length)];

const MotivationCard: React.FC = () => (
  <div
    className={`w-full max-w-2xl mx-auto my-8 p-6 rounded-2xl shadow-lg bg-gradient-to-r ${randomTip.color} text-white transition-transform hover:scale-105`}
    style={{ minHeight: 120 }}
  >
    <div className="text-xl font-semibold mb-2 animate-pulse">{randomTip.quote}</div>
    <div className="text-right text-md font-medium opacity-90">— {randomTip.author}</div>
  </div>
);

export default MotivationCard;
