import json
import sys
import os # Added for path operations
import subprocess # Added for running ESLint
from typing import List, Dict, Any, Optional
import logging # Added for better logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)

# --- OpenAI Client Setup (Assuming environment variables are set) ---
try:
    from openai import OpenAI
    # Expects OPENAI_API_KEY environment variable to be set
    openai_client = OpenAI()
    logging.info("OpenAI client initialized successfully.")
except ImportError:
    logging.warning("OpenAI SDK not found. LLM correction loop will be disabled.")
    openai_client = None
except Exception as e:
    logging.error(f"Failed to initialize OpenAI client: {e}. LLM correction loop will be disabled.")
    openai_client = None
# --- End OpenAI Client Setup ---


# Import Agent SDK and Pydantic models if available, otherwise define dummies
try:
    from agents import function_tool
    # Attempt to import relevant Pydantic models from stonk_research_agent for type hinting
    # Adjust path as necessary based on your project structure
    # sys.path.append('../../') # Add parent directory if needed - Assuming it's handled by PYTHONPATH or project structure
    from stonk_research_agent.tools import WebSearchNewsArticle, HttpUrl
    from pydantic import BaseModel, Field, ValidationError
    logging.info("Successfully imported agents SDK and Pydantic models.")

except ImportError as e:
    logging.warning(f"Failed to import agents SDK or Pydantic models: {e}. Using placeholders.")
    # Define dummy decorator and models if import fails
    def function_tool(func=None, **kwargs): return func if func else lambda f: f
    class BaseModel: pass
    class Field: pass
    class HttpUrl: pass
    ValidationError = Exception
    class WebSearchNewsArticle(BaseModel):
        headline: Optional[str] = None
        source_name: Optional[str] = None
        source_url: Optional[str] = None # Keep as str for simplicity here
        summary: Optional[str] = None
        publish_date: Optional[str] = None
        reason: Optional[str] = None
        transcript: Optional[str] = None
        sentiment_score: Optional[float] = None

# --- Helper Function for TSX Generation ---

def _generate_single_news_box_tsx(article: WebSearchNewsArticle, index: int) -> str:
    """Generates TSX for a single news article box."""

    # Basic escaping for strings embedded in TSX (replace quotes, backticks, newlines)
    def escape_tsx(text: Optional[str]) -> str:
        if text is None:
            return 'null' # Return JS null for None
        # More robust escaping for embedding within JS strings in TSX
        escaped = text.replace('\\', '\\\\') # Escape backslashes first
        escaped = escaped.replace('"', '\\"')  # Escape double quotes
        escaped = escaped.replace('\n', '\\n') # Escape newlines
        escaped = escaped.replace('\r', '\\r') # Escape carriage returns
        escaped = escaped.replace('\t', '\\t') # Escape tabs
        escaped = escaped.replace('`', '\\`')  # Escape backticks
        # Escape script tags to prevent XSS if summary/etc could contain them
        escaped = escaped.replace('<script', '<\\script') # Use HTML entity for less than sign
        return f'"{escaped}"' # Enclose in double quotes for JS string literal

    # Sentiment color logic - simplified for direct use in template
    sentiment_color_class = "text-gray-500 dark:text-gray-400"
    sentiment_prefix = ""
    if article.sentiment_score is not None:
        if article.sentiment_score > 0:
            sentiment_color_class = "text-green-600 dark:text-green-400"
            sentiment_prefix = "+"
        elif article.sentiment_score < 0:
            sentiment_color_class = "text-red-600 dark:text-red-400"

    sentiment_display = "N/A"
    if article.sentiment_score is not None:
        sentiment_display = f"{sentiment_prefix}{article.sentiment_score:.1f}"

    publish_date_display = "No Date"
    if article.publish_date:
        # Using template literal for safety, assuming date format is ISO-like
        # TEMPORARY SIMPLIFICATION FOR DEBUGGING:
        # js_date_code = f'`${{new Date({escape_tsx(article.publish_date)}).toLocaleDateString()}}`'
        # publish_date_display = f'{{{js_date_code}}}'
        # Just display the raw (escaped) date string
        publish_date_display = f'{{{escape_tsx(article.publish_date)}}}'

    # --- Simplified Conditional Rendering ---
    reason_tsx = ''
    if article.reason:
        # Using template literal for potentially longer/complex reasons
        reason_tsx = f'<p className="text-sm italic text-gray-600 dark:text-gray-300">{{`{escape_tsx(article.reason)}`}}</p>'

    transcript_tsx = ''
    if article.transcript:
        transcript_tsx = f'''<div className="text-sm text-gray-700 dark:text-gray-300 border-l-2 border-gray-200 dark:border-gray-600 pl-2 my-2 max-h-32 overflow-y-auto flex-grow">
  <p className="whitespace-pre-wrap">{{`{escape_tsx(article.transcript)}`}}</p>
</div>'''

    link_tsx = ''
    if article.source_url:
        # Use json.dumps for proper HTML attribute quoting of the URL
        href_attr = json.dumps(article.source_url)
        link_tsx = f'<a href={href_attr} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 self-end mt-1">Read More</a>'
    # --- End Simplified Conditional Rendering ---


    # Placeholder for image URL - assuming article might have it in the future
    image_url = getattr(article, 'image_url', None) # Safely check for an image_url attribute
    logging.info(f"Article headline: {article.headline}, Image URL: {image_url}") # Log image_url
    image_tsx = ''
    if image_url:
        image_tsx = f'<img src={{{escape_tsx(image_url)}}} alt={{`{escape_tsx(article.headline)}`}} className="w-full h-32 object-cover rounded-t-lg mb-3" />'
    else:
        # Placeholder image or icon if no image_url
        image_tsx = f'<div className="w-full h-32 bg-gray-200 dark:bg-gray-700 flex items-center justify-center rounded-t-lg mb-3"><svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg></div>'


    # Use template literals in TSX for embedded strings for better handling of quotes/newlines
    # Enhanced styling: Added shadow-lg, rounded-xl, better spacing, flex-grow for content
    return f"""
<div key={{{index}}} className="border border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-800 shadow-lg overflow-hidden flex flex-col h-full transition-shadow hover:shadow-xl">
  {image_tsx}
  <div className="p-4 flex flex-col flex-grow space-y-3">
    <h3 className="font-bold text-lg text-gray-900 dark:text-white leading-tight">{{`{escape_tsx(article.headline) if article.headline else '"No Headline"'}`}}</h3>
    <div className="text-xs text-gray-500 dark:text-gray-400">
      <span>{{`{escape_tsx(article.source_name) if article.source_name else '"Unknown Source"'}`}}</span>
      <span className="mx-1">|</span>
      <span>{publish_date_display}</span>
    </div>
    {reason_tsx}
    {transcript_tsx}
    <div className="mt-auto pt-3 flex justify-between items-center">
      <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
        Sentiment: <span className="{sentiment_color_class} font-semibold">{sentiment_display}</span>
      </span>
      {link_tsx}
    </div>
  </div>
</div>
"""

# --- ESLint Validation and Correction Logic ---

def _validate_and_correct_tsx(tsx_code: str, max_retries: int = 2) -> str:
    """
    Validates TSX code using ESLint and attempts corrections using an LLM.

    Args:
        tsx_code (str): The TSX code string to validate.
        max_retries (int): Maximum number of correction attempts.

    Returns:
        str: The validated (and potentially corrected) TSX code, or the original
             code if validation passes or correction fails repeatedly.
             Returns an error TSX string if validation fails definitively.
    """
    if not openai_client:
        logging.warning("OpenAI client not available. Skipping TSX validation and correction loop.")
        return tsx_code # Skip validation if LLM correction isn't possible

    current_tsx = tsx_code
    lint_error_tsx = '<p className="text-red-500">TSX validation failed after multiple attempts. Check backend logs.</p>'

    # Define paths relative to the project root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    dashboard_dir = os.path.join(project_root, 'dashboard')
    # Create temp dir *inside* dashboard
    temp_dir = os.path.join(dashboard_dir, 'temp')
    temp_tsx_path = os.path.join(temp_dir, 'lint_check.tsx')
    # Path to temp file relative to dashboard_dir
    temp_tsx_rel_to_dashboard = os.path.join('temp', 'lint_check.tsx')

    os.makedirs(temp_dir, exist_ok=True) # Ensure temp dir exists inside dashboard

    for attempt in range(max_retries + 1):
        logging.info(f"TSX Validation Attempt {attempt + 1}/{max_retries + 1}")

        # 1. Write code to temp file
        try:
            with open(temp_tsx_path, 'w', encoding='utf-8') as f:
                # Wrap the fragment in a basic functional component for better linting context
                f.write(f"""
import React from 'react';

const GeneratedContent = () => {{
  return (
    <>
      {current_tsx}
    </>
  );
}};

export default GeneratedContent;
""")
            logging.info(f"Wrote TSX to temporary file: {temp_tsx_path}")
        except IOError as e:
            logging.error(f"Failed to write temporary TSX file: {e}")
            return lint_error_tsx # Cannot proceed

        # 2. Run ESLint via npm script (next lint)
        # Use '--' to pass arguments to the underlying eslint command
        # Using npx eslint directly instead of npm run lint (next lint)
        eslint_command = [
            'npx', 'eslint',
            '--format', 'json',
            '--config', 'temp/temp_eslint.config.js', # Use the new temporary ESLint config
            '--fix', # Standard ESLint option to auto-fix problems
            temp_tsx_rel_to_dashboard # Target the specific temp file (e.g., temp/lint_check.tsx)
        ]
        logging.info(f"Running ESLint command directly in '{dashboard_dir}' with temp config: {' '.join(eslint_command)}")

        try:
            # Execute from the dashboard directory
            process = subprocess.run(
                eslint_command,
                cwd=dashboard_dir, # Explicitly set the working directory
                capture_output=True,
                text=True,
                check=False, # Don't raise exception on non-zero exit
                encoding='utf-8'
            )
            logging.info(f"ESLint finished with code {process.returncode}")
            # Log stderr for debugging ESLint itself
            if process.stderr:
                logging.warning(f"ESLint stderr:\n{process.stderr}")

        except FileNotFoundError:
            logging.error("ESLint command (npx eslint) not found. Make sure Node.js and npm/npx are installed and in PATH.")
            return '<p className="text-red-500">ESLint execution failed (command not found). Check backend setup.</p>'
        except Exception as e:
            logging.error(f"ESLint execution failed: {e}")
            return '<p className="text-red-500">ESLint execution failed. Check backend logs.</p>'

        # 3. Parse ESLint output
        eslint_results = None
        try:
            # ESLint outputs JSON array, even for one file
            output_json = json.loads(process.stdout)
            if output_json and isinstance(output_json, list):
                eslint_results = output_json[0] # Get results for the first (only) file
            else:
                 logging.warning(f"Unexpected ESLint JSON output format: {process.stdout}")

        except json.JSONDecodeError:
            logging.error(f"Failed to parse ESLint JSON output:\n{process.stdout}")
            # If ESLint failed badly (e.g., config error), stdout might not be JSON
            if attempt >= max_retries:
                 return lint_error_tsx
            else:
                 # Maybe the code is *so* broken ESLint crashed? Try correcting anyway?
                 # Or assume ESLint setup error and bail? Let's bail for now.
                 return '<p className="text-red-500">Failed to parse ESLint output. Check backend logs.</p>'

        # 4. Check for errors and attempt correction
        if eslint_results and eslint_results.get('errorCount', 0) > 0:
            logging.warning(f"ESLint found {eslint_results['errorCount']} errors.")
            if attempt >= max_retries:
                logging.error("Max correction retries reached. Validation failed.")
                return lint_error_tsx # Failed after retries

            # Prepare error messages for LLM
            error_messages = [f"- {msg['message']} (Line: {msg.get('line', 'N/A')}, Col: {msg.get('column', 'N/A')}, Rule: {msg.get('ruleId', 'N/A')})"
                              for msg in eslint_results.get('messages', []) if msg.get('severity') == 2] # Severity 2 is error

            if not error_messages:
                 logging.warning("ESLint reported errors but no specific error messages found in JSON.")
                 # Hard to correct without messages, maybe retry or give up? Give up for now.
                 return lint_error_tsx

            # Construct parts separately to avoid f-string expression issues with backslashes
            errors_str = '\n'.join(error_messages)
            tsx_str = current_tsx

            # Use regular string formatting/concatenation for the prompt
            correction_prompt = (
                "The following TSX code fragment failed ESLint validation. "
                "Please fix the errors and return ONLY the corrected TSX code fragment "
                "(inside the ```tsx block), without any explanations. Ensure the output is "
                "valid TSX suitable for direct rendering within a React component.\n\n"
                "ESLint Errors:\n"
                "```\n"
                f"{errors_str}\n"  # Use the pre-constructed string
                "```\n\n"
                "Original TSX Code Fragment:\n"
                "```tsx\n"
                f"{tsx_str}\n"    # Use the pre-constructed string
                "```\n\n"
                "Corrected TSX Code Fragment:\n"
                "```tsx\n"
            )
            # End of prompt construction

            logging.info("Attempting LLM correction...")
            try:
                # Ensure you have the OpenAI client initialized
                if not openai_client:
                    logging.error("OpenAI client not available for correction.")
                    return lint_error_tsx

                chat_completion = openai_client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": correction_prompt,
                        }
                    ],
                    model="gpt-4o", # Or your preferred model
                    temperature=0.2, # Lower temperature for more deterministic fixes
                )
                corrected_tsx_raw = chat_completion.choices[0].message.content

                # Extract code block - simple extraction assuming ```tsx ... ```
                if corrected_tsx_raw:
                     start = corrected_tsx_raw.find('```tsx')
                     end = corrected_tsx_raw.rfind('```')
                     if start != -1 and end != -1 and start < end:
                          corrected_tsx = corrected_tsx_raw[start + 6:end].strip()
                          if corrected_tsx: # Check if not empty after stripping
                               logging.info("Received corrected TSX from LLM.")
                               current_tsx = corrected_tsx
                               continue # Go to next validation attempt with corrected code
                          else:
                               logging.warning("LLM returned empty code block.")
                     else:
                          logging.warning("Could not extract corrected code block from LLM response.")
                else:
                     logging.warning("LLM response was empty.")

                # If correction failed or wasn't extracted, proceed to next attempt or fail
                logging.warning("LLM correction did not yield usable code. Proceeding without correction for this attempt.")


            except Exception as e:
                logging.error(f"LLM correction call failed: {e}")
                # Don't retry LLM failure, just proceed to next validation attempt or fail
        else:
            # No errors found or ESLint output parsing failed without errors
            if eslint_results and eslint_results.get('errorCount', 0) == 0:
                 logging.info("ESLint validation passed.")
                 return current_tsx # Success!
            else:
                 # Handle cases where ESLint might have run but didn't report errors correctly
                 logging.warning("ESLint ran but did not report errors clearly, or parsing failed. Assuming success with caution.")
                 return current_tsx


    # Should not be reached if loop breaks on success or returns error on failure
    logging.error("Validation loop finished unexpectedly.")
    return lint_error_tsx


# --- Tool Logic (Undecorated) ---

def _generate_news_display_code_logic(research_data_json: str) -> str:
    """
    Generates and validates Next.js TSX code to display relevant news articles
    based on input JSON data. Attempts to correct linting errors using an LLM.
    The input JSON should contain a 'relevant_news' list following the WebSearchNewsArticle schema.

    Args:
        research_data_json (str): A JSON string containing the research data.

    Returns:
        str: A string containing validated TSX code for rendering the news boxes,
             or an error message string if processing/validation fails.
    """
    logging.info("Entering generate_news_display_code")
    try:
        # --- (Parsing logic remains the same as before) ---
        research_data = json.loads(research_data_json)
        logging.info("Parsed research_data_json")

        news_list_raw: Optional[List[Dict[str, Any]]] = None
        # Try extracting from common structures, including the correct nested path
        if 'relevant_news' in research_data: # Top level
             news_list_raw = research_data.get('relevant_news')
        elif 'web_search' in research_data and 'relevant_news' in research_data['web_search']: # Nested under 'web_search' at top level
             news_list_raw = research_data['web_search'].get('relevant_news')
        elif 'report' in research_data and isinstance(research_data.get('report'), list) and research_data['report']: # NEW: Check report LIST
             logging.info("Attempting to extract news from 'report' list structure.") # ADDED LOG
             # Access the first item in the report list
             report_item = research_data['report'][0]
             logging.info(f"Report item type: {type(report_item)}") # ADDED LOG
             if isinstance(report_item, dict) and 'web_search' in report_item: # Check if web_search key exists
                  logging.info("'web_search' key found in report_item.") # ADDED LOG
                  web_search_data = report_item.get('web_search')
                  logging.info(f"web_search_data type: {type(web_search_data)}") # ADDED LOG
                  if isinstance(web_search_data, dict):
                      news_list_raw = web_search_data.get('relevant_news')
                      logging.info(f"Extracted news_list_raw (type: {type(news_list_raw)}) from report structure.") # ADDED LOG
                  else:
                      logging.warning("'web_search' data in report_item is not a dictionary.") # ADDED LOG
             else:
                 logging.warning("'web_search' key not found in report_item or report_item is not a dict.") # ADDED LOG
        elif isinstance(research_data, list) and research_data: # Handle if input is just the list
             logging.info("Input data is a list, attempting to treat it as the news list directly.") # ADDED LOG
             # Basic check if list items look like news articles
             if isinstance(research_data[0], dict) and ('headline' in research_data[0] or 'source_url' in research_data[0]):
                  news_list_raw = research_data # Assume the list itself is the news list


        if not news_list_raw or not isinstance(news_list_raw, list):
            logging.warning("'relevant_news' not found or not a list in input JSON.")
            return '<p className="text-gray-500">No relevant news articles found in input data.</p>';

        logging.info(f"Found {len(news_list_raw)} raw news items.")

        news_articles: List[WebSearchNewsArticle] = []
        for i, item_raw in enumerate(news_list_raw):
            try:
                if not isinstance(item_raw, dict):
                    logging.warning(f"Skipping news item {i} as it is not a dictionary.")
                    continue
                article = WebSearchNewsArticle(**item_raw)
                news_articles.append(article)
            except ValidationError as e:
                 logging.warning(f"Skipping news item {i} due to validation error: {e}")
            except TypeError as e:
                 logging.warning(f"Skipping news item {i} due to type error during validation: {e}")

        if not news_articles:
            logging.warning("No valid news articles after validation.")
            return '<p className="text-gray-500">No valid news articles to display.</p>';

        logging.info(f"Generating initial TSX for {len(news_articles)} validated news articles.")
        tsx_boxes = [_generate_single_news_box_tsx(article, i) for i, article in enumerate(news_articles)]

        # Combine into a grid structure
        initial_tsx = f"""
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {''.join(tsx_boxes)}
</div>
"""
        initial_tsx = initial_tsx.strip()
        logging.info("Finished generating initial TSX code. Proceeding to validation.")

        # --- Validation Step Re-enabled ---
        validated_tsx = _validate_and_correct_tsx(initial_tsx)
        # --- End Validation Step Re-enabled ---

        logging.info("Finished generate_news_display_code (validation attempted)")
        return validated_tsx # Return the validated (or original if validation failed internally) TSX

    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse input JSON: {e}")
        return f'<p className="text-red-500">Error: Could not parse input data.</p>'
    except Exception as e:
        logging.error(f"Unexpected error in generate_news_display_code: {e}", exc_info=True) # Log traceback
        return f'<p className="text-red-500">Error: Failed to generate news display code. Type: {type(e).__name__}</p>'

# --- Tool Definition (Decorated Wrapper) ---
@function_tool
def generate_news_display_code(research_data_json: str) -> str:
    """
    Generates and validates Next.js TSX code to display relevant news articles
    based on input JSON data. Attempts to correct linting errors using an LLM.
    This is a wrapper calling the main logic function.

    Args:
        research_data_json (str): A JSON string containing the research data.

    Returns:
        str: A string containing validated TSX code for rendering the news boxes,
             or an error message string if processing/validation fails.
    """
    # Call the actual logic function
    return _generate_news_display_code_logic(research_data_json)


# --- Old Tool (Keep for reference or remove if unused) ---
# from .agent import generate_dashboard as old_generate_dashboard

# try:
#     from openai import Tool # Assumes this is the SDK being used
# except ImportError:
#     print("WARN: openai package not found for old tool definition.", file=sys.stderr)
#     class Tool: # Dummy
#         @staticmethod
#         def from_function(**kwargs): return None

# old_dashboard_tool = Tool.from_function(
#     function=old_generate_dashboard,
#     name="OLD_generate_dashboard_build",
#     description="[DEPRECATED] Builds the dashboard using npm build.",
# ) if Tool else None
