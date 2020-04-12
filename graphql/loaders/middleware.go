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
	UsersByID        UserLoader
	RepositoriesByID RepositoriesByIDLoader
}

func fetchUsersByID(ctx context.Context,
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

func fetchRepositoriesByID(ctx context.Context,
	db *sql.DB) func (ids []int) ([]*model.Repository, []error) {

	return func (ids []int) ([]*model.Repository, []error) {
		var (
			err  error
			rows *sql.Rows
			repo model.Repository
		)
		if rows, err = db.QueryContext(ctx, `
			SELECT DISTINCT `+repo.Rows()+`
			FROM repository repo
			FULL OUTER JOIN
				access ON repo.id = access.repo_id
			WHERE
				repo.id = ANY($1)
				AND (access.user_id = 1
					OR repo.owner_id = 1
					OR repo.visibility != 'private')
			`, pq.Array(ids)); err != nil {
			panic(err)
		}
		defer rows.Close()

		reposById := map[int]*model.Repository{}
		for rows.Next() {
			repo := model.Repository{}
			if err := rows.Scan(repo.Fields()...); err != nil {
				panic(err)
			}
			reposById[repo.ID] = &repo
		}
		if err = rows.Err(); err != nil {
			panic(err)
		}

		repos := make([]*model.Repository, len(ids))
		for i, id := range ids {
			repos[i] = reposById[id]
		}

		return repos, nil
	}
}

func Middleware(db *sql.DB) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := context.WithValue(r.Context(), loadersCtxKey, &Loaders{
				UsersByID: UserLoader{
					maxBatch: 100,
					wait: 1 * time.Millisecond,
					fetch: fetchUsersByID(r.Context(), db),
				},
				RepositoriesByID: RepositoriesByIDLoader{
					maxBatch: 100,
					wait: 1 * time.Millisecond,
					fetch: fetchRepositoriesByID(r.Context(), db),
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
