package model

import (
	"context"
	"database/sql"
	"strconv"
	"time"

	sq "github.com/Masterminds/squirrel"

	"git.sr.ht/~sircmpwn/core-go/database"
	"git.sr.ht/~sircmpwn/core-go/model"
)

// TODO: Drop updated column from database
type ACL struct {
	ID         int         `json:"id"`
	Created    time.Time   `json:"created"`
	Mode       *AccessMode `json:"mode"`

	RepoID int
	UserID int

	alias  string
	fields *database.ModelFields
}

func (acl *ACL) As(alias string) *ACL {
	acl.alias = alias
	return acl
}

func (acl *ACL) Alias() string {
	return acl.alias
}

func (acl *ACL) Table() string {
	return "access"
}

func (acl *ACL) Fields() *database.ModelFields {
	if acl.fields != nil {
		return acl.fields
	}
	acl.fields = &database.ModelFields{
		Fields: []*database.FieldMap{
			{ "id", "id", &acl.ID },
			{ "created", "created", &acl.Created },
			{ "mode", "mode", &acl.Mode },

			// Always fetch:
			{ "id", "", &acl.ID },
			{ "repo_id", "", &acl.RepoID },
			{ "user_id", "", &acl.UserID },
		},
	}
	return acl.fields
}

func (acl *ACL) QueryWithCursor(ctx context.Context,
	runner sq.BaseRunner, q sq.SelectBuilder,
	cur *model.Cursor) ([]*ACL, *model.Cursor) {
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

	if rows, err = q.RunWith(runner).QueryContext(ctx); err != nil {
		panic(err)
	}
	defer rows.Close()

	var acls []*ACL
	for rows.Next() {
		var acl ACL
		if err := rows.Scan(database.Scan(ctx, &acl)...); err != nil {
			panic(err)
		}
		acls = append(acls, &acl)
	}

	if len(acls) > cur.Count {
		cur = &model.Cursor{
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
