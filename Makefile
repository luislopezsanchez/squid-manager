# ============================================
# SquidManager - Makefile
# ============================================
# Comandos útiles para desarrollo y operación
# ============================================

.PHONY: help up down rebuild logs ps backup restore status test clean

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Levanta todos los contenedores
	docker compose up -d

down: ## Detiene los contenedores (sin borrar datos)
	docker compose down

rebuild: ## Reconstruye las imágenes y levanta
	docker compose build
	docker compose up -d

logs: ## Ver logs de todos los contenedores
	docker compose logs -f

logs-squid: ## Ver logs del contenedor Squid
	docker compose logs -f squid

ps: ## Ver estado de los contenedores
	docker compose ps

status: ## Ver estado + uso de recursos
	docker compose ps
	docker stats --no-stream

backup: ## Crear backup de la BD a ./backups/
	@mkdir -p backups
	docker exec squidmgr-db pg_dump -U squid squidmanager > backups/squidmanager_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Backup creado en backups/"

restore: ## Restaurar backup de la BD (usage: make restore FILE=backups/xxx.sql)
	@test -n "$(FILE)" || (echo "Especifica FILE=backups/archivo.sql"; exit 1)
	docker exec -i squidmgr-db psql -U squid squidmanager < $(FILE)

test: ## Ejecutar tests del backend
	docker exec squidmgr-backend pytest -v

clean: ## Eliminar contenedores Y volúmenes (¡borra todos los datos!)
	docker compose down -v

reset: ## Reiniciar el backend (recarga código)
	docker compose restart backend
