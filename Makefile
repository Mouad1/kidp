.PHONY: dashboard generate generate-dry assemble niche-research help

help:
	@echo "KDP Pipeline Commands:"
	@echo "  make dashboard                      - Start the web dashboard UI on localhost:8000"
	@echo "  make generate BOOK=book-name        - Generate images for a book"
	@echo "  make generate-dry BOOK=book-name    - Preview prompts for a book without calling Gemini API"
	@echo "  make assemble BOOK=book-name        - Assemble PDF for a book"
	@echo "  make niche-research CSV=...         - Run niche research script (via CLI)"
	@echo ""
	@echo "Examples:"
	@echo "  make generate BOOK=book2-modern-anime"
	@echo "  make assemble BOOK=book1-90s-legends"

dashboard:
	@set -a && . .env.local && set +a && python3 dashboard/app.py

niche-research:
	@if [ -z "$(CSV)" ] || [ -z "$(NICHE)" ]; then \
		echo "Error: Usage: make niche-research CSV=path/to/data.csv NICHE='book topic'"; \
		exit 1; \
	fi
	@set -a && . .env.local && set +a && python3 pipeline/niche_research.py --csv "$(CSV)" --niche "$(NICHE)"

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
