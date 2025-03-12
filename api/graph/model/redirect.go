package model

import (
	"time"

	"git.sr.ht/~sircmpwn/core-go/database"
)

type Redirect struct {
	ID      int       `json:"id"`
	Created time.Time `json:"created"`
	Name    string    `json:"name"`
	Path    string    `json:"path"`

	OwnerID      int
	RepositoryID int

	alias  string
	fields *database.ModelFields
}

func (r *Redirect) As(alias string) *Redirect {
	r.alias = alias
	return r
}

func (r *Redirect) Alias() string {
	return r.alias
}

func (r *Redirect) Table() string {
	return "redirect"
}

func (r *Redirect) Fields() *database.ModelFields {
	if r.fields != nil {
		return r.fields
	}
	r.fields = &database.ModelFields{
		Fields: []*database.FieldMap{
			{"id", "id", &r.ID},
			{"created", "created", &r.Created},
			{"name", "name", &r.Name},
			{"name", "name", &r.Name},
			{"path", "originalPath", &r.Path},

			// Always fetch:
			{"id", "", &r.ID},
			{"owner_id", "", &r.OwnerID},
			{"new_repo_id", "", &r.RepositoryID},
		},
	}
	return r.fields
}
