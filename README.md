# Flask Docker Application with Multiple Modules

This project demonstrates a **Flask web application** structured with **3 modules** using **Flask blueprints**, a **Docker setup** for easy containerization, and **data volume mounting** for persistent data storage.

## Project Structure

The project is organized as follows:

```
flask-docker-app/
│
├── app/                # Main Flask application
│   ├── __init__.py     # Initializes Flask app and registers blueprints
│   ├── config.py       # Configuration settings for the app
│   ├── extensions.py   # Flask extensions (e.g. DB, Cache, etc.)
│   │
│   ├── module1/        # Module 1 blueprint (module1 routes and views)
│   │   ├── __init__.py
│   │   └── routes.py   # Routes for module 1
│   │
│   ├── module2/        # Module 2 blueprint (module2 routes and views)
│   │   ├── __init__.py
│   │   └── routes.py   # Routes for module 2
│   │
│   ├── module3/        # Module 3 blueprint (module3 routes and views)
│   │   ├── __init__.py
│   │   └── routes.py   # Routes for module 3
│   │
│   ├── templates/      # HTML templates (Jinja2)
│   └── static/         # Static assets (CSS, JS, Images)
│
├── data/               # Folder for persistent data (e.g., files, datasets)
│   └── example.json    # Example data file used by the app
│
├── tests/              # Optional folder for unit tests
│   └── test_basic.py   # Example test file
│
├── Dockerfile          # Dockerfile to build the image for Flask app
├── docker-compose.yml  # Docker Compose configuration for running the app
├── requirements.txt    # Python dependencies for the app
└── README.md           # Project description and instructions
```

## Core Concepts

### Flask Modules (Blueprints)

The app is divided into **three modules** (`module1`, `module2`, `module3`), each defined as a **Flask blueprint**. Blueprints allow for better organization and separation of concerns, making it easier to manage larger Flask applications.

* **`module1/`**: Contains the routes for the first module. Can be accessed via `/module1`.
* **`module2/`**: Contains the routes for the second module. Can be accessed via `/module2`.
* **`module3/`**: Contains the routes for the third module. Can be accessed via `/module3`. It also includes an endpoint (`/data`) to fetch data from a file stored in the `data/` folder.

### Docker Setup

The project is set up to run inside a **Docker container**, which allows for consistent environments across different machines.

* The `Dockerfile` specifies how to build the app's image.
* **Docker Compose** (`docker-compose.yml`) helps to manage the services, including setting up the app container, mounting the code for live updates, and ensuring data persistence.

### Mounted Data Folder

The `data/` folder is **mounted from the host system** into the Docker container to persist data (e.g., uploaded files, JSON data, logs) across container restarts. This means that changes made to files inside the `data/` folder on your machine will be reflected inside the container.

---

## Setting Up The Application

### Prerequisites

Make sure you have the following installed:

* **Docker**: For containerization and running the app
* **Docker Compose**: To manage multi-container applications (included with Docker Desktop)

### Install Dependencies

First, make sure you have the required Python dependencies by creating a virtual environment and installing them:

```bash
pip install -r requirements.txt
```

### Running the App with Docker

1. **Build and run the application** using Docker Compose:

```bash
docker-compose up --build
```

2. **Access the application** in your browser at `http://localhost:5100`.

   * **Module 1**: `http://localhost:5100/module1`
   * **Module 2**: `http://localhost:5100/module2`
   * **Module 3**: `http://localhost:5100/module3`

   You can also access the data from the `/data` endpoint in **Module 3** (`http://localhost:5100/module3/data`).

### If Docker logs spam `Error: Could not import 'app'`

This usually means Flask failed during startup and the container keeps restarting.

1. Stop the loop:

```bash
docker compose down
```

2. Rebuild cleanly and start again:

```bash
docker compose build --no-cache flask
docker compose up
```

3. If it still fails, run a one-shot import check to see the real traceback:

```bash
docker compose run --rm flask conda run --no-capture-output -n pcd python -c "import app; print('import-ok')"
```

---

## Directory Breakdown

* **`app/`**: This is the core application code.

  * **`__init__.py`**: Initializes the Flask app and registers the blueprints.
  * **`config.py`**: Configuration settings such as debug mode, secret keys, etc.
  * **`module1/`, `module2/`, `module3/`**: Each module is organized as a separate Flask **blueprint**, containing routes and views.
  * **`templates/`**: Jinja2 HTML templates.
  * **`static/`**: Static assets like CSS, JavaScript, and images.

* **`data/`**: This folder holds persistent data like JSON files, logs, etc. It is mounted from the host system into the Docker container.

* **`tests/`**: (Optional) Unit tests for the application. These can be added as the app evolves.

* **`Dockerfile`**: Defines the Docker image used to run the Flask app.

* **`docker-compose.yml`**: Manages the Flask app container, volumes, and ports.

* **`requirements.txt`**: Python package dependencies for the project.

---

## Development Workflow

### Hot Reloading

During development, the Flask app will automatically reload when you make changes to the code. This is enabled by mounting the project directory as a volume in Docker.

* Code changes will be reflected immediately without needing to rebuild the container.

### Data Persistence

The `data/` folder is **mounted as a volume** inside the container, which ensures that any data (such as uploaded files or logs) remains persistent even when the container is restarted or rebuilt.

---

## Testing the App

You can test individual modules by sending HTTP requests to the endpoints:

* **Module 1**: `http://localhost:5100/module1`
* **Module 2**: `http://localhost:5100/module2`
* **Module 3**: `http://localhost:5100/module3`
* **Module 3 Data**: `http://localhost:5100/module3/data`

To add unit tests, create test files inside the `tests/` directory. You can use **pytest** or any other testing framework.

---

## Running in Production

For production environments, you can use a WSGI server like **Gunicorn** and deploy behind a reverse proxy like **Nginx**. A production-grade setup would require additional configurations for better performance, security, and scalability.

---

## How to run the full flow (Login -> Sanitize -> Generate -> Audit)

1. Login to get an admin token (default password: `admin-pass`):

```bash
curl -X POST http://localhost:5100/login -H 'Content-Type: application/json' -d '{"password":"admin-pass"}'
# {"status":"ok","token":"..."}
```

2. Sanitize a prompt:

```bash
curl -X POST http://localhost:5100/sanitize -H 'Content-Type: application/json' -d '{"role":"client","prompt":"My phone is 012-3456789"}'
# {"status":"sanitized","sanitized_prompt":"My phone is [REDACTED_PHONE]"}
```

3. Generate via Privacy Firewall (raw prompts are tokenized before LLM dispatch):

```bash
curl -X POST http://localhost:5100/generate -H 'Content-Type: application/json' -d '{"prompt":"Ali from KL, phone 012-3456789, email ali@example.com"}'
# Response can be:
# - {"status":"ok", ...}       -> forwarded to LLM
# - {"status":"challenge", ...} -> medium-risk, requires review
# - {"status":"denied", ...}    -> high-risk blocked by policy engine
```

4. (Admin only) Detokenize for legal/audit workflows:

```bash
curl -X POST http://localhost:5100/detokenize \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <admin-token>' \
  -d '{"text":"[NAME_...], phone [PHONE_...], email [EMAIL_...]"}'
```

5. View audit summary (admin only):

```bash
curl -H 'Authorization: Bearer <token>' http://localhost:5100/audit/summary
```

6. Dashboard (passes token via query):

Open in browser: `http://localhost:5100/audit/dashboard?token=<token>`

7. High-fidelity prototype landing page:

Open in browser: `http://localhost:5100/`

7. Run adversarial privacy benchmark (admin only):

```bash
curl -H 'Authorization: Bearer <token>' http://localhost:5100/privacy/benchmark
```

8. Get policy threshold calibration recommendation (admin only):

```bash
curl -H 'Authorization: Bearer <token>' http://localhost:5100/privacy/calibrate
```

9. Optional: enable spaCy NER backend (Phase 3):

```bash
pip install spacy
python -m spacy download en_core_web_sm
export PRIVACY_NER_BACKEND=spacy
export PRIVACY_NER_MODEL=en_core_web_sm
```

10. Optional: enable transformer NER backend (Phase 4):

```bash
pip install transformers torch
export PRIVACY_NER_BACKEND=transformer
export PRIVACY_NER_TRANSFORMER_MODEL=dslim/bert-base-NER
```

11. Auto-tune policy thresholds from audit telemetry (admin only):

```bash
curl -H 'Authorization: Bearer <token>' 'http://localhost:5100/privacy/autotune?hours=168&min_samples=10'
```

12. View benchmark trend history (admin only):

```bash
curl -H 'Authorization: Bearer <token>' 'http://localhost:5100/privacy/benchmark/history?limit=20'
```

13. List benchmark dataset versions (admin only):

```bash
curl -H 'Authorization: Bearer <token>' 'http://localhost:5100/privacy/benchmark/datasets'
```

14. Run multilingual benchmark dataset v2 (admin only):

```bash
curl -H 'Authorization: Bearer <token>' 'http://localhost:5100/privacy/benchmark?dataset_version=v2&split=all'
```

15. Run cross-split evaluation (train/validation/test):

```bash
curl -H 'Authorization: Bearer <token>' 'http://localhost:5100/privacy/benchmark?dataset_version=v2&mode=cross_split&persist=0'
```

16. Run local benchmark gate (same logic as CI):

```bash
python3 scripts/check_benchmark_gate.py --dataset-version v2 --split all
```

17. Generate reproducible phase6 evaluation artifacts:

```bash
python3 scripts/run_phase6_evaluation.py
```

---

## License

MIT License

---

## Conclusion

This project is a **modular Flask web application** with a **Docker setup** for easy development and deployment. By organizing the application into **blueprints**, we ensure that the code remains scalable and easy to maintain. Additionally, by mounting the `data/` folder, we ensure that important data is persisted even across Docker container restarts.

Feel free to modify and extend the project for your specific needs!

---