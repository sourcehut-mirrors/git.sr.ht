package model

import (
	"context"
	"strings"
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
	Objects           []Object     `json:"objects"`
	Log               []*Commit    `json:"log"`
	Tree              *Tree        `json:"tree"`
	File              *Blob        `json:"file"`
	RevparseSingle    Object       `json:"revparse_single"`

	Path    string
	OwnerID int

	repo    *git.Repository
}

func (r *Repository) Columns(ctx context.Context, tbl string) string {
	columns := ColumnsFor(ctx, map[string]string{
		"id": "id",
		"created": "created",
		"updated": "updated",
		"name": "name",
		"description": "description",
		"visibility": "visibility",
		"upstreamUrl": "upstream_uri",
	}, tbl)
	return strings.Join(append(columns, tbl + ".path", tbl + ".owner_id"), ", ")
}

func (r *Repository) Fields(ctx context.Context) []interface{} {
	fields := FieldsFor(ctx, map[string]interface{}{
		"id": &r.ID,
		"created": &r.Created,
		"updated": &r.Updated,
		"name": &r.Name,
		"description": &r.Description,
		"visibility": &r.Visibility,
		"upstream_url": &r.UpstreamURL,
	})
	return append(fields, &r.Path, &r.OwnerID)
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
