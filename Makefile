.PHONY: init run test coverage demo docker-up docker-down
init:
	python3 scripts/init_env.py
run:
	python3 scripts/run_local.py
test:
	python3 -m pytest -q
coverage:
	python3 -m coverage run --source=hub,scripts -m pytest -q
	python3 -m coverage report -m
demo:
	python3 scripts/demo_scenario.py
docker-up:
	docker compose up -d --build
docker-down:
	docker compose down
