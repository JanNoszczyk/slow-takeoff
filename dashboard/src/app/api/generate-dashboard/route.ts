import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs/promises'; // For async file operations
import crypto from 'crypto'; // For unique filenames

// Helper function to ensure the temp directory exists
async function ensureTempDir(tempDirPath: string) {
  try {
    await fs.mkdir(tempDirPath, { recursive: true });
  } catch (error: any) {
    if (error.code !== 'EEXIST') {
      throw error; // Rethrow if it's not a "directory already exists" error
    }
  }
}

// Helper function to run a command and return output/error
async function runCommand(command: string, args: string[], cwd: string): Promise<{ stdout: string; stderr: string; code: number | null }> {
    return new Promise((resolve, reject) => {
        console.log(`Running command: ${command} ${args.join(' ')} in ${cwd}`);
        const process = spawn(command, args, { cwd, shell: false }); // Use shell: false for security
        let stdout = '';
        let stderr = '';

        process.stdout.on('data', (data) => stdout += data.toString());
        process.stderr.on('data', (data) => stderr += data.toString());

        process.on('close', (code) => {
            console.log(`Command finished with code ${code}`);
            if (stderr) console.warn(`Command stderr: ${stderr.trim()}`);
            resolve({ stdout, stderr, code });
        });

        process.on('error', (err) => {
            console.error(`Failed to start command ${command}:`, err);
            reject(err);
        });
    });
}


export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const stockQuery = searchParams.get('stockQuery');

  if (!stockQuery || typeof stockQuery !== 'string') {
    return NextResponse.json({ error: 'Missing or invalid stockQuery parameter in URL.' }, { status: 400 });
  }

  // Define paths relative to the Next.js project root (dashboard directory)
  const dashboardDir = process.cwd();
  const tempDir = path.join(dashboardDir, 'temp');
  const uuid = crypto.randomUUID();
  const tempTsxFilePath = path.join(tempDir, `dynamic_${uuid}.tsx`);
  const tempInputCssPath = path.join(tempDir, `input_${uuid}.css`);
  const tempOutputCssPath = path.join(tempDir, `output_${uuid}.css`);

  try {
    // 0. Ensure temp directory exists
    await ensureTempDir(tempDir);

    // 1. Execute Python script to get TSX fragment
    const pythonExecutable = 'python3';
    const scriptPath = path.join(dashboardDir, '..', 'run_pipeline.py'); // Path relative to dashboard dir

    console.log(`API (GET): Executing script: ${pythonExecutable} ${scriptPath} "${stockQuery}"`);
    // Run python script from the project root directory (one level up from dashboard)
    const pythonResult = await runCommand(pythonExecutable, [scriptPath, stockQuery], path.join(dashboardDir, '..'));

    if (pythonResult.code !== 0) {
        throw new Error(`Python script failed (code ${pythonResult.code}). Stderr: ${pythonResult.stderr.substring(0, 500)}...`);
    }
    let finalTsxFragment = pythonResult.stdout.trim();
    if (!finalTsxFragment) {
        console.warn("API (GET): Python script succeeded but produced empty TSX output.");
        finalTsxFragment = '<div class="p-4 text-yellow-700 bg-yellow-100 border border-yellow-300 rounded">Warning: Dashboard generation resulted in empty content.</div>';
    }

    // 2. Write TSX to temporary file
    await fs.writeFile(tempTsxFilePath, finalTsxFragment, 'utf-8');
    console.log(`API (GET): Wrote TSX to ${tempTsxFilePath}`);

    // 3. Write minimal Tailwind input CSS to temporary file
    const tailwindInputCss = '@tailwind base;\n@tailwind components;\n@tailwind utilities;';
    await fs.writeFile(tempInputCssPath, tailwindInputCss, 'utf-8');
    console.log(`API (GET): Wrote input CSS to ${tempInputCssPath}`);

    // 4. Execute Tailwind CLI
    const tailwindArgs = [
        'tailwindcss',
        '-c', './tailwind.config.mjs', // Relative to dashboardDir
        '-i', `./temp/${path.basename(tempInputCssPath)}`, // Relative to dashboardDir
        '-o', `./temp/${path.basename(tempOutputCssPath)}`, // Relative to dashboardDir
        '--content', `./temp/${path.basename(tempTsxFilePath)}` // Relative to dashboardDir
    ];
    console.log(`API (GET): Running Tailwind CLI...`);
    // Run tailwindcss from the dashboard directory where its config and node_modules are
    const tailwindResult = await runCommand('npx', tailwindArgs, dashboardDir);

    if (tailwindResult.code !== 0) {
        // Log Tailwind error but try to continue, maybe some CSS was generated
        console.error(`API (GET): Tailwind CLI failed (code ${tailwindResult.code}). Stderr: ${tailwindResult.stderr}`);
        // Decide if this should be a hard failure or not. Let's try to read CSS anyway.
        // throw new Error(`Tailwind CLI failed. Stderr: ${tailwindResult.stderr.substring(0, 500)}...`);
    } else {
        console.log(`API (GET): Tailwind CLI finished successfully.`);
    }

    // 5. Read generated CSS content
    let generatedCssContent = '';
    try {
        generatedCssContent = await fs.readFile(tempOutputCssPath, 'utf-8');
        console.log(`API (GET): Read ${generatedCssContent.length} bytes from ${tempOutputCssPath}`);
    } catch (readError: any) {
        // If Tailwind failed, the output file might not exist. Log and continue with empty CSS.
        console.error(`API (GET): Failed to read generated CSS file ${tempOutputCssPath}: ${readError.message}. Proceeding with empty CSS.`);
        generatedCssContent = '/* Tailwind CSS generation failed */';
    }

    // 7. Return JSON response
    return NextResponse.json({
        tsx: finalTsxFragment,
        css: generatedCssContent
    });

  } catch (error: any) {
    console.error("API (GET): Error in Dynamic Tailwind Build handler:", error);
    return NextResponse.json({ error: error.message || 'An unexpected server error occurred' }, { status: 500 });
  } finally {
      // 8. Clean up temporary files (fire and forget, errors logged)
      console.log("API (GET): Cleaning up temporary files...");
      Promise.all([
          fs.unlink(tempTsxFilePath).catch(e => console.error(`Cleanup error (tsx): ${e.message}`)),
          fs.unlink(tempInputCssPath).catch(e => console.error(`Cleanup error (input css): ${e.message}`)),
          fs.unlink(tempOutputCssPath).catch(e => console.error(`Cleanup error (output css): ${e.message}`))
      ]);
      // No need to remove tempDir itself on every request
  }
}
