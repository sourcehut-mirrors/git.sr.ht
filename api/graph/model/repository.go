package model

import (
	"time"

	"github.com/go-git/go-git/v5"
)

type Repository struct {
	ID                int          `json:"id"`
	Created           time.Time    `json:"created"`
	Updated           time.Time    `json:"updated"`
	Name              string       `json:"name"`
	Description       *string      `json:"description"`
	Visibility        Visibility   `json:"visibility"`
	UpstreamURL       *string      `json:"upstreamUrl"`
	AccessControlList []*ACL       `json:"accessControlList"`
	Objects           []Object     `json:"objects"`
	Log               []*Commit    `json:"log"`
	Tree              *Tree        `json:"tree"`
	File              *Blob        `json:"file"`
	RevparseSingle    Object       `json:"revparse_single"`

	Path    string
	OwnerID int

	repo    *git.Repository
}

func (r *Repository) Rows() string {
	return `
		repo.id,
		repo.created, repo.updated,
		repo.name, repo.description,
		repo.visibility,
		repo.upstream_uri,
		repo.path,
		repo.owner_id
	`
}

func (r *Repository) Fields() []interface{} {
	return []interface{}{
		&r.ID,
		&r.Created, &r.Updated,
		&r.Name, &r.Description,
		&r.Visibility,
		&r.UpstreamURL,
		&r.Path,
		&r.OwnerID,
	}
}

func (r *Repository) Repo() *git.Repository {
	if r.repo != nil {
		return r.repo
	}
	var err error
	r.repo, err = git.PlainOpen(r.Path)
	if err != nil {
		panic(err)
	}
	return r.repo
}

func (r *Repository) Head() *Reference {
	ref, err := r.Repo().Head()
	if err != nil {
		panic(err)
	}
	return &Reference{Ref: ref, Repo: r.repo}
}
