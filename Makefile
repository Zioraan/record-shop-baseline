.PHONY: up down logs seed eval eval-all typecheck clean

up:
	docker compose up -d --build

down:
	docker compose down

clean:
	docker compose down -v

logs:
	docker compose logs -f --tail=100

seed:
	docker compose exec api python -m common.seed_cli

# Usage: make eval PHASE=1
eval:
	pytest evals/phase$(PHASE) -v

eval-all:
	pytest evals -v

typecheck:
	cd frontends/storefront && npm run typecheck
