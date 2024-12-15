# X-Faktor

An AI-powered video generation system that creates an episode of Beyond Belief using OpenAI, ElevenLabs, and Luma AI.

## Features

- Text generation using GPT-4
- Image generation
- Video generation using Luma AI
- Voice synthesis using ElevenLabs
- Automated episode creation from JSON templates

## Prerequisites

- Python 3.8+
- Poetry for dependency management
- API keys for:
  - OpenAI
  - ElevenLabs
  - Luma AI

## Setup

1. Clone the repository
```bash
git clone https://github.com/yourusername/x-faktor.git
cd x-faktor
```

2. Install dependencies using Poetry
```bash
poetry install
```

3. Create a `.env` file with your API keys
```
OPENAI_API_KEY=
ELEVENLABS_API_KEY=
REPLICATE_API_TOKEN=
LUMAAI_API_KEY=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_ACCOUNT_ID=
R2_BUCKET_PUB_ID=
```

## Usage

1. Run the Jupyter notebook.

2. Run the render script:
```bash
poetry run python renderer.py
```

The system will generate video. Enjoy!
