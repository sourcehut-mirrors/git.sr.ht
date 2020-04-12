package loaders

import (
	"context"
	"database/sql"
	"errors"
	"net/http"
	"time"

	"github.com/lib/pq"

	"git.sr.ht/~sircmpwn/git.sr.ht/graphql/graph/model"
)

var loadersCtxKey = &contextKey{"user"}
type contextKey struct {
	name string
}

type Loaders struct {
	UsersById UserLoader
}

func fetchUsersById(ctx context.Context,
	db *sql.DB) func (ids []int) ([]*model.User, []error) {

	return func (ids []int) ([]*model.User, []error) {
		var (
			err  error
			rows *sql.Rows
			user model.User
		)
		if rows, err = db.QueryContext(ctx,`
			SELECT `+user.Rows()+`
			FROM "user"
			WHERE "user".id = ANY($1)`, pq.Array(ids)); err != nil {
			panic(err)
		}
		defer rows.Close()

		usersById := map[int]*model.User{}
		for rows.Next() {
			user := model.User{}
			if err := rows.Scan(user.Fields()...); err != nil {
				panic(err)
			}
			usersById[user.ID] = &user
		}
		if err = rows.Err(); err != nil {
			panic(err)
		}

		users := make([]*model.User, len(ids))
		for i, id := range ids {
			users[i] = usersById[id]
		}

		return users, nil
	}
}

func Middleware(db *sql.DB) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := context.WithValue(r.Context(), loadersCtxKey, &Loaders{
				UsersById: UserLoader{
					maxBatch: 100,
					wait: 1 * time.Millisecond,
					fetch: fetchUsersById(r.Context(), db),
				},
			})
			r = r.WithContext(ctx)
			next.ServeHTTP(w, r)
		})
	}
}

func ForContext(ctx context.Context) *Loaders {
	raw, ok := ctx.Value(loadersCtxKey).(*Loaders)
	if !ok {
		panic(errors.New("Invalid data loaders context"))
	}
	return raw
}
