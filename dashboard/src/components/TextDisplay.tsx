// dashboard/components/TextDisplay.tsx

import React from 'react';

interface TextDisplayProps {
  label: string;
  value: string | number | undefined | null;
}

const TextDisplay: React.FC<TextDisplayProps> = ({ label, value }) => {
  return (
    <div className="mb-4">
      <p className="text-gray-500 text-sm">{label}</p>
      <p className="text-gray-800 text-lg font-semibold">{value !== undefined && value !== null ? value : 'N/A'}</p>
    </div>
  );
};

export default TextDisplay;
