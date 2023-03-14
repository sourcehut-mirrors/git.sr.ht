module git.sr.ht/~sircmpwn/git.sr.ht

go 1.16

require (
	git.sr.ht/~sircmpwn/core-go v0.0.0-20221025082458-3e69641ef307
	git.sr.ht/~sircmpwn/dowork v0.0.0-20210820133136-d3970e97def3
	github.com/99designs/gqlgen v0.17.20
	github.com/Masterminds/squirrel v1.4.0
	github.com/go-git/go-git/v5 v5.0.0
	github.com/google/uuid v1.1.1
	github.com/lib/pq v1.8.0
	github.com/minio/minio-go/v7 v7.0.5
	github.com/mitchellh/mapstructure v1.3.2 // indirect
	github.com/prometheus/common v0.30.0 // indirect
	github.com/smartystreets/goconvey v1.6.4 // indirect
	github.com/urfave/cli/v2 v2.20.2 // indirect
	github.com/vektah/dataloaden v0.2.1-0.20190515034641-a19b9a6e7c9e
	github.com/vektah/gqlparser/v2 v2.5.1
	golang.org/x/mod v0.6.0 // indirect
)

replace github.com/go-git/go-git/v5 => git.sr.ht/~sircmpwn/go-git/v5 v5.0.0-20221206091532-7155ffca4d7a
