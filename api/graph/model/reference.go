package model

import (
	"github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/plumbing"
)

type Reference struct {
	Repo *git.Repository
	Ref  *plumbing.Reference
}

func (r *Reference) Follow() Object {
	ref, err := r.Repo.Reference(r.Ref.Name(), true)
	if err != nil {
		panic(err)
	}
	obj, err := LookupObject(r.Repo, ref.Hash())
	if err != nil {
		panic(err)
	}
	return obj
}

func (r *Reference) Name() string {
	return string(r.Ref.Name())
}

func (r *Reference) Target() string {
	if r.Ref.Type() == plumbing.HashReference {
		return r.Ref.Hash().String()
	} else {
		return string(r.Ref.Target())
	}
}
