# pipeline/refine_prompt.py
"""
Subprocess script: given a current image prompt and user feedback,
ask Gemini to return a refined prompt and a human-readable list of changes.

Usage (called by dashboard/app.py as a subprocess):
    python3 pipeline/refine_prompt.py --prompt "..." --feedback "..."

Stdout: JSON  {"refined_prompt": "...", "changes": ["...", "..."]}
Exit 0 = success, Exit 1 = error (JSON with "error" key).
"""
import argparse
import json
import os
import sys

try:
    from google import genai
    from google.genai import types
except ImportError:
    print(json.dumps({"error": "Missing dependency: pip install google-genai"}))
    sys.exit(1)


def run(current_prompt: str, feedback: str) -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(json.dumps({"error": "GEMINI_API_KEY missing"}))
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    system_prompt = (
        "You are an expert KDP coloring book and children's storybook image prompt engineer.\n"
        "Your job is to refine an existing image generation prompt based on user feedback.\n\n"
        "RULES:\n"
        "- Never mention specific colors or dark fills in the refined prompt.\n"
        "- If the original prompt contains 'PURE BLACK AND WHITE', preserve that instruction.\n"
        "- Keep the refined prompt concise and actionable (under 400 words).\n"
        "- List each change you made in plain English (3-8 words each).\n\n"
        "OUTPUT: Return ONLY valid JSON with this exact shape:\n"
        '{"refined_prompt": "...", "changes": ["Change description 1", "Change description 2"]}'
    )

    user_message = (
        f"Current prompt:\n{current_prompt}\n\n"
        f"User feedback:\n{feedback}"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
            ),
        )
        print(response.text)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, help="Current image prompt")
    parser.add_argument("--feedback", required=True, help="User feedback text")
    args = parser.parse_args()
    run(current_prompt=args.prompt, feedback=args.feedback)
