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

2. **Access the application** in your browser at `http://localhost:5000`.

   * **Module 1**: `http://localhost:5000/module1`
   * **Module 2**: `http://localhost:5000/module2`
   * **Module 3**: `http://localhost:5000/module3`

   You can also access the data from the `/data` endpoint in **Module 3** (`http://localhost:5000/module3/data`).

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

* **Module 1**: `http://localhost:5000/module1`
* **Module 2**: `http://localhost:5000/module2`
* **Module 3**: `http://localhost:5000/module3`
* **Module 3 Data**: `http://localhost:5000/module3/data`

To add unit tests, create test files inside the `tests/` directory. You can use **pytest** or any other testing framework.

---

## Running in Production

For production environments, you can use a WSGI server like **Gunicorn** and deploy behind a reverse proxy like **Nginx**. A production-grade setup would require additional configurations for better performance, security, and scalability.

---

## How to run the full flow (Login -> Sanitize -> Generate -> Audit)

1. Login to get an admin token (default password: `admin-pass`):

```bash
curl -X POST http://localhost:5000/login -H 'Content-Type: application/json' -d '{"password":"admin-pass"}'
# {"status":"ok","token":"..."}
```

2. Sanitize a prompt:

```bash
curl -X POST http://localhost:5000/sanitize -H 'Content-Type: application/json' -d '{"role":"client","prompt":"My phone is 012-3456789"}'
# {"status":"sanitized","sanitized_prompt":"My phone is [REDACTED_PHONE]"}
```

3. Generate via LLM Proxy (ensure sanitized_prompt is sent):

```bash
curl -X POST http://localhost:5000/generate -H 'Content-Type: application/json' -d '{"sanitized_prompt":"Hello world"}'
```

4. View audit summary (admin only):

```bash
curl -H 'Authorization: Bearer <token>' http://localhost:5000/audit/summary
```

5. Dashboard (passes token via query):

Open in browser: `http://localhost:5000/audit/dashboard?token=<token>`

---

## License

MIT License

---

## Conclusion

This project is a **modular Flask web application** with a **Docker setup** for easy development and deployment. By organizing the application into **blueprints**, we ensure that the code remains scalable and easy to maintain. Additionally, by mounting the `data/` folder, we ensure that important data is persisted even across Docker container restarts.

Feel free to modify and extend the project for your specific needs!

---