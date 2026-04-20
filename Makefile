# Makefile for common dev tasks
.PHONY: test docker-test test-local

# Prefer docker-based test; make test will invoke docker-test
test: docker-test

# Build Dockerfile up to the 'test' stage which runs pytest inside the conda env
docker-test:
	docker build --target test -t pcd-test .

# Local test (requires conda and environment.yml)
test-local:
	conda env create -f environment.yml || true
	conda run -n pcd pytest -q
