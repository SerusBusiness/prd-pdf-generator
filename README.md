# PRD Generator

A Python tool that generates Product Requirement Documents (PRDs) from simple text file inputs using Ollama's LLM capabilities.

## Features

- Generate comprehensive PRDs from simple text inputs
- Use local LLM models via Ollama for privacy and flexibility
- Include automatically generated diagrams using Mermaid syntax
- Add relevant images for concept visualization
- Search for and include reference links to related resources
- Output polished PDF documents with proper formatting
- Automatic timestamp-based unique filenames for generated documents
- "Powered by AI" footer on all PDF pages

## Requirements

- Python 3.8+
- Ollama running locally with a supported model (default: llama3)
- Optional: Mermaid diagram conversion microservice for improved diagram rendering

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/prd-generator.git
cd prd-generator
```

2. Install the package:
```bash
pip install -e . 
```

3. Configure environment variables:
```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file with your configurations
```

## JSON Structure

The PRD generator produces and consumes JSON with the following structure:

```json
{
  "Executive Summary": {
    "content": "Brief overview of the product and its purpose."
  },
  "Problem Statement": {
    "content": "Clear description of the problem being solved."
  },
  "Target Users": {
    "content": [
      "User type one",
      "User type two",
      "User type three"
    ]
  },
  "Product Goals": {
    "content": [
      "Goal one",
      "Goal two",
      "Goal three"
    ]
  },
  "Requirements & Features": {
    "content": [
      "Feature one with description",
      "Feature two with description",
      "Feature three with description"
    ]
  },
  "User Stories": {
    "content": [
      "As a [user type], I want to [action] so that [benefit]",
      "As a [user type], I want to [action] so that [benefit]"
    ]
  },
  "Technical Requirements": {
    "content": [
      "Technical requirement one",
      "Technical requirement two"
    ]
  },
  "Architecture": {
    "content": [
      "Architecture component one",
      "Architecture component two"
    ],
    "diagrams": [
      {
        "title": "System Architecture",
        "type": "flowchart",
        "mermaid_code": "graph TD\nA[Component A] --> B[Component B]\nB --> C[Component C]"
      }
    ]
  },
  "Implementation Plan": {
    "content": [
      "Phase 1: Description and timeline",
      "Phase 2: Description and timeline" 
    ]
  },
  "Success Metrics": {
    "content": [
      "Metric one",
      "Metric two" 
    ]
  },
  "Risks & Mitigation": {
    "content": [
      "Risk one: Mitigation strategy",
      "Risk two: Mitigation strategy"
    ]
  },
  "References": {
    "content": [
      "Reference one",
      "Reference two"
    ],
    "search_terms": ["term one", "term two", "term three"]
  },
  "image_suggestions": [
    "Description of image one",
    "Description of image two"
  ]
}
```

### JSON Structure Notes

- **Section Content Types**: Content for each section can be either:
  - A string (direct text content)
  - An object with a `content` key (which can be a string or array)
  - For list-type content, an array of strings is used

- **Special Fields**:
  - `diagrams`: Array of diagram objects with title, type, and mermaid_code
  - `search_terms`: Array of terms used for reference search
  - `image_suggestions`: Array of descriptions for images to generate

- **Diagram Types**:
  - `flowchart`: For system flows and processes
  - `sequence`: For time-based interaction sequences
  - `class`: For class/component relationships
  - `gantt`: For project timelines
  - Others supported by Mermaid syntax

- **Content Normalization**: The system automatically normalizes content from different formats:
  - Arrays are converted to bullet points in the final PDF
  - Dictionary content with nested structure is properly extracted
  - Proper formatting is maintained throughout the PDF generation process

### Storing and Debugging PRD Content

PRD content is automatically saved to the `data/debug/` directory with timestamped filenames for debugging purposes:

- `prd_content_[timestamp].json`: The parsed PRD content
- `raw_response_[timestamp].txt`: The raw response from the LLM

These files can be used for debugging issues with the PRD generation process.

## Usage

### Basic usage

```bash
# Generate a PRD from the default input file
prd-gen

# Generate a PRD from a specific input file
prd-gen -i your_input.txt -o your_output.pdf

# Generate a PRD from direct text input
prd-gen -p "Your project description here"

# Use a specific Ollama model
prd-gen -m llama3:13b -i your_input.txt
```

### Configuration

You can customize the generator behavior with these options:

```bash
# Disable reference search
prd-gen --no-search

# Disable image generation
prd-gen --no-images

# Disable diagram generation
prd-gen --no-diagrams
```

## Environment Variables

The following environment variables can be used to customize behavior (see `.env.example`):

- `OLLAMA_HOST`: URL to Ollama API (default: http://localhost:11434)
- `OLLAMA_MODEL`: Default model to use (default: llama3)
- `PIXABAY_API_KEY`: API key for image generation via Pixabay
- `GOOGLE_PSE_CX`: Google Programmable Search Engine custom search engine ID
- `GOOGLE_PSE_API_KEY`: Google API key for PSE
- `ENABLE_SEARCH`: Enable/disable reference search functionality (true/false)
- `GENERATE_IMAGES`: Enable/disable image generation (true/false)
- `GENERATE_DIAGRAMS`: Enable/disable diagram generation (true/false)
- `MERMAID_SERVICE_URL`: URL for the Mermaid diagram conversion service

## Setting Up Google Programmable Search Engine

The PRD Generator can use Google's Programmable Search Engine (PSE) for finding relevant references. Here's how to set it up:

1. **Create a Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable billing (required for API access, but you get 100 free searches per day)

2. **Enable the Custom Search API**:
   - Go to [API Library](https://console.cloud.google.com/apis/library)
   - Search for "Custom Search API"
   - Click "Enable"

3. **Create an API Key**:
   - Go to [Credentials](https://console.cloud.google.com/apis/credentials)
   - Click "Create Credentials" and select "API Key"
   - Copy the generated key
   - Set it as your `GOOGLE_PSE_API_KEY` in the `.env` file

4. **Create a Programmable Search Engine**:
   - Go to [Programmable Search Engine Control Panel](https://programmablesearchengine.google.com/)
   - Click "Add" to create a new search engine
   - Choose "Search the entire web" or specify sites to search
   - Give your search engine a name and click "Create"

5. **Get Your Search Engine ID**:
   - On your search engine's dashboard, click "Customize"
   - Find your "Search engine ID" (it looks like: `012345678901234567890:abcdefghijk`)
   - Set it as your `GOOGLE_PSE_CX` in the `.env` file

6. **Customize your search engine** (optional):
   - You can refine your search engine to focus on specific sites
   - Exclude sites you don't want in your PRD references
   - Add search features like image search, autocomplete, etc.

7. **Test Your Configuration**:
   - Run the PRD generator with search enabled
   - Check the console output for "Using Google Programmable Search Engine"
   - Verify that references are being correctly pulled into your PRD

### Note on Usage Limits

The free tier of Google's Custom Search API includes:
- 100 search queries per day
- Additional queries are billed at $5 per 1000 queries

For most PRD generation use cases, the free tier should be sufficient.

## Example

```bash
# Store your project idea in a text file
echo "Create a mobile app for tracking personal carbon emissions" > prompt.txt

# Generate a PRD
prd-gen -i prompt.txt -o carbon_app_prd.pdf
```

## Project Structure

- `prd_generator/`: Main package
  - `main.py`: CLI entry point
  - `prd_processor.py`: Core PRD generation logic
  - `config.py`: Configuration settings
  - `utils/`: Utility modules
    - `ollama_client.py`: Client for Ollama API
    - `pdf_generator.py`: PDF document generation
    - `diagram_generator.py`: Mermaid diagram generation
    - `image_generator.py`: Image generation
    - `reference_search.py`: Web search for references

## Output Details

When generating a PRD, the system automatically:

- Creates a timestamp-based unique filename (e.g., `prd_document_20250423_185142.pdf`) when no output file is specified
- Adds a professional "Powered by AI" footer to each page
- Includes the generation timestamp in the footer for version tracking

## License

MIT