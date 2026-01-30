# Prompt Testing

This folder contains test cases for AI prompts and their results.

## Structure

```
tests/prompts/
├── README.md
├── runner.py              # Run tests and save results
├── test_cases/            # Input test cases
│   ├── audio_*.txt        # Audio transcription samples
│   ├── conversation_*.txt # Conversation samples
│   └── profile_*.json     # Profile data samples
└── results/               # Output results (gitignored)
    └── YYYY-MM-DD_HH-MM/  # Timestamped results
```

## Running Tests

```bash
cd sphere-bot
python tests/prompts/runner.py

# Test specific prompt
python tests/prompts/runner.py --prompt audio_extraction

# Test with specific input file
python tests/prompts/runner.py --input tests/prompts/test_cases/audio_sample_ru.txt
```

## Adding Test Cases

1. Create a `.txt` or `.json` file in `test_cases/`
2. Name it descriptively: `audio_networking_ru.txt`, `profile_founder_en.json`
3. Run the test runner to see results

## Test Case Format

**Audio transcription (`.txt`):**
```
Привет! Меня зовут Саша, я занимаюсь продуктовым менеджментом...
```

**Conversation (`.json`):**
```json
{
  "messages": [
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello!"}
  ],
  "context": {"event_name": "TechConf"}
}
```

## Evaluating Results

Results are saved with:
- `input.txt` - Original input
- `output.json` - Extracted data
- `raw_response.txt` - Raw LLM response
- `metadata.json` - Timing, tokens, model info
