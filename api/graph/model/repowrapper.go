package model

import (
	"sync"

	"github.com/go-git/go-git/v5"
)

type RepoWrapper struct {
	*git.Repository
	sync.Mutex
}

func WrapRepo(repo *git.Repository) *RepoWrapper {
	return &RepoWrapper{repo, sync.Mutex{}}
}
