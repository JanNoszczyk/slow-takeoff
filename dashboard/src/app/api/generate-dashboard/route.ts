import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { StockDashboardData } from '../../../../types/dashboard'; // Correct relative path


export async function POST(request: Request) {
  try {
    const { stockQuery } = await request.json();

    if (!stockQuery || typeof stockQuery !== 'string') {
      return NextResponse.json({ error: 'Missing or invalid stockQuery parameter' }, { status: 400 });
    }

    // Path to the python executable and the script
    // Assuming python3 is in PATH and the script is at the root relative to dashboard app
    const pythonExecutable = 'python3'; // Or specify full path if needed
    // Construct path relative to the current file location (__dirname is not available in ESM)
    // process.cwd() should give the root of the Next.js project
    const scriptPath = path.join(process.cwd(), '..', 'run_pipeline.py'); // Go up one level from 'dashboard'

    console.log(`API: Executing script: ${pythonExecutable} ${scriptPath} "${stockQuery}"`);

    const pythonProcess = spawn(pythonExecutable, [scriptPath, stockQuery]);

    let jsonData = '';
    let errorData = '';

    pythonProcess.stdout.on('data', (data) => {
      jsonData += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      errorData += data.toString();
      console.error(`API stderr: ${data}`); // Log stderr for debugging
    });

    const result: StockDashboardData = await new Promise((resolve, reject) => {
      pythonProcess.on('close', (code) => {
        console.log(`API: Python script exited with code ${code}`);
        if (code !== 0) {
          // Reject with error including stderr content
          reject(new Error(`Python script failed with code ${code}. Error: ${errorData || 'Unknown error'}`));
        } else {
          try {
            // Attempt to parse the JSON output from stdout
            const parsedData = JSON.parse(jsonData) as StockDashboardData;
            // If the parsed data itself contains an error field from the agent
            if (parsedData.error) {
                console.warn("API: Agent returned an error field:", parsedData.error);
                // Optionally, you could reject here or just pass the error through
            }
             // Add stderr log if present, even on success, for potential warnings
             if (errorData) {
                if(!parsedData.error) parsedData.error = ""; // Initialize error if not present
                parsedData.error += ` | Python stderr logs: ${errorData.substring(0, 500)}${errorData.length > 500 ? '...' : ''}`; // Append stderr snippet
            }
            resolve(parsedData);
          } catch (parseError) {
            console.error("API: Error parsing JSON output:", parseError);
            console.error("API: Raw JSON output:", jsonData); // Log raw output
             // Reject with parsing error and include stderr
            reject(new Error(`Failed to parse JSON output from Python script. Parse Error: ${parseError}. Stderr: ${errorData || 'None'}`));
          }
        }
      });

      pythonProcess.on('error', (err) => {
        console.error('API: Failed to start Python process:', err);
        reject(new Error(`Failed to start Python process: ${err.message}`));
      });
    });

    return NextResponse.json(result);

  } catch (error: any) {
    console.error("API: Error in POST handler:", error);
    return NextResponse.json({ error: error.message || 'An unexpected error occurred' }, { status: 500 });
  }
}
