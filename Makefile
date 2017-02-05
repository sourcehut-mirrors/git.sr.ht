# Run `make` to compile static assets
# Run `make watch` to recompile whenever a change is made

.PHONY: all static watch clean

SCRIPTS+=$(patsubst js/%.js,static/%.js,$(wildcard js/*.js))
_STATIC:=$(patsubst _static/%,static/%,$(wildcard _static/*))

SRHT_PATH?=/usr/lib/python3.6/site-packages/srht

static/%: _static/%
	@mkdir -p static/
	cp $< $@

static/main.css: scss/*.scss ${SRHT_PATH}/scss/*.scss
	@mkdir -p static/
	sassc -I${SRHT_PATH}/scss scss/main.scss $@

static/%.js: js/%.js
	@mkdir -p static/
	cp $< $@

static: $(SCRIPTS) $(_STATIC) static/main.css

all: static

clean:
	rm -rf static

watch:
	while inotifywait \
		-e close_write js/ \
		-e close_write scss/ \
		-e close_write _static/; \
		do make; done
