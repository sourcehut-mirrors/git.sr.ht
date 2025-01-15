PREFIX?=/usr/local
BINDIR?=$(PREFIX)/bin
LIBDIR?=$(PREFIX)/lib
SHAREDIR?=$(PREFIX)/share/sourcehut

SERVICE=git.sr.ht
STATICDIR=$(SHAREDIR)/static/$(SERVICE)

SASSC?=sassc
SASSC_INCLUDE=-I$(SHAREDIR)/scss/

BINARIES=\
	$(SERVICE)-api \
	$(SERVICE)-dispatch \
	$(SERVICE)-keys \
	$(SERVICE)-shell \
	$(SERVICE)-update-hook

all: all-bin all-share

install: install-bin install-share

clean: clean-bin clean-share

all-bin: $(BINARIES)

all-share: static/main.min.css

install-bin: all-bin
	mkdir -p $(BINDIR)
	for bin in $(BINARIES); \
	do \
		install -Dm755 $$bin $(BINDIR)/; \
	done

install-share: all-share
	mkdir -p $(STATICDIR)
	install -Dm644 static/*.css $(STATICDIR)
	install -Dm644 api/graph/schema.graphqls $(SHAREDIR)/$(SERVICE).graphqls

clean-bin:
	rm -f $(BINARIES)

clean-share:
	rm -f static/main.min.css static/main.css

.PHONY: all all-bin all-share
.PHONY: install install-bin install-share
.PHONY: clean clean-bin clean-share

static/main.css: scss/main.scss
	mkdir -p $(@D)
	$(SASSC) $(SASSC_INCLUDE) $< $@

static/main.min.css: static/main.css
	minify -o $@ $<
	cp $@ $(@D)/main.min.$$(sha256sum $@ | cut -c1-8).css

api/loaders/*_gen.go &: api/loaders/generate.go api/loaders/gen go.sum
	cd api && go generate ./loaders

api/graph/api/generated.go: api/graph/schema.graphqls api/graph/generate.go go.sum api/loaders/*_gen.go
	cd api && go generate ./graph

$(SERVICE)-api: api/graph/api/generated.go api/loaders/*_gen.go
	go build -o $@ ./api

$(SERVICE)-dispatch:
	go build -o $@ ./dispatch

$(SERVICE)-keys:
	go build -o $@ ./keys

$(SERVICE)-shell:
	go build -o $@ ./shell

$(SERVICE)-update-hook:
	go build -o $@ ./update-hook

# Always rebuild
.PHONY: $(BINARIES)
