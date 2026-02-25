.PHONY: help build up down restart logs clean

help:
	@echo Available commands:
	@echo   build		- Build the Docker image
	@echo   up		- Start the application
	@echo   down		- Stop the application
	@echo   restart	- Restart the application
	@echo   logs		- Show application logs
	@echo   clean		- Clean up containers and images

build:
	docker compose build

up:
	docker compose up --no-build

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f app

clean:
	docker compose down --rmi all --volumes --remove-orphans