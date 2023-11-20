module git.sr.ht/~sircmpwn/git.sr.ht

go 1.16

require (
	git.sr.ht/~sircmpwn/core-go v0.0.0-20231024101834-7f5f70710c33
	git.sr.ht/~sircmpwn/dowork v0.0.0-20221010085743-46c4299d76a1
	github.com/99designs/gqlgen v0.17.36
	github.com/Masterminds/squirrel v1.5.4
	github.com/go-git/go-git/v5 v5.0.0
	github.com/google/uuid v1.3.0
	github.com/hashicorp/golang-lru v0.5.4 // indirect
	github.com/lib/pq v1.10.9
	github.com/minio/minio-go/v7 v7.0.61
	github.com/vektah/dataloaden v0.2.1-0.20190515034641-a19b9a6e7c9e
	github.com/vektah/gqlparser/v2 v2.5.8
)

replace github.com/go-git/go-git/v5 => git.sr.ht/~sircmpwn/go-git/v5 v5.0.0-20221206091532-7155ffca4d7a
