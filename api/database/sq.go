package database

import (
	"context"
	"fmt"

	sq "github.com/Masterminds/squirrel"
)

type Selectable interface {
	Select(ctx context.Context) []string
	Fields(ctx context.Context) []interface{}
}

func Select(ctx context.Context, cols ...interface{}) sq.SelectBuilder {
	q := sq.Select().PlaceholderFormat(sq.Dollar)
	for _, col := range cols {
		switch col := col.(type) {
		case string:
			q = q.Columns(col)
		case []string:
			q = q.Columns(col...)
		case Selectable:
			q = q.Columns(col.Select(ctx)...)
		default:
			panic(fmt.Errorf("Unknown selectable type %T", col))
		}
	}
	return q
}
