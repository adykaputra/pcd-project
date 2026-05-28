# Use Miniforge as the runtime base image
FROM condaforge/mambaforge:latest AS runtime

# Set the working directory inside the container
WORKDIR /usr/src/app

# Copy the environment.yml to the container and create the conda environment
COPY environment.yml .

# Create conda environment from environment.yml (environment.yml defines `name: pcd`)
RUN conda env create -f environment.yml

# Use a bash shell for subsequent RUN/CMD
SHELL ["/bin/bash", "-lc"]

# Copy the entire project into the container
COPY . /usr/src/app

# Expose the port Flask will run on
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=app:create_app
ENV FLASK_ENV=production
ENV PYTHONPATH=/usr/src/app

# Default command: production-grade WSGI runtime
CMD ["conda", "run", "--no-capture-output", "-n", "pcd", "gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "app:create_app()"]

# Optional test stage:
#   docker build --target test .
FROM runtime AS test
RUN conda run -n pcd pytest -q --ignore=pcd-project --ignore-glob='*/pcd-project/*'
