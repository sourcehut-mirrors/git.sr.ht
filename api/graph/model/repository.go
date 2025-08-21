package model

import (
	"context"
	"database/sql"
	"strconv"
	"time"

	sq "github.com/Masterminds/squirrel"
	"github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/plumbing"

	"git.sr.ht/~sircmpwn/core-go/database"
	"git.sr.ht/~sircmpwn/core-go/model"
)

type Repository struct {
	ID          int       `json:"id"`
	Created     time.Time `json:"created"`
	Updated     time.Time `json:"updated"`
	Name        string    `json:"name"`
	Description *string   `json:"description"`
	Readme      *string   `json:"readme"`

	Path       string
	OwnerID    int
	Visibility Visibility

	alias  string
	repo   *RepoWrapper
	fields *database.ModelFields
}

func (r *Repository) Repo() *RepoWrapper {
	if r.repo != nil {
		return r.repo
	}
	repo, err := git.PlainOpen(r.Path)
	if err != nil {
		panic(err)
	}
	r.repo = WrapRepo(r, repo)
	return r.repo
}

func (r *Repository) Head() *Reference {
	r.Repo().Lock()
	ref, err := r.Repo().Head()
	r.repo.Unlock()
	if err != nil {
		if err == plumbing.ErrReferenceNotFound {
			return nil
		}
		panic(err)
	}
	return &Reference{Ref: ref, Repo: r}
}

func (r *Repository) As(alias string) *Repository {
	r.alias = alias
	return r
}

func (r *Repository) Alias() string {
	return r.alias
}

func (r *Repository) Table() string {
	return "repository"
}

func (r *Repository) Fields() *database.ModelFields {
	if r.fields != nil {
		return r.fields
	}
	r.fields = &database.ModelFields{
		Fields: []*database.FieldMap{
			{"id", "id", &r.ID},
			{"created", "created", &r.Created},
			{"updated", "updated", &r.Updated},
			{"name", "name", &r.Name},
			{"description", "description", &r.Description},
			{"visibility", "visibility", &r.Visibility},
			{"readme", "readme", &r.Readme},

			// Always fetch:
			{"id", "", &r.ID},
			{"path", "", &r.Path},
			{"owner_id", "", &r.OwnerID},
			{"updated", "", &r.Updated},
		},
	}
	return r.fields
}

func (r *Repository) QueryWithCursor(ctx context.Context,
	runner sq.BaseRunner, q sq.SelectBuilder,
	cur *model.Cursor) ([]*Repository, *model.Cursor) {
	var (
		err  error
		rows *sql.Rows
	)

	if cur.Next != "" {
		ts, _ := strconv.ParseInt(cur.Next, 10, 64)
		updated := time.UnixMicro(ts).UTC()
		q = q.Where(database.WithAlias(r.alias, "updated")+"<= ?", updated)
	}
	q = q.
		OrderBy(database.WithAlias(r.alias, "updated") + " DESC").
		Limit(uint64(cur.Count + 1))

	if rows, err = q.RunWith(runner).QueryContext(ctx); err != nil {
		panic(err)
	}
	defer rows.Close()

	var repos []*Repository
	for rows.Next() {
		var repo Repository
		if err := rows.Scan(database.Scan(ctx, &repo)...); err != nil {
			panic(err)
		}
		repos = append(repos, &repo)
	}

	if len(repos) > cur.Count {
		cur = &model.Cursor{
			Count:  cur.Count,
			Next:   strconv.FormatInt(repos[len(repos)-1].Updated.UnixMicro(), 10),
			Search: cur.Search,
		}
		repos = repos[:cur.Count]
	} else {
		cur = nil
	}

	return repos, cur
}

func (r *Repository) DefaultSearch(query sq.SelectBuilder,
	term string) (sq.SelectBuilder, error) {
	name := database.WithAlias(r.alias, "name")
	desc := database.WithAlias(r.alias, "description")
	return query.
		Where(sq.Or{
			sq.Expr(name+` ILIKE '%' || ? || '%'`, term),
			sq.Expr(desc+` ILIKE '%' || ? || '%'`, term),
		}), nil
}
