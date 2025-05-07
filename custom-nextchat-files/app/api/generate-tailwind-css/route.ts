import { NextRequest, NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";
import { spawn } from "child_process";

// Helper function to execute a command
function runCommand(
  command: string,
  args: string[],
  cwd: string,
): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const process = spawn(command, args, { cwd });
    let stdout = "";
    let stderr = "";

    process.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    process.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    process.on("close", (code) => {
      if (code === 0) {
        resolve({ stdout, stderr });
      } else {
        reject(new Error(`Command failed with code ${code}: ${stderr}`));
      }
    });

    process.on("error", (err) => {
      reject(err);
    });
  });
}

export async function POST(request: NextRequest) {
  const uniqueId = Date.now().toString();
  const nextChatRoot = process.cwd(); // Assumes API route runs from NextChat project root

  const tempTsxFilename = `temp-ui-${uniqueId}.tsx`;
  const tempInputCssFilename = `temp-input-${uniqueId}.css`;
  const tempOutputCssFilename = `temp-output-${uniqueId}.css`;

  // These paths are relative to nextChatRoot for the tailwindcss command
  const tempTsxPath = path.join(nextChatRoot, tempTsxFilename);
  const tempInputCssPath = path.join(nextChatRoot, tempInputCssFilename);
  const tempOutputCssPath = path.join(nextChatRoot, tempOutputCssFilename);

  const tailwindConfigPath = "./tailwind.config.mjs"; // Relative to nextChatRoot

  try {
    const body = await request.json();
    const tsxString = body.tsxString;

    if (!tsxString || typeof tsxString !== "string") {
      return NextResponse.json(
        { error: "Missing or invalid tsxString in request body" },
        { status: 400 },
      );
    }

    // 1. Write TSX to a temporary file
    await fs.writeFile(tempTsxPath, tsxString);

    // 2. Create a temporary input CSS file
    const cssInputContent =
      "@tailwind base;\n@tailwind components;\n@tailwind utilities;";
    await fs.writeFile(tempInputCssPath, cssInputContent);

    // 3. Execute the tailwindcss CLI command
    // Command: npx tailwindcss -c <config> -i <input_css> -o <output_css> --content <content_to_scan>
    const args = [
      "tailwindcss",
      "-c",
      tailwindConfigPath,
      "-i",
      tempInputCssFilename, // Use relative path for the command
      "-o",
      tempOutputCssFilename, // Use relative path for the command
      "--content",
      tempTsxFilename, // Use relative path for the command
    ];

    // console.log(`Executing command: npx ${args.join(' ')} in ${nextChatRoot}`);
    await runCommand("npx", args, nextChatRoot);

    // 4. Read the generated CSS from the temporary output file
    const generatedCss = await fs.readFile(tempOutputCssPath, "utf-8");

    return NextResponse.json({ css: generatedCss }, { status: 200 });
  } catch (error: any) {
    console.error("Error generating Tailwind CSS:", error);
    return NextResponse.json(
      { error: "Failed to generate Tailwind CSS", details: error.message },
      { status: 500 },
    );
  } finally {
    // 5. Clean up all temporary files
    try {
      await fs.unlink(tempTsxPath).catch(() => {}); // Ignore errors if file doesn't exist
      await fs.unlink(tempInputCssPath).catch(() => {});
      await fs.unlink(tempOutputCssPath).catch(() => {});
    } catch (cleanupError) {
      console.error("Error cleaning up temporary files:", cleanupError);
    }
  }
}
