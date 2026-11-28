# Install Instructions - Error Monitoring AI Agent

## Step 1: Install Ollama & Pull Local Models

Install Ollama to host your models locally, then pull Google DeepMind’s Gemma 4 (or any preferred multimodal vision model, like LLaVA or MiniCPM).

1.	Install Ollama:
⚬	macOS / Linux: Download from ollama.com or run:

    ```bash
    brew install ollama
    ```
⚬	Windows: Download and run the setup installer from ollama.com.

2.	Pull the Local Gemma 4 & 2 Models:
Open your terminal and run:

    ```bash
    ollama pull gemma4
    ollama pull gemma2

    ```

## Step 2: Create a Python Virtual Environment

Keep your dependencies isolated by creating a clean virtual environment:

    ```bash
    # 1. Navigate to your project folder
    cd ai_app

    # 2. Create the virtual environment
    python3 -m venv venv

    # 3. Activate the virtual environment
    # macOS / Linux:
    source venv/bin/activate

    ```

## Step 3: Install dependencies

    ```text
    fastapi>=0.115.5
    uvicorn>=0.32.1
    pydantic>=2.10.0
    langgraph>=0.2.0
    ollama>=0.4.0
    playwright>=1.49.0
    ```

    ```bash
    pip install -r requirements.txt
    ```
## Step 4: Run Open WebUI in Docker Container

    ```bash
    docker run -d --name open-webui \
    -p 3000:8080 \
    --add-host=host.docker.internal:host-gateway \
    -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
    -e OPENAI_API_BASE_URL=http://host.docker.internal:8000/v1 \
    -e OPENAI_API_KEY=local-no-key-needed \
    -v open-webui:/app/backend/data \
    ghcr.io/open-webui/open-webui:main

    ```

## Step 5: Source documents pip 

    Copy Python scripts from the GitHub repositoey

## Step 6: Run Sample web application

    Run error_demo_app.py  from the commandline

## Step 7: Run server wrapper

    Run server.py from the commandline

## Step 8: Run OpenWebUI as a Docker container 

    Verify Open WebUI in Docker Desktop

## Step 9: Connect Open WebUI to Your Local Agent

To connect and include your custom local-error-check-agent server in Open WebUI, you need to link your running FastAPI wrapper as an OpenAI-compatible API connection.

Since Open WebUI is running inside a Docker container (open_webui_graphrag) and your FastAPI server is running on your host machine, follow these step-by-step instructions to configure it properly:

1. Ensure Your FastAPI Server is Running on the Host

    Open a terminal on your Mac, navigate to your project directory, activate your virtual environment, and start your wrapper server on port 8000:

    ```bash
        python3 serer.py

    ```

    Your server exposes local-error-check-agent through the OpenAI-compatible endpoint at http://localhost:8000/v1

2. Configure the Connections Settings in Open WebUI

    a. Open your browser at http://localhost:3000 (where Open WebUI is running).

    b. Click on your Profile icon (bottom left corner) and select Admin Panel (or Settings).

    c. Navigate to Settings -> Connections (or General depending on your Open WebUI version).

    d. Look for the OpenAI API section.

    e. Add a new connection with the following details:
        API Base URL: [http://host.docker.internal:8000/v1](http://host.docker.internal:8000/v1)
        (Note: host.docker.internal allows the Docker container to talk to your host machine's port 8000).
        API Key: not-needed (or any dummy string like 12345).

    f. Click the Save button (or refresh the connection). Open WebUI will automatically query /v1/models and register graphrag-router-agent.


## Step 10: Create error conditions in the web app

Go to http://127.0.0.1:5001/
Click on the menu and select errors


## Step 11: Give prompts in Open WebUI

Sample Prompts:

Specific Error Check ("Out of Memory"):
Open http://localhost:5001/oom and check if an "Out of memory" error is displayed on the screen.

General Error Detection (500 Server Error):
Visit http://localhost:5001/server-error, inspect what is shown on the page, and report any errors or HTTP status issues.

Form Validation Error Check:
Go to http://localhost:5001/form-check, fill #threshold with "150", click #apply_btn, and report whether a validation error appears on screen.

Healthy / No-Error Page Check:
Check http://localhost:5001/ and verify whether the page is healthy with no error messages displayed.


====




