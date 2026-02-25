# Taxonomy Engine

An AI-powered system that automatically extracts concepts from PDF standards documents and intelligently integrates them into existing taxonomy trees.

# Getting Started

### External dependencies

Since this application is Dockerized, the only external dependencies for normal execution are [Docker](https://docs.docker.com/engine/install/) and [Ollama](https://ollama.com/download/windows).

### Run with Make

Start the application, build the Docker image, and run tests quickly using commands from the [Makefile](Makefile). Run the following from the project root to start the application:

```bash
make up
```

To discover other available commands:

```bash
make help
```

### Run with Docker Compose

If you're more familiar with the [Docker CLI](https://docs.docker.com/reference/cli/docker/), the same functionality is exposed via [docker-compose.yml](docker-compose.yml). To run the application (and build the image if necessary):

```bash
docker compose up
```

# Development

See [DEV.md](DEV.md) for development setup instructions and technical details.
