/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic":
          "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
      },
    },
  },
  safelist: [
    // Add all classes used in the dynamically generated TSX here
    // Outer div
    'border', 'border-gray-200', 'dark:border-gray-700', 'rounded-xl', 'bg-white', 'dark:bg-gray-800', 'shadow-lg', 'overflow-hidden', 'flex', 'flex-col', 'h-full', 'transition-shadow', 'hover:shadow-xl',
    // Image placeholder div & SVG
    'w-full', 'h-32', 'bg-gray-200', 'dark:bg-gray-700', 'items-center', 'justify-center', 'rounded-t-lg', 'mb-3', 'h-12', 'w-12', 'text-gray-400',
    // Image (if present)
    'object-cover',
    // Content div
    'p-4', 'flex-grow', 'space-y-3',
    // Headline
    'font-bold', 'text-lg', 'text-gray-900', 'dark:text-white', 'leading-tight',
    // Source/Date div & separator
    'text-xs', 'text-gray-500', 'dark:text-gray-400', 'mx-1',
    // Reason p
    'text-sm', 'italic', 'text-gray-600', 'dark:text-gray-300',
    // Transcript div & p
    'border-l-2', 'border-gray-200', 'dark:border-gray-600', 'pl-2', 'my-2', 'max-h-32', 'overflow-y-auto', 'whitespace-pre-wrap',
    // Bottom div
    'mt-auto', 'pt-3', 'justify-between',
    // Sentiment span & value
    'font-medium', 'text-gray-700', 'dark:text-gray-300', 'font-semibold',
    'text-green-600', 'dark:text-green-400', // Positive sentiment
    'text-red-600', 'dark:text-red-400',     // Negative sentiment
    // Link
    'text-blue-600', 'hover:text-blue-800', 'dark:text-blue-400', 'dark:hover:text-blue-300', 'self-end', 'mt-1',
    // Grid container (from _generate_news_display_code_logic)
    'grid', 'grid-cols-1', 'md:grid-cols-2', 'lg:grid-cols-3', 'gap-4',
  ],
  plugins: [],
};
