module git.sr.ht/~sircmpwn/git.sr.ht/api

go 1.14

require (
	git.sr.ht/~sircmpwn/core-go v0.0.0-20220217133755-ebf93be7318f
	git.sr.ht/~sircmpwn/dowork v0.0.0-20210820133136-d3970e97def3
	github.com/99designs/gqlgen v0.14.0
	github.com/Masterminds/squirrel v1.4.0
	github.com/go-git/go-git/v5 v5.0.0
	github.com/google/uuid v1.1.1
	github.com/hashicorp/golang-lru v0.5.4 // indirect
	github.com/lib/pq v1.8.0
	github.com/minio/minio-go/v7 v7.0.5
	github.com/mitchellh/mapstructure v1.3.2 // indirect
	github.com/prometheus/common v0.30.0 // indirect
	github.com/smartystreets/goconvey v1.6.4 // indirect
	github.com/vektah/gqlparser/v2 v2.2.0
)

replace github.com/go-git/go-git/v5 => git.sr.ht/~sircmpwn/go-git/v5 v5.0.0-20220207102101-70373b908e0a
