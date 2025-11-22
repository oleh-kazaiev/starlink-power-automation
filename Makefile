.PHONY: help up stop restart rebuild

up:
	docker compose up -d

stop:
	docker compose stop

restart:
	docker compose restart

rebuild:
	docker compose up -d --build

