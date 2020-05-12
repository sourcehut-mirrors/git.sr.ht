package model

import (
	"context"
	"database/sql"
	"time"
	"strconv"

	"github.com/go-git/go-git/v5"
	sq "github.com/Masterminds/squirrel"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/database"
)

type Repository struct {
	ID             int        `json:"id"`
	Created        time.Time  `json:"created"`
	Updated        time.Time  `json:"updated"`
	Name           string     `json:"name"`
	Description    *string    `json:"description"`
	Visibility     Visibility `json:"visibility"`
	Cursor         *Cursor    `json:"cursor"`
	UpstreamURL    *string    `json:"upstreamUrl"`
	Objects        []Object   `json:"objects"`
	Log            []*Commit  `json:"log"`
	Tree           *Tree      `json:"tree"`
	File           *Blob      `json:"file"`
	RevparseSingle Object     `json:"revparse_single"`

	Path    string
	OwnerID int

	alias string
	repo  *git.Repository
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

func (r *Repository) Select(ctx context.Context) []string {
	return append(database.ColumnsFor(ctx, r.alias, map[string]string{
		"id":          "id",
		"created":     "created",
		"updated":     "updated",
		"name":        "name",
		"description": "description",
		"visibility":  "visibility",
		"upstreamUrl": "upstream_uri",
	}),
		database.WithAlias(r.alias, "path"),
		database.WithAlias(r.alias, "owner_id"),
		database.WithAlias(r.alias, "updated"))
}

func (r *Repository) As(alias string) *Repository {
	r.alias = alias
	return r
}

func (r *Repository) Fields(ctx context.Context) []interface{} {
	fields := database.FieldsFor(ctx, map[string]interface{}{
		"id":           &r.ID,
		"created":      &r.Created,
		"updated":      &r.Updated,
		"name":         &r.Name,
		"description":  &r.Description,
		"visibility":   &r.Visibility,
		"upstream_url": &r.UpstreamURL,
	})
	return append(fields, &r.Path, &r.OwnerID, &r.Updated)
}

func (r *Repository) QueryWithCursor(ctx context.Context,
	db *sql.DB, q sq.SelectBuilder, cur *Cursor) ([]*Repository, *Cursor) {
	var (
		err  error
		rows *sql.Rows
	)

	if cur.Next != "" {
		ts, _ := strconv.ParseInt(cur.Next, 10, 64)
		updated := time.Unix(ts, 0)
		q = q.Where(database.WithAlias(r.alias, "updated") + "<= ?", updated)
	}
	q = q.
		OrderBy(database.WithAlias(r.alias, "updated") + " DESC").
		Limit(uint64(cur.Count + 1))

	if rows, err = q.RunWith(db).QueryContext(ctx); err != nil {
		panic(err)
	}
	defer rows.Close()

	var repos []*Repository
	for rows.Next() {
		var repo Repository
		if err := rows.Scan(repo.Fields(ctx)...); err != nil {
			panic(err)
		}
		repos = append(repos, &repo)
	}

	if len(repos) > cur.Count {
		cur = &Cursor{
			Count:  cur.Count,
			Next:   strconv.FormatInt(repos[len(repos)-1].Updated.Unix(), 10),
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
			sq.Expr(name + ` ILIKE '%' || ? || '%'`, term),
			sq.Expr(desc + ` ILIKE '%' || ? || '%'`, term),
		}), nil
}
