package loaders

//go:generate ./gen RepositoriesByIDLoader int api/graph/model.Repository
//go:generate ./gen UsersByNameLoader string api/graph/model.User
//go:generate ./gen UsersByIDLoader int api/graph/model.User

import (
	"context"
	"database/sql"
	"errors"
	"net/http"
	"time"

	"github.com/lib/pq"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/auth"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/model"
)

var loadersCtxKey = &contextKey{"user"}
type contextKey struct {
	name string
}

type Loaders struct {
	UsersByID        UsersByIDLoader
	UsersByName      UsersByNameLoader
	RepositoriesByID RepositoriesByIDLoader
}

func fetchUsersByID(ctx context.Context,
	db *sql.DB) func (ids []int) ([]*model.User, []error) {
	return func (ids []int) ([]*model.User, []error) {
		var (
			err  error
			rows *sql.Rows
		)
		if rows, err = db.QueryContext(ctx,`
			SELECT `+(&model.User{}).Columns(ctx, "u")+`
			FROM "user" u
			WHERE u.id = ANY($1)`, pq.Array(ids)); err != nil {
			panic(err)
		}
		defer rows.Close()

		usersById := map[int]*model.User{}
		for rows.Next() {
			user := model.User{}
			if err := rows.Scan(user.Fields(ctx)...); err != nil {
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

func fetchUsersByName(ctx context.Context,
	db *sql.DB) func (names []string) ([]*model.User, []error) {
	return func (names []string) ([]*model.User, []error) {
		var (
			err  error
			rows *sql.Rows
		)
		if rows, err = db.QueryContext(ctx,`
			SELECT `+(&model.User{}).Columns(ctx, "u")+`
			FROM "user" u
			WHERE u.username = ANY($1)`, pq.Array(names)); err != nil {
			panic(err)
		}
		defer rows.Close()

		usersByName := map[string]*model.User{}
		for rows.Next() {
			user := model.User{}
			if err := rows.Scan(user.Fields(ctx)...); err != nil {
				panic(err)
			}
			usersByName[user.Username] = &user
		}
		if err = rows.Err(); err != nil {
			panic(err)
		}

		users := make([]*model.User, len(names))
		for i, name := range names {
			users[i] = usersByName[name]
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
		)
		if rows, err = db.QueryContext(ctx, `
			SELECT DISTINCT `+(&model.Repository{}).Columns(ctx, "repo")+`
			FROM repository repo
			FULL OUTER JOIN
				access ON repo.id = access.repo_id
			WHERE
				repo.id = ANY($2)
				AND (access.user_id = $1
					OR repo.owner_id = $1
					OR repo.visibility != 'private')
			`, auth.ForContext(ctx).ID, pq.Array(ids)); err != nil {
			panic(err)
		}
		defer rows.Close()

		reposById := map[int]*model.Repository{}
		for rows.Next() {
			repo := model.Repository{}
			if err := rows.Scan(repo.Fields(ctx)...); err != nil {
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
				UsersByID: UsersByIDLoader{
					maxBatch: 100,
					wait: 1 * time.Millisecond,
					fetch: fetchUsersByID(r.Context(), db),
				},
				UsersByName: UsersByNameLoader{
					maxBatch: 100,
					wait: 1 * time.Millisecond,
					fetch: fetchUsersByName(r.Context(), db),
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
