# Dev notes and plans

# Getting started

### External dependencies

Since this application is Dockerized, the only external dependencies for normal execution are:
- [Docker](https://docs.docker.com/engine/install/)
- [Ollama](https://ollama.com/download/windows)

### Containerized execution

1. Get Ollama docker image and load the desired model (we recommend: mistral-small3.2)
2. Run Ollama container and attach to it on iteractive mode
    ```bash
    docker run -d --gpus=all --rm -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

    docker exec -it ollama /bin/bash
    ```
3. Run the model within Ollama container:
    ```bash
    ollama run mistral-small3.2
    ```
    Wait for the model to be loaded then exit (CTRL+d)
4. [From another terminal] Attach Ollama container to the docker environment
    ```bash
    docker network connect taxonomy-engine_default ollama
    ```
    make sure that ollama was correctly attached by using:
    ```bash
    docker inspect taxonomy-engine_default
    ```
    This is a one-time setup.
5. Check the `docker-compose.yaml` file

    Check that the ports are correct and that models match
6. Build the docker and run it
    ```bash
    make build
    make up
    ```

### Local Python environment

To add the required Python packages to a local Python interpreter, use [conda](https://www.anaconda.com/docs/getting-started/miniconda/main).

```bash
$ conda create -n taxonomy-engine python=3.12
$ conda activate taxonomy-engine
(taxonomy-engine) $ pip install -r requirements.txt
```

### Local, uncontainerized execution

For fast iteration, many components of the application may be run locally on your host machine without the need to build and run a Docker container.

# Architecture

### App-level

- App: FastAPI, input = user provided bullets/context ; output = JSON fields
- LLM: Ollama

### Orchestration

- Single Docker container + Ollama
- Python env: just pip install onto the container's default Python interpreter

### Functional details

- Logging: python logging package