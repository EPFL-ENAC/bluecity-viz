PY := uv run python
SRC := $(wildcard notebooks/src/*.py)
NB  := $(patsubst notebooks/src/%.py,notebooks/%.ipynb,$(SRC))

.PHONY: all sync notebooks run-all clean

all: notebooks

sync:
	uv sync

# Generate .ipynb from py:percent sources
notebooks: $(NB)

notebooks/%.ipynb: notebooks/src/%.py
	$(PY) -m sppdptw.nb_convert $< $@

# Execute every notebook in order (fails loudly on any error)
run-all: notebooks
	for nb in notebooks/0*.ipynb; do \
		uv run jupyter nbconvert --to notebook --execute --inplace $$nb || exit 1; \
	done

clean:
	rm -rf outputs data/cache notebooks/*.ipynb
