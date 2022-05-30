module git.sr.ht/~sircmpwn/git.sr.ht/api

go 1.14

require (
	git.sr.ht/~sircmpwn/core-go v0.0.0-20220530120843-d0bf1153ada4
	git.sr.ht/~sircmpwn/dowork v0.0.0-20210820133136-d3970e97def3
	github.com/99designs/gqlgen v0.17.2
	github.com/Masterminds/squirrel v1.4.0
	github.com/agnivade/levenshtein v1.1.1 // indirect
	github.com/go-git/go-git/v5 v5.0.0
	github.com/google/uuid v1.1.1
	github.com/hashicorp/golang-lru v0.5.4 // indirect
	github.com/lib/pq v1.8.0
	github.com/matryer/moq v0.2.6 // indirect
	github.com/minio/minio-go/v7 v7.0.5
	github.com/mitchellh/mapstructure v1.3.2 // indirect
	github.com/prometheus/common v0.30.0 // indirect
	github.com/smartystreets/goconvey v1.6.4 // indirect
	github.com/urfave/cli/v2 v2.4.0 // indirect
	github.com/vektah/dataloaden v0.2.1-0.20190515034641-a19b9a6e7c9e
	github.com/vektah/gqlparser/v2 v2.4.1
	golang.org/x/sys v0.0.0-20220319134239-a9b59b0215f8 // indirect
)

replace github.com/go-git/go-git/v5 => git.sr.ht/~sircmpwn/go-git/v5 v5.0.0-20220207102101-70373b908e0a
