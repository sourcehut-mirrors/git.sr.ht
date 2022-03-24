SRHT_PATH?=/usr/lib/python3.9/site-packages/srht
MODULE=gitsrht/
include ${SRHT_PATH}/Makefile

all: api gitsrht-dispatch gitsrht-keys gitsrht-shell gitsrht-update-hook

api:
	cd api && go generate ./loaders
	cd api && go generate ./graph
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
