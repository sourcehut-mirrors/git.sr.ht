package model

import (
	"context"
	"database/sql"
	"strconv"
	"time"

	sq "github.com/Masterminds/squirrel"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/database"
)

// TODO: Drop updated column from database
type ACL struct {
	ID         int         `json:"id"`
	Created    time.Time   `json:"created"`
	Mode       *AccessMode `json:"mode"`

	RepoID int
	UserID int

	alias  string
}

func (acl *ACL) As(alias string) *ACL {
	acl.alias = alias
	return acl
}

func (acl *ACL) Select(ctx context.Context) []string {
	cols := database.ColumnsFor(ctx, acl.alias, map[string]string{
		"id":      "id",
		"created": "created",
		"mode":    "mode",
	})
	return append(cols,
		database.WithAlias(acl.alias, "id"),
		database.WithAlias(acl.alias, "repo_id"),
		database.WithAlias(acl.alias, "user_id"))
}

func (acl *ACL) Fields(ctx context.Context) []interface{} {
	fields := database.FieldsFor(ctx, map[string]interface{}{
		"id":      &acl.ID,
		"created": &acl.Created,
		"mode":    &acl.Mode,
	})
	return append(fields, &acl.ID, &acl.RepoID, &acl.UserID)
}

func (acl *ACL) QueryWithCursor(ctx context.Context,
	db *sql.DB, q sq.SelectBuilder, cur *Cursor) ([]*ACL, *Cursor) {
	var (
		err  error
		rows *sql.Rows
	)

	if cur.Next != "" {
		next, _ := strconv.Atoi(cur.Next)
		q = q.Where(database.WithAlias(acl.alias, "id") + "<= ?", next)
	}
	q = q.
		OrderBy(database.WithAlias(acl.alias, "id") + " DESC").
		Limit(uint64(cur.Count + 1))

	if rows, err = q.RunWith(db).QueryContext(ctx); err != nil {
		panic(err)
	}
	defer rows.Close()

	var acls []*ACL
	for rows.Next() {
		var acl ACL
		if err := rows.Scan(acl.Fields(ctx)...); err != nil {
			panic(err)
		}
		acls = append(acls, &acl)
	}

	if len(acls) > cur.Count {
		cur = &Cursor{
			Count:  cur.Count,
			Next:   strconv.Itoa(acls[len(acls)-1].ID),
			Search: cur.Search,
		}
		acls = acls[:cur.Count]
	} else {
		cur = nil
	}

	return acls, cur
}
