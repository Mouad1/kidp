.PHONY: dashboard storefront storefront-check storefront-send-test generate generate-dry assemble help

help:
	@echo "KDP Pipeline Commands:"
	@echo "  make dashboard                      - Start the web dashboard UI on localhost:8000"
	@echo "  make storefront                     - Load env, print storefront checks, then start dashboard"
	@echo "  make storefront-check               - Print storefront checks only (no server start)"
	@echo "  make storefront-send-test EMAIL=...  - Send a real test email to verify delivery"
	@echo "  make generate BOOK=book-name        - Generate images for a book"
	@echo "  make generate-dry BOOK=book-name    - Preview prompts for a book without calling Gemini API"
	@echo "  make assemble BOOK=book-name        - Assemble PDF for a book"
	@echo ""
	@echo "Examples:"
	@echo "  make generate BOOK=book2-modern-anime"
	@echo "  make assemble BOOK=book1-90s-legends"

dashboard:
	@set -a && . .env.local && set +a && python3 dashboard/app.py

storefront:
	@set -a; [ -f .env.local ] && . .env.local || true; set +a; \
	python3 scripts/storefront_doctor.py; \
	python3 dashboard/app.py

storefront-check:
	@set -a; [ -f .env.local ] && . .env.local || true; set +a; \
	python3 scripts/storefront_doctor.py

storefront-send-test:
	@if [ -z "$(EMAIL)" ]; then \
		echo "Error: EMAIL is required. Usage: make storefront-send-test EMAIL=you@example.com"; \
		exit 1; \
	fi
	@set -a; [ -f .env.local ] && . .env.local || true; set +a; \
	python3 scripts/storefront_send_test.py "$(EMAIL)"

generate:
	@if [ -z "$(BOOK)" ]; then \
		echo "Error: BOOK is required. Usage: make generate BOOK=book-name"; \
		exit 1; \
	fi
	python3 pipeline/generate.py --book $(BOOK)

generate-dry:
	@if [ -z "$(BOOK)" ]; then \
		echo "Error: BOOK is required. Usage: make generate-dry BOOK=book-name"; \
		exit 1; \
	fi
	python3 pipeline/generate.py --book $(BOOK) --dry-run

assemble:
	@if [ -z "$(BOOK)" ]; then \
		echo "Error: BOOK is required. Usage: make assemble BOOK=book-name"; \
		exit 1; \
	fi
	python3 pipeline/assemble.py --book $(BOOK)
