SRHT_PATH?=/usr/lib/python3.10/site-packages/srht
MODULE=gitsrht/
include ${SRHT_PATH}/Makefile

all: api gitsrht-dispatch gitsrht-keys gitsrht-shell gitsrht-update-hook

api/loaders/*_gen.go: api/loaders/generate.go api/loaders/gen go.sum
	cd api && go generate ./loaders

api/graph/api/generated.go: api/graph/schema.graphqls api/graph/generate.go go.sum
	cd api && go generate ./graph

api: api/graph/api/generated.go api/loaders/*_gen.go
	cd api && go build

gitsrht-dispatch:
	cd gitsrht-dispatch && go build

gitsrht-keys:
	cd gitsrht-keys && go build

gitsrht-shell:
	cd gitsrht-shell && go build

gitsrht-update-hook:
	cd gitsrht-update-hook && go build

.PHONY: all api gitsrht-dispatch gitsrht-keys gitsrht-shell gitsrht-update-hook
