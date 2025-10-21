# Makefile for the fm40-updater application

# Use a variable for the image name for easier updates
IMAGE_NAME = fm40-updater:latest

# Phony targets are not files. This prevents make from getting confused by a file named 'build' or 'run'.
.PHONY: build run

# Build the Docker image
# The Dockerfile is in the current directory, so the context is '.'
build:
	docker build -t $(IMAGE_NAME) .

# Run the Docker container
# This command mounts the local 'inputs' and 'outputs' directories
# into the container and runs the default command specified in the Dockerfile.
run:
	@echo "--> Running Docker container..."
	docker run --rm -it \
		-v "$(CURDIR)/inputs:/inputs" \
		-v "$(CURDIR)/outputs:/outputs" \
		$(IMAGE_NAME) \