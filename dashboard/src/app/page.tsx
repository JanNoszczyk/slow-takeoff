'use client';

import React, { useState, FormEvent, useEffect } from 'react';
import ErrorBoundary from '@/components/ErrorBoundary'; // Re-add ErrorBoundary

// Declare Babel on window if TS complains
declare global {
  interface Window {
    Babel?: {
      transform: (code: string, options: any) => { code: string | null };
    };
  }
}

// Define the expected API response structure
interface DynamicContent {
  tsx: string;
  css: string;
}

export default function Home() {
  const [stockQuery, setStockQuery] = useState<string>('');
  const [dynamicContent, setDynamicContent] = useState<DynamicContent | null>(null);
  const [compiledElement, setCompiledElement] = useState<React.ReactNode | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const styleTagId = 'dynamic-tailwind-styles'; // ID for the injected style tag

  // Effect to compile TSX and inject CSS when dynamicContent changes
  useEffect(() => {
    // Clean up previous styles
    const existingStyleTag = document.getElementById(styleTagId);
    if (existingStyleTag) {
      existingStyleTag.remove();
    }

    if (dynamicContent?.tsx && dynamicContent.css && window.Babel) {
      try {
        // 1. Inject CSS into head
        console.log("Injecting dynamic CSS...");
        console.log("Dynamic CSS to inject (first 500 chars):", JSON.stringify(dynamicContent.css.substring(0, 500))); // Log CSS
        const style = document.createElement('style');
        style.id = styleTagId;
        style.textContent = dynamicContent.css;
        document.head.appendChild(style);
        console.log("Dynamic CSS injected.");

        // 2. Compile TSX using Babel
        console.log("Attempting to compile TSX string with Babel...");
        console.log("TSX for Babel:", JSON.stringify(dynamicContent.tsx)); // Added for debugging
        const compiled = window.Babel.transform(dynamicContent.tsx, {
          presets: ['react'],
        });

        console.log("Babel's compiled code:", compiled?.code); // ADDED THIS LOG

        if (compiled?.code) {
          console.log("Babel compilation deemed successful by presence of compiled.code.");
          try {
            console.log("Attempting to create factory function...");
            // Explicitly return compiled.code.
            // compiled.code should be a string like "React.createElement(...)"
            const factory = new Function('React', `return ${compiled.code}`); 
            console.log("Factory function created. Attempting to create element...");
            const element = factory(React);
            console.log("Created React element:", element); // ADDED LOG
            setCompiledElement(element);
            setError(null); // Clear previous errors
            console.log("React element created successfully.");
          } catch (factoryError: unknown) {
            console.error("Error during factory function creation or execution:", factoryError);
            setError(`Error creating component from compiled code: ${factoryError instanceof Error ? factoryError.message : String(factoryError)}`);
            setCompiledElement(null);
          }
        } else {
          // This case handles if Babel.transform returns null or no code.
          console.error('Babel compilation resulted in null or empty code.');
          setError('Babel compilation failed: No output code.');
          setCompiledElement(null);
          // throw new Error('Babel compilation resulted in empty code.'); // Original throw
        }
      } catch (babelTransformError: unknown) { // Changed variable name for clarity
        // This catch block is specifically for errors from Babel.transform itself
        console.error('Error directly from Babel.transform():', babelTransformError);
        setError(`Babel.transform() failed: ${babelTransformError instanceof Error ? babelTransformError.message : String(babelTransformError)}`);
        setCompiledElement(null);
      }
    } else if (dynamicContent && !window.Babel) {
      console.error("Babel is not available on window object.");
      setError("Babel compiler not loaded. Cannot render dynamic component.");
      setCompiledElement(null);
    } else {
      // Clear compiled element if dynamicContent is null
      setCompiledElement(null);
    }

    // Cleanup function to remove style tag on unmount or before next run
    return () => {
      const styleTag = document.getElementById(styleTagId);
      if (styleTag) {
        styleTag.remove();
        console.log("Dynamic CSS removed.");
      }
    };
  }, [dynamicContent]); // Re-run when dynamicContent changes


  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsLoading(true);
    setDynamicContent(null); // Reset dynamic content
    setCompiledElement(null); // Reset compiled element
    setError(null);

    try {
      // Use GET request with query parameter
      const response = await fetch(`/api/generate-dashboard?stockQuery=${encodeURIComponent(stockQuery)}`, {
        method: 'GET', // Change to GET
        headers: {
          'Accept': 'application/json', // Expect JSON response
        },
        // No body for GET request
      });

      if (!response.ok) {
         // Try to parse error JSON, fallback to text
         let errorMsg = `HTTP error! status: ${response.status}`;
         try {
            const errorJson = await response.json();
            errorMsg = errorJson.error || errorMsg;
         } catch {
            errorMsg = await response.text() || errorMsg;
         }
        throw new Error(errorMsg);
      }

      const data: DynamicContent = await response.json();
      console.log('Received dynamic content (TSX + CSS):', data);
      setDynamicContent(data); // Set the received TSX and CSS

    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred during fetch.');
      }
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-start p-12 bg-slate-50">
      <h1 className="text-3xl font-bold mb-8 text-gray-800">Stock Research Dashboard</h1>

      <form onSubmit={handleSubmit} className="mb-8 w-full max-w-md flex gap-2">
        <input
          type="text"
          value={stockQuery}
          onChange={(e) => setStockQuery(e.target.value)}
          placeholder="Enter stock symbol (e.g., NVDA)"
          className="flex-grow p-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        />
        <button
          type="submit"
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
          disabled={isLoading || !stockQuery.trim()}
        >
          {isLoading ? 'Loading...' : 'Get Dashboard'}
        </button>
      </form>

      {isLoading && <p className="text-gray-600">Generating dashboard and styles, please wait...</p>}

      {/* Render compile/fetch/API error message */}
      {error && <div className="text-red-600 bg-red-100 border border-red-400 rounded p-4 w-full max-w-4xl whitespace-pre-wrap">{error}</div>}

      {/* Render the compiled element within an Error Boundary */}
      {compiledElement && !isLoading && !error && (
        <ErrorBoundary>
          {/* Render the compiled element directly */}
          <div className="mt-6 w-full max-w-6xl">
             {compiledElement}
          </div>
        </ErrorBoundary>
      )}
    </main>
  );
}
