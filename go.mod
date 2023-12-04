module git.sr.ht/~sircmpwn/git.sr.ht

go 1.16

require (
	git.sr.ht/~sircmpwn/core-go v0.0.0-20231024101834-7f5f70710c33
	git.sr.ht/~sircmpwn/dowork v0.0.0-20221010085743-46c4299d76a1
	git.sr.ht/~sircmpwn/scm.sr.ht/srht-keys v0.0.0-20211208105818-48011a5e6b35
	git.sr.ht/~turminal/go-fnmatch v0.0.0-20211021204744-1a55764af6de
	github.com/99designs/gqlgen v0.17.36
	github.com/Masterminds/squirrel v1.5.4
	github.com/fernet/fernet-go v0.0.0-20211208181803-9f70042a33ee
	github.com/go-git/go-git/v5 v5.0.0
	github.com/go-redis/redis/v8 v8.11.5
	github.com/google/shlex v0.0.0-20191202100458-e7afc7fbc510
	github.com/google/uuid v1.3.0
	github.com/hashicorp/golang-lru v0.5.4 // indirect
	github.com/lib/pq v1.10.9
	github.com/mattn/go-runewidth v0.0.9
	github.com/minio/minio-go/v7 v7.0.61
	github.com/pkg/errors v0.9.1
	github.com/vaughan0/go-ini v0.0.0-20130923145212-a98ad7ee00ec
	github.com/vektah/dataloaden v0.2.1-0.20190515034641-a19b9a6e7c9e
	github.com/vektah/gqlparser v1.3.1
	github.com/vektah/gqlparser/v2 v2.5.8
	gopkg.in/yaml.v2 v2.4.0
)

replace github.com/go-git/go-git/v5 => git.sr.ht/~sircmpwn/go-git/v5 v5.0.0-20221206091532-7155ffca4d7a
