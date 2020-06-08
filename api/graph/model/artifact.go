package model

import (
	"context"
	"database/sql"
	"strconv"
	"time"

	sq "github.com/Masterminds/squirrel"

	"git.sr.ht/~sircmpwn/gql.sr.ht/database"
	"git.sr.ht/~sircmpwn/gql.sr.ht/model"
)

type Artifact struct {
	ID         int         `json:"id"`
	Created    time.Time   `json:"created"`
	Filename   string      `json:"filename"`
	Checksum   string      `json:"checksum"`
	Size       int         `json:"size"`

	alias  string
	commit string
}

func (a *Artifact) As(alias string) *Artifact {
	a.alias = alias
	return a
}

func (a *Artifact) Select(ctx context.Context) []string {
	cols := database.ColumnsFor(ctx, a.alias, map[string]string{
		"id":       "id",
		"created":  "created",
		"filename": "filename",
		"checksum": "checksum",
		"size":     "size",
	})
	return append(cols,
		database.WithAlias(a.alias, "commit"),
		database.WithAlias(a.alias, "filename"))
}

func (a *Artifact) Fields(ctx context.Context) []interface{} {
	fields := database.FieldsFor(ctx, map[string]interface{}{
		"id":       &a.ID,
		"created":  &a.Created,
		"filename": &a.Filename,
		"checksum": &a.Checksum,
		"size":     &a.Size,
	})
	return append(fields, &a.commit, &a.Filename)
}

func (a *Artifact) QueryWithCursor(ctx context.Context,
	db *sql.DB, q sq.SelectBuilder, cur *model.Cursor) ([]*Artifact, *model.Cursor) {
	var (
		err  error
		rows *sql.Rows
	)

	if cur.Next != "" {
		next, _ := strconv.Atoi(cur.Next)
		q = q.Where(database.WithAlias(a.alias, "id") + "<= ?", next)
	}
	q = q.
		OrderBy(database.WithAlias(a.alias, "id") + " DESC").
		Limit(uint64(cur.Count + 1))

	if rows, err = q.RunWith(db).QueryContext(ctx); err != nil {
		panic(err)
	}
	defer rows.Close()

	var artifacts []*Artifact
	for rows.Next() {
		var a Artifact
		if err := rows.Scan(a.Fields(ctx)...); err != nil {
			panic(err)
		}
		artifacts = append(artifacts, &a)
	}

	if len(artifacts) > cur.Count {
		cur = &model.Cursor{
			Count:  cur.Count,
			Next:   strconv.Itoa(artifacts[len(artifacts)-1].ID),
			Search: cur.Search,
		}
		artifacts = artifacts[:cur.Count]
	} else {
		cur = nil
	}

	return artifacts, cur
}
