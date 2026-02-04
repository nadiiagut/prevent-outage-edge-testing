.PHONY: up down logs test clean

up:
	docker-compose up -d
	@echo ""
	@echo "Demo environment started:"
	@echo "  Edge proxy: http://localhost:8080"
	@echo "  Health:     http://localhost:8080/health"
	@echo "  Metrics:    http://localhost:8080/metrics"
	@echo ""
	@echo "Test endpoints:"
	@echo "  curl http://localhost:8080/"
	@echo "  curl http://localhost:8080/echo?test=1"
	@echo "  curl http://localhost:8080/faulty/"
	@echo ""

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	@echo "Testing backend selection consistency..."
	@for i in 1 2 3 4 5; do curl -s http://localhost:8080/echo?key=test1 | grep -o '"server":"[^"]*"'; done
	@echo ""
	@echo "Testing health endpoint..."
	@curl -s http://localhost:8080/health
	@echo ""
	@echo "Testing faulty endpoint (expect 503)..."
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/faulty/
	@echo ""

clean:
	docker-compose down -v --remove-orphans
