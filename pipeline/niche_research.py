import csv
import json
import os
import sys
import argparse

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    print("Missing dependency. Run:  pip install google-genai", file=sys.stderr)
    sys.exit(1)

def _read_file_content(file_path: str) -> str:
    with open(file_path, "rb") as f:
        raw = f.read()
    if raw.startswith(b'\xff\xfe'):
        return raw.decode("utf-16le", errors="replace")
    elif raw.startswith(b'\xfe\xff'):
        return raw.decode("utf-16be", errors="replace")
    else:
        return raw.decode("utf-8", errors="replace")

def parse_csv_file(file_path: str) -> str:
    """Parses a Book Bolt or AMZScout CSV file and returns a concise text summary of trends to avoid token limits."""
    lines = []
    
    content = _read_file_content(file_path)
    from io import StringIO
    
    try:
        reader = csv.DictReader(StringIO(content), delimiter='\t')
        for row in reader:
            # Basic parsing tailored to AMZScout-style TSV or comma CSV.
            product_name = row.get('Product Name') or row.get('Title', 'Unknown')
            price = row.get('Price', 'N/A')
            reviews = row.get('# of Reviews') or row.get('Reviews', 'N/A')
            est_sales = row.get('Est. Sales') or row.get('Parent ASIN Est. Sales') or row.get('Sales', 'N/A')

            if product_name and product_name != 'Unknown' and not product_name.startswith('Please purchase'):
                lines.append(f"- Title: {product_name[:100]} | Price: {price} | Reviews: {reviews} | Est. Sales: {est_sales}")
    except Exception as e:
        # Fallback to comma if TSV parsing fails
        reader = csv.DictReader(StringIO(content), delimiter=',')
        for row in reader:
            product_name = row.get('Product Name') or row.get('Title', 'Unknown')
            if product_name and product_name != 'Unknown' and not product_name.startswith('Please purchase'):
                lines.append(f"- Title: {product_name[:100]}")
    return "\n".join(lines[:50]) # Use top 50 products

def analyze_niche(csv_data: str, base_niche: str) -> dict:
    """Sends the data to Gemini and returns 3 sub-niche suggestions."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
I am building a KDP (Amazon Kindle Direct Publishing) coloring book business.
Below is the search and competition data downloaded for the niche/topic: "{base_niche}".

Data highlights:
{csv_data}

Analyze these current trends and suggest 3 UNTAPPED SUB-NICHES for adult coloring books in this space.
The goal is low competition but high demand. Focus exclusively on coloring books.

Return exactly a JSON array of 3 objects, where each object has:
- "title": A catchy title for the sub-niche book
- "description": A 2-sentence summary of the concept
- "target_audience": Who is it for
- "why_it_works": Why this is a good sub-niche based on the data

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

def run(csv_path: str, base_niche: str):
    data = parse_csv_file(csv_path)
    res = analyze_niche(data, base_niche)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze niche trends using Gemini")
    parser.add_argument("--csv", required=True, help="Path to BookBolt or AMZScout CSV file")
    parser.add_argument("--niche", required=True, help="Base niche or search query (e.g. 'nostalgic anime')")
    
    args = parser.parse_args()
    try:
        run(args.csv, args.niche)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
