# slacky

A lightweight AI slackbot with built-in tool support and thread memory.

## Features
- Thread-aware conversation memory
- Powered by PydanticAI for robust agent interactions
- FastAPI backend for Slack events
- Background task processing with Prefect
- Comprehensive logging system
- File-based message caching
- Configurable via environment variables
- Development mode with hot reload

## Quick Start

1. Install dependencies:
```bash
make install
```

2. Set up your environment variables (see `.env.example`)

3. Run development server:
```bash
make dev
```

## Development

- `make dev` - Run the development server with hot reload
- `make lint` - Run code quality checks
- `make clean` - Clean up build artifacts and caches