import os
import sys
import argparse
import json

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    print("Missing dependency. Run:  pip install google-genai", file=sys.stderr)
    sys.exit(1)

def generate_social_content(title: str, subtitle: str, description: str) -> dict:
    """Generates social media captions and ad keywords using Gemini."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
We are publishing a new adult coloring book on Amazon KDP.
Title: {title}
Subtitle: {subtitle}
Description:
{description}

Please provide:
1. 3 engaging Instagram/TikTok captions with emojis and hashtags.
2. 2 short, punchy tweets.
3. A list of 10 long-tail target keywords for an Amazon Ads campaign ($2/day budget).

Return exactly a JSON object:
{{
  "instagram": ["caption1", "caption2", "caption3"],
  "twitter": ["tweet1", "tweet2"],
  "ad_keywords": ["keyword1", "keyword2", ...]
}}

Provide only the JSON. No markdown formatting or backticks.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            temperature=0.7,
        ),
    )
    
    try:
        text = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(text)
        return data
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Gemini response as JSON: {response.text}") from e

def run(title: str, subtitle: str, description: str):
    res = generate_social_content(title, subtitle, description)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate social media marketing content")
    parser.add_argument("--title", required=True)
    parser.add_argument("--subtitle", required=True)
    parser.add_argument("--desc", required=True)
    
    args = parser.parse_args()
    try:
        run(args.title, args.subtitle, args.desc)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
